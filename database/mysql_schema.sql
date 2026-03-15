-- ===================================================
-- MySQL Database Schema - Transactional Database (Core Business Data)
-- ===================================================

-- 1. Users Table
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(255) UNIQUE NOT NULL COMMENT 'Username',
    email VARCHAR(255) UNIQUE NOT NULL COMMENT 'Email',
    password_hash VARCHAR(255) NOT NULL COMMENT 'Password hash',
    user_role ENUM('admin', 'user') DEFAULT 'user' COMMENT 'User role',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT 'Creation time',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Update time',
    is_active BOOLEAN DEFAULT TRUE COMMENT 'Is active',
    last_login TIMESTAMP NULL COMMENT 'Last login time',
    INDEX idx_username (username),
    INDEX idx_email (email),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Users table';

-- 2. Stocks Table
CREATE TABLE IF NOT EXISTS stocks (
    id INT AUTO_INCREMENT PRIMARY KEY,
    ticker VARCHAR(10) UNIQUE NOT NULL COMMENT 'Stock ticker',
    company_name VARCHAR(255) COMMENT 'Company name',
    sector VARCHAR(100) COMMENT 'Sector',
    industry VARCHAR(100) COMMENT 'Industry',
    description TEXT COMMENT 'Company description',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT 'Creation time',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Update time',
    INDEX idx_ticker (ticker),
    INDEX idx_sector (sector),
    INDEX idx_industry (industry)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Stocks table';

-- 3. Sentiment Snapshots Table
CREATE TABLE IF NOT EXISTS sentiment_snapshots (
    id INT AUTO_INCREMENT PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL COMMENT 'Stock ticker',
    snapshot_date DATE NOT NULL COMMENT 'Snapshot date',
    sentiment_score DECIMAL(5,4) COMMENT 'Overall sentiment score (-1 to 1)',
    positive_ratio DECIMAL(5,4) COMMENT 'Positive ratio (0 to 1)',
    negative_ratio DECIMAL(5,4) COMMENT 'Negative ratio (0 to 1)',
    neutral_ratio DECIMAL(5,4) COMMENT 'Neutral ratio (0 to 1)',
    news_count INT DEFAULT 0 COMMENT 'News count',
    source VARCHAR(100) DEFAULT 'finviz' COMMENT 'Data source',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT 'Creation time',
    UNIQUE KEY unique_ticker_date (ticker, snapshot_date),
    INDEX idx_ticker (ticker),
    INDEX idx_date (snapshot_date),
    INDEX idx_created_at (created_at),
    FOREIGN KEY (ticker) REFERENCES stocks(ticker) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Sentiment snapshots table';

-- 4. News Records Table
CREATE TABLE IF NOT EXISTS news_records (
    id INT AUTO_INCREMENT PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL COMMENT 'Stock ticker',
    headline VARCHAR(500) NOT NULL COMMENT 'News headline',
    news_date DATE COMMENT 'News date',
    news_time VARCHAR(20) COMMENT 'News time',
    sentiment_score DECIMAL(5,4) COMMENT 'Single news sentiment score',
    positive DECIMAL(5,4) COMMENT 'Positive score',
    negative DECIMAL(5,4) COMMENT 'Negative score',
    neutral DECIMAL(5,4) COMMENT 'Neutral score',
    source VARCHAR(100) DEFAULT 'finviz' COMMENT 'Data source',
    url VARCHAR(500) COMMENT 'News URL',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT 'Creation time',
    INDEX idx_ticker (ticker),
    INDEX idx_date (news_date),
    INDEX idx_created_at (created_at),
    FOREIGN KEY (ticker) REFERENCES stocks(ticker) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='News records table';

-- 5. User Preferences Table
CREATE TABLE IF NOT EXISTS user_preferences (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL UNIQUE COMMENT 'User ID',
    watchlist JSON COMMENT 'Watchlist (JSON list of stocks)',
    alert_threshold_positive DECIMAL(5,4) DEFAULT 0.50 COMMENT 'Positive alert threshold',
    alert_threshold_negative DECIMAL(5,4) DEFAULT -0.50 COMMENT 'Negative alert threshold',
    notification_enabled BOOLEAN DEFAULT TRUE COMMENT 'Notifications enabled',
    dashboard_layout VARCHAR(50) DEFAULT 'default' COMMENT 'Dashboard layout',
    theme VARCHAR(20) DEFAULT 'light' COMMENT 'Theme (light/dark)',
    language VARCHAR(10) DEFAULT 'en' COMMENT 'Language',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT 'Creation time',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Update time',
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE ON UPDATE CASCADE,
    INDEX idx_user_id (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='User preferences table';

-- 6. User Query History Table
CREATE TABLE IF NOT EXISTS query_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL COMMENT 'User ID',
    ticker VARCHAR(10) COMMENT 'Queried stock ticker',
    sector VARCHAR(100) COMMENT 'Queried sector',
    query_type VARCHAR(50) COMMENT 'Query type (ticker/sector/all)',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT 'Creation time',
    INDEX idx_user_id (user_id),
    INDEX idx_created_at (created_at),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='User query history table';

-- 7. User Alerts Table
CREATE TABLE IF NOT EXISTS user_alerts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL COMMENT 'User ID',
    ticker VARCHAR(10) NOT NULL COMMENT 'Stock ticker',
    alert_type ENUM('sentiment_spike', 'threshold_reached', 'sector_trend') COMMENT 'Alert type',
    alert_condition VARCHAR(255) COMMENT 'Alert condition',
    is_active BOOLEAN DEFAULT TRUE COMMENT 'Is active',
    triggered_count INT DEFAULT 0 COMMENT 'Trigger count',
    last_triggered TIMESTAMP NULL COMMENT 'Last triggered time',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT 'Creation time',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Update time',
    INDEX idx_user_id (user_id),
    INDEX idx_ticker (ticker),
    INDEX idx_is_active (is_active),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (ticker) REFERENCES stocks(ticker) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='User alerts table';

-- 8. Audit Logs Table
CREATE TABLE IF NOT EXISTS audit_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT COMMENT 'User ID',
    action VARCHAR(100) NOT NULL COMMENT 'Action type',
    resource_type VARCHAR(100) COMMENT 'Resource type',
    resource_id VARCHAR(100) COMMENT 'Resource ID',
    old_value JSON COMMENT 'Old value',
    new_value JSON COMMENT 'New value',
    ip_address VARCHAR(45) COMMENT 'IP address',
    status VARCHAR(20) DEFAULT 'success' COMMENT 'Operation status',
    error_message TEXT COMMENT 'Error message',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT 'Creation time',
    INDEX idx_user_id (user_id),
    INDEX idx_action (action),
    INDEX idx_created_at (created_at),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Audit logs table';

-- 9. Sync Status Table
CREATE TABLE IF NOT EXISTS sync_status (
    id INT AUTO_INCREMENT PRIMARY KEY,
    source_table VARCHAR(100) NOT NULL COMMENT 'Source table',
    target_db VARCHAR(50) NOT NULL COMMENT 'Target database',
    last_sync_time TIMESTAMP COMMENT 'Last sync time',
    last_record_id INT COMMENT 'Last synced record ID',
    status VARCHAR(20) DEFAULT 'success' COMMENT 'Sync status',
    error_message TEXT COMMENT 'Error message',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT 'Creation time',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Update time',
    UNIQUE KEY unique_source_target (source_table, target_db),
    INDEX idx_updated_at (updated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Sync status table';

-- ===================================================
-- Create Triggers: Auto-update updated_at field
-- ===================================================

DELIMITER //

CREATE TRIGGER users_update_trigger
BEFORE UPDATE ON users
FOR EACH ROW
BEGIN
    SET NEW.updated_at = CURRENT_TIMESTAMP;
END//

CREATE TRIGGER stocks_update_trigger
BEFORE UPDATE ON stocks
FOR EACH ROW
BEGIN
    SET NEW.updated_at = CURRENT_TIMESTAMP;
END//

CREATE TRIGGER user_preferences_update_trigger
BEFORE UPDATE ON user_preferences
FOR EACH ROW
BEGIN
    SET NEW.updated_at = CURRENT_TIMESTAMP;
END//

CREATE TRIGGER user_alerts_update_trigger
BEFORE UPDATE ON user_alerts
FOR EACH ROW
BEGIN
    SET NEW.updated_at = CURRENT_TIMESTAMP;
END//

DELIMITER ;

-- ===================================================
-- Initialize Stock Data (S&P 500 Sample)
-- ===================================================

INSERT INTO stocks (ticker, company_name, sector, industry) VALUES
('AAPL', 'Apple Inc.', 'Information Technology', 'Consumer Electronics'),
('MSFT', 'Microsoft Corporation', 'Information Technology', 'Software'),
('GOOGL', 'Alphabet Inc.', 'Communication Services', 'Internet Services'),
('AMZN', 'Amazon.com Inc.', 'Consumer Discretionary', 'Internet Retail'),
('TSLA', 'Tesla Inc.', 'Consumer Discretionary', 'Automotive'),
('JPM', 'JPMorgan Chase & Co.', 'Financials', 'Banks'),
('JNJ', 'Johnson & Johnson', 'Healthcare', 'Pharmaceuticals'),
('V', 'Visa Inc.', 'Financials', 'Financial Services'),
('WMT', 'Walmart Inc.', 'Consumer Staples', 'Retail'),
('MCD', 'McDonald\'s Corporation', 'Consumer Discretionary', 'Restaurants')
ON DUPLICATE KEY UPDATE company_name=VALUES(company_name);

