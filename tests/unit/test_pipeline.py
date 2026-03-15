"""
Unit tests for the pipeline layer.

Covers:
- runner.run()  : orchestration with mocked scraper & analyzer
- PipelineResult: data integrity and field contracts
- Error resilience: empty news, partial failures
"""

import sys
import os
import unittest
from unittest.mock import patch, MagicMock
from datetime import date

import pandas as pd

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
_DS = os.path.join(os.path.dirname(__file__), "../../backend/services/data-service")
if _DS not in sys.path:
    sys.path.insert(0, _DS)


# ---------------------------------------------------------------------------
# Fixture factories
# ---------------------------------------------------------------------------

def _mean_df():
    """Simulates output of aggregate_recent() — uses 'Ticker' (capital T)."""
    return pd.DataFrame([
        {"Ticker": "AAPL", "compound": 0.8, "pos": 0.7, "neg": 0.1, "neu": 0.2},
        {"Ticker": "MSFT", "compound": -0.3, "pos": 0.2, "neg": 0.5, "neu": 0.3},
        {"Ticker": "GOOG", "compound": 0.1, "pos": 0.4, "neg": 0.3, "neu": 0.3},
    ])


def _sector_df():
    return pd.DataFrame([
        {"Ticker": "AAPL", "Security": "Apple Inc.", "Sector": "Information Technology"},
        {"Ticker": "MSFT", "Security": "Microsoft", "Sector": "Information Technology"},
        {"Ticker": "GOOG", "Security": "Alphabet Inc.", "Sector": "Communication Services"},
    ])


def _scored_df():
    today = str(date.today())
    return pd.DataFrame([
        {"ticker": "AAPL", "date": today, "time": "9AM", "headline": "Apple up",
         "compound": 0.8, "pos": 0.7, "neg": 0.1, "neu": 0.2},
        {"ticker": "MSFT", "date": today, "time": "10AM", "headline": "MSFT down",
         "compound": -0.3, "pos": 0.2, "neg": 0.5, "neu": 0.3},
    ])


# ---------------------------------------------------------------------------
# All mocks applied inside _run_with_mocks so each test is self-contained
# ---------------------------------------------------------------------------

def _run_with_mocks():
    with (
        patch("pipeline.runner.get_tickers",
              return_value=["AAPL", "MSFT", "GOOG"]) as m_tickers,
        patch("pipeline.runner.get_ticker_sector_df",
              return_value=_sector_df()) as m_sectors,
        patch("pipeline.runner.get_news_table",
              return_value={"AAPL": MagicMock(), "MSFT": MagicMock(),
                            "GOOG": MagicMock()}) as m_news,
        patch("pipeline.runner.parse_news_table",
              return_value=[
                  ["AAPL", "2024-12-01", "09:00AM", "Apple up"],
                  ["MSFT", "2024-12-01", "10:00AM", "MSFT down"],
              ]) as m_parse,
        patch("pipeline.runner.run_sentiment",
              return_value=_scored_df()) as m_sent,
        patch("pipeline.runner.aggregate_recent",
              return_value=_mean_df()) as m_agg,
    ):
        from pipeline.runner import run
        result = run(debug=True)
        return result, m_tickers, m_sectors, m_news, m_parse, m_sent, m_agg


# ===========================================================================
# PipelineResult contract
# ===========================================================================

class TestPipelineResult(unittest.TestCase):

    def setUp(self):
        from pipeline.runner import PipelineResult
        self.result = PipelineResult(
            all_stocks=[
                {"ticker": "AAPL", "sector": "Tech", "sentiment_score": 0.8,
                 "positive": 0.7, "negative": 0.1, "neutral": 0.2, "news_count": 5,
                 "timestamp": 1000},
                {"ticker": "MSFT", "sector": "Tech", "sentiment_score": -0.3,
                 "positive": 0.2, "negative": 0.5, "neutral": 0.3, "news_count": 3,
                 "timestamp": 1000},
                {"ticker": "GOOG", "sector": "Comms", "sentiment_score": 0.1,
                 "positive": 0.4, "negative": 0.3, "neutral": 0.3, "news_count": 2,
                 "timestamp": 1000},
            ],
            top_5=[{"ticker": "AAPL", "sentiment_score": 0.8}],
            low_5=[{"ticker": "MSFT", "sentiment_score": -0.3}],
            total_stocks=3,
            elapsed_seconds=12.5,
            timestamp=1000,
        )

    def test_has_all_stocks_attribute(self):
        self.assertTrue(hasattr(self.result, "all_stocks"))
        self.assertIsInstance(self.result.all_stocks, list)

    def test_has_top_5_and_low_5(self):
        self.assertTrue(hasattr(self.result, "top_5"))
        self.assertTrue(hasattr(self.result, "low_5"))

    def test_has_total_stocks(self):
        self.assertEqual(self.result.total_stocks, 3)

    def test_has_elapsed_seconds(self):
        self.assertIsInstance(self.result.elapsed_seconds, float)

    def test_has_timestamp(self):
        self.assertIsInstance(self.result.timestamp, int)

    def test_all_stocks_have_required_keys(self):
        for stock in self.result.all_stocks:
            for key in ("ticker", "sector", "sentiment_score",
                        "positive", "negative", "neutral", "news_count"):
                self.assertIn(key, stock, f"Missing key '{key}' in stock {stock}")

    def test_sentiment_score_in_range(self):
        for stock in self.result.all_stocks:
            self.assertGreaterEqual(stock["sentiment_score"], -1.0)
            self.assertLessEqual(stock["sentiment_score"], 1.0)


# ===========================================================================
# runner.run() orchestration
# ===========================================================================

class TestPipelineRunner(unittest.TestCase):

    def test_run_returns_pipeline_result(self):
        from pipeline.runner import PipelineResult
        result, *_ = _run_with_mocks()
        self.assertIsInstance(result, PipelineResult)

    def test_run_calls_all_sub_layers(self):
        result, tickers, sectors, news, parse, sent, agg = _run_with_mocks()
        tickers.assert_called_once()
        sectors.assert_called_once()
        news.assert_called_once()
        parse.assert_called_once()
        sent.assert_called_once()
        agg.assert_called_once()

    def test_run_passes_known_tickers_to_parse(self):
        """parse_news_table must receive the full ticker list for cross-detection."""
        result, _, _, _, parse, *_ = _run_with_mocks()
        args, kwargs = parse.call_args
        # known_tickers is the second positional argument
        known = kwargs.get("known_tickers") or (args[1] if len(args) > 1 else None)
        self.assertIsNotNone(known)
        self.assertIn("AAPL", known)

    def test_run_result_has_all_stocks(self):
        result, *_ = _run_with_mocks()
        self.assertIsInstance(result.all_stocks, list)

    def test_run_result_total_stocks(self):
        result, *_ = _run_with_mocks()
        self.assertEqual(result.total_stocks, len(result.all_stocks))

    def test_run_result_has_timestamp(self):
        result, *_ = _run_with_mocks()
        self.assertGreater(result.timestamp, 0)

    def test_run_result_has_elapsed_seconds(self):
        result, *_ = _run_with_mocks()
        self.assertGreaterEqual(result.elapsed_seconds, 0.0)

    def test_run_debug_mode_calls_get_tickers_with_debug_true(self):
        """
        In debug mode, run() must pass debug=True to get_tickers so that
        the Wikipedia scraper limits its output to ≤50 symbols.
        """
        with (
            patch("pipeline.runner.get_tickers",
                  return_value=["AAPL", "MSFT"]) as mock_tickers,
            patch("pipeline.runner.get_ticker_sector_df",
                  return_value=pd.DataFrame(
                      columns=["Ticker", "Security", "Sector"])),
            patch("pipeline.runner.get_news_table", return_value={}),
            patch("pipeline.runner.parse_news_table", return_value=[]),
            patch("pipeline.runner.run_sentiment",
                  return_value=pd.DataFrame(
                      columns=["ticker","date","compound","pos","neg","neu","headline"])),
            patch("pipeline.runner.aggregate_recent",
                  return_value=pd.DataFrame(
                      columns=["Ticker","compound","pos","neg","neu"])),
        ):
            from pipeline.runner import run
            run(debug=True)
            mock_tickers.assert_called_once_with(debug=True)

    def test_run_handles_empty_news_gracefully(self):
        """Pipeline must not raise even when all news tables are empty."""
        with (
            patch("pipeline.runner.get_tickers", return_value=["AAPL"]),
            patch("pipeline.runner.get_ticker_sector_df",
                  return_value=_sector_df()),
            patch("pipeline.runner.get_news_table", return_value={}),
            patch("pipeline.runner.parse_news_table", return_value=[]),
            patch("pipeline.runner.run_sentiment",
                  return_value=pd.DataFrame(
                      columns=["ticker","date","compound","pos","neg","neu","headline"])),
            patch("pipeline.runner.aggregate_recent",
                  return_value=pd.DataFrame(
                      columns=["Ticker","compound","pos","neg","neu"])),
        ):
            from pipeline.runner import run
            try:
                result = run(debug=True)
            except Exception as exc:
                self.fail(f"run() raised unexpectedly: {exc}")

    def test_all_stocks_sorted_descending_by_sentiment(self):
        """all_stocks in the result must be sorted highest→lowest sentiment."""
        result, *_ = _run_with_mocks()
        scores = [s["sentiment_score"] for s in result.all_stocks]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_top_5_are_highest_sentiment(self):
        result, *_ = _run_with_mocks()
        if result.top_5 and result.all_stocks:
            best = result.all_stocks[0]["sentiment_score"]
            self.assertEqual(result.top_5[0]["sentiment_score"], best)

    def test_low_5_are_lowest_sentiment(self):
        result, *_ = _run_with_mocks()
        if result.low_5 and result.all_stocks:
            worst = sorted(result.all_stocks, key=lambda x: x["sentiment_score"])[0]
            self.assertEqual(result.low_5[0]["sentiment_score"], worst["sentiment_score"])


if __name__ == "__main__":
    unittest.main()
