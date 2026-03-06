import structlog
from fastapi import APIRouter
from pydantic import BaseModel

from api.dependencies import RedisDep

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    redis: str


@router.get("/health", response_model=HealthResponse)
async def health_check(redis: RedisDep) -> HealthResponse:
    try:
        await redis.ping()
        redis_status = "ok"
    except Exception:
        redis_status = "unavailable"
        logger.warning("health_check_redis_failed")

    return HealthResponse(status="ok", redis=redis_status)
