#!/usr/bin/env python3
"""
Database migration script to add customer page functionality.
This script adds the necessary columns to the User table for customer pages.
"""

import sys
import os
from datetime import datetime
from sqlalchemy import text

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import db_manager, logger

def migrate_customer_pages():
    """Add customer page columns to User table."""
    try:
        print("[INFO] Starting customer pages migration...")
        
        # Get a database session
        with db_manager.get_session() as session:
            # Check if columns already exist
            try:
                result = session.execute(text(
                    "SELECT customer_page_id FROM users LIMIT 1"
                ))
                print("[INFO] Customer page columns already exist. Migration not needed.")
                return True
            except Exception:
                # Columns don't exist, proceed with migration
                pass
            
            print("[INFO] Adding customer page columns to users table...")
            
            # Add customer_page_id column (without UNIQUE constraint initially)
            session.execute(text(
                "ALTER TABLE users ADD COLUMN customer_page_id VARCHAR(255)"
            ))
            print("[SUCCESS] Added customer_page_id column")
            
            # Add customer_page_created column
            session.execute(text(
                "ALTER TABLE users ADD COLUMN customer_page_created TIMESTAMP"
            ))
            print("[SUCCESS] Added customer_page_created column")
            
            # Add customer_page_last_accessed column
            session.execute(text(
                "ALTER TABLE users ADD COLUMN customer_page_last_accessed TIMESTAMP"
            ))
            print("[SUCCESS] Added customer_page_last_accessed column")
            
            # Commit the changes
            session.commit()
            print("[SUCCESS] Customer pages migration completed successfully!")
            
            # Create unique index on customer_page_id for better performance and uniqueness
            try:
                session.execute(text(
                    "CREATE UNIQUE INDEX idx_users_customer_page_id ON users(customer_page_id)"
                ))
                session.commit()
                print("[SUCCESS] Created unique index on customer_page_id")
            except Exception as e:
                print(f"[WARNING] Could not create unique index (may already exist): {e}")
            
            return True
            
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        print(f"[ERROR] Migration failed: {e}")
        return False

def verify_migration():
    """Verify that the migration was successful."""
    try:
        print("[INFO] Verifying migration...")
        
        with db_manager.get_session() as session:
            # Test that we can query the new columns
            result = session.execute(text(
                "SELECT customer_page_id, customer_page_created, customer_page_last_accessed FROM users LIMIT 1"
            ))
            
            print("[SUCCESS] Migration verification passed!")
            print("[INFO] Customer page functionality is now available.")
            return True
            
    except Exception as e:
        print(f"[ERROR] Migration verification failed: {e}")
        return False

def main():
    """Main migration function."""
    print("Customer Pages Migration Script")
    print("=" * 40)
    
    # Initialize database connection
    try:
        db_manager.init_db()
        print("[SUCCESS] Database connection established")
    except Exception as e:
        print(f"[ERROR] Failed to connect to database: {e}")
        return False
    
    # Run migration
    if migrate_customer_pages():
        if verify_migration():
            print("\n[COMPLETE] Customer pages migration completed successfully!")
            print("[INFO] Users can now access their personal dashboard pages.")
            return True
    
    print("\n[FAILED] Migration failed. Please check the error messages above.")
    return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)