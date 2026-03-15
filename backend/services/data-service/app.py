"""
数据服务（Data Service）— 端口 5002
======================================
职责：
  1. 启动时在后台线程运行情感分析流水线
  2. 将流水线结果缓存到内存（避免每次请求都重新抓取）
  3. 持久化到三个数据库（MySQL / DynamoDB / ClickHouse）
  4. 通过 REST API 暴露情感数据给前端和 API Gateway

端点概览：
  GET  /health                   → 健康检查
  GET  /data/status              → 查询流水线是否正在运行、数据是否就绪
  POST /data/refresh             → 手动触发后台刷新
  GET  /data/top-stocks          → 所有股票的情感排名列表
  GET  /sentiment/all            → 完整情感数据（含股票总数）
  GET  /sentiment/top-stocks     → 情感最正面的 Top N 股票
  GET  /sentiment/bottom-stocks  → 情感最负面的 Bottom N 股票
  GET  /sentiment/by-ticker/{t}  → 查询指定股票的情感数据

架构说明：
  - 数据库连接在启动时初始化，连接失败不阻塞服务（降级运行）
  - 情感流水线在后台线程中运行，不阻塞 HTTP 请求处理
  - 使用模块级字典 _cache 作为内存缓存（单进程场景下足够）
"""

import logging
import os
import sys
import threading
import time
from datetime import date

from fastapi import BackgroundTasks, FastAPI
from fastapi.middleware.cors import CORSMiddleware

# 将 backend/ 目录加入 Python 路径，使 database/ 和 shared/ 可以被直接导入
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from database.clickhouse_manager import ClickHouseManager
from database.dynamodb_manager import DynamoDBManager
from database.mysql_manager import MySQLManager
from shared.models import APIResponse

# 配置日志格式（时间 + 级别 + 消息）
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ===========================================================================
# FastAPI 应用初始化
# ===========================================================================

app = FastAPI(
    title="MarketViews Data Service",
    description="S&P 500 实时新闻抓取、情感分析与数据缓存服务",
    version="2.0.0",
    openapi_tags=[
        {"name": "data", "description": "数据管理（刷新、状态查询）"},
        {"name": "sentiment", "description": "情感分析结果查询"},
    ],
)

# 允许所有来源的跨域请求（开发环境；生产环境建议限制为前端域名）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ===========================================================================
# 数据库连接（全部可选：任何一个连接失败都不影响服务启动）
# ===========================================================================

def _try_connect(factory, name: str):
    """
    尝试连接数据库，失败时打印警告并返回 None。
    这种模式称为"可选依赖"：数据库不可用时服务降级运行，而非崩溃。
    """
    try:
        instance = factory()
        logger.info("✓ %s 连接成功", name)
        return instance
    except Exception as exc:
        logger.warning("⚠ %s 不可用：%s（服务继续运行，跳过持久化）", name, exc)
        return None


mysql_db = _try_connect(MySQLManager, "MySQL")
dynamodb = _try_connect(DynamoDBManager, "DynamoDB")
clickhouse_db = _try_connect(ClickHouseManager, "ClickHouse")


# ===========================================================================
# 内存缓存（单进程场景，无需 Redis）
# ===========================================================================

_cache: dict = {
    "data": None,            # 流水线结果（all_data / top_positive / top_negative）
    "timestamp": None,       # 数据生成的 Unix 时间戳
    "is_generating": False,  # 是否正在运行流水线（防止重复触发）
    "generation_start": None,  # 流水线开始时间（用于计算已耗时）
}


# ===========================================================================
# 流水线模块导入（可选）
# ===========================================================================

_PIPELINE_AVAILABLE = False
try:
    from pipeline import run as run_pipeline, PipelineResult
    _PIPELINE_AVAILABLE = True
    logger.info("✓ 情感分析流水线模块已加载")
except Exception as exc:
    logger.warning("⚠ 流水线模块加载失败：%s（/data/refresh 接口将不可用）", exc)


# ===========================================================================
# 生命周期事件
# ===========================================================================
@app.on_event("startup")
async def _startup() -> None:
    """
    服务启动时自动在后台线程触发一次流水线。
    这样前端在服务启动几分钟后就能获取到第一批数据，无需手动刷新。
    """
    if _PIPELINE_AVAILABLE and _cache["data"] is None:
        logger.info("服务启动，自动触发后台流水线...")
        threading.Thread(target=_run_pipeline_bg, daemon=True).start()


# ===========================================================================
# 后台任务
# ===========================================================================

def _run_pipeline_bg() -> None:
    """
    在后台线程中执行完整的情感分析流水线。

    流程：
      1. 标记 is_generating = True（防止并发重复触发）
      2. 运行流水线（约 5~10 分钟）
      3. 将结果写入各数据库
      4. 更新内存缓存
      5. 标记 is_generating = False
    """
    _cache["is_generating"] = True
    _cache["generation_start"] = time.time()
    try:
        result: PipelineResult = run_pipeline(debug=False)

        # 持久化到数据库（任何单个数据库的写入失败不影响其他）
        _store_to_databases(result)

        # 更新内存缓存（前端查询直接读缓存，不走数据库）
        _cache["data"] = {
            "all_data": result.all_stocks,
            "top_positive": result.top_5,
            "top_negative": result.low_5,
        }
        _cache["timestamp"] = result.timestamp

        logger.info(
            "✓ 流水线完成：%d 支股票，耗时 %.1f 秒",
            result.total_stocks, result.elapsed_seconds,
        )
    except Exception as exc:
        logger.error("✗ 流水线运行失败：%s", exc)
    finally:
        # 无论成功失败，都解除 generating 锁
        _cache["is_generating"] = False


def _store_to_databases(result: "PipelineResult") -> None:
    """
    将流水线结果持久化到三个数据库。

    MySQL   : 保存每日情感快照（便于历史查询和趋势分析）
    DynamoDB: 保存实时情感数据（高并发读取，低延迟）
    ClickHouse: 批量写入情感事件（用于 OLAP 分析和可视化）

    每个数据库的写入错误都被独立 catch，不会影响其他数据库或缓存更新。
    """
    today = date.today()
    ts = int(time.time())

    # 逐条写入 MySQL 和 DynamoDB
    for item in result.all_stocks:
        ticker = item["ticker"]
        score = item["sentiment_score"]
        pos = item["positive"]
        neg = item["negative"]
        neu = item["neutral"]
        count = item["news_count"]

        if mysql_db:
            try:
                mysql_db.save_sentiment_snapshot(
                    ticker=ticker, snapshot_date=today,
                    sentiment_score=score, positive_ratio=pos,
                    negative_ratio=neg, neutral_ratio=neu, news_count=count,
                )
            except Exception as exc:
                logger.debug("MySQL 写入失败（%s）：%s", ticker, exc)

        if dynamodb:
            try:
                dynamodb.save_realtime_sentiment(
                    ticker=ticker, timestamp=ts,
                    sentiment_score=score, positive=pos,
                    negative=neg, neutral=neu, source="data-service",
                )
            except Exception as exc:
                logger.debug("DynamoDB 写入失败（%s）：%s", ticker, exc)

    # ClickHouse 支持批量写入，一次调用处理所有记录（效率更高）
    if clickhouse_db:
        events = [
            {
                "ticker": it["ticker"],
                "sector": it["sector"],
                "sentiment_score": it["sentiment_score"],
                "positive": it["positive"],
                "negative": it["negative"],
                "neutral": it["neutral"],
                "news_count": it["news_count"],
            }
            for it in result.all_stocks
        ]
        try:
            clickhouse_db.insert_sentiment_events_batch(events)
            logger.info("✓ ClickHouse 批量写入 %d 条记录", len(events))
        except Exception as exc:
            logger.warning("ClickHouse 批量写入失败：%s", exc)


# ===========================================================================
# API 端点
# ===========================================================================

@app.get("/health", summary="健康检查")
async def health():
    """返回服务状态，API Gateway 用此接口判断服务是否存活。"""
    return {"status": "healthy", "service": "data-service", "version": "2.0.0"}


@app.get("/data/status", tags=["data"], summary="查询数据状态")
async def get_status():
    """
    返回当前流水线状态和数据就绪情况。

    前端轮询此接口，当 has_data=true 且 is_generating=false 时，
    说明数据已就绪，可以请求 /data/top-stocks 等接口。
    """
    elapsed = 0
    if _cache["is_generating"] and _cache["generation_start"]:
        elapsed = int(time.time() - _cache["generation_start"])
    return APIResponse(
        success=True, code="SUCCESS",
        data={
            "has_data": _cache["data"] is not None,
            "is_generating": _cache["is_generating"],
            "elapsed_seconds": elapsed,    # 流水线已运行的秒数
            "last_update": _cache["timestamp"],  # 上次数据更新时间戳
        },
    ).model_dump()


@app.post("/data/refresh", tags=["data"], summary="手动触发数据刷新")
async def refresh_data(background_tasks: BackgroundTasks):
    """
    手动触发一次完整的情感分析流水线（约 5~10 分钟）。

    注意：
      - 若流水线正在运行，返回 ALREADY_GENERATING 错误
      - 流水线在后台线程中运行，本接口立即返回（非阻塞）
    """
    if _cache["is_generating"]:
        elapsed = int(time.time() - (_cache["generation_start"] or 0))
        return APIResponse(
            success=False, code="ALREADY_GENERATING",
            message=f"流水线正在运行中（已耗时 {elapsed} 秒），请稍后再试",
        ).model_dump()

    if not _PIPELINE_AVAILABLE:
        return APIResponse(
            success=False, code="UNAVAILABLE",
            message="流水线模块未加载，请检查服务日志",
        ).model_dump()

    background_tasks.add_task(_run_pipeline_bg)
    return APIResponse(
        success=True, code="SUCCESS",
        message="后台刷新已启动，预计 5~10 分钟完成，请通过 /data/status 查询进度",
    ).model_dump()


@app.get("/data/top-stocks", tags=["sentiment"], summary="获取所有股票情感排名")
async def get_top_stocks(limit: int = 500):
    """
    返回按情感分数排序的股票列表（降序，情感最正面的在前）。

    参数
    ----
    limit : 最多返回的股票数量，默认 500（即全部）

    数据未就绪时返回 NO_DATA 或 GENERATING 状态码，
    前端可据此显示加载动画或生成进度提示。
    """
    if _cache["data"] is None:
        code = "GENERATING" if _cache["is_generating"] else "NO_DATA"
        elapsed = int(time.time() - (_cache["generation_start"] or 0)) if _cache["is_generating"] else 0
        msg = (
            f"数据生成中（已耗时 {elapsed} 秒），请稍候..."
            if code == "GENERATING"
            else "暂无数据，请先触发刷新（POST /data/refresh）"
        )
        return APIResponse(success=False, code=code, message=msg, data=[]).model_dump()

    stocks = _cache["data"]["all_data"]
    if 0 < limit < len(stocks):
        stocks = stocks[:limit]

    return APIResponse(
        success=True, code="SUCCESS",
        data=stocks, message=f"共 {len(stocks)} 支股票",
    ).model_dump()


@app.get("/sentiment/all", tags=["sentiment"], summary="获取完整情感数据")
async def get_all_sentiment():
    """返回所有股票的情感数据，额外包含总数字段（方便前端显示统计信息）。"""
    if _cache["data"] is None:
        return APIResponse(success=False, code="NO_DATA", message="暂无数据").model_dump()
    all_data = _cache["data"]["all_data"]
    return APIResponse(
        success=True, code="SUCCESS",
        data={"total_stocks": len(all_data), "stocks": all_data},
    ).model_dump()


@app.get("/sentiment/top-stocks", tags=["sentiment"], summary="情感最正面的 Top N")
async def get_top(limit: int = 10):
    """返回情感分数最高的前 N 支股票（正面情绪最强）。"""
    if _cache["data"] is None:
        return APIResponse(success=False, code="NO_DATA", message="暂无数据").model_dump()
    return APIResponse(
        success=True, code="SUCCESS",
        data=_cache["data"]["all_data"][:limit],
    ).model_dump()


@app.get("/sentiment/bottom-stocks", tags=["sentiment"], summary="情感最负面的 Bottom N")
async def get_bottom(limit: int = 10):
    """返回情感分数最低的前 N 支股票（负面情绪最强）。"""
    if _cache["data"] is None:
        return APIResponse(success=False, code="NO_DATA", message="暂无数据").model_dump()
    bottom = sorted(_cache["data"]["all_data"], key=lambda x: x["sentiment_score"])[:limit]
    return APIResponse(success=True, code="SUCCESS", data=bottom).model_dump()


@app.get("/sentiment/by-ticker/{ticker}", tags=["sentiment"], summary="按股票代码查询")
async def get_by_ticker(ticker: str):
    """
    查询指定股票的情感数据。

    ticker 大小写不敏感（"aapl" 和 "AAPL" 等价）。
    """
    if _cache["data"] is None:
        return APIResponse(success=False, code="NO_DATA", message="暂无数据").model_dump()
    ticker_upper = ticker.upper()
    for item in _cache["data"]["all_data"]:
        if item["ticker"] == ticker_upper:
            return APIResponse(success=True, code="SUCCESS", data=item).model_dump()
    return APIResponse(
        success=False, code="NOT_FOUND",
        message=f"未找到股票 {ticker_upper} 的情感数据",
    ).model_dump()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5002)
