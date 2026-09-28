from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # swagger docs info
    APP_NAME: str = "Crypto Market Service"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    API_KEY: str = "secret-api-key-test" # api key client must pass in X-API-Key header

    # upstream coingecko details
    COINGECKO_BASE_URL: str = "https://api.coingecko.com/api/v3"
    COINGECKO_API_KEY: str = ""
    CACHE_TTL_SECONDS: int = 60 # cache expiry in seconds
    WEBHOOK_URL: str = "https://webhook.site/replace-with-your-url" # webhook receiver for cache-miss alerts

    # pull from local .env; ignore extra keys so it won't crash
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

settings = Settings() # singleton instance used across the app