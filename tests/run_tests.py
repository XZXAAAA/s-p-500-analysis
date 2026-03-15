"""
Test Runner Script
Run all tests with coverage reporting
"""

import unittest
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def run_unit_tests():
    """Run all unit tests"""
    print("\n" + "="*60)
    print("Running Unit Tests")
    print("="*60 + "\n")
    
    loader = unittest.TestLoader()
    suite = loader.discover('tests/unit', pattern='test_*.py')
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


def run_integration_tests():
    """Run all integration tests"""
    print("\n" + "="*60)
    print("Running Integration Tests")
    print("="*60 + "\n")
    
    loader = unittest.TestLoader()
    suite = loader.discover('tests/integration', pattern='test_*.py')
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


def run_all_tests():
    """Run all tests"""
    print("\n" + "="*60)
    print("S&P 500 Sentiment Analysis - Test Suite")
    print("="*60)
    
    unit_success = run_unit_tests()
    integration_success = run_integration_tests()
    
    print("\n" + "="*60)
    print("Test Summary")
    print("="*60)
    print(f"Unit Tests: {'✓ PASSED' if unit_success else '✗ FAILED'}")
    print(f"Integration Tests: {'✓ PASSED' if integration_success else '✗ FAILED'}")
    print("="*60 + "\n")
    
    return unit_success and integration_success


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)

