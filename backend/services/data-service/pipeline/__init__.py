"""
流水线层（Pipeline Layer）公共接口
=====================================
对外暴露一个函数和一个数据类：

  run(debug=False) → PipelineResult
      执行完整的情感分析流水线（抓取 → 解析 → 评分 → 聚合 → 排序）

  PipelineResult
      流水线结果容器，包含 all_stocks / top_5 / low_5 / 耗时等信息
"""

from .runner import run, PipelineResult

__all__ = ["run", "PipelineResult"]
