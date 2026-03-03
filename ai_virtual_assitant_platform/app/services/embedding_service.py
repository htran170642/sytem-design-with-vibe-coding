"""
Embedding Service
Generate vector embeddings for text chunks
Phase 4, Step 3: Generate embeddings
Phase 6, Step 2: Cache embeddings
"""

import time
from typing import List, Optional

from app.core.config import settings
from app.core.exceptions import LLMError
from app.core.logging_config import get_logger
from app.services.cache_service import CacheService, get_cache_service
from app.services.openai_client import get_openai_client

logger = get_logger(__name__)


class EmbeddingService:
    """
    Generate embeddings for text using OpenAI API.

    Embeddings are cached in Redis (keyed by SHA-256 of the text) so that
    repeated calls for identical text skip the OpenAI API call entirely.
    """

    def __init__(
        self,
        model: str = "text-embedding-3-small",
        dimensions: int = 1536,
        cache: Optional[CacheService] = None,
    ):
        """
        Initialize embedding service.

        Args:
            model:      OpenAI embedding model.
            dimensions: Embedding dimensions (1536 for text-embedding-3-small).
            cache:      CacheService instance; uses singleton if not provided.
        """
        self.client = get_openai_client()
        self.model = model
        self.dimensions = dimensions
        self._cache = cache if cache is not None else get_cache_service()

        # Pricing: $0.02 per 1M tokens
        self.cost_per_1k_tokens = 0.00002

        logger.info(
            "EmbeddingService initialized",
            extra={"model": model, "dimensions": dimensions},
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _cache_key(self, text: str) -> str:
        """Return the Redis key used to cache the embedding for *text*."""
        return CacheService.hash_key("embedding", text)

    async def _generate_from_api(
        self,
        texts: List[str],
        batch_size: int = 100,
    ) -> List[List[float]]:
        """
        Call OpenAI embeddings API in batches.  No caching logic here —
        callers are responsible for cache reads/writes.
        """
        all_embeddings: List[List[float]] = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]

            logger.info(
                f"Processing batch {i // batch_size + 1}",
                extra={"batch_size": len(batch), "total_texts": len(texts)},
            )

            response = await self.client.client.embeddings.create(
                model=self.model,
                input=batch,
                encoding_format="float",
            )

            batch_embeddings = [item.embedding for item in response.data]
            all_embeddings.extend(batch_embeddings)

        return all_embeddings

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.

        Checks the cache first; calls OpenAI only on a miss and stores the
        result for future calls.

        Args:
            text: Text to embed.

        Returns:
            List of floats (embedding vector, length = self.dimensions).

        Example:
            >>> embedding = await service.generate_embedding("Hello world")
            >>> len(embedding)
            1536
        """
        key = self._cache_key(text)

        cached = await self._cache.get(key)
        if cached is not None:
            logger.debug("Embedding cache hit", extra={"key": key})
            return cached

        try:
            start_time = time.time()

            response = await self.client.client.embeddings.create(
                model=self.model,
                input=text,
                encoding_format="float",
            )

            embedding: List[float] = response.data[0].embedding
            elapsed = time.time() - start_time

            logger.info(
                "Embedding generated",
                extra={
                    "model": self.model,
                    "tokens": response.usage.total_tokens,
                    "duration_seconds": round(elapsed, 3),
                    "cache_hit": False,
                },
            )

            await self._cache.set(key, embedding, ttl=settings.CACHE_EMBEDDING_TTL)
            return embedding

        except Exception as e:
            logger.error(f"Error generating embedding: {e}", exc_info=True)
            raise LLMError(
                message="Failed to generate embedding",
                details={"error": str(e)},
            )

    async def generate_embeddings_batch(
        self,
        texts: List[str],
        batch_size: int = 100,
    ) -> List[List[float]]:
        """
        Generate embeddings for multiple texts with per-text cache checks.

        Algorithm:
        1. Check cache for every text.
        2. Collect indices of cache misses.
        3. Call OpenAI only for the missed texts (batched).
        4. Fill results in original order and cache the new embeddings.

        Args:
            texts:      List of texts to embed.
            batch_size: Max texts per OpenAI API call (OpenAI limit: 2048).

        Returns:
            List of embedding vectors in the same order as *texts*.

        Example:
            >>> texts = ["Hello", "World", "AI is amazing"]
            >>> embeddings = await service.generate_embeddings_batch(texts)
            >>> len(embeddings)
            3
            >>> len(embeddings[0])
            1536
        """
        if not texts:
            return []

        start_time = time.time()

        # Step 1 & 2: cache lookup for all texts
        results: List[Optional[List[float]]] = [None] * len(texts)
        miss_indices: List[int] = []

        for i, text in enumerate(texts):
            cached = await self._cache.get(self._cache_key(text))
            if cached is not None:
                results[i] = cached
            else:
                miss_indices.append(i)

        cache_hits = len(texts) - len(miss_indices)
        logger.info(
            "Embedding batch cache check",
            extra={
                "total": len(texts),
                "cache_hits": cache_hits,
                "cache_misses": len(miss_indices),
            },
        )

        # All hits — return immediately without any API call
        if not miss_indices:
            logger.info(
                "Batch embeddings served fully from cache",
                extra={"total": len(texts)},
            )
            return results  # type: ignore[return-value]

        # Step 3: call OpenAI for misses only
        try:
            miss_texts = [texts[i] for i in miss_indices]
            new_embeddings = await self._generate_from_api(miss_texts, batch_size)
        except Exception as e:
            logger.error(f"Error generating batch embeddings: {e}", exc_info=True)
            raise LLMError(
                message="Failed to generate batch embeddings",
                details={"error": str(e), "batch_size": len(texts)},
            )

        # Step 4: merge into results and populate cache
        for idx, embedding in zip(miss_indices, new_embeddings):
            results[idx] = embedding
            await self._cache.set(
                self._cache_key(texts[idx]),
                embedding,
                ttl=settings.CACHE_EMBEDDING_TTL,
            )

        elapsed = time.time() - start_time
        logger.info(
            "Batch embeddings generated",
            extra={
                "total_texts": len(texts),
                "api_calls": len(miss_indices),
                "cache_hits": cache_hits,
                "duration_seconds": round(elapsed, 3),
            },
        )

        return results  # type: ignore[return-value]

    def estimate_cost(self, total_tokens: int) -> float:
        """
        Estimate cost for embedding generation.

        Args:
            total_tokens: Total tokens to embed.

        Returns:
            Estimated cost in USD.

        Example:
            >>> cost = service.estimate_cost(10000)
            >>> print(f"${cost:.4f}")
            $0.0002
        """
        return (total_tokens / 1000) * self.cost_per_1k_tokens


# ---------------------------------------------------------------------------
# Singleton factory
# ---------------------------------------------------------------------------

_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service(
    model: str = "text-embedding-3-small",
    dimensions: int = 1536,
) -> EmbeddingService:
    """Return the shared EmbeddingService singleton (created on first call)."""
    global _embedding_service

    if _embedding_service is None:
        _embedding_service = EmbeddingService(model=model, dimensions=dimensions)

    return _embedding_service
