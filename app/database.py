from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import csv
import logging
import os

# from .queries import main_trend_query

logger = logging.getLogger(__name__)

@dataclass
class CacheData:
    """Data structure for cached items."""
    data: List[Dict[str, Any]]
    timestamp: datetime

class InMemoryCache:
    """Thread-safe in-memory cache with expiration."""
    
    def __init__(self, expiry_hours: int = 0.0833):
        self._cache: Optional[CacheData] = None
        self.expiry_time = timedelta(hours=expiry_hours)
    
    @property
    def is_valid(self) -> bool:
        """Check if cache is valid and not expired."""
        return (
            self._cache is not None 
            and datetime.now() - self._cache.timestamp <= self.expiry_time
        )
    
    def get(self) -> Optional[List[Dict[str, Any]]]:
        """Get cached data if valid."""
        return self._cache.data if self.is_valid else None
    
    def set(self, data: List[Dict[str, Any]]) -> None:
        """Set new cache data."""
        self._cache = CacheData(data=data, timestamp=datetime.now())
    
    def clear(self) -> None:
        """Clear cache data."""
        self._cache = None

# Initialize the in-memory cache
cache = InMemoryCache()

"""
Example BigQuery implementation for production use:

from google.cloud import bigquery
from google.oauth2 import service_account
import json

@lru_cache(maxsize=1)
def get_bigquery_client() -> bigquery.Client:
    try:
        # First try Heroku-style environment credentials
        if 'BQ_CREDENTIALS' in os.environ:
            credentials_info = json.loads(os.environ['BQ_CREDENTIALS'])
            credentials = service_account.Credentials.from_service_account_info(credentials_info)
        
        # Then try local file-based credentials
        elif os.path.exists('bq.json'):
            credentials = service_account.Credentials.from_service_account_file('bq.json')
        
        # Finally try environment variable path
        elif 'GOOGLE_APPLICATION_CREDENTIALS' in os.environ:
            credentials = service_account.Credentials.from_service_account_file(
                os.environ['GOOGLE_APPLICATION_CREDENTIALS']
            )
        
        else:
            raise ValueError(
                "No BigQuery credentials found. Either set BQ_CREDENTIALS environment variable, "
                "provide a bq.json file in the root directory, "
                "or set GOOGLE_APPLICATION_CREDENTIALS environment variable."
            )
        
        return bigquery.Client(credentials=credentials, project=credentials.project_id)
    except Exception as e:
        logger.error(f"Error creating BigQuery client: {str(e)}", exc_info=True)
        raise
"""

def convert_numeric_values(row: Dict[str, Any]) -> Dict[str, Any]:
    """Convert string numeric values to float."""
    numeric_fields = [
        'revenue_daily_change', 'revenue_weekly_change', 'revenue_monthly_change',
        'commission_daily_change', 'commission_weekly_change', 'commission_monthly_change'
    ]
    for field in numeric_fields:
        if field in row and row[field]:
            try:
                row[field] = float(row[field])
            except (ValueError, TypeError):
                row[field] = 0.0
    return row

async def fetch_trends(force_refresh: bool = False) -> List[Dict[str, Any]]:
    """Fetch trends data from local CSV with in-memory caching."""
    try:
        if not force_refresh:
            cached_data = cache.get()
            if cached_data:
                logger.info("Found cached data")
                return cached_data

        logger.info("Reading from local CSV" + (" (forced refresh)" if force_refresh else ""))
        
        # Read from local CSV file
        csv_path = os.path.join(os.path.dirname(__file__), 'data', 'example_data.csv')
        results = []
        
        with open(csv_path, 'r', newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                # Convert numeric string values to float
                processed_row = convert_numeric_values(row)
                results.append(processed_row)
        
        if not results:
            logger.warning("CSV file contained no results")
            return []
        
        # Sort results by absolute value of revenue_weekly_change
        results.sort(key=lambda x: abs(x.get('revenue_weekly_change', 0)), reverse=True)
        
        cache.set(results)
        logger.info(f"Successfully cached {len(results)} records in memory")
        
        return results
            
    except Exception as e:
        logger.error(f"Error in fetch_trends: {str(e)}", exc_info=True)
        return []