from unittest.mock import AsyncMock, patch
import httpx
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.cache import cache_service
from app.services.coingecko import coingecko_service
from app.services.webhook import send_webhook_notification

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
        with patch.object(coingecko_service, "check_health", new_callable=AsyncMock) as mock_health:
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
        with patch.object(coingecko_service, "check_health", new_callable=AsyncMock) as mock_health:
            mock_health.return_value = (False, None)
            response = await ac.get("/api/v1/health")
            assert response.status_code == 200
            data = response.json()
            assert data["external_service_status"] == "unreachable"
            assert data["external_service_version"] is None


@pytest.mark.asyncio
async def test_protected_endpoints_missing_or_invalid_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        assert (await ac.get("/api/v1/coins")).status_code == 401
        assert (await ac.get("/api/v1/categories")).status_code == 401
        assert (await ac.get("/api/v1/coins/markets", headers={"X-API-Key": "bad-key"})).status_code == 401


@pytest.mark.asyncio
async def test_list_coins_pagination_and_cache():
    mock_coins = [{"id": f"coin-{i}", "name": f"Coin {i}", "symbol": f"c{i}"} for i in range(25)]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        with patch.object(coingecko_service, "_fetch", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_coins
            
            res1 = await ac.get("/api/v1/coins?page_num=2&per_page=5", headers=AUTH_HEADERS)
            assert res1.status_code == 200
            data1 = res1.json()
            assert data1["page"] == 2
            assert data1["per_page"] == 5
            assert len(data1["data"]) == 5

            res2 = await ac.get("/api/v1/coins?page_num=1&per_page=5", headers=AUTH_HEADERS)
            assert res2.status_code == 200


@pytest.mark.asyncio
async def test_list_categories_pagination_and_cache():
    mock_cats = [{"category_id": f"cat-{i}", "name": f"Category {i}"} for i in range(15)]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        with patch.object(coingecko_service, "_fetch", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_cats

            res1 = await ac.get("/api/v1/categories?page_num=1&per_page=10", headers=AUTH_HEADERS)
            assert res1.status_code == 200
            assert len(res1.json()["data"]) == 10

            res2 = await ac.get("/api/v1/categories?page_num=1&per_page=5", headers=AUTH_HEADERS)
            assert res2.status_code == 200


@pytest.mark.asyncio
async def test_market_data_validation():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/api/v1/coins/markets", headers=AUTH_HEADERS)
        assert res.status_code == 400


@pytest.mark.asyncio
async def test_market_data_success_and_cache_branch():
    mock_records = [{"id": "bitcoin", "current_price": 95000.0}]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        with patch.object(coingecko_service, "_fetch", new_callable=AsyncMock) as mock_fetch, \
             patch("app.services.coingecko.send_webhook_notification", new_callable=AsyncMock) as mock_webhook:
            mock_fetch.return_value = mock_records

            res1 = await ac.get("/api/v1/coins/markets?coin_id=bitcoin&category=layer-1", headers=AUTH_HEADERS)
            assert res1.status_code == 200
            assert res1.json()["currency"] == "CAD"
            assert mock_webhook.called

            mock_webhook.reset_mock()
            res2 = await ac.get("/api/v1/coins/markets?coin_id=bitcoin&category=layer-1", headers=AUTH_HEADERS)
            assert res2.status_code == 200
            assert not mock_webhook.called


@pytest.mark.asyncio
async def test_coingecko_service_http_errors():
    req = httpx.Request("GET", "http://test")

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = httpx.Response(429, request=req)
        with pytest.raises(Exception) as exc:
            await coingecko_service._fetch("/test")
        assert exc.value.status_code == 429

    with patch("httpx.AsyncClient.get", side_effect=httpx.TimeoutException("timeout")):
        with pytest.raises(Exception) as exc:
            await coingecko_service._fetch("/test")
        assert exc.value.status_code == 504

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = httpx.Response(500, request=req)
        with pytest.raises(Exception) as exc:
            await coingecko_service._fetch("/test")
        assert exc.value.status_code == 502

    with patch("httpx.AsyncClient.get", side_effect=httpx.RequestError("offline", request=req)):
        with pytest.raises(Exception) as exc:
            await coingecko_service._fetch("/test")
        assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_coingecko_health_network_failure():
    with patch("httpx.AsyncClient.get", side_effect=Exception("network down")):
        status_ok, ver = await coingecko_service.check_health()
        assert status_ok is False
        assert ver is None


@pytest.mark.asyncio
async def test_webhook_delivery_paths():
    # Test valid webhook delivery by patching WEBHOOK_URL to a non-placeholder value
    with patch("app.services.webhook.settings.WEBHOOK_URL", "https://api.custom-webhook.com/alerts"):
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = httpx.Response(200, request=httpx.Request("POST", "http://test"))
            await send_webhook_notification({"test": "data"})
            assert mock_post.called

        with patch("httpx.AsyncClient.post", side_effect=Exception("webhook failed")):
            await send_webhook_notification({"test": "data"})

    # Test skipped path when placeholder is present
    with patch("app.services.webhook.settings.WEBHOOK_URL", "https://webhook.site/replace-with-your-url"):
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            await send_webhook_notification({"test": "data"})
            assert not mock_post.called


@pytest.mark.asyncio
async def test_global_exception_handler():
    # Pass raise_app_exceptions=False so ASGITransport routes errors to FastAPI's 500 handler
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        with patch.object(coingecko_service, "check_health", side_effect=RuntimeError("unexpected crash")):
            res = await ac.get("/api/v1/health")
            assert res.status_code == 500
            assert res.json()["error_type"] == "RuntimeError"
