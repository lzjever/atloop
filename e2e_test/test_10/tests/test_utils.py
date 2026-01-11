"""
Test module for utils.py
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.utils import helper_function


def test_helper_function():
    """Test helper_function with various inputs."""
    # Test normal input
    result = helper_function("test")
    assert result == "Processed: test"
    
    # Test empty string
    result = helper_function("")
    assert result == "Processed: "
    
    # Test with numbers
    result = helper_function("123")
    assert result == "Processed: 123"
    
    print("All tests passed!")


if __name__ == "__main__":
    test_helper_function()
