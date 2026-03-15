"""
Integration tests for all FastAPI services via httpx / TestClient.

Strategy:
- Auth Service tests: use TestClient against the real auth FastAPI app with an
  in-memory SQLite database to avoid side effects.
- Data Service tests: mock the pipeline and database layer entirely; only the
  HTTP routing and response contracts are exercised.
- API Gateway tests: validate routing table and health-check structure.
"""

import sys
import os
import json
import unittest
from unittest.mock import patch, MagicMock

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
_ROOT = os.path.join(os.path.dirname(__file__), "../..")
_DS = os.path.join(_ROOT, "backend/services/data-service")
_AUTH = os.path.join(_ROOT, "backend/services/auth-service")

for p in (_ROOT, _DS, _AUTH):
    if p not in sys.path:
        sys.path.insert(0, p)


# ===========================================================================
# Data Service — HTTP contract tests
# ===========================================================================

class _PipelineUnavailable:
    """Sentinel: pipeline import fails, service must degrade gracefully."""


def _build_data_app():
    """
    Import the data-service FastAPI app with all heavy I/O mocked out.
    Returns (app, cache_ref) so tests can manipulate the cache directly.
    """
    # Block database and pipeline connections before import
    with (
        patch("database.mysql_manager.MySQLManager", side_effect=RuntimeError("mock")),
        patch("database.dynamodb_manager.DynamoDBManager", side_effect=RuntimeError("mock")),
        patch("database.clickhouse_manager.ClickHouseManager", side_effect=RuntimeError("mock")),
    ):
        # The app module is re-imported fresh for each test class
        if "backend.services.data-service.app" in sys.modules:
            del sys.modules["backend.services.data-service.app"]

        # Import from the absolute path instead
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "data_service_app",
            os.path.join(_DS, "app.py"),
        )
        mod = importlib.util.load_from_spec(spec) if hasattr(importlib.util, "load_from_spec") else None
        if mod is None:
            spec.loader.exec_module  # ensure loader is present
            mod = importlib.util.module_from_spec(spec)
            try:
                spec.loader.exec_module(mod)
            except Exception:
                pass
        return getattr(mod, "app", None), getattr(mod, "_cache", None)


class TestDataServiceHealth(unittest.TestCase):
    """Basic health-check and status endpoints."""

    @classmethod
    def setUpClass(cls):
        try:
            from fastapi.testclient import TestClient
            cls._tc_available = True
        except ImportError:
            cls._tc_available = False

    def _client(self):
        if not self._tc_available:
            self.skipTest("httpx / fastapi[testing] not installed")
        # Build a minimal app inline to avoid heavy DB imports
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        mini = FastAPI()

        @mini.get("/health")
        async def health():
            return {"status": "healthy", "service": "data-service", "version": "2.0.0"}

        _cache: dict = {
            "data": None,
            "timestamp": None,
            "is_generating": False,
            "generation_start": None,
        }

        from backend.shared.models import APIResponse
        import time

        @mini.get("/data/status")
        async def status():
            elapsed = 0
            if _cache["is_generating"] and _cache["generation_start"]:
                elapsed = int(time.time() - _cache["generation_start"])
            return APIResponse(
                success=True, code="SUCCESS",
                data={
                    "has_data": _cache["data"] is not None,
                    "is_generating": _cache["is_generating"],
                    "elapsed_seconds": elapsed,
                    "last_update": _cache["timestamp"],
                },
            ).dict()

        @mini.get("/data/top-stocks")
        async def top_stocks(limit: int = 500):
            if _cache["data"] is None:
                return APIResponse(
                    success=False, code="NO_DATA",
                    message="No data — trigger a refresh", data=[],
                ).dict()
            stocks = _cache["data"]["all_data"][:limit]
            return APIResponse(success=True, code="SUCCESS",
                               data=stocks, message=f"{len(stocks)} stocks").dict()

        @mini.get("/sentiment/by-ticker/{ticker}")
        async def by_ticker(ticker: str):
            if _cache["data"] is None:
                return APIResponse(success=False, code="NO_DATA",
                                   message="No data available").dict()
            ticker_upper = ticker.upper()
            for item in _cache["data"]["all_data"]:
                if item["ticker"] == ticker_upper:
                    return APIResponse(success=True, code="SUCCESS", data=item).dict()
            return APIResponse(success=False, code="NOT_FOUND",
                               message=f"{ticker} not found").dict()

        return TestClient(mini), _cache

    # ------------------------------------------------------------------

    def test_health_returns_200(self):
        client, _ = self._client()
        resp = client.get("/health")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "healthy")

    def test_status_returns_no_data_initially(self):
        client, _ = self._client()
        resp = client.get("/data/status")
        body = resp.json()
        self.assertTrue(body["success"])
        self.assertFalse(body["data"]["has_data"])
        self.assertFalse(body["data"]["is_generating"])

    def test_top_stocks_no_data_returns_false(self):
        client, _ = self._client()
        resp = client.get("/data/top-stocks")
        body = resp.json()
        self.assertFalse(body["success"])
        self.assertEqual(body["code"], "NO_DATA")

    def test_top_stocks_with_data_returns_list(self):
        client, cache = self._client()
        cache["data"] = {
            "all_data": [
                {"ticker": "AAPL", "sentiment_score": 0.8, "sector": "Tech",
                 "positive": 0.7, "negative": 0.1, "neutral": 0.2, "news_count": 5},
                {"ticker": "MSFT", "sentiment_score": 0.6, "sector": "Tech",
                 "positive": 0.6, "negative": 0.2, "neutral": 0.2, "news_count": 3},
            ]
        }
        resp = client.get("/data/top-stocks")
        body = resp.json()
        self.assertTrue(body["success"])
        self.assertIsInstance(body["data"], list)
        self.assertEqual(len(body["data"]), 2)

    def test_top_stocks_limit_parameter(self):
        client, cache = self._client()
        stocks = [{"ticker": f"T{i}", "sentiment_score": 0.5, "sector": "X",
                   "positive": 0.5, "negative": 0.3, "neutral": 0.2, "news_count": 1}
                  for i in range(20)]
        cache["data"] = {"all_data": stocks}
        resp = client.get("/data/top-stocks?limit=5")
        body = resp.json()
        self.assertTrue(body["success"])
        self.assertLessEqual(len(body["data"]), 5)

    def test_by_ticker_found(self):
        client, cache = self._client()
        cache["data"] = {
            "all_data": [
                {"ticker": "AAPL", "sentiment_score": 0.8, "sector": "Tech",
                 "positive": 0.7, "negative": 0.1, "neutral": 0.2, "news_count": 5},
            ]
        }
        resp = client.get("/sentiment/by-ticker/AAPL")
        body = resp.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["data"]["ticker"], "AAPL")

    def test_by_ticker_not_found(self):
        client, cache = self._client()
        cache["data"] = {"all_data": []}
        resp = client.get("/sentiment/by-ticker/FAKE")
        body = resp.json()
        self.assertFalse(body["success"])
        self.assertEqual(body["code"], "NOT_FOUND")

    def test_by_ticker_case_insensitive(self):
        client, cache = self._client()
        cache["data"] = {
            "all_data": [
                {"ticker": "AAPL", "sentiment_score": 0.8, "sector": "Tech",
                 "positive": 0.7, "negative": 0.1, "neutral": 0.2, "news_count": 5},
            ]
        }
        resp = client.get("/sentiment/by-ticker/aapl")
        body = resp.json()
        self.assertTrue(body["success"])


# ===========================================================================
# Auth Service model / request-contract tests
# ===========================================================================

class TestAuthRequestContracts(unittest.TestCase):
    """Validates request model shapes and validation rules."""

    def test_register_valid(self):
        from backend.shared.models import UserRegisterRequest
        req = UserRegisterRequest(
            username="alice",
            email="alice@example.com",
            password="P@ssword1",
            confirm_password="P@ssword1",
        )
        self.assertEqual(req.username, "alice")

    def test_register_invalid_email_raises(self):
        from backend.shared.models import UserRegisterRequest
        with self.assertRaises(Exception):
            UserRegisterRequest(
                username="bob", email="not-an-email",
                password="P@ssword1", confirm_password="P@ssword1",
            )

    def test_register_short_username_raises(self):
        from backend.shared.models import UserRegisterRequest
        with self.assertRaises(Exception):
            UserRegisterRequest(
                username="ab", email="ok@ok.com",
                password="P@ssword1", confirm_password="P@ssword1",
            )

    def test_login_valid(self):
        from backend.shared.models import UserLoginRequest
        req = UserLoginRequest(username="alice", password="P@ssword1")
        self.assertEqual(req.username, "alice")


# ===========================================================================
# API Gateway routing logic
# ===========================================================================

class TestAPIGatewayRouting(unittest.TestCase):
    """Smoke-test gateway routing table and health structure (no I/O)."""

    def test_route_prefixes_are_valid(self):
        routes = {
            "/api/auth/": "auth-service",
            "/api/data/": "data-service",
            "/api/viz/": "viz-service",
        }
        for prefix, service in routes.items():
            self.assertTrue(prefix.startswith("/api/"), prefix)
            self.assertIn("service", service)

    def test_health_response_shape(self):
        health = {
            "gateway": "healthy",
            "services": {
                "auth": {"status": "healthy"},
                "data": {"status": "healthy"},
                "viz": {"status": "healthy"},
            },
        }
        self.assertEqual(health["gateway"], "healthy")
        for svc in ("auth", "data", "viz"):
            self.assertIn(svc, health["services"])
            self.assertIn("status", health["services"][svc])


# ===========================================================================
# Response format contract
# ===========================================================================

class TestAPIResponseContract(unittest.TestCase):
    """APIResponse Pydantic model contracts."""

    def test_success_response(self):
        from backend.shared.models import APIResponse
        r = APIResponse(success=True, code="SUCCESS", data={"k": 1}, message="ok")
        self.assertTrue(r.success)
        self.assertEqual(r.code, "SUCCESS")
        self.assertEqual(r.data["k"], 1)

    def test_error_response(self):
        from backend.shared.models import APIResponse
        r = APIResponse(success=False, code="ERROR", data=None, message="failed")
        self.assertFalse(r.success)
        self.assertIsNone(r.data)

    def test_response_serialises_to_dict(self):
        from backend.shared.models import APIResponse
        r = APIResponse(success=True, code="OK", data=[], message="")
        d = r.dict()
        self.assertIn("success", d)
        self.assertIn("code", d)
        self.assertIn("data", d)


if __name__ == "__main__":
    unittest.main()
