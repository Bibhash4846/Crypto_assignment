from typing import Optional
from fastapi import HTTPException, Query, Security, status
from fastapi.security import APIKeyHeader
from app.core.config import settings

# Enforces API key verification via request header 'X-API-Key'
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(api_key: Optional[str] = Security(api_key_header)) -> str:
    if not api_key or api_key != settings.API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API Key. Provide a valid 'X-API-Key' header.",
        )
    return api_key

#for pagination of results
class PaginationParams:
    def __init__(
        self,
        page_num: int = Query(1, ge=1, description="Page number (starts at 1)"),
        per_page: int = Query(10, ge=1, le=250, description="Items per page"),
    ):
        self.page_num = page_num
        self.per_page = per_page

    def paginate(self, items: list) -> list:
        start = (self.page_num - 1) * self.per_page
        end = start + self.per_page
        return items[start:end]