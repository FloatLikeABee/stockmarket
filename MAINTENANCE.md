# Maintenance & Cleanup Guide

This document describes the automated maintenance features and manual cleanup tools for the Chinese Stock Market Data Crawler.

## 🤖 Automated Features

### 1. Scheduled Crawling
- **Frequency**: Every **1 hour** (changed from 20 minutes)
- **Location**: `backend/api.py` - `_schedule_crawling()` method
- **Runs automatically** when the backend starts

### 2. Automatic File Cleanup
- **Frequency**: Every **24 hours**
- **Retention**: Keeps files for **15 days**
- **Location**: `backend/cleanup_scheduler.py`
- **Runs automatically** when the backend starts
- **Actions**:
  - Deletes data files older than 15 days
  - Removes orphaned database records
  - Removes duplicate database entries

## 🛠️ Manual Cleanup Tools

### 1. Clean Up Old Files
Remove data files older than a specified number of days:

```bash
# Clean files older than 15 days (default)
python cleanup_old_files.py

# Clean files older than 30 days
python cleanup_old_files.py 30

# Clean files older than 7 days
python cleanup_old_files.py 7
```

**What it does:**
- ✅ Deletes JSON files older than specified days
- ✅ Removes corresponding database records
- ✅ Cleans up orphaned database entries
- ✅ Removes duplicate records
- ✅ Shows detailed statistics

### 2. Remove Duplicate Records
Clean up duplicate database entries without deleting files:

```bash
python cleanup_duplicates.py
```

**What it does:**
- ✅ Finds duplicate records (same filepath)
- ✅ Keeps the most recent record
- ✅ Removes older duplicates

### 3. Reindex Database
Rebuild the entire database from scratch:

```bash
python reindex_database.py
```

**What it does:**
- ✅ Clears existing database
- ✅ Scans all JSON files in `data/` directory
- ✅ Indexes each file with metadata
- ✅ Removes duplicates after indexing
- ✅ Shows detailed statistics

## 📊 File Retention Policy

| File Age | Action |
|----------|--------|
| 0-15 days | **Kept** - Active data |
| 15+ days | **Deleted** - Automatically removed daily |

## 🗂️ Data Storage

### Directory Structure
```
data/
├── manual/          # Manually triggered crawls
│   └── stock_data_manual_YYYYMMDD_HHMMSS.json
├── scheduled/       # Automatically scheduled crawls
│   └── stock_data_scheduled_YYYYMMDD_HHMMSS.json
├── index.json       # TinyDB database index
└── cache.db         # Redis cache
```

### File Naming Convention
- **Manual**: `stock_data_manual_YYYYMMDD_HHMMSS.json`
- **Scheduled**: `stock_data_scheduled_YYYYMMDD_HHMMSS.json`

## 🔧 Configuration

### Change Retention Period
Edit `backend/api.py`:
```python
self.cleanup_scheduler = CleanupScheduler(
    days_to_keep=15,           # Change this number
    check_interval_hours=24    # How often to run cleanup
)
```

### Change Crawl Frequency
Edit `backend/api.py`:
```python
time.sleep(60 * 60)  # 1 hour in seconds
# Change to: time.sleep(30 * 60) for 30 minutes
```

## 📈 Monitoring

### Check Database Statistics
The API provides statistics at: `GET /stats`

Returns:
```json
{
  "total_records": 65,
  "sites": {
    "tonghuashun": 13,
    "dongfangcaifu": 13,
    ...
  },
  "latest_update": "2025-12-28T21:11:20"
}
```

### View Latest Records
API endpoint: `GET /data/latest?limit=10`

## ⚠️ Important Notes

1. **Automatic cleanup runs in the background** - No manual intervention needed
2. **Files are permanently deleted** - Make sure you have backups if needed
3. **Database is automatically maintained** - Duplicates and orphaned records are cleaned up
4. **Cleanup runs daily** - First cleanup happens 24 hours after server start

## 🚀 Best Practices

1. **Monitor disk space** regularly
2. **Adjust retention period** based on your needs
3. **Run manual cleanup** if you need immediate space
4. **Backup important data** before running cleanup scripts
5. **Check logs** for cleanup activity

## 📝 Logs

Cleanup activities are logged to console:
- ✅ Successful operations
- ⚠️ Warnings for non-critical issues
- ❌ Errors for failed operations

Example log output:
```
🧹 [Scheduled Cleanup] Starting cleanup of files older than 15 days...
✅ [Scheduled Cleanup] Complete: 5 files deleted, 2.34 MB freed, 0 orphaned records, 0 duplicates removed
```

