import json
from tinydb import TinyDB, Query
from datetime import datetime
from typing import Dict, List, Optional
import os

# Try to import redislite, but make it optional
try:
    import redislite
    REDISLITE_AVAILABLE = True
except ImportError:
    REDISLITE_AVAILABLE = False
    redislite = None


class StockDatabase:
    def __init__(self, tinydb_path: str = "data/index.json", redis_db_path: str = "data/cache.db"):
        # Initialize TinyDB for persistent storage
        self.tinydb = TinyDB(tinydb_path)
        self.query = Query()
        
        # Initialize redislite for embedded caching (optional)
        self.redis_client = None
        if REDISLITE_AVAILABLE:
            try:
                self.redis_client = redislite.Redis(redis_db_path)
                # Test Redis connection
                self.redis_client.ping()
            except Exception as e:
                print(f"Warning: Could not initialize redislite. Running without caching: {e}")
                self.redis_client = None
        else:
            print("Info: redislite not available. Running without caching.")

    def index_crawled_file(self, filepath: str, metadata: Dict) -> bool:
        """Index a crawled file in TinyDB, avoiding duplicates and loading actual content"""
        try:
            # Load the actual JSON file content
            file_data = None
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    file_data = json.load(f)
            except Exception as e:
                print(f"Warning: Could not load file content from {filepath}: {e}")

            # Check if a record with the same filepath already exists
            existing_records = self.tinydb.search(self.query.filepath == filepath)

            if existing_records:
                # Update the existing record instead of inserting a new one
                record = {
                    "filepath": filepath,
                    "timestamp": datetime.now().isoformat(),
                    "metadata": metadata,
                    "indexed_at": datetime.now().isoformat(),
                    "data": file_data  # Include actual file content
                }

                # Update the first matching record
                self.tinydb.update(record, self.query.filepath == filepath)

                # Update cache if available
                if self.redis_client:
                    cache_key = f"file:{os.path.basename(filepath)}"
                    self.redis_client.setex(
                        cache_key,
                        3600,  # 1 hour cache
                        json.dumps(record)
                    )

                return True
            else:
                # Insert new record
                record = {
                    "filepath": filepath,
                    "timestamp": datetime.now().isoformat(),
                    "metadata": metadata,
                    "indexed_at": datetime.now().isoformat(),
                    "data": file_data  # Include actual file content
                }

                # Insert into TinyDB
                self.tinydb.insert(record)

                # Cache in redislite if available
                if self.redis_client:
                    cache_key = f"file:{os.path.basename(filepath)}"
                    self.redis_client.setex(
                        cache_key,
                        3600,  # 1 hour cache
                        json.dumps(record)
                    )

                return True
        except Exception as e:
            print(f"Error indexing file: {e}")
            return False

    def search_by_date_range(self, start_date: str, end_date: str) -> List[Dict]:
        """Search for records within a date range"""
        # Convert date strings to datetime objects for comparison
        def filter_by_date(record):
            record_time = datetime.fromisoformat(record['timestamp'].replace('Z', '+00:00'))
            start = datetime.fromisoformat(start_date)
            end = datetime.fromisoformat(end_date)
            return start <= record_time <= end
        
        results = self.tinydb.search(
            self.query.timestamp.test(filter_by_date)
        )
        return results

    def search_by_site(self, site_name: str) -> List[Dict]:
        """Search for records from a specific site"""
        results = self.tinydb.search(
            self.query.metadata.site == site_name
        )
        return results

    def get_latest_records(self, limit: int = 10) -> List[Dict]:
        """Get the latest records up to the specified limit"""
        all_records = self.tinydb.all()
        # Sort by timestamp in descending order
        sorted_records = sorted(all_records, key=lambda x: x['timestamp'], reverse=True)
        return sorted_records[:limit]

    def get_record_by_id(self, record_id: int) -> Optional[Dict]:
        """Get a record by its TinyDB ID"""
        result = self.tinydb.get(doc_id=record_id)
        return result

    def get_all_sites(self) -> List[str]:
        """Get all unique sites in the database"""
        all_records = self.tinydb.all()
        sites = set()
        for record in all_records:
            if 'site' in record.get('metadata', {}):
                sites.add(record['metadata']['site'])
        return list(sites)

    def get_statistics(self) -> Dict:
        """Get database statistics"""
        total_records = len(self.tinydb)
        all_records = self.tinydb.all()
        
        site_counts = {}
        for record in all_records:
            site = record.get('metadata', {}).get('site', 'unknown')
            site_counts[site] = site_counts.get(site, 0) + 1
        
        return {
            "total_records": total_records,
            "sites": site_counts,
            "latest_update": max([r['timestamp'] for r in all_records]) if all_records else None
        }