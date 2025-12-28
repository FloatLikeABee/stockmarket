#!/usr/bin/env python3
"""
Script to reindex all crawled data files with their actual content
"""
import os
import json
from pathlib import Path
from backend.database import StockDatabase

def reindex_all_files():
    """Reindex all JSON files in the data directory"""
    db = StockDatabase()
    
    # Clear existing database
    db.tinydb.truncate()
    print("Cleared existing database")
    
    # Find all JSON files in data directory
    data_dir = Path("data")
    json_files = []
    
    for category_dir in data_dir.iterdir():
        if category_dir.is_dir() and category_dir.name not in ['__pycache__']:
            for json_file in category_dir.glob("*.json"):
                json_files.append((json_file, category_dir.name))
    
    print(f"Found {len(json_files)} JSON files to reindex")
    
    # Reindex each file
    for filepath, category in json_files:
        try:
            # Load the file to extract metadata
            with open(filepath, 'r', encoding='utf-8') as f:
                file_data = json.load(f)
            
            # Extract sites and timestamp from the data
            sites_crawled = list(file_data.keys())
            timestamp = ""
            
            # Get timestamp from first site's data
            if sites_crawled:
                first_site = sites_crawled[0]
                timestamp = file_data[first_site].get("timestamp", "")
            
            # Create metadata
            metadata = {
                "category": category,
                "sites_crawled": sites_crawled,
                "timestamp": timestamp
            }
            
            # Index the file
            db.index_crawled_file(str(filepath), metadata)
            print(f"Indexed: {filepath}")
            
        except Exception as e:
            print(f"Error indexing {filepath}: {e}")
    
    print(f"\nReindexing complete! Total records: {len(db.tinydb)}")
    
    # Show statistics
    stats = db.get_statistics()
    print(f"\nDatabase Statistics:")
    print(f"Total records: {stats['total_records']}")
    print(f"Sites: {stats['sites']}")
    print(f"Latest update: {stats['latest_update']}")

if __name__ == "__main__":
    reindex_all_files()

