from unittest.mock import AsyncMock, patch
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

AUTH_HEADERS = {"X-API-Key": "secret-api-key-test"}


@pytest.mark.asyncio
async def test_root_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/")
        assert response.status_code == 200
        assert "Swagger documentation" in response.json()["message"]


@pytest.mark.asyncio
async def test_health_check_success():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        with patch("app.services.coingecko.coingecko_service.check_health", new_callable=AsyncMock) as mock_health:
            mock_health.return_value = (True, "v3")
            response = await ac.get("/api/v1/health")
            assert response.status_code == 200
            data = response.json()
            assert data["app_status"] == "healthy"
            assert data["external_service_status"] == "reachable"
            assert data["external_service_version"] == "v3"


@pytest.mark.asyncio
async def test_health_check_external_unreachable():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        with patch("app.services.coingecko.coingecko_service.check_health", new_callable=AsyncMock) as mock_health:
            mock_health.return_value = (False, None)
            response = await ac.get("/api/v1/health")
            assert response.status_code == 200
            data = response.json()
            assert data["external_service_status"] == "unreachable"
            assert data["external_service_version"] is None


@pytest.mark.asyncio
async def test_protected_endpoints_missing_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res_coins = await ac.get("/api/v1/coins")
        assert res_coins.status_code == 401

        res_cat = await ac.get("/api/v1/categories")
        assert res_cat.status_code == 401

        res_markets = await ac.get("/api/v1/coins/markets", headers={"X-API-Key": "wrong-key"})
        assert res_markets.status_code == 401


@pytest.mark.asyncio
async def test_list_coins_with_pagination():
    mock_coins = [
        {"id": f"coin-{i}", "name": f"Coin {i}", "symbol": f"c{i}"}
        for i in range(25)
    ]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        with patch("app.services.coingecko.coingecko_service.get_all_coins", new_callable=AsyncMock) as mock_coins_call:
            mock_coins_call.return_value = mock_coins
            response = await ac.get("/api/v1/coins?page_num=2&per_page=5", headers=AUTH_HEADERS)
            assert response.status_code == 200
            data = response.json()
            assert data["page"] == 2
            assert data["per_page"] == 5
            assert data["total_items"] == 25
            assert len(data["data"]) == 5
            assert data["data"][0]["id"] == "coin-5"


@pytest.mark.asyncio
async def test_list_categories_with_pagination():
    mock_cats = [{"category_id": f"cat-{i}", "name": f"Category {i}"} for i in range(12)]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        with patch("app.services.coingecko.coingecko_service.get_all_categories", new_callable=AsyncMock) as mock_cat_call:
            mock_cat_call.return_value = mock_cats
            response = await ac.get("/api/v1/categories?page_num=1&per_page=10", headers=AUTH_HEADERS)
            assert response.status_code == 200
            data = response.json()
            assert data["page"] == 1
            assert len(data["data"]) == 10


@pytest.mark.asyncio
async def test_market_data_validation_error_when_no_params():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/v1/coins/markets", headers=AUTH_HEADERS)
        assert response.status_code == 400
        assert "At least one query parameter" in response.json()["detail"]


@pytest.mark.asyncio
async def test_market_data_success_and_webhook_trigger():
    mock_market_records = [
        {"id": "bitcoin", "name": "Bitcoin", "current_price": 98500.0, "currency": "cad"}
    ]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        with patch("app.services.coingecko.coingecko_service._fetch", new_callable=AsyncMock) as mock_fetch, \
             patch("app.services.coingecko.send_webhook_notification", new_callable=AsyncMock) as mock_webhook:
            mock_fetch.return_value = mock_market_records

            response = await ac.get("/api/v1/coins/markets?coin_id=bitcoin", headers=AUTH_HEADERS)
            assert response.status_code == 200
            payload = response.json()
            assert payload["currency"] == "CAD"
            assert payload["total_items"] == 1
            assert payload["data"][0]["id"] == "bitcoin"
            assert mock_webhook.called