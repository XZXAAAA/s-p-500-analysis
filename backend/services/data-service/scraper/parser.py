"""
新闻表格解析器
==============
将 Finviz 页面中抓取到的原始 BeautifulSoup 表格转换为结构化记录列表。

原始数据格式说明（Finviz news-table 的 HTML 结构）：
  <table id="news-table">
    <tr>
      <td>Dec-01-24 09:00AM</td>   ← 第一列：日期+时间（同一天后续行只有时间）
      <td><a href="...">标题</a></td>  ← 第二列：新闻标题（含超链接）
    </tr>
    <tr>
      <td>10:30AM</td>             ← 省略了日期（与上一行同一天）
      <td><a href="...">另一条标题</a></td>
    </tr>
  </table>

日期继承逻辑：
  Finviz 同一天的第一条新闻显示完整日期（"Dec-01-24 09:00AM"），
  后续同一天的新闻只显示时间（"10:30AM"），
  解析时需要从上一条记录继承日期，否则日期字段会丢失。

跨股票检测（Cross-Ticker Attribution）：
  如果一条新闻标题中同时提到了多支 S&P 500 股票（例如 "AAPL and MSFT announce..."），
  该新闻不仅归属于主股票（AAPL），还会额外归属于被提及的其他股票（MSFT），
  从而让情感分析能够捕获到 "某股票被新闻间接影响" 的信号。
"""

import re
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# 用于从新闻标题中识别 S&P 500 股票代码的正则
# 匹配 1~5 个大写字母组成的 "词"（\b 确保是完整单词，避免误匹配句中的大写缩写）
_TICKER_TOKEN_RE = re.compile(r"\b[A-Z]{1,5}\b")


def parse_news_table(
    news_tables: dict,
    known_tickers: list[str] | None = None,
) -> list[list]:
    """
    将原始新闻表格字典解析为扁平化记录列表。

    参数
    ----
    news_tables   : {ticker: BeautifulSoup <table> 标签}，来自 finviz.get_news_table()
                    table 为 None 表示该 ticker 抓取失败，会被静默跳过
    known_tickers : 可选，S&P 500 完整股票代码列表，用于跨股票检测
                    若不提供则不做跨股票归属

    返回
    ----
    记录列表，每条记录格式为：
        [ticker, date_str, time_str, headline]
    例：
        ["AAPL", "Dec-01-24", "09:00AM", "Apple reports record revenue"]

    注意：跨股票检测可能使总记录数 > 原始新闻条数（一条新闻对应多条记录）
    """
    # 构建已知 ticker 集合（大写），用于 O(1) 查找
    ticker_set: set[str] = set(t.upper() for t in (known_tickers or []))
    parsed: list[list] = []

    for primary, news_table in news_tables.items():
        if news_table is None:
            # 该 ticker 抓取失败，静默跳过（不影响其他 ticker 的处理）
            continue
        primary_upper = primary.upper()

        for row in news_table.find_all("tr"):
            try:
                # 过滤没有链接的行（Finviz 表格中偶有纯分隔行）
                if not row.find_all("a"):
                    continue

                headline = row.a.get_text().strip()  # 提取新闻标题文本

                # 解析日期和时间
                # Finviz 格式示例：
                #   完整行："Dec-01-24 09:00AM"  → parts = ["Dec-01-24", "09:00AM"]
                #   仅时间："10:30AM"            → parts = ["10:30AM"]
                parts = row.td.text.split()
                if len(parts) == 1:
                    # 只有时间，继承上一条记录的日期（日期继承逻辑）
                    date_str = parsed[-1][1] if parsed else datetime.today().strftime("%b-%d-%y")
                    time_str = parts[0]
                else:
                    date_str, time_str = parts[0], parts[1]

                # 添加主股票的记录
                parsed.append([primary_upper, date_str, time_str, headline])

                # 跨股票检测：在标题中查找其他已知股票代码
                if ticker_set:
                    # 提取标题中所有符合格式的大写词
                    candidates = set(_TICKER_TOKEN_RE.findall(headline))
                    # 与已知 ticker 集合取交集，排除主股票自身（避免重复计数）
                    for related in (candidates & ticker_set) - {primary_upper}:
                        parsed.append([related, date_str, time_str, headline])

            except Exception as exc:
                # 单行解析失败不影响其他行
                logger.debug("解析 %s 新闻行出错：%s", primary, exc)

    return parsed
