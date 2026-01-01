"""
AKShare-based data fetcher for comprehensive Chinese stock market data
Provides deep, structured data from EastMoney (东方财富) via AKShare library

All functions use EastMoney data sources (indicated by _em suffix in AKShare functions)
"""
import akshare as ak
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import time
import json


class AKShareFetcher:
    """Fetches comprehensive Chinese stock market data using AKShare library"""
    
    def __init__(self):
        self.data_cache = {}
        self.last_fetch_times = {}
        self.min_fetch_interval = 60  # 1 minute minimum between fetches for same data type
    
    def _can_fetch(self, data_type: str, bypass_rate_limit: bool = False) -> bool:
        """Check if we can fetch data based on rate limiting"""
        if bypass_rate_limit:
            return True
        current_time = time.time()
        last_fetch = self.last_fetch_times.get(data_type, 0)
        return (current_time - last_fetch) >= self.min_fetch_interval
    
    def _update_fetch_time(self, data_type: str):
        """Update last fetch time"""
        self.last_fetch_times[data_type] = time.time()
    
    def get_market_indices(self, bypass_rate_limit: bool = False) -> List[Dict]:
        """Get real-time market indices (上证指数, 深证成指, etc.)"""
        if not self._can_fetch('indices', bypass_rate_limit):
            return []
        
        try:
            indices_list = []
            
            # Get real-time index quotes - use stock_zh_index_spot_em
            try:
                realtime_indices = ak.stock_zh_index_spot_em()
                if not realtime_indices.empty:
                    for _, row in realtime_indices.head(20).iterrows():
                        indices_list.append({
                            "name": str(row.get('名称', 'N/A')),
                            "symbol": str(row.get('代码', 'N/A')),
                            "value": str(row.get('最新价', 'N/A')),
                            "change": str(row.get('涨跌额', 'N/A')),
                            "change_percent": f"{row.get('涨跌幅', 0):.2f}%" if pd.notna(row.get('涨跌幅')) else 'N/A'
                        })
            except Exception as e:
                print(f"[AKShare] Error fetching real-time indices: {e}")
                import traceback
                traceback.print_exc()
            
            # Try to get historical data for major indices if real-time fails
            if not indices_list:
                # Shanghai Composite Index (上证指数)
                try:
                    sh_data = ak.index_zh_a_hist(symbol="000001", period="daily", start_date="20240101", end_date="20241231")
                    if not sh_data.empty:
                        latest = sh_data.iloc[-1]
                        indices_list.append({
                            "name": "上证指数",
                            "symbol": "000001",
                            "value": str(latest.get('收盘', 'N/A')),
                            "change": str(latest.get('涨跌额', 'N/A')),
                            "change_percent": f"{latest.get('涨跌幅', 0):.2f}%" if pd.notna(latest.get('涨跌幅')) else "N/A"
                        })
                except Exception as e:
                    print(f"[AKShare] Error fetching 上证指数: {e}")
                
                # Shenzhen Component Index (深证成指)
                try:
                    sz_data = ak.index_zh_a_hist(symbol="399001", period="daily", start_date="20240101", end_date="20241231")
                    if not sz_data.empty:
                        latest = sz_data.iloc[-1]
                        indices_list.append({
                            "name": "深证成指",
                            "symbol": "399001",
                            "value": str(latest.get('收盘', 'N/A')),
                            "change": str(latest.get('涨跌额', 'N/A')),
                            "change_percent": f"{latest.get('涨跌幅', 0):.2f}%" if pd.notna(latest.get('涨跌幅')) else "N/A"
                        })
                except Exception as e:
                    print(f"[AKShare] Error fetching 深证成指: {e}")
            
            self._update_fetch_time('indices')
            return indices_list
            
        except Exception as e:
            print(f"[AKShare] Error in get_market_indices: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def get_stock_list(self, market: str = "all", bypass_rate_limit: bool = False) -> List[Dict]:
        """
        Get list of all stocks
        market: 'sh' (Shanghai), 'sz' (Shenzhen), 'all' (both)
        """
        if not self._can_fetch('stock_list', bypass_rate_limit):
            return []
        
        try:
            stocks = []
            
            if market in ['sh', 'all']:
                # Shanghai stocks
                try:
                    sh_stocks = ak.stock_info_a_code_name()
                    if not sh_stocks.empty:
                        for _, row in sh_stocks.iterrows():
                            if str(row.get('code', '')).startswith('6'):  # Shanghai stocks start with 6
                                stocks.append({
                                    "symbol": str(row.get('code', '')),
                                    "name": str(row.get('name', 'N/A'))
                                })
                except Exception as e:
                    print(f"[AKShare] Error fetching Shanghai stocks: {e}")
            
            if market in ['sz', 'all']:
                # Shenzhen stocks
                try:
                    sz_stocks = ak.stock_info_a_code_name()
                    if not sz_stocks.empty:
                        for _, row in sz_stocks.iterrows():
                            code = str(row.get('code', ''))
                            if code.startswith(('0', '3')):  # Shenzhen stocks start with 0 or 3
                                stocks.append({
                                    "symbol": code,
                                    "name": str(row.get('name', 'N/A'))
                                })
                except Exception as e:
                    print(f"[AKShare] Error fetching Shenzhen stocks: {e}")
            
            self._update_fetch_time('stock_list')
            return stocks[:500]  # Limit to 500 for performance
            
        except Exception as e:
            print(f"[AKShare] Error in get_stock_list: {e}")
            return []
    
    def get_stock_realtime_quotes(self, symbols: Optional[List[str]] = None, bypass_rate_limit: bool = False) -> List[Dict]:
        """
        Get real-time quotes for stocks
        If symbols is None, gets top stocks by volume
        """
        if not self._can_fetch('realtime_quotes', bypass_rate_limit):
            return []
        
        try:
            stocks = []
            
            if symbols:
                # Get all stocks first, then filter
                try:
                    all_stocks = ak.stock_zh_a_spot_em()
                    if not all_stocks.empty:
                        # Filter by requested symbols
                        for symbol in symbols[:100]:  # Limit to 100 stocks
                            symbol_str = str(symbol)
                            matching = all_stocks[all_stocks['代码'] == symbol_str]
                            if not matching.empty:
                                row = matching.iloc[0]
                                stocks.append({
                                    "symbol": symbol_str,
                                    "name": str(row.get('名称', 'N/A')),
                                    "price": str(row.get('最新价', 'N/A')),
                                    "change": str(row.get('涨跌额', 'N/A')),
                                    "change_percent": str(row.get('涨跌幅', 'N/A')) + '%' if pd.notna(row.get('涨跌幅')) else 'N/A',
                                    "volume": str(row.get('成交量', 'N/A')),
                                    "turnover": str(row.get('成交额', 'N/A')),
                                    "high": str(row.get('最高', 'N/A')),
                                    "low": str(row.get('最低', 'N/A')),
                                    "open": str(row.get('今开', 'N/A')),
                                    "yesterday_close": str(row.get('昨收', 'N/A')),
                                    "turnover_rate": str(row.get('换手率', 'N/A')) + '%' if pd.notna(row.get('换手率')) else 'N/A',
                                    "pe_ratio": str(row.get('市盈率', 'N/A')),
                                    "market_cap": str(row.get('总市值', 'N/A')),
                                    "circulating_market_cap": str(row.get('流通市值', 'N/A'))
                                })
                except Exception as e:
                    print(f"[AKShare] Error fetching quotes for symbols: {e}")
            else:
                # Get ALL stocks (not just top 100)
                try:
                    all_stocks = ak.stock_zh_a_spot_em()
                    if not all_stocks.empty:
                        print(f"[AKShare] Fetching all {len(all_stocks)} stocks...")
                        for _, row in all_stocks.iterrows():
                            stocks.append({
                                "symbol": str(row.get('代码', 'N/A')),
                                "name": str(row.get('名称', 'N/A')),
                                "price": str(row.get('最新价', 'N/A')),
                                "change": str(row.get('涨跌额', 'N/A')),
                                "change_percent": str(row.get('涨跌幅', 'N/A')) + '%' if pd.notna(row.get('涨跌幅')) else 'N/A',
                                "volume": str(row.get('成交量', 'N/A')),
                                "turnover": str(row.get('成交额', 'N/A')),
                                "high": str(row.get('最高', 'N/A')),
                                "low": str(row.get('最低', 'N/A')),
                                "open": str(row.get('今开', 'N/A')),
                                "yesterday_close": str(row.get('昨收', 'N/A')),
                                "turnover_rate": str(row.get('换手率', 'N/A')) + '%' if pd.notna(row.get('换手率')) else 'N/A',
                                "pe_ratio": str(row.get('市盈率', 'N/A')),
                                "market_cap": str(row.get('总市值', 'N/A')),
                                "circulating_market_cap": str(row.get('流通市值', 'N/A'))
                            })
                        print(f"[AKShare] Successfully fetched {len(stocks)} stocks")
                except Exception as e:
                    print(f"[AKShare] Error fetching all stocks: {e}")
                    import traceback
                    traceback.print_exc()
            
            self._update_fetch_time('realtime_quotes')
            return stocks
            
        except Exception as e:
            print(f"[AKShare] Error in get_stock_realtime_quotes: {e}")
            return []
    
    def get_top_gainers_losers(self, bypass_rate_limit: bool = False) -> Dict[str, List[Dict]]:
        """Get top gainers and losers"""
        if not self._can_fetch('gainers_losers', bypass_rate_limit):
            return {"gainers": [], "losers": []}
        
        try:
            gainers = []
            losers = []
            
            # Get stock board data
            try:
                board_data = ak.stock_zh_a_spot_em()
                if not board_data.empty:
                    # Top gainers (sorted by change percent)
                    top_gainers = board_data.nlargest(20, '涨跌幅')
                    for _, row in top_gainers.iterrows():
                        if pd.notna(row.get('涨跌幅')) and row.get('涨跌幅') > 0:
                            gainers.append({
                                "symbol": str(row.get('代码', 'N/A')),
                                "name": str(row.get('名称', 'N/A')),
                                "change_percent": f"{row.get('涨跌幅', 0):.2f}%",
                                "price": str(row.get('最新价', 'N/A'))
                            })
                    
                    # Top losers (sorted by change percent, ascending)
                    top_losers = board_data.nsmallest(20, '涨跌幅')
                    for _, row in top_losers.iterrows():
                        if pd.notna(row.get('涨跌幅')) and row.get('涨跌幅') < 0:
                            losers.append({
                                "symbol": str(row.get('代码', 'N/A')),
                                "name": str(row.get('名称', 'N/A')),
                                "change_percent": f"{row.get('涨跌幅', 0):.2f}%",
                                "price": str(row.get('最新价', 'N/A'))
                            })
            except Exception as e:
                print(f"[AKShare] Error fetching gainers/losers: {e}")
            
            self._update_fetch_time('gainers_losers')
            return {"gainers": gainers, "losers": losers}
            
        except Exception as e:
            print(f"[AKShare] Error in get_top_gainers_losers: {e}")
            return {"gainers": [], "losers": []}
    
    def get_market_overview(self, bypass_rate_limit: bool = False) -> Dict:
        """Get comprehensive market overview"""
        if not self._can_fetch('market_overview', bypass_rate_limit):
            return {}
        
        try:
            overview = {
                "timestamp": datetime.now().isoformat(),
                "indices": [],
                "market_summary": "",
                "total_stocks": 0,
                "rising_stocks": 0,
                "falling_stocks": 0,
                "unchanged_stocks": 0
            }
            
            # Get indices
            overview["indices"] = self.get_market_indices(bypass_rate_limit=True)
            
            # Get market statistics
            try:
                spot_data = ak.stock_zh_a_spot_em()
                if not spot_data.empty:
                    overview["total_stocks"] = len(spot_data)
                    overview["rising_stocks"] = len(spot_data[spot_data['涨跌幅'] > 0])
                    overview["falling_stocks"] = len(spot_data[spot_data['涨跌幅'] < 0])
                    overview["unchanged_stocks"] = len(spot_data[spot_data['涨跌幅'] == 0])
                    
                    # Create market summary
                    rising_pct = (overview["rising_stocks"] / overview["total_stocks"] * 100) if overview["total_stocks"] > 0 else 0
                    overview["market_summary"] = (
                        f"今日市场概况：共{overview['total_stocks']}只股票，"
                        f"上涨{overview['rising_stocks']}只({rising_pct:.1f}%)，"
                        f"下跌{overview['falling_stocks']}只，"
                        f"平盘{overview['unchanged_stocks']}只。"
                    )
            except Exception as e:
                print(f"[AKShare] Error fetching market statistics: {e}")
            
            self._update_fetch_time('market_overview')
            return overview
            
        except Exception as e:
            print(f"[AKShare] Error in get_market_overview: {e}")
            return {}
    
    def get_comprehensive_data(self, bypass_rate_limit: bool = False) -> Dict:
        """Get comprehensive market data from all sources - ALL stocks included"""
        print("[AKShare] Fetching comprehensive market data (ALL stocks)...")
        
        try:
            # Get all data - stocks will include ALL stocks, not just top 100
            indices = self.get_market_indices(bypass_rate_limit)
            all_stocks = self.get_stock_realtime_quotes(bypass_rate_limit=bypass_rate_limit)  # Gets ALL stocks now
            gainers_losers = self.get_top_gainers_losers(bypass_rate_limit)
            market_overview = self.get_market_overview(bypass_rate_limit)
            
            # Combine into structured format
            comprehensive_data = {
                "site": "akshare",
                "timestamp": datetime.now().isoformat(),
                "ai_processed_data": {
                    "indices": indices,
                    "stocks": all_stocks,  # ALL stocks with comprehensive data
                    "top_gainers": gainers_losers.get("gainers", []),
                    "top_losers": gainers_losers.get("losers", []),
                    "market_overview": market_overview.get("market_summary", ""),
                    "trading_summary": (
                        f"市场统计：总股票数{market_overview.get('total_stocks', 0)}，"
                        f"上涨{market_overview.get('rising_stocks', 0)}，"
                        f"下跌{market_overview.get('falling_stocks', 0)}"
                    )
                },
                "raw_data_preview": f"AKShare comprehensive data - {len(indices)} indices, {len(all_stocks)} stocks (ALL stocks included)"
            }
            
            print(f"[AKShare] Successfully fetched comprehensive data: {len(indices)} indices, {len(all_stocks)} stocks (ALL stocks)")
            return comprehensive_data
            
        except Exception as e:
            print(f"[AKShare] Error in get_comprehensive_data: {e}")
            import traceback
            traceback.print_exc()
            return {
                "site": "akshare",
                "timestamp": datetime.now().isoformat(),
                "error": f"Error fetching comprehensive data: {str(e)}",
                "ai_processed_data": None
            }
    
    def _safe_float(self, value):
        """Safely convert value to float"""
        try:
            if pd.isna(value) or value is None:
                return None
            return float(value)
        except (ValueError, TypeError):
            return None
    
    def get_stock_historical_data(self, symbol: str, start_date: str, end_date: str, 
                                   period: str = "daily", adjust: str = "qfq", 
                                   bypass_rate_limit: bool = False) -> List[Dict]:
        """
        Get historical stock data for a specific symbol
        
        Args:
            symbol: Stock code (e.g., '000001')
            start_date: Start date in format 'YYYYMMDD' (e.g., '20240101')
            end_date: End date in format 'YYYYMMDD' (e.g., '20241231')
            period: 'daily', 'weekly', 'monthly' - default is 'daily'
            adjust: 'qfq' (前复权), 'hfq' (后复权), '' (不复权) - default is 'qfq'
            bypass_rate_limit: Whether to bypass rate limiting
        
        Returns:
            List of dictionaries containing historical data
        """
        cache_key = f"hist_{symbol}_{start_date}_{end_date}_{period}"
        if not bypass_rate_limit and cache_key in self.data_cache:
            return self.data_cache[cache_key]
        
        if not self._can_fetch(cache_key, bypass_rate_limit):
            return []
        
        try:
            historical_data = []
            
            # Use stock_zh_a_hist for A-share historical data
            try:
                # AKShare function: stock_zh_a_hist(symbol, period, start_date, end_date, adjust)
                df = ak.stock_zh_a_hist(
                    symbol=symbol,
                    period=period,
                    start_date=start_date,
                    end_date=end_date,
                    adjust=adjust
                )
                
                if not df.empty:
                    # Convert DataFrame to list of dictionaries
                    for _, row in df.iterrows():
                        historical_data.append({
                            "date": str(row.get('日期', '')),
                            "open": self._safe_float(row.get('开盘', None)),
                            "close": self._safe_float(row.get('收盘', None)),
                            "high": self._safe_float(row.get('最高', None)),
                            "low": self._safe_float(row.get('最低', None)),
                            "volume": self._safe_float(row.get('成交量', None)),
                            "turnover": self._safe_float(row.get('成交额', None)),
                            "amplitude": self._safe_float(row.get('振幅', None)),
                            "change_percent": self._safe_float(row.get('涨跌幅', None)),
                            "change_amount": self._safe_float(row.get('涨跌额', None)),
                            "turnover_rate": self._safe_float(row.get('换手率', None))
                        })
                    
                    # Cache the data
                    self.data_cache[cache_key] = historical_data
                    self._update_fetch_time(cache_key)
                    print(f"[AKShare] Fetched {len(historical_data)} historical records for {symbol}")
                else:
                    print(f"[AKShare] No historical data found for {symbol}")
                    
            except Exception as e:
                print(f"[AKShare] Error fetching historical data for {symbol}: {e}")
                import traceback
                traceback.print_exc()
            
            return historical_data
            
        except Exception as e:
            print(f"[AKShare] Error in get_stock_historical_data: {e}")
            import traceback
            traceback.print_exc()
            return []

