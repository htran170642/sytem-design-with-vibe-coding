Great question! Here are **interview questions about caching** with answers based on our implementation:

---

# Redis Caching Interview Questions

## 1. Basic Caching Concepts

### Q: "What is caching and why do we use it?"

**A:** "Caching is storing frequently accessed data in fast storage (like Redis) to avoid expensive operations like database queries.

In our chat app:
- Without cache: Every request hits PostgreSQL (~45ms)
- With cache: Data served from Redis (~2ms)
- **20x performance improvement**

Benefits:
- Reduced database load
- Lower latency
- Better scalability
- Cost savings (fewer database operations)"

---

### Q: "Why did you choose Redis over in-memory caching?"

**A:** "Redis is better for distributed systems:

**Redis advantages:**
- Shared across multiple servers (distributed cache)
- Persistent (survives restarts with AOF/RDB)
- Advanced data structures (lists, sets, sorted sets)
- Built-in TTL and eviction policies
- Can handle rate limiting, sessions, pub/sub

**In-memory cache drawbacks:**
- Each server has its own cache (cache inconsistency)
- Lost on restart
- Limited to single server

For our chat app, if we scale to 3 servers, Redis ensures all servers see the same cached data."

---

### Q: "Explain your cache key strategy"

**A:** "Cache key includes all query parameters to ensure uniqueness:

```python
cache_key = f"messages:{room_id}:{limit}:{before_id or 'latest'}"
```

Examples:
- `messages:general:50:latest` - Different from
- `messages:general:100:latest` - Different limit
- `messages:vip:50:latest` - Different room

This prevents returning wrong data. If user requests 50 messages vs 100 messages, they're different queries with different cache keys."

---

## 2. Cache Invalidation

### Q: "What is cache invalidation and why is it hard?"

**A:** "Cache invalidation is removing stale data from cache.

Phil Karlton said: *'There are only two hard things in Computer Science: cache invalidation and naming things.'*

**Why it's hard:**
- **Timing**: When to invalidate? Too early = cache miss, too late = stale data
- **Granularity**: Invalidate specific keys or patterns?
- **Distributed systems**: Multiple servers, race conditions

**Our approach:**
```python
# When new message posted:
invalidate_cache('messages:general:*')
```

We use pattern-based invalidation - delete all cache entries for that room.

**Trade-offs:**
- ✅ Simple, always fresh data
- ❌ Aggressive (deletes more than necessary)
- Alternative: Could use write-through cache or shorter TTL"

---

### Q: "How would you handle cache invalidation in a distributed system?"

**A:** "In our current implementation, invalidation happens on the server that receives the write. This works but has issues:

**Current approach (single server):**
```python
# Server A receives new message
save_to_db(message)
invalidate_cache('messages:*')  # Only clears Server A's Redis
```

**Problem:** If we have multiple app servers, they might cache different data.

**Solution: Redis Pub/Sub**
```python
# Server A
save_to_db(message)
redis.publish('cache:invalidate', 'messages:general:*')

# All servers subscribe
def cache_invalidation_listener():
    pubsub = redis.pubsub()
    pubsub.subscribe('cache:invalidate')
    for message in pubsub.listen():
        pattern = message['data']
        invalidate_cache(pattern)
```

All servers get the invalidation message and clear their caches.

**Alternative: Use Redis as single source of truth** (what we do)
- One Redis instance, all servers share it
- Invalidation affects all servers automatically"

---

### Q: "What are the cache invalidation strategies?"

**A:** "Three main strategies:

**1. Time-based (TTL) - What we use**
```python
redis.setex(key, 60, value)  # Expires after 60 seconds
```
✅ Simple, automatic
❌ May serve stale data until expiry

**2. Event-based - We also use this**
```python
# When data changes, invalidate immediately
invalidate_cache('messages:general:*')
```
✅ Always fresh data
❌ Need to track all write operations

**3. Write-through cache**
```python
# Update cache AND database together
def save_message(msg):
    db.save(msg)
    redis.set(cache_key, msg)  # Update cache immediately
```
✅ Cache always in sync
❌ Slower writes

**Our hybrid approach:**
- TTL for safety (60 seconds)
- Event-based for freshness (invalidate on write)
- Best of both worlds"

---

## 3. Performance & Optimization

### Q: "How did you measure cache performance?"

**A:** "I created a benchmark comparing cached vs non-cached requests:

```python
def test_without_cache():
    for i in range(10):
        redis.flushdb()  # Clear cache before EACH request
        time_start = time.time()
        get_messages()
        time_end = time.time()
        # Measures actual database query time

def test_with_cache():
    get_messages()  # Populate cache
    for i in range(10):
        time_start = time.time()
        get_messages()  # Same request, hits cache
        time_end = time.time()
```

**Results:**
- Without cache: ~45ms (database query)
- With cache: ~2ms (Redis lookup)
- **20x speedup**

**Key metrics tracked:**
- Response time (latency)
- Cache hit rate
- Database load reduction
- Redis memory usage"

---

### Q: "What's the cache hit rate and why does it matter?"

**A:** "Cache hit rate = (cache hits) / (total requests)

**Formula:**
```
Hit Rate = Hits / (Hits + Misses) × 100%
```

**Why it matters:**
- 90% hit rate = 90% of requests avoid database
- 50% hit rate = Only half benefit from cache
- Low hit rate might mean cache strategy is wrong

**How to measure:**
```python
hits = redis.get('cache:hits') or 0
misses = redis.get('cache:misses') or 0
hit_rate = hits / (hits + misses) * 100

# Track in code
cached = redis.get(key)
if cached:
    redis.incr('cache:hits')
    return cached
else:
    redis.incr('cache:misses')
    # ... fetch from DB
```

**Good hit rates:**
- 80-90%: Excellent
- 60-80%: Good
- <50%: Need to investigate

**Improvements:**
- Increase TTL (longer caching)
- Warm cache on startup
- Add cache warming for popular queries"

---

### Q: "How do you determine the right TTL (Time To Live)?"

**A:** "TTL depends on data characteristics:

**Our choice: 60 seconds for messages**

**Factors to consider:**

**1. Data freshness requirements**
- Real-time stock prices: 1-5 seconds
- Social media feed: 30-60 seconds
- Product catalog: 5-15 minutes
- User profiles: 1 hour

**2. Update frequency**
- Frequently updated: Short TTL
- Rarely updated: Long TTL

**3. Staleness tolerance**
- Banking data: Very short TTL
- Blog posts: Long TTL OK

**Formula I use:**
```
TTL = Average_Time_Between_Updates × 0.5
```

For chat:
- Messages posted every ~2 minutes
- TTL = 60 seconds (safe middle ground)

**Dynamic TTL strategy:**
```python
# Popular rooms: shorter TTL (more frequent updates)
if room.message_rate > 10_per_minute:
    ttl = 30
else:
    ttl = 300  # Quieter rooms can cache longer
```"

---

## 4. Scalability & Architecture

### Q: "How does caching help with scalability?"

**A:** "Caching enables horizontal scaling:

**Without cache:**
```
1 server → 1000 req/s → 1000 DB queries/s
10 servers → 10,000 req/s → 10,000 DB queries/s ❌ Database bottleneck
```

**With cache (90% hit rate):**
```
10 servers → 10,000 req/s → 1,000 DB queries/s ✅ Database handles it
```

**How it helps:**

**1. Database Load Reduction**
- Cache absorbs read traffic
- Database handles only writes + cache misses
- Can scale reads independently

**2. Cost Savings**
- Fewer database connections needed
- Smaller database instance
- Redis is cheaper than scaling database

**3. Better Latency**
- Redis: <1ms
- PostgreSQL: 10-50ms
- Users get faster responses

**Example from our app:**
- 1000 users requesting messages
- Without cache: 1000 DB queries
- With cache (90% hit): 100 DB queries
- **10x reduction in DB load**"

---

### Q: "What happens if Redis goes down?"

**A:** "Good question! This is a critical failure scenario.

**Current implementation (no fallback):**
```python
cached = redis_client.get(key)
if cached:
    return cached
# If Redis is down, this throws exception ❌
```

**Better implementation (graceful degradation):**
```python
def get_messages_cached(room_id, limit):
    try:
        # Try cache first
        cached = redis_client.get(cache_key)
        if cached:
            return json.loads(cached)
    except redis.ConnectionError:
        print('Redis unavailable, falling back to database')
        # Continue to database query
    
    # Fetch from database
    messages = db.query(Message).filter(...).all()
    
    # Try to cache (but don't fail if Redis is down)
    try:
        redis_client.setex(cache_key, 60, json.dumps(messages))
    except redis.ConnectionError:
        pass  # Cache unavailable, but request succeeds
    
    return messages
```

**Better yet: Redis Sentinel or Cluster**
- Automatic failover
- High availability
- Multiple Redis instances

**Monitoring:**
```python
@app.get('/health')
def health_check():
    db_healthy = check_database()
    redis_healthy = check_redis()
    
    return {
        'status': 'healthy' if (db_healthy and redis_healthy) else 'degraded',
        'database': db_healthy,
        'redis': redis_healthy
    }
```"

---

### Q: "How do you handle the thundering herd problem?"

**A:** "The thundering herd problem: When cache expires, multiple requests hit database simultaneously.

**Scenario:**
```
Time 0: Cache has data (TTL = 60s)
Time 60: Cache expires
Time 61: 1000 simultaneous requests
         → All see cache miss
         → All query database
         → Database overload ❌
```

**Solution 1: Cache Stampede Prevention (Locking)**
```python
def get_messages_with_lock(key):
    # Try cache
    cached = redis.get(key)
    if cached:
        return cached
    
    # Try to acquire lock
    lock_key = f'lock:{key}'
    lock_acquired = redis.set(lock_key, '1', nx=True, ex=5)
    
    if lock_acquired:
        # This request rebuilds cache
        data = expensive_db_query()
        redis.setex(key, 60, data)
        redis.delete(lock_key)
        return data
    else:
        # Other requests wait for first request to finish
        time.sleep(0.1)
        return get_messages_with_lock(key)  # Retry
```

**Solution 2: Probabilistic Early Expiration**
```python
def get_messages_probabilistic(key, ttl=60):
    cached = redis.get(key)
    
    if cached:
        # Refresh cache before expiry based on probability
        remaining_ttl = redis.ttl(key)
        probability = 1 - (remaining_ttl / ttl)
        
        if random.random() < probability:
            # Refresh cache in background
            threading.Thread(target=refresh_cache, args=(key,)).start()
        
        return cached
    
    # Cache miss
    return refresh_cache(key)
```

**Solution 3: Stale-While-Revalidate**
```python
# Store both data and timestamp
redis.set(key, json.dumps({
    'data': messages,
    'cached_at': time.time()
}))

# Serve stale data while refreshing
if cached:
    data = json.loads(cached)
    age = time.time() - data['cached_at']
    
    if age > 60:  # Stale
        # Return stale data immediately
        # Refresh in background
        threading.Thread(target=refresh_cache).start()
    
    return data['data']
```"

---

## 5. Rate Limiting with Redis

### Q: "How did you implement rate limiting with Redis?"

**A:** "I used Redis for distributed rate limiting:

```python
def rate_limit(user_id, max_requests=10, window=60):
    key = f'rate_limit:message:{user_id}'
    
    # Get current count
    current = redis.get(key)
    
    if current and int(current) >= max_requests:
        # Rate limit exceeded
        ttl = redis.ttl(key)
        raise RateLimitError(f'Retry after {ttl} seconds')
    
    # Increment counter with expiry
    pipe = redis.pipeline()
    pipe.incr(key)
    pipe.expire(key, window)
    pipe.execute()
```

**Why Redis is perfect for this:**

**1. Atomic Operations**
- `INCR` is atomic (no race conditions)
- Multiple servers can't bypass limit

**2. Automatic Expiry**
- TTL resets counter automatically
- No cleanup needed

**3. Distributed**
- Works across multiple servers
- Shared state

**Algorithm: Fixed Window**
```
Time:    0s    60s   120s   180s
Requests: 10    10    10     10   ← Max per minute
Counter:  ↓     ↓     ↓      ↓
         Reset Reset Reset Reset
```

**Alternative: Sliding Window (more accurate)**
```python
def rate_limit_sliding_window(user_id, max_requests=10, window=60):
    key = f'rate_limit:{user_id}'
    now = time.time()
    
    # Use sorted set with timestamps
    pipe = redis.pipeline()
    
    # Remove old entries
    pipe.zremrangebyscore(key, 0, now - window)
    
    # Count recent requests
    pipe.zcard(key)
    
    # Add current request
    pipe.zadd(key, {now: now})
    
    # Set expiry
    pipe.expire(key, window)
    
    results = pipe.execute()
    count = results[1]
    
    if count >= max_requests:
        raise RateLimitError()
```"

---

### Q: "What's the difference between Fixed Window and Sliding Window rate limiting?"

**A:** "Great question! Let me illustrate:

**Fixed Window:**
```
Window 1: 0-60s    Window 2: 60-120s
Limit: 10/minute

Time:  0s .... 59s | 60s .... 119s
Requests: 10 msgs  | 10 msgs

Problem at boundary:
Time 59s: 10 requests
Time 60s: 10 requests
→ 20 requests in 2 seconds! ❌
```

**Sliding Window:**
```
Always looks back 60 seconds from current time

Time 59s: Look back to 0s → 10 requests
Time 60s: Look back to 1s → Only count requests from last 60s
Time 61s: Look back to 2s → Requests from 0-1s dropped

✅ Never exceeds 10 requests in ANY 60-second period
```

**Code comparison:**

```python
# Fixed Window (simpler, less accurate)
def fixed_window(user_id):
    key = f'rate:{user_id}'
    count = redis.incr(key)
    if count == 1:
        redis.expire(key, 60)
    return count <= 10

# Sliding Window (complex, more accurate)
def sliding_window(user_id):
    key = f'rate:{user_id}'
    now = time.time()
    
    # Remove requests older than 60s
    redis.zremrangebyscore(key, 0, now - 60)
    
    # Count requests in last 60s
    count = redis.zcard(key)
    
    if count < 10:
        redis.zadd(key, {now: now})
        return True
    return False
```

**Trade-offs:**
- Fixed: Faster, less memory, but can burst
- Sliding: Accurate, prevents bursts, but more complex"

---

## 6. Advanced Topics

### Q: "What caching strategies are there besides simple key-value?"

**A:** "Multiple caching patterns:

**1. Cache-Aside (Lazy Loading) - What we use**
```python
def get_data(key):
    # Try cache
    data = cache.get(key)
    if data:
        return data
    
    # Miss: Load from DB
    data = db.query(key)
    cache.set(key, data)
    return data
```
✅ Only cache what's requested
❌ Cache miss penalty

**2. Write-Through**
```python
def save_data(key, value):
    # Write to DB and cache together
    db.save(key, value)
    cache.set(key, value)
```
✅ Cache always consistent
❌ Slower writes

**3. Write-Behind (Write-Back)**
```python
def save_data(key, value):
    # Write to cache first
    cache.set(key, value)
    
    # Async write to DB
    queue.enqueue(lambda: db.save(key, value))
```
✅ Fast writes
❌ Risk of data loss

**4. Read-Through**
```python
# Cache layer handles DB loading
data = cache.get(key)  # Cache loads from DB if needed
```

**5. Cache Warming**
```python
# Pre-populate cache on startup
@app.on_event('startup')
def warm_cache():
    popular_rooms = ['general', 'tech', 'random']
    for room in popular_rooms:
        messages = db.query_messages(room)
        cache.set(f'messages:{room}', messages)
```"

---

### Q: "How do you monitor cache performance in production?"

**A:** "Key metrics to track:

**1. Cache Hit Rate**
```python
# Track in Redis
hits = redis.incr('metrics:cache:hits')
misses = redis.incr('metrics:cache:misses')
total = hits + misses
hit_rate = (hits / total) * 100

# Export to Prometheus
cache_hit_rate = Gauge('cache_hit_rate', 'Cache hit rate percentage')
cache_hit_rate.set(hit_rate)
```

**2. Response Time**
```python
from prometheus_client import Histogram

response_time_cache = Histogram('response_time_cache', 'Cache response time')
response_time_db = Histogram('response_time_db', 'DB response time')

# Measure
with response_time_cache.time():
    data = cache.get(key)

with response_time_db.time():
    data = db.query(key)
```

**3. Cache Size & Memory**
```python
# Redis memory usage
info = redis.info('memory')
used_memory = info['used_memory_human']
max_memory = info['maxmemory_human']

# Key count
key_count = redis.dbsize()
```

**4. Eviction Rate**
```python
# How often is data kicked out?
info = redis.info('stats')
evicted_keys = info['evicted_keys']
```

**Dashboard metrics:**
- Hit rate over time
- P50, P95, P99 latency
- Cache vs DB response time
- Error rate
- Memory usage

**Alerts:**
- Hit rate < 70%: Investigate cache strategy
- Eviction rate high: Increase memory or reduce TTL
- Memory usage > 80%: Scale Redis"

---

### Q: "What's the difference between Redis and Memcached?"

**A:** "Both are in-memory key-value stores, but different use cases:

**Redis:**
- Data structures (lists, sets, sorted sets, hashes)
- Persistence (RDB snapshots, AOF logs)
- Pub/Sub messaging
- Atomic operations
- Transactions
- Lua scripting
- Single-threaded

**Memcached:**
- Simple key-value only
- No persistence
- Multi-threaded
- Simpler, slightly faster for simple gets
- Less memory overhead

**When to use Redis:** (What we use)
- Need data structures
- Need persistence
- Need pub/sub
- Need atomic operations (rate limiting)
- Complex caching scenarios

**When to use Memcached:**
- Pure caching only
- Extremely high throughput needed
- Simple key-value lookup
- Don't need persistence

**For our chat app, Redis is better because:**
- We use sorted sets for rate limiting
- We use pub/sub for cache invalidation
- We want persistence
- We need atomic counters"

---

## 7. Real-World Scenarios

### Q: "How would you cache chat messages for 1 million users?"

**A:** "Strategy for massive scale:

**1. Multi-Layer Caching**
```python
# L1: Application memory (fastest)
local_cache = {}

# L2: Redis (shared)
redis_cache = redis.Redis()

# L3: Database (slowest)
def get_messages_multilayer(room_id):
    # Try L1
    if room_id in local_cache:
        return local_cache[room_id]
    
    # Try L2
    cached = redis_cache.get(f'messages:{room_id}')
    if cached:
        local_cache[room_id] = cached  # Promote to L1
        return cached
    
    # L3: Database
    messages = db.query(room_id)
    redis_cache.set(f'messages:{room_id}', messages)
    local_cache[room_id] = messages
    return messages
```

**2. Sharding by Room**
```python
# Distribute rooms across Redis instances
def get_redis_instance(room_id):
    hash_val = hash(room_id)
    shard = hash_val % NUM_REDIS_SHARDS
    return redis_cluster[shard]

redis = get_redis_instance('general')
```

**3. Hot/Cold Data Strategy**
```python
# Hot data (active rooms): Short TTL, always cached
if room.messages_per_hour > 100:
    ttl = 30  # 30 seconds
    priority = 'high'

# Cold data (inactive rooms): Longer TTL or no cache
else:
    ttl = 600  # 10 minutes
    priority = 'low'
```

**4. Cache Budget**
```python
# Limit cache size
MAX_CACHE_SIZE = 10_000_000  # 10M messages

# LRU eviction
redis_config = {
    'maxmemory': '10gb',
    'maxmemory-policy': 'allkeys-lru'
}
```

**5. Compression**
```python
import gzip

def cache_compressed(key, data):
    compressed = gzip.compress(json.dumps(data).encode())
    redis.set(key, compressed)

# Saves ~70% memory for text
```"

---

### Q: "Design a caching strategy for a social media feed"

**A:** "Social feed has unique challenges:

**Requirements:**
- Personalized (each user sees different content)
- Real-time updates
- High read:write ratio
- Mix of following, trending, ads

**Strategy:**

**1. Fan-Out on Write**
```python
# When user posts
def create_post(user_id, content):
    post = save_to_db(content)
    
    # Get followers
    followers = get_followers(user_id)
    
    # Add to each follower's feed cache
    for follower_id in followers:
        redis.lpush(f'feed:{follower_id}', post.id)
        redis.ltrim(f'feed:{follower_id}', 0, 99)  # Keep last 100
```

**2. Hybrid Approach**
```python
def get_feed(user_id):
    # Cache recent posts
    cached_posts = redis.lrange(f'feed:{user_id}', 0, 49)
    
    if len(cached_posts) < 50:
        # Fetch more from DB
        following = get_following(user_id)
        posts = db.query(Post).filter(
            Post.user_id.in_(following)
        ).order_by(Post.created_at.desc()).limit(50)
        
        # Update cache
        for post in posts:
            redis.lpush(f'feed:{user_id}', post.id)
```

**3. Pre-compute Popular Content**
```python
# Cache trending posts separately
@celery.task(schedule=timedelta(minutes=5))
def update_trending():
    trending = calculate_trending_posts()
    redis.set('trending:posts', trending, ex=300)

# Mix into personal feed
def get_feed(user_id):
    personal = get_personal_feed(user_id)
    trending = redis.get('trending:posts')
    return merge_feeds(personal, trending)
```

**Metrics:**
- Cache hit rate target: >95%
- Feed load time: <100ms
- Post propagation: <1 second"

---

## Summary - Key Takeaways

1. **Caching = Performance** (20x speedup in our case)
2. **Invalidation is hard** (use TTL + event-based)
3. **Monitor cache hit rate** (aim for 80%+)
4. **Redis > in-memory** (for distributed systems)
5. **Handle failures gracefully** (fallback to DB)
6. **Different data = different TTL**
7. **Rate limiting** (Redis atomic operations)
8. **Thundering herd** (use locking or probabilistic refresh)

---

These questions cover **basic to advanced** caching concepts. Practice explaining with our code examples!

**Which topic do you want to dive deeper into?** Or ready to move to the next feature?