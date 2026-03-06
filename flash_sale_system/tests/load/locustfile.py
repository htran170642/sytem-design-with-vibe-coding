"""
Flash Sale load test — Locust scenario.

Simulates a burst of users all racing to buy the same product during a flash sale.

Scenarios
---------
FlashSaleUser   — each user sends one POST /buy with a unique user_id + idempotency_key.
                  Mirrors real flash-sale traffic: everyone hits at the same moment.

Run (headless, 10k users, ramp 100/s):
    locust -f tests/load/locustfile.py \
        --headless -u 10000 -r 100 \
        --run-time 60s \
        --host http://localhost:8000

Run (interactive web UI):
    locust -f tests/load/locustfile.py --host http://localhost:8000
    open http://localhost:8089
"""

import uuid

from locust import HttpUser, between, events, task

# ------------------------------------------------------------------ #
# Shared product — all users compete for the same stock
# ------------------------------------------------------------------ #

PRODUCT_ID = "PROD-FLASH-001"


# ------------------------------------------------------------------ #
# User behaviour
# ------------------------------------------------------------------ #


class FlashSaleUser(HttpUser):
    """
    Simulates a single buyer in a flash sale.

    Each virtual user:
      1. Generates a unique user_id + idempotency_key (no collisions across users)
      2. Sends ONE POST /buy request
      3. Waits 1-3s before the next task (simulates think time / retry backoff)
    """

    wait_time = between(1, 3)

    def on_start(self) -> None:
        # Stable identity for this virtual user across retries
        self.user_id = f"load-user-{uuid.uuid4().hex}"
        self.idempotency_key = uuid.uuid4().hex  # 32 chars — satisfies min_length=16

    @task
    def buy(self) -> None:
        payload = {
            "user_id": self.user_id,
            "product_id": PRODUCT_ID,
            "idempotency_key": self.idempotency_key,
        }

        with self.client.post(
            "/buy",
            json=payload,
            catch_response=True,
            name="POST /buy",
        ) as resp:
            if resp.status_code == 200:
                body = resp.json()
                status = body.get("status", "")

                if status == "accepted":
                    resp.success()
                elif status == "sold_out":
                    # Expected once stock runs out — not a failure
                    resp.success()
                elif status == "processing":
                    # Duplicate in-flight — success from Locust's perspective
                    resp.success()
                else:
                    resp.failure(f"Unexpected status: {status}")

            elif resp.status_code == 429:
                # Rate limited — mark as success (expected under high load)
                resp.success()
            else:
                resp.failure(f"HTTP {resp.status_code}: {resp.text[:120]}")


# ------------------------------------------------------------------ #
# Summary hook — print outcome breakdown at end of test
# ------------------------------------------------------------------ #

_outcome_counts: dict[str, int] = {
    "accepted": 0,
    "sold_out": 0,
    "processing": 0,
    "rate_limited": 0,
    "error": 0,
}


@events.request.add_listener
def on_request(
    request_type: str,
    name: str,
    response_time: float,
    response_length: int,
    response,
    context,
    exception,
    **kwargs,
) -> None:
    if name != "POST /buy" or exception:
        return
    try:
        if response.status_code == 429:
            _outcome_counts["rate_limited"] += 1
        elif response.status_code == 200:
            status = response.json().get("status", "error")
            _outcome_counts[status] = _outcome_counts.get(status, 0) + 1
        else:
            _outcome_counts["error"] += 1
    except Exception:
        pass


@events.quitting.add_listener
def on_quitting(environment, **kwargs) -> None:
    print("\n=== Flash Sale Outcome Breakdown ===")
    for outcome, count in _outcome_counts.items():
        if count:
            print(f"  {outcome:15s}: {count:>8,}")
    print("====================================\n")
