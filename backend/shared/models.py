"""
全局共享数据模型（Pydantic Schemas）
=====================================
所有微服务共用同一套数据模型，保证 API 接口格式的一致性。

设计原则：
  - 所有 API 响应使用统一的 APIResponse 包装，前端只需处理一种格式
  - 请求模型内置字段校验（长度、格式、范围），不通过则自动返回 422
  - Pydantic v2 兼容（使用 model_config 代替内部 Config 类）
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from pydantic import BaseModel, EmailStr, Field


def _utcnow() -> datetime:
    """返回当前 UTC 时间（兼容 Python 3.12+ 的 timezone-aware 写法）。"""
    return datetime.now(timezone.utc)


# ===========================================================================
# 通用响应模型
# ===========================================================================

class APIResponse(BaseModel):
    """
    统一 API 响应格式。

    所有微服务的 HTTP 响应均使用此模型包装，前端通过 success 字段
    快速判断请求是否成功，无需检查 HTTP 状态码。

    字段说明
    --------
    success   : True = 成功，False = 失败
    code      : 业务状态码（如 "SUCCESS"、"NOT_FOUND"、"GENERATING"）
    data      : 响应数据，格式因接口而异
    message   : 人类可读的说明文字（可选）
    timestamp : 响应生成时间（UTC）

    示例
    ----
    成功：{"success": true, "code": "SUCCESS", "data": [...], "message": null}
    失败：{"success": false, "code": "NO_DATA", "data": [], "message": "请先触发数据刷新"}
    """
    success: bool
    code: str
    data: Optional[Any] = None
    message: Optional[str] = None
    timestamp: Optional[datetime] = Field(default_factory=_utcnow)

    model_config = {
        "json_schema_extra": {
            "example": {
                "success": True,
                "code": "SUCCESS",
                "data": {"id": 1, "name": "example"},
                "message": None,
                "timestamp": "2025-11-25T10:00:00Z",
            }
        }
    }


# ===========================================================================
# 认证相关模型
# ===========================================================================

class UserRegisterRequest(BaseModel):
    """
    用户注册请求体。

    字段校验规则：
      username : 3~50 个字符（防止过短或过长的用户名）
      email    : 必须是合法的邮箱格式（由 EmailStr 自动校验）
      password : 8~128 个字符（密码强度由 utils.validate_password_strength 二次校验）
    """
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    confirm_password: str  # 前端二次确认密码，后端校验两次输入是否一致

    model_config = {
        "json_schema_extra": {
            "example": {
                "username": "john_doe",
                "email": "john@example.com",
                "password": "SecurePass123!",
                "confirm_password": "SecurePass123!",
            }
        }
    }


class UserLoginRequest(BaseModel):
    """用户登录请求体（用户名 + 密码）。"""
    username: str
    password: str


class UserResponse(BaseModel):
    """
    返回给前端的用户信息（不含敏感字段如密码哈希）。

    id         : 数据库主键
    created_at : 账号创建时间
    last_login : 最近登录时间（用于安全审计）
    """
    id: int
    username: str
    email: str
    created_at: Optional[datetime] = None
    last_login: Optional[datetime] = None


class AuthTokenResponse(BaseModel):
    """
    登录/注册成功后返回的 JWT 令牌信息。

    access_token  : 短效令牌，用于 API 请求鉴权（Bearer Token）
    refresh_token : 长效令牌，用于无感刷新 access_token（可选）
    token_type    : 固定为 "Bearer"（OAuth 2.0 标准）
    expires_in    : access_token 有效期（秒）
    user          : 当前用户信息
    """
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "Bearer"
    expires_in: int
    user: UserResponse


# ===========================================================================
# 情感数据模型
# ===========================================================================

class SentimentData(BaseModel):
    """
    单支股票的情感分析结果。

    字段校验范围：
      sentiment_score : [-1, 1]（对应 VADER compound 值）
      positive        : [0, 1]（正面新闻比例）
      negative        : [0, 1]（负面新闻比例）
      neutral         : [0, 1]（中性新闻比例）

    注意：positive + negative + neutral 理论上应 ≈ 1.0，
          但由于浮点舍入，可能有极小偏差，不做严格校验。
    """
    ticker: str            # 股票代码，如 "AAPL"
    sector: str            # 所属行业，如 "Information Technology"
    sentiment_score: float = Field(..., ge=-1, le=1)
    positive: float = Field(..., ge=0, le=1)
    negative: float = Field(..., ge=0, le=1)
    neutral: float = Field(..., ge=0, le=1)
    news_count: int        # 参与计算的新闻条数（越多越可靠）
    timestamp: Optional[datetime] = None  # 数据生成时间


# ===========================================================================
# 可视化相关模型
# ===========================================================================

class VisualizationResponse(BaseModel):
    """
    可视化数据响应模型。

    type     : 图表类型，如 "treemap"（树状图）、"line"（折线图）
    title    : 图表标题
    data     : 图表数据，格式由具体 type 决定
    metadata : 附加信息，如颜色方案、坐标轴配置等（可选）
    """
    type: str
    title: str
    data: Dict[str, Any]
    metadata: Optional[Dict[str, Any]] = None
