"""
Environment Variable Configuration Management
"""

import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# ===================================================
# MySQL Configuration
# ===================================================
MYSQL_HOST = os.getenv('MYSQL_HOST', 'localhost')
MYSQL_PORT = int(os.getenv('MYSQL_PORT', 3306))
MYSQL_USER = os.getenv('MYSQL_USER', 'root')
MYSQL_PASSWORD = os.getenv('MYSQL_PASSWORD', '')
MYSQL_DATABASE = os.getenv('MYSQL_DATABASE', 'sentiment_db')
MYSQL_POOL_SIZE = int(os.getenv('MYSQL_POOL_SIZE', 10))
MYSQL_MAX_OVERFLOW = int(os.getenv('MYSQL_MAX_OVERFLOW', 20))

# ===================================================
# DynamoDB Configuration
# ===================================================
AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID', '')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY', '')
DYNAMODB_ENDPOINT = os.getenv('DYNAMODB_ENDPOINT', None)
DYNAMODB_TABLE_PREFIX = os.getenv('DYNAMODB_TABLE_PREFIX', 'sentiment_')

# ===================================================
# ClickHouse Configuration
# ===================================================
CLICKHOUSE_HOST = os.getenv('CLICKHOUSE_HOST', 'localhost')
CLICKHOUSE_PORT = int(os.getenv('CLICKHOUSE_PORT', 9000))
CLICKHOUSE_USER = os.getenv('CLICKHOUSE_USER', 'default')
CLICKHOUSE_PASSWORD = os.getenv('CLICKHOUSE_PASSWORD', '')
CLICKHOUSE_DATABASE = os.getenv('CLICKHOUSE_DATABASE', 'sentiment_analytics')

# ===================================================
# AWS Redshift Configuration
# ===================================================
REDSHIFT_HOST = os.getenv('REDSHIFT_HOST', '')
REDSHIFT_PORT = int(os.getenv('REDSHIFT_PORT', 5439))
REDSHIFT_USER = os.getenv('REDSHIFT_USER', '')
REDSHIFT_PASSWORD = os.getenv('REDSHIFT_PASSWORD', '')
REDSHIFT_DATABASE = os.getenv('REDSHIFT_DATABASE', '')
REDSHIFT_SCHEMA = os.getenv('REDSHIFT_SCHEMA', 'public')

# ===================================================
# Redis Configuration
# ===================================================
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
REDIS_PASSWORD = os.getenv('REDIS_PASSWORD', '')
REDIS_DB = int(os.getenv('REDIS_DB', 0))
REDIS_CACHE_TTL = int(os.getenv('REDIS_CACHE_TTL', 3600))

# ===================================================
# Flask Application Configuration
# ===================================================
FLASK_ENV = os.getenv('FLASK_ENV', 'production')
FLASK_SECRET_KEY = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')
FLASK_DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
FLASK_HOST = os.getenv('FLASK_HOST', '0.0.0.0')
FLASK_PORT = int(os.getenv('FLASK_PORT', 5000))

# ===================================================
# Data Sync Configuration
# ===================================================
SYNC_INTERVAL_SECONDS = int(os.getenv('SYNC_INTERVAL_SECONDS', 300))
ENABLE_REALTIME_SYNC = os.getenv('ENABLE_REALTIME_SYNC', 'True').lower() == 'true'
SYNC_WORKER_THREADS = int(os.getenv('SYNC_WORKER_THREADS', 3))

# ===================================================
# Logging Configuration
# ===================================================
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_FILE = os.getenv('LOG_FILE', 'logs/app.log')
LOG_MAX_BYTES = int(os.getenv('LOG_MAX_BYTES', 10485760))  # 10MB
LOG_BACKUP_COUNT = int(os.getenv('LOG_BACKUP_COUNT', 10))

# ===================================================
# Feature Toggles
# ===================================================
ENABLE_MYSQL = os.getenv('ENABLE_MYSQL', 'True').lower() == 'true'
ENABLE_DYNAMODB = os.getenv('ENABLE_DYNAMODB', 'True').lower() == 'true'
ENABLE_CLICKHOUSE = os.getenv('ENABLE_CLICKHOUSE', 'False').lower() == 'true'
ENABLE_REDSHIFT = os.getenv('ENABLE_REDSHIFT', 'False').lower() == 'true'

# ===================================================
# Scraper Configuration (keep original)
# ===================================================
DEBUG_MODE = os.getenv('DEBUG_MODE', 'False').lower() == 'true'
CACHE_DURATION = int(os.getenv('CACHE_DURATION', 3600))
MAX_WORKERS = int(os.getenv('MAX_WORKERS', 15))
REQUEST_DELAY_MIN = int(os.getenv('REQUEST_DELAY_MIN', 1))
REQUEST_DELAY_MAX = int(os.getenv('REQUEST_DELAY_MAX', 3))
BATCH_SLEEP_MIN = int(os.getenv('BATCH_SLEEP_MIN', 2))
BATCH_SLEEP_MAX = int(os.getenv('BATCH_SLEEP_MAX', 5))
BATCH_SIZE = int(os.getenv('BATCH_SIZE', 50))

# ===================================================
# Configuration Validation Functions
# ===================================================

def validate_mysql_config():
    """Validate MySQL configuration completeness"""
    required_fields = [MYSQL_HOST, MYSQL_USER, MYSQL_DATABASE]
    if not all(required_fields):
        raise ValueError("MySQL configuration incomplete, please check MYSQL_HOST, MYSQL_USER, MYSQL_DATABASE")
    print("✓ MySQL configuration validated")


def validate_dynamodb_config():
    """Validate DynamoDB configuration completeness"""
    if not AWS_ACCESS_KEY_ID or not AWS_SECRET_ACCESS_KEY:
        print("⚠ DynamoDB requires AWS credentials, will disable DynamoDB if not configured")
    print("✓ DynamoDB configuration validated")


def validate_all_configs():
    """Validate all critical configurations"""
    print("=== Starting configuration validation ===")
    if ENABLE_MYSQL:
        validate_mysql_config()
    if ENABLE_DYNAMODB:
        validate_dynamodb_config()
    print("=== Configuration validation complete ===\n")


if __name__ == "__main__":
    print("Environment variable configuration loaded successfully!")
    print(f"Current environment: {FLASK_ENV}")
    print(f"MySQL: {MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}")
    print(f"Redis: {REDIS_HOST}:{REDIS_PORT}")
    validate_all_configs()

