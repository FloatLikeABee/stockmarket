"""
Automatic cleanup scheduler - runs daily to remove old files
"""
import threading
import time
from datetime import datetime
from pathlib import Path
from datetime import timedelta


class CleanupScheduler:
    """Schedules automatic cleanup of old data files"""
    
    def __init__(self, days_to_keep: int = 1, check_interval_hours: int = 24):
        """
        Initialize cleanup scheduler
        
        Args:
            days_to_keep: Number of days to keep files (default: 15)
            check_interval_hours: How often to run cleanup in hours (default: 24)
        """
        self.days_to_keep = days_to_keep
        self.check_interval = check_interval_hours * 3600  # Convert to seconds
        self.running = False
        self.thread = None
        
    def cleanup_old_files(self):
        """Remove data files older than specified days"""
        from backend.database import StockDatabase
        
        print(f"\n🧹 [Scheduled Cleanup] Starting cleanup of files older than {self.days_to_keep} days...")
        
        cutoff_date = datetime.now() - timedelta(days=self.days_to_keep)
        db = StockDatabase()
        
        files_deleted = 0
        total_size_deleted = 0
        
        # Find and delete old files
        data_dir = Path("data")
        
        for category_dir in data_dir.iterdir():
            if category_dir.is_dir() and category_dir.name not in ['__pycache__']:
                for json_file in category_dir.glob("*.json"):
                    try:
                        file_mtime = datetime.fromtimestamp(json_file.stat().st_mtime)
                        
                        if file_mtime < cutoff_date:
                            file_size = json_file.stat().st_size
                            
                            # Remove from database
                            db.tinydb.remove(db.query.filepath == str(json_file))
                            
                            # Delete file
                            json_file.unlink()
                            
                            files_deleted += 1
                            total_size_deleted += file_size
                            
                    except Exception as e:
                        print(f"  ⚠️  Error processing {json_file.name}: {e}")
        
        # Clean up orphaned records
        all_records = db.tinydb.all()
        orphaned = 0
        
        for record in all_records:
            filepath = record.get('filepath')
            if filepath and not Path(filepath).exists():
                db.tinydb.remove(doc_ids=[record.doc_id])
                orphaned += 1
        
        # Remove duplicates
        duplicates = db.remove_duplicates()
        
        print(f"✅ [Scheduled Cleanup] Complete: {files_deleted} files deleted, "
              f"{total_size_deleted / 1024 / 1024:.2f} MB freed, "
              f"{orphaned} orphaned records, {duplicates} duplicates removed")
        
    def _run_scheduler(self):
        """Background thread that runs cleanup periodically"""
        print(f"🕐 Cleanup scheduler started: will run every {self.check_interval / 3600:.0f} hours")
        
        while self.running:
            try:
                # Wait for the interval
                time.sleep(self.check_interval)
                
                # Run cleanup
                self.cleanup_old_files()
                
            except Exception as e:
                print(f"❌ Error in cleanup scheduler: {e}")
    
    def start(self):
        """Start the cleanup scheduler"""
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._run_scheduler, daemon=True)
            self.thread.start()
            print(f"✅ Cleanup scheduler started (keeps files for {self.days_to_keep} days)")
    
    def stop(self):
        """Stop the cleanup scheduler"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        print("🛑 Cleanup scheduler stopped")

