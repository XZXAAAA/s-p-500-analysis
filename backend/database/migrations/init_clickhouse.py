#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""ClickHouse Initialization Script"""

import time
import sys
from pathlib import Path

# Add project root directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from database.clickhouse_manager import ClickHouseManager

time.sleep(3)  # Wait for ClickHouse to start

try:
    print("Initializing ClickHouse...")
    mgr = ClickHouseManager()
    result = mgr.init_tables()
    
    if result:
        print("\n✓ ClickHouse initialization successful!")
        print("✓ Created the following tables:")
        print("  - sentiment_events (sentiment events table)")
        print("  - market_trends (market trends table)")
        print("  - daily_sentiment_stats (daily statistics table)")
    else:
        print("\n✗ ClickHouse initialization failed, please check connection")
        
except Exception as e:
    print(f"\n✗ Error: {str(e)}")

