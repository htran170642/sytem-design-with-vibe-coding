# Phase 6 Complete — Caching & Performance Optimization

**Date:** 2026-03-02

## What Was Built

### Step 1 — Cache Foundation (`cache_service.py`)
- Redis-backed async cache with JSON serialization
- `CacheStats` dataclass with `hits`, `misses`, `hit_rate` property
- `make_key()` / `hash_key()` (SHA256) key builders
- `CACHE_ENABLED` global switch — graceful no-op when disabled
- Singleton via `get_cache_service()`

### Step 2 — Embedding Cache (`embedding_service.py`)
- Single embedding: check cache before OpenAI call, store on miss
- Batch embeddings: cache-check each text, batch only the misses, store individually
- TTL: `CACHE_EMBEDDING_TTL` (default 24h)

### Step 3 — AI Response Cache (`rag_service.py`)
- Cache key: SHA256 hash of `question + document_ids + top_k + min_score + fallback_to_general`
- Check cache **before** search and LLM — returns immediately on hit with `cached=True`
- Stores result after: normal answer, low-confidence answer, fallback-to-general answer
- Does **not** cache: no-results path, error path (transient failures)
- TTL: `CACHE_AI_RESPONSE_TTL` (default 1h)

### Step 4 — Configurable TTL (`config.py`)
Pre-configured per-type TTLs, all overridable via environment variables:

| Setting | Default | Purpose |
|---------|---------|---------|
| `CACHE_EMBEDDING_TTL` | 86400s (24h) | Stable text→vector mappings |
| `CACHE_AI_RESPONSE_TTL` | 3600s (1h) | RAG answers |
| `CACHE_FAQ_TTL` | 1800s (30min) | Frequently asked questions |
| `CACHE_DEFAULT_TTL` | 600s (10min) | Fallback |

### Step 5 — Hit/Miss Metrics (`health.py`, `cache_service.py`)
- `GET /health/cache-stats` endpoint — returns `hits`, `misses`, `hit_rate`
- `elapsed_ms` added to every cache GET log entry (DEBUG level)
- In-process counters accumulate since last restart; reset via `cache.reset_stats()`

### Step 6 — Async I/O Audit
- All Redis calls use `redis.asyncio` (non-blocking)
- Embedding batching already done in Step 2
- `time.monotonic()` used for sub-millisecond timing (no blocking)

## Files Changed

| File | Change |
|------|--------|
| `app/services/rag_service.py` | Injected CacheService; cache check + store in `query()` |
| `app/api/routes/health.py` | Added `GET /health/cache-stats` endpoint |
| `app/services/cache_service.py` | Added `import time`; `elapsed_ms` in GET log |
| `tests/unit/test_rag_cache.py` | 9 new tests for RAG response caching |
| `TODO.md` | Phase 6 marked complete |

## Test Results

```
152 passed in 6.33s
```

New tests in `tests/unit/test_rag_cache.py`:
- Cache hit skips search and LLM
- Cache hit does not re-write to cache
- Cache miss runs full pipeline
- Cache miss stores result with TTL
- Same params → deterministic key
- Different params → different keys
- No-results path not cached
- Fallback-to-general path is cached
- Error path not cached
