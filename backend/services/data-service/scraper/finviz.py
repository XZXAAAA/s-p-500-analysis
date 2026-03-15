"""
Finviz 新闻爬虫 — 双车道（Fast Lane / Slow Lane）设计
======================================================

架构说明
--------
处理 500+ 支股票时，如果串行请求每支约需 3 小时，因此本模块使用两个并发阶段：

  ┌─────────────────────────────────────────────────────┐
  │  快车道（Fast Lane）                                 │
  │  • 并发线程数：MAX_WORKERS（默认 3）                  │
  │  • 每请求前随机延迟 1~3 秒                            │
  │  • 失败时按 100ms/200ms/400ms/800ms 指数退避重试       │
  │  • 目标：处理约 95% 的 ticker                         │
  └─────────────────────────────────────────────────────┘
              ↓ 失败列表
  ┌─────────────────────────────────────────────────────┐
  │  慢车道（Slow Lane）                                  │
  │  • 并发线程数：最多 3（保守策略）                     │
  │  • 每请求前随机延迟 3~6 秒                            │
  │  • 失败时按 2s/4s/8s/16s 指数退避重试                 │
  │  • 可选 Redis 消息队列作为任务分发器                   │
  │  • 目标：消化剩余 5% 的难处理 ticker                  │
  └─────────────────────────────────────────────────────┘

robots.txt 合规：
  每次抓取前都检查 Finviz 的 robots.txt，确保爬虫行为合法合规。

数据来源：
  URL 格式：https://finviz.com/quote.ashx?t=AAPL
  目标元素：页面中 id="news-table" 的 <table> 标签，包含近期新闻标题和时间。
"""

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from http.client import IncompleteRead
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import numpy as np
from bs4 import BeautifulSoup

from .config import (
    BACKOFFS_FAST,
    BACKOFFS_SLOW,
    BATCH_SIZE,
    BATCH_SLEEP_MAX,
    BATCH_SLEEP_MIN,
    DEFAULT_USER_AGENT,
    DELAY_FAST_MAX,
    DELAY_FAST_MIN,
    DELAY_SLOW_MAX,
    DELAY_SLOW_MIN,
    MAX_WORKERS,
    QUEUE_BACKEND,
    QUEUE_REDIS_URL,
    QUEUE_SLOW_KEY,
)
from .robots import can_fetch

logger = logging.getLogger(__name__)

# Finviz 股票报价页面基础 URL（ticker 拼接在末尾）
_FINVIZ_BASE = "https://finviz.com/quote.ashx?t="
# 检查爬虫权限所用的 robots.txt 地址
_ROBOTS_URL = "https://finviz.com/robots.txt"


# ===========================================================================
# 公开 API
# ===========================================================================

def get_news_table(tickers: list[str]) -> dict[str, object]:
    """
    为指定 ticker 列表批量抓取 Finviz 新闻表格。

    参数
    ----
    tickers : 股票代码列表，例如 ["AAPL", "MSFT", "BRK.B"]

    返回
    ----
    字典：ticker → BeautifulSoup <table> 标签（失败则为 None）
    例：{"AAPL": <table ...>, "MSFT": None, ...}

    流程
    ----
    1. 快车道并发抓取全部 ticker
    2. 收集失败列表（table 为 None 的 ticker）
    3. 将失败列表交给慢车道重试
    """
    news_tables: dict[str, object] = {}
    fast_failures: list[str] = []

    # ---- 快车道：线程池并发抓取 ----
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {
            pool.submit(_process_ticker, idx, ticker, fast=True): ticker
            for idx, ticker in enumerate(tickers)
        }
        for future in as_completed(futures):
            ticker, table = future.result()
            if table is None:
                fast_failures.append(ticker)  # 记录失败的 ticker 供慢车道重试
            else:
                news_tables[ticker] = table

    # ---- 如果有失败的 ticker，交给慢车道重试 ----
    if fast_failures:
        logger.info(
            "快车道失败 %d 支 ticker，进入慢车道重试...",
            len(fast_failures),
        )
        _slow_lane(fast_failures, news_tables)

    # 打印最终成功率（用于监控和告警）
    total = len(tickers)
    success = len(news_tables)
    logger.info(
        "新闻抓取完成：%d/%d 成功（成功率 %.1f%%）",
        success, total, 100 * success / max(total, 1),
    )
    return news_tables


# ===========================================================================
# 慢车道实现
# ===========================================================================

def _slow_lane(failed: list[str], results: dict) -> None:
    """
    慢车道调度器：根据环境变量决定使用 Redis 队列还是线程池。

    优先尝试 Redis 队列（支持多进程/分布式），失败时自动降级为线程池。
    """
    if QUEUE_BACKEND == "redis":
        try:
            _slow_lane_redis(failed, results)
            return
        except Exception as exc:
            logger.warning("Redis 慢车道异常（%s），降级为线程池重试", exc)

    _slow_lane_threads(failed, results)


def _slow_lane_threads(failed: list[str], results: dict) -> None:
    """
    使用进程内线程池执行慢车道重试。
    并发数最多 3，保守策略降低触发限速的概率。
    """
    slow_workers = min(3, len(failed))
    with ThreadPoolExecutor(max_workers=slow_workers) as pool:
        futures = {
            pool.submit(_process_ticker, idx, ticker, fast=False): ticker
            for idx, ticker in enumerate(failed)
        }
        for future in as_completed(futures):
            ticker, table = future.result()
            if table is None:
                logger.warning("ticker %s 慢车道仍然失败，跳过", ticker)
            else:
                results[ticker] = table


def _slow_lane_redis(failed: list[str], results: dict) -> None:
    """
    使用 Redis List 作为消息队列执行慢车道重试。

    流程：
      RPUSH → 将失败的 ticker 列表压入 Redis 队列
      BLPOP → 依次弹出并处理（阻塞式消费，超时 5 秒）

    适合场景：多个工作进程共享同一 Redis 实例，实现分布式重试。
    """
    import redis as redis_lib  # type: ignore

    client = redis_lib.Redis.from_url(QUEUE_REDIS_URL)
    # 将所有失败 ticker 批量推入队列末尾
    client.rpush(QUEUE_SLOW_KEY, *failed)

    for _ in range(len(failed)):
        # 阻塞等待队列中的下一个任务，超时 5 秒后退出
        item = client.blpop(QUEUE_SLOW_KEY, timeout=5)
        if item is None:
            break
        _, raw = item
        ticker = raw.decode("utf-8")
        _, table = _fetch_news_table(ticker, fast=False)
        if table is None:
            logger.warning("ticker %s Redis 慢车道仍然失败，跳过", ticker)
        else:
            results[ticker] = table


# ===========================================================================
# 内部辅助函数
# ===========================================================================

def _process_ticker(index: int, ticker: str, *, fast: bool) -> tuple[str, object]:
    """
    处理单个 ticker：先按批次执行批量暂停，再抓取新闻。

    每处理 BATCH_SIZE 个 ticker 后随机暂停 8~12 秒，
    模拟真实用户浏览行为，避免被服务器识别为机器人并封禁 IP。
    """
    if index % BATCH_SIZE == 0 and index > 0:
        sleep_time = np.random.uniform(BATCH_SLEEP_MIN, BATCH_SLEEP_MAX)
        logger.debug("批次暂停 %.1f 秒（第 %d 批）", sleep_time, index // BATCH_SIZE)
        time.sleep(sleep_time)
    return _fetch_news_table(ticker, fast=fast)


def _fetch_news_table(ticker: str, *, fast: bool) -> tuple[str, object]:
    """
    抓取单个 ticker 在 Finviz 页面上的新闻表格。

    参数
    ----
    ticker : 股票代码（支持带点格式如 "BRK.B"，会自动转换为 "BRK-B" 用于 URL）
    fast   : True = 快车道（短延迟 + 短退避），False = 慢车道（长延迟 + 长退避）

    返回
    ----
    (原始 ticker, BeautifulSoup 表格标签 或 None)

    失败处理：
      - HTTP 429（限速）→ 按退避序列等待后重试
      - 网络错误/超时   → 同上
      - robots.txt 禁止 → 直接返回 (ticker, None)，不消耗重试次数
      - 退避次数耗尽    → 返回 (ticker, None)，由慢车道接管或放弃
    """
    original = ticker
    # Finviz 不接受 "." 格式（如 BRK.B），需要替换为 "-"（如 BRK-B）
    norm = ticker.replace(".", "-").upper()
    path = f"/quote.ashx?t={norm}"

    # robots.txt 检查：Finviz 明确允许爬取股票报价页面
    if not can_fetch(_ROBOTS_URL, DEFAULT_USER_AGENT, path):
        logger.warning("robots.txt 禁止访问 %s，跳过", path)
        return original, None

    # 根据快/慢车道选择对应的延迟参数和退避序列
    delay_min = DELAY_FAST_MIN if fast else DELAY_SLOW_MIN
    delay_max = DELAY_FAST_MAX if fast else DELAY_SLOW_MAX
    backoffs = BACKOFFS_FAST if fast else BACKOFFS_SLOW

    # 请求前随机等待（防止请求过于密集）
    time.sleep(np.random.uniform(delay_min, delay_max))

    url = _FINVIZ_BASE + norm

    # 按退避序列尝试最多 len(backoffs) 次
    for attempt, backoff in enumerate(backoffs, start=1):
        try:
            req = Request(url, headers={"User-Agent": DEFAULT_USER_AGENT})
            with urlopen(req, timeout=15) as resp:
                # 用 BeautifulSoup 解析 HTML，提取 id="news-table" 的表格
                html = BeautifulSoup(resp, "html.parser")
            table = html.find(id="news-table")
            if table is None:
                logger.debug("%s 页面中未找到 news-table 元素", norm)
            return original, table  # 成功：返回解析结果

        except HTTPError as exc:
            # 429 = Too Many Requests，按退避等待后重试
            logger.warning(
                "HTTP %d（%s，第 %d/%d 次）→ 等待 %.1fs",
                exc.code, norm, attempt, len(backoffs), backoff,
            )
            time.sleep(backoff)

        except (IncompleteRead, URLError, TimeoutError, OSError) as exc:
            # 网络层错误（连接重置、超时等），同样等待后重试
            logger.warning(
                "网络错误（%s，第 %d/%d 次）：%s → 等待 %.1fs",
                norm, attempt, len(backoffs), exc, backoff,
            )
            time.sleep(backoff)

    # 所有重试次数耗尽，放弃该 ticker
    logger.error(
        "ticker %s 在 %d 次重试后仍然失败（fast=%s），跳过",
        norm, len(backoffs), fast,
    )
    return original, None
