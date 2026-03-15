"""
流水线编排器（Pipeline Runner）
================================
将爬虫层（Scraper）和分析层（Analyzer）串联成完整的端到端流程。

本模块故意保持"薄"：
  - 不包含业务逻辑（业务逻辑在 scraper/ 和 analyzer/ 中）
  - 只负责调用顺序、数据传递和日志记录
  - 便于单独测试每个步骤（通过 mock 替换子层）

完整流程（7 步）：
  Step 1：从 Wikipedia 获取 S&P 500 ticker 列表（含 robots.txt 检查）
  Step 2：用双车道策略从 Finviz 批量抓取新闻表格（500+ 支股票）
  Step 3：将原始 HTML 表格解析为结构化记录（含跨股票检测）
  Step 4：对每条新闻标题执行情感分析（OpenAI API）
  Step 5：按 ticker 聚合近 2 天的情感均值
  Step 6：从 Wikipedia 获取行业数据，与情感分数合并
  Step 7：按 compound 分数排序，生成完整结果

性能目标：
  - 500+ 支股票在 5~10 分钟内完成（取决于网络速度和 Finviz 限速策略）
  - 整体成功率 >95%（快车道 ~95% + 慢车道兜底剩余 ~5%）
"""

import logging
import time
from dataclasses import dataclass, field

import pandas as pd

# 支持两种导入方式：
#   1. 相对导入（作为 data-service 包的子包使用）
#   2. 绝对导入（data-service 目录在 sys.path 上，例如直接运行或测试时）
try:
    from ..scraper import get_tickers, get_news_table, parse_news_table
    from ..scraper.wikipedia import get_ticker_sector_df
    from ..analyzer import run_sentiment, aggregate_recent
except ImportError:
    from scraper import get_tickers, get_news_table, parse_news_table  # type: ignore
    from scraper.wikipedia import get_ticker_sector_df  # type: ignore
    from analyzer import run_sentiment, aggregate_recent  # type: ignore

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 流水线结果数据类
# ---------------------------------------------------------------------------

@dataclass
class PipelineResult:
    """
    流水线运行结果的结构化容器。

    字段说明
    --------
    all_stocks      : 所有股票的情感数据列表，按 sentiment_score 降序排列
                      每个元素为 dict，包含 ticker/sector/sentiment_score/
                      positive/negative/neutral/news_count/timestamp
    top_5           : sentiment_score 最高的 5 支股票（市场情绪最正面）
    low_5           : sentiment_score 最低的 5 支股票（市场情绪最负面）
    total_stocks    : 成功处理的股票总数
    elapsed_seconds : 流水线总耗时（秒）
    timestamp       : 流水线完成时的 Unix 时间戳
    """
    all_stocks: list[dict] = field(default_factory=list)
    top_5: list[dict] = field(default_factory=list)
    low_5: list[dict] = field(default_factory=list)
    total_stocks: int = 0
    elapsed_seconds: float = 0.0
    timestamp: int = 0


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

def run(debug: bool = False) -> PipelineResult:
    """
    执行完整的情感分析流水线。

    参数
    ----
    debug : True 时只处理前 50 支 ticker，加速本地调试（约 1~2 分钟）
            False 时处理全部 500+ 支 ticker（约 5~10 分钟）

    返回
    ----
    PipelineResult 实例，包含所有股票的情感评分和排名。

    异常处理：
      本函数本身不 catch 异常，由调用方（data-service/app.py）负责处理，
      确保异常能被记录到日志并触发告警。
    """
    start = time.time()
    logger.info("=" * 50)
    logger.info("情感分析流水线启动（debug=%s）", debug)

    # Step 1：获取股票代码列表
    tickers = get_tickers(debug=debug)
    logger.info("Step 1 完成：获取 %d 支 ticker", len(tickers))

    # Step 2：批量抓取新闻（双车道 + 指数退避）
    news_tables = get_news_table(tickers)
    logger.info("Step 2 完成：成功抓取 %d/%d 支股票的新闻", len(news_tables), len(tickers))

    # Step 3：解析新闻表格（传入完整 ticker 列表用于跨股票检测）
    parsed = parse_news_table(news_tables, known_tickers=tickers)
    logger.info("Step 3 完成：解析出 %d 条新闻记录", len(parsed))

    # Step 4：情感分析（OpenAI API）
    scored = run_sentiment(parsed)
    logger.info("Step 4 完成：评分 %d 条新闻", len(scored))

    # Step 5：聚合近 2 天的情感均值（每支股票一行）
    mean_scores = aggregate_recent(scored, days=2)
    logger.info("Step 5 完成：聚合 %d 支股票的情感均值", len(mean_scores))

    # Step 6：获取行业数据并与情感分数合并
    sector_df = get_ticker_sector_df()
    merged = _merge_sector(mean_scores, sector_df)
    logger.info("Step 6 完成：合并行业数据后共 %d 支股票", len(merged))

    # Step 7：排序并构建最终结果
    all_stocks, top_5, low_5 = _rank(merged, scored)
    elapsed = time.time() - start
    logger.info("Step 7 完成：排序完毕，共 %d 支股票", len(all_stocks))
    logger.info("流水线完成！耗时 %.1f 秒", elapsed)

    return PipelineResult(
        all_stocks=all_stocks,
        top_5=top_5,
        low_5=low_5,
        total_stocks=len(all_stocks),
        elapsed_seconds=elapsed,
        timestamp=int(time.time()),
    )


# ---------------------------------------------------------------------------
# 内部辅助函数
# ---------------------------------------------------------------------------

def _merge_sector(mean_scores: pd.DataFrame, sector_df: pd.DataFrame) -> pd.DataFrame:
    """
    将情感均值 DataFrame 与行业数据 DataFrame 进行内连接（inner join）。

    连接键：Ticker（两个 DataFrame 都有此列）
    使用 inner join 的原因：只保留同时有情感数据和行业信息的股票，
    过滤掉 Wikipedia 列表和 Finviz 数据中不重合的个别股票。

    同时将列名从英文技术名改为语义化名称，便于前端直接使用。
    """
    merged = sector_df.merge(mean_scores, on="Ticker", how="inner")
    # 重命名列：compound → Sentiment Score，neg → Negative，以此类推
    merged = merged.rename(columns={
        "compound": "Sentiment Score",
        "neg": "Negative",
        "neu": "Neutral",
        "pos": "Positive",
    })
    return merged.reset_index(drop=True)


def _rank(merged: pd.DataFrame, scored: pd.DataFrame) -> tuple[list, list, list]:
    """
    将合并后的 DataFrame 转换为字典列表，并按情感分数排序。

    同时统计每支股票的新闻数量（news_count），
    该指标反映了数据的可靠性：新闻越多，情感均值越稳定。

    返回
    ----
    (all_stocks, top_5, low_5)
    all_stocks : 所有股票，按 sentiment_score 降序排列
    top_5      : 情感最正面的前 5 支
    low_5      : 情感最负面的前 5 支
    """
    # 统计每支股票的原始新闻条数（含跨股票归属的条数）
    news_counts = scored.groupby("ticker").size().to_dict()

    all_stocks = []
    for _, row in merged.iterrows():
        ticker = row["Ticker"]
        all_stocks.append({
            "ticker": ticker,
            "sector": row["Sector"],
            # round(4) 保留 4 位小数，减少 JSON 体积
            "sentiment_score": round(float(row["Sentiment Score"]), 4),
            "positive": round(float(row["Positive"]), 4),
            "negative": round(float(row["Negative"]), 4),
            "neutral": round(float(row["Neutral"]), 4),
            "news_count": news_counts.get(ticker, 0),
            "timestamp": int(time.time()),
        })

    # 按情感分数降序排列（最正面的在前）
    all_stocks.sort(key=lambda x: x["sentiment_score"], reverse=True)

    # 取前 5 / 后 5（情感最极端的股票最有参考价值）
    top_5 = all_stocks[:5]
    low_5 = sorted(all_stocks, key=lambda x: x["sentiment_score"])[:5]

    return all_stocks, top_5, low_5
