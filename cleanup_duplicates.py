#!/usr/bin/env python3
"""
Script to remove duplicate records from the database without full reindexing
"""
from backend.database import StockDatabase


def cleanup_duplicates():
    """Remove duplicate records from the database"""
    print("🧹 Starting duplicate cleanup...")
    print("=" * 60)
    
    db = StockDatabase()
    
    # Get initial statistics
    initial_count = len(db.tinydb)
    print(f"Initial record count: {initial_count}")
    
    # Remove duplicates
    duplicates_removed = db.remove_duplicates()
    
    # Get final statistics
    final_count = len(db.tinydb)
    
    print("=" * 60)
    print(f"✅ Cleanup complete!")
    print(f"  Records before: {initial_count}")
    print(f"  Duplicates removed: {duplicates_removed}")
    print(f"  Records after: {final_count}")
    print("=" * 60)
    
    if duplicates_removed == 0:
        print("✨ No duplicates found - database is clean!")
    else:
        print(f"🎉 Successfully removed {duplicates_removed} duplicate record(s)!")


if __name__ == "__main__":
    cleanup_duplicates()

