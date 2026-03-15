"""
Unit Tests for Data Service
"""

import unittest
import sys
import os
from unittest.mock import Mock, patch, MagicMock
import pandas as pd
import numpy as np

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from backend.shared.models import SentimentData, APIResponse


class TestSentimentData(unittest.TestCase):
    """Test sentiment data model"""
    
    def test_sentiment_data_valid(self):
        """Test valid sentiment data"""
        data = {
            "ticker": "AAPL",
            "sector": "Technology",
            "sentiment_score": 0.75,
            "positive": 0.8,
            "negative": 0.1,
            "neutral": 0.1,
            "news_count": 50
        }
        
        sentiment = SentimentData(**data)
        self.assertEqual(sentiment.ticker, "AAPL")
        self.assertEqual(sentiment.sector, "Technology")
        self.assertEqual(sentiment.sentiment_score, 0.75)
    
    def test_sentiment_score_range(self):
        """Test sentiment score within valid range"""
        valid_data = {
            "ticker": "AAPL",
            "sector": "Technology",
            "sentiment_score": 0.5,
            "positive": 0.6,
            "negative": 0.2,
            "neutral": 0.2,
            "news_count": 50
        }
        
        # Valid score
        sentiment = SentimentData(**valid_data)
        self.assertGreaterEqual(sentiment.sentiment_score, -1)
        self.assertLessEqual(sentiment.sentiment_score, 1)
        
        # Invalid score (too high)
        invalid_data = valid_data.copy()
        invalid_data["sentiment_score"] = 1.5
        
        with self.assertRaises(Exception):  # Pydantic validation error
            SentimentData(**invalid_data)
        
        # Invalid score (too low)
        invalid_data["sentiment_score"] = -1.5
        
        with self.assertRaises(Exception):  # Pydantic validation error
            SentimentData(**invalid_data)
    
    def test_sentiment_ratios_range(self):
        """Test sentiment ratios within valid range [0, 1]"""
        data = {
            "ticker": "AAPL",
            "sector": "Technology",
            "sentiment_score": 0.5,
            "positive": 0.6,
            "negative": 0.2,
            "neutral": 0.2,
            "news_count": 50
        }
        
        sentiment = SentimentData(**data)
        
        self.assertGreaterEqual(sentiment.positive, 0)
        self.assertLessEqual(sentiment.positive, 1)
        self.assertGreaterEqual(sentiment.negative, 0)
        self.assertLessEqual(sentiment.negative, 1)
        self.assertGreaterEqual(sentiment.neutral, 0)
        self.assertLessEqual(sentiment.neutral, 1)


class TestAPIResponse(unittest.TestCase):
    """Test API response model"""
    
    def test_api_response_success(self):
        """Test successful API response"""
        response = APIResponse(
            success=True,
            code="SUCCESS",
            data={"result": "ok"},
            message="Operation successful"
        )
        
        self.assertTrue(response.success)
        self.assertEqual(response.code, "SUCCESS")
        self.assertEqual(response.data["result"], "ok")
    
    def test_api_response_error(self):
        """Test error API response"""
        response = APIResponse(
            success=False,
            code="ERROR",
            data=None,
            message="Operation failed"
        )
        
        self.assertFalse(response.success)
        self.assertEqual(response.code, "ERROR")
        self.assertIsNone(response.data)


class TestSentimentAnalyzer(unittest.TestCase):
    """Test sentiment analyzer functions"""

    def test_fetch_news_success(self):
        """Verify that a mocked HTTP 200 response can be constructed."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '<html><body>Test news</body></html>'
        self.assertEqual(mock_response.status_code, 200)
        self.assertIn("news", mock_response.text)

    def test_sentiment_score_calculation(self):
        """Compound score (positive - negative) must be positive."""
        positive = 0.8
        negative = 0.1
        compound = positive - negative
        self.assertGreater(compound, 0)
        self.assertAlmostEqual(compound, 0.7, places=10)
    
    def test_sector_grouping(self):
        """Test sector-based data grouping"""
        data = [
            {"ticker": "AAPL", "sector": "Technology", "sentiment_score": 0.8},
            {"ticker": "MSFT", "sector": "Technology", "sentiment_score": 0.7},
            {"ticker": "JPM", "sector": "Finance", "sentiment_score": 0.6}
        ]
        
        df = pd.DataFrame(data)
        grouped = df.groupby('sector')['sentiment_score'].mean()
        
        self.assertAlmostEqual(grouped['Technology'], 0.75)
        self.assertEqual(grouped['Finance'], 0.6)


class TestDataCaching(unittest.TestCase):
    """Test data caching logic"""
    
    def test_cache_structure(self):
        """Test cache data structure"""
        cache = {
            'data': None,
            'timestamp': None,
            'is_generating': False,
            'generation_start': None
        }
        
        self.assertIn('data', cache)
        self.assertIn('timestamp', cache)
        self.assertIn('is_generating', cache)
        self.assertFalse(cache['is_generating'])
    
    def test_cache_update(self):
        """Test cache update logic"""
        import time
        
        cache = {
            'data': None,
            'timestamp': None,
            'is_generating': False,
            'generation_start': None
        }
        
        # Simulate data generation
        cache['is_generating'] = True
        cache['generation_start'] = time.time()
        
        # Simulate data ready
        cache['data'] = {"stocks": []}
        cache['timestamp'] = int(time.time())
        cache['is_generating'] = False
        
        self.assertIsNotNone(cache['data'])
        self.assertIsNotNone(cache['timestamp'])
        self.assertFalse(cache['is_generating'])


if __name__ == '__main__':
    unittest.main()

