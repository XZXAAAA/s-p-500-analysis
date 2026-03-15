# Configuration file for the Flask application

# Debug mode: Set to True for faster testing (only 50 stocks), False for full S&P 500
DEBUG_MODE = False

# Cache duration in seconds (1 hour = 3600)
CACHE_DURATION = 3600

# Data generation settings
MAX_WORKERS = 15  # Number of concurrent threads for fetching news
REQUEST_DELAY_MIN = 1  # Minimum delay between requests (seconds)
REQUEST_DELAY_MAX = 3  # Maximum delay between requests (seconds)
BATCH_SLEEP_MIN = 2  # Minimum sleep after batch of requests (seconds)
BATCH_SLEEP_MAX = 5  # Maximum sleep after batch of requests (seconds)
BATCH_SIZE = 50  # Number of requests before longer sleep

