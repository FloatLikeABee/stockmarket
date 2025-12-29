#!/usr/bin/env python3
"""
Script to clean up crawled data files older than 15 days
"""
import os
from pathlib import Path
from datetime import datetime, timedelta
from backend.database import StockDatabase


def cleanup_old_files(days_to_keep: int = 15):
    """
    Remove data files older than specified days and clean up database
    
    Args:
        days_to_keep: Number of days to keep files (default: 15)
    """
    print(f"🧹 Starting cleanup of files older than {days_to_keep} days...")
    print("=" * 70)
    
    # Calculate cutoff date
    cutoff_date = datetime.now() - timedelta(days=days_to_keep)
    print(f"Cutoff date: {cutoff_date.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Files older than this will be deleted.\n")
    
    # Initialize database
    db = StockDatabase()
    
    # Track statistics
    files_deleted = 0
    files_kept = 0
    total_size_deleted = 0
    errors = 0
    
    # Find all JSON files in data directory
    data_dir = Path("data")
    
    for category_dir in data_dir.iterdir():
        if category_dir.is_dir() and category_dir.name not in ['__pycache__']:
            print(f"\n📁 Checking directory: {category_dir.name}/")
            
            for json_file in category_dir.glob("*.json"):
                try:
                    # Get file modification time
                    file_mtime = datetime.fromtimestamp(json_file.stat().st_mtime)
                    file_size = json_file.stat().st_size
                    
                    if file_mtime < cutoff_date:
                        # File is older than cutoff date - delete it
                        print(f"  ❌ Deleting: {json_file.name} (from {file_mtime.strftime('%Y-%m-%d')})")
                        
                        # Remove from database first
                        db.tinydb.remove(db.query.filepath == str(json_file))
                        
                        # Delete the file
                        json_file.unlink()
                        
                        files_deleted += 1
                        total_size_deleted += file_size
                    else:
                        files_kept += 1
                        
                except Exception as e:
                    print(f"  ⚠️  Error processing {json_file.name}: {e}")
                    errors += 1
    
    # Clean up any orphaned database records (files that don't exist)
    print(f"\n🔍 Checking for orphaned database records...")
    all_records = db.tinydb.all()
    orphaned_records = 0
    
    for record in all_records:
        filepath = record.get('filepath')
        if filepath and not Path(filepath).exists():
            db.tinydb.remove(doc_ids=[record.doc_id])
            orphaned_records += 1
            print(f"  🗑️  Removed orphaned record: {Path(filepath).name}")
    
    # Remove duplicates
    print(f"\n🔍 Checking for duplicate records...")
    duplicates_removed = db.remove_duplicates()
    
    # Print summary
    print("\n" + "=" * 70)
    print("✅ Cleanup Complete!")
    print("=" * 70)
    print(f"  Files deleted: {files_deleted}")
    print(f"  Files kept: {files_kept}")
    print(f"  Space freed: {total_size_deleted / 1024 / 1024:.2f} MB")
    print(f"  Orphaned records removed: {orphaned_records}")
    print(f"  Duplicate records removed: {duplicates_removed}")
    print(f"  Errors: {errors}")
    print(f"  Total records in database: {len(db.tinydb)}")
    print("=" * 70)
    
    if files_deleted > 0:
        print(f"🎉 Successfully cleaned up {files_deleted} old file(s)!")
    else:
        print("✨ No old files to clean up - all files are recent!")


if __name__ == "__main__":
    import sys
    
    # Allow custom days parameter
    days = 15
    if len(sys.argv) > 1:
        try:
            days = int(sys.argv[1])
        except ValueError:
            print("Usage: python cleanup_old_files.py [days_to_keep]")
            print("Example: python cleanup_old_files.py 30")
            sys.exit(1)
    
    cleanup_old_files(days)

