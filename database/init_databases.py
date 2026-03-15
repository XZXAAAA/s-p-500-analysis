"""
Database Initialization Script
Initialize all databases (MySQL, DynamoDB, etc.)
"""

import sys
import os
import logging
from pathlib import Path

# Add project root directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.mysql_manager import MySQLManager
from database.dynamodb_manager import DynamoDBManager
from database.env_config import ENABLE_MYSQL, ENABLE_DYNAMODB, validate_all_configs

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ===================================================
# Initialization Functions
# ===================================================

def init_mysql():
    """Initialize MySQL database"""
    logger.info("=" * 60)
    logger.info("Starting MySQL database initialization")
    logger.info("=" * 60)
    
    try:
        db_manager = MySQLManager()
        
        # Create all tables
        logger.info("Creating database tables...")
        db_manager.create_tables()
        
        logger.info("✓ MySQL database initialization complete!")
        db_manager.close()
        return True
    except Exception as e:
        logger.error(f"✗ MySQL initialization failed: {str(e)}")
        return False


def init_dynamodb():
    """Initialize DynamoDB database"""
    logger.info("=" * 60)
    logger.info("Starting DynamoDB database initialization")
    logger.info("=" * 60)
    
    try:
        db_manager = DynamoDBManager()
        
        # Create all tables
        logger.info("Creating DynamoDB tables...")
        db_manager.init_tables()
        
        logger.info("✓ DynamoDB database initialization complete!")
        return True
    except Exception as e:
        logger.error(f"✗ DynamoDB initialization failed: {str(e)}")
        logger.info("Tip: If in local development, ensure DynamoDB Local is running")
        return False


def main():
    """Main initialization function"""
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 58 + "║")
    print("║" + "   Hybrid Database Architecture - Initialization Script".center(58) + "║")
    print("║" + " " * 58 + "║")
    print("╚" + "=" * 58 + "╝")
    print()
    
    # Validate configuration
    logger.info("Validating environment variable configuration...")
    try:
        validate_all_configs()
    except Exception as e:
        logger.warning(f"Configuration validation warning: {str(e)}")
    
    print()
    
    results = {
        'MySQL': False,
        'DynamoDB': False
    }
    
    # Initialize MySQL
    if ENABLE_MYSQL:
        results['MySQL'] = init_mysql()
    else:
        logger.warning("MySQL disabled (ENABLE_MYSQL=False)")
    
    print()
    
    # Initialize DynamoDB
    if ENABLE_DYNAMODB:
        results['DynamoDB'] = init_dynamodb()
    else:
        logger.warning("DynamoDB disabled (ENABLE_DYNAMODB=False)")
    
    # Output summary
    print()
    print("╔" + "=" * 58 + "╗")
    print("║" + " Initialization Summary ".center(58) + "║")
    print("╠" + "=" * 58 + "╣")
    
    for db_name, result in results.items():
        status = "✓ Success" if result else "✗ Failed/Disabled"
        print(f"║ {db_name:15} : {status:40} ║")
    
    print("╚" + "=" * 58 + "╝")
    print()
    
    # Return status
    if all(results.values()):
        logger.info("✓ All databases initialized successfully!")
        return 0
    else:
        logger.warning("⚠ Some databases encountered issues, please check logs")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)

