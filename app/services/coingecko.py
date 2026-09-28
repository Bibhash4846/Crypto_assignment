import logging
from typing import Any, Optional, Tuple
import httpx
from fastapi import HTTPException, status
from app.core.config import settings
from app.services.cache import cache_service
from app.services.webhook import send_webhook_notification

logger = logging.getLogger(__name__)


class CoinGeckoService:
    def __init__(self):
        self.base_url = settings.COINGECKO_BASE_URL

    async def _fetch(self, path: str, params: Optional[dict] = None) -> Any:
        """Fetch data from CoinGecko and handle common API errors."""
        url = f"{self.base_url}{path}"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(url, params=params)

                # CoinGecko blocks requests when the rate limit is reached.
                if res.status_code == 429:
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail="CoinGecko rate limit exceeded. Please retry shortly.",
                    )

                res.raise_for_status()
                return res.json()

        except httpx.TimeoutException:
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="External cryptocurrency API request timed out.",
            )
        except httpx.HTTPStatusError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"External cryptocurrency API error: {exc.response.status_code}",
            )
        except httpx.RequestError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="External cryptocurrency service is unreachable.",
            )

    async def check_health(self) -> Tuple[bool, Optional[str]]:
        """Check whether CoinGecko is reachable."""
        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                res = await client.get(f"{self.base_url}/ping")

                if res.status_code == 200:
                    data = res.json()
                    version = data.get("gecko_says", "v3")
                    return True, version

                return False, None

        except Exception:
            return False, None

    async def get_all_coins(self) -> list[dict]:
        cache_key = "all_coins"
        cached = await cache_service.get(cache_key)

        # Return cached data instead of calling CoinGecko again.
        if cached:
            return cached

        data = await self._fetch("/coins/list")

        # Keep only the fields our application needs.
        clean_coins = [
            {"id": item["id"], "name": item["name"], "symbol": item["symbol"]}
            for item in data
        ]

        await cache_service.set(cache_key, clean_coins)
        return clean_coins

    async def get_all_categories(self) -> list[dict]:
        cache_key = "all_categories"
        cached = await cache_service.get(cache_key)

        if cached:
            return cached

        data = await self._fetch("/coins/categories/list")
        await cache_service.set(cache_key, data)
        return data

    async def get_markets(
        self, coin_id: Optional[str] = None, category: Optional[str] = None
    ) -> list[dict]:
        cache_key = f"markets_cad_{coin_id}_{category}"
        cached = await cache_service.get(cache_key)

        if cached:
            return cached

        params = {"vs_currency": "cad"}

        if coin_id:
            params["ids"] = coin_id
        if category:
            params["category"] = category

        data = await self._fetch("/coins/markets", params=params)
        await cache_service.set(cache_key, data)

        # Notify the webhook only when fresh data is fetched.
        await send_webhook_notification(
            {
                "event": "market_data_fetched",
                "filters": {
                    "coin_id": coin_id,
                    "category": category,
                    "currency": "cad",
                },
                "results_count": len(data),
            }
        )

        return data


coingecko_service = CoinGeckoService()