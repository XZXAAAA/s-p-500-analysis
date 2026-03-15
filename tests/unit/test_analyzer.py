"""
Unit tests for the analyzer layer.

Covers:
- engines.py  : OpenAI-only sentiment; output shape, ranges, and error when API missing/fails
- sentiment.py: run_sentiment() DataFrame output (with mocked engine)
- aggregation.py: aggregate_recent() date filtering and mean computation
"""

import json
import sys
import os
import unittest
from unittest.mock import patch, MagicMock
from datetime import date, timedelta

import pandas as pd

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
_DS = os.path.join(os.path.dirname(__file__), "../../backend/services/data-service")
if _DS not in sys.path:
    sys.path.insert(0, _DS)


# ===========================================================================
# engines.py — OpenAI-only
# ===========================================================================

class TestOpenAIEngine(unittest.TestCase):
    """
    Validate engines.analyze() when OpenAI client is mocked.
    Output contract: neg, neu, pos in [0,1] (sum ≈ 1), compound in [-1, 1].
    """

    def _make_ai_response(self, content: str):
        mock_choice = MagicMock()
        mock_choice.message.content = content
        mock_resp = MagicMock()
        mock_resp.choices = [mock_choice]
        return mock_resp

    def test_successful_call_returns_parsed_scores(self):
        """Valid JSON from API returns neg/neu/pos/compound with correct ranges."""
        import analyzer.engines as eng

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = self._make_ai_response(
            '{"neg": 0.05, "neu": 0.60, "pos": 0.35, "compound": 0.42}'
        )

        with (
            patch.object(eng, "_ai_client", mock_client),
            patch.object(eng, "_ai_mode", "v1"),
        ):
            result = eng.analyze("Apple beats earnings estimates")

        self.assertAlmostEqual(result["compound"], 0.42)
        for key in ("neg", "neu", "pos", "compound"):
            self.assertIn(key, result)
        self.assertGreaterEqual(result["compound"], -1.0)
        self.assertLessEqual(result["compound"], 1.0)
        total = result["neg"] + result["neu"] + result["pos"]
        self.assertAlmostEqual(total, 1.0, places=4)

    def test_all_keys_present(self):
        import analyzer.engines as eng

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = self._make_ai_response(
            '{"neg": 0.2, "neu": 0.6, "pos": 0.2, "compound": 0.0}'
        )

        with (
            patch.object(eng, "_ai_client", mock_client),
            patch.object(eng, "_ai_mode", "v1"),
        ):
            result = eng.analyze("Test sentence")
        for key in ("neg", "neu", "pos", "compound"):
            self.assertIn(key, result)

    def test_neg_neu_pos_normalized_to_sum_one(self):
        import analyzer.engines as eng

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = self._make_ai_response(
            '{"neg": 0.1, "neu": 0.5, "pos": 0.3, "compound": 0.2}'
        )

        with (
            patch.object(eng, "_ai_client", mock_client),
            patch.object(eng, "_ai_mode", "v1"),
        ):
            result = eng.analyze("Mixed signals")
        total = result["neg"] + result["neu"] + result["pos"]
        self.assertAlmostEqual(total, 1.0, places=4)

    def test_invalid_json_raises(self):
        """Malformed JSON from API raises; no fallback."""
        import analyzer.engines as eng

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = self._make_ai_response(
            "not valid json {{"
        )

        with (
            patch.object(eng, "_ai_client", mock_client),
            patch.object(eng, "_ai_mode", "v1"),
        ):
            with self.assertRaises((ValueError, json.JSONDecodeError)):
                eng.analyze("Apple reports strong quarter")

    def test_api_exception_propagates(self):
        """OpenAI client exception propagates to caller."""
        import analyzer.engines as eng

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = RuntimeError("API down")

        with (
            patch.object(eng, "_ai_client", mock_client),
            patch.object(eng, "_ai_mode", "v1"),
        ):
            with self.assertRaises(RuntimeError):
                eng.analyze("Test headline")

    def test_compound_out_of_range_raises(self):
        """Score outside [-1, 1] raises ValueError."""
        import analyzer.engines as eng

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = self._make_ai_response(
            '{"neg": 0.0, "neu": 0.0, "pos": 0.0, "compound": 99.9}'
        )

        with (
            patch.object(eng, "_ai_client", mock_client),
            patch.object(eng, "_ai_mode", "v1"),
        ):
            with self.assertRaises(ValueError):
                eng.analyze("test")

    def test_no_ai_client_raises(self):
        """If _ai_client is None, analyze() raises RuntimeError."""
        import analyzer.engines as eng

        with patch.object(eng, "_ai_client", None), patch.object(eng, "_ai_mode", None):
            with self.assertRaises(RuntimeError):
                eng.analyze("Markets are up today")


# ===========================================================================
# sentiment.py
# ===========================================================================

def _fake_analyze(_text):
    """Real callable returning a dict so pandas apply works as in production."""
    return {"neg": 0.1, "neu": 0.7, "pos": 0.2, "compound": 0.3}


class TestRunSentiment(unittest.TestCase):
    """run_sentiment() applies engine to every headline row. Uses mocked analyze()."""

    def _records(self):
        return [
            ("AAPL", "2024-12-01", "09:00AM", "Apple surges on strong earnings"),
            ("MSFT", "2024-12-01", "10:00AM", "Microsoft cloud revenue disappoints"),
        ]

    @patch("analyzer.sentiment.analyze", _fake_analyze)
    def test_output_has_required_columns(self):
        from analyzer.sentiment import run_sentiment
        records = self._records()
        df = run_sentiment(records)
        for col in ("ticker", "date", "time", "headline", "neg", "neu", "pos", "compound"):
            self.assertIn(col, df.columns)

    @patch("analyzer.sentiment.analyze", _fake_analyze)
    def test_row_count_matches_input(self):
        from analyzer.sentiment import run_sentiment
        records = self._records()
        df = run_sentiment(records)
        self.assertEqual(len(df), len(records))

    def test_compound_values_in_range(self):
        outcomes = iter([
            {"neg": 0.1, "neu": 0.7, "pos": 0.2, "compound": 0.5},
            {"neg": 0.6, "neu": 0.3, "pos": 0.1, "compound": -0.4},
        ])

        def fake_analyze_two(_text):
            return next(outcomes)

        with patch("analyzer.sentiment.analyze", fake_analyze_two):
            from analyzer.sentiment import run_sentiment
            df = run_sentiment(self._records())
        self.assertTrue((df["compound"] >= -1.0).all())
        self.assertTrue((df["compound"] <= 1.0).all())

    def test_empty_records_returns_empty_dataframe(self):
        from analyzer.sentiment import run_sentiment
        df = run_sentiment([])
        self.assertIsInstance(df, pd.DataFrame)
        self.assertTrue(df.empty)


# ===========================================================================
# aggregation.py
# ===========================================================================

class TestAggregateRecent(unittest.TestCase):
    """
    aggregate_recent() filters by date window and computes per-ticker means.
    """

    def _scored_df(self):
        today = pd.Timestamp(date.today())
        old = today - timedelta(days=30)
        return pd.DataFrame([
            {"ticker": "AAPL", "date": today,
             "compound": 0.8, "pos": 0.7, "neg": 0.1, "neu": 0.2,
             "headline": "h1", "time": "9AM"},
            {"ticker": "AAPL", "date": today,
             "compound": 0.6, "pos": 0.6, "neg": 0.2, "neu": 0.2,
             "headline": "h2", "time": "10AM"},
            {"ticker": "MSFT", "date": today,
             "compound": -0.4, "pos": 0.2, "neg": 0.6, "neu": 0.2,
             "headline": "h3", "time": "11AM"},
            {"ticker": "AAPL", "date": old,
             "compound": 0.1, "pos": 0.3, "neg": 0.3, "neu": 0.4,
             "headline": "old", "time": "8AM"},
        ])

    def test_aggregate_produces_mean_compound(self):
        from analyzer.aggregation import aggregate_recent
        df = aggregate_recent(self._scored_df(), days=7)
        aapl = df[df["Ticker"] == "AAPL"]
        self.assertEqual(len(aapl), 1)
        self.assertAlmostEqual(float(aapl["compound"].iloc[0]), 0.7, places=5)

    def test_old_records_excluded_with_days_1(self):
        from analyzer.aggregation import aggregate_recent
        df = aggregate_recent(self._scored_df(), days=1)
        aapl = df[df["Ticker"] == "AAPL"]
        self.assertAlmostEqual(float(aapl["compound"].iloc[0]), 0.7, places=5)

    def test_ticker_column_is_capital_t(self):
        from analyzer.aggregation import aggregate_recent
        df = aggregate_recent(self._scored_df(), days=7)
        self.assertIn("Ticker", df.columns)

    def test_scores_present_in_output(self):
        from analyzer.aggregation import aggregate_recent
        df = aggregate_recent(self._scored_df(), days=7)
        for col in ("compound", "neg", "neu", "pos"):
            self.assertIn(col, df.columns)

    def test_empty_dataframe_returns_empty(self):
        from analyzer.aggregation import aggregate_recent
        empty = pd.DataFrame(columns=["ticker", "date", "compound", "pos", "neg", "neu"])
        result = aggregate_recent(empty, days=7)
        self.assertIsInstance(result, pd.DataFrame)
        self.assertTrue(result.empty)


if __name__ == "__main__":
    unittest.main()
