import uuid
from typing import AsyncGenerator
import pytest
import pytest_asyncio
from sqlalchemy import select, text, insert
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from app.core.config import settings
from app.db.base import Base
from app.models.user import User
from app.models.resume import Resume
from app.models.job import Job
from app.models.match import Match
from app.models.taxonomy import SkillTaxonomy
from app.models.association import resume_skills, job_skills
from app.repositories.user_repository import UserRepository
from app.repositories.resume_repository import ResumeRepository
from app.repositories.job_repository import JobRepository
from app.repositories.match_repository import MatchRepository

from urllib.parse import urlparse
import asyncio
from alembic.config import Config
from alembic import command

# Target PostgreSQL URL strictly for database integration tests
TEST_POSTGRES_URL = settings.get_test_database_url()
APPROVED_TEST_DB = settings.POSTGRES_TEST_DB  # "resumematch_test"

# Fail-fast validation at module load time
parsed_test_url = urlparse(TEST_POSTGRES_URL)
target_db = parsed_test_url.path.lstrip("/")

if target_db != APPROVED_TEST_DB:
    pytest.fail(
        f"CRITICAL SAFETY VIOLATION: Test database must strictly be '{APPROVED_TEST_DB}', "
        f"got '{target_db}'. Test execution halted."
    )

if target_db == settings.POSTGRES_DB:
    pytest.fail(
        f"CRITICAL SAFETY VIOLATION: Test database resolved to development database '{settings.POSTGRES_DB}'. "
        "Test execution halted."
    )


async def _ensure_test_database_provisioned():
    """
    Ensures resumematch_test exists, has extensions, and has Alembic migrations applied.
    Never drops or recreates any database.
    """
    import asyncpg

    # Connect to maintenance db to check/create test db if absent
    maint_url = (
        f"postgresql://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}"
        f"@{settings.POSTGRES_SERVER}:{settings.POSTGRES_PORT}/postgres"
    )
    conn = await asyncpg.connect(maint_url)
    try:
        exists = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM pg_database WHERE datname = $1);",
            APPROVED_TEST_DB,
        )
        if not exists:
            await conn.execute(f'CREATE DATABASE "{APPROVED_TEST_DB}" OWNER "{settings.POSTGRES_USER}";')
    finally:
        await conn.close()

    # Ensure extensions on test db
    test_conn_url = (
        f"postgresql://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}"
        f"@{settings.POSTGRES_SERVER}:{settings.POSTGRES_PORT}/{APPROVED_TEST_DB}"
    )
    test_conn = await asyncpg.connect(test_conn_url)
    try:
        await test_conn.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";')
        await test_conn.execute('CREATE EXTENSION IF NOT EXISTS "vector";')
    finally:
        await test_conn.close()

    # Apply Alembic migrations to test db
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", TEST_POSTGRES_URL)
    await asyncio.to_thread(command.upgrade, alembic_cfg, "head")


@pytest_asyncio.fixture(scope="function")
async def postgres_engine():
    """
    Function-scoped engine fixture connecting strictly to the dedicated test database.
    Never connects to or drops the development database.
    """
    # Fail-fast safety checks
    assert target_db == APPROVED_TEST_DB, f"Target database must be {APPROVED_TEST_DB}"
    assert target_db != settings.POSTGRES_DB, "Target database must never be development database"

    await _ensure_test_database_provisioned()

    engine = create_async_engine(TEST_POSTGRES_URL, poolclass=NullPool, future=True)

    # Verify connection and confirm current_database
    async with engine.connect() as conn:
        current_db = await conn.scalar(text("SELECT current_database();"))
        if current_db != APPROVED_TEST_DB:
            await engine.dispose()
            pytest.fail(
                f"CRITICAL SAFETY VIOLATION: Connected to unexpected database '{current_db}' "
                f"instead of '{APPROVED_TEST_DB}'. Aborting."
            )

    yield engine

    # Safe row-level cleanup between tests: NEVER calls Base.metadata.drop_all()
    try:
        async with engine.begin() as conn:
            current_db = await conn.scalar(text("SELECT current_database();"))
            if current_db == APPROVED_TEST_DB:
                await conn.execute(text(
                    "TRUNCATE TABLE matches, resume_skills, job_skills, resumes, jobs, users, skill_taxonomy CASCADE;"
                ))
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def db_session(postgres_engine) -> AsyncGenerator[AsyncSession, None]:
    """
    Session fixture bound to the isolated PostgreSQL test database.
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


# ---------------------------------------------------------------------------
# Skill-Association Integration Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_association_tables_exist_in_live_db(postgres_engine):
    """
    Verify both association tables exist in the live PostgreSQL schema.
    """
    async with postgres_engine.connect() as conn:
        for table_name in ("resume_skills", "job_skills"):
            result = await conn.execute(
                text(
                    "SELECT EXISTS("
                    "  SELECT 1 FROM information_schema.tables "
                    "  WHERE table_schema = 'public' AND table_name = :tbl"
                    ")"
                ),
                {"tbl": table_name},
            )
            assert result.scalar() is True, f"Table {table_name} must exist in PostgreSQL"


@pytest.mark.asyncio
async def test_resume_skill_association(db_session: AsyncSession):
    """
    A resume can be associated with a taxonomy skill via resume_skills.
    """
    # Setup
    user = User(email=f"rs_{uuid.uuid4().hex[:8]}@test.com", hashed_password="pw")
    db_session.add(user)
    await db_session.flush()

    resume = Resume(
        user_id=user.id,
        original_filename="rs_test.pdf",
        file_size_bytes=100,
        parsed_text="test",
        structured_data={},
    )
    db_session.add(resume)

    skill = SkillTaxonomy(
        canonical_name=f"Python_{uuid.uuid4().hex[:6]}",
        category="Programming Language",
    )
    db_session.add(skill)
    await db_session.flush()

    # Associate
    await db_session.execute(
        insert(resume_skills).values(resume_id=resume.id, skill_id=skill.id)
    )
    await db_session.flush()

    # Verify the association row exists
    row = await db_session.execute(
        select(resume_skills).where(
            resume_skills.c.resume_id == resume.id,
            resume_skills.c.skill_id == skill.id,
        )
    )
    assert row.first() is not None, "resume_skills association row must exist"


@pytest.mark.asyncio
async def test_job_skill_association(db_session: AsyncSession):
    """
    A job can be associated with a taxonomy skill via job_skills.
    """
    user = User(email=f"js_{uuid.uuid4().hex[:8]}@test.com", hashed_password="pw")
    db_session.add(user)
    await db_session.flush()

    job = Job(
        user_id=user.id,
        title="Backend Engineer",
        raw_text="Looking for Python engineer",
        structured_data={},
    )
    db_session.add(job)

    skill = SkillTaxonomy(
        canonical_name=f"Go_{uuid.uuid4().hex[:6]}",
        category="Programming Language",
    )
    db_session.add(skill)
    await db_session.flush()

    # Associate
    await db_session.execute(
        insert(job_skills).values(job_id=job.id, skill_id=skill.id)
    )
    await db_session.flush()

    # Verify the association row exists
    row = await db_session.execute(
        select(job_skills).where(
            job_skills.c.job_id == job.id,
            job_skills.c.skill_id == skill.id,
        )
    )
    assert row.first() is not None, "job_skills association row must exist"


@pytest.mark.asyncio
async def test_duplicate_resume_skill_rejected(db_session: AsyncSession):
    """
    Inserting the same (resume_id, skill_id) twice must raise an integrity error
    due to the composite primary key constraint.
    """
    user = User(email=f"dup_rs_{uuid.uuid4().hex[:8]}@test.com", hashed_password="pw")
    db_session.add(user)
    await db_session.flush()

    resume = Resume(
        user_id=user.id,
        original_filename="dup.pdf",
        file_size_bytes=50,
        parsed_text="dup test",
        structured_data={},
    )
    skill = SkillTaxonomy(
        canonical_name=f"Rust_{uuid.uuid4().hex[:6]}", category="Programming Language"
    )
    db_session.add_all([resume, skill])
    await db_session.flush()

    await db_session.execute(
        insert(resume_skills).values(resume_id=resume.id, skill_id=skill.id)
    )
    await db_session.flush()

    # Second insert must fail
    with pytest.raises(Exception):
        await db_session.execute(
            insert(resume_skills).values(resume_id=resume.id, skill_id=skill.id)
        )
        await db_session.flush()


@pytest.mark.asyncio
async def test_duplicate_job_skill_rejected(db_session: AsyncSession):
    """
    Inserting the same (job_id, skill_id) twice must raise an integrity error.
    """
    user = User(email=f"dup_js_{uuid.uuid4().hex[:8]}@test.com", hashed_password="pw")
    db_session.add(user)
    await db_session.flush()

    job = Job(
        user_id=user.id, title="ML Engineer",
        raw_text="Need ML skills", structured_data={},
    )
    skill = SkillTaxonomy(
        canonical_name=f"TF_{uuid.uuid4().hex[:6]}", category="Framework"
    )
    db_session.add_all([job, skill])
    await db_session.flush()

    await db_session.execute(
        insert(job_skills).values(job_id=job.id, skill_id=skill.id)
    )
    await db_session.flush()

    with pytest.raises(Exception):
        await db_session.execute(
            insert(job_skills).values(job_id=job.id, skill_id=skill.id)
        )
        await db_session.flush()


@pytest.mark.asyncio
async def test_cascade_delete_resume_removes_skill_associations(db_session: AsyncSession):
    """
    Deleting a resume must cascade-delete its resume_skills rows
    without deleting the skill itself.
    """
    user = User(email=f"cas_r_{uuid.uuid4().hex[:8]}@test.com", hashed_password="pw")
    db_session.add(user)
    await db_session.flush()

    resume = Resume(
        user_id=user.id, original_filename="cas.pdf",
        file_size_bytes=50, parsed_text="cascade test", structured_data={},
    )
    skill = SkillTaxonomy(
        canonical_name=f"Java_{uuid.uuid4().hex[:6]}", category="Programming Language"
    )
    db_session.add_all([resume, skill])
    await db_session.flush()

    await db_session.execute(
        insert(resume_skills).values(resume_id=resume.id, skill_id=skill.id)
    )
    await db_session.flush()

    resume_id = resume.id
    skill_id = skill.id

    # Delete the resume
    await db_session.delete(resume)
    await db_session.flush()

    # Association row must be gone
    row = await db_session.execute(
        select(resume_skills).where(resume_skills.c.resume_id == resume_id)
    )
    assert row.first() is None, "resume_skills rows must cascade-delete with the resume"

    # Skill must survive
    surviving = await db_session.get(SkillTaxonomy, skill_id)
    assert surviving is not None, "SkillTaxonomy must not be deleted when a resume is deleted"


@pytest.mark.asyncio
async def test_cascade_delete_job_removes_skill_associations(db_session: AsyncSession):
    """
    Deleting a job must cascade-delete its job_skills rows
    without deleting the skill itself.
    """
    user = User(email=f"cas_j_{uuid.uuid4().hex[:8]}@test.com", hashed_password="pw")
    db_session.add(user)
    await db_session.flush()

    job = Job(
        user_id=user.id, title="DevOps",
        raw_text="Need K8s skills", structured_data={},
    )
    skill = SkillTaxonomy(
        canonical_name=f"K8s_{uuid.uuid4().hex[:6]}", category="Infrastructure"
    )
    db_session.add_all([job, skill])
    await db_session.flush()

    await db_session.execute(
        insert(job_skills).values(job_id=job.id, skill_id=skill.id)
    )
    await db_session.flush()

    job_id = job.id
    skill_id = skill.id

    await db_session.delete(job)
    await db_session.flush()

    row = await db_session.execute(
        select(job_skills).where(job_skills.c.job_id == job_id)
    )
    assert row.first() is None, "job_skills rows must cascade-delete with the job"

    surviving = await db_session.get(SkillTaxonomy, skill_id)
    assert surviving is not None, "SkillTaxonomy must not be deleted when a job is deleted"


@pytest.mark.asyncio
async def test_cascade_delete_skill_removes_associations_not_entities(db_session: AsyncSession):
    """
    Deleting a skill must cascade-delete its association rows in both
    resume_skills and job_skills, but must NOT delete the resume or job.
    """
    user = User(email=f"cas_s_{uuid.uuid4().hex[:8]}@test.com", hashed_password="pw")
    db_session.add(user)
    await db_session.flush()

    resume = Resume(
        user_id=user.id, original_filename="sk.pdf",
        file_size_bytes=50, parsed_text="skill cascade test", structured_data={},
    )
    job = Job(
        user_id=user.id, title="Data Eng",
        raw_text="Need SQL skills", structured_data={},
    )
    skill = SkillTaxonomy(
        canonical_name=f"SQL_{uuid.uuid4().hex[:6]}", category="Database"
    )
    db_session.add_all([resume, job, skill])
    await db_session.flush()

    await db_session.execute(
        insert(resume_skills).values(resume_id=resume.id, skill_id=skill.id)
    )
    await db_session.execute(
        insert(job_skills).values(job_id=job.id, skill_id=skill.id)
    )
    await db_session.flush()

    resume_id = resume.id
    job_id = job.id
    skill_id = skill.id

    # Delete the skill
    await db_session.delete(skill)
    await db_session.flush()

    # Association rows must be gone
    rs_row = await db_session.execute(
        select(resume_skills).where(resume_skills.c.skill_id == skill_id)
    )
    assert rs_row.first() is None, "resume_skills rows must cascade when skill is deleted"

    js_row = await db_session.execute(
        select(job_skills).where(job_skills.c.skill_id == skill_id)
    )
    assert js_row.first() is None, "job_skills rows must cascade when skill is deleted"

    # Resume and Job must survive
    surviving_resume = await db_session.get(Resume, resume_id)
    assert surviving_resume is not None, "Resume must survive skill deletion"
    surviving_job = await db_session.get(Job, job_id)
    assert surviving_job is not None, "Job must survive skill deletion"


@pytest.mark.asyncio
async def test_orm_relationship_resume_skills(db_session: AsyncSession):
    """
    Verify ORM relationship navigation: resume.skills can be populated
    and loaded via selectinload.
    """
    user = User(email=f"orm_rs_{uuid.uuid4().hex[:8]}@test.com", hashed_password="pw")
    db_session.add(user)
    await db_session.flush()

    skill1 = SkillTaxonomy(canonical_name=f"FastAPI_{uuid.uuid4().hex[:6]}", category="Web Framework")
    skill2 = SkillTaxonomy(canonical_name=f"Docker_{uuid.uuid4().hex[:6]}", category="DevOps")
    db_session.add_all([skill1, skill2])
    await db_session.flush()

    resume = Resume(
        user_id=user.id,
        original_filename="orm_test.pdf",
        file_size_bytes=200,
        parsed_text="FastAPI Docker expert",
        structured_data={"skills": ["FastAPI", "Docker"]},
    )
    resume.skills.extend([skill1, skill2])
    db_session.add(resume)
    await db_session.flush()

    # Query with selectinload to verify ORM eager loading
    stmt = select(Resume).options(selectinload(Resume.skills)).where(Resume.id == resume.id)
    result = await db_session.execute(stmt)
    loaded_resume = result.scalar_one()

    loaded_skill_names = {s.canonical_name for s in loaded_resume.skills}
    assert skill1.canonical_name in loaded_skill_names
    assert skill2.canonical_name in loaded_skill_names


@pytest.mark.asyncio
async def test_orm_relationship_job_skills(db_session: AsyncSession):
    """
    Verify ORM relationship navigation: job.skills can be populated
    and loaded via selectinload.
    """
    user = User(email=f"orm_js_{uuid.uuid4().hex[:8]}@test.com", hashed_password="pw")
    db_session.add(user)
    await db_session.flush()

    skill = SkillTaxonomy(canonical_name=f"PostgreSQL_{uuid.uuid4().hex[:6]}", category="Database")
    db_session.add(skill)
    await db_session.flush()

    job = Job(
        user_id=user.id,
        title="Database Architect",
        raw_text="PostgreSQL tuning",
        structured_data={"required_skills": ["PostgreSQL"]},
    )
    job.skills.append(skill)
    db_session.add(job)
    await db_session.flush()

    # Query with selectinload
    stmt = select(Job).options(selectinload(Job.skills)).where(Job.id == job.id)
    result = await db_session.execute(stmt)
    loaded_job = result.scalar_one()

    assert len(loaded_job.skills) == 1
    assert loaded_job.skills[0].canonical_name == skill.canonical_name
