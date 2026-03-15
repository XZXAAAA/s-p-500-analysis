"""
Flask Web Application for S&P 500 Stock Sentiment Analysis
Main application file with routes, authentication, and sentiment analysis integration
"""

from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_file
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import os
import json
from datetime import datetime, date
import logging
from functools import wraps
import threading
import time
import uuid

# Import new database managers
from database.mysql_manager import MySQLManager
from database.dynamodb_manager import DynamoDBManager
from database.clickhouse_manager import ClickHouseManager
from database.data_sync_pipeline import get_sync_pipeline

# Import sentiment analysis functions
from marketviews_sentiment_panel_finalized import (
    get_data_to_draw, 
    draw_sentiment_panel,
    get_top_five,
    get_all_stocks,
    get_wiki_data,
    get_recent_data,
    get_tickers,
    get_news_table,
    parse_news_table,
    sentiment_analysis
)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)  # Change this to a secure random key in production

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'

# Initialize database managers
try:
    mysql_db = MySQLManager()
    logger.info("✓ MySQL database manager initialized")
except Exception as e:
    logger.error(f"✗ Failed to initialize MySQL: {str(e)}")
    mysql_db = None

try:
    dynamodb = DynamoDBManager()
    logger.info("✓ DynamoDB manager initialized")
except Exception as e:
    logger.warning(f"⚠ DynamoDB not available: {str(e)}")
    dynamodb = None

try:
    from database.env_config import ENABLE_CLICKHOUSE
    if ENABLE_CLICKHOUSE:
        clickhouse_db = ClickHouseManager()
        logger.info("✓ ClickHouse manager initialized")
    else:
        clickhouse_db = None
        logger.info("⊘ ClickHouse disabled")
except Exception as e:
    logger.warning(f"⚠ ClickHouse not available: {str(e)}")
    clickhouse_db = None

# Initialize data sync pipeline
try:
    sync_pipeline = get_sync_pipeline()
    sync_pipeline.start_realtime_sync()
    logger.info("✓ Data sync pipeline initialized and running")
except Exception as e:
    logger.warning(f"⚠ Data sync pipeline not available: {str(e)}")
    sync_pipeline = None

def init_db():
    """Initialize all databases with tables"""
    try:
        if mysql_db:
            mysql_db.create_tables()
            logger.info("✓ MySQL tables initialized")
    except Exception as e:
        logger.error(f"✗ Failed to initialize MySQL tables: {str(e)}")
    
    try:
        if clickhouse_db:
            clickhouse_db.init_database()
            logger.info("✓ ClickHouse database initialized")
    except Exception as e:
        logger.error(f"✗ Failed to initialize ClickHouse tables: {str(e)}")

# User class for Flask-Login
class User(UserMixin):
    def __init__(self, id, username, email):
        self.id = id
        self.username = username
        self.email = email

@login_manager.user_loader
def load_user(user_id):
    """Load user from MySQL database"""
    try:
        if mysql_db:
            user_obj = mysql_db.get_user_by_id(int(user_id))
            if user_obj:
                return User(user_obj.id, user_obj.username, user_obj.email)
    except Exception as e:
        logger.error(f"Error loading user: {str(e)}")
    return None

# Cache for sentiment data (to avoid re-scraping on every request)
sentiment_cache = {
    'data': None,
    'timestamp': None,
    'lock': threading.Lock(),
    'generating': False,
    'generation_start_time': None
}
# Try to import config, otherwise use defaults
try:
    from config import DEBUG_MODE, CACHE_DURATION
except ImportError:
    DEBUG_MODE = True  # Set to False for full S&P 500, True for faster testing (50 stocks only)
    CACHE_DURATION = 3600  # Cache for 1 hour

def get_cached_sentiment_data(force_refresh=False):
    """Get sentiment data from cache or generate new data"""
    with sentiment_cache['lock']:
        current_time = time.time()
        
        # Check if cache is valid
        if (not force_refresh and 
            sentiment_cache['data'] is not None and 
            sentiment_cache['timestamp'] is not None and
            (current_time - sentiment_cache['timestamp']) < CACHE_DURATION):
            return sentiment_cache['data']
        
        # Check if data is currently being generated
        if sentiment_cache['generating']:
            generation_time = 0
            if sentiment_cache['generation_start_time']:
                generation_time = current_time - sentiment_cache['generation_start_time']
            
            # If generation started more than 10 minutes ago, allow retry (likely stuck)
            if generation_time > 600:  # 10 minutes
                print(f"WARNING: Previous generation has been running for {int(generation_time/60)} minutes, allowing new generation")
                sentiment_cache['generating'] = False
                sentiment_cache['generation_start_time'] = None
            else:
                raise Exception(f"Data is currently being generated (running for {int(generation_time/60)} minutes). Please wait...")
        
        # For direct calls (not from background thread), use the direct generation function
        # But set the flag first
        sentiment_cache['generating'] = True
        sentiment_cache['generation_start_time'] = current_time
        
        try:
            _generate_data_directly()
            return sentiment_cache['data']
        except Exception as e:
            import traceback
            error_msg = f"Error generating sentiment data: {str(e)}\n{traceback.format_exc()}"
            print(error_msg)
            sentiment_cache['generating'] = False
            sentiment_cache['generation_start_time'] = None
            # Return cached data if available, even if expired
            if sentiment_cache['data'] is not None:
                print("Returning cached data due to error")
                return sentiment_cache['data']
            raise

# Routes
@app.route('/')
def index():
    """Home page - redirect to login or dashboard"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    """User registration page - using MySQL"""
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        # Validation
        if not username or not email or not password:
            return render_template('register.html', error='All fields are required')
        
        if password != confirm_password:
            return render_template('register.html', error='Passwords do not match')
        
        if len(password) < 6:
            return render_template('register.html', error='Password must be at least 6 characters')
        
        try:
            if not mysql_db:
                return render_template('register.html', error='Database connection failed')
            
            # Check if user already exists
            existing_user = mysql_db.get_user_by_username(username)
            if existing_user:
                return render_template('register.html', error='Username already exists')
            
            # Create new user
            password_hash = generate_password_hash(password)
            user_obj = mysql_db.create_user(username, email, password_hash)
            
            # Log audit
            mysql_db.log_action(
                user_id=user_obj.id,
                action='USER_REGISTER',
                resource_type='user',
                resource_id=str(user_obj.id),
                status='success'
            )
            
            # Log in the new user
            user = User(user_obj.id, user_obj.username, user_obj.email)
            login_user(user)
            
            logger.info(f"✓ User registered: {username}")
            return redirect(url_for('dashboard'))
        
        except Exception as e:
            logger.error(f"Registration error: {str(e)}")
            return render_template('register.html', error='Registration failed. Please try again.')
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """User login page - using MySQL"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if not username or not password:
            return render_template('login.html', error='Username and password are required')
        
        try:
            if not mysql_db:
                return render_template('login.html', error='Database connection failed')
            
            # Get user from MySQL
            user_obj = mysql_db.get_user_by_username(username)
            
            if user_obj and check_password_hash(user_obj.password_hash, password):
                # Update last login
                user_obj.last_login = datetime.utcnow()
                
                # Log audit
                mysql_db.log_action(
                    user_id=user_obj.id,
                    action='USER_LOGIN',
                    resource_type='user',
                    resource_id=str(user_obj.id),
                    status='success'
                )
                
                # Create Flask-Login user
                user = User(user_obj.id, user_obj.username, user_obj.email)
                login_user(user)
                
                logger.info(f"✓ User logged in: {username}")
                return redirect(url_for('dashboard'))
            else:
                # Log failed attempt
                if user_obj:
                    mysql_db.log_action(
                        user_id=user_obj.id,
                        action='USER_LOGIN_FAILED',
                        resource_type='user',
                        resource_id=str(user_obj.id),
                        status='failed',
                        error_message='Invalid password'
                    )
                return render_template('login.html', error='Invalid username or password')
        
        except Exception as e:
            logger.error(f"Login error: {str(e)}")
            return render_template('login.html', error='Login failed. Please try again.')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    """User logout"""
    # Log logout action
    try:
        if mysql_db:
            mysql_db.log_action(
                user_id=current_user.id,
                action='USER_LOGOUT',
                resource_type='user',
                resource_id=str(current_user.id),
                status='success'
            )
    except Exception as e:
        logger.error(f"Error logging logout: {str(e)}")
    
    logout_user()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    """Main dashboard with sentiment visualization"""
    return render_template('dashboard.html', username=current_user.username)

@app.route('/api/status')
@login_required
def get_status():
    """API endpoint to check data generation status"""
    with sentiment_cache['lock']:
        has_data = sentiment_cache['data'] is not None
        is_generating = sentiment_cache['generating']
        generation_time = None
        if sentiment_cache['generation_start_time']:
            generation_time = int(time.time() - sentiment_cache['generation_start_time'])
            # Auto-reset if generation has been running for more than 2 hours (likely stuck)
            if generation_time > 7200:  # 2 hours
                print(f"WARNING: Generation has been running for {generation_time} seconds (>2 hours), resetting...")
                sentiment_cache['generating'] = False
                sentiment_cache['generation_start_time'] = None
                is_generating = False
        
        return jsonify({
            'has_data': has_data,
            'is_generating': is_generating,
            'generation_time': generation_time,
            'timestamp': sentiment_cache['timestamp']
        })

@app.route('/api/reset-status', methods=['POST'])
@login_required
def reset_status():
    """Force reset generation status (use if stuck)"""
    with sentiment_cache['lock']:
        sentiment_cache['generating'] = False
        sentiment_cache['generation_start_time'] = None
        print("Generation status has been manually reset")
        return jsonify({
            'status': 'reset',
            'message': 'Generation status has been reset. You can now start a new generation.'
        })

@app.route('/api/refresh-data', methods=['POST'])
@login_required
def trigger_refresh():
    """Trigger data refresh in background"""
    try:
        with sentiment_cache['lock']:
            current_time = time.time()
            
            # Check if already generating, but allow reset if stuck
            if sentiment_cache['generating']:
                generation_time = 0
                if sentiment_cache['generation_start_time']:
                    generation_time = int(current_time - sentiment_cache['generation_start_time'])
                
                # If stuck for more than 10 minutes, reset and allow new generation
                if generation_time > 600:  # 10 minutes
                    print(f"WARNING: Previous generation stuck for {generation_time} seconds, resetting...")
                    sentiment_cache['generating'] = False
                    sentiment_cache['generation_start_time'] = None
                else:
                    return jsonify({
                        'status': 'generating',
                        'message': 'Data is already being generated',
                        'elapsed_time': generation_time
                    }), 202
            
            # Start generation in background thread
            def generate_data():
                try:
                    print("=" * 80)
                    print("BACKGROUND THREAD: Starting data generation...")
                    print("=" * 80)
                    # Directly call the generation logic without checking generating flag
                    # (we already set it before starting the thread)
                    _generate_data_directly()
                    print("=" * 80)
                    print("BACKGROUND THREAD: Data generation completed successfully!")
                    print("=" * 80)
                except Exception as e:
                    import traceback
                    error_msg = f"BACKGROUND THREAD ERROR: {str(e)}\n{traceback.format_exc()}"
                    print("=" * 80)
                    print(error_msg)
                    print("=" * 80)
                    # Reset generating flag on error
                    with sentiment_cache['lock']:
                        sentiment_cache['generating'] = False
                        sentiment_cache['generation_start_time'] = None
            
            # Set generating flag BEFORE starting thread
            sentiment_cache['generating'] = True
            sentiment_cache['generation_start_time'] = current_time
            
            thread = threading.Thread(target=generate_data, daemon=True)
            thread.start()
            print(f"Background thread started: {thread.name}")
            
            return jsonify({
                'status': 'started',
                'message': 'Data generation started in background. This may take 10-30 minutes.'
            }), 202
    except Exception as e:
        import traceback
        print(f"Error in trigger_refresh: {e}\n{traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

def _generate_data_directly():
    """Direct data generation without checking generating flag (for background thread)"""
    current_time = time.time()
    
    try:
        print("=" * 80)
        print("Generating new sentiment data...")
        print(f"DEBUG_MODE: {DEBUG_MODE} (using {'50 stocks' if DEBUG_MODE else 'all S&P 500 stocks'})")
        print("=" * 80)
        
        # Get base data
        print("[STEP 1/6] Getting tickers from Wikipedia...")
        tickers = get_tickers(debug=DEBUG_MODE)
        print(f"✓ Retrieved {len(tickers)} tickers")
        
        print(f"\n[STEP 2/6] Fetching news data from Finviz (this may take a while)...")
        print(f"Processing {len(tickers)} stocks with delays...")
        news_tables = get_news_table(tickers)
        print(f"✓ Retrieved news for {len(news_tables)} stocks")
        
        print(f"\n[STEP 3/6] Parsing news data...")
        parsed_news = parse_news_table(news_tables)
        print(f"✓ Parsed {len(parsed_news)} news items")
        
        print(f"\n[STEP 4/6] Performing sentiment analysis...")
        parsed_news_scores = sentiment_analysis(parsed_news)
        print(f"✓ Analyzed sentiment for {len(parsed_news_scores)} news items")
        
        print(f"\n[STEP 5/6] Calculating recent sentiment scores...")
        mean_scores = get_recent_data(parsed_news_scores)
        print(f"✓ Calculated scores for {len(mean_scores)} stocks")
        
        print(f"\n[STEP 6/6] Merging with sector data and generating reports...")
        grouped = get_wiki_data(mean_scores)
        print("✓ Merged with sector data")
        
        # Get both top 5 and all stocks
        top5, low5 = get_top_five(grouped)
        print(f"✓ Generated top5: {len(top5)} stocks, low5: {len(low5)} stocks")
        
        all_positive, all_negative = get_all_stocks(grouped)
        print(f"✓ Generated all_positive: {len(all_positive)} stocks, all_negative: {len(all_negative)} stocks")
        
        # Save sentiment data to MySQL
        print(f"\n[STEP 7/7] Saving sentiment data to MySQL database...")
        if mysql_db:
            try:
                today = date.today()
                for _, row in mean_scores.iterrows():
                    mysql_db.save_sentiment_snapshot(
                        ticker=row['Ticker'],
                        snapshot_date=today,
                        sentiment_score=float(row.get('Sentiment Score', 0)),
                        positive_ratio=float(row.get('Positive', 0)),
                        negative_ratio=float(row.get('Negative', 0)),
                        neutral_ratio=float(row.get('Neutral', 0)),
                        news_count=0  # Will be updated later if needed
                    )
                print(f"✓ Saved {len(mean_scores)} sentiment snapshots to MySQL")
            except Exception as e:
                logger.warning(f"Error saving sentiment data to MySQL: {str(e)}")
        
        # Save to DynamoDB for fast access
        if dynamodb:
            try:
                timestamp = int(current_time)
                for _, row in mean_scores.iterrows():
                    dynamodb.save_realtime_sentiment(
                        ticker=row['Ticker'],
                        timestamp=timestamp,
                        sentiment_score=float(row.get('Sentiment Score', 0)),
                        positive=float(row.get('Positive', 0)),
                        negative=float(row.get('Negative', 0)),
                        neutral=float(row.get('Neutral', 0)),
                        source='finviz'
                    )
                print(f"✓ Saved {len(mean_scores)} sentiment data to DynamoDB")
            except Exception as e:
                logger.warning(f"Error saving sentiment data to DynamoDB: {str(e)}")
        
        # Save to ClickHouse for real-time analytics
        print(f"\n[STEP 8/8] Saving sentiment data to ClickHouse...")
        if clickhouse_db:
            try:
                # Build events list with sector information
                events = []
                for sector, sector_group in grouped:
                    for _, row in sector_group.iterrows():
                        events.append({
                            'ticker': row['Ticker'],
                            'sector': sector,
                            'sentiment_score': float(row.get('Sentiment Score', 0)),
                            'positive': float(row.get('Positive', 0)),
                            'negative': float(row.get('Negative', 0)),
                            'neutral': float(row.get('Neutral', 0)),
                            'news_count': 0
                        })
                
                if events:
                    clickhouse_db.insert_sentiment_events_batch(events)
                    print(f"✓ Saved {len(events)} sentiment events to ClickHouse")
            except Exception as e:
                logger.warning(f"Error saving sentiment data to ClickHouse: {str(e)}")
        
        with sentiment_cache['lock']:
            sentiment_cache['data'] = {
                'top5': top5,
                'low5': low5,
                'all_positive': all_positive,
                'all_negative': all_negative
            }
            sentiment_cache['timestamp'] = current_time
            sentiment_cache['generating'] = False
            sentiment_cache['generation_start_time'] = None
        
        print("=" * 80)
        print("✓ Data generation completed successfully!")
        print("=" * 80)
    except Exception as e:
        import traceback
        error_msg = f"Error generating sentiment data: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)
        with sentiment_cache['lock']:
            sentiment_cache['generating'] = False
            sentiment_cache['generation_start_time'] = None
        raise

@app.route('/api/sentiment-data')
@login_required
def get_sentiment_data():
    """API endpoint to get sentiment data"""
    sentiment_type = request.args.get('type', 'positive')  # 'positive' or 'negative'
    view_mode = request.args.get('mode', 'top5')  # 'top5' or 'all'
    force_refresh = request.args.get('refresh', 'false').lower() == 'true'
    
    try:
        # Don't allow force refresh here - use /api/refresh-data endpoint instead
        if force_refresh:
            return jsonify({
                'error': 'Please use the "Refresh Data" button to trigger data generation. This endpoint does not support force refresh.'
            }), 400
        
        data = get_cached_sentiment_data(force_refresh=False)
        
        # Select data based on sentiment type and view mode
        if view_mode == 'all':
            if sentiment_type == 'positive':
                df = data['all_positive']
            else:
                df = data['all_negative']
        else:  # top5
            if sentiment_type == 'positive':
                df = data['top5']
            else:
                df = data['low5']
        
        # Convert DataFrame to JSON
        result = {
            'data': df.to_dict('records'),
            'timestamp': sentiment_cache['timestamp']
        }
        
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/treemap')
@login_required
def get_treemap():
    """API endpoint to get treemap visualization JSON"""
    sentiment_type = request.args.get('type', 'positive')
    view_mode = request.args.get('mode', 'top5')  # 'top5' or 'all'
    force_refresh = request.args.get('refresh', 'false').lower() == 'true'
    
    try:
        data = get_cached_sentiment_data(force_refresh=force_refresh)
        
        # Select data based on view mode
        if view_mode == 'all':
            positive_df = data.get('all_positive')
            negative_df = data.get('all_negative')
            if positive_df is None or negative_df is None:
                return jsonify({'error': 'All stocks data not available. Please refresh data first.'}), 500
        else:  # top5
            positive_df = data.get('top5')
            negative_df = data.get('low5')
            if positive_df is None or negative_df is None:
                return jsonify({'error': 'Top 5 data not available. Please refresh data first.'}), 500
        
        # Check if dataframes are empty
        if positive_df.empty or negative_df.empty:
            return jsonify({'error': 'No data available. Please refresh data first.'}), 500
        
        # Generate treemap
        fig_json_top, fig_json_low = draw_sentiment_panel(positive_df, negative_df)
        
        if sentiment_type == 'positive':
            result = json.loads(fig_json_top)
        else:
            result = json.loads(fig_json_low)
        
        return jsonify(result)
    except Exception as e:
        import traceback
        error_msg = f"Error generating treemap: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)
        return jsonify({'error': str(e)}), 500

@app.route('/api/download-csv')
@login_required
def download_csv():
    """Download sentiment data as CSV"""
    sentiment_type = request.args.get('type', 'positive')
    view_mode = request.args.get('mode', 'top5')  # 'top5' or 'all'
    
    try:
        data = get_cached_sentiment_data()
        
        # Select data based on sentiment type and view mode
        if view_mode == 'all':
            if sentiment_type == 'positive':
                df = data['all_positive']
                filename = f'sentiment_positive_all_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
            else:
                df = data['all_negative']
                filename = f'sentiment_negative_all_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        else:  # top5
            if sentiment_type == 'positive':
                df = data['top5']
                filename = f'sentiment_positive_top5_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
            else:
                df = data['low5']
                filename = f'sentiment_negative_top5_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        
        # Save to temporary file
        temp_path = os.path.join('temp', filename)
        os.makedirs('temp', exist_ok=True)
        df.to_csv(temp_path, index=False)
        
        # Log action
        if mysql_db:
            mysql_db.log_action(
                user_id=current_user.id,
                action='DOWNLOAD_CSV',
                resource_type='data',
                resource_id=sentiment_type,
                status='success'
            )
        
        return send_file(temp_path, as_attachment=True, download_name=filename)
    except Exception as e:
        if mysql_db:
            mysql_db.log_action(
                user_id=current_user.id,
                action='DOWNLOAD_CSV',
                resource_type='data',
                resource_id=sentiment_type,
                status='failed',
                error_message=str(e)
            )
        return jsonify({'error': str(e)}), 500

@app.route('/api/user-profile')
@login_required
def get_user_profile():
    """Get current user profile from MySQL"""
    try:
        if not mysql_db:
            return jsonify({'error': 'Database connection failed'}), 500
        
        user_obj = mysql_db.get_user_by_id(current_user.id)
        if not user_obj:
            return jsonify({'error': 'User not found'}), 404
        
        return jsonify({
            'id': user_obj.id,
            'username': user_obj.username,
            'email': user_obj.email,
            'created_at': user_obj.created_at.isoformat() if user_obj.created_at else None,
            'last_login': user_obj.last_login.isoformat() if user_obj.last_login else None
        })
    except Exception as e:
        logger.error(f"Error fetching user profile: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/user-preferences', methods=['GET', 'POST'])
@login_required
def manage_user_preferences():
    """Manage user preferences (watchlist, alerts, etc.) via DynamoDB"""
    try:
        if request.method == 'GET':
            if dynamodb:
                prefs = dynamodb.get_user_preferences(str(current_user.id))
                if prefs:
                    return jsonify(prefs)
            return jsonify({'watchlist': [], 'theme': 'light', 'language': 'en'})
        
        elif request.method == 'POST':
            data = request.get_json()
            if not dynamodb:
                return jsonify({'error': 'DynamoDB not available'}), 500
            
            watchlist = data.get('watchlist', [])
            theme = data.get('theme', 'light')
            language = data.get('language', 'en')
            
            prefs = dynamodb.save_user_preferences(
                user_id=str(current_user.id),
                watchlist=watchlist,
                theme=theme,
                language=language
            )
            
            # Log action
            if mysql_db:
                mysql_db.log_action(
                    user_id=current_user.id,
                    action='UPDATE_PREFERENCES',
                    resource_type='preferences',
                    resource_id=str(current_user.id),
                    new_value=data,
                    status='success'
                )
            
            return jsonify(prefs)
    except Exception as e:
        logger.error(f"Error managing preferences: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/analytics/sentiment-timeline')
@login_required
def get_sentiment_timeline():
    """Get stock sentiment timeline analysis (ClickHouse)"""
    try:
        ticker = request.args.get('ticker', 'AAPL')
        days = int(request.args.get('days', 7))
        
        if not clickhouse_db:
            return jsonify({'error': 'ClickHouse not available'}), 503
        
        timeline = clickhouse_db.get_ticker_analysis(ticker, days)
        
        # Log operation
        if mysql_db:
            mysql_db.log_action(
                user_id=current_user.id,
                action='VIEW_SENTIMENT_TIMELINE',
                resource_type='analytics',
                resource_id=ticker,
                status='success'
            )
        
        return jsonify({
            'ticker': ticker,
            'timeline': [
                {
                    'date': str(row[0]),
                    'sentiment_score': round(row[4], 3),
                    'positive': round(row[5], 3),
                    'negative': round(row[6], 3),
                    'news_count': row[8]
                } for row in timeline
            ],
            'period_days': days
        })
    except Exception as e:
        logger.error(f"Error getting sentiment timeline: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/analytics/market-overview')
@login_required
def get_market_overview():
    """获取市场整体情感概览（ClickHouse）"""
    try:
        days = int(request.args.get('days', 7))
        
        if not clickhouse_db:
            return jsonify({'error': 'ClickHouse not available'}), 503
        
        overview = clickhouse_db.get_daily_sentiment_summary(days)
        
        # Log operation
        if mysql_db:
            mysql_db.log_action(
                user_id=current_user.id,
                action='VIEW_MARKET_OVERVIEW',
                resource_type='analytics',
                resource_id='market',
                status='success'
            )
        
        if not overview:
            return jsonify({'market_overview': {'sectors': []}}),200
        
        # Return as object with sectors array for frontend
        return jsonify({
            'market_overview': {
                'period_days': days,
                'sectors': [
                    {
                        'Date': str(row[0]),
                        'Sector': row[1],
                        'Avg_Sentiment': round(row[3], 3),
                        'Ticker_Count': row[2],
                        'Total_News': row[6]
                    } for row in overview
                ]
            }
        })
    except Exception as e:
        logger.error(f"Error getting market overview: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/analytics/top-gainers')
@login_required
def get_top_gainers():
    """获取情感最高的股票（ClickHouse）"""
    try:
        limit = int(request.args.get('limit', 10))
        days = int(request.args.get('days', 7))
        
        if not clickhouse_db:
            return jsonify({'error': 'ClickHouse not available'}), 503
        
        gainers = clickhouse_db.get_top_positive_stocks(days, limit)
        
        # Return as direct array for frontend
        return jsonify([
            {
                'Ticker': row[0],
                'Sector': row[1],
                'Avg_Sentiment': round(row[2], 3),
                'Total_News': row[4]
            } for row in gainers
        ])
    except Exception as e:
        logger.error(f"Error getting top gainers: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/analytics/top-losers')
@login_required
def get_top_losers():
    """获取情感最低的股票（ClickHouse）"""
    try:
        limit = int(request.args.get('limit', 10))
        days = int(request.args.get('days', 7))
        
        if not clickhouse_db:
            return jsonify({'error': 'ClickHouse not available'}), 503
        
        losers = clickhouse_db.get_top_negative_stocks(days, limit)
        
        # Return as direct array for frontend
        return jsonify([
            {
                'Ticker': row[0],
                'Sector': row[1],
                'Avg_Sentiment': round(row[2], 3),
                'Total_News': row[4]
            } for row in losers
        ])
    except Exception as e:
        logger.error(f"Error getting top losers: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/analytics/sector-analysis')
@login_required
def get_sector_analysis():
    """获取部门情感分析"""
    try:
        days = int(request.args.get('days', 7))
        
        if not clickhouse_db:
            return jsonify({'error': 'ClickHouse not available'}), 503
        
        stats = clickhouse_db.get_sector_statistics(days)
        
        # Log operation
        if mysql_db:
            mysql_db.log_action(
                user_id=current_user.id,
                action='VIEW_SECTOR_ANALYSIS',
                resource_type='analytics',
                resource_id='sectors',
                status='success'
            )
        
        if not stats:
            return jsonify({'sectors': []}), 200
        
        # Return as object with sectors array for frontend
        return jsonify({
            'sectors': [
                {
                    'Sector': row[0],
                    'Ticker_Count': row[1],
                    'Avg_Sentiment': round(row[2], 3),
                    'Max_Sentiment': round(row[3], 3),
                    'Min_Sentiment': round(row[4], 3),
                    'Total_News': row[5],
                    'Volatility': round(row[6], 3) if len(row) > 6 and row[6] else 0
                } for row in stats
            ],
            'period_days': days
        })
    except Exception as e:
        logger.error(f"Error getting sector analysis: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/analytics/sector-trends')
@login_required
def get_sector_trends():
    """获取部门趋势分析"""
    try:
        sector = request.args.get('sector', None)
        days = int(request.args.get('days', 7))
        
        if not clickhouse_db:
            return jsonify({'error': 'ClickHouse not available'}), 503
        
        trends = clickhouse_db.get_sector_trends(sector, days)
        
        if not trends:
            return jsonify({'trends': []}), 200
        
        return jsonify({
            'sector': sector or 'all',
            'trends': [
                {
                    'date': str(row[0]),
                    'sector': row[1],
                    'avg_sentiment': round(row[2], 3),
                    'ticker_count': row[3],
                    'total_news': row[4]
                } for row in trends
            ],
            'period_days': days
        })
    except Exception as e:
        logger.error(f"Error getting sector trends: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Initialize database
    init_db()
    
    # Create necessary directories
    os.makedirs('temp', exist_ok=True)
    os.makedirs('panel_data', exist_ok=True)
    
    # Run the app
    app.run(debug=True, host='0.0.0.0', port=5000)

