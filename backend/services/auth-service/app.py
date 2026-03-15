"""
Auth Service
Port: 5001
Responsibilities: User authentication, session management, permission verification
"""

from fastapi import FastAPI, HTTPException, status, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import EmailStr
import logging
import os
from datetime import timedelta
import sys

# Add parent directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from database.mysql_manager import MySQLManager
from database.dynamodb_manager import DynamoDBManager
from shared.models import (
    APIResponse,
    UserRegisterRequest,
    UserLoginRequest,
    UserResponse,
    AuthTokenResponse
)
from shared.errors import (
    ValidationError,
    AuthenticationError,
    ConflictError,
    NotFoundError
)
from shared.utils import (
    generate_jwt_token,
    verify_jwt_token,
    validate_password_strength
)
from werkzeug.security import generate_password_hash, check_password_hash

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI application
app = FastAPI(
    title="Auth Service",
    description="User authentication and session management service",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {
            "name": "authentication",
            "description": "User authentication operations"
        },
        {
            "name": "users",
            "description": "User management operations"
        }
    ]
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database managers
try:
    mysql_db = MySQLManager()
    logger.info("✓ Connected to MySQL successfully")
except Exception as e:
    logger.error(f"✗ Failed to connect to MySQL: {str(e)}")
    mysql_db = None

try:
    dynamodb = DynamoDBManager()
    logger.info("✓ Connected to DynamoDB successfully")
except Exception as e:
    logger.warning(f"⚠ Failed to connect to DynamoDB: {str(e)}")
    dynamodb = None

# Get JWT secret key
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24


def get_current_user(request: Request):
    """Resolve current user id from bearer token"""
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header"
        )
    
    try:
        scheme, token = auth_header.split()
        if scheme.lower() != "bearer":
            raise ValueError("Invalid authentication scheme")
        
        payload = verify_jwt_token(token, JWT_SECRET_KEY)
        user_id = payload.get("user_id")
        if not user_id:
            raise ValueError("Invalid token payload")
        
        return user_id
    except Exception as e:
        logger.error(f"Token verification failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )


# ===== API Endpoints =====

@app.get("/health")
async def health_check():
    """Health check"""
    return {
        "status": "healthy",
        "service": "auth-service",
        "version": "1.0.0"
    }


@app.post("/auth/register", response_model=APIResponse, tags=["authentication"])
async def register(request: UserRegisterRequest):
    """
    Register a new user
    
    **Requirements:**
    - username: 3-50 characters
    - email: valid email address
    - password: minimum 8 characters including upper/lower case, number, special char
    - confirm_password: must match password
    
    **Returns:**
    - User object
    - JWT access token
    
    **Errors:**
    - 400: Validation error (invalid input)
    - 409: Conflict (username already exists)
    - 500: Internal server error
    """
    try:
        # Verify password consistency
        if request.password != request.confirm_password:
            raise ValidationError("Passwords do not match")
        
        # Validate password strength
        if not validate_password_strength(request.password):
            raise ValidationError(
                "Password must contain uppercase, lowercase, number, and special character"
            )
        
        if not mysql_db:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database connection failed"
            )
        
        # Check if user already exists
        existing_user = mysql_db.get_user_by_username(request.username)
        if existing_user:
            raise ConflictError(f"Username {request.username} already exists")
        
        # Create user
        password_hash = generate_password_hash(request.password)
        user_obj = mysql_db.create_user(request.username, request.email, password_hash)
        
        # Log audit entry
        mysql_db.log_action(
            user_id=user_obj.id,
            action="USER_REGISTER",
            resource_type="user",
            resource_id=str(user_obj.id),
            status="success"
        )
        
        logger.info(f"✓ User registered: {request.username}")
        
        # Generate JWT token
        access_token = generate_jwt_token(
            {"user_id": user_obj.id, "username": user_obj.username},
            JWT_SECRET_KEY,
            timedelta(hours=JWT_EXPIRATION_HOURS)
        )
        
        return APIResponse(
            success=True,
            code="SUCCESS",
            data={
                "user": UserResponse(
                    id=user_obj.id,
                    username=user_obj.username,
                    email=user_obj.email,
                    created_at=user_obj.created_at
                ),
                "token": access_token
            },
            message="Registration successful"
        )
    
    except (ValidationError, ConflictError) as e:
        logger.warning(f"Registration validation failed: {str(e)}")
        raise HTTPException(
            status_code=e.status_code,
            detail=e.message
        )
    except Exception as e:
        logger.error(f"Registration failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        )


@app.post("/auth/login", response_model=APIResponse, tags=["authentication"])
async def login(request: UserLoginRequest):
    """
    Authenticate user and get access token
    
    **Parameters:**
    - username: User's username
    - password: User's password
    
    **Returns:**
    - User object
    - JWT access token (valid for 24 hours)
    
    **Errors:**
    - 401: Authentication failed (incorrect credentials)
    - 500: Internal server error
    """
    try:
        if not mysql_db:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database connection failed"
            )
        
        # Get user
        user_obj = mysql_db.get_user_by_username(request.username)
        if not user_obj or not check_password_hash(user_obj.password_hash, request.password):
            raise AuthenticationError("Incorrect username or password")
        
        # Update last login time
        from datetime import datetime
        user_obj.last_login = datetime.utcnow()
        mysql_db.get_session().commit()
        
        # Log audit entry
        mysql_db.log_action(
            user_id=user_obj.id,
            action="USER_LOGIN",
            resource_type="user",
            resource_id=str(user_obj.id),
            status="success"
        )
        
        logger.info(f"✓ User signed in: {request.username}")
        
        # Generate JWT token
        access_token = generate_jwt_token(
            {"user_id": user_obj.id, "username": user_obj.username},
            JWT_SECRET_KEY,
            timedelta(hours=JWT_EXPIRATION_HOURS)
        )
        
        return APIResponse(
            success=True,
            code="SUCCESS",
            data={
                "user": UserResponse(
                    id=user_obj.id,
                    username=user_obj.username,
                    email=user_obj.email,
                    created_at=user_obj.created_at,
                    last_login=user_obj.last_login
                ),
                "token": access_token
            },
            message="Login successful"
        )
    
    except AuthenticationError as e:
        logger.warning(f"Login failed: {str(e)}")
        raise HTTPException(
            status_code=e.status_code,
            detail=e.message
        )
    except Exception as e:
        logger.error(f"Login exception: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )


@app.post("/auth/logout", response_model=APIResponse)
async def logout(user_id: int = Depends(get_current_user)):
    """User logout"""
    try:
        if not mysql_db:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database connection failed"
            )
        
        # Log audit entry
        mysql_db.log_action(
            user_id=user_id,
            action="USER_LOGOUT",
            resource_type="user",
            resource_id=str(user_id),
            status="success"
        )
        
        logger.info(f"✓ User signed out: {user_id}")
        
        return APIResponse(
            success=True,
            code="SUCCESS",
            message="Logout successful"
        )
    except Exception as e:
        logger.error(f"Logout failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Logout failed"
        )


@app.get("/auth/verify", response_model=APIResponse)
async def verify_token(user_id: int = Depends(get_current_user)):
    """Validate token"""
    try:
        if not mysql_db:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database connection failed"
            )
        
        user_obj = mysql_db.get_user_by_id(user_id)
        if not user_obj:
            raise NotFoundError("User")
        
        return APIResponse(
            success=True,
            code="SUCCESS",
            data={
                "user": UserResponse(
                    id=user_obj.id,
                    username=user_obj.username,
                    email=user_obj.email
                )
            },
            message="Token valid"
        )
    except Exception as e:
        logger.error(f"Token validation failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token verification failed"
        )


@app.get("/users/profile", response_model=APIResponse)
async def get_profile(user_id: int = Depends(get_current_user)):
    """Fetch user profile"""
    try:
        if not mysql_db:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database connection failed"
            )
        
        user_obj = mysql_db.get_user_by_id(user_id)
        if not user_obj:
            raise NotFoundError("User")
        
        return APIResponse(
            success=True,
            code="SUCCESS",
            data={
                "user": UserResponse(
                    id=user_obj.id,
                    username=user_obj.username,
                    email=user_obj.email,
                    created_at=user_obj.created_at,
                    last_login=user_obj.last_login
                )
            }
        )
    except Exception as e:
        logger.error(f"Failed to fetch user profile: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user profile"
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5001)

