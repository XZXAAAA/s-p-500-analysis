"""
爬虫层（Scraper Layer）公共接口
================================
对外只暴露三个核心函数，外部模块只需导入此包，无需关心内部模块划分。

  get_tickers(debug)
      → 从 Wikipedia 获取 S&P 500 股票代码列表

  get_news_table(tickers)
      → 从 Finviz 批量抓取各股票的新闻表格（双车道 + 指数退避）

  parse_news_table(news_tables, known_tickers)
      → 将原始 HTML 表格解析为结构化记录，支持跨股票检测
"""

from .wikipedia import get_tickers
from .finviz import get_news_table
from .parser import parse_news_table

__all__ = ["get_tickers", "get_news_table", "parse_news_table"]
