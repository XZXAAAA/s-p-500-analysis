"""
Visualization Service
Port: 5003
Responsibilities: Generate interactive visualizations, data aggregation analysis
"""

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
import logging
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from shared.models import APIResponse, VisualizationResponse
from database.clickhouse_manager import ClickHouseManager
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Visualization Service",
    description="Interactive data visualization service",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize ClickHouse connection
try:
    clickhouse_db = ClickHouseManager()
    logger.info("✓ ClickHouse connected successfully")
except Exception as e:
    logger.warning(f"⚠ ClickHouse connection failed: {str(e)}")
    clickhouse_db = None


@app.get("/health")
async def health():
    """Health check"""
    return {"status": "healthy", "service": "viz-service"}


@app.get("/viz/treemap")
async def get_treemap(sentiment: str = "positive", mode: str = "all", days: int = 1):
    """
    Get Treemap visualization data from ClickHouse
    
    sentiment: positive or negative
    mode: top5 or all
    days: number of days to query
    """
    if not clickhouse_db:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ClickHouse not available"
        )
    
    try:
        # Get top stocks based on sentiment
        if sentiment.lower() == "positive":
            stocks = clickhouse_db.get_top_positive_stocks(days=days, limit=500 if mode == "all" else 5)
        else:
            stocks = clickhouse_db.get_top_negative_stocks(days=days, limit=500 if mode == "all" else 5)
        
        if not stocks:
            return APIResponse(
                success=True,
                code="SUCCESS",
                data={
                    "type": "treemap",
                    "layout": {
                        "title": f"S&P 500 Stocks - {sentiment.upper()} Sentiment ({mode.upper()})",
                        "width": 1200,
                        "height": 600
                    },
                    "data": []
                }
            ).dict()
        
        # Group by sector for treemap structure
        labels = ["S&P 500"]
        parents = [""]
        values = [1]
        sectors_seen = set()
        
        for row in stocks:
            ticker = row[0]
            sector = row[1]
            sentiment_score = float(row[2]) if len(row) > 2 else 0.0
            
            # Add sector if not seen
            if sector not in sectors_seen:
                labels.append(sector)
                parents.append("S&P 500")
                values.append(0)  # Will be calculated
                sectors_seen.add(sector)
            
            # Add ticker
            labels.append(ticker)
            parents.append(sector)
            values.append(abs(sentiment_score))
        
        treemap_data = {
            "type": "treemap",
            "layout": {
                "title": f"S&P 500 Stocks - {sentiment.upper()} Sentiment ({mode.upper()})",
                "width": 1200,
                "height": 600
            },
            "data": [{
                "labels": labels,
                "parents": parents,
                "values": values,
                "type": "treemap"
            }]
        }
        
        return APIResponse(
            success=True,
            code="SUCCESS",
            data=treemap_data
        ).dict()
    except Exception as e:
        logger.error(f"Error getting treemap data: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get treemap data: {str(e)}"
        )


@app.get("/viz/sentiment-timeline")
async def get_sentiment_timeline(ticker: str = "AAPL", days: int = 7):
    """Get sentiment timeline from ClickHouse"""
    if not clickhouse_db:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ClickHouse not available"
        )
    
    try:
        ticker = ticker.upper().strip()
        analysis_data = clickhouse_db.get_ticker_analysis(ticker=ticker, days=days)
        
        if not analysis_data:
            return APIResponse(
                success=True,
                code="SUCCESS",
                data={
                    "ticker": ticker,
                    "period_days": days,
                    "data": []
                }
            ).dict()
        
        # Convert ClickHouse results to timeline format
        timeline_records = []
        for row in analysis_data:
            event_date = row[0]
            sentiment_score = float(row[3]) if len(row) > 3 else 0.0
            positive = float(row[4]) if len(row) > 4 else 0.0
            negative = float(row[5]) if len(row) > 5 else 0.0
            news_count = int(row[7]) if len(row) > 7 else 0
            
            timeline_records.append({
                "date": event_date.strftime("%Y-%m-%d") if hasattr(event_date, 'strftime') else str(event_date),
                "sentiment_score": round(sentiment_score, 3),
                "positive": round(positive, 3),
                "negative": round(negative, 3),
                "news_count": news_count
            })
        
        # Sort by date ascending
        timeline_records.sort(key=lambda x: x["date"])
        
        timeline_data = {
            "ticker": ticker,
            "period_days": days,
            "data": timeline_records
        }
        
        return APIResponse(
            success=True,
            code="SUCCESS",
            data=timeline_data
        ).dict()
    except Exception as e:
        logger.error(f"Error getting sentiment timeline: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get sentiment timeline: {str(e)}"
        )


@app.get("/viz/market-overview")
async def get_market_overview(days: int = 7):
    """Get market overview from ClickHouse"""
    if not clickhouse_db:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ClickHouse not available"
        )
    
    try:
        # Get sector trends aggregated by sector
        sector_stats = clickhouse_db.get_sector_statistics(days=days)
        
        if not sector_stats:
            return APIResponse(
                success=True,
                code="SUCCESS",
                data={
                    "period_days": days,
                    "sectors": []
                }
            ).dict()
        
        # Convert to response format
        sectors_list = []
        for row in sector_stats:
            sector = row[0]
            ticker_count = int(row[1]) if len(row) > 1 else 0
            avg_sentiment = float(row[2]) if len(row) > 2 else 0.0
            total_news = int(row[5]) if len(row) > 5 else 0
            
            sectors_list.append({
                "sector": sector,
                "avg_sentiment": round(avg_sentiment, 3),
                "ticker_count": ticker_count,
                "total_news": total_news
            })
        
        overview_data = {
            "period_days": days,
            "sectors": sectors_list
        }
        
        return APIResponse(
            success=True,
            code="SUCCESS",
            data=overview_data
        ).dict()
    except Exception as e:
        logger.error(f"Error getting market overview: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get market overview: {str(e)}"
        )


@app.get("/viz/sector-analysis")
async def get_sector_analysis(days: int = 7):
    """Get sector analysis from ClickHouse"""
    if not clickhouse_db:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ClickHouse not available"
        )
    
    try:
        stats = clickhouse_db.get_sector_statistics(days=days)
        
        if not stats:
            return APIResponse(
                success=True,
                code="SUCCESS",
                data={
                    "sectors": [],
                    "period_days": days
                }
            ).dict()
        
        # Convert ClickHouse results to response format
        sectors_list = []
        for row in stats:
            sector = row[0]
            ticker_count = int(row[1]) if len(row) > 1 else 0
            avg_sentiment = float(row[2]) if len(row) > 2 else 0.0
            max_sentiment = float(row[3]) if len(row) > 3 else 0.0
            min_sentiment = float(row[4]) if len(row) > 4 else 0.0
            total_news = int(row[5]) if len(row) > 5 else 0
            volatility = float(row[6]) if len(row) > 6 else 0.0
            
            sectors_list.append({
                "sector": sector,
                "ticker_count": ticker_count,
                "avg_sentiment": round(avg_sentiment, 3),
                "max_sentiment": round(max_sentiment, 3),
                "min_sentiment": round(min_sentiment, 3),
                "total_news": total_news,
                "volatility": round(volatility, 3)
            })
        
        sectors_data = {
            "sectors": sectors_list,
            "period_days": days
        }
        
        return APIResponse(
            success=True,
            code="SUCCESS",
            data=sectors_data
        ).dict()
    except Exception as e:
        logger.error(f"Error getting sector analysis: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get sector analysis: {str(e)}"
        )


@app.get("/viz/download-csv")
async def download_csv(sentiment: str = "positive", mode: str = "all", days: int = 1):
    """Get CSV download metadata from ClickHouse"""
    if not clickhouse_db:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ClickHouse not available"
        )
    
    try:
        # Get stock data based on sentiment
        if sentiment.lower() == "positive":
            stocks = clickhouse_db.get_top_positive_stocks(days=days, limit=500 if mode == "all" else 5)
        else:
            stocks = clickhouse_db.get_top_negative_stocks(days=days, limit=500 if mode == "all" else 5)
        
        record_count = len(stocks) if stocks else 0
        # Estimate size: approximately 100 bytes per record
        estimated_size_kb = max(1, record_count * 100 // 1024)
        
        return APIResponse(
            success=True,
            code="SUCCESS",
            data={
                "filename": f"sentiment_{sentiment}_{mode}_{days}days.csv",
                "records": record_count,
                "size_kb": estimated_size_kb
            }
        ).dict()
    except Exception as e:
        logger.error(f"Error getting CSV metadata: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get CSV metadata: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5003)

