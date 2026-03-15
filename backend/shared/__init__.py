"""
Shared library module
"""

from .errors import (
    APIError,
    ValidationError,
    AuthenticationError,
    AuthorizationError,
    NotFoundError,
    ConflictError,
    DatabaseError,
    ExternalServiceError
)
from .models import (
    APIResponse,
    UserRegisterRequest,
    UserLoginRequest,
    UserResponse,
    AuthTokenResponse,
    SentimentData,
    VisualizationResponse
)
from .utils import (
    generate_jwt_token,
    verify_jwt_token,
    validate_password_strength,
    format_timestamp,
    parse_timestamp
)

__all__ = [
    # Errors
    "APIError",
    "ValidationError",
    "AuthenticationError",
    "AuthorizationError",
    "NotFoundError",
    "ConflictError",
    "DatabaseError",
    "ExternalServiceError",
    # Models
    "APIResponse",
    "UserRegisterRequest",
    "UserLoginRequest",
    "UserResponse",
    "AuthTokenResponse",
    "SentimentData",
    "VisualizationResponse",
    # Utils
    "generate_jwt_token",
    "verify_jwt_token",
    "validate_password_strength",
    "format_timestamp",
    "parse_timestamp",
]

