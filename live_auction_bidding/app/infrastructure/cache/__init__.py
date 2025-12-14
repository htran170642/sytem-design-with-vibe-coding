"""
Cache Infrastructure

Centralized caching for high-performance reads.
"""
from app.infrastructure.cache.cache_manager import (
    CacheManager,
    get_cache_manager
)
from app.infrastructure.cache.auction_cache import AuctionCache
from app.infrastructure.cache.bid_cache import BidCache
from app.infrastructure.cache.base_cache import BaseCache

# For backward compatibility with old code
get_cache = get_cache_manager  # ← ADD THIS LINE!

__all__ = [
    "CacheManager",
    "get_cache_manager",
    "get_cache",  # ← ADD THIS!
    "AuctionCache",
    "BidCache",
    "BaseCache"
]