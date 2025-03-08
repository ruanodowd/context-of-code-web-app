from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from functools import lru_cache

from .config import get_settings

settings = get_settings()

# Create async engine
@lru_cache()
def get_engine():
    """
    Create and cache database engine.
    Uses environment variables for configuration.
    """
    return create_async_engine(
        settings.DATABASE_URL,
        echo=settings.DEBUG,
    )

# Create async session factory
@lru_cache()
def get_session_factory():
    """
    Create and cache session factory.
    """
    return async_sessionmaker(
        get_engine(),
        class_=AsyncSession,
        expire_on_commit=False
    )

# Dependency to get database session
async def get_db():
    """
    Dependency that provides an async database session.
    Usage: add this as a dependency to your route handlers:
        @app.get("/")
        async def root(db: AsyncSession = Depends(get_db)):
    """
    async_session = get_session_factory()
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()
