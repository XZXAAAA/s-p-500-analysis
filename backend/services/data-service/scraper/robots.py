"""
robots.txt 合规检查模块
=======================
在对任何目标网站发起请求之前，先解析其 robots.txt 文件，
确认当前 User-Agent 是否被允许抓取目标路径。

背景知识（robots.txt 是什么）：
  robots.txt 是网站根目录下的纯文本文件，用来声明哪些爬虫可以/不可以访问哪些页面。
  遵守 robots.txt 是负责任爬虫的基本礼仪，也能避免法律风险。

示例 robots.txt：
  User-agent: *
  Disallow: /private/
  Allow: /public/

本模块行为：
  - 首次访问某域名时解析并缓存其 robots.txt（避免重复请求）
  - 解析失败时 fail-open（默认允许）：网络不通时不能因此阻塞整个流水线
"""

import logging
from urllib import robotparser

logger = logging.getLogger(__name__)

# 模块级缓存：robots_url → RobotFileParser 实例
# 这样同一域名只需解析一次 robots.txt，减少不必要的网络请求
_cache: dict[str, robotparser.RobotFileParser] = {}


def can_fetch(robots_url: str, user_agent: str, path: str) -> bool:
    """
    检查是否允许爬取指定路径。

    参数
    ----
    robots_url  : 目标网站的 robots.txt 完整 URL，例如 "https://finviz.com/robots.txt"
    user_agent  : 发起请求时使用的 User-Agent 字符串
    path        : 要访问的页面路径，例如 "/quote.ashx?t=AAPL"

    返回
    ----
    True  = 允许抓取（或 robots.txt 无法加载时默认允许）
    False = 明确禁止抓取
    """
    # 使用缓存：同一 robots_url 只下载/解析一次
    if robots_url not in _cache:
        parser = robotparser.RobotFileParser()
        parser.set_url(robots_url)
        try:
            parser.read()
            logger.debug("已解析 robots.txt: %s", robots_url)
        except Exception as exc:
            # 网络超时、DNS 失败等情况：默认允许，不阻塞正常流程
            logger.warning("无法读取 robots.txt (%s): %s；默认允许", robots_url, exc)
            return True
        _cache[robots_url] = parser

    return _cache[robots_url].can_fetch(user_agent, path)
