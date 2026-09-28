import logging
import httpx
from app.core.config import settings

logger = logging.getLogger(__name__)


async def send_webhook_notification(payload: dict) -> None:
    """Sends an asynchronous POST request to the configured webhook URL when fresh data is fetched."""
    if not settings.WEBHOOK_URL or "replace-with-your-url" in settings.WEBHOOK_URL:
        logger.info("Webhook URL not configured or using placeholder; skipping.")
        return

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(settings.WEBHOOK_URL, json=payload)
            logger.info(f"Webhook delivered: status {response.status_code}")
    except Exception as exc:
        logger.error(f"Failed to deliver webhook notification: {exc}")