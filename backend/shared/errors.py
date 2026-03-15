"""
Unified error handling and custom exceptions
"""

from typing import Dict, Any, Optional


class APIError(Exception):
    """API base exception"""
    def __init__(
        self, 
        message: str, 
        code: str = "ERROR", 
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)

    def to_dict(self):
        return {
            'success': False,
            'code': self.code,
            'message': self.message,
            'details': self.details
        }


class ValidationError(APIError):
    """Data validation exception"""
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            status_code=400,
            details=details
        )


class AuthenticationError(APIError):
    """Authentication exception"""
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(
            message=message,
            code="AUTHENTICATION_ERROR",
            status_code=401
        )


class AuthorizationError(APIError):
    """Authorization exception"""
    def __init__(self, message: str = "Access denied"):
        super().__init__(
            message=message,
            code="AUTHORIZATION_ERROR",
            status_code=403
        )


class NotFoundError(APIError):
    """Resource not found exception"""
    def __init__(self, resource: str = "Resource"):
        super().__init__(
            message=f"{resource} not found",
            code="NOT_FOUND",
            status_code=404
        )


class ConflictError(APIError):
    """Resource conflict exception"""
    def __init__(self, message: str):
        super().__init__(
            message=message,
            code="CONFLICT",
            status_code=409
        )


class DatabaseError(APIError):
    """Database exception"""
    def __init__(self, message: str = "Database operation failed"):
        super().__init__(
            message=message,
            code="DATABASE_ERROR",
            status_code=500
        )


class ExternalServiceError(APIError):
    """External service exception"""
    def __init__(self, service: str, message: str):
        super().__init__(
            message=f"{service} error: {message}",
            code="EXTERNAL_SERVICE_ERROR",
            status_code=502
        )

