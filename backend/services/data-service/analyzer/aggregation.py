"""
情感评分聚合模块
================
按股票代码（ticker）对近 N 天的情感评分取平均值，
输出每支股票的代表性情感指标。

为什么需要聚合？
  单条新闻的评分存在噪声（例如，一条中性的公告新闻 compound≈0），
  对近几天的多条新闻取平均，能更稳定地反映市场对该股票的整体情绪。

聚合策略：
  1. 按 ticker 分组，找到每支股票的最新新闻日期（max_date）
  2. 截取 [max_date - (days-1), max_date] 时间窗口内的所有新闻
  3. 对 neg/neu/pos/compound 四个指标取算术平均值

注意：使用"最新日期 - N 天"而非"当天 - N 天"，
      是因为某些股票的最新新闻可能不是今天（周末、假日无新闻），
      这样能保证每支股票都有足够的数据参与聚合。
"""

import logging
from datetime import timedelta

import pandas as pd

logger = logging.getLogger(__name__)


def aggregate_recent(scored: pd.DataFrame, days: int = 2) -> pd.DataFrame:
    """
    对每支股票计算最近 days 天的平均情感评分。

    参数
    ----
    scored : run_sentiment() 的输出，必须包含列：
             ticker, date（datetime64）, neg, neu, pos, compound
    days   : 时间窗口（日历天数，默认 2 天）
             设为 1 = 只看最新一天的新闻
             设为 7 = 看最近一周的新闻

    返回
    ----
    DataFrame，列名为 ["Ticker", "neg", "neu", "pos", "compound"]
    每行代表一支股票的近期情感均值。

    空输入返回空 DataFrame（列名相同，便于 concat 和 merge）。

    注意：返回列名 "Ticker"（大写 T）以便与 Wikipedia 行业数据进行 merge。
    """
    if scored.empty:
        return pd.DataFrame(columns=["Ticker", "neg", "neu", "pos", "compound"])

    frames: list[pd.DataFrame] = []
    # 找到每支股票的最新新闻日期
    max_dates = scored.groupby("ticker")["date"].max()

    for ticker, max_date in max_dates.items():
        # 时间窗口：最新日期往前推 (days-1) 天
        cutoff = max_date - timedelta(days=days - 1)
        # 筛选该 ticker 在时间窗口内的所有记录
        mask = (scored["ticker"] == ticker) & (scored["date"] >= cutoff)
        frames.append(scored.loc[mask])

    if not frames:
        return pd.DataFrame(columns=["Ticker", "neg", "neu", "pos", "compound"])

    # 合并所有 ticker 的近期记录
    recent = pd.concat(frames)

    # 按 ticker 分组，对四个情感指标取均值
    mean = (
        recent.groupby("ticker")[["neg", "neu", "pos", "compound"]]
        .mean()
        .dropna()          # 删除有 NaN 的行（日期解析失败等边缘情况）
        .reset_index()
        .rename(columns={"ticker": "Ticker"})  # 统一为大写 Ticker，便于后续 merge
    )
    return mean
