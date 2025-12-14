"""
Database configuration and connection pooling
"""
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool
from app.config import settings
import logging
import time

# Disable verbose SQLAlchemy logs
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
logging.getLogger('sqlalchemy.pool').setLevel(logging.WARNING)

# Create engine
engine = create_engine(
    settings.DATABASE_URL,
    poolclass=QueuePool,
    pool_size=settings.POOL_SIZE,
    max_overflow=settings.MAX_OVERFLOW,
    pool_timeout=settings.POOL_TIMEOUT,
    pool_recycle=settings.POOL_RECYCLE,
    pool_pre_ping=True,
    execution_options={"isolation_level": "READ COMMITTED"}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Statistics tracking
query_stats = {
    'total_queries': 0,
    'slow_queries': 0,
    'failed_queries': 0
}


@event.listens_for(engine, "before_cursor_execute")
def receive_before_cursor_execute(conn, cursor, statement, params, context, executemany):
    """Track query start time"""
    conn.info.setdefault('query_start_time', []).append(time.time())


@event.listens_for(engine, "after_cursor_execute")
def receive_after_cursor_execute(conn, cursor, statement, params, context, executemany):
    """Track query completion"""
    total_time = time.time() - conn.info['query_start_time'].pop()
    query_stats['total_queries'] += 1
    
    if total_time > 1.0:
        query_stats['slow_queries'] += 1
        print(f"⚠️  SLOW QUERY ({total_time:.3f}s): {statement[:100]}...")


def get_db():
    """Dependency for getting database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_pool_status():
    """Get connection pool status"""
    pool = engine.pool
    
    try:
        size = pool.size() if hasattr(pool, 'size') else settings.POOL_SIZE
        checked_in = pool.checkedin() if hasattr(pool, 'checkedin') else 0
        checked_out = pool.checkedout() if hasattr(pool, 'checkedout') else 0
        overflow = pool.overflow() if hasattr(pool, 'overflow') else 0
        
        if size <= 0:
            size = settings.POOL_SIZE
        if overflow < 0:
            overflow = 0
        
        return {
            "pool_size": size,
            "checked_in": checked_in,
            "checked_out": checked_out,
            "overflow": overflow,
            "max_overflow": settings.MAX_OVERFLOW,
            "total_possible": size + settings.MAX_OVERFLOW
        }
    except Exception as e:
        return {
            "pool_size": settings.POOL_SIZE,
            "checked_in": settings.POOL_SIZE,
            "checked_out": 0,
            "overflow": 0,
            "max_overflow": settings.MAX_OVERFLOW,
            "total_possible": settings.POOL_SIZE + settings.MAX_OVERFLOW,
            "error": str(e)
        }


def get_query_stats():
    """Get query statistics"""
    return query_stats.copy()


def check_database_health():
    """Check database connection"""
    try:
        db = SessionLocal()
        result = db.execute(text("SELECT 1"))
        result.fetchone()
        db.close()
        return True
    except Exception as e:
        print(f"Database health check failed: {e}")
        return False