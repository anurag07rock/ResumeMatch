"""
Pytest configuration and global fixtures for ResumeMatch test suites.
"""
import pytest
from app.core.limiter import limiter


@pytest.fixture(autouse=True)
def reset_rate_limits():
    """
    Automatically resets SlowAPI in-memory rate limiting state before and after each test.
    Ensures that test executions run in complete isolation without unexpected 429 errors.
    """
    limiter.reset()
    yield
    limiter.reset()
