"""
Grid Trading Engine
Core logic for grid trading strategies on Chinese stocks
"""
import math
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from .grid_trading_db import GridTradingDatabase
from .akshare_fetcher import AKShareFetcher


class GridTradingEngine:
    """Grid trading strategy engine"""
    
    def __init__(self, db: GridTradingDatabase, akshare_fetcher: AKShareFetcher):
        self.db = db
        self.akshare_fetcher = akshare_fetcher
        self.active_strategies = {}  # strategy_id -> strategy_data
    
    def generate_grid_levels(self, lower_price: float, upper_price: float, 
                            grid_count: int, grid_type: str = 'ARITHMETIC') -> List[Dict]:
        """
        Generate grid price levels
        
        Returns list of grid levels with prices
        """
        grid_levels = []
        
        if grid_type == 'ARITHMETIC':
            # Arithmetic grid: equal price steps
            grid_step = (upper_price - lower_price) / grid_count
            for i in range(grid_count + 1):
                price = lower_price + (i * grid_step)
                grid_levels.append({
                    "level": i,
                    "price": round(price, 2)
                })
        else:
            # Geometric grid: equal percentage steps
            ratio = upper_price / lower_price
            for i in range(grid_count + 1):
                price = lower_price * (ratio ** (i / grid_count))
                grid_levels.append({
                    "level": i,
                    "price": round(price, 2)
                })
        
        return grid_levels
    
    def get_current_price(self, symbol: str) -> Optional[float]:
        """Get current market price for a symbol"""
        try:
            stocks = self.akshare_fetcher.get_stock_realtime_quotes(
                symbols=[symbol],
                bypass_rate_limit=True
            )
            if stocks and len(stocks) > 0:
                price_str = stocks[0].get('price', '0')
                try:
                    return float(price_str)
                except (ValueError, TypeError):
                    return None
        except Exception as e:
            print(f"[GridEngine] Error fetching price for {symbol}: {e}")
        return None
    
    def initialize_strategy(self, strategy_id: int) -> bool:
        """Initialize a strategy - generate grid and place initial orders"""
        strategy = self.db.get_strategy(strategy_id)
        if not strategy:
            return False
        
        # Get current price
        current_price = self.get_current_price(strategy['symbol'])
        if not current_price:
            print(f"[GridEngine] Could not get current price for {strategy['symbol']}")
            return False
        
        # Check if price is within range
        if current_price < strategy['lower_price'] or current_price > strategy['upper_price']:
            print(f"[GridEngine] Current price {current_price} is outside grid range [{strategy['lower_price']}, {strategy['upper_price']}]")
            return False
        
        # Generate grid levels
        grid_levels = self.generate_grid_levels(
            strategy['lower_price'],
            strategy['upper_price'],
            strategy['grid_count'],
            strategy['grid_type']
        )
        
        # Find current price's position in grid
        current_level = None
        for i, level in enumerate(grid_levels):
            if i < len(grid_levels) - 1:
                if grid_levels[i]['price'] <= current_price <= grid_levels[i + 1]['price']:
                    current_level = i
                    break
        
        if current_level is None:
            current_level = len(grid_levels) - 1
        
        # Place initial orders
        # Buy orders below current price
        for i in range(current_level):
            price = grid_levels[i]['price']
            quantity = strategy['order_size']
            self.db.create_order(strategy_id, i, price, 'BUY', quantity)
        
        # Sell orders above current price
        for i in range(current_level + 1, len(grid_levels)):
            price = grid_levels[i]['price']
            quantity = strategy['order_size']
            self.db.create_order(strategy_id, i, price, 'SELL', quantity)
        
        # Update strategy status
        self.db.update_strategy_status(strategy_id, 'RUNNING', current_price)
        
        # Store in active strategies
        strategy['grid_levels'] = grid_levels
        strategy['current_level'] = current_level
        self.active_strategies[strategy_id] = strategy
        
        print(f"[GridEngine] Strategy {strategy_id} initialized with {len(grid_levels)} grid levels")
        return True
    
    def check_and_fill_orders(self, strategy_id: int):
        """Check if any pending orders should be filled based on current price"""
        if strategy_id not in self.active_strategies:
            return
        
        strategy = self.active_strategies[strategy_id]
        current_price = self.get_current_price(strategy['symbol'])
        
        if not current_price:
            return
        
        # Update strategy current price
        self.db.update_strategy_status(strategy_id, 'RUNNING', current_price)
        strategy['current_price'] = current_price
        
        # Get pending orders
        pending_orders = self.db.get_strategy_orders(strategy_id, 'PENDING')
        
        for order in pending_orders:
            order_price = order['price']
            order_side = order['side']
            
            # Check if order should be filled
            # For BUY orders: fill if current price <= order price
            # For SELL orders: fill if current price >= order price
            should_fill = False
            if order_side == 'BUY' and current_price <= order_price:
                should_fill = True
            elif order_side == 'SELL' and current_price >= order_price:
                should_fill = True
            
            if should_fill:
                self._fill_order(order, current_price, strategy)
    
    def _fill_order(self, order: Dict, fill_price: float, strategy: Dict):
        """Handle order fill"""
        strategy_id = order['strategy_id']
        order_id = order['id']
        grid_level = order['grid_level']
        side = order['side']
        quantity = order['quantity']
        
        # Mark order as filled
        self.db.fill_order(order_id, fill_price)
        
        # Update position
        if side == 'BUY':
            self.db.update_position(strategy_id, strategy['symbol'], quantity, fill_price, fill_price)
            # Place sell order at next higher grid level
            if grid_level < strategy['grid_count']:
                next_level = grid_level + 1
                next_price = strategy['grid_levels'][next_level]['price']
                self.db.create_order(strategy_id, next_level, next_price, 'SELL', quantity)
        else:  # SELL
            self.db.update_position(strategy_id, strategy['symbol'], -quantity, fill_price, fill_price)
            # Place buy order at next lower grid level
            if grid_level > 0:
                next_level = grid_level - 1
                next_price = strategy['grid_levels'][next_level]['price']
                self.db.create_order(strategy_id, next_level, next_price, 'BUY', quantity)
        
        # Calculate realized PnL (simplified - assumes FIFO)
        # For now, we'll calculate it when positions are closed
        realized_pnl = 0  # Will be calculated when opposite side fills
        
        # Record trade
        fee = fill_price * quantity * 0.0003  # 0.03% fee (typical for Chinese stocks)
        self.db.create_trade(strategy_id, strategy['symbol'], side, quantity, fill_price, realized_pnl, fee)
        
        print(f"[GridEngine] Order {order_id} filled: {side} {quantity} @ {fill_price}")
    
    def check_risk_controls(self, strategy_id: int) -> Tuple[bool, Optional[str]]:
        """Check risk controls - returns (is_safe, error_message)"""
        if strategy_id not in self.active_strategies:
            return False, "Strategy not active"
        
        strategy = self.active_strategies[strategy_id]
        current_price = self.get_current_price(strategy['symbol'])
        
        if not current_price:
            return True, None  # Can't check without price
        
        # Check stop loss
        if strategy['stop_loss'] and current_price <= strategy['stop_loss']:
            return False, f"Stop loss triggered at {current_price}"
        
        # Check price breakout
        if current_price < strategy['lower_price'] or current_price > strategy['upper_price']:
            return False, f"Price {current_price} outside grid range"
        
        # Check max orders (prevent order explosion)
        pending_orders = self.db.get_strategy_orders(strategy_id, 'PENDING')
        if len(pending_orders) > strategy['grid_count'] * 2:
            return False, "Too many pending orders"
        
        return True, None
    
    def stop_strategy(self, strategy_id: int, close_positions: bool = False):
        """Stop a strategy"""
        if strategy_id not in self.active_strategies:
            return
        
        # Cancel all pending orders
        pending_orders = self.db.get_strategy_orders(strategy_id, 'PENDING')
        for order in pending_orders:
            self.db.cancel_order(order['id'])
        
        # Close positions if requested
        if close_positions:
            # This would require market orders - for now just mark as stopped
            pass
        
        # Update strategy status
        self.db.update_strategy_status(strategy_id, 'STOPPED')
        
        # Remove from active strategies
        if strategy_id in self.active_strategies:
            del self.active_strategies[strategy_id]
        
        print(f"[GridEngine] Strategy {strategy_id} stopped")
    
    def pause_strategy(self, strategy_id: int):
        """Pause a strategy (cancel orders but keep positions)"""
        if strategy_id not in self.active_strategies:
            return
        
        # Cancel all pending orders
        pending_orders = self.db.get_strategy_orders(strategy_id, 'PENDING')
        for order in pending_orders:
            self.db.cancel_order(order['id'])
        
        # Update strategy status
        self.db.update_strategy_status(strategy_id, 'PAUSED')
        
        print(f"[GridEngine] Strategy {strategy_id} paused")
    
    def resume_strategy(self, strategy_id: int):
        """Resume a paused strategy"""
        strategy = self.db.get_strategy(strategy_id)
        if not strategy or strategy['status'] != 'PAUSED':
            return False
        
        # Rebuild grid and place orders
        return self.initialize_strategy(strategy_id)
    
    def get_strategy_state(self, strategy_id: int) -> Optional[Dict]:
        """Get current state of a strategy"""
        strategy = self.db.get_strategy(strategy_id)
        if not strategy:
            return None
        
        # Get orders
        orders = self.db.get_strategy_orders(strategy_id)
        
        # Get positions/stats
        stats = self.db.get_strategy_stats(strategy_id)
        
        # Get current price
        current_price = self.get_current_price(strategy['symbol'])
        
        # Generate grid levels for visualization
        grid_levels = self.generate_grid_levels(
            strategy['lower_price'],
            strategy['upper_price'],
            strategy['grid_count'],
            strategy['grid_type']
        )
        
        return {
            "strategy": strategy,
            "orders": orders,
            "stats": stats,
            "current_price": current_price,
            "grid_levels": grid_levels
        }

