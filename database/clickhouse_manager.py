"""
ClickHouse Database Manager
Handles all interactions with ClickHouse (real-time analytics database)
"""

from clickhouse_driver import Client
import logging
from datetime import datetime, date, timedelta
from database.env_config import (
    CLICKHOUSE_HOST, CLICKHOUSE_PORT, CLICKHOUSE_USER,
    CLICKHOUSE_PASSWORD, CLICKHOUSE_DATABASE
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ===================================================
# ClickHouse Manager Class
# ===================================================

class ClickHouseManager:
    """ClickHouse database manager - for real-time analytics and time-series data"""
    
    def __init__(self):
        """Initialize ClickHouse manager"""
        self.host = CLICKHOUSE_HOST
        self.port = CLICKHOUSE_PORT
        self.user = CLICKHOUSE_USER
        self.password = CLICKHOUSE_PASSWORD
        self.database = CLICKHOUSE_DATABASE
        
        self.client = self._init_client()
        logger.info(f"✓ ClickHouse manager initialized: {self.host}:{self.port}/{self.database}")
    
    def _init_client(self):
        """Initialize ClickHouse client"""
        try:
            # Handle password: check if a real password is provided
            password = None
            if self.password and str(self.password).strip():
                # Only use password if a non-empty one is provided
                password = str(self.password).strip()
            
            client_kwargs = {
                'host': self.host,
                'port': self.port,
                'user': self.user or 'default',
                'settings': {
                    'use_numpy': False,
                    'use_client_time_zone': True
                }
            }
            
            # Only add password parameter if password exists
            # For no-password case, don't pass password parameter, let ClickHouse use no-password auth
            if password:
                client_kwargs['password'] = password
            # If no password, don't add 'password' key to client_kwargs
            # This way clickhouse-driver will use default no-password authentication
            
            # Don't specify database during initialization, as database may not exist yet
            # Will automatically switch database when executing queries
            
            logger.info(f"Connecting to ClickHouse: user={client_kwargs['user']}, host={self.host}:{self.port}, password={'***' if password else '(empty)'}")
            client = Client(**client_kwargs)
            logger.info("ClickHouse client connection successful")
            return client
        except Exception as e:
            logger.error(f"ClickHouse client connection failed: {str(e)}")
            logger.error(f"Connection params: host={self.host}, port={self.port}, user={self.user}, database={self.database}")
            raise
    
    # ===================================================
    # Database and Table Management
    # ===================================================
    
    def init_database(self):
        """Initialize ClickHouse database and tables"""
        try:
            # Create database
            self.client.execute(f"CREATE DATABASE IF NOT EXISTS {self.database}")
            logger.info(f"✓ Database {self.database} created/exists")
            
            # Create tables
            self._create_tables()
            logger.info("✓ ClickHouse database initialization complete")
        except Exception as e:
            logger.error(f"✗ Database initialization failed: {str(e)}")
            raise
    
    def _create_tables(self):
        """Create ClickHouse tables"""
        
        # Sentiment events table - for storing real-time sentiment data
        create_sentiment_events = f"""
        CREATE TABLE IF NOT EXISTS {self.database}.sentiment_events (
            event_date Date,
            event_time DateTime,
            ticker String,
            sector String,
            sentiment_score Float32,
            positive Float32,
            negative Float32,
            neutral Float32,
            news_count UInt32
        ) ENGINE = MergeTree()
        ORDER BY (event_date, ticker)
        PARTITION BY toYYYYMM(event_date);
        """
        
        # Market trends table - for aggregation analysis
        create_market_trends = f"""
        CREATE TABLE IF NOT EXISTS {self.database}.market_trends (
            period_date Date,
            period_hour UInt8,
            sector String,
            avg_sentiment Float32,
            positive_count UInt32,
            negative_count UInt32,
            neutral_count UInt32,
            volatility Float32,
            total_news UInt32
        ) ENGINE = MergeTree()
        ORDER BY (period_date, sector);
        """
        
        # Stock sentiment history table - for time-series analysis
        create_stock_sentiment_history = f"""
        CREATE TABLE IF NOT EXISTS {self.database}.stock_sentiment_history (
            date Date,
            hour UInt8,
            ticker String,
            company_name String,
            sector String,
            sentiment_score Float32,
            positive Float32,
            negative Float32,
            neutral Float32,
            news_count UInt32
        ) ENGINE = MergeTree()
        ORDER BY (date, ticker)
        PARTITION BY toYYYYMM(date);
        """
        
        try:
            self.client.execute(create_sentiment_events)
            logger.info("✓ sentiment_events table created successfully")
            
            self.client.execute(create_market_trends)
            logger.info("✓ market_trends table created successfully")
            
            self.client.execute(create_stock_sentiment_history)
            logger.info("✓ stock_sentiment_history table created successfully")
        except Exception as e:
            logger.error(f"✗ Failed to create tables: {str(e)}")
            raise
    
    # ===================================================
    # Data Write Operations
    # ===================================================
    
    def insert_sentiment_event(self, ticker: str, sector: str, sentiment_data: dict):
        """Insert single sentiment event"""
        try:
            insert_query = f"""
            INSERT INTO {self.database}.sentiment_events 
            (event_date, event_time, ticker, sector, sentiment_score, positive, negative, neutral, news_count)
            VALUES
            """
            
            now = datetime.now()
            query_date = date.today()
            
            # Ensure all values are not None and converted to correct types
            ticker_val = str(ticker) if ticker else 'UNKNOWN'
            sector_val = str(sector) if sector else 'Unknown'
            
            values = (
                query_date,
                now,
                ticker_val,
                sector_val,
                float(sentiment_data.get('sentiment_score', 0)) or 0,
                float(sentiment_data.get('positive', 0)) or 0,
                float(sentiment_data.get('negative', 0)) or 0,
                float(sentiment_data.get('neutral', 0)) or 0,
                int(sentiment_data.get('news_count', 0)) or 0
            )
            
            self.client.execute(insert_query, [values])
            logger.info(f"Sentiment event saved: {ticker}")
        except Exception as e:
            logger.error(f"Failed to save sentiment event: {str(e)}")
            raise
    
    def insert_sentiment_events_batch(self, events_list: list):
        """Batch insert sentiment events"""
        try:
            if not events_list:
                logger.warning("Event list is empty, skipping insert")
                return
            
            insert_query = f"""
            INSERT INTO {self.database}.sentiment_events 
            (event_date, event_time, ticker, sector, sentiment_score, positive, negative, neutral, news_count)
            VALUES
            """
            
            now = datetime.now()
            query_date = date.today()
            
            values = []
            for event in events_list:
                # Ensure all values are not None and converted to correct types
                ticker_val = str(event.get('ticker', 'UNKNOWN')) if event.get('ticker') else 'UNKNOWN'
                sector_val = str(event.get('sector', 'Unknown')) if event.get('sector') else 'Unknown'
                
                row = (
                    query_date,
                    now,
                    ticker_val,
                    sector_val,
                    float(event.get('sentiment_score', 0)) or 0,
                    float(event.get('positive', 0)) or 0,
                    float(event.get('negative', 0)) or 0,
                    float(event.get('neutral', 0)) or 0,
                    int(event.get('news_count', 0)) or 0
                )
                values.append(row)
            
            self.client.execute(insert_query, values)
            logger.info(f"Batch inserted {len(values)} sentiment events")
        except Exception as e:
            logger.error(f"Batch insert failed: {str(e)}")
            raise
    
    # ===================================================
    # Data Query Operations
    # ===================================================
    
    def get_daily_sentiment_summary(self, days: int = 7):
        """Get daily sentiment summary"""
        try:
            # Validate input parameters
            days = max(1, min(int(days), 90))
            
            query = f"""
            SELECT
                event_date,
                sector,
                COUNT(*) as ticker_count,
                AVG(sentiment_score) as avg_sentiment,
                MAX(sentiment_score) as max_sentiment,
                MIN(sentiment_score) as min_sentiment,
                SUM(news_count) as total_news
            FROM {self.database}.sentiment_events
            WHERE event_date >= toDate(now() - INTERVAL {days} DAY)
            GROUP BY event_date, sector
            ORDER BY event_date DESC, avg_sentiment DESC
            """
            
            result = self.client.execute(query)
            logger.info(f"Queried {len(result)} daily summary records")
            return result
        except Exception as e:
            logger.error(f"Query failed: {str(e)}")
            return []
    
    def get_sector_trends(self, sector: str = None, days: int = 7):
        """Get sector trends"""
        try:
            # Validate input parameters
            days = max(1, min(int(days), 90))  # Limit to 1-90 days
            
            if sector:
                # Safely handle sector parameter
                sector = str(sector).strip()
                if not sector:
                    return []
                
                query = f"""
                SELECT
                    event_date,
                    sector,
                    AVG(sentiment_score) as avg_sentiment,
                    COUNT(DISTINCT ticker) as ticker_count,
                    SUM(news_count) as total_news
                FROM {self.database}.sentiment_events
                WHERE sector = %(sector)s AND event_date >= toDate(now() - INTERVAL {days} DAY)
                GROUP BY event_date, sector
                ORDER BY event_date DESC
                """
                result = self.client.execute(query, {'sector': sector})
            else:
                query = f"""
                SELECT
                    event_date,
                    sector,
                    AVG(sentiment_score) as avg_sentiment,
                    COUNT(DISTINCT ticker) as ticker_count,
                    SUM(news_count) as total_news
                FROM {self.database}.sentiment_events
                WHERE event_date >= toDate(now() - INTERVAL {days} DAY)
                GROUP BY event_date, sector
                ORDER BY event_date DESC, avg_sentiment DESC
                """
                result = self.client.execute(query)
            
            logger.info(f"Queried {len(result)} sector trend records")
            return result
        except Exception as e:
            logger.error(f"Query failed: {str(e)}")
            return []
    
    def get_ticker_analysis(self, ticker: str, days: int = 30):
        """Get analysis data for a single stock"""
        try:
            # Validate input parameters
            ticker = str(ticker).strip().upper() if ticker else 'UNKNOWN'
            days = max(1, min(int(days), 90))
            
            query = f"""
            SELECT
                event_date,
                ticker,
                sector,
                sentiment_score,
                positive,
                negative,
                neutral,
                news_count
            FROM {self.database}.sentiment_events
            WHERE ticker = %(ticker)s AND event_date >= toDate(now() - INTERVAL {days} DAY)
            ORDER BY event_date DESC
            """
            
            result = self.client.execute(query, {'ticker': ticker})
            logger.info(f"Queried {len(result)} stock analysis records: {ticker}")
            return result
        except Exception as e:
            logger.error(f"Query failed: {str(e)}")
            return []
    
    def get_top_positive_stocks(self, days: int = 1, limit: int = 10):
        """Get most positive stocks"""
        try:
            # Validate input parameters
            days = max(1, min(int(days), 90))
            limit = max(1, min(int(limit), 500))
            
            query = f"""
            SELECT
                ticker,
                sector,
                AVG(sentiment_score) as avg_sentiment,
                MAX(sentiment_score) as max_sentiment,
                SUM(news_count) as total_news
            FROM {self.database}.sentiment_events
            WHERE event_date >= toDate(now() - INTERVAL {days} DAY)
            GROUP BY ticker, sector
            ORDER BY avg_sentiment DESC
            LIMIT {limit}
            """
            
            result = self.client.execute(query)
            logger.info(f"Queried {len(result)} most positive stocks")
            return result
        except Exception as e:
            logger.error(f"Query failed: {str(e)}")
            return []
    
    def get_top_negative_stocks(self, days: int = 1, limit: int = 10):
        """Get most negative stocks"""
        try:
            # Validate input parameters
            days = max(1, min(int(days), 90))
            limit = max(1, min(int(limit), 500))
            
            query = f"""
            SELECT
                ticker,
                sector,
                AVG(sentiment_score) as avg_sentiment,
                MIN(sentiment_score) as min_sentiment,
                SUM(news_count) as total_news
            FROM {self.database}.sentiment_events
            WHERE event_date >= toDate(now() - INTERVAL {days} DAY)
            GROUP BY ticker, sector
            ORDER BY avg_sentiment ASC
            LIMIT {limit}
            """
            
            result = self.client.execute(query)
            logger.info(f"Queried {len(result)} most negative stocks")
            return result
        except Exception as e:
            logger.error(f"Query failed: {str(e)}")
            return []
    
    def get_sector_statistics(self, days: int = 7):
        """Get sector statistics"""
        try:
            # Validate input parameters
            days = max(1, min(int(days), 90))
            
            query = f"""
            SELECT
                sector,
                COUNT(DISTINCT ticker) as ticker_count,
                AVG(sentiment_score) as avg_sentiment,
                MAX(sentiment_score) as max_sentiment,
                MIN(sentiment_score) as min_sentiment,
                SUM(news_count) as total_news,
                STDDEV(sentiment_score) as volatility
            FROM {self.database}.sentiment_events
            WHERE event_date >= toDate(now() - INTERVAL {days} DAY)
            GROUP BY sector
            ORDER BY avg_sentiment DESC
            """
            
            result = self.client.execute(query)
            logger.info(f"Queried {len(result)} sector statistics")
            return result
        except Exception as e:
            logger.error(f"Query failed: {str(e)}")
            return []
    
    # ===================================================
    # Data Management
    # ===================================================
    
    def get_table_info(self, table_name: str):
        """Get table information"""
        try:
            query = f"""
            SELECT
                database,
                name,
                bytes_on_disk,
                rows
            FROM system.tables
            WHERE database = '{self.database}' AND name = '{table_name}'
            """
            
            result = self.client.execute(query)
            return result
        except Exception as e:
            logger.error(f"✗ Failed to query table info: {str(e)}")
            return []
    
    def get_all_tables_info(self):
        """Get information for all tables"""
        try:
            query = f"""
            SELECT
                name,
                bytes_on_disk,
                rows
            FROM system.tables
            WHERE database = '{self.database}'
            """
            
            result = self.client.execute(query)
            logger.info(f"✓ Queried {len(result)} table info")
            return result
        except Exception as e:
            logger.error(f"✗ Failed to query table info: {str(e)}")
            return []
    
    def close(self):
        """Close connection"""
        try:
            if self.client:
                self.client.disconnect()
                logger.info("✓ ClickHouse connection closed")
        except Exception as e:
            logger.error(f"✗ Failed to close connection: {str(e)}")


# ===================================================
# Test Functions
# ===================================================

if __name__ == "__main__":
    try:
        # Initialize manager
        ch = ClickHouseManager()
        print("✓ ClickHouse manager initialized successfully!")
        
        # Initialize database and tables
        print("\nInitializing database...")
        ch.init_database()
        
        # Get table information
        print("\nTable information:")
        for table_info in ch.get_all_tables_info():
            print(f"  - {table_info[0]}: {table_info[2]} rows, {table_info[1]/1024/1024:.2f} MB")
        
        print("\n✓ ClickHouse setup complete!")
        
    except Exception as e:
        print(f"\n✗ Initialization failed: {str(e)}")
        print("Please ensure ClickHouse service is running")
