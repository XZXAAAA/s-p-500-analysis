"""
DynamoDB Database Manager
Handles all interactions with DynamoDB (high-concurrency cache layer)
"""

import boto3
import json
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from botocore.exceptions import ClientError
from database.env_config import (
    AWS_REGION, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY,
    DYNAMODB_ENDPOINT, DYNAMODB_TABLE_PREFIX
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ===================================================
# DynamoDB Manager Class
# ===================================================

class DynamoDBManager:
    """DynamoDB database manager - for high-concurrency cache and real-time data"""
    
    def __init__(self):
        """Initialize DynamoDB manager"""
        self.dynamodb = self._init_dynamodb()
        self.table_prefix = DYNAMODB_TABLE_PREFIX
        
        logger.info(f"DynamoDB manager initialized: region={AWS_REGION}")
    
    def _init_dynamodb(self):
        """Initialize DynamoDB client"""
        try:
            if DYNAMODB_ENDPOINT:
                # Local development environment
                logger.warning(f"Using local DynamoDB: {DYNAMODB_ENDPOINT}")
                dynamodb = boto3.resource(
                    'dynamodb',
                    region_name=AWS_REGION,
                    endpoint_url=DYNAMODB_ENDPOINT,
                    aws_access_key_id='local',
                    aws_secret_access_key='local'
                )
            else:
                # AWS production environment
                dynamodb = boto3.resource(
                    'dynamodb',
                    region_name=AWS_REGION,
                    aws_access_key_id=AWS_ACCESS_KEY_ID,
                    aws_secret_access_key=AWS_SECRET_ACCESS_KEY
                )
            logger.info("DynamoDB client created successfully")
            return dynamodb
        except Exception as e:
            logger.error(f"Failed to create DynamoDB client: {str(e)}")
            raise
    
    # ===================================================
    # Table Management Operations
    # ===================================================
    
    def create_table(self, table_name: str, schema: dict):
        """Create DynamoDB table"""
        try:
            table_name = f"{self.table_prefix}{table_name}"
            logger.info(f"Creating table: {table_name}")
            
            table = self.dynamodb.create_table(
                TableName=table_name,
                **schema
            )
            
            table.wait_until_exists()
            logger.info(f"Table created successfully: {table_name}")
            return table
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceInUseException':
                logger.info(f"Table already exists: {table_name}")
                return self.dynamodb.Table(table_name)
            else:
                logger.error(f"Failed to create table: {str(e)}")
                raise
    
    def get_all_tables(self):
        """Get all DynamoDB table names"""
        try:
            client = boto3.client('dynamodb', region_name=AWS_REGION)
            response = client.list_tables()
            return response.get('TableNames', [])
        except Exception as e:
            logger.error(f"Failed to get table list: {str(e)}")
            return []
    
    def close(self):
        """Close connection"""
        try:
            if self.dynamodb:
                # DynamoDB resource doesn't need explicit closing
                logger.info("DynamoDB connection closed")
        except Exception as e:
            logger.error(f"Failed to close connection: {str(e)}")

    def get_table(self, table_name: str):
        """Get table object"""
        return self.dynamodb.Table(f"{self.table_prefix}{table_name}")
    
    def delete_table(self, table_name: str):
        """Delete table"""
        try:
            table_name = f"{self.table_prefix}{table_name}"
            self.dynamodb.Table(table_name).delete()
            logger.info(f"Table deleted successfully: {table_name}")
        except Exception as e:
            logger.error(f"Failed to delete table: {str(e)}")
            raise
    
    # ===================================================
    # User Session Management
    # ===================================================
    
    def create_user_session(self, user_id: str, session_id: str, token: str, 
                           expires_at: int, device_info: dict = None):
        """Create user session"""
        try:
            table = self.get_table('user_sessions')
            
            item = {
                'user_id': user_id,
                'session_id': session_id,
                'token': token,
                'expires_at': expires_at,
                'created_at': int(datetime.utcnow().timestamp()),
                'device_info': device_info or {}
            }
            
            table.put_item(Item=item)
            logger.info(f"User session created successfully: {user_id}")
            return item
        except Exception as e:
            logger.error(f"Failed to create user session: {str(e)}")
            raise
    
    def get_user_session(self, user_id: str, session_id: str) -> dict:
        """Get user session"""
        try:
            table = self.get_table('user_sessions')
            response = table.get_item(
                Key={
                    'user_id': user_id,
                    'session_id': session_id
                }
            )
            return response.get('Item', None)
        except Exception as e:
            logger.error(f"Failed to get user session: {str(e)}")
            raise
    
    def delete_user_session(self, user_id: str, session_id: str):
        """Delete user session"""
        try:
            table = self.get_table('user_sessions')
            table.delete_item(
                Key={
                    'user_id': user_id,
                    'session_id': session_id
                }
            )
            logger.info(f"User session deleted successfully: {user_id}")
        except Exception as e:
            logger.error(f"Failed to delete user session: {str(e)}")
            raise
    
    # ===================================================
    # Real-Time Sentiment Data Management
    # ===================================================
    
    def save_realtime_sentiment(self, ticker: str, timestamp: int,
                               sentiment_score: float, positive: float,
                               negative: float, neutral: float,
                               news_headline: str = None, source: str = 'finviz'):
        """Save real-time sentiment data (with TTL auto-deletion)"""
        try:
            table = self.get_table('realtime_sentiment')
            
            # Set TTL to 24 hours later
            ttl = timestamp + 86400
            
            # Convert float to Decimal to comply with DynamoDB requirements
            item = {
                'ticker': ticker,
                'timestamp': timestamp,
                'sentiment_score': Decimal(str(sentiment_score)),
                'positive': Decimal(str(positive)),
                'negative': Decimal(str(negative)),
                'neutral': Decimal(str(neutral)),
                'news_headline': news_headline or '',
                'source': source,
                'ttl': ttl
            }
            
            table.put_item(Item=item)
            return item
        except Exception as e:
            logger.error(f"Failed to save real-time sentiment data: {str(e)}")
            raise
    
    def get_realtime_sentiment(self, ticker: str, timestamp: int = None) -> dict:
        """Get real-time sentiment data"""
        try:
            table = self.get_table('realtime_sentiment')
            
            if timestamp:
                response = table.get_item(
                    Key={
                        'ticker': ticker,
                        'timestamp': timestamp
                    }
                )
                return response.get('Item', None)
            else:
                # Get latest sentiment data
                response = table.query(
                    KeyConditionExpression='ticker = :ticker',
                    ExpressionAttributeValues={
                        ':ticker': ticker
                    },
                    ScanIndexForward=False,  # Descending order, get latest
                    Limit=1
                )
                items = response.get('Items', [])
                return items[0] if items else None
        except Exception as e:
            logger.error(f"Failed to get real-time sentiment data: {str(e)}")
            raise
    
    def get_sentiment_range(self, ticker: str, start_timestamp: int, 
                           end_timestamp: int) -> list:
        """Get sentiment data within time range"""
        try:
            table = self.get_table('realtime_sentiment')
            response = table.query(
                KeyConditionExpression='ticker = :ticker AND #ts BETWEEN :start AND :end',
                ExpressionAttributeNames={
                    '#ts': 'timestamp'
                },
                ExpressionAttributeValues={
                    ':ticker': ticker,
                    ':start': start_timestamp,
                    ':end': end_timestamp
                }
            )
            return response.get('Items', [])
        except Exception as e:
            logger.error(f"Failed to get sentiment data range: {str(e)}")
            raise
    
    # ===================================================
    # User Preferences Management
    # ===================================================
    
    def save_user_preferences(self, user_id: str, watchlist: list = None,
                            alerts: dict = None, theme: str = 'light',
                            language: str = 'en'):
        """Save user preferences"""
        try:
            table = self.get_table('user_preferences')
            
            item = {
                'user_id': user_id,
                'watchlist': watchlist or [],
                'alerts': alerts or {},
                'theme': theme,
                'language': language,
                'updated_at': int(datetime.utcnow().timestamp())
            }
            
            table.put_item(Item=item)
            logger.info(f"User preferences saved successfully: {user_id}")
            return item
        except Exception as e:
            logger.error(f"Failed to save user preferences: {str(e)}")
            raise
    
    def get_user_preferences(self, user_id: str) -> dict:
        """Get user preferences"""
        try:
            table = self.get_table('user_preferences')
            response = table.get_item(
                Key={'user_id': user_id}
            )
            return response.get('Item', None)
        except Exception as e:
            logger.error(f"Failed to get user preferences: {str(e)}")
            raise
    
    def update_user_watchlist(self, user_id: str, watchlist: list):
        """Update user watchlist"""
        try:
            table = self.get_table('user_preferences')
            
            table.update_item(
                Key={'user_id': user_id},
                UpdateExpression='SET watchlist = :wl, updated_at = :ua',
                ExpressionAttributeValues={
                    ':wl': watchlist,
                    ':ua': int(datetime.utcnow().timestamp())
                }
            )
            logger.info(f"User watchlist updated successfully: {user_id}")
        except Exception as e:
            logger.error(f"Failed to update user watchlist: {str(e)}")
            raise
    
    # ===================================================
    # Initialize Table Structure
    # ===================================================
    
    def _enable_ttl(self, table_name: str, attribute_name: str):
        """Enable TTL (Time To Live) for table"""
        try:
            table_name = f"{self.table_prefix}{table_name}"
            client = self.dynamodb.meta.client
            client.update_time_to_live(
                TableName=table_name,
                TimeToLiveSpecification={
                    'Enabled': True,
                    'AttributeName': attribute_name
                }
            )
            logger.info(f"✓ Enabled TTL for table {table_name} (attribute: {attribute_name})")
        except client.exceptions.ResourceNotFoundException:
            logger.warning(f"Table {table_name} does not exist, skipping TTL setup")
        except Exception as e:
            logger.warning(f"Error setting TTL: {str(e)}")
    
    def init_tables(self):
        """Initialize all DynamoDB tables"""
        
        # UserSessions table (don't set TTL during creation)
        user_sessions_schema = {
            'KeySchema': [
                {'AttributeName': 'user_id', 'KeyType': 'HASH'},
                {'AttributeName': 'session_id', 'KeyType': 'RANGE'}
            ],
            'AttributeDefinitions': [
                {'AttributeName': 'user_id', 'AttributeType': 'S'},
                {'AttributeName': 'session_id', 'AttributeType': 'S'}
            ],
            'BillingMode': 'PAY_PER_REQUEST'
        }
        self.create_table('user_sessions', user_sessions_schema)
        # Enable TTL separately after creation
        self._enable_ttl('user_sessions', 'expires_at')
        
        # RealtimeSentiment table (don't set TTL during creation)
        realtime_sentiment_schema = {
            'KeySchema': [
                {'AttributeName': 'ticker', 'KeyType': 'HASH'},
                {'AttributeName': 'timestamp', 'KeyType': 'RANGE'}
            ],
            'AttributeDefinitions': [
                {'AttributeName': 'ticker', 'AttributeType': 'S'},
                {'AttributeName': 'timestamp', 'AttributeType': 'N'}
            ],
            'BillingMode': 'PAY_PER_REQUEST'
        }
        self.create_table('realtime_sentiment', realtime_sentiment_schema)
        # Enable TTL separately after creation
        self._enable_ttl('realtime_sentiment', 'ttl')
        
        # UserPreferences table
        user_preferences_schema = {
            'KeySchema': [
                {'AttributeName': 'user_id', 'KeyType': 'HASH'}
            ],
            'AttributeDefinitions': [
                {'AttributeName': 'user_id', 'AttributeType': 'S'}
            ],
            'BillingMode': 'PAY_PER_REQUEST'
        }
        self.create_table('user_preferences', user_preferences_schema)
        
        logger.info("All DynamoDB tables initialized successfully!")


# ===================================================
# Test Functions
# ===================================================

if __name__ == "__main__":
    try:
        db_manager = DynamoDBManager()
        print("DynamoDB manager initialized successfully!")
        
        # Initialize tables
        print("\nInitializing tables...")
        db_manager.init_tables()
        
        print("\n✓ DynamoDB setup complete!")
    except Exception as e:
        print(f"\n✗ Initialization failed: {str(e)}")
        print("Please ensure DynamoDB service is running or AWS credentials are configured")

