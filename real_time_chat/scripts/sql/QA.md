Summary - Key Interview Takeaways
Indexes:

B-tree for range queries, sorting
Composite index for (room_id, created_at) - column order matters
Always index foreign keys
Use EXPLAIN ANALYZE to verify

Performance:

1000x speedup with proper indexing
Cursor pagination > offset pagination
Avoid N+1 queries (use joins)
Monitor with pg_stat_user_indexes

Trade-offs:

Indexes speed up reads, slow down writes
Index size ≈ 10-30% of table size
Don't over-index (max 5-6 per table)

Maintenance:

ANALYZE for statistics
REINDEX for bloat
Drop unused indexes
Monitor cache hit ratio