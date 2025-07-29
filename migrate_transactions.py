#!/usr/bin/env python3
"""
Database migration script for transactions table.
This script handles database schema updates and data migrations.
"""

import sqlite3
import os
import sys
from datetime import datetime

def get_db_path():
    """Get the database file path."""
    return os.path.join(os.path.dirname(__file__), 'telegram_bot.db')

def migrate_transactions():
    """Perform transaction table migrations."""
    db_path = get_db_path()
    
    if not os.path.exists(db_path):
        print(f"Database file not found: {db_path}")
        return True  # Not an error if DB doesn't exist yet
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if transactions table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='transactions'
        """)
        
        if not cursor.fetchone():
            print("Transactions table doesn't exist yet. Migration not needed.")
            conn.close()
            return True
        
        # Check current table structure
        cursor.execute("PRAGMA table_info(transactions)")
        columns = [column[1] for column in cursor.fetchall()]
        
        # Add any missing columns that might be needed
        migrations_applied = []
        
        # Example migration: Add service_date column if it doesn't exist
        if 'service_date' not in columns:
            try:
                cursor.execute("ALTER TABLE transactions ADD COLUMN service_date TEXT")
                migrations_applied.append("Added service_date column")
            except sqlite3.OperationalError as e:
                if "duplicate column name" not in str(e).lower():
                    raise
        
        # Example migration: Add status column if it doesn't exist
        if 'status' not in columns:
            try:
                cursor.execute("ALTER TABLE transactions ADD COLUMN status TEXT DEFAULT 'completed'")
                migrations_applied.append("Added status column")
            except sqlite3.OperationalError as e:
                if "duplicate column name" not in str(e).lower():
                    raise
        
        conn.commit()
        conn.close()
        
        if migrations_applied:
            print(f"Migration completed successfully. Applied: {', '.join(migrations_applied)}")
        else:
            print("No migrations needed. Database is up to date.")
        
        return True
        
    except Exception as e:
        print(f"Migration failed: {e}")
        return False

if __name__ == "__main__":
    success = migrate_transactions()
    sys.exit(0 if success else 1)