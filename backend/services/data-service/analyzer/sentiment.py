"""
情感评分模块
============
将解析好的新闻记录列表批量送入情感引擎，输出带评分的 DataFrame。

输入格式（来自 parser.parse_news_table）：
  每条记录为 [ticker, date_str, time_str, headline]
  例：["AAPL", "Dec-01-24", "09:00AM", "Apple beats earnings estimates"]

输出格式（DataFrame 列）：
  ticker   : 股票代码
  date     : 日期（datetime64，由 pandas 解析）
  time     : 时间字符串（如 "09:00AM"）
  headline : 新闻标题
  neg      : 负面情绪比例 [0, 1]
  neu      : 中性内容比例 [0, 1]
  pos      : 正面情绪比例 [0, 1]
  compound : 综合情感分数 [-1, 1]
"""

import logging
from datetime import datetime

import pandas as pd

from .engines import analyze

logger = logging.getLogger(__name__)

# DataFrame 基础列顺序（与 parser 输出记录顺序一致）
_COLUMNS = ["ticker", "date", "time", "headline"]


def run_sentiment(parsed_news: list[list]) -> pd.DataFrame:
    """
    对所有新闻记录批量执行情感分析。

    参数
    ----
    parsed_news : 来自 parse_news_table 的记录列表
                  每条记录：[ticker, date_str, time_str, headline]

    返回
    ----
    DataFrame，包含原始字段 + neg/neu/pos/compound 四列。
    空输入返回空 DataFrame（保持列定义，方便后续 concat）。

    实现细节：
      - 使用 pandas 向量化操作（.apply）批量调用 analyze()
      - 日期字符串统一转为 datetime64（便于后续按日期过滤聚合）
      - "Today" 关键字替换为当天日期字符串（Finviz 当天新闻的日期格式）
    """
    if not parsed_news:
        # 返回空 DataFrame 而非 None，保持接口一致性
        return pd.DataFrame(columns=_COLUMNS + ["neg", "neu", "pos", "compound"])

    # 构建基础 DataFrame
    df = pd.DataFrame(parsed_news, columns=_COLUMNS)

    # 批量情感分析：对每条 headline 调用 analyze()，返回 dict 列表
    scores = df["headline"].apply(analyze)
    # 将 dict 列表展开为四列，与原始 DataFrame 合并
    df = df.join(pd.DataFrame(scores.tolist()))

    # 统一日期格式：将 "Today" 替换为今天的日期字符串，然后解析为 datetime64
    today = datetime.today().date()
    df["date"] = df["date"].replace("Today", str(today))
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    # errors="coerce"：无法解析的日期变为 NaT（Not a Time），不会导致整列报错

    logger.info("共评分 %d 条新闻标题", len(df))
    return df
