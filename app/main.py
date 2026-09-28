import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from app.api.v1.router import router as api_v1_router
from app.core.config import settings
from app.core.logging import setup_logging

# Initialize structured logging
setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
)


# Centralized global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception at {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "An internal server error occurred.",
            "error_type": type(exc).__name__,
        },
    )


# Register API v1 routes
app.include_router(api_v1_router, prefix="/api/v1")


@app.get("/", include_in_schema=False)
async def root():
    return {"message": "Service is running. Visit /docs for Swagger documentation."}