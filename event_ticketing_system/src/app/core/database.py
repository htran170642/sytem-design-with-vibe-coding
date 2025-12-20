"""
Database configuration and async session management
"""
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base

from app.core.config import settings

# Create async engine
# Using asyncpg driver for PostgreSQL
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,  # Log SQL queries in debug mode
    future=True,
    pool_pre_ping=True,  # Verify connections before using
    pool_size=20,  # Default connection pool size
    max_overflow=40,  # Max connections beyond pool_size
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Don't expire objects after commit
    autocommit=False,
    autoflush=False,
)

# Create declarative base for models
Base = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for FastAPI to provide database sessions.
    
    Usage:
        @app.get("/users")
        async def get_users(db: AsyncSession = Depends(get_db)):
            result = await db.execute(select(User))
            return result.scalars().all()
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """
    Initialize database tables.
    Only for development - use Alembic migrations in production.
    """
    async with engine.begin() as conn:
        # Import all models to register them with Base
        from app.models import (
            User, Event, EventSeat, Booking, BookingSeat
        )
        
        # Create all tables
        await conn.run_sync(Base.metadata.create_all)


async def drop_db():
    """
    Drop all database tables.
    WARNING: Use only in development/testing!
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
