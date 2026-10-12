from datetime import UTC, datetime, timedelta
import uuid
from typing import Optional
from httpx import ASGITransport, AsyncClient
import pytest
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from app.core.security import create_access_token
from app.db.session import get_db
from app.main import app
from app.models.job import Job
from app.models.resume import Resume
from app.models.user import User
from app.repositories.job_repository import JobRepository
from app.repositories.resume_repository import ResumeRepository
from app.repositories.user_repository import UserRepository


class MockUserStorage:
    def __init__(self):
        self.users = {}

    def create(self, user: User) -> User:
        if not user.id:
            user.id = uuid.uuid4()
        user.created_at = datetime.now(UTC)
        user.updated_at = datetime.now(UTC)
        self.users[user.id] = user
        return user

    def get_by_id(self, id_: uuid.UUID) -> Optional[User]:
        return self.users.get(id_)

    def get_by_email(self, email: str) -> Optional[User]:
        for u in self.users.values():
            if u.email.lower() == email.lower():
                return u
        return None


@pytest.fixture
def error_test_setup(monkeypatch):
    user_store = MockUserStorage()
    resumes = {}
    jobs = {}

    # Seed User A and User B
    user_a = User(
        id=uuid.uuid4(),
        email="usera@example.com",
        hashed_password="hash",
        full_name="User A",
        is_active=True,
        is_superuser=False,
    )
    user_store.create(user_a)

    user_b = User(
        id=uuid.uuid4(),
        email="userb@example.com",
        hashed_password="hash",
        full_name="User B",
        is_active=True,
        is_superuser=False,
    )
    user_store.create(user_b)

    # Seed Resume owned by User B
    resume_b = Resume(
        id=uuid.uuid4(),
        user_id=user_b.id,
        original_filename="userb_cv.pdf",
        parsed_text="software engineer with python experience",
        file_size_bytes=1024,
        structured_data={},
    )
    resumes[resume_b.id] = resume_b

    # Seed Job owned by User B
    job_b = Job(
        id=uuid.uuid4(),
        user_id=user_b.id,
        title="Backend Engineer",
        raw_text="Seeking Senior Python Backend Engineer",
        structured_data={},
    )
    jobs[job_b.id] = job_b

    async def _mock_user_get_by_id(self, uid):
        return user_store.get_by_id(uid)

    async def _mock_user_get_by_email(self, email):
        return user_store.get_by_email(email)

    async def _mock_resume_get_by_id(self, rid):
        return resumes.get(rid)

    async def _mock_job_get_by_id(self, jid):
        return jobs.get(jid)

    monkeypatch.setattr(UserRepository, "get_by_id", _mock_user_get_by_id)
    monkeypatch.setattr(UserRepository, "get_by_email", _mock_user_get_by_email)
    monkeypatch.setattr(ResumeRepository, "get_by_id", _mock_resume_get_by_id)
    monkeypatch.setattr(JobRepository, "get_by_id", _mock_job_get_by_id)

    async def _dummy_get_db():
        class DummySession:
            async def commit(self): pass
            async def rollback(self): pass
            async def close(self): pass
        yield DummySession()

    app.dependency_overrides[get_db] = _dummy_get_db
    yield {"user_a": user_a, "user_b": user_b, "resume_b": resume_b, "job_b": job_b}
    app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_validation_error_envelope(error_test_setup):
    """Verifies that schema validation failures conform to canonical error envelope."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Send empty payload to register endpoint
        response = await client.post("/api/v1/auth/register", json={})
        assert response.status_code == 422
        data = response.json()

        assert "error" in data
        assert data["error"]["code"] == "VALIDATION_ERROR"
        assert "message" in data["error"]
        assert isinstance(data["error"]["details"], list)
        assert len(data["error"]["details"]) > 0


@pytest.mark.asyncio
async def test_unauthorized_missing_token_envelope():
    """Verifies that unauthenticated requests to protected endpoints return canonical 401."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/auth/me")
        assert response.status_code == 401
        data = response.json()

        assert "error" in data
        assert data["error"]["code"] == "UNAUTHORIZED"
        assert "credentials were not provided" in data["error"]["message"].lower()


@pytest.mark.asyncio
async def test_invalid_jwt_envelope():
    """Verifies that invalid or corrupted JWTs return canonical 401 envelope."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": "Bearer totally-invalid-garbage-token"}
        response = await client.get("/api/v1/auth/me", headers=headers)
        assert response.status_code == 401
        data = response.json()

        assert "error" in data
        assert data["error"]["code"] == "UNAUTHORIZED"
        assert "invalid" in data["error"]["message"].lower()


@pytest.mark.asyncio
async def test_expired_jwt_envelope(error_test_setup):
    """Verifies that expired JWTs return canonical 401 envelope."""
    user_a = error_test_setup["user_a"]
    expired_token = create_access_token(
        subject=str(user_a.id),
        expires_delta=timedelta(seconds=-60),
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": f"Bearer {expired_token}"}
        response = await client.get("/api/v1/auth/me", headers=headers)
        assert response.status_code == 401
        data = response.json()

        assert "error" in data
        assert data["error"]["code"] == "UNAUTHORIZED"
        assert "expired" in data["error"]["message"].lower()


@pytest.mark.asyncio
async def test_forbidden_tenant_access_envelope(error_test_setup):
    """Verifies that anti-IDOR violations return canonical 403 envelope."""
    user_a = error_test_setup["user_a"]
    resume_b = error_test_setup["resume_b"]
    token_a = create_access_token(subject=str(user_a.id))

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": f"Bearer {token_a}"}
        response = await client.get(f"/api/v1/resumes/{resume_b.id}", headers=headers)
        assert response.status_code == 403
        data = response.json()

        assert "error" in data
        assert data["error"]["code"] == "FORBIDDEN"
        assert "forbidden" in data["error"]["message"].lower()


@pytest.mark.asyncio
async def test_internal_exception_mapping_never_leaks_stack_traces(error_test_setup, monkeypatch):
    """
    Verifies that unhandled server exceptions return 500 without leaking stack traces or internal details.
    """
    user_a = error_test_setup["user_a"]
    token_a = create_access_token(subject=str(user_a.id))

    # Mock an unexpected crash in a service method
    async def _crashing_method(*args, **kwargs):
        raise RuntimeError("Secret internal database password: 'supersecret'")

    monkeypatch.setattr(ResumeRepository, "get_by_id", _crashing_method)

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": f"Bearer {token_a}"}
        response = await client.get(f"/api/v1/resumes/{uuid.uuid4()}", headers=headers)
        assert response.status_code == 500
        data = response.json()

        assert "error" in data
        assert data["error"]["code"] == "INTERNAL_SERVER_ERROR"
        assert data["error"]["message"] == "An unexpected server error occurred."
        # Verify NO secret or stack trace is exposed
        assert "supersecret" not in response.text
        assert "Traceback" not in response.text
        assert data["error"]["details"] == {}


@pytest.mark.asyncio
async def test_database_integrity_error_mapping(error_test_setup, monkeypatch):
    """
    Verifies that database IntegrityErrors return 409 without leaking raw SQL strings.
    """
    user_a = error_test_setup["user_a"]
    token_a = create_access_token(subject=str(user_a.id))

    async def _integrity_fail(*args, **kwargs):
        raise IntegrityError("SELECT * FROM sensitive_table", {}, Exception("foreign key violation"))

    monkeypatch.setattr(JobRepository, "get_by_id", _integrity_fail)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": f"Bearer {token_a}"}
        response = await client.get(f"/api/v1/jobs/{uuid.uuid4()}", headers=headers)
        assert response.status_code == 409
        data = response.json()

        assert "error" in data
        assert data["error"]["code"] == "CONFLICT"
        assert "sensitive_table" not in response.text
