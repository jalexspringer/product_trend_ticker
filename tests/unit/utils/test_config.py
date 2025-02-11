"""Tests for configuration settings."""

import pytest
from app.config import Settings


def test_default_settings():
    """Test that default settings are loaded correctly."""
    settings = Settings()

    # Test project settings
    assert settings.google_cloud_project == "example_project"
    assert settings.force_cache_refresh is False

    # Test trend filtering settings
    assert settings.max_daily_change == 300.0
    assert settings.max_weekly_change == 300.0
    assert settings.min_weekly_change == 0.01
    assert settings.min_total_revenue == 10000.0

    # Test trend score weights
    assert settings.daily_change_weight == 0.1
    assert settings.weekly_change_weight == 0.9
    assert (
        pytest.approx(settings.daily_change_weight + settings.weekly_change_weight)
        == 1.0
    )

    # Test excluded categories
    assert "religious & ceremonial" in settings.excluded_categories


def test_settings_override():
    """Test that settings can be overridden through environment variables."""
    settings = Settings(
        google_cloud_project="test-project",
        max_daily_change=200.0,
        excluded_categories=["test-category"],
    )

    assert settings.google_cloud_project == "test-project"
    assert settings.max_daily_change == 200.0
    assert settings.excluded_categories == ["test-category"]
