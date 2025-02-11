"""Shared test fixtures and configuration."""

import pytest
from typing import List, Dict, Any
from app.database import cache


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear the cache before each test."""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def sample_trends_data() -> List[Dict[str, Any]]:
    """Sample trends data for testing."""
    return [
        {
            "category": "Electronics",
            "country": "US",
            "product_name": "Test Product 1",
            "weekly_revenue": 1000.0,
            "weekly_revenue_change": 50.0,
            "weekly_units_sold": 100,
            "weekly_units_sold_change": 25.0,
        },
        {
            "category": "Clothing",
            "country": "UK",
            "product_name": "Test Product 2",
            "weekly_revenue": 500.0,
            "weekly_revenue_change": -20.0,
            "weekly_units_sold": 50,
            "weekly_units_sold_change": -10.0,
        },
    ]


@pytest.fixture
def mock_fetch_trends(monkeypatch, sample_trends_data):
    """Mock the fetch_trends function."""

    async def mock_fetch(*args, **kwargs):
        return sample_trends_data

    from app import database

    monkeypatch.setattr(database, "fetch_trends", mock_fetch)
