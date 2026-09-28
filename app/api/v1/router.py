from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from app.api.deps import PaginationParams, verify_api_key
from app.core.config import settings
from app.schemas.responses import HealthResponse, PaginatedResponse
from app.services.coingecko import coingecko_service

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    # Check if the external CoinGecko service is reachable
    reachable, ext_version = await coingecko_service.check_health()
    return HealthResponse(
        app_status="healthy",
        app_version=settings.APP_VERSION,
        external_service_status="reachable" if reachable else "unreachable",
        external_service_version=ext_version,
    )


@router.get(
    "/coins",
    response_model=PaginatedResponse,
    dependencies=[Depends(verify_api_key)],
    tags=["Coins"],
)
async def list_coins(pagination: PaginationParams = Depends()):
    # Get all coins and return the requested page
    coins = await coingecko_service.get_all_coins()
    paginated_data = pagination.paginate(coins)
    return PaginatedResponse(
        page=pagination.page_num,
        per_page=pagination.per_page,
        total_items=len(coins),
        data=paginated_data,
    )


@router.get(
    "/categories",
    response_model=PaginatedResponse,
    dependencies=[Depends(verify_api_key)],
    tags=["Coins"],
)
async def list_categories(pagination: PaginationParams = Depends()):
    # Get all categories and apply pagination
    categories = await coingecko_service.get_all_categories()
    paginated_data = pagination.paginate(categories)
    return PaginatedResponse(
        page=pagination.page_num,
        per_page=pagination.per_page,
        total_items=len(categories),
        data=paginated_data,
    )


@router.get(
    "/coins/markets",
    dependencies=[Depends(verify_api_key)],
    tags=["Markets"],
)
async def get_markets(
    coin_id: Optional[str] = Query(None, description="Cryptocurrency Coin ID (e.g., 'bitcoin')"),
    category: Optional[str] = Query(None, description="Cryptocurrency Category (e.g., 'decentralized-finance-defi')"),
    pagination: PaginationParams = Depends(),
):
    # Require at least one filter for market data
    if not coin_id and not category:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one query parameter ('coin_id' or 'category') must be provided.",
        )

    markets = await coingecko_service.get_markets(coin_id=coin_id, category=category)

    # Apply pagination to the market results
    paginated_data = pagination.paginate(markets)

    return {
        "page": pagination.page_num,
        "per_page": pagination.per_page,
        "currency": "CAD",
        "total_items": len(markets),
        "data": paginated_data,
    }

