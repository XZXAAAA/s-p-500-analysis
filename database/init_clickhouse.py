"""
ClickHouse Database Initialization Script
Initialize ClickHouse database and table structure
"""

import sys
from pathlib import Path
import logging

sys.path.insert(0, str(Path(__file__).parent.parent))

from database.clickhouse_manager import ClickHouseManager
from database.env_config import ENABLE_CLICKHOUSE

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def init_clickhouse():
    """Initialize ClickHouse"""
    
    print("\n" + "=" * 60)
    print("ClickHouse 数据库初始化")
    print("=" * 60)
    
    if not ENABLE_CLICKHOUSE:
        logger.warning("[WARNING] ClickHouse has been disabled (ENABLE_CLICKHOUSE=False)")
        print("[OK] ClickHouse initialization skipped")
        return True
    
    try:
        print("\n[1/2] Connecting to ClickHouse...")
        ch = ClickHouseManager()
        print("[OK] ClickHouse connection successful")
        
        print("\n[2/2] Initializing database and tables...")
        ch.init_database()
        print("[OK] ClickHouse database initialization complete")
        
        # Display table information
        print("\nTable Information:")
        print("-" * 60)
        for table_name, size_mb, rows in ch.get_all_tables_info():
            print(f"  [OK] {table_name:35} | {rows:10} rows | {size_mb/1024/1024:.2f} MB")
        print("-" * 60)
        
        ch.close()
        return True
        
    except Exception as e:
        logger.error(f"[ERROR] ClickHouse initialization failed: {str(e)}")
        print(f"[ERROR] ClickHouse initialization failed: {str(e)}")
        print("\nTroubleshooting Tips:")
        print("  1. Make sure ClickHouse service is running")
        print("  2. Available command: docker run -d --name clickhouse-server -p 9000:9000 clickhouse/clickhouse-server:latest")
        return False


if __name__ == "__main__":
    success = init_clickhouse()
    sys.exit(0 if success else 1)

