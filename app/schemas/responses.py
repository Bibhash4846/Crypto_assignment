from typing import Any, List, Optional
from pydantic import BaseModel


class HealthResponse(BaseModel):
    # health check payload reporting local api and upstream coingecko status
    app_status: str
    app_version: str
    external_service_status: str
    external_service_version: Optional[str] = None


class CoinItem(BaseModel):
    # minimal coin metadata shape for listings
    id: str
    name: str
    symbol: str


class CategoryItem(BaseModel):
    # category identifier and label from coingecko
    category_id: str
    name: str


class PaginatedResponse(BaseModel):
    # generic paginated wrapper for lists of coins or categories
    page: int
    per_page: int
    total_items: int
    data: List[Any]