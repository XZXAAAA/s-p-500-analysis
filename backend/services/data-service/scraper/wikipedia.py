"""
Wikipedia S&P 500 股票列表爬虫
===============================
从 Wikipedia 的 "List of S&P 500 companies" 页面获取标准普尔 500 指数成分股的
股票代码（Ticker）和所属行业（Sector）。

为什么选择 Wikipedia？
  - Wikipedia 的 S&P 500 页面由社区持续维护，与官方数据保持高度一致
  - 相比 EDGAR、Bloomberg 等数据源，访问无需付费授权
  - robots.txt 明确允许爬虫访问该页面

数据格式：
  Wikipedia 用标准 HTML 表格（<table class="wikitable sortable">）呈现数据，
  pandas.read_html() 可直接将其解析为 DataFrame。

容错设计：
  任何网络/解析异常都会回退到内置的 10 支头部股票作为备用列表，
  确保整个情感分析流水线不会因为 Wikipedia 暂时不可达而崩溃。
"""

import re
import logging

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .config import DEFAULT_USER_AGENT
from .robots import can_fetch

logger = logging.getLogger(__name__)

# Wikipedia S&P 500 成分股列表页面地址
_WIKI_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
# robots.txt 地址（在发起实际请求前先检查是否允许）
_ROBOTS_URL = "https://en.wikipedia.org/robots.txt"

# 合法 Ticker 格式：1~5 个大写字母，可选带一个点+一个大写字母（如 BRK.B）
_TICKER_RE = re.compile(r"^[A-Z]{1,5}(\.[A-Z])?$")

# 备用 Ticker 列表（当 Wikipedia 不可达时使用），涵盖市值最大的头部股票
_FALLBACK_TICKERS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "TSLA",
    "META", "NVDA", "JPM", "V", "WMT",
]


def get_tickers(debug: bool = False) -> list[str]:
    """
    获取 S&P 500 所有成分股的 Ticker 列表。

    流程
    ----
    1. 检查 Wikipedia 的 robots.txt → 不允许则直接返回备用列表
    2. 用带自动重试的 Session 下载页面 HTML
    3. 用 pandas.read_html 找到包含 "Symbol" + "Sector" 列的表格
    4. 用正则过滤掉格式不合法的字符串（防止 Wikipedia 表格格式变化）
    5. debug 模式下截取前 50 支（加速本地调试）

    参数
    ----
    debug : True 时只返回前 50 支 ticker，用于本地快速测试

    返回
    ----
    股票代码字符串列表，例如 ["AAPL", "MSFT", "BRK.B", ...]
    任何错误都会返回内置备用列表，流水线不会中断。
    """
    # Step 1：robots.txt 合规检查
    if not can_fetch(_ROBOTS_URL, DEFAULT_USER_AGENT, "/wiki/List_of_S%26P_500_companies"):
        logger.error("robots.txt 禁止访问 Wikipedia，使用备用 ticker 列表")
        return list(_FALLBACK_TICKERS)

    # Step 2：创建带重试逻辑的 HTTP Session（最多重试 3 次，退避因子 0.3）
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=Retry(total=3, backoff_factor=0.3)))

    try:
        resp = session.get(
            _WIKI_URL,
            headers={"User-Agent": DEFAULT_USER_AGENT},
            timeout=10,
        )
        resp.raise_for_status()  # 非 2xx 状态码会抛出异常

        # Step 3：在页面所有表格中找出 S&P 500 成分股表格
        target = _find_sp500_table(resp.text)
        if target is None:
            raise ValueError("S&P 500 table not found in Wikipedia page")

        # Step 4：提取 "Symbol" 列并过滤格式不合法的字符串
        raw = target["Symbol"].astype(str).str.strip().tolist()
        tickers = [t for t in raw if _TICKER_RE.match(t)]

        # 如果有效 ticker 数量异常偏少，打印警告（可能是页面格式发生了变化）
        if len(tickers) < 400:
            logger.warning("从 Wikipedia 获取的 ticker 数量异常偏少：%d 支", len(tickers))

        # Step 5：debug 模式截取前 50 支，减少调试耗时
        if debug:
            tickers = tickers[:50]

        logger.info("从 Wikipedia 成功获取 %d 支 ticker", len(tickers))
        return tickers

    except Exception as exc:
        # 任何异常（网络超时、HTML 格式变化等）都回退到备用列表
        logger.error("从 Wikipedia 获取 ticker 失败：%s，使用备用列表", exc)
        return list(_FALLBACK_TICKERS)


def get_ticker_sector_df() -> pd.DataFrame:
    """
    获取 S&P 500 成分股的 Ticker → Sector 映射表。

    用途：在情感分析流水线的最后一步，将行业信息合并到情感评分结果中，
    使得最终输出包含 ticker、sector、sentiment_score 等完整字段。

    返回
    ----
    DataFrame，列名为 ["Ticker", "Sector"]
    失败时返回空 DataFrame（调用方需兼容空结果）。
    """
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=Retry(total=3, backoff_factor=0.3)))
    try:
        resp = session.get(
            _WIKI_URL,
            headers={"User-Agent": DEFAULT_USER_AGENT},
            timeout=10,
        )
        resp.raise_for_status()

        # 首选路径：用 pandas.read_html 直接解析表格
        target = _find_sp500_table(resp.text)
        if target is not None:
            # 把 "Symbol" 列映射为 "Ticker"，找到含 "sector" 的列映射为 "Sector"
            col_map = {}
            for c in target.columns:
                lc = str(c).strip().lower()
                if lc == "symbol":
                    col_map[c] = "Ticker"
                elif "sector" in lc:
                    col_map[c] = "Sector"
            return target[list(col_map)].rename(columns=col_map)

        # 备选路径：用 BeautifulSoup 手动解析（应对 pandas 解析失败的边缘情况）
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, "html.parser")
        table = soup.find("table", {"class": "wikitable sortable"})
        if table is None:
            raise ValueError("wikitable sortable not found")
        rows = table.find_all("tr")[1:]  # 跳过表头行
        data = [
            (row.find_all("td")[0].text.strip(), row.find_all("td")[2].text.strip())
            for row in rows
            if len(row.find_all("td")) >= 3
        ]
        return pd.DataFrame(data, columns=["Ticker", "Sector"])

    except Exception as exc:
        logger.error("获取行业数据失败：%s", exc)
        return pd.DataFrame(columns=["Ticker", "Sector"])  # 返回空 DataFrame，不抛出异常


# ---------------------------------------------------------------------------
# 内部工具函数
# ---------------------------------------------------------------------------

def _find_sp500_table(html: str) -> pd.DataFrame | None:
    """
    在页面 HTML 中找到包含 S&P 500 数据的表格。

    策略：用 pandas.read_html 解析页面所有表格，
    找出同时包含 "symbol" 列和 "sector" 关键字列的第一个表格。

    返回 None 表示未找到符合条件的表格。
    """
    try:
        tables = pd.read_html(html)
    except Exception:
        return None
    for t in tables:
        cols = [str(c).strip().lower() for c in t.columns]
        if "symbol" in cols and any("sector" in c for c in cols):
            return t
    return None
