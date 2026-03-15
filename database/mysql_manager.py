"""
MySQL Database Manager
Handles all interactions with MySQL database
"""

from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, Boolean, JSON, Enum, Date, DECIMAL
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from datetime import datetime, date
import logging
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

Base = declarative_base()

# ===================================================
# SQLAlchemy ORM Model Definitions
# ===================================================

class User(Base):
    """User table model"""
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    username = Column(String(255), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    user_role = Column(Enum('admin', 'user'), default='user')
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    last_login = Column(DateTime, nullable=True)


class Stock(Base):
    """Stock table model"""
    __tablename__ = 'stocks'
    
    id = Column(Integer, primary_key=True)
    ticker = Column(String(10), unique=True, nullable=False)
    company_name = Column(String(255))
    sector = Column(String(100))
    industry = Column(String(100))
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SentimentSnapshot(Base):
    """Sentiment score snapshot table model"""
    __tablename__ = 'sentiment_snapshots'
    
    id = Column(Integer, primary_key=True)
    ticker = Column(String(10), nullable=False)
    snapshot_date = Column(Date, nullable=False)
    sentiment_score = Column(DECIMAL(5, 4))
    positive_ratio = Column(DECIMAL(5, 4))
    negative_ratio = Column(DECIMAL(5, 4))
    neutral_ratio = Column(DECIMAL(5, 4))
    news_count = Column(Integer, default=0)
    source = Column(String(100), default='finviz')
    created_at = Column(DateTime, default=datetime.utcnow)


class NewsRecord(Base):
    """News record table model"""
    __tablename__ = 'news_records'
    
    id = Column(Integer, primary_key=True)
    ticker = Column(String(10), nullable=False)
    headline = Column(String(500), nullable=False)
    news_date = Column(Date)
    news_time = Column(String(20))
    sentiment_score = Column(DECIMAL(5, 4))
    positive = Column(DECIMAL(5, 4))
    negative = Column(DECIMAL(5, 4))
    neutral = Column(DECIMAL(5, 4))
    source = Column(String(100), default='finviz')
    url = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow)


class UserPreferences(Base):
    """User preferences table model"""
    __tablename__ = 'user_preferences'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, unique=True, nullable=False)
    watchlist = Column(JSON)
    alert_threshold_positive = Column(DECIMAL(5, 4), default=0.50)
    alert_threshold_negative = Column(DECIMAL(5, 4), default=-0.50)
    notification_enabled = Column(Boolean, default=True)
    dashboard_layout = Column(String(50), default='default')
    theme = Column(String(20), default='light')
    language = Column(String(10), default='en')
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class UserAlert(Base):
    """User alert table model"""
    __tablename__ = 'user_alerts'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    ticker = Column(String(10), nullable=False)
    alert_type = Column(Enum('sentiment_spike', 'threshold_reached', 'sector_trend'))
    alert_condition = Column(String(255))
    is_active = Column(Boolean, default=True)
    triggered_count = Column(Integer, default=0)
    last_triggered = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AuditLog(Base):
    """Audit log table model"""
    __tablename__ = 'audit_logs'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=True)
    action = Column(String(100), nullable=False)
    resource_type = Column(String(100))
    resource_id = Column(String(100))
    old_value = Column(JSON)
    new_value = Column(JSON)
    ip_address = Column(String(45))
    status = Column(String(20), default='success')
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class SyncStatus(Base):
    """Data sync status table model"""
    __tablename__ = 'sync_status'
    
    id = Column(Integer, primary_key=True)
    source_table = Column(String(100), nullable=False)
    target_db = Column(String(50), nullable=False)
    last_sync_time = Column(DateTime)
    last_record_id = Column(Integer)
    status = Column(String(20), default='success')
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ===================================================
# MySQL Database Manager Class
# ===================================================

class MySQLManager:
    """MySQL database manager"""
    
    def __init__(self, host=None, port=None, user=None, password=None, database=None):
        """
        Initialize MySQL manager
        
        Args:
            host: MySQL server address (default from environment variable)
            port: MySQL port (default from environment variable)
            user: MySQL username (default from environment variable)
            password: MySQL password (default from environment variable)
            database: Database name (default from environment variable)
        """
        self.host = host or os.getenv('MYSQL_HOST', 'localhost')
        self.port = port or os.getenv('MYSQL_PORT', 3306)
        self.user = user or os.getenv('MYSQL_USER', 'root')
        self.password = password or os.getenv('MYSQL_PASSWORD', '')
        self.database = database or os.getenv('MYSQL_DATABASE', 'sentiment_db')
        
        # Create database engine
        self.engine = self._create_engine()
        # Create session factory
        self.SessionLocal = sessionmaker(bind=self.engine, expire_on_commit=False)
        
        logger.info(f"MySQL manager initialized: {self.user}@{self.host}:{self.port}/{self.database}")
    
    def _create_engine(self):
        """Create SQLAlchemy engine"""
        try:
            # MySQL connection string
            if self.password:
                database_url = f"mysql+pymysql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}?charset=utf8mb4"
            else:
                database_url = f"mysql+pymysql://{self.user}@{self.host}:{self.port}/{self.database}?charset=utf8mb4"
            
            engine = create_engine(
                database_url,
                echo=False,
                pool_size=10,
                max_overflow=20,
                pool_pre_ping=True,  # Test if connection is valid
                connect_args={'connect_timeout': 10}
            )
            logger.info("Database engine created successfully")
            return engine
        except Exception as e:
            logger.error(f"Failed to create database engine: {str(e)}")
            raise
    
    def create_tables(self):
        """Create all tables"""
        try:
            Base.metadata.create_all(self.engine)
            logger.info("Database tables created successfully")
        except Exception as e:
            logger.error(f"Failed to create tables: {str(e)}")
            raise
    
    def get_session(self) -> Session:
        """Get database session"""
        return self.SessionLocal()
    
    def close(self):
        """Close database connection"""
        self.engine.dispose()
        logger.info("Database connection closed")
    
    # ===================================================
    # User Related Operations
    # ===================================================
    
    def create_user(self, username: str, email: str, password_hash: str, user_role: str = 'user') -> User:
        """Create new user"""
        session = self.get_session()
        try:
            user = User(
                username=username,
                email=email,
                password_hash=password_hash,
                user_role=user_role
            )
            session.add(user)
            session.commit()
            logger.info(f"User created successfully: {username}")
            return user
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to create user: {str(e)}")
            raise
        finally:
            session.close()
    
    def get_user_by_username(self, username: str) -> User:
        """Get user by username"""
        session = self.get_session()
        try:
            user = session.query(User).filter(User.username == username).first()
            return user
        finally:
            session.close()
    
    def get_user_by_id(self, user_id: int) -> User:
        """Get user by ID"""
        session = self.get_session()
        try:
            user = session.query(User).filter(User.id == user_id).first()
            return user
        finally:
            session.close()
    
    # ===================================================
    # Stock Data Related Operations
    # ===================================================
    
    def add_stock(self, ticker: str, company_name: str, sector: str, industry: str) -> Stock:
        """Add stock"""
        session = self.get_session()
        try:
            stock = Stock(
                ticker=ticker,
                company_name=company_name,
                sector=sector,
                industry=industry
            )
            session.add(stock)
            session.commit()
            logger.info(f"Stock added successfully: {ticker}")
            return stock
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to add stock: {str(e)}")
            raise
        finally:
            session.close()
    
    def get_stock_by_ticker(self, ticker: str) -> Stock:
        """Get stock by ticker"""
        session = self.get_session()
        try:
            stock = session.query(Stock).filter(Stock.ticker == ticker).first()
            return stock
        finally:
            session.close()
    
    def get_all_stocks(self) -> list:
        """Get all stocks"""
        session = self.get_session()
        try:
            stocks = session.query(Stock).all()
            return stocks
        finally:
            session.close()
    
    # ===================================================
    # Sentiment Data Related Operations
    # ===================================================
    
    def save_sentiment_snapshot(self, ticker: str, snapshot_date: date, 
                               sentiment_score: float, positive_ratio: float,
                               negative_ratio: float, neutral_ratio: float,
                               news_count: int) -> SentimentSnapshot:
        """Save sentiment score snapshot"""
        session = self.get_session()
        try:
            snapshot = SentimentSnapshot(
                ticker=ticker,
                snapshot_date=snapshot_date,
                sentiment_score=sentiment_score,
                positive_ratio=positive_ratio,
                negative_ratio=negative_ratio,
                neutral_ratio=neutral_ratio,
                news_count=news_count
            )
            session.add(snapshot)
            session.commit()
            logger.info(f"Sentiment snapshot saved successfully: {ticker} - {snapshot_date}")
            return snapshot
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to save sentiment snapshot: {str(e)}")
            raise
        finally:
            session.close()
    
    def get_sentiment_history(self, ticker: str, days: int = 30) -> list:
        """Get historical sentiment data for stock"""
        session = self.get_session()
        try:
            from datetime import timedelta
            start_date = date.today() - timedelta(days=days)
            snapshots = session.query(SentimentSnapshot).filter(
                SentimentSnapshot.ticker == ticker,
                SentimentSnapshot.snapshot_date >= start_date
            ).order_by(SentimentSnapshot.snapshot_date).all()
            return snapshots
        finally:
            session.close()
    
    # ===================================================
    # News Record Related Operations
    # ===================================================
    
    def save_news_record(self, ticker: str, headline: str, 
                        sentiment_score: float, positive: float,
                        negative: float, neutral: float,
                        news_date: date = None, news_time: str = None) -> NewsRecord:
        """Save news record"""
        session = self.get_session()
        try:
            news = NewsRecord(
                ticker=ticker,
                headline=headline,
                sentiment_score=sentiment_score,
                positive=positive,
                negative=negative,
                neutral=neutral,
                news_date=news_date or date.today(),
                news_time=news_time
            )
            session.add(news)
            session.commit()
            logger.info(f"News record saved successfully: {ticker}")
            return news
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to save news record: {str(e)}")
            raise
        finally:
            session.close()
    
    # ===================================================
    # User Preferences Related Operations
    # ===================================================
    
    def create_user_preferences(self, user_id: int) -> UserPreferences:
        """Create user preferences record"""
        session = self.get_session()
        try:
            prefs = UserPreferences(user_id=user_id)
            session.add(prefs)
            session.commit()
            logger.info(f"User preferences created successfully: user_id={user_id}")
            return prefs
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to create user preferences: {str(e)}")
            raise
        finally:
            session.close()
    
    def update_user_watchlist(self, user_id: int, watchlist: list) -> UserPreferences:
        """Update user watchlist"""
        session = self.get_session()
        try:
            prefs = session.query(UserPreferences).filter(UserPreferences.user_id == user_id).first()
            if prefs:
                prefs.watchlist = watchlist
                session.commit()
                logger.info(f"User watchlist updated successfully: user_id={user_id}")
                return prefs
            else:
                raise ValueError(f"User preferences not found: user_id={user_id}")
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to update user watchlist: {str(e)}")
            raise
        finally:
            session.close()
    
    # ===================================================
    # Audit Log Related Operations
    # ===================================================
    
    def log_action(self, user_id: int, action: str, resource_type: str,
                  resource_id: str, old_value=None, new_value=None,
                  ip_address: str = None, status: str = 'success',
                  error_message: str = None) -> AuditLog:
        """Log audit entry"""
        session = self.get_session()
        try:
            log = AuditLog(
                user_id=user_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                old_value=old_value,
                new_value=new_value,
                ip_address=ip_address,
                status=status,
                error_message=error_message
            )
            session.add(log)
            session.commit()
            return log
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to log audit entry: {str(e)}")
            raise
        finally:
            session.close()


# ===================================================
# Test Functions
# ===================================================

if __name__ == "__main__":
    # Initialize database manager
    db_manager = MySQLManager()
    
    # Create tables
    print("Creating database tables...")
    db_manager.create_tables()
    
    print("MySQL database manager initialized successfully!")

