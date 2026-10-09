from collections.abc import AsyncGenerator
from typing import Optional
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from app.core.config import settings

_engine: Optional[AsyncEngine] = None
_session_factory: Optional[async_sessionmaker[AsyncSession]] = None

def get_engine() -> AsyncEngine:
    """
    Returns the singleton AsyncEngine configured for the database profile.
    """
    global _engine
    if _engine is None:
        db_url = settings.get_database_url()
        _engine = create_async_engine(
            db_url,
            echo=(settings.ENVIRONMENT == "development_debug"),
            future=True,
            pool_pre_ping=True,
        )
    return _engine

def async_session_factory() -> async_sessionmaker[AsyncSession]:
    """
    Returns the singleton async_sessionmaker bound to the AsyncEngine.
    """
    global _session_factory
    if _session_factory is None:
        engine = get_engine()
        _session_factory = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
        )
    return _session_factory

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency yielding a request-safe AsyncSession.
    Ensures safe commit, rollback on exception, and guaranteed session closure.
    """
    session_maker = async_session_factory()
    async with session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
