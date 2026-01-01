from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, List, Optional
import asyncio
import threading
import time

from .crawler import ChineseStockCrawler
from .database import StockDatabase
from .stock_db import StockDatabaseSQLite
from .cleanup_scheduler import CleanupScheduler
from .grid_trading_db import GridTradingDatabase
from .grid_trading_engine import GridTradingEngine


class CrawlRequest(BaseModel):
    sites: Optional[List[str]] = None  # List of site names to crawl, None means all
    category: Optional[str] = "general"


class StockAPI:
    def __init__(self):
        self.crawler = ChineseStockCrawler()
        self.db = StockDatabase()
        self.stock_db = StockDatabaseSQLite()  # SQLite database for stocks
        self.grid_db = GridTradingDatabase()  # Grid trading database
        self.grid_engine = GridTradingEngine(self.grid_db, self.crawler.akshare_fetcher)
        self.cleanup_scheduler = CleanupScheduler(days_to_keep=1, check_interval_hours=24)
        self.app = FastAPI(title="Chinese Stock Market API")
        
        # Start grid trading monitoring thread
        self._start_grid_monitoring()
        
        # Track manual crawl times (separate from scheduled crawls)
        self.last_manual_crawl_time = 0
        self.manual_crawl_interval = 10 * 60  # 10 minutes in seconds

        # Add CORS middleware to allow all origins
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # Allow all origins
            allow_credentials=True,
            allow_methods=["*"],  # Allow all methods
            allow_headers=["*"],  # Allow all headers
            # Additional options to handle preflight requests properly
            allow_origin_regex="https?://.*",  # Allow any HTTP/HTTPS origin
            max_age=3600,  # Cache preflight requests for 1 hour
        )

        self._setup_routes()
        
        # Start grid trading monitoring
        self._start_grid_monitoring()

        # Schedule periodic crawling (every 1 hour)
        self._schedule_crawling()

        # Start automatic cleanup scheduler (runs daily to remove files older than 15 days)
        self.cleanup_scheduler.start()

    def _setup_routes(self):
        @self.app.get("/")
        def read_root():
            return {"message": "Chinese Stock Market Data API"}

        @self.app.post("/crawl")
        def crawl_stocks(request: CrawlRequest, background_tasks: BackgroundTasks):
            """Trigger crawling of stock data - Manual crawls with 10-minute rate limiting"""
            # Check if manual crawl is allowed (10 minutes since last manual crawl)
            current_time = time.time()
            time_since_last_manual = current_time - self.last_manual_crawl_time
            
            if time_since_last_manual < self.manual_crawl_interval:
                remaining_time = self.manual_crawl_interval - time_since_last_manual
                raise HTTPException(
                    status_code=429,
                    detail=f"Manual crawl rate limit: Please wait {int(remaining_time / 60)} minutes and {int(remaining_time % 60)} seconds before crawling again"
                )
            
            # Update last manual crawl time
            self.last_manual_crawl_time = current_time
            
            def run_crawling():
                # Manual crawls bypass site rate limiting but respect manual crawl interval
                bypass_rate_limit = True
                
                if request.sites:
                    # Crawl specific sites (only AKShare is available now)
                    results = {}
                    for site in request.sites:
                        if site == 'akshare':
                            results[site] = self.crawler.crawl_akshare(bypass_rate_limit)
                        else:
                            results[site] = {"error": f"Site '{site}' is no longer supported. Only 'akshare' is available."}
                else:
                    # Crawl all sites (only AKShare)
                    results = self.crawler.crawl_all_sites(bypass_rate_limit)
                
                # Save data to files
                filepath = self.crawler.save_data(results, request.category)
                
                # Index the file in the database
                metadata = {
                    "category": request.category,
                    "sites_crawled": list(results.keys()),
                    "timestamp": results[list(results.keys())[0]].get("timestamp", "")
                }
                self.db.index_crawled_file(filepath, metadata)
                
                # Save stocks to SQLite database
                if 'akshare' in results:
                    akshare_data = results['akshare']
                    ai_data = akshare_data.get('ai_processed_data', {})
                    if ai_data and 'stocks' in ai_data:
                        stocks = ai_data['stocks']
                        timestamp = akshare_data.get('timestamp', '')
                        inserted = self.stock_db.insert_stocks(stocks, timestamp)
                        print(f"[API] Inserted {inserted} stocks into SQLite database")
                    
                
            background_tasks.add_task(run_crawling)
            return {"message": "Crawling started", "sites": request.sites or "all"}

        @self.app.get("/data/latest")
        def get_latest_data(limit: int = 10):
            """Get latest crawled records"""
            try:
                records = self.db.get_latest_records(limit)
                # Ensure we return a valid response even if there are issues with records
                if records is None:
                    records = []
                return {"records": records, "count": len(records)}
            except Exception as e:
                print(f"Error in get_latest_data: {e}")
                import traceback
                traceback.print_exc()
                raise HTTPException(status_code=500, detail=f"Error retrieving data: {str(e)}")

        @self.app.get("/data/sites")
        def get_all_sites():
            """Get all unique sites in the database"""
            try:
                sites = self.db.get_all_sites()
                return {"sites": sites}
            except Exception as e:
                print(f"Error in get_all_sites: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/data/site/{site_name}")
        def get_data_by_site(site_name: str):
            """Get data from a specific site"""
            try:
                records = self.db.search_by_site(site_name)
                return {"records": records, "count": len(records)}
            except Exception as e:
                print(f"Error in get_data_by_site: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/stats")
        def get_statistics():
            """Get database statistics"""
            try:
                stats = self.db.get_statistics()
                return stats
            except Exception as e:
                print(f"Error in get_statistics: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/rate_limit_status")
        def get_rate_limit_status():
            """Get rate limit status for all crawlers and manual crawl"""
            current_time = time.time()
            status = {
                "manual_crawl": {},
                "scheduled_crawl": {},
                "market_hours": self._is_market_hours()
            }
            
            # Manual crawl status
            time_since_last_manual = current_time - self.last_manual_crawl_time
            remaining_manual = max(0, self.manual_crawl_interval - time_since_last_manual)
            status["manual_crawl"] = {
                "last_crawled": self.last_manual_crawl_time,
                "time_since_last_crawl": time_since_last_manual,
                "remaining_wait_time": remaining_manual,
                "can_crawl": remaining_manual == 0,
                "interval_seconds": self.manual_crawl_interval
            }
            
            # Site-specific rate limits
            for site_name, last_crawl in self.crawler.last_crawl_times.items():
                time_since_last_crawl = current_time - last_crawl
                remaining = max(0, self.crawler.min_crawl_interval - time_since_last_crawl)
                status["scheduled_crawl"][site_name] = {
                    "last_crawled": last_crawl,
                    "time_since_last_crawl": time_since_last_crawl,
                    "remaining_wait_time": remaining,
                    "can_crawl": remaining == 0
                }
            
            return status

        @self.app.post("/reset_rate_limits")
        def reset_rate_limits():
            """Reset rate limits for all crawlers (for testing)"""
            self.crawler.last_crawl_times = {}
            return {"message": "Rate limits reset successfully"}
        
        @self.app.get("/stocks")
        def get_stocks(page: int = 1, per_page: int = 50, 
                      order_by: str = 'symbol', order_dir: str = 'ASC',
                      symbol: Optional[str] = None):
            """Get stocks with pagination"""
            try:
                stocks, total_count = self.stock_db.get_stocks_paginated(
                    page=page,
                    per_page=per_page,
                    order_by=order_by,
                    order_dir=order_dir,
                    symbol_filter=symbol,
                    latest_only=True
                )
                return {
                    "stocks": stocks,
                    "pagination": {
                        "page": page,
                        "per_page": per_page,
                        "total": total_count,
                        "total_pages": (total_count + per_page - 1) // per_page
                    }
                }
            except Exception as e:
                print(f"Error in get_stocks: {e}")
                import traceback
                traceback.print_exc()
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/historical")
        def get_historical_data(
            symbol: str,
            start_date: str,
            end_date: str,
            period: str = "daily",
            adjust: str = "qfq"
        ):
            """Get historical stock data from AKShare"""
            try:
                # Validate date format (should be YYYYMMDD)
                if len(start_date) != 8 or len(end_date) != 8:
                    raise HTTPException(status_code=400, detail="Date format must be YYYYMMDD (e.g., 20240101)")
                
                # Validate period
                if period not in ['daily', 'weekly', 'monthly']:
                    period = 'daily'
                
                # Validate adjust
                if adjust not in ['qfq', 'hfq', '']:
                    adjust = 'qfq'
                
                # Get historical data from AKShare
                if not self.crawler.akshare_fetcher:
                    raise HTTPException(status_code=500, detail="AKShare fetcher not available")
                
                historical_data = self.crawler.akshare_fetcher.get_stock_historical_data(
                    symbol=symbol,
                    start_date=start_date,
                    end_date=end_date,
                    period=period,
                    adjust=adjust,
                    bypass_rate_limit=True
                )
                
                return {
                    "symbol": symbol,
                    "start_date": start_date,
                    "end_date": end_date,
                    "period": period,
                    "adjust": adjust,
                    "data": historical_data,
                    "count": len(historical_data)
                }
            except HTTPException:
                raise
            except Exception as e:
                print(f"Error in get_historical_data: {e}")
                import traceback
                traceback.print_exc()
                raise HTTPException(status_code=500, detail=f"Error retrieving historical data: {str(e)}")
        
        # Print available routes for debugging
        print(f"[API] Registered /historical route")
        
        # Grid Trading endpoints
        @self.app.post("/grid-strategies")
        def create_grid_strategy(request: Dict):
            """Create a new grid trading strategy"""
            try:
                strategy_id = self.grid_db.create_strategy(request)
                return {"id": strategy_id, "message": "Strategy created successfully"}
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Error creating strategy: {str(e)}")
        
        @self.app.get("/grid-strategies")
        def get_grid_strategies(status: Optional[str] = None):
            """Get all grid trading strategies"""
            try:
                strategies = self.grid_db.get_all_strategies(status)
                return {"strategies": strategies}
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Error retrieving strategies: {str(e)}")
        
        @self.app.get("/grid-strategies/{strategy_id}")
        def get_grid_strategy(strategy_id: int):
            """Get a specific grid trading strategy with full state"""
            try:
                state = self.grid_engine.get_strategy_state(strategy_id)
                if not state:
                    raise HTTPException(status_code=404, detail="Strategy not found")
                return state
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Error retrieving strategy: {str(e)}")
        
        @self.app.post("/grid-strategies/{strategy_id}/start")
        def start_grid_strategy(strategy_id: int):
            """Start a grid trading strategy"""
            try:
                success = self.grid_engine.initialize_strategy(strategy_id)
                if not success:
                    raise HTTPException(status_code=400, detail="Failed to start strategy. Check if price is within range.")
                return {"message": "Strategy started successfully"}
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Error starting strategy: {str(e)}")
        
        @self.app.post("/grid-strategies/{strategy_id}/stop")
        def stop_grid_strategy(strategy_id: int, close_positions: bool = False):
            """Stop a grid trading strategy"""
            try:
                self.grid_engine.stop_strategy(strategy_id, close_positions)
                return {"message": "Strategy stopped successfully"}
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Error stopping strategy: {str(e)}")
        
        @self.app.post("/grid-strategies/{strategy_id}/pause")
        def pause_grid_strategy(strategy_id: int):
            """Pause a grid trading strategy"""
            try:
                self.grid_engine.pause_strategy(strategy_id)
                return {"message": "Strategy paused successfully"}
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Error pausing strategy: {str(e)}")
        
        @self.app.post("/grid-strategies/{strategy_id}/resume")
        def resume_grid_strategy(strategy_id: int):
            """Resume a paused grid trading strategy"""
            try:
                success = self.grid_engine.resume_strategy(strategy_id)
                if not success:
                    raise HTTPException(status_code=400, detail="Failed to resume strategy")
                return {"message": "Strategy resumed successfully"}
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Error resuming strategy: {str(e)}")
        
        @self.app.get("/grid-strategies/{strategy_id}/stats")
        def get_strategy_stats(strategy_id: int):
            """Get statistics for a strategy"""
            try:
                stats = self.grid_db.get_strategy_stats(strategy_id)
                return stats
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Error retrieving stats: {str(e)}")
        
        @self.app.get("/grid-strategies/{strategy_id}/trades")
        def get_strategy_trades(strategy_id: int):
            """Get all trades for a strategy"""
            try:
                trades = self.grid_db.get_strategy_trades(strategy_id)
                return {"trades": trades}
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Error retrieving trades: {str(e)}")
        
        print(f"[API] Registered grid trading routes")
        
    def _start_grid_monitoring(self):
        """Start background thread to monitor and process grid trading strategies"""
        def monitor_loop():
            while True:
                try:
                    # Get all running strategies
                    running_strategies = self.grid_db.get_all_strategies('RUNNING')
                    
                    for strategy in running_strategies:
                        strategy_id = strategy['id']
                        
                        # Check risk controls
                        is_safe, error_msg = self.grid_engine.check_risk_controls(strategy_id)
                        if not is_safe:
                            print(f"[GridMonitor] Risk control triggered for strategy {strategy_id}: {error_msg}")
                            self.grid_engine.stop_strategy(strategy_id)
                            continue
                        
                        # Check and fill orders
                        self.grid_engine.check_and_fill_orders(strategy_id)
                    
                    # Sleep for 5 seconds before next check
                    time.sleep(5)
                except Exception as e:
                    print(f"[GridMonitor] Error in monitoring loop: {e}")
                    time.sleep(10)
        
        thread = threading.Thread(target=monitor_loop, daemon=True)
        thread.start()
        print("[GridMonitor] Grid trading monitoring thread started")
        
    def _is_market_hours(self) -> bool:
        """Check if current time is within market hours (Mon-Fri, 9am-4pm)"""
        from datetime import datetime
        now = datetime.now()
        
        # Check if it's Monday to Friday (0=Monday, 4=Friday)
        weekday = now.weekday()
        if weekday > 4:  # Saturday (5) or Sunday (6)
            return False
        
        # Check if time is between 9am and 4pm
        hour = now.hour
        return 9 <= hour < 16  # 9am to 4pm (16:00 is 4pm, but we use < 16 so it stops at 3:59pm)
    
    def _schedule_crawling(self):
        """Schedule periodic crawling during market hours (Mon-Fri, 9am-4pm) twice per hour (every 30 minutes)"""
        def run_periodic_crawling():
            crawl_interval = 30 * 60  # 30 minutes in seconds (twice per hour)
            
            while True:
                # Check if we're in market hours
                if self._is_market_hours():
                    print(f"[Scheduled Crawl] Running scheduled crawl during market hours...")
                    try:
                        # Scheduled crawls respect rate limiting
                        results = self.crawler.crawl_all_sites(bypass_rate_limit=False)
                        
                        # Save data to files
                        filepath = self.crawler.save_data(results, "scheduled")
                        
                        # Index the file in the database
                        metadata = {
                            "category": "scheduled",
                            "sites_crawled": list(results.keys()),
                            "timestamp": results[list(results.keys())[0]].get("timestamp", "")
                        }
                        self.db.index_crawled_file(filepath, metadata)
                        
                        # Save stocks to SQLite database
                        if 'akshare' in results:
                            akshare_data = results['akshare']
                            ai_data = akshare_data.get('ai_processed_data', {})
                            if ai_data and 'stocks' in ai_data:
                                stocks = ai_data['stocks']
                                timestamp = akshare_data.get('timestamp', '')
                                inserted = self.stock_db.insert_stocks(stocks, timestamp)
                                print(f"[Scheduled Crawl] Inserted {inserted} stocks into SQLite database")
                            
                        
                        # Cleanup old SQLite data (keep only 1 day)
                        self.stock_db.cleanup_old_data(days_to_keep=1)
                        
                        print(f"[Scheduled Crawl] Completed successfully")
                    except Exception as e:
                        print(f"[Scheduled Crawl] Error during scheduled crawl: {e}")
                else:
                    # Outside market hours - log and wait
                    from datetime import datetime
                    now = datetime.now()
                    weekday_name = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'][now.weekday()]
                    print(f"[Scheduled Crawl] Outside market hours ({weekday_name} {now.strftime('%H:%M')}). Waiting...")
                
                # Wait 30 minutes before next check (twice per hour)
                time.sleep(crawl_interval)
                
        # Run the scheduled crawling in a separate thread
        thread = threading.Thread(target=run_periodic_crawling, daemon=True)
        thread.start()
        print("[Scheduled Crawl] Scheduled crawler started: Mon-Fri 9am-4pm, twice per hour (every 30 minutes)")

    def run(self, host: str = "0.0.0.0", port: int = 9878):  # Changed to 9878
        """Run the API server"""
        import uvicorn
        uvicorn.run(self.app, host=host, port=port)


# Create the API instance
api = StockAPI().app