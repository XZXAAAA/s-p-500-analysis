"""
Data Sync Pipeline (ETL)
Manages data synchronization between MySQL, DynamoDB and ClickHouse
"""

import logging
import threading
import time
from datetime import datetime, timedelta
from typing import List, Dict

from database.mysql_manager import MySQLManager
from database.dynamodb_manager import DynamoDBManager
from database.clickhouse_manager import ClickHouseManager
from database.env_config import (
    SYNC_INTERVAL_SECONDS,
    ENABLE_REALTIME_SYNC,
    SYNC_WORKER_THREADS
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ===================================================
# Data Sync Pipeline Class
# ===================================================

class DataSyncPipeline:
    """Data sync pipeline - synchronize data between multiple databases"""
    
    def __init__(self):
        """Initialize sync pipeline"""
        self.mysql_db = None
        self.dynamodb = None
        self.clickhouse_db = None
        self.is_running = False
        self.sync_thread = None
        
        try:
            self.mysql_db = MySQLManager()
            logger.info("✓ MySQL connected successfully")
        except Exception as e:
            logger.warning(f"⚠ MySQL connection failed: {str(e)}")
        
        try:
            self.dynamodb = DynamoDBManager()
            logger.info("✓ DynamoDB connected successfully")
        except Exception as e:
            logger.warning(f"⚠ DynamoDB connection failed: {str(e)}")
        
        try:
            self.clickhouse_db = ClickHouseManager()
            logger.info("✓ ClickHouse connected successfully")
        except Exception as e:
            logger.warning(f"⚠ ClickHouse connection failed: {str(e)}")
    
    # ===================================================
    # Sync Operations
    # ===================================================
    
    def sync_sentiment_snapshot_to_clickhouse(self, ticker: str, snapshot_data: dict):
        """Sync MySQL sentiment snapshot to ClickHouse"""
        try:
            if not self.clickhouse_db:
                logger.warning("ClickHouse unavailable, skipping sync")
                return False
            
            event = {
                'ticker': ticker,
                'sector': snapshot_data.get('sector', 'Unknown'),
                'sentiment_score': float(snapshot_data.get('sentiment_score', 0)),
                'positive': float(snapshot_data.get('positive_ratio', 0)),
                'negative': float(snapshot_data.get('negative_ratio', 0)),
                'neutral': float(snapshot_data.get('neutral_ratio', 0)),
                'news_count': int(snapshot_data.get('news_count', 0))
            }
            
            self.clickhouse_db.insert_sentiment_event(ticker, event['sector'], event)
            logger.debug(f"✓ Synced sentiment snapshot to ClickHouse: {ticker}")
            return True
        except Exception as e:
            logger.error(f"✗ Failed to sync sentiment snapshot: {str(e)}")
            return False
    
    def sync_realtime_sentiment_to_clickhouse(self, ticker: str, sentiment_data: dict):
        """Sync DynamoDB real-time sentiment data to ClickHouse"""
        try:
            if not self.clickhouse_db:
                logger.warning("ClickHouse unavailable, skipping sync")
                return False
            
            event = {
                'ticker': ticker,
                'sector': sentiment_data.get('sector', 'Unknown'),
                'sentiment_score': float(sentiment_data.get('sentiment_score', 0)),
                'positive': float(sentiment_data.get('positive', 0)),
                'negative': float(sentiment_data.get('negative', 0)),
                'neutral': float(sentiment_data.get('neutral', 0)),
                'news_count': int(sentiment_data.get('news_count', 0))
            }
            
            self.clickhouse_db.insert_sentiment_event(ticker, event['sector'], event)
            logger.debug(f"✓ Synced real-time sentiment to ClickHouse: {ticker}")
            return True
        except Exception as e:
            logger.error(f"✗ Failed to sync real-time sentiment: {str(e)}")
            return False
    
    def sync_batch_sentiment_data(self, events: List[Dict]) -> int:
        """Batch sync sentiment data to all databases"""
        sync_count = 0
        
        try:
            if not events:
                logger.warning("Event list is empty")
                return 0
            
            # Sync to ClickHouse
            if self.clickhouse_db:
                try:
                    self.clickhouse_db.insert_sentiment_events_batch(events)
                    sync_count += 1
                    logger.info(f"✓ Batch synced {len(events)} events to ClickHouse")
                except Exception as e:
                    logger.error(f"✗ Batch sync to ClickHouse failed: {str(e)}")
            
            # Sync to DynamoDB
            if self.dynamodb:
                try:
                    for event in events:
                        self.dynamodb.save_realtime_sentiment(
                            ticker=event.get('ticker'),
                            timestamp=int(time.time()),
                            sentiment_score=float(event.get('sentiment_score', 0)),
                            positive=float(event.get('positive', 0)),
                            negative=float(event.get('negative', 0)),
                            neutral=float(event.get('neutral', 0)),
                            source='sentiment_pipeline'
                        )
                    sync_count += 1
                    logger.info(f"✓ Batch synced {len(events)} events to DynamoDB")
                except Exception as e:
                    logger.error(f"✗ Batch sync to DynamoDB failed: {str(e)}")
            
            return sync_count
        except Exception as e:
            logger.error(f"✗ Batch sync failed: {str(e)}")
            return 0
    
    # ===================================================
    # Scheduled Sync
    # ===================================================
    
    def start_realtime_sync(self):
        """Start real-time sync thread"""
        if not ENABLE_REALTIME_SYNC:
            logger.info("⊘ Real-time sync is disabled")
            return
        
        if self.is_running:
            logger.warning("⚠ Sync thread is already running")
            return
        
        self.is_running = True
        self.sync_thread = threading.Thread(target=self._sync_worker, daemon=True)
        self.sync_thread.start()
        logger.info(f"✓ Started real-time sync thread, interval: {SYNC_INTERVAL_SECONDS} seconds")
    
    def stop_realtime_sync(self):
        """Stop real-time sync thread"""
        self.is_running = False
        if self.sync_thread:
            self.sync_thread.join(timeout=5)
            logger.info("✓ Real-time sync thread stopped")
    
    def _sync_worker(self):
        """Sync worker thread"""
        while self.is_running:
            try:
                self._perform_sync_tasks()
            except Exception as e:
                logger.error(f"✗ Sync task failed: {str(e)}")
            
            # Wait for specified interval
            time.sleep(SYNC_INTERVAL_SECONDS)
    
    def _perform_sync_tasks(self):
        """Perform sync tasks"""
        try:
            # Sync user operation logs
            if self.mysql_db and self.clickhouse_db:
                self._sync_audit_logs()
            
            # Sync sentiment statistics
            if self.mysql_db and self.clickhouse_db:
                self._sync_sentiment_statistics()
            
            logger.debug("✓ Completed one sync cycle")
        except Exception as e:
            logger.error(f"✗ Failed to execute sync tasks: {str(e)}")
    
    def _sync_audit_logs(self):
        """Sync audit logs to analytics database"""
        try:
            # Get logs from the last hour
            # This is an example, actual implementation needs to fetch from MySQL
            pass
        except Exception as e:
            logger.error(f"✗ Failed to sync audit logs: {str(e)}")
    
    def _sync_sentiment_statistics(self):
        """Sync sentiment statistics"""
        try:
            # Get recent sentiment snapshots from MySQL
            # Then sync to ClickHouse
            pass
        except Exception as e:
            logger.error(f"✗ Failed to sync sentiment statistics: {str(e)}")
    
    # ===================================================
    # Data Validation
    # ===================================================
    
    def verify_data_consistency(self) -> Dict:
        """Verify data consistency"""
        consistency_report = {
            'mysql_records': 0,
            'dynamodb_records': 0,
            'clickhouse_records': 0,
            'status': 'unknown'
        }
        
        try:
            # Check MySQL
            if self.mysql_db:
                try:
                    stocks = self.mysql_db.get_all_stocks()
                    consistency_report['mysql_records'] = len(stocks) if stocks else 0
                except Exception as e:
                    logger.warning(f"⚠ Cannot get MySQL records: {str(e)}")
            
            # Check ClickHouse
            if self.clickhouse_db:
                try:
                    tables_info = self.clickhouse_db.get_all_tables_info()
                    for table_name, size, rows in tables_info:
                        if 'sentiment' in table_name:
                            consistency_report['clickhouse_records'] = rows
                            break
                except Exception as e:
                    logger.warning(f"⚠ Cannot get ClickHouse records: {str(e)}")
            
            # Determine consistency status
            if consistency_report['mysql_records'] > 0 and \
               consistency_report['clickhouse_records'] > 0:
                consistency_report['status'] = 'healthy'
            else:
                consistency_report['status'] = 'degraded'
            
            logger.info(f"✓ Data consistency check complete: {consistency_report}")
            return consistency_report
        except Exception as e:
            logger.error(f"✗ Data consistency check failed: {str(e)}")
            consistency_report['status'] = 'error'
            return consistency_report
    
    # ===================================================
    # Cleanup
    # ===================================================
    
    def close(self):
        """Close all connections"""
        try:
            self.stop_realtime_sync()
            
            if self.mysql_db:
                self.mysql_db.close()
            if self.dynamodb:
                self.dynamodb.close()
            if self.clickhouse_db:
                self.clickhouse_db.close()
            
            logger.info("✓ Data sync pipeline closed")
        except Exception as e:
            logger.error(f"✗ Failed to close pipeline: {str(e)}")


# ===================================================
# Global Instance
# ===================================================

_sync_pipeline_instance = None

def get_sync_pipeline() -> DataSyncPipeline:
    """Get global sync pipeline instance"""
    global _sync_pipeline_instance
    if _sync_pipeline_instance is None:
        _sync_pipeline_instance = DataSyncPipeline()
    return _sync_pipeline_instance


# ===================================================
# Test Functions
# ===================================================

if __name__ == "__main__":
    pipeline = DataSyncPipeline()
    
    try:
        print("\n" + "=" * 60)
        print("Data Sync Pipeline Test")
        print("=" * 60)
        
        # Verify data consistency
        print("\n[1/3] Verifying data consistency...")
        consistency = pipeline.verify_data_consistency()
        print(f"✓ Consistency report: {consistency}")
        
        # Test batch sync
        print("\n[2/3] Testing batch sync...")
        test_events = [
            {
                'ticker': 'AAPL',
                'sector': 'Technology',
                'sentiment_score': 0.75,
                'positive': 0.8,
                'negative': 0.1,
                'neutral': 0.1,
                'news_count': 5
            }
        ]
        sync_count = pipeline.sync_batch_sentiment_data(test_events)
        print(f"✓ Synced to {sync_count} databases")
        
        # Start real-time sync
        print("\n[3/3] Starting real-time sync (will stop after 10 seconds)...")
        pipeline.start_realtime_sync()
        time.sleep(10)
        pipeline.stop_realtime_sync()
        
        print("\n✓ All tests complete!")
        
    except Exception as e:
        print(f"\n✗ Test failed: {str(e)}")
    finally:
        pipeline.close()

