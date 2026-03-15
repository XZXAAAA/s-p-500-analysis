"""
Shared utility functions
"""

import jwt
import os
from datetime import datetime, timedelta
from typing import Dict, Optional, Any
from functools import wraps
from fastapi import HTTPException, status


def generate_jwt_token(
    data: Dict[str, Any],
    secret_key: str,
    expires_delta: Optional[timedelta] = None
) -> str:
    """Generate JWT token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=24)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, secret_key, algorithm="HS256")
    return encoded_jwt


def verify_jwt_token(
    token: str,
    secret_key: str
) -> Dict[str, Any]:
    """Verify JWT token"""
    try:
        payload = jwt.decode(token, secret_key, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired"
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )


def validate_password_strength(password: str) -> bool:
    """
    Validate password strength
    Requirements:
    - Minimum 8 characters
    - Contains uppercase and lowercase letters
    - Contains numbers
    - Contains special characters
    """
    if len(password) < 8:
        return False
    
    has_upper = any(c.isupper() for c in password)
    has_lower = any(c.islower() for c in password)
    has_digit = any(c.isdigit() for c in password)
    has_special = any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password)
    
    return has_upper and has_lower and has_digit and has_special


def format_timestamp(dt: datetime) -> str:
    """Format timestamp"""
    return dt.isoformat()


def parse_timestamp(ts: str) -> datetime:
    """Parse timestamp string"""
    return datetime.fromisoformat(ts)

