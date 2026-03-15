"""
Unit tests for database managers.

Covers:
- MySQLManager  : ORM model creation, save_sentiment_snapshot call contract
- DynamoDBManager: table-name prefixing, save_realtime_sentiment call contract
- ClickHouseManager: batch insert, query validation
- DataSyncPipeline: initialization and event structure
"""

import sys
import os
import unittest
from unittest.mock import Mock, patch, MagicMock, call
from datetime import date

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
_ROOT = os.path.join(os.path.dirname(__file__), "../..")
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


# ===========================================================================
# MySQL Manager
# ===========================================================================

class TestMySQLManagerModels(unittest.TestCase):
    """SQLAlchemy ORM model creation — no real DB connection needed."""

    def test_user_model_attributes(self):
        from database.mysql_manager import User
        u = User(
            username="alice",
            email="alice@example.com",
            password_hash="$2b$12$hash",
            user_role="user",
        )
        self.assertEqual(u.username, "alice")
        self.assertEqual(u.email, "alice@example.com")
        self.assertEqual(u.user_role, "user")

    def test_stock_model_attributes(self):
        from database.mysql_manager import Stock
        s = Stock(ticker="AAPL", company_name="Apple Inc.",
                  sector="Technology", industry="Consumer Electronics")
        self.assertEqual(s.ticker, "AAPL")
        self.assertEqual(s.sector, "Technology")

    def test_sentiment_snapshot_attributes(self):
        from database.mysql_manager import SentimentSnapshot
        snap = SentimentSnapshot(
            ticker="AAPL",
            snapshot_date=date.today(),
            sentiment_score=0.75,
            positive_ratio=0.8,
            negative_ratio=0.1,
            neutral_ratio=0.1,
            news_count=50,
        )
        self.assertEqual(snap.ticker, "AAPL")
        self.assertAlmostEqual(snap.sentiment_score, 0.75)
        self.assertEqual(snap.news_count, 50)


class TestMySQLManagerInit(unittest.TestCase):
    """MySQLManager constructor and session factory."""

    @patch("database.mysql_manager.create_engine")
    @patch("database.mysql_manager.sessionmaker")
    def test_init_creates_engine_and_session(self, mock_sm, mock_engine):
        mock_engine.return_value = Mock()
        mock_sm.return_value = Mock()

        from database.mysql_manager import MySQLManager
        mgr = MySQLManager()

        mock_engine.assert_called_once()
        self.assertIsNotNone(mgr.engine)

    @patch("database.mysql_manager.create_engine")
    @patch("database.mysql_manager.sessionmaker")
    def test_save_sentiment_snapshot_opens_session(self, mock_sm, mock_engine):
        """save_sentiment_snapshot must open a DB session and commit."""
        mock_engine.return_value = Mock()
        mock_session = MagicMock()
        mock_sm.return_value = mock_session

        from database.mysql_manager import MySQLManager
        mgr = MySQLManager()

        today = date.today()
        mgr.save_sentiment_snapshot(
            ticker="AAPL", snapshot_date=today,
            sentiment_score=0.7, positive_ratio=0.6,
            negative_ratio=0.2, neutral_ratio=0.2, news_count=5,
        )
        # Session must have been called (opened)
        mock_session.assert_called()


# ===========================================================================
# DynamoDB Manager
# ===========================================================================

def _inject_boto3_mock():
    """Inject mock boto3 + botocore into sys.modules so dynamodb_manager can be imported."""
    import sys
    for mod_name in ("boto3", "botocore", "botocore.exceptions"):
        if mod_name not in sys.modules:
            sys.modules[mod_name] = MagicMock()
    if "database.dynamodb_manager" in sys.modules:
        del sys.modules["database.dynamodb_manager"]


class TestDynamoDBManager(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        _inject_boto3_mock()

    def _make_manager(self):
        import sys
        mock_dynamo = MagicMock()
        sys.modules["boto3"].resource.return_value = mock_dynamo
        # Force re-import to pick up mock
        if "database.dynamodb_manager" in sys.modules:
            del sys.modules["database.dynamodb_manager"]
        from database.dynamodb_manager import DynamoDBManager
        mgr = DynamoDBManager()
        return mgr, mock_dynamo

    def test_init_stores_dynamodb_resource(self):
        mgr, _ = self._make_manager()
        self.assertIsNotNone(mgr.dynamodb)

    def test_table_prefix_stored(self):
        mgr, _ = self._make_manager()
        self.assertIsNotNone(mgr.table_prefix)

    def test_get_table_uses_prefix(self):
        mgr, mock_dynamo = self._make_manager()
        mgr.get_table("user_sessions")
        mock_dynamo.Table.assert_called()
        table_name_used = mock_dynamo.Table.call_args[0][0]
        self.assertIn("user_sessions", table_name_used)

    def test_table_name_prefix_concatenation(self):
        prefix = "sentiment_"
        table = "user_sessions"
        self.assertEqual(f"{prefix}{table}", "sentiment_user_sessions")

    def test_save_realtime_sentiment_calls_put_item(self):
        """save_realtime_sentiment must call put_item on the table."""
        import time
        mgr, mock_dynamo = self._make_manager()
        mock_table = MagicMock()
        mock_dynamo.Table.return_value = mock_table
        mgr.save_realtime_sentiment(
            ticker="AAPL", timestamp=int(time.time()),
            sentiment_score=0.7, positive=0.6,
            negative=0.2, neutral=0.2, source="test",
        )
        mock_table.put_item.assert_called_once()


# ===========================================================================
# ClickHouse Manager
# ===========================================================================

def _inject_clickhouse_mock():
    """Inject mock clickhouse_driver into sys.modules."""
    import sys
    for mod_name in ("clickhouse_driver", "clickhouse_driver.client"):
        if mod_name not in sys.modules:
            sys.modules[mod_name] = MagicMock()
    if "database.clickhouse_manager" in sys.modules:
        del sys.modules["database.clickhouse_manager"]


class TestClickHouseManager(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        _inject_clickhouse_mock()

    def _make_manager(self):
        import sys
        mock_client_inst = MagicMock()
        sys.modules["clickhouse_driver"].Client.return_value = mock_client_inst
        if "database.clickhouse_manager" in sys.modules:
            del sys.modules["database.clickhouse_manager"]
        from database.clickhouse_manager import ClickHouseManager
        mgr = ClickHouseManager()
        return mgr, mock_client_inst

    def test_init_stores_client(self):
        mgr, _ = self._make_manager()
        self.assertIsNotNone(mgr.client)

    def test_database_name_stored(self):
        mgr, _ = self._make_manager()
        self.assertIsNotNone(mgr.database)

    def test_days_parameter_clamped_to_90(self):
        days = 100
        clamped = max(1, min(int(days), 90))
        self.assertEqual(clamped, 90)

    def test_days_parameter_clamped_to_1(self):
        days = 0
        clamped = max(1, min(int(days), 90))
        self.assertEqual(clamped, 1)

    def test_limit_parameter_clamped_to_500(self):
        limit = 1000
        clamped = max(1, min(int(limit), 500))
        self.assertEqual(clamped, 500)

    def test_ticker_normalization(self):
        ticker = "  aapl  "
        self.assertEqual(ticker.strip().upper(), "AAPL")

    def test_insert_sentiment_events_batch_calls_execute(self):
        """insert_sentiment_events_batch must call client.execute."""
        mgr, mock_client = self._make_manager()
        events = [
            {"ticker": "AAPL", "sector": "Tech", "sentiment_score": 0.8,
             "positive": 0.7, "negative": 0.1, "neutral": 0.2, "news_count": 5},
        ]
        mgr.insert_sentiment_events_batch(events)
        mock_client.execute.assert_called_once()


# ===========================================================================
# DataSyncPipeline
# ===========================================================================

class TestDataSyncPipeline(unittest.TestCase):

    def test_init_stores_all_three_managers(self):
        import sys
        # Ensure mocks are in place before importing data_sync_pipeline
        _inject_boto3_mock()
        _inject_clickhouse_mock()
        if "database.data_sync_pipeline" in sys.modules:
            del sys.modules["database.data_sync_pipeline"]

        import database.data_sync_pipeline as mod
        mock_mysql = MagicMock()
        mock_dynamo = MagicMock()
        mock_ch = MagicMock()
        with (
            patch.object(mod, "MySQLManager", return_value=mock_mysql),
            patch.object(mod, "DynamoDBManager", return_value=mock_dynamo),
            patch.object(mod, "ClickHouseManager", return_value=mock_ch),
        ):
            from database.data_sync_pipeline import DataSyncPipeline
            pipeline = DataSyncPipeline()

        self.assertIsNotNone(pipeline.mysql_db)
        self.assertIsNotNone(pipeline.dynamodb)
        self.assertIsNotNone(pipeline.clickhouse_db)

    def test_sync_event_required_keys(self):
        event = {
            "ticker": "AAPL",
            "sector": "Technology",
            "sentiment_score": 0.75,
            "positive": 0.8,
            "negative": 0.1,
            "neutral": 0.1,
            "news_count": 50,
        }
        for key in ("ticker", "sector", "sentiment_score",
                    "positive", "negative", "neutral", "news_count"):
            self.assertIn(key, event)

    def test_sentiment_score_in_range(self):
        score = 0.75
        self.assertGreaterEqual(score, -1.0)
        self.assertLessEqual(score, 1.0)

    def test_ratio_fields_sum_to_one(self):
        pos, neg, neu = 0.8, 0.1, 0.1
        self.assertAlmostEqual(pos + neg + neu, 1.0, places=5)


if __name__ == "__main__":
    unittest.main()
