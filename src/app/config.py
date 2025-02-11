from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    google_cloud_project: str = "prod-data-enablement"
    force_cache_refresh: bool = False

    # Trend filtering settings
    max_daily_change: float = 300.0
    max_weekly_change: float = 300.0
    min_weekly_change: float = 0.01
    min_total_revenue: float = 10000.0

    # Trend score weights
    daily_change_weight: float = 0.1
    weekly_change_weight: float = 0.9

    excluded_categories: list[str] = ["religious & ceremonial"]

    class Config:
        case_sensitive = False
