import os
import uuid
from typing import AsyncGenerator
import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.core.config import settings
from app.db.base import Base
from app.models.user import User
from app.models.resume import Resume
from app.models.job import Job
from app.models.match import Match
from app.models.taxonomy import SkillTaxonomy
from app.repositories.user_repository import UserRepository
from app.repositories.resume_repository import ResumeRepository
from app.repositories.job_repository import JobRepository
from app.repositories.match_repository import MatchRepository

# Target PostgreSQL URL specifically for database integration tests
TEST_POSTGRES_URL = settings.get_database_url()

@pytest_asyncio.fixture(scope="module")
async def postgres_engine():
    """
    Module-scoped engine fixture connecting strictly to PostgreSQL + pgvector.
    Fails immediately if PostgreSQL is not reachable.
    """
    if "sqlite" in TEST_POSTGRES_URL:
        pytest.fail("Database tests must run against real PostgreSQL + pgvector, not SQLite.")
    
    engine = create_async_engine(TEST_POSTGRES_URL, future=True)
    
    # Verify connectivity and pgvector extension
    try:
        async with engine.connect() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";"))
            await conn.run_sync(Base.metadata.create_all)
    except Exception as exc:
        pytest.fail(
            f"PostgreSQL + pgvector connection failed: {exc}. "
            "Ensure Docker Desktop is running with 'docker compose up -d db'."
        )
    
    yield engine
    
    async with engine.connect() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

@pytest_asyncio.fixture
async def db_session(postgres_engine) -> AsyncGenerator[AsyncSession, None]:
    """
    Session fixture bound to the real PostgreSQL database.
    """
    session_factory = async_sessionmaker(bind=postgres_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()

@pytest.mark.asyncio
async def test_postgres_pgvector_extension_installed(postgres_engine):
    """
    Verify pgvector extension is installed in PostgreSQL.
    """
    async with postgres_engine.connect() as conn:
        result = await conn.execute(
            text("SELECT extname FROM pg_extension WHERE extname = 'vector';")
        )
        row = result.scalar()
        assert row == "vector", "pgvector extension must be active in PostgreSQL"

@pytest.mark.asyncio
async def test_user_crud_and_unique_constraint(db_session: AsyncSession):
    """
    Verify User creation, retrieval, and unique email constraint.
    """
    user_repo = UserRepository(db_session)
    email = f"test_{uuid.uuid4().hex[:8]}@example.com"
    
    user = User(
        email=email,
        hashed_password="hashed_pw_test",
        full_name="Database Test User",
    )
    created = await user_repo.create(user)
    assert created.id is not None
    assert created.email == email

    # Fetch
    fetched = await user_repo.get_by_email(email)
    assert fetched is not None
    assert fetched.id == created.id

    # Duplicate constraint violation
    duplicate = User(
        email=email,
        hashed_password="another_password",
    )
    with pytest.raises(Exception):
        await user_repo.create(duplicate)
        await db_session.flush()

@pytest.mark.asyncio
async def test_resume_vector_storage_and_cascade_delete(db_session: AsyncSession):
    """
    Verify 384-dimensional vector embedding persistence and cascade deletion.
    """
    user_repo = UserRepository(db_session)
    resume_repo = ResumeRepository(db_session)

    # 1. Create owner user
    user = User(
        email=f"cascade_{uuid.uuid4().hex[:8]}@example.com",
        hashed_password="pw",
    )
    await user_repo.create(user)

    # 2. Create 384-d vector embedding
    sample_vector = [0.05] * 384

    # 3. Create Resume with vector
    resume = Resume(
        user_id=user.id,
        original_filename="candidate.pdf",
        file_size_bytes=1024,
        parsed_text="Software engineer with Python experience.",
        structured_data={"skills": ["Python"]},
        embedding=sample_vector,
    )
    created_resume = await resume_repo.create(resume)
    assert created_resume.id is not None
    assert len(created_resume.embedding) == 384

    # 4. Delete user and assert resume cascades
    await user_repo.delete(user)
    deleted_resume = await resume_repo.get_by_id(created_resume.id)
    assert deleted_resume is None, "Resume must cascade delete when owner user is deleted"
