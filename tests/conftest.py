"""
Pytest configuration and shared fixtures
"""

import pytest
import sys
from pathlib import Path

# Add src to Python path
src_path = Path(__file__).parent.parent
sys.path.insert(0, str(src_path))


@pytest.fixture(scope="session")
def test_settings():
    """Test settings"""
    return {
        "JWT_SECRET_KEY": "test_secret_key_for_testing_only",
        "MONGODB_URL": "mongodb://localhost:27017/chembot_test",
        "REDIS_HOST": "localhost",
        "REDIS_PORT": 6379,
        "LLM_MODEL": "gpt-3.5-turbo",
    }

