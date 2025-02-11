"""Unit tests for the in-memory cache functionality."""

import pytest
from datetime import datetime, timedelta
from app.database import InMemoryCache, CacheData


@pytest.fixture
def cache():
    """Create a fresh cache instance for each test."""
    return InMemoryCache(expiry_hours=0.0833)  # 5 minutes


def test_cache_initialization(cache):
    """Test that cache is properly initialized."""
    assert cache._cache is None
    assert cache.expiry_time == timedelta(hours=0.0833)


def test_cache_set_and_get(cache):
    """Test setting and getting cache data."""
    test_data = [{"test": "data"}]
    cache.set(test_data)
    assert cache.get() == test_data


def test_cache_expiration(cache):
    """Test that cache properly expires."""
    test_data = [{"test": "data"}]
    # Set cache with expired timestamp
    cache._cache = CacheData(
        data=test_data, timestamp=datetime.now() - timedelta(hours=1)
    )
    assert cache.get() is None


def test_cache_clear(cache):
    """Test clearing the cache."""
    test_data = [{"test": "data"}]
    cache.set(test_data)
    cache.clear()
    assert cache._cache is None
