"""
情感分析引擎（OpenAI API 实现）
==============================
所有情感分析均通过 OpenAI Chat Completions API 完成，需配置 OPENAI_API_KEY。

输出格式（与下游兼容）：
  neg      : 负面情绪比例 [0, 1]
  neu      : 中性内容比例 [0, 1]
  pos      : 正面情绪比例 [0, 1]
  compound : 综合情感分数 [-1, 1]

环境变量
--------
  OPENAI_API_KEY        : OpenAI API 密钥（必填）
  SENTIMENT_AI_MODEL    : 模型名，默认 "gpt-4.1-mini"
"""

import json
import logging
import os

logger = logging.getLogger(__name__)

_AI_MODEL = os.getenv("SENTIMENT_AI_MODEL", "gpt-4.1-mini")
_ai_client = None
_ai_mode: str | None = None

try:
    from openai import OpenAI  # type: ignore
    _ai_client = OpenAI()  # 自动读取环境变量 OPENAI_API_KEY
    _ai_mode = "v1"
    logger.info("OpenAI 情感引擎已初始化（模型：%s）", _AI_MODEL)
except Exception as e:
    try:
        import openai as _openai_legacy  # type: ignore
        if os.getenv("OPENAI_API_KEY"):
            _openai_legacy.api_key = os.getenv("OPENAI_API_KEY")
        _ai_client = _openai_legacy
        _ai_mode = "legacy"
        logger.info("OpenAI legacy 客户端已初始化")
    except Exception:
        logger.warning("OpenAI 客户端初始化失败：%s", e)


def analyze(text: str) -> dict[str, float]:
    """
    使用 OpenAI API 对输入文本进行情感分析，返回标准评分字典。

    参数
    ----
    text : 待分析的新闻标题或文本

    返回
    ----
    字典：neg, neu, pos (各 [0,1]，和≈1), compound ([-1,1])

    异常
    ----
    若未配置 OPENAI_API_KEY 或 API 调用失败，抛出异常（由调用方处理）。
    """
    if _ai_client is None or _ai_mode is None:
        raise RuntimeError(
            "情感分析依赖 OpenAI API，请设置环境变量 OPENAI_API_KEY 并安装 openai 包"
        )

    _SYSTEM = (
        "You are a financial news sentiment analyser. "
        "For the given headline return ONLY a JSON object with four numeric fields: "
        "neg, neu, pos (each in [0,1], sum ≈ 1) and compound (in [-1,1]). "
        "No extra text, no markdown, just JSON."
    )
    messages = [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": text},
    ]

    if _ai_mode == "v1":
        resp = _ai_client.chat.completions.create(
            model=_AI_MODEL,
            temperature=0,
            response_format={"type": "json_object"},
            messages=messages,
        )
        raw = resp.choices[0].message.content
    else:
        resp = _ai_client.ChatCompletion.create(
            model=_AI_MODEL, temperature=0, messages=messages
        )
        raw = resp.choices[0].message["content"]

    data = json.loads(raw or "{}")
    neg = float(data.get("neg", 0))
    neu = float(data.get("neu", 0))
    pos = float(data.get("pos", 0))
    compound = float(data.get("compound", 0))

    if not (0.0 <= neg <= 1.0 and 0.0 <= neu <= 1.0 and 0.0 <= pos <= 1.0):
        raise ValueError(f"比例分数超出 [0,1]：neg={neg}, neu={neu}, pos={pos}")
    if not (-1.0 <= compound <= 1.0):
        raise ValueError(f"compound 超出 [-1,1]：{compound}")

    total = neg + neu + pos
    if total > 0:
        neg, neu, pos = neg / total, neu / total, pos / total

    return {"neg": neg, "neu": neu, "pos": pos, "compound": compound}
