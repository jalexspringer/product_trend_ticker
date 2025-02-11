"""Unit tests for the FastAPI endpoints."""

import pytest
from fastapi.testclient import TestClient
from app.main import app
import os

# Ensure we're using the correct static directory path
os.environ["STATIC_DIR"] = "src/app/static"


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


def test_health_check(client):
    """Test the health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["status"] == "healthy"


def test_get_trends(client):
    """Test the trends endpoint."""
    response = client.get("/api/trends")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_get_gainers(client):
    """Test the gainers endpoint."""
    response = client.get("/api/trends/gainers")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_get_losers(client):
    """Test the losers endpoint."""
    response = client.get("/api/trends/losers")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_filter_trends_invalid_category(client):
    """Test filtering trends with invalid category."""
    response = client.get("/api/trends/filter?category=invalid")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_get_categories(client):
    """Test getting available categories."""
    response = client.get("/api/trends/categories")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
