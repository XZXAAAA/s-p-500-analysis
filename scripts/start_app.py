"""
Application startup script
Initialize database and start Flask application
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app import app, init_db, mysql_db, dynamodb
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """Start application"""
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 58 + "║")
    print("║" + "   S&P 500 Stock Sentiment Analysis".center(58) + "║")
    print("║" + "   Starting Application".center(58) + "║")
    print("║" + " " * 58 + "║")
    print("╚" + "=" * 58 + "╝")
    print()
    
    # Initialize database
    print("[1/3] Initializing database...")
    try:
        init_db()
        print("✓ Database initialization complete")
    except Exception as e:
        logger.error(f"Database initialization failed: {str(e)}")
        print(f"✗ Database initialization failed: {str(e)}")
        return False
    
    # Verify database connections
    print("\n[2/3] Verifying database connections...")
    try:
        if mysql_db:
            stocks = mysql_db.get_all_stocks()
            print(f"✓ MySQL connected successfully ({len(stocks)} stocks)")
        else:
            print("⚠ MySQL not connected")
        
        if dynamodb:
            print("✓ DynamoDB connected successfully")
        else:
            print("⚠ DynamoDB not connected")
    except Exception as e:
        logger.error(f"Database verification failed: {str(e)}")
        print(f"✗ Database verification failed: {str(e)}")
        return False
    
    # Start Flask application
    print("\n[3/3] Starting Flask application...")
    print()
    print("=" * 60)
    print("Application started!")
    print("=" * 60)
    print("\nAccess URLs:")
    print("  - Local: http://127.0.0.1:5000")
    print("  - Network: http://0.0.0.0:5000")
    print("\nPress Ctrl+C to stop the application\n")
    
    try:
        app.run(debug=True, host='0.0.0.0', port=5000, use_reloader=True)
    except KeyboardInterrupt:
        print("\n\nApplication stopped")
        return True
    except Exception as e:
        logger.error(f"Application startup failed: {str(e)}")
        print(f"✗ Application startup failed: {str(e)}")
        return False


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)

