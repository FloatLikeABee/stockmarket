"""
SQLite database for storing stock data with pagination support
"""
import sqlite3
import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import os


class StockDatabaseSQLite:
    """SQLite database for storing stock market data"""
    
    def __init__(self, db_path: str = "data/stocks.db"):
        """Initialize SQLite database"""
        self.db_path = db_path
        self._ensure_db_dir()
        self._init_database()
    
    def _ensure_db_dir(self):
        """Ensure the database directory exists"""
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)
    
    def _init_database(self):
        """Initialize database tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create stocks table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS stocks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                name TEXT,
                price REAL,
                change REAL,
                change_percent TEXT,
                volume REAL,
                turnover REAL,
                high REAL,
                low REAL,
                open REAL,
                yesterday_close REAL,
                turnover_rate TEXT,
                pe_ratio TEXT,
                market_cap TEXT,
                circulating_market_cap TEXT,
                timestamp TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(symbol, timestamp)
            )
        ''')
        
        # Create indices for faster queries
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_symbol ON stocks(symbol)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON stocks(timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_symbol_timestamp ON stocks(symbol, timestamp)')
        
        conn.commit()
        conn.close()
    
    def insert_stocks(self, stocks: List[Dict], timestamp: Optional[str] = None) -> int:
        """Insert or update stock data"""
        if not timestamp:
            timestamp = datetime.now().isoformat()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        inserted_count = 0
        created_at = datetime.now().isoformat()
        
        for stock in stocks:
            try:
                cursor.execute('''
                    INSERT OR REPLACE INTO stocks 
                    (symbol, name, price, change, change_percent, volume, turnover,
                     high, low, open, yesterday_close, turnover_rate, pe_ratio,
                     market_cap, circulating_market_cap, timestamp, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    stock.get('symbol', ''),
                    stock.get('name', ''),
                    self._safe_float(stock.get('price')),
                    self._safe_float(stock.get('change')),
                    stock.get('change_percent', ''),
                    self._safe_float(stock.get('volume')),
                    self._safe_float(stock.get('turnover')),
                    self._safe_float(stock.get('high')),
                    self._safe_float(stock.get('low')),
                    self._safe_float(stock.get('open')),
                    self._safe_float(stock.get('yesterday_close')),
                    stock.get('turnover_rate', ''),
                    stock.get('pe_ratio', ''),
                    stock.get('market_cap', ''),
                    stock.get('circulating_market_cap', ''),
                    timestamp,
                    created_at
                ))
                inserted_count += 1
            except Exception as e:
                print(f"[StockDB] Error inserting stock {stock.get('symbol', 'unknown')}: {e}")
        
        conn.commit()
        conn.close()
        return inserted_count
    
    def get_stocks_paginated(self, page: int = 1, per_page: int = 50, 
                            order_by: str = 'symbol', order_dir: str = 'ASC',
                            symbol_filter: Optional[str] = None,
                            latest_only: bool = True) -> Tuple[List[Dict], int]:
        """Get stocks with pagination"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Build WHERE clause
        where_clauses = []
        if latest_only:
            # Get only the latest timestamp for each stock
            where_clauses.append("timestamp = (SELECT MAX(timestamp) FROM stocks s2 WHERE s2.symbol = stocks.symbol)")
        if symbol_filter:
            where_clauses.append(f"symbol LIKE '%{symbol_filter}%'")
        
        where_sql = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""
        
        # Validate order_by to prevent SQL injection
        valid_order_by = ['symbol', 'name', 'price', 'change', 'change_percent', 'volume', 'timestamp']
        if order_by not in valid_order_by:
            order_by = 'symbol'
        
        order_dir = 'ASC' if order_dir.upper() == 'ASC' else 'DESC'
        
        # Get total count
        count_sql = f"SELECT COUNT(DISTINCT symbol) FROM stocks{where_sql}"
        cursor.execute(count_sql)
        total_count = cursor.fetchone()[0]
        
        # Get paginated data
        offset = (page - 1) * per_page
        query_sql = f'''
            SELECT * FROM stocks
            {where_sql}
            ORDER BY {order_by} {order_dir}
            LIMIT ? OFFSET ?
        '''
        
        cursor.execute(query_sql, (per_page, offset))
        rows = cursor.fetchall()
        
        stocks = [dict(row) for row in rows]
        
        conn.close()
        return stocks, total_count
    
    def get_latest_stocks(self, limit: int = 100) -> List[Dict]:
        """Get latest stock data (one record per symbol)"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM stocks s1
            WHERE timestamp = (SELECT MAX(timestamp) FROM stocks s2 WHERE s2.symbol = s1.symbol)
            ORDER BY symbol
            LIMIT ?
        ''', (limit,))
        
        rows = cursor.fetchall()
        stocks = [dict(row) for row in rows]
        
        conn.close()
        return stocks
    
    def cleanup_old_data(self, days_to_keep: int = 1):
        """Remove stock data older than specified days"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cutoff_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        cutoff_date = cutoff_date.replace(day=cutoff_date.day - days_to_keep)
        cutoff_timestamp = cutoff_date.isoformat()
        
        # Delete old stock records
        cursor.execute('DELETE FROM stocks WHERE timestamp < ?', (cutoff_timestamp,))
        stocks_deleted = cursor.rowcount
        
        conn.commit()
        conn.close()
        
        print(f"[StockDB] Cleaned up {stocks_deleted} stock records older than {days_to_keep} days")
        return stocks_deleted
    
    def _safe_float(self, value) -> Optional[float]:
        """Safely convert value to float"""
        if value is None or value == 'N/A' or value == '':
            return None
        try:
            if isinstance(value, str):
                # Remove % and other non-numeric characters
                value = value.replace('%', '').replace(',', '').strip()
            return float(value)
        except (ValueError, TypeError):
            return None

