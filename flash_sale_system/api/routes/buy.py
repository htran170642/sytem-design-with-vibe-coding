import uuid

import structlog
from fastapi import APIRouter, HTTPException, status

from api.circuit_breaker import redis_circuit_breaker
from api.dependencies import RedisDep
from api.rate_limiter import RateLimiter
from api.redis_ops import (
    claim_idempotency,
    decrement_stock,
    enqueue_order,
    get_idempotency,
    release_idempotency,
    resolve_idempotency,
)
from api.schemas import BuyRequest, BuyResponse
from shared.metrics import REQUEST_COUNT, STOCK_REMAINING

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["flash-sale"])

_rate_limiter: RateLimiter | None = None


def get_rate_limiter(redis: RedisDep) -> RateLimiter:  # type: ignore[return]
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter(redis)
    return _rate_limiter


@router.post("/buy", response_model=BuyResponse, status_code=status.HTTP_200_OK)
async def buy(body: BuyRequest, redis: RedisDep) -> BuyResponse:
    log = logger.bind(
        user_id=body.user_id,
        product_id=body.product_id,
        idempotency_key=body.idempotency_key,
    )

    # --- Circuit breaker ---
    if redis_circuit_breaker.is_open():
        log.error("circuit_open")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service temporarily unavailable",
        )

    try:
        # --- Rate limiting ---
        limiter = get_rate_limiter(redis)
        if not await limiter.allow_user(body.user_id):
            log.warning("rate_limited_user")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded",
            )
        if not await limiter.allow_global():
            log.warning("rate_limited_global")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="System at capacity",
            )

        # --- Idempotency: atomic SET NX EX claim (user-scoped) ---
        claimed = await claim_idempotency(redis, body.user_id, body.idempotency_key)
        if not claimed:
            existing = await get_idempotency(redis, body.user_id, body.idempotency_key)
            redis_circuit_breaker.record_success()

            if existing is None:
                # Key expired between the NX check and GET — treat as fresh request
                pass
            elif existing == "pending":
                # First request is still in-flight
                log.info("duplicate_request_in_flight")
                REQUEST_COUNT.labels(status="duplicate").inc()
                return BuyResponse(
                    status="processing",
                    message="Order is being processed — retry shortly for result",
                )
            else:
                # Key holds the resolved order_id — return identical success response
                log.info("duplicate_request_cached", order_id=existing)
                REQUEST_COUNT.labels(status="duplicate").inc()
                return BuyResponse(
                    status="accepted",
                    order_id=existing,
                    message="Order accepted",
                )

        # --- Atomic stock decrement (Lua) ---
        stock_ok = await decrement_stock(redis, body.product_id)
        if not stock_ok:
            # Release key so caller can retry with a fresh idempotency key
            await release_idempotency(redis, body.user_id, body.idempotency_key)
            log.info("out_of_stock")
            redis_circuit_breaker.record_success()
            REQUEST_COUNT.labels(status="sold_out").inc()
            return BuyResponse(status="sold_out", message="Product sold out")

        # --- Enqueue to Redis Stream ---
        order_id = str(uuid.uuid4())
        await enqueue_order(
            redis,
            order_id=order_id,
            user_id=body.user_id,
            product_id=body.product_id,
        )

        # --- Resolve idempotency key: pending → order_id ---
        await resolve_idempotency(redis, body.user_id, body.idempotency_key, order_id)

        redis_circuit_breaker.record_success()
        log.info("order_accepted", order_id=order_id)
        REQUEST_COUNT.labels(status="accepted").inc()
        STOCK_REMAINING.labels(product_id=body.product_id).dec()
        return BuyResponse(status="accepted", order_id=order_id, message="Order accepted")

    except HTTPException:
        raise
    except Exception as exc:
        redis_circuit_breaker.record_failure()
        log.error("buy_error", error=str(exc))
        REQUEST_COUNT.labels(status="error").inc()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Internal error",
        ) from exc
