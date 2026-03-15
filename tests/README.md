# Test Suite Documentation

## Overview

This directory contains the complete test suite for the S&P 500 Stock Sentiment Analysis application.

## Test Structure

```
tests/
├── unit/                       # Unit tests
│   ├── test_auth_service.py   # Authentication service tests
│   ├── test_data_service.py   # Data service tests
│   └── test_database_managers.py  # Database manager tests
├── integration/                # Integration tests
│   └── test_api_endpoints.py  # API endpoint tests
├── run_tests.py               # Test runner script
└── README.md                  # This file
```

## Running Tests

### Run All Tests

```bash
# From project root
python tests/run_tests.py
```

### Run Unit Tests Only

```bash
python -m unittest discover tests/unit
```

### Run Integration Tests Only

```bash
python -m unittest discover tests/integration
```

### Run Specific Test File

```bash
python -m unittest tests/unit/test_auth_service.py
```

### Run Specific Test Class

```bash
python -m unittest tests.unit.test_auth_service.TestAuthService
```

### Run Specific Test Method

```bash
python -m unittest tests.unit.test_auth_service.TestAuthService.test_user_register_request_valid
```

## Test Coverage

### Unit Tests

- **Authentication Service** (15 tests)
  - User registration validation
  - Login validation
  - Password strength validation
  - JWT token generation and verification
  - Custom error handling

- **Data Service** (10 tests)
  - Sentiment data model validation
  - API response format
  - Data caching logic
  - Sentiment score calculations

- **Database Managers** (12 tests)
  - MySQL manager initialization
  - DynamoDB manager operations
  - ClickHouse query validation
  - Data sync pipeline

### Integration Tests

- **API Endpoints** (15 tests)
  - Authentication endpoints
  - Data service endpoints
  - Visualization endpoints
  - API Gateway routing
  - End-to-end user flows

## Test Requirements

Install test dependencies:

```bash
pip install -r requirements.txt
```

Additional testing packages (optional):

```bash
pip install pytest pytest-cov coverage
```

## Writing New Tests

### Unit Test Template

```python
import unittest

class TestYourFeature(unittest.TestCase):
    """Test your feature"""
    
    def setUp(self):
        """Set up test fixtures"""
        pass
    
    def test_something(self):
        """Test something specific"""
        # Arrange
        expected = "result"
        
        # Act
        actual = your_function()
        
        # Assert
        self.assertEqual(actual, expected)
    
    def tearDown(self):
        """Clean up after tests"""
        pass
```

### Integration Test Template

```python
import unittest
from fastapi.testclient import TestClient

class TestAPIIntegration(unittest.TestCase):
    """Integration test for API"""
    
    def setUp(self):
        """Set up test client"""
        # self.client = TestClient(app)
        pass
    
    def test_endpoint(self):
        """Test API endpoint"""
        # response = self.client.get("/api/endpoint")
        # self.assertEqual(response.status_code, 200)
        pass
```

## Best Practices

1. **Test Naming**: Use descriptive names starting with `test_`
2. **Isolation**: Each test should be independent
3. **Mocking**: Use mocks for external dependencies
4. **Coverage**: Aim for >80% code coverage
5. **Documentation**: Add docstrings to all test methods
6. **Assertions**: Use appropriate assertion methods
7. **Setup/Teardown**: Use setUp() and tearDown() for common operations

## Continuous Integration

Tests are automatically run on:
- Pull requests
- Commits to main branch
- Before deployment

## Test Reports

Test results are saved in:
- `test-results/` - JUnit XML format
- `coverage/` - Coverage reports

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure project root is in PYTHONPATH
2. **Database Errors**: Use test database or mocks
3. **Async Tests**: Use appropriate async test runners

### Debug Mode

Run tests with verbose output:

```bash
python -m unittest -v tests/unit/test_auth_service.py
```

## Contributing

When adding new features:
1. Write tests first (TDD)
2. Ensure all tests pass
3. Maintain >80% coverage
4. Update this documentation

## Contact

For questions about tests, contact the development team.

