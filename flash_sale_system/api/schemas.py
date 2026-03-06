from pydantic import BaseModel, Field


class BuyRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=128)
    product_id: str = Field(..., min_length=1, max_length=128)
    idempotency_key: str = Field(..., min_length=16, max_length=256)


class BuyResponse(BaseModel):
    status: str  # "accepted" | "processing" | "sold_out" | "rate_limited"
    order_id: str | None = None
    message: str
