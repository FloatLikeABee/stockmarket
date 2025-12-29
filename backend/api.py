from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, List, Optional
import asyncio
import threading
import time

from .crawler import ChineseStockCrawler
from .database import StockDatabase
from .cleanup_scheduler import CleanupScheduler


class CrawlRequest(BaseModel):
    sites: Optional[List[str]] = None  # List of site names to crawl, None means all
    category: Optional[str] = "general"


class StockAPI:
    def __init__(self):
        self.crawler = ChineseStockCrawler()
        self.db = StockDatabase()
        self.cleanup_scheduler = CleanupScheduler(days_to_keep=15, check_interval_hours=24)
        self.app = FastAPI(title="Chinese Stock Market API")

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
            """Trigger crawling of stock data - Manual crawls bypass rate limiting"""
            def run_crawling():
                # Manual crawls bypass rate limiting
                bypass_rate_limit = True
                
                if request.sites:
                    # Crawl specific sites
                    results = {}
                    for site in request.sites:
                        if site == 'tonghuashun':
                            results[site] = self.crawler.crawl_tonghuashun(bypass_rate_limit)
                        elif site == 'dongfangcaifu':
                            results[site] = self.crawler.crawl_dongfangcaifu(bypass_rate_limit)
                        elif site == 'xueqiu':
                            results[site] = self.crawler.crawl_xueqiu(bypass_rate_limit)
                        elif site == 'tongdaxin':
                            results[site] = self.crawler.crawl_tongdaxin(bypass_rate_limit)
                        elif site == 'caijinglian':
                            results[site] = self.crawler.crawl_caijinglian(bypass_rate_limit)
                        else:
                            results[site] = {"error": f"Unknown site: {site}"}
                else:
                    # Crawl all sites
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
            """Get rate limit status for all crawlers"""
            current_time = time.time()
            status = {}
            for site_name, last_crawl in self.crawler.last_crawl_times.items():
                time_since_last_crawl = current_time - last_crawl
                remaining = max(0, self.crawler.min_crawl_interval - time_since_last_crawl)
                status[site_name] = {
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

    def _schedule_crawling(self):
        """Schedule periodic crawling every 1 hour"""
        def run_periodic_crawling():
            while True:
                time.sleep(60 * 60)  # 1 hour (3600 seconds)
                print("Running scheduled crawl...")
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
                
        # Run the scheduled crawling in a separate thread
        thread = threading.Thread(target=run_periodic_crawling, daemon=True)
        thread.start()

    def run(self, host: str = "0.0.0.0", port: int = 9878):  # Changed to 9878
        """Run the API server"""
        import uvicorn
        uvicorn.run(self.app, host=host, port=port)


# Create the API instance
api = StockAPI().app