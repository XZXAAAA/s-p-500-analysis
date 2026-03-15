"""
爬虫层集中配置文件
=================
所有可调参数均在此统一管理，支持通过环境变量覆盖（便于 Docker 部署）。

快车道 vs 慢车道设计思路：
  - 快车道：并发高、延迟短，负责处理约 95% 的 ticker，目标 5~10 分钟内完成 500+ 支股票
  - 慢车道：并发低、延迟长，仅重试快车道失败的少数 ticker，保证整体成功率 >95%

指数退避原则（Exponential Backoff）：
  遇到 HTTP 429（Too Many Requests）时，按序等待 100ms → 200ms → 400ms → 800ms，
  避免对目标服务器造成持续压力，同时最大限度提高最终成功率。
"""

import os

# ---------------------------------------------------------------------------
# HTTP 请求头 — 模拟真实 Chrome 浏览器，减少被反爬虫系统识别的概率
# ---------------------------------------------------------------------------
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)

# ---------------------------------------------------------------------------
# 并发控制参数（可通过环境变量调整）
# ---------------------------------------------------------------------------
# 线程池最大线程数（数值越大速度越快，但容易触发 429 限速）
MAX_WORKERS: int = int(os.getenv("SCRAPER_MAX_WORKERS", "3"))

# 每处理 BATCH_SIZE 个 ticker 后，随机暂停一次（模拟人类浏览节奏）
BATCH_SIZE: int = int(os.getenv("SCRAPER_BATCH_SIZE", "30"))

# 批次间暂停时长范围（秒），随机取其中一个值
BATCH_SLEEP_MIN: float = float(os.getenv("SCRAPER_BATCH_SLEEP_MIN", "8"))
BATCH_SLEEP_MAX: float = float(os.getenv("SCRAPER_BATCH_SLEEP_MAX", "12"))

# ---------------------------------------------------------------------------
# 单次请求前的随机延迟（秒）
# 增加随机性使请求模式更接近真实用户，降低封禁风险
# ---------------------------------------------------------------------------
DELAY_FAST_MIN: float = float(os.getenv("SCRAPER_DELAY_FAST_MIN", "1.0"))   # 快车道最小延迟
DELAY_FAST_MAX: float = float(os.getenv("SCRAPER_DELAY_FAST_MAX", "3.0"))   # 快车道最大延迟

DELAY_SLOW_MIN: float = float(os.getenv("SCRAPER_DELAY_SLOW_MIN", "3.0"))   # 慢车道最小延迟
DELAY_SLOW_MAX: float = float(os.getenv("SCRAPER_DELAY_SLOW_MAX", "6.0"))   # 慢车道最大延迟

# ---------------------------------------------------------------------------
# 指数退避序列（秒）
# 遇到 429 / 网络错误时按此序列依次等待后重试，超出次数后放弃该 ticker
# ---------------------------------------------------------------------------
BACKOFFS_FAST: list[float] = [0.1, 0.2, 0.4, 0.8]   # 快车道：100ms / 200ms / 400ms / 800ms
BACKOFFS_SLOW: list[float] = [2.0, 4.0, 8.0, 16.0]  # 慢车道：2s / 4s / 8s / 16s

# ---------------------------------------------------------------------------
# 慢车道队列后端
# 留空 = 使用进程内线程池（简单、无外部依赖）
# "redis" = 使用 Redis List 作为消息队列（适合多进程/多实例场景）
# ---------------------------------------------------------------------------
QUEUE_BACKEND: str = os.getenv("NEWS_QUEUE_BACKEND", "").lower()
QUEUE_REDIS_URL: str = os.getenv("NEWS_QUEUE_REDIS_URL", "redis://localhost:6379/0")
QUEUE_SLOW_KEY: str = os.getenv("NEWS_QUEUE_SLOW_KEY", "sentiment:news_slow_queue")
