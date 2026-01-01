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
        # Initialize TinyDB for persistent storage with error handling
        try:
            # Check if file exists and is valid JSON
            if os.path.exists(tinydb_path):
                try:
                    # Try to read and validate the JSON file
                    with open(tinydb_path, 'r', encoding='utf-8') as f:
                        content = f.read().strip()
                        if content:
                            json.loads(content)  # Validate JSON
                        else:
                            # File is empty, will be initialized by TinyDB
                            print(f"[Database] Warning: {tinydb_path} is empty, initializing new database")
                except json.JSONDecodeError as e:
                    # File is corrupted, backup and create new one
                    backup_path = f"{tinydb_path}.backup"
                    print(f"[Database] Warning: {tinydb_path} appears corrupted (JSON error: {e}), backing up and creating new database")
                    try:
                        import shutil
                        shutil.copy2(tinydb_path, backup_path)
                        print(f"[Database] Corrupted file backed up to {backup_path}")
                    except Exception as backup_error:
                        print(f"[Database] Could not backup corrupted file: {backup_error}")
                    # Remove corrupted file so TinyDB can create a new one
                    try:
                        os.remove(tinydb_path)
                    except Exception as remove_error:
                        print(f"[Database] Could not remove corrupted file: {remove_error}")
            
            # Initialize TinyDB (will create file if it doesn't exist)
            self.tinydb = TinyDB(tinydb_path)
            self.query = Query()
            
        except Exception as e:
            print(f"[Database] Error initializing TinyDB: {e}")
            # Try to create a fresh database
            try:
                if os.path.exists(tinydb_path):
                    backup_path = f"{tinydb_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    import shutil
                    shutil.move(tinydb_path, backup_path)
                    print(f"[Database] Moved corrupted file to {backup_path}")
                self.tinydb = TinyDB(tinydb_path)
                self.query = Query()
                print("[Database] Created new database file")
            except Exception as e2:
                print(f"[Database] Critical error: Could not initialize database: {e2}")
                raise
        
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

            # Create the record data
            record = {
                "filepath": filepath,
                "timestamp": metadata.get("timestamp", datetime.now().isoformat()),
                "metadata": metadata,
                "indexed_at": datetime.now().isoformat(),
                "data": file_data  # Include actual file content
            }

            if existing_records:
                # Update the existing record instead of inserting a new one
                # Use the document ID from the first existing record
                doc_id = existing_records[0].doc_id

                # Update using the document ID to avoid conflicts
                self.tinydb.update(record, doc_ids=[doc_id])

                print(f"Updated existing record (ID: {doc_id}) for {filepath}")
            else:
                # Insert new record - let TinyDB assign the next available ID
                # Handle potential duplicate ID errors
                try:
                    doc_id = self.tinydb.insert(record)
                    print(f"Inserted new record (ID: {doc_id}) for {filepath}")
                except ValueError as ve:
                    # Handle "Document with ID already exists" error
                    if "already exists" in str(ve):
                        print(f"[Database] Warning: Document ID conflict for {filepath}, attempting to resolve...")
                        # Try to find if there's actually a duplicate by checking all records
                        all_records = self.tinydb.all()
                        found_duplicate = False
                        for existing_record in all_records:
                            if existing_record.get('filepath') == filepath:
                                # Found a duplicate by filepath, update it instead
                                doc_id = existing_record.doc_id
                                self.tinydb.update(record, doc_ids=[doc_id])
                                print(f"Updated existing record (ID: {doc_id}) for {filepath} (resolved duplicate)")
                                found_duplicate = True
                                break
                        
                        if not found_duplicate:
                            # No duplicate by filepath, but ID conflict exists
                            # Try to extract the conflicting ID and handle it
                            try:
                                # Extract ID from error message if possible
                                import re
                                id_match = re.search(r'ID (\d+)', str(ve))
                                if id_match:
                                    conflicting_id = int(id_match.group(1))
                                    # Check if that document exists
                                    existing_doc = self.tinydb.get(doc_id=conflicting_id)
                                    if existing_doc:
                                        # Check if it's the same filepath (shouldn't happen, but check anyway)
                                        if existing_doc.get('filepath') == filepath:
                                            # Same filepath, just update it
                                            self.tinydb.update(record, doc_ids=[conflicting_id])
                                            print(f"Updated existing record (ID: {conflicting_id}) for {filepath}")
                                        else:
                                            # Different filepath - this is a real conflict
                                            # Remove the old document and insert the new one
                                            self.tinydb.remove(doc_ids=[conflicting_id])
                                            doc_id = self.tinydb.insert(record)
                                            print(f"Resolved ID conflict: removed old doc (ID: {conflicting_id}), inserted new (ID: {doc_id}) for {filepath}")
                                    else:
                                        # Document doesn't exist at that ID (database inconsistency)
                                        # Try insert again - the ID should be free now
                                        try:
                                            doc_id = self.tinydb.insert(record)
                                            print(f"Inserted new record (ID: {doc_id}) for {filepath} (after clearing inconsistent ID)")
                                        except ValueError as retry_error:
                                            # Still failing, skip this insert
                                            print(f"[Database] Could not insert after conflict resolution: {retry_error}")
                                            return False
                                else:
                                    # Can't extract ID from error message
                                    print(f"[Database] Could not extract ID from error message, skipping insert for {filepath}")
                                    return False
                            except Exception as resolve_error:
                                print(f"[Database] Error resolving ID conflict: {resolve_error}")
                                import traceback
                                traceback.print_exc()
                                return False
                    else:
                        # Different ValueError, re-raise it
                        raise

            # Update cache if available
            if self.redis_client:
                try:
                    cache_key = f"file:{os.path.basename(filepath)}"
                    self.redis_client.setex(
                        cache_key,
                        3600,  # 1 hour cache
                        json.dumps(record)
                    )
                except Exception as cache_error:
                    print(f"Warning: Could not update cache: {cache_error}")

            return True
        except Exception as e:
            print(f"Error indexing file {filepath}: {e}")
            import traceback
            traceback.print_exc()
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
        try:
            all_records = self.tinydb.all()
            if not all_records:
                return []
            # Sort by timestamp in descending order
            sorted_records = sorted(all_records, key=lambda x: x.get('timestamp', ''), reverse=True)
            return sorted_records[:limit]
        except json.JSONDecodeError as e:
            print(f"[Database] JSON decode error in get_latest_records: {e}")
            print("[Database] Attempting to recover database...")
            # Try to reinitialize the database
            try:
                self._recover_database()
                return []  # Return empty list after recovery
            except Exception as recovery_error:
                print(f"[Database] Could not recover database: {recovery_error}")
                return []
        except Exception as e:
            print(f"[Database] Error in get_latest_records: {e}")
            import traceback
            traceback.print_exc()
            return []

    def get_record_by_id(self, record_id: int) -> Optional[Dict]:
        """Get a record by its TinyDB ID"""
        result = self.tinydb.get(doc_id=record_id)
        return result

    def get_all_sites(self) -> List[str]:
        """Get all unique sites in the database"""
        try:
            all_records = self.tinydb.all()
            sites = set()
            for record in all_records:
                metadata = record.get('metadata', {})
                if isinstance(metadata, dict) and 'sites_crawled' in metadata:
                    # Handle sites_crawled list
                    for site in metadata.get('sites_crawled', []):
                        sites.add(site)
                elif isinstance(metadata, dict) and 'site' in metadata:
                    sites.add(metadata['site'])
            return list(sites)
        except Exception as e:
            print(f"[Database] Error in get_all_sites: {e}")
            return []

    def _recover_database(self):
        """Recover from a corrupted database file"""
        tinydb_path = self.tinydb.storage.path
        try:
            # Close current connection
            self.tinydb.close()
            
            # Backup corrupted file
            if os.path.exists(tinydb_path):
                backup_path = f"{tinydb_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                import shutil
                shutil.copy2(tinydb_path, backup_path)
                print(f"[Database] Backed up corrupted file to {backup_path}")
                os.remove(tinydb_path)
            
            # Reinitialize TinyDB
            self.tinydb = TinyDB(tinydb_path)
            self.query = Query()
            print("[Database] Database recovered successfully")
        except Exception as e:
            print(f"[Database] Error recovering database: {e}")
            raise

    def get_statistics(self) -> Dict:
        """Get database statistics"""
        try:
            # Try to get total records count safely
            try:
                total_records = len(self.tinydb)
            except Exception:
                total_records = 0
            
            # Try to get all records safely
            try:
                all_records = self.tinydb.all()
            except json.JSONDecodeError:
                # If JSON decode fails, try to recover and return empty stats
                print("[Database] JSON decode error when reading records, attempting recovery...")
                try:
                    self._recover_database()
                    all_records = []
                except:
                    all_records = []
            except Exception as e:
                print(f"[Database] Error reading records: {e}")
                all_records = []

            site_counts = {}
            timestamps = []
            
            for record in all_records:
                try:
                    metadata = record.get('metadata', {})
                    if isinstance(metadata, dict):
                        # Handle sites_crawled list
                        sites_crawled = metadata.get('sites_crawled', [])
                        if sites_crawled:
                            for site in sites_crawled:
                                if site:
                                    site_counts[site] = site_counts.get(site, 0) + 1
                        # Also handle single site
                        site = metadata.get('site', 'unknown')
                        if site != 'unknown':
                            site_counts[site] = site_counts.get(site, 0) + 1
                    
                    # Collect timestamps safely
                    timestamp = record.get('timestamp', '')
                    if timestamp:
                        timestamps.append(timestamp)
                except Exception as record_error:
                    # Skip problematic records
                    print(f"[Database] Error processing record: {record_error}")
                    continue

            # Get latest update safely
            latest_update = None
            if timestamps:
                try:
                    latest_update = max(timestamps)
                except Exception:
                    latest_update = timestamps[0] if timestamps else None

            return {
                "total_records": total_records,
                "sites": site_counts,
                "latest_update": latest_update
            }
        except json.JSONDecodeError as e:
            print(f"[Database] JSON decode error in get_statistics: {e}")
            try:
                self._recover_database()
            except Exception as recovery_error:
                print(f"[Database] Could not recover database: {recovery_error}")
            return {
                "total_records": 0,
                "sites": {},
                "latest_update": None
            }
        except Exception as e:
            print(f"[Database] Error in get_statistics: {e}")
            return {
                "total_records": 0,
                "sites": {},
                "latest_update": None
            }

    def remove_duplicates(self) -> int:
        """Remove duplicate records based on filepath, keeping the most recent one"""
        try:
            all_records = self.tinydb.all()
            filepath_map = {}
            duplicates_removed = 0

            # Group records by filepath
            for record in all_records:
                filepath = record.get('filepath')
                if not filepath:
                    continue

                if filepath not in filepath_map:
                    filepath_map[filepath] = []
                filepath_map[filepath].append(record)

            # For each filepath with duplicates, keep only the most recent
            for filepath, records in filepath_map.items():
                if len(records) > 1:
                    # Sort by indexed_at timestamp, most recent first
                    sorted_records = sorted(
                        records,
                        key=lambda x: x.get('indexed_at', ''),
                        reverse=True
                    )

                    # Keep the first (most recent), remove the rest
                    for record in sorted_records[1:]:
                        self.tinydb.remove(doc_ids=[record.doc_id])
                        duplicates_removed += 1
                        print(f"Removed duplicate record (ID: {record.doc_id}) for {filepath}")

            return duplicates_removed
        except json.JSONDecodeError as e:
            print(f"[Database] JSON decode error in remove_duplicates: {e}")
            try:
                self._recover_database()
            except Exception as recovery_error:
                print(f"[Database] Could not recover database: {recovery_error}")
            return 0
        except Exception as e:
            print(f"[Database] Error in remove_duplicates: {e}")
            return 0