# Database Migration Scripts

This folder contains all database migration and initialization scripts.

## File Descriptions

### migrate_sqlite_to_mysql.py
Migrates user data from SQLite database to MySQL database.

**Usage**:
```bash
cd backend/database/migrations
python migrate_sqlite_to_mysql.py
```

**Features**:
- Read user data from SQLite
- Check if user already exists in MySQL
- Automatically migrate non-existent users
- Display migration statistics

### init_clickhouse.py
Initializes ClickHouse analytics database and creates necessary tables.

**Usage**:
```bash
cd backend/database/migrations
python init_clickhouse.py
```

**Features**:
- Create ClickHouse database
- Create sentiment_events table
- Create sector_statistics table
- Verify table creation

## Prerequisites

- Python 3.11+
- Required packages installed (see requirements.txt)
- Database services running (MySQL, ClickHouse)
- Correct environment variables configured (.env file)

## Notes

- Run migrations in order
- Back up data before migration
- Check logs for any errors
- Verify data integrity after migration
