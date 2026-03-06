from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from api.dependencies import close_redis, get_redis, init_redis
from api.middleware.request_id import RequestIDMiddleware
from api.redis_ops import setup_stream
from api.routes import buy, health, metrics
from shared.config import settings
from shared.logging import configure_logging
from shared.lua_scripts import lua_scripts

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    configure_logging()
    await init_redis()
    redis = await get_redis()
    await lua_scripts.load(redis)
    logger.info("lua_scripts_loaded")
    await setup_stream(redis)
    logger.info("stream_ready", stream=settings.orders_stream, group=settings.orders_consumer_group)
    logger.info("startup_complete", service="flash-sale-api")
    yield
    await close_redis()
    logger.info("shutdown_complete", service="flash-sale-api")


app = FastAPI(
    title="Flash Sale API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(RequestIDMiddleware)

app.include_router(health.router)
app.include_router(buy.router)
app.include_router(metrics.router)
