"""
Database module for Grid Trading strategies
Stores strategies, orders, positions, and trading history
"""
import sqlite3
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from pathlib import Path


class GridTradingDatabase:
    """SQLite database for grid trading strategies and orders"""
    
    def __init__(self, db_path: str = "data/grid_trading.db"):
        self.db_path = db_path
        self._ensure_db_dir()
        self._init_database()
    
    def _ensure_db_dir(self):
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)
    
    def _init_database(self):
        """Initialize database tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Strategies table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS strategies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                name TEXT,
                grid_type TEXT NOT NULL DEFAULT 'ARITHMETIC',
                lower_price REAL NOT NULL,
                upper_price REAL NOT NULL,
                grid_count INTEGER NOT NULL,
                capital REAL NOT NULL,
                order_size_type TEXT NOT NULL DEFAULT 'FIXED',
                order_size REAL NOT NULL,
                take_profit REAL,
                stop_loss REAL,
                paper_trading INTEGER NOT NULL DEFAULT 1,
                status TEXT NOT NULL DEFAULT 'STOPPED',
                current_price REAL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                started_at TEXT,
                stopped_at TEXT
            )
        ''')
        
        # Orders table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy_id INTEGER NOT NULL,
                grid_level INTEGER NOT NULL,
                price REAL NOT NULL,
                side TEXT NOT NULL,
                quantity REAL NOT NULL,
                status TEXT NOT NULL DEFAULT 'PENDING',
                filled_price REAL,
                filled_at TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (strategy_id) REFERENCES strategies(id)
            )
        ''')
        
        # Positions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy_id INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                quantity REAL NOT NULL,
                avg_price REAL NOT NULL,
                current_price REAL,
                unrealized_pnl REAL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (strategy_id) REFERENCES strategies(id)
            )
        ''')
        
        # Trades history table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy_id INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                quantity REAL NOT NULL,
                price REAL NOT NULL,
                realized_pnl REAL DEFAULT 0,
                fee REAL DEFAULT 0,
                traded_at TEXT NOT NULL,
                FOREIGN KEY (strategy_id) REFERENCES strategies(id)
            )
        ''')
        
        # Create indices
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_strategies_symbol ON strategies(symbol)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_strategies_status ON strategies(status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_orders_strategy ON orders(strategy_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_positions_strategy ON positions(strategy_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_trades_strategy ON trades(strategy_id)')
        
        conn.commit()
        conn.close()
    
    def create_strategy(self, strategy_data: Dict) -> int:
        """Create a new grid trading strategy"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        cursor.execute('''
            INSERT INTO strategies 
            (symbol, name, grid_type, lower_price, upper_price, grid_count, capital,
             order_size_type, order_size, take_profit, stop_loss, paper_trading,
             status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            strategy_data.get('symbol'),
            strategy_data.get('name', ''),
            strategy_data.get('grid_type', 'ARITHMETIC'),
            strategy_data.get('lower_price'),
            strategy_data.get('upper_price'),
            strategy_data.get('grid_count'),
            strategy_data.get('capital'),
            strategy_data.get('order_size_type', 'FIXED'),
            strategy_data.get('order_size'),
            strategy_data.get('take_profit'),
            strategy_data.get('stop_loss'),
            1 if strategy_data.get('paper_trading', True) else 0,
            'STOPPED',
            now,
            now
        ))
        
        strategy_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return strategy_id
    
    def get_strategy(self, strategy_id: int) -> Optional[Dict]:
        """Get strategy by ID"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM strategies WHERE id = ?', (strategy_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return dict(row)
        return None
    
    def get_all_strategies(self, status: Optional[str] = None) -> List[Dict]:
        """Get all strategies, optionally filtered by status"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if status:
            cursor.execute('SELECT * FROM strategies WHERE status = ? ORDER BY created_at DESC', (status,))
        else:
            cursor.execute('SELECT * FROM strategies ORDER BY created_at DESC')
        
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    def update_strategy_status(self, strategy_id: int, status: str, current_price: Optional[float] = None):
        """Update strategy status"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        if status == 'RUNNING':
            cursor.execute('''
                UPDATE strategies 
                SET status = ?, current_price = ?, started_at = ?, updated_at = ?
                WHERE id = ?
            ''', (status, current_price, now, now, strategy_id))
        elif status == 'STOPPED':
            cursor.execute('''
                UPDATE strategies 
                SET status = ?, stopped_at = ?, updated_at = ?
                WHERE id = ?
            ''', (status, now, now, strategy_id))
        else:
            cursor.execute('''
                UPDATE strategies 
                SET status = ?, current_price = ?, updated_at = ?
                WHERE id = ?
            ''', (status, current_price, now, strategy_id))
        
        conn.commit()
        conn.close()
    
    def create_order(self, strategy_id: int, grid_level: int, price: float, 
                     side: str, quantity: float) -> int:
        """Create a new order"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        cursor.execute('''
            INSERT INTO orders 
            (strategy_id, grid_level, price, side, quantity, status, created_at)
            VALUES (?, ?, ?, ?, ?, 'PENDING', ?)
        ''', (strategy_id, grid_level, price, side, quantity, now))
        
        order_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return order_id
    
    def fill_order(self, order_id: int, filled_price: float):
        """Mark order as filled"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        cursor.execute('''
            UPDATE orders 
            SET status = 'FILLED', filled_price = ?, filled_at = ?
            WHERE id = ?
        ''', (filled_price, now, order_id))
        
        conn.commit()
        conn.close()
    
    def cancel_order(self, order_id: int):
        """Cancel an order"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('UPDATE orders SET status = ? WHERE id = ?', ('CANCELLED', order_id))
        conn.commit()
        conn.close()
    
    def get_strategy_orders(self, strategy_id: int, status: Optional[str] = None) -> List[Dict]:
        """Get orders for a strategy"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if status:
            cursor.execute('''
                SELECT * FROM orders 
                WHERE strategy_id = ? AND status = ?
                ORDER BY grid_level
            ''', (strategy_id, status))
        else:
            cursor.execute('''
                SELECT * FROM orders 
                WHERE strategy_id = ?
                ORDER BY grid_level
            ''', (strategy_id,))
        
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    def create_trade(self, strategy_id: int, symbol: str, side: str, 
                     quantity: float, price: float, realized_pnl: float = 0, fee: float = 0):
        """Record a completed trade"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        cursor.execute('''
            INSERT INTO trades 
            (strategy_id, symbol, side, quantity, price, realized_pnl, fee, traded_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (strategy_id, symbol, side, quantity, price, realized_pnl, fee, now))
        
        conn.commit()
        conn.close()
    
    def get_strategy_trades(self, strategy_id: int) -> List[Dict]:
        """Get all trades for a strategy"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM trades 
            WHERE strategy_id = ?
            ORDER BY traded_at DESC
        ''', (strategy_id,))
        
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    def get_strategy_stats(self, strategy_id: int) -> Dict:
        """Get statistics for a strategy"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get total trades
        cursor.execute('SELECT COUNT(*) FROM trades WHERE strategy_id = ?', (strategy_id,))
        total_trades = cursor.fetchone()[0]
        
        # Get realized PnL
        cursor.execute('SELECT SUM(realized_pnl) FROM trades WHERE strategy_id = ?', (strategy_id,))
        realized_pnl = cursor.fetchone()[0] or 0
        
        # Get total fees
        cursor.execute('SELECT SUM(fee) FROM trades WHERE strategy_id = ?', (strategy_id,))
        total_fees = cursor.fetchone()[0] or 0
        
        # Get win rate
        cursor.execute('''
            SELECT COUNT(*) FROM trades 
            WHERE strategy_id = ? AND realized_pnl > 0
        ''', (strategy_id,))
        winning_trades = cursor.fetchone()[0]
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        # Get current position
        cursor.execute('''
            SELECT SUM(quantity) FROM positions 
            WHERE strategy_id = ?
        ''', (strategy_id,))
        position = cursor.fetchone()[0] or 0
        
        conn.close()
        
        return {
            "total_trades": total_trades,
            "realized_pnl": realized_pnl,
            "total_fees": total_fees,
            "win_rate": win_rate,
            "current_position": position
        }
    
    def update_position(self, strategy_id: int, symbol: str, quantity: float, 
                        avg_price: float, current_price: Optional[float] = None):
        """Update or create position"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        
        # Check if position exists
        cursor.execute('SELECT id, quantity FROM positions WHERE strategy_id = ? AND symbol = ?', 
                      (strategy_id, symbol))
        existing = cursor.fetchone()
        
        if existing:
            pos_id, old_qty = existing
            new_qty = old_qty + quantity
            if new_qty == 0:
                # Close position
                cursor.execute('DELETE FROM positions WHERE id = ?', (pos_id,))
            else:
                # Update position
                new_avg = ((old_qty * avg_price) + (quantity * avg_price)) / new_qty if new_qty != 0 else avg_price
                unrealized_pnl = (current_price - new_avg) * new_qty if current_price else 0
                cursor.execute('''
                    UPDATE positions 
                    SET quantity = ?, avg_price = ?, current_price = ?, 
                        unrealized_pnl = ?, updated_at = ?
                    WHERE id = ?
                ''', (new_qty, new_avg, current_price, unrealized_pnl, now, pos_id))
        else:
            # Create new position
            unrealized_pnl = (current_price - avg_price) * quantity if current_price else 0
            cursor.execute('''
                INSERT INTO positions 
                (strategy_id, symbol, quantity, avg_price, current_price, unrealized_pnl, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (strategy_id, symbol, quantity, avg_price, current_price, unrealized_pnl, now, now))
        
        conn.commit()
        conn.close()

