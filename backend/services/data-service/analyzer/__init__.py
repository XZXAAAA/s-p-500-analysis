"""
情感分析层（Analyzer Layer）公共接口
======================================
对外只暴露两个核心函数：

  run_sentiment(parsed_news)
      → 对解析好的新闻记录批量进行情感打分
      → 返回带 neg/neu/pos/compound 列的 DataFrame

  aggregate_recent(scored_df, days)
      → 对近 N 天的评分按股票取均值
      → 返回每支股票的代表性情感均值 DataFrame

底层使用 OpenAI API 进行情感分析，需配置 OPENAI_API_KEY。
"""

from .sentiment import run_sentiment
from .aggregation import aggregate_recent

__all__ = ["run_sentiment", "aggregate_recent"]
