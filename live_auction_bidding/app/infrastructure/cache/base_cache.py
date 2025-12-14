"""
Base Cache - Generic caching foundation

DRY Principle: Common logic in base class
Extensible: Each entity extends and customizes
"""
from abc import ABC, abstractmethod
from typing import Optional, Dict, List, TypeVar, Generic, Callable
import json
import redis
from sqlalchemy.orm import Session

from app.core.config import get_settings

T = TypeVar('T')


class BaseCache(ABC, Generic[T]):
    """
    Abstract base cache with common caching patterns
    
    Subclasses implement:
    - Entity-specific key prefix
    - Serialization logic
    - Database query logic
    """
    
    def __init__(self, redis_client: redis.Redis, ttl: int):
        """
        Initialize cache
        
        Args:
            redis_client: Redis connection
            ttl: Time to live in seconds
        """
        self.redis = redis_client
        self.ttl = ttl
        
        # Metrics
        self.hits = 0
        self.misses = 0
    
    # ========================================================================
    # ABSTRACT METHODS - Implement in subclasses
    # ========================================================================
    
    @abstractmethod
    def _get_key_prefix(self) -> str:
        """
        Return cache key prefix
        
        Examples:
        - "auction" → auction:123
        - "bid" → bid:456
        """
        pass
    
    @abstractmethod
    def _fetch_from_db(self, entity_id: int, db: Session) -> Optional[T]:
        """
        Fetch entity from database
        
        Args:
            entity_id: Entity ID
            db: Database session
            
        Returns:
            Entity object or None
        """
        pass
    
    @abstractmethod
    def _serialize(self, entity: T) -> Dict:
        """
        Convert entity to dict for caching
        
        Args:
            entity: Entity object
            
        Returns:
            Serialized dict
        """
        pass
    
    

    # ========================================================================
    # CONCRETE METHODS - Reusable across all caches
    # ========================================================================
    
    def _make_key(self, entity_id: int) -> str:
        """Generate cache key"""
        return f"{self._get_key_prefix()}:{entity_id}"
    
    def get(self, entity_id: int, db: Session) -> Optional[Dict]:
        """
        Get entity from cache (cache-first strategy)
        
        Flow:
        1. Try cache → Hit? Return immediately
        2. Cache miss → Query DB
        3. Store in cache for next time
        
        Args:
            entity_id: Entity ID
            db: Database session
            
        Returns:
            Entity dict or None
        """
        cache_key = self._make_key(entity_id)
        
        # Try cache first
        cached_data = self.redis.get(cache_key)
        
        if cached_data:
            # CACHE HIT
            self.hits += 1
            data = json.loads(cached_data)
            print(f"✅ [CACHE HIT] {self._get_key_prefix()}:{entity_id} "
                  f"(hit rate: {self.get_hit_rate():.1%})")
            return data
        
        # CACHE MISS - Query database
        self.misses += 1
        print(f"💾 [CACHE MISS] {self._get_key_prefix()}:{entity_id}")
        
        entity = self._fetch_from_db(entity_id, db)
        
        if not entity:
            return None
        
        # Store in cache
        entity_data = self._serialize(entity)
        self.redis.setex(
            cache_key,
            self.ttl,
            json.dumps(entity_data)
        )
        
        return entity_data
    
    def get_many(self, entity_ids: List[int], db: Session) -> Dict[int, Dict]:
        """
        Get multiple entities at once (batch operation)
        
        Optimized for listing pages with multiple items.
        Uses Redis MGET for performance.
        
        Args:
            entity_ids: List of entity IDs
            db: Database session
            
        Returns:
            Dict mapping entity_id → entity_data
        """
        if not entity_ids:
            return {}
        
        # Generate keys
        cache_keys = [self._make_key(eid) for eid in entity_ids]
        
        # Batch get from Redis (MGET)
        cached_values = self.redis.mget(cache_keys)
        
        result = {}
        missing_ids = []
        
        # Process cached results
        for entity_id, cached_value in zip(entity_ids, cached_values):
            if cached_value:
                # Cache hit
                self.hits += 1
                result[entity_id] = json.loads(cached_value)
            else:
                # Cache miss - need to fetch from DB
                self.misses += 1
                missing_ids.append(entity_id)
        
        # Fetch missing entities from DB
        if missing_ids:
            missing_entities = self._fetch_many_from_db(missing_ids, db)
            
            # Store in cache and add to result
            for entity_id, entity in missing_entities.items():
                entity_data = self._serialize(entity)
                
                # Store in cache
                cache_key = self._make_key(entity_id)
                self.redis.setex(cache_key, self.ttl, json.dumps(entity_data))
                
                result[entity_id] = entity_data
        
        print(f"📊 [BATCH] {len(result)}/{len(entity_ids)} from cache "
              f"(hit rate: {self.get_hit_rate():.1%})")
        
        return result
    
    def _fetch_many_from_db(self, entity_ids: List[int], db: Session) -> Dict[int, T]:
        """
        Fetch multiple entities from DB (override if needed for optimization)
        
        Default: Calls _fetch_from_db for each ID
        Override: Use optimized batch query (IN clause)
        """
        result = {}
        for entity_id in entity_ids:
            entity = self._fetch_from_db(entity_id, db)
            if entity:
                result[entity_id] = entity
        return result
    
    def set(self, entity_id: int, entity: T):
        """
        Manually set/update cache
        
        Args:
            entity_id: Entity ID
            entity: Entity object
        """
        cache_key = self._make_key(entity_id)
        entity_data = self._serialize(entity)
        
        self.redis.setex(cache_key, self.ttl, json.dumps(entity_data))
        print(f"💾 [CACHE SET] {self._get_key_prefix()}:{entity_id}")
    
    def invalidate(self, entity_id: int):
        """
        Remove from cache
        
        Args:
            entity_id: Entity ID
        """
        cache_key = self._make_key(entity_id)
        deleted = self.redis.delete(cache_key)
        
        if deleted:
            print(f"🗑️  [CACHE] Invalidated {self._get_key_prefix()}:{entity_id}")
    
    def invalidate_many(self, entity_ids: List[int]):
        """
        Invalidate multiple entities at once
        
        Args:
            entity_ids: List of entity IDs
        """
        if not entity_ids:
            return
        
        cache_keys = [self._make_key(eid) for eid in entity_ids]
        deleted = self.redis.delete(*cache_keys)
        
        print(f"🗑️  [CACHE] Invalidated {deleted} {self._get_key_prefix()} items")
    
    def warm(self, entities: List[T]):
        """
        Pre-load entities into cache
        
        Args:
            entities: List of entity objects
        """
        count = 0
        for entity in entities:
            # Assumes entity has 'id' attribute - override if different
            entity_id = self._get_entity_id(entity)
            self.set(entity_id, entity)
            count += 1
        
        print(f"🔥 [CACHE WARM] Loaded {count} {self._get_key_prefix()} items")
        return count
    
    def _get_entity_id(self, entity: T) -> int:
        """
        Extract entity ID (override if needed)
        
        Default: entity.id
        Override: entity.auction_id, entity.bid_id, etc.
        """
        return entity.id
    
    def clear_all(self):
        """Clear all caches of this type"""
        pattern = f"{self._get_key_prefix()}:*"
        keys = self.redis.keys(pattern)
        
        if keys:
            self.redis.delete(*keys)
            print(f"🗑️  [CACHE] Cleared {len(keys)} {self._get_key_prefix()} items")
    
    def get_hit_rate(self) -> float:
        """Calculate cache hit rate"""
        total = self.hits + self.misses
        if total == 0:
            return 0.0
        return self.hits / total
    
    def get_stats(self) -> Dict:
        """Get cache statistics"""
        return {
            "cache_type": self._get_key_prefix(),
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": self.get_hit_rate(),
            "ttl_seconds": self.ttl
        }