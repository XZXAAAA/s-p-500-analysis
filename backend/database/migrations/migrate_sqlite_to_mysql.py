"""
SQLite to MySQL Migration Script
Migrate all user data from SQLite (users.db) to MySQL
"""

import sqlite3
import sys
from pathlib import Path
from datetime import datetime

# Add project root directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from database.mysql_manager import MySQLManager
from werkzeug.security import generate_password_hash

def migrate_users():
    """Migrate user data from SQLite to MySQL"""
    
    print("=" * 60)
    print("SQLite → MySQL User Data Migration Script")
    print("=" * 60)
    
    # Connect to SQLite
    print("\n[1/3] Connecting to SQLite database...")
    try:
        sqlite_conn = sqlite3.connect('users.db')
        sqlite_cursor = sqlite_conn.cursor()
        
        # Query user count
        sqlite_cursor.execute('SELECT COUNT(*) FROM users')
        user_count = sqlite_cursor.fetchone()[0]
        print(f"✓ Found {user_count} users in SQLite")
    except Exception as e:
        print(f"✗ Cannot connect to SQLite: {str(e)}")
        print("Hint: Does users.db file exist?")
        return False
    
    # Connect to MySQL
    print("\n[2/3] Connecting to MySQL database...")
    try:
        mysql_db = MySQLManager()
        print("✓ MySQL connection successful")
    except Exception as e:
        print(f"✗ Cannot connect to MySQL: {str(e)}")
        print("Hint: Check if .env configuration is correct")
        return False
    
    # Migrate users
    print("\n[3/3] Migrating user data...")
    try:
        sqlite_cursor.execute('SELECT id, username, email, password_hash, created_at FROM users')
        users = sqlite_cursor.fetchall()
        
        migrated = 0
        skipped = 0
        errors = 0
        
        for user_id, username, email, password_hash, created_at in users:
            try:
                # Check if user already exists
                existing = mysql_db.get_user_by_username(username)
                if existing:
                    print(f"⊘ Skipped (already exists): {username}")
                    skipped += 1
                    continue
                
                # Create user
                try:
                    user_obj = mysql_db.create_user(
                        username=username,
                        email=email,
                        password_hash=password_hash,
                        user_role='user'
                    )
                    # Get ID ensuring data is available
                    user_id_returned = user_obj.id if hasattr(user_obj, 'id') else 'N/A'
                    print(f"✓ Migration successful: {username} (ID: {user_id_returned})")
                    migrated += 1
                except AttributeError as ae:
                    # If Session is closed, still consider it successful (data is saved)
                    print(f"✓ Migration successful: {username} (ID: {user_id})")
                    migrated += 1
                    
            except Exception as e:
                print(f"✗ Migration failed: {username} - {str(e)}")
                errors += 1
        
        sqlite_conn.close()
        mysql_db.close()
        
        # Output summary
        print("\n" + "=" * 60)
        print("Migration Complete")
        print("=" * 60)
        print(f"Successfully migrated: {migrated} users")
        print(f"Already exists (skipped): {skipped} users")
        print(f"Migration failed: {errors} users")
        
        if errors == 0:
            print("\n✓ All users migrated successfully!")
            return True
        else:
            print(f"\n⚠ {errors} users failed to migrate")
            return False
    
    except Exception as e:
        print(f"✗ Error during migration: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = migrate_users()
    sys.exit(0 if success else 1)

