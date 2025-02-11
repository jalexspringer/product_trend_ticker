# app/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from fastapi.templating import Jinja2Templates
from fastapi import HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from typing import List, Dict, Any
from functools import lru_cache
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from prometheus_fastapi_instrumentator import Instrumentator
import time

from app.database import fetch_trends, cache

import logging
import os

# Initialize logging with more detail for production
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Suppress specific HTTP server warnings
uvicorn_logger = logging.getLogger("uvicorn.error")
uvicorn_logger.setLevel(logging.ERROR)

# Setup rate limiter
limiter = Limiter(key_func=get_remote_address)

# Setup scheduler
scheduler = AsyncIOScheduler()

# Get environment variables
FORCE_CACHE_REFRESH = os.getenv('FORCE_CACHE_REFRESH', 'false').lower() == 'true'
ENVIRONMENT = os.getenv('ENVIRONMENT', 'production')
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', '*').split(',')

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        # Perform initial data fetch
        logger.info("Initiating first BigQuery fetch...")
        initial_data = await fetch_trends(force_refresh=FORCE_CACHE_REFRESH)
        if not initial_data:
            logger.error("Initial data fetch returned empty result")
        else:
            logger.info(f"Successfully fetched initial data with {len(initial_data)} records")
        
        # Schedule daily data fetch at midnight
        scheduler.add_job(
            fetch_trends,
            'cron',
            hour=0,
            minute=0,
            kwargs={'force_refresh': True}
        )
        scheduler.start()
        logger.info("Scheduler started successfully")
        
        yield
        
    except Exception as e:
        logger.error(f"Startup error: {str(e)}", exc_info=True)
        raise
    finally:
        if scheduler.running:
            scheduler.shutdown()

app = FastAPI(
    title="Impact Trending Products",
    description="Real-time product category trends dashboard",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=None if ENVIRONMENT == 'production' else "/docs",
    redoc_url=None if ENVIRONMENT == 'production' else "/redoc",
    root_path=os.getenv('ROOT_PATH', '')
)

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static_files")

# Configure templates with custom functions
templates = Jinja2Templates(directory="app/templates")
templates.env.globals["url_for"] = app.url_path_for

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_HOSTS if '*' not in ALLOWED_HOSTS else ["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Setup metrics
Instrumentator().instrument(app).expose(app)

# Exception handlers
@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return _rate_limit_exceeded_handler(request, exc)

@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response

# Enhanced health check endpoint
@app.get("/health")
@limiter.exempt
async def health_check():
    try:
        # Check if we can fetch data
        trends_data = await fetch_trends()
        if not trends_data:
            return Response(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content="Data service unavailable"
            )
        return {
            "status": "healthy",
            "cache_status": "valid" if cache.is_valid else "invalid",
            "data_count": len(trends_data)
        }
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return Response(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content="Service unhealthy"
        )

@app.get("/")
async def home(request: Request):
    """Render the home page with initial data."""
    trends_data = await fetch_trends()
    filtered_data = await filter_trend_data(trends_data, "all", "US")
    
    gainers = get_sorted_trends(filtered_data, ascending=False)
    losers = get_sorted_trends(filtered_data, ascending=True)
    
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "gainers": gainers,
            "losers": losers
        }
    )

@app.get("/api/trends")
async def get_trends():
    logger.info("Fetching trends data...")
    trends_data = await fetch_trends()
    if not trends_data:
        logger.error("No trends data returned from fetch")
        return []
    logger.info(f"Successfully retrieved {len(trends_data)} trend records")
    return trends_data

async def filter_trend_data(
    trends_data: List[Dict[str, Any]], 
    category: str = "all", 
    country: str = "US"
) -> List[Dict[str, Any]]:
    """Filter trends data by category and country."""
    filtered_data = trends_data
    if category != "all":
        filtered_data = [t for t in filtered_data if t['product_category_level_1'] == category]
    return [t for t in filtered_data if t['campaign_country'] == country]

def get_sorted_trends(
    trends_data: List[Dict[str, Any]], 
    ascending: bool = True
) -> List[Dict[str, Any]]:
    """Sort trends by weekly revenue change."""
    def filter_func(x):
        return x['revenue_weekly_change'] < 0 if ascending else x['revenue_weekly_change'] > 0
    return sorted(
        [t for t in trends_data if filter_func(t)],
        key=lambda x: x['revenue_weekly_change'],
        reverse=not ascending
    )

@lru_cache(maxsize=100)
def get_cached_trend_key(category: str, country: str, trend_type: str) -> str:
    """Generate a cache key for trends filtering.
    
    Args:
        category: Product category
        country: Country code
        trend_type: Either 'gainers' or 'losers'
    
    Returns:
        Cache key string
    """
    return f"{category}:{country}:{trend_type}"

@app.get("/api/trends/gainers")
async def get_gainers(request: Request, category: str = "all", country: str = "US"):
    """Get trending products with positive revenue change."""
    _ = get_cached_trend_key(category, country, "gainers")  # Cache the key combination
    trends_data = await fetch_trends()
    filtered_data = await filter_trend_data(trends_data, category, country)
    gainers = get_sorted_trends(filtered_data, ascending=False)
    return templates.TemplateResponse(
        "components/cards/trend_card.html", 
        {"request": request, "trend": gainers[0] if gainers else None}
    )

@app.get("/api/trends/losers")
async def get_losers(request: Request, category: str = "all", country: str = "US"):
    """Get trending products with negative revenue change."""
    _ = get_cached_trend_key(category, country, "losers")  # Cache the key combination
    trends_data = await fetch_trends()
    filtered_data = await filter_trend_data(trends_data, category, country)
    losers = get_sorted_trends(filtered_data, ascending=True)
    return templates.TemplateResponse(
        "components/cards/trend_card.html", 
        {"request": request, "trend": losers[0] if losers else None}
    )

@app.post("/api/trends/refresh")
async def refresh_trends(force: bool = False):
    """
    Force refresh the trends data cache
    
    Args:
        force (bool): If True, bypass cache and fetch fresh data from BigQuery
    """
    try:
        if force:
            cache.clear()
        trends_data = await fetch_trends(force_refresh=force)
        return {
            "message": "Cache refreshed successfully",
            "force_refresh": force,
            "records_count": len(trends_data)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/trends/categories")
async def get_categories(request: Request):
    """Get unique categories from trends data."""
    trends_data = await fetch_trends()
    categories = sorted(set(t['product_category_level_1'] for t in trends_data))
    return templates.TemplateResponse(
        "categories.html",
        {
            "request": request,
            "categories": categories
        }
    )

@app.get("/api/trends/filter")
async def filter_trends(request: Request, category: str = "all", country: str = "US"):
    """Filter trends by category and country."""
    trends_data = await fetch_trends()
    filtered_data = await filter_trend_data(trends_data, category, country)
    
    gainers = get_sorted_trends(filtered_data, ascending=False)
    losers = get_sorted_trends(filtered_data, ascending=True)
    
    return templates.TemplateResponse(
        "layouts/trends_grid.html",
        {
            "request": request,
            "gainers": gainers,
            "losers": losers
        }
    )

@app.get("/api/trends/ticker")
async def get_ticker_updates(request: Request):
    trends_data = await fetch_trends()
    
    # Split into gainers and losers
    gainers = sorted(
        [t for t in trends_data if t['revenue_weekly_change'] > 0],
        key=lambda x: x['revenue_weekly_change'],
        reverse=True
    )[:5]  # Top 5 gainers
    
    losers = sorted(
        [t for t in trends_data if t['revenue_weekly_change'] < 0],
        key=lambda x: x['revenue_weekly_change']
    )[:5]  # Top 5 losers
    
    # Combine and shuffle to mix gainers and losers
    significant_trends = gainers + losers
    
    return templates.TemplateResponse(
        "ticker.html",
        {"request": request, "trends": significant_trends}
    )

@app.get("/api/trends/countries")
async def get_countries(request: Request):
    """Get unique countries from trends data."""
    trends_data = await fetch_trends()
    countries = sorted(set(t['campaign_country'] for t in trends_data))
    return templates.TemplateResponse(
        "countries.html",
        {
            "request": request,
            "countries": countries
        }
    )

@app.get("/share-modal")
async def share_modal(request: Request):
    """Render the share modal template."""
    return templates.TemplateResponse(
        "components/modals/share_modal.html",
        {"request": request}
    )