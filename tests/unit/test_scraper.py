"""
Unit tests for the scraper layer.

Covers:
- robots.py  : robots.txt caching and can_fetch logic
- wikipedia.py: ticker fetching, structural validation, fallback
- finviz.py  : fast/slow lane, exponential backoff, robots enforcement
- parser.py  : HTML parsing, date inheritance, cross-ticker detection
"""

import sys
import os
import unittest
from unittest.mock import MagicMock, patch, call
from datetime import datetime

import pandas as pd
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Path setup — let Python find the data-service package
# ---------------------------------------------------------------------------
_DS = os.path.join(os.path.dirname(__file__), "../../backend/services/data-service")
if _DS not in sys.path:
    sys.path.insert(0, _DS)


# ===========================================================================
# robots.py
# ===========================================================================

class TestRobots(unittest.TestCase):
    """robots.txt caching and can_fetch."""

    def setUp(self):
        import scraper.robots as rb
        rb._cache.clear()

    def test_can_fetch_returns_true_when_read_raises(self):
        """If robots.txt fetch throws, we assume allowed (fail-open)."""
        import scraper.robots as rb
        rb._cache.clear()
        with patch("scraper.robots.robotparser.RobotFileParser") as MockParser:
            inst = MockParser.return_value
            inst.read.side_effect = OSError("timeout")
            result = rb.can_fetch("https://example.com/robots.txt", "TestAgent", "/path")
        self.assertTrue(result)

    def test_can_fetch_respects_disallow(self):
        import scraper.robots as rb
        rb._cache.clear()
        with patch("scraper.robots.robotparser.RobotFileParser") as MockParser:
            inst = MockParser.return_value
            inst.read.return_value = None
            inst.can_fetch.return_value = False
            result = rb.can_fetch("https://example.com/robots.txt", "Agent", "/secret")
        self.assertFalse(result)

    def test_parser_is_cached_after_first_call(self):
        """The RobotFileParser should only be instantiated once per URL."""
        import scraper.robots as rb
        rb._cache.clear()
        with patch("scraper.robots.robotparser.RobotFileParser") as MockParser:
            inst = MockParser.return_value
            inst.read.return_value = None
            inst.can_fetch.return_value = True
            rb.can_fetch("https://x.com/robots.txt", "A", "/a")
            rb.can_fetch("https://x.com/robots.txt", "A", "/b")
            self.assertEqual(MockParser.call_count, 1)


# ===========================================================================
# wikipedia.py
# ===========================================================================

class TestWikipediaScraper(unittest.TestCase):
    """get_tickers() and get_ticker_sector_df()."""

    @staticmethod
    def _make_wiki_html():
        # pd.read_html requires a proper <table> with <th> column headers that
        # include both "Symbol" and a "sector" keyword so _find_sp500_table() matches.
        return """
        <html><body>
        <table class="wikitable sortable">
          <tr>
            <th>Symbol</th><th>Security</th><th>GICS Sector</th>
            <th>GICS Sub-Industry</th><th>Headquarters Location</th>
            <th>Date added</th><th>CIK</th><th>Founded</th>
          </tr>
          <tr><td>AAPL</td><td>Apple</td><td>Information Technology</td>
              <td>-</td><td>-</td><td>-</td><td>-</td><td>-</td></tr>
          <tr><td>MSFT</td><td>Microsoft</td><td>Information Technology</td>
              <td>-</td><td>-</td><td>-</td><td>-</td><td>-</td></tr>
          <tr><td>BRK.B</td><td>Berkshire</td><td>Financials</td>
              <td>-</td><td>-</td><td>-</td><td>-</td><td>-</td></tr>
        </table>
        </body></html>
        """

    def _mock_response(self, html: str, status: int = 200):
        resp = MagicMock()
        resp.status_code = status
        resp.text = html
        resp.raise_for_status.return_value = None
        return resp

    @patch("scraper.wikipedia.can_fetch", return_value=True)
    @patch("scraper.wikipedia._find_sp500_table")
    def test_get_tickers_returns_valid_symbols(self, mock_find, _):
        """_find_sp500_table returns a DataFrame — tickers are extracted from it."""
        import pandas as pd
        mock_find.return_value = pd.DataFrame({
            "Symbol": ["AAPL", "MSFT", "BRK.B"],
            "Security": ["Apple", "Microsoft", "Berkshire"],
            "GICS Sector": ["IT", "IT", "Financials"],
        })
        # Also patch the session so no real HTTP call happens
        with patch("scraper.wikipedia.requests.Session") as MockSession:
            session_inst = MockSession.return_value
            session_inst.get.return_value = self._mock_response(self._make_wiki_html())
            from scraper.wikipedia import get_tickers
            tickers = get_tickers(debug=False)

        self.assertIn("AAPL", tickers)
        self.assertIn("MSFT", tickers)
        self.assertIn("BRK.B", tickers)

    @patch("scraper.wikipedia.can_fetch", return_value=True)
    @patch("scraper.wikipedia.requests.Session")
    def test_get_tickers_debug_limits_to_50(self, MockSession, _):
        # Generate 100 tickers in the HTML
        rows = "\n".join(
            f"<tr><td>T{i:04d}</td><td>Name{i}</td><td>Sector</td></tr>"
            for i in range(100)
        )
        html = f"""
        <html><body>
        <table class="wikitable sortable">
          <thead><tr><th>Symbol</th><th>Security</th><th>GICS Sector</th></tr></thead>
          <tbody>{rows}</tbody>
        </table>
        </body></html>
        """
        session_inst = MockSession.return_value
        session_inst.get.return_value = self._mock_response(html)

        from scraper.wikipedia import get_tickers
        tickers = get_tickers(debug=True)
        self.assertLessEqual(len(tickers), 50)

    @patch("scraper.wikipedia.can_fetch", return_value=False)
    def test_get_tickers_falls_back_when_robots_blocks(self, _):
        from scraper.wikipedia import get_tickers, _FALLBACK_TICKERS
        tickers = get_tickers()
        self.assertEqual(tickers, list(_FALLBACK_TICKERS))

    @patch("scraper.wikipedia.can_fetch", return_value=True)
    @patch("scraper.wikipedia.requests.Session")
    def test_get_tickers_falls_back_on_http_error(self, MockSession, _):
        resp = self._mock_response("", status=503)
        resp.raise_for_status.side_effect = Exception("503")
        session_inst = MockSession.return_value
        session_inst.get.return_value = resp

        from scraper.wikipedia import get_tickers, _FALLBACK_TICKERS
        tickers = get_tickers()
        self.assertEqual(tickers, list(_FALLBACK_TICKERS))

    @patch("scraper.wikipedia.can_fetch", return_value=True)
    @patch("scraper.wikipedia.requests.Session")
    def test_ticker_regex_filters_invalid_symbols(self, MockSession, _):
        """Numbers, empty strings, or >5-char symbols must be filtered out."""
        bad_html = """
        <html><body>
        <table class="wikitable sortable">
          <thead><tr><th>Symbol</th><th>Security</th><th>GICS Sector</th></tr></thead>
          <tbody>
            <tr><td>AAPL</td><td>Apple</td><td>Tech</td></tr>
            <tr><td>123</td><td>Bad</td><td>Bad</td></tr>
            <tr><td></td><td>Empty</td><td>Empty</td></tr>
            <tr><td>TOOLONG</td><td>Too Long</td><td>Bad</td></tr>
          </tbody>
        </table>
        </body></html>
        """
        session_inst = MockSession.return_value
        session_inst.get.return_value = self._mock_response(bad_html)

        from scraper.wikipedia import get_tickers
        tickers = get_tickers()
        self.assertIn("AAPL", tickers)
        self.assertNotIn("123", tickers)
        self.assertNotIn("TOOLONG", tickers)

    @patch("scraper.wikipedia.can_fetch", return_value=True)
    @patch("scraper.wikipedia.requests.Session")
    def test_get_ticker_sector_df_returns_dataframe(self, MockSession, _):
        session_inst = MockSession.return_value
        session_inst.get.return_value = self._mock_response(self._make_wiki_html())

        from scraper.wikipedia import get_ticker_sector_df
        df = get_ticker_sector_df()
        self.assertIsInstance(df, pd.DataFrame)
        self.assertIn("Ticker", df.columns)
        self.assertIn("Sector", df.columns)

    @patch("scraper.wikipedia.can_fetch", return_value=True)
    @patch("scraper.wikipedia.requests.Session")
    def test_get_ticker_sector_df_falls_back_on_error(self, MockSession, _):
        session_inst = MockSession.return_value
        session_inst.get.side_effect = Exception("network error")

        from scraper.wikipedia import get_ticker_sector_df
        df = get_ticker_sector_df()
        self.assertIsInstance(df, pd.DataFrame)
        self.assertTrue(df.empty)


# ===========================================================================
# finviz.py
# ===========================================================================

class TestFinvizFetchNewsTable(unittest.TestCase):
    """_fetch_news_table: exponential backoff, robots, success path."""

    @staticmethod
    def _news_html():
        return """
        <html><body>
        <table id="news-table">
          <tr>
            <td>Dec-01-24 09:00AM</td>
            <td><a href="#">Apple reports earnings</a></td>
          </tr>
        </table>
        </body></html>
        """.encode()

    @patch("scraper.finviz.can_fetch", return_value=True)
    @patch("scraper.finviz.np.random.uniform", return_value=0.0)
    @patch("scraper.finviz.time.sleep")
    @patch("scraper.finviz.urlopen")
    def test_success_returns_ticker_and_table(self, mock_urlopen, mock_sleep, *_):
        """On successful fetch, returns (ticker, BeautifulSoup tag)."""
        cm = MagicMock()
        cm.__enter__ = lambda s: MagicMock(read=lambda: self._news_html())
        cm.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = cm

        from scraper.finviz import _fetch_news_table
        ticker, table = _fetch_news_table("AAPL", fast=True)
        self.assertEqual(ticker, "AAPL")
        # table can be None (no news-table id in our minimal mock) or a tag

    @patch("scraper.finviz.can_fetch", return_value=True)
    @patch("scraper.finviz.np.random.uniform", return_value=0.0)
    @patch("scraper.finviz.time.sleep")
    @patch("scraper.finviz.urlopen")
    def test_http_429_exhausts_fast_backoffs(self, mock_urlopen, mock_sleep, *_):
        """
        HTTP 429 must trigger a sleep for each BACKOFFS_FAST entry.
        After exhaustion the function returns (ticker, None).
        """
        from urllib.error import HTTPError
        from scraper.finviz import BACKOFFS_FAST, _fetch_news_table

        mock_urlopen.side_effect = HTTPError(
            url="http://x", code=429, msg="Too Many", hdrs={}, fp=None
        )

        ticker, table = _fetch_news_table("MSFT", fast=True)

        self.assertEqual(ticker, "MSFT")
        self.assertIsNone(table)

        # sleep was called at least len(BACKOFFS_FAST) times with the backoff values
        sleep_args = [c.args[0] for c in mock_sleep.call_args_list]
        for expected in BACKOFFS_FAST:
            self.assertIn(expected, sleep_args)

    @patch("scraper.finviz.can_fetch", return_value=True)
    @patch("scraper.finviz.np.random.uniform", return_value=0.0)
    @patch("scraper.finviz.time.sleep")
    @patch("scraper.finviz.urlopen")
    def test_slow_lane_uses_longer_backoffs(self, mock_urlopen, mock_sleep, *_):
        from urllib.error import HTTPError
        from scraper.finviz import BACKOFFS_SLOW, _fetch_news_table

        mock_urlopen.side_effect = HTTPError(
            url="", code=429, msg="", hdrs={}, fp=None
        )

        _fetch_news_table("JPM", fast=False)

        sleep_args = [c.args[0] for c in mock_sleep.call_args_list]
        for expected in BACKOFFS_SLOW:
            self.assertIn(expected, sleep_args)

    @patch("scraper.finviz.can_fetch", return_value=False)
    def test_robots_blocks_returns_none_immediately(self, _):
        """robots.txt disallow → return (ticker, None) without network call."""
        with patch("scraper.finviz.urlopen") as mock_urlopen:
            from scraper.finviz import _fetch_news_table
            ticker, table = _fetch_news_table("TSLA", fast=True)

        self.assertEqual(ticker, "TSLA")
        self.assertIsNone(table)
        mock_urlopen.assert_not_called()

    @patch("scraper.finviz.can_fetch", return_value=True)
    @patch("scraper.finviz.np.random.uniform", return_value=0.0)
    @patch("scraper.finviz.time.sleep")
    @patch("scraper.finviz.urlopen")
    def test_network_error_exhausts_backoffs(self, mock_urlopen, mock_sleep, *_):
        """URLError must also trigger the full backoff sequence."""
        from urllib.error import URLError
        from scraper.finviz import BACKOFFS_FAST, _fetch_news_table

        mock_urlopen.side_effect = URLError("connection refused")

        ticker, table = _fetch_news_table("GOOG", fast=True)
        self.assertIsNone(table)
        sleep_args = [c.args[0] for c in mock_sleep.call_args_list]
        for expected in BACKOFFS_FAST:
            self.assertIn(expected, sleep_args)


class TestFinvizGetNewsTable(unittest.TestCase):
    """get_news_table: two-lane orchestration."""

    @patch("scraper.finviz.np.random.uniform", return_value=0.0)
    @patch("scraper.finviz.time.sleep")
    @patch("scraper.finviz._process_ticker")
    def test_all_succeed_in_fast_lane(self, mock_proc, *_):
        """No slow lane invocation when every ticker succeeds."""
        mock_proc.side_effect = lambda idx, ticker, fast: (ticker, MagicMock())

        with patch("scraper.finviz._slow_lane") as mock_slow:
            from scraper.finviz import get_news_table
            tables = get_news_table(["AAPL", "MSFT"])

        mock_slow.assert_not_called()
        self.assertEqual(len(tables), 2)

    @patch("scraper.finviz.np.random.uniform", return_value=0.0)
    @patch("scraper.finviz.time.sleep")
    @patch("scraper.finviz._process_ticker")
    def test_failures_forwarded_to_slow_lane(self, mock_proc, *_):
        """Tickers that return None in fast lane must be passed to _slow_lane."""
        def side(idx, ticker, fast):
            return (ticker, None) if ticker == "FAIL" else (ticker, MagicMock())

        mock_proc.side_effect = side

        with patch("scraper.finviz._slow_lane") as mock_slow:
            from scraper.finviz import get_news_table
            get_news_table(["OK", "FAIL"])

        mock_slow.assert_called_once()
        failed_list = mock_slow.call_args[0][0]
        self.assertIn("FAIL", failed_list)
        self.assertNotIn("OK", failed_list)

    @patch("scraper.finviz.np.random.uniform", return_value=0.0)
    @patch("scraper.finviz.time.sleep")
    @patch("scraper.finviz._process_ticker")
    def test_success_rate_reported(self, mock_proc, *_):
        """Success rate logging — all 3 tickers succeed."""
        mock_proc.side_effect = lambda idx, ticker, fast: (ticker, MagicMock())
        from scraper.finviz import get_news_table
        result = get_news_table(["A", "B", "C"])
        self.assertEqual(len(result), 3)


# ===========================================================================
# parser.py
# ===========================================================================

class TestNewsParser(unittest.TestCase):
    """parse_news_table: date inheritance, cross-ticker, None tables."""

    @staticmethod
    def _build_table(rows):
        """
        rows: list of (date_cell_text, headline_text)
        Returns a BeautifulSoup tag representing a <table id="news-table">.
        """
        trs = ""
        for date_txt, headline in rows:
            trs += f"""
            <tr>
              <td>{date_txt}</td>
              <td><a href="#">{headline}</a></td>
            </tr>
            """
        html = f'<table id="news-table">{trs}</table>'
        return BeautifulSoup(html, "html.parser").find("table")

    def test_basic_parsing(self):
        table = self._build_table([("Dec-01-24 09:00AM", "Apple up 5%")])
        from scraper.parser import parse_news_table
        records = parse_news_table({"AAPL": table})
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0][0], "AAPL")
        self.assertEqual(records[0][3], "Apple up 5%")

    def test_date_and_time_extracted(self):
        table = self._build_table([("Dec-01-24 09:00AM", "First headline")])
        from scraper.parser import parse_news_table
        records = parse_news_table({"AAPL": table})
        self.assertEqual(records[0][1], "Dec-01-24")
        self.assertEqual(records[0][2], "09:00AM")

    def test_date_inheritance_when_only_time_present(self):
        """
        Finviz omits the date for same-day subsequent headlines.
        The parser must inherit the date from the previous record.
        """
        table = self._build_table([
            ("Dec-01-24 09:00AM", "First headline"),
            ("10:30AM", "Second same-day headline"),
        ])
        from scraper.parser import parse_news_table
        records = parse_news_table({"AAPL": table})
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0][1], records[1][1])  # same date

    def test_none_table_is_skipped(self):
        from scraper.parser import parse_news_table
        records = parse_news_table({"FAIL": None})
        self.assertEqual(records, [])

    def test_cross_ticker_detection(self):
        """
        Headline mentioning another known S&P 500 ticker must generate
        an extra record attributed to that ticker (MSFT in this case).
        """
        table = self._build_table([
            ("Dec-01-24 09:00AM", "AAPL and MSFT announce partnership"),
        ])
        from scraper.parser import parse_news_table
        records = parse_news_table({"AAPL": table}, known_tickers=["AAPL", "MSFT"])
        tickers = {r[0] for r in records}
        self.assertIn("AAPL", tickers)
        self.assertIn("MSFT", tickers)

    def test_cross_ticker_excludes_primary_duplicate(self):
        """Primary ticker must not be double-counted via cross-detection."""
        table = self._build_table([
            ("Dec-01-24 09:00AM", "AAPL AAPL strong buy"),
        ])
        from scraper.parser import parse_news_table
        records = parse_news_table({"AAPL": table}, known_tickers=["AAPL"])
        aapl_records = [r for r in records if r[0] == "AAPL"]
        self.assertEqual(len(aapl_records), 1)

    def test_mixed_valid_and_none_tables(self):
        table = self._build_table([("Dec-01-24 09:00AM", "Test")])
        from scraper.parser import parse_news_table
        records = parse_news_table({"AAPL": table, "FAIL": None})
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0][0], "AAPL")

    def test_no_cross_detection_when_no_known_tickers(self):
        """Without known_tickers, no cross attribution should occur."""
        table = self._build_table([
            ("Dec-01-24 09:00AM", "AAPL MSFT GOOG joint news"),
        ])
        from scraper.parser import parse_news_table
        records = parse_news_table({"AAPL": table})
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0][0], "AAPL")

    def test_ticker_uppercased_in_output(self):
        """Tickers in output must always be upper-case."""
        table = self._build_table([("Dec-01-24 09:00AM", "Test")])
        from scraper.parser import parse_news_table
        records = parse_news_table({"aapl": table})
        self.assertEqual(records[0][0], "AAPL")


if __name__ == "__main__":
    unittest.main()
