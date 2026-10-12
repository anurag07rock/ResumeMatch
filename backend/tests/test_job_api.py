from datetime import UTC, datetime
from typing import Dict, List, Optional
import uuid
from httpx import ASGITransport, AsyncClient
import pytest
from app.core.security import create_access_token, hash_password
from app.db.session import get_db
from app.main import app
from app.models.job import Job
from app.models.user import User
from app.repositories.job_repository import JobRepository
from app.repositories.user_repository import UserRepository


class MockJobStorage:
    def __init__(self):
        self.users: Dict[uuid.UUID, User] = {}
        self.jobs: Dict[uuid.UUID, Job] = {}

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
    storage = MockJobStorage()

    async def _mock_get_by_id_user(self, id_: uuid.UUID):
        return storage.users.get(id_)

    monkeypatch.setattr(UserRepository, "get_by_id", _mock_get_by_id_user)

    async def _mock_create_job(self, instance: Job):
        if not instance.id:
            instance.id = uuid.uuid4()
        if not instance.created_at:
            instance.created_at = datetime.now(UTC)
        storage.jobs[instance.id] = instance
        return instance

    async def _mock_get_by_id_job(self, id_: uuid.UUID):
        return storage.jobs.get(id_)

    async def _mock_get_by_user_id_job(self, user_id: uuid.UUID, skip: int = 0, limit: int = 50):
        matching = [j for j in storage.jobs.values() if j.user_id == user_id]
        matching.sort(key=lambda j: j.created_at, reverse=True)
        return matching[skip : skip + limit]

    async def _mock_delete_job(self, instance: Job):
        storage.jobs.pop(instance.id, None)

    monkeypatch.setattr(JobRepository, "create", _mock_create_job)
    monkeypatch.setattr(JobRepository, "get_by_id", _mock_get_by_id_job)
    monkeypatch.setattr(JobRepository, "get_by_user_id", _mock_get_by_user_id_job)
    monkeypatch.setattr(JobRepository, "delete", _mock_delete_job)

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
async def test_job_analyze_without_jwt_rejected():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/v1/jobs/analyze",
            json={"title": "Backend Engineer", "raw_text": "We need Python and FastAPI."},
        )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_job_analyze_with_invalid_jwt_rejected():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/v1/jobs/analyze",
            json={"title": "Backend Engineer", "raw_text": "We need Python and FastAPI."},
            headers={"Authorization": "Bearer invalid.jwt.token"},
        )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Ingestion & Requirement Extraction Pipeline Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_job_analyze_successful_extraction(mock_storage):
    user = mock_storage.add_user("recruiter@example.com")
    token = create_access_token(subject=str(user.id))

    job_payload = {
        "title": "Senior Backend Engineer",
        "company": "Acme Cloud Corp",
        "raw_text": (
            "We are seeking a Senior Backend Engineer.\n\n"
            "Requirements:\n"
            "- At least 5 years of experience with Python, FastAPI, and PostgreSQL\n"
            "- Bachelor's degree in Computer Science\n\n"
            "Preferred Qualifications:\n"
            "- Experience with Docker and Kubernetes"
        ),
    }

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/v1/jobs/analyze",
            json=job_payload,
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Senior Backend Engineer"
    assert data["company"] == "Acme Cloud Corp"
    assert "skills_breakdown" in data
    assert "experience_breakdown" in data
    assert "education_breakdown" in data
    assert "explanation" in data

    # Verify skill partitioning
    req_skills = data["skills_breakdown"]["required_skills"]
    pref_skills = data["skills_breakdown"]["preferred_skills"]
    assert "Python" in req_skills
    assert "FastAPI" in req_skills
    assert "Docker" in pref_skills

    # Verify experience and education extraction
    assert data["experience_breakdown"]["minimum_years"] == 5.0
    assert data["education_breakdown"]["minimum_level"] == "Bachelor's"

    # Verify embedding attached to stored job
    job_record = mock_storage.jobs[uuid.UUID(data["id"])]
    assert job_record.embedding is not None
    assert len(job_record.embedding) == 384


@pytest.mark.asyncio
async def test_job_analyze_with_description_alias(mock_storage):
    user = mock_storage.add_user("recruiter2@example.com")
    token = create_access_token(subject=str(user.id))

    job_payload = {
        "title": "Data Engineer",
        "description": "Looking for a Data Engineer with Python, Spark, and SQL experience.",
    }

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/v1/jobs/analyze",
            json=job_payload,
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Data Engineer"
    assert "Python" in data["skills_breakdown"]["required_skills"]


@pytest.mark.asyncio
async def test_job_analyze_validation_errors(mock_storage):
    user = mock_storage.add_user("recruiter3@example.com")
    token = create_access_token(subject=str(user.id))

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Empty title
        res1 = await client.post(
            "/api/v1/jobs/analyze",
            json={"title": "", "raw_text": "Valid text with Python"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res1.status_code == 422

        # Too short text (< 10 chars)
        res2 = await client.post(
            "/api/v1/jobs/analyze",
            json={"title": "Engineer", "raw_text": "short"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res2.status_code == 422


# ---------------------------------------------------------------------------
# Tenant Ownership & Anti-IDOR Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_user_can_view_own_job(mock_storage):
    user = mock_storage.add_user("job_owner@example.com")
    token = create_access_token(subject=str(user.id))

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        created = await client.post(
            "/api/v1/jobs/analyze",
            json={"title": "ML Engineer", "raw_text": "Requirements: Python, PyTorch, and NLP."},
            headers={"Authorization": f"Bearer {token}"},
        )
        job_id = created.json()["id"]

        detail = await client.get(
            f"/api/v1/jobs/{job_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert detail.status_code == 200
    assert detail.json()["id"] == job_id


@pytest.mark.asyncio
async def test_user_cannot_view_another_users_job(mock_storage):
    user1 = mock_storage.add_user("owner1@example.com")
    user2 = mock_storage.add_user("intruder@example.com")

    token1 = create_access_token(subject=str(user1.id))
    token2 = create_access_token(subject=str(user2.id))

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        created = await client.post(
            "/api/v1/jobs/analyze",
            json={"title": "DevOps Engineer", "raw_text": "Requirements: Docker and Terraform."},
            headers={"Authorization": f"Bearer {token1}"},
        )
        job_id = created.json()["id"]

        forbidden = await client.get(
            f"/api/v1/jobs/{job_id}",
            headers={"Authorization": f"Bearer {token2}"},
        )

    assert forbidden.status_code == 403


@pytest.mark.asyncio
async def test_user_cannot_delete_another_users_job(mock_storage):
    user1 = mock_storage.add_user("owner2@example.com")
    user2 = mock_storage.add_user("intruder2@example.com")

    token1 = create_access_token(subject=str(user1.id))
    token2 = create_access_token(subject=str(user2.id))

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        created = await client.post(
            "/api/v1/jobs/analyze",
            json={"title": "QA Engineer", "raw_text": "Requirements: PyTest and Selenium."},
            headers={"Authorization": f"Bearer {token1}"},
        )
        job_id = created.json()["id"]

        forbidden = await client.delete(
            f"/api/v1/jobs/{job_id}",
            headers={"Authorization": f"Bearer {token2}"},
        )

    assert forbidden.status_code == 403
    assert uuid.UUID(job_id) in mock_storage.jobs


# ---------------------------------------------------------------------------
# CRUD Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_jobs_tenant_isolation(mock_storage):
    user1 = mock_storage.add_user("lister_job1@example.com")
    user2 = mock_storage.add_user("lister_job2@example.com")

    token1 = create_access_token(subject=str(user1.id))
    token2 = create_access_token(subject=str(user2.id))

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # User 1 creates 2 jobs
        await client.post(
            "/api/v1/jobs/analyze",
            json={"title": "Job A", "raw_text": "Python experience required."},
            headers={"Authorization": f"Bearer {token1}"},
        )
        await client.post(
            "/api/v1/jobs/analyze",
            json={"title": "Job B", "raw_text": "FastAPI experience required."},
            headers={"Authorization": f"Bearer {token1}"},
        )

        # User 2 creates 1 job
        await client.post(
            "/api/v1/jobs/analyze",
            json={"title": "Job C", "raw_text": "React experience required."},
            headers={"Authorization": f"Bearer {token2}"},
        )

        list1 = await client.get("/api/v1/jobs/", headers={"Authorization": f"Bearer {token1}"})
        list2 = await client.get("/api/v1/jobs/", headers={"Authorization": f"Bearer {token2}"})

    assert list1.status_code == 200
    assert len(list1.json()) == 2

    assert list2.status_code == 200
    assert len(list2.json()) == 1


@pytest.mark.asyncio
async def test_delete_job_success(mock_storage):
    user = mock_storage.add_user("deleter_job@example.com")
    token = create_access_token(subject=str(user.id))

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        created = await client.post(
            "/api/v1/jobs/analyze",
            json={"title": "Temporary Job", "raw_text": "Temporary description with Python."},
            headers={"Authorization": f"Bearer {token}"},
        )
        job_id = created.json()["id"]

        del_resp = await client.delete(
            f"/api/v1/jobs/{job_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert del_resp.status_code == 200
        assert "data" in del_resp.json()

        # Subsequent GET yields 404
        get_again = await client.get(
            f"/api/v1/jobs/{job_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert get_again.status_code == 404
