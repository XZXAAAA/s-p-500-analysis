"""
Unit Tests for Auth Service
"""

import unittest
import sys
import os
from unittest.mock import Mock, patch, MagicMock

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from backend.shared.models import UserRegisterRequest, UserLoginRequest
from backend.shared.errors import ValidationError, AuthenticationError, ConflictError


class TestAuthService(unittest.TestCase):
    """Test cases for authentication service"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.valid_user_data = {
            "username": "testuser",
            "email": "test@example.com",
            "password": "SecurePass123!",
            "confirm_password": "SecurePass123!"
        }
        
        self.valid_login_data = {
            "username": "testuser",
            "password": "SecurePass123!"
        }
    
    def test_user_register_request_valid(self):
        """Test valid user registration request"""
        request = UserRegisterRequest(**self.valid_user_data)
        self.assertEqual(request.username, "testuser")
        self.assertEqual(request.email, "test@example.com")
    
    def test_user_register_request_invalid_email(self):
        """Test registration with invalid email"""
        invalid_data = self.valid_user_data.copy()
        invalid_data["email"] = "invalid-email"
        
        with self.assertRaises(Exception):  # Pydantic validation error
            UserRegisterRequest(**invalid_data)
    
    def test_user_register_request_short_username(self):
        """Test registration with short username"""
        invalid_data = self.valid_user_data.copy()
        invalid_data["username"] = "ab"  # Less than 3 characters
        
        with self.assertRaises(Exception):  # Pydantic validation error
            UserRegisterRequest(**invalid_data)
    
    def test_user_login_request_valid(self):
        """Test valid login request"""
        request = UserLoginRequest(**self.valid_login_data)
        self.assertEqual(request.username, "testuser")
        self.assertEqual(request.password, "SecurePass123!")
    
    def test_password_mismatch(self):
        """Test password confirmation mismatch"""
        invalid_data = self.valid_user_data.copy()
        invalid_data["confirm_password"] = "DifferentPass123!"
        
        # This should be caught in the service logic
        request = UserRegisterRequest(**invalid_data)
        self.assertNotEqual(request.password, request.confirm_password)


class TestPasswordValidation(unittest.TestCase):
    """Test password validation logic"""
    
    def test_validate_password_strength_valid(self):
        """Test valid password"""
        from backend.shared.utils import validate_password_strength
        
        self.assertTrue(validate_password_strength("SecurePass123!"))
        self.assertTrue(validate_password_strength("MyP@ssw0rd"))
    
    def test_validate_password_strength_too_short(self):
        """Test password too short"""
        from backend.shared.utils import validate_password_strength
        
        self.assertFalse(validate_password_strength("Short1!"))
    
    def test_validate_password_strength_no_uppercase(self):
        """Test password without uppercase"""
        from backend.shared.utils import validate_password_strength
        
        self.assertFalse(validate_password_strength("password123!"))
    
    def test_validate_password_strength_no_lowercase(self):
        """Test password without lowercase"""
        from backend.shared.utils import validate_password_strength
        
        self.assertFalse(validate_password_strength("PASSWORD123!"))
    
    def test_validate_password_strength_no_digit(self):
        """Test password without digit"""
        from backend.shared.utils import validate_password_strength
        
        self.assertFalse(validate_password_strength("SecurePass!"))
    
    def test_validate_password_strength_no_special(self):
        """Test password without special character"""
        from backend.shared.utils import validate_password_strength
        
        self.assertFalse(validate_password_strength("SecurePass123"))


class TestJWTToken(unittest.TestCase):
    """Test JWT token generation and verification"""
    
    def test_generate_jwt_token(self):
        """Test JWT token generation"""
        from backend.shared.utils import generate_jwt_token
        from datetime import timedelta
        
        data = {"user_id": 1, "username": "testuser"}
        secret = "test-secret-key"
        
        token = generate_jwt_token(data, secret, timedelta(hours=1))
        
        self.assertIsInstance(token, str)
        self.assertTrue(len(token) > 0)
    
    def test_verify_jwt_token_valid(self):
        """Test valid JWT token verification"""
        from backend.shared.utils import generate_jwt_token, verify_jwt_token
        from datetime import timedelta
        
        data = {"user_id": 1, "username": "testuser"}
        secret = "test-secret-key"
        
        token = generate_jwt_token(data, secret, timedelta(hours=1))
        payload = verify_jwt_token(token, secret)
        
        self.assertEqual(payload["user_id"], 1)
        self.assertEqual(payload["username"], "testuser")
    
    def test_verify_jwt_token_invalid_secret(self):
        """Test JWT token verification with wrong secret"""
        from backend.shared.utils import generate_jwt_token, verify_jwt_token
        from datetime import timedelta
        from fastapi import HTTPException
        
        data = {"user_id": 1, "username": "testuser"}
        secret = "test-secret-key"
        wrong_secret = "wrong-secret-key"
        
        token = generate_jwt_token(data, secret, timedelta(hours=1))
        
        with self.assertRaises(HTTPException):
            verify_jwt_token(token, wrong_secret)


class TestCustomErrors(unittest.TestCase):
    """Test custom error classes"""
    
    def test_validation_error(self):
        """Test ValidationError"""
        error = ValidationError("Invalid input")
        self.assertEqual(error.code, "VALIDATION_ERROR")
        self.assertEqual(error.status_code, 400)
    
    def test_authentication_error(self):
        """Test AuthenticationError"""
        error = AuthenticationError("Login failed")
        self.assertEqual(error.code, "AUTHENTICATION_ERROR")
        self.assertEqual(error.status_code, 401)
    
    def test_conflict_error(self):
        """Test ConflictError"""
        error = ConflictError("User already exists")
        self.assertEqual(error.code, "CONFLICT")
        self.assertEqual(error.status_code, 409)
    
    def test_error_to_dict(self):
        """Test error serialization"""
        error = ValidationError("Invalid input", {"field": "email"})
        error_dict = error.to_dict()
        
        self.assertFalse(error_dict["success"])
        self.assertEqual(error_dict["code"], "VALIDATION_ERROR")
        self.assertEqual(error_dict["message"], "Invalid input")
        self.assertEqual(error_dict["details"]["field"], "email")


if __name__ == '__main__':
    unittest.main()

