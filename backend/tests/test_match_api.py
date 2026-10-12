from datetime import UTC, datetime
from typing import Dict, List, Optional
import uuid
from httpx import ASGITransport, AsyncClient
import pytest
from app.core.security import create_access_token, hash_password
from app.db.session import get_db
from app.main import app
from app.models.job import Job
from app.models.match import Match
from app.models.resume import Resume
from app.models.user import User
from app.repositories.job_repository import JobRepository
from app.repositories.match_repository import MatchRepository
from app.repositories.resume_repository import ResumeRepository
from app.repositories.user_repository import UserRepository


class MockUnifiedStorage:
    def __init__(self):
        self.users: Dict[uuid.UUID, User] = {}
        self.resumes: Dict[uuid.UUID, Resume] = {}
        self.jobs: Dict[uuid.UUID, Job] = {}
        self.matches: Dict[uuid.UUID, Match] = {}

    def add_user(self, email: str, is_superuser: bool = False) -> User:
        user_id = uuid.uuid4()
        user = User(
            id=user_id,
            email=email.lower().strip(),
            hashed_password=hash_password("StrongPassword123!"),
            is_active=True,
            is_superuser=is_superuser,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        self.users[user_id] = user
        return user


@pytest.fixture
def mock_storage(monkeypatch):
    storage = MockUnifiedStorage()

    # UserRepo mock
    async def _mock_get_user(self, id_: uuid.UUID):
        return storage.users.get(id_)
    monkeypatch.setattr(UserRepository, "get_by_id", _mock_get_user)

    # ResumeRepo mock
    async def _mock_get_resume(self, id_: uuid.UUID):
        return storage.resumes.get(id_)
    async def _mock_create_resume(self, instance: Resume):
        if not instance.id: instance.id = uuid.uuid4()
        if not instance.created_at: instance.created_at = datetime.now(UTC)
        storage.resumes[instance.id] = instance
        return instance
    monkeypatch.setattr(ResumeRepository, "get_by_id", _mock_get_resume)
    monkeypatch.setattr(ResumeRepository, "create", _mock_create_resume)

    # JobRepo mock
    async def _mock_get_job(self, id_: uuid.UUID):
        return storage.jobs.get(id_)
    async def _mock_create_job(self, instance: Job):
        if not instance.id: instance.id = uuid.uuid4()
        if not instance.created_at: instance.created_at = datetime.now(UTC)
        storage.jobs[instance.id] = instance
        return instance
    monkeypatch.setattr(JobRepository, "get_by_id", _mock_get_job)
    monkeypatch.setattr(JobRepository, "create", _mock_create_job)

    # MatchRepo mock
    async def _mock_get_match(self, id_: uuid.UUID):
        return storage.matches.get(id_)
    async def _mock_create_match(self, instance: Match):
        if not instance.id: instance.id = uuid.uuid4()
        if not instance.created_at: instance.created_at = datetime.now(UTC)
        storage.matches[instance.id] = instance
        return instance
    async def _mock_get_user_matches(self, user_id: uuid.UUID, skip: int = 0, limit: int = 50):
        matching = [m for m in storage.matches.values() if m.user_id == user_id]
        matching.sort(key=lambda m: m.created_at, reverse=True)
        return matching[skip : skip + limit]
    async def _mock_delete_match(self, instance: Match):
        storage.matches.pop(instance.id, None)

    monkeypatch.setattr(MatchRepository, "get_by_id", _mock_get_match)
    monkeypatch.setattr(MatchRepository, "create", _mock_create_match)
    monkeypatch.setattr(MatchRepository, "get_by_user_id", _mock_get_user_matches)
    monkeypatch.setattr(MatchRepository, "delete", _mock_delete_match)

    async def _dummy_get_db():
        class DummySession:
            async def commit(self): pass
            async def rollback(self): pass
            async def close(self): pass
        yield DummySession()

    app.dependency_overrides[get_db] = _dummy_get_db
    yield storage
    app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# Authentication Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_match_without_jwt_rejected():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/v1/match",
            json={"resume_id": str(uuid.uuid4()), "job_id": str(uuid.uuid4())},
        )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_match_with_invalid_jwt_rejected():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/v1/match",
            json={"resume_id": str(uuid.uuid4()), "job_id": str(uuid.uuid4())},
            headers={"Authorization": "Bearer invalid.token"},
        )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Matching Execution Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_match_with_saved_resume_and_job(mock_storage):
    user = mock_storage.add_user("candidate_match@example.com")
    token = create_access_token(subject=str(user.id))

    # Create candidate resume
    resume_id = uuid.uuid4()
    resume = Resume(
        id=resume_id,
        user_id=user.id,
        original_filename="candidate.pdf",
        file_size_bytes=1000,
        parsed_text="Senior Python and FastAPI engineer with 5 years experience.",
        structured_data={
            "skills": ["Python", "FastAPI", "PostgreSQL"],
            "experience_years": 5.0,
            "education_level": "Bachelor's",
        },
        embedding=[0.05] * 384,
    )
    mock_storage.resumes[resume_id] = resume

    # Create target job
    job_id = uuid.uuid4()
    job = Job(
        id=job_id,
        user_id=user.id,
        title="Senior Python Backend Engineer",
        raw_text="Requirements: Python, FastAPI. Preferred: Docker.",
        structured_data={
            "required_skills": ["Python", "FastAPI"],
            "preferred_skills": ["Docker"],
            "minimum_experience_years": 4.0,
            "minimum_education_level": "Bachelor's",
        },
        embedding=[0.05] * 384,
    )
    mock_storage.jobs[job_id] = job

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/v1/match",
            json={"resume_id": str(resume_id), "job_id": str(job_id)},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    data = response.json()
    assert "overall_score" in data
    assert "semantic_score" in data
    assert "skill_score" in data
    assert "experience_score" in data
    assert "education_score" in data
    assert "fit_category" in data
    assert "skills_breakdown" in data
    assert "experience_breakdown" in data
    assert "education_breakdown" in data
    assert "explanation" in data
    assert data["match_id"] is not None

    # Verify score bounds
    assert 0.0 <= data["overall_score"] <= 100.0
    assert 0.0 <= data["skill_score"] <= 100.0


@pytest.mark.asyncio
async def test_match_with_on_the_fly_job_text(mock_storage):
    user = mock_storage.add_user("candidate_otf@example.com")
    token = create_access_token(subject=str(user.id))

    resume_id = uuid.uuid4()
    resume = Resume(
        id=resume_id,
        user_id=user.id,
        original_filename="dev.pdf",
        file_size_bytes=1000,
        parsed_text="Software engineer with Python and Docker.",
        structured_data={
            "skills": ["Python", "Docker"],
            "experience_years": 3.0,
            "education_level": "Bachelor's",
        },
        embedding=[0.01] * 384,
    )
    mock_storage.resumes[resume_id] = resume

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/v1/match",
            json={
                "resume_id": str(resume_id),
                "job_text": "We need a Software Engineer with Python and Docker experience.",
                "job_title": "Software Engineer",
            },
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["overall_score"] > 0.0
    assert "skills_breakdown" in data


@pytest.mark.asyncio
async def test_match_without_job_rejected(mock_storage):
    user = mock_storage.add_user("candidate_err@example.com")
    token = create_access_token(subject=str(user.id))

    resume_id = uuid.uuid4()
    mock_storage.resumes[resume_id] = Resume(
        id=resume_id,
        user_id=user.id,
        original_filename="doc.pdf",
        file_size_bytes=500,
        parsed_text="test",
        structured_data={},
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/v1/match",
            json={"resume_id": str(resume_id)},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Tenant Ownership & Anti-IDOR Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_match_rejects_cross_tenant_resume(mock_storage):
    user1 = mock_storage.add_user("victim_resume@example.com")
    user2 = mock_storage.add_user("attacker_match@example.com")

    token2 = create_access_token(subject=str(user2.id))

    # Resume belongs to user 1
    resume_id = uuid.uuid4()
    mock_storage.resumes[resume_id] = Resume(
        id=resume_id,
        user_id=user1.id,
        original_filename="victim.pdf",
        file_size_bytes=500,
        parsed_text="Python",
        structured_data={"skills": ["Python"]},
        embedding=[0.0] * 384,
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # User 2 tries to run match against user 1's resume
        response = await client.post(
            "/api/v1/match",
            json={
                "resume_id": str(resume_id),
                "job_text": "Requirements: Python experience required.",
            },
            headers={"Authorization": f"Bearer {token2}"},
        )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_match_rejects_cross_tenant_job(mock_storage):
    user1 = mock_storage.add_user("owner_job_tenant@example.com")
    user2 = mock_storage.add_user("intruder_job_tenant@example.com")

    token2 = create_access_token(subject=str(user2.id))

    # Resume belongs to user 2
    resume_id = uuid.uuid4()
    mock_storage.resumes[resume_id] = Resume(
        id=resume_id,
        user_id=user2.id,
        original_filename="user2.pdf",
        file_size_bytes=500,
        parsed_text="Python",
        structured_data={"skills": ["Python"]},
        embedding=[0.0] * 384,
    )

    # Job belongs to user 1
    job_id = uuid.uuid4()
    mock_storage.jobs[job_id] = Job(
        id=job_id,
        user_id=user1.id,
        title="Secret Position",
        raw_text="Requirements: Python",
        structured_data={"required_skills": ["Python"]},
        embedding=[0.0] * 384,
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/v1/match",
            json={"resume_id": str(resume_id), "job_id": str(job_id)},
            headers={"Authorization": f"Bearer {token2}"},
        )

    assert response.status_code == 403


# ---------------------------------------------------------------------------
# History & Detail CRUD Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_match_history_scoped_to_user(mock_storage):
    user1 = mock_storage.add_user("history_user1@example.com")
    user2 = mock_storage.add_user("history_user2@example.com")

    token1 = create_access_token(subject=str(user1.id))
    token2 = create_access_token(subject=str(user2.id))

    r1 = uuid.uuid4()
    j1 = uuid.uuid4()
    mock_storage.resumes[r1] = Resume(id=r1, user_id=user1.id, original_filename="r1.pdf", file_size_bytes=100, parsed_text="Py", structured_data={"skills": ["Python"]}, embedding=[0.1]*384)
    mock_storage.jobs[j1] = Job(id=j1, user_id=user1.id, title="J1", raw_text="Py", structured_data={"required_skills": ["Python"]}, embedding=[0.1]*384)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # User 1 runs a match
        await client.post(
            "/api/v1/match",
            json={"resume_id": str(r1), "job_id": str(j1)},
            headers={"Authorization": f"Bearer {token1}"},
        )

        hist1 = await client.get("/api/v1/match/history", headers={"Authorization": f"Bearer {token1}"})
        hist2 = await client.get("/api/v1/match/history", headers={"Authorization": f"Bearer {token2}"})

    assert hist1.status_code == 200
    assert len(hist1.json()) == 1

    assert hist2.status_code == 200
    assert len(hist2.json()) == 0


@pytest.mark.asyncio
async def test_get_and_delete_match_detail(mock_storage):
    user = mock_storage.add_user("detail_user@example.com")
    token = create_access_token(subject=str(user.id))

    r_id = uuid.uuid4()
    j_id = uuid.uuid4()
    mock_storage.resumes[r_id] = Resume(id=r_id, user_id=user.id, original_filename="r.pdf", file_size_bytes=100, parsed_text="Py", structured_data={"skills": ["Python"]}, embedding=[0.1]*384)
    mock_storage.jobs[j_id] = Job(id=j_id, user_id=user.id, title="J", raw_text="Py", structured_data={"required_skills": ["Python"]}, embedding=[0.1]*384)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        created = await client.post(
            "/api/v1/match",
            json={"resume_id": str(r_id), "job_id": str(j_id)},
            headers={"Authorization": f"Bearer {token}"},
        )
        match_id = created.json()["match_id"]

        # Detail
        detail = await client.get(f"/api/v1/match/{match_id}", headers={"Authorization": f"Bearer {token}"})
        assert detail.status_code == 200
        assert detail.json()["match_id"] == match_id

        # Delete
        del_resp = await client.delete(f"/api/v1/match/{match_id}", headers={"Authorization": f"Bearer {token}"})
        assert del_resp.status_code == 200

        # Subsequent GET yields 404
        get_again = await client.get(f"/api/v1/match/{match_id}", headers={"Authorization": f"Bearer {token}"})
        assert get_again.status_code == 404
