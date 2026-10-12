from datetime import UTC, datetime
import uuid
from httpx import ASGITransport, AsyncClient
import pytest
from app.core.config import settings
from app.core.limiter import limiter
from app.core.security import create_access_token, hash_password
from app.db.session import get_db
from app.main import app
from app.models.user import User
from app.repositories.user_repository import UserRepository


class MockUserStorage:
    def __init__(self):
        self.users_by_email = {}
        self.users_by_id = {}

    def get_by_email(self, email: str):
        return self.users_by_email.get(email.lower().strip())

    def get_by_id(self, id_: uuid.UUID):
        return self.users_by_id.get(id_)

    def create(self, user: User):
        if not user.id:
            user.id = uuid.uuid4()
        self.users_by_email[user.email.lower().strip()] = user
        self.users_by_id[user.id] = user
        return user


@pytest.fixture
def rate_limit_setup(monkeypatch):
    storage = MockUserStorage()
    test_user = User(
        id=uuid.uuid4(),
        email="ratelimit_user@example.com",
        hashed_password=hash_password("SecurePass123!"),
        full_name="Rate Limit User",
        is_active=True,
        is_superuser=False,
    )
    storage.create(test_user)

    async def _mock_get_by_email(self, email: str):
        return storage.get_by_email(email)

    async def _mock_get_by_id(self, id_: uuid.UUID):
        return storage.get_by_id(id_)

    async def _mock_create(self, instance: User):
        return storage.create(instance)

    monkeypatch.setattr(UserRepository, "get_by_email", _mock_get_by_email)
    monkeypatch.setattr(UserRepository, "get_by_id", _mock_get_by_id)
    monkeypatch.setattr(UserRepository, "create", _mock_create)

    async def _dummy_get_db():
        class DummySession:
            async def commit(self): pass
            async def rollback(self): pass
            async def close(self): pass
        yield DummySession()

    app.dependency_overrides[get_db] = _dummy_get_db
    limiter.reset()
    yield {"user": test_user}
    app.dependency_overrides.pop(get_db, None)
    limiter.reset()


@pytest.mark.asyncio
async def test_auth_rate_limiting_enforced(rate_limit_setup):
    """
    Verifies that authentication endpoint (POST /auth/login) enforces AUTH_RATE_LIMIT (5/minute).
    Requests 1-5 succeed or return normal auth responses, and request 6 is throttled with 429.
    """
    limiter.reset()
    limiter.enabled = True
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {"email": "ratelimit_user@example.com", "password": "SecurePass123!"}

        # 5 requests within limit
        for i in range(5):
            res = await client.post("/api/v1/auth/login", json=payload)
            assert res.status_code == 200, f"Request {i+1} failed with {res.status_code}: {res.text}"

        # 6th request must exceed rate limit
        throttled_res = await client.post("/api/v1/auth/login", json=payload)
        assert throttled_res.status_code == 429
        data = throttled_res.json()

        # Canonical error envelope assertions
        assert "error" in data
        assert data["error"]["code"] == "RATE_LIMIT_EXCEEDED"
        assert "Rate limit exceeded" in data["error"]["message"]
        assert "Retry-After" in throttled_res.headers


@pytest.mark.asyncio
async def test_rate_limit_can_be_disabled_via_flag(rate_limit_setup):
    """
    Verifies that when limiter.enabled is False, requests are never throttled.
    """
    limiter.reset()
    limiter.enabled = False
    transport = ASGITransport(app=app)

    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            payload = {"email": "ratelimit_user@example.com", "password": "SecurePass123!"}
            for i in range(7):
                res = await client.post("/api/v1/auth/login", json=payload)
                assert res.status_code == 200
    finally:
        limiter.enabled = True
        limiter.reset()


@pytest.mark.asyncio
async def test_ai_rate_limiting_enforced(rate_limit_setup, monkeypatch):
    """
    Verifies that AI-heavy operations enforce rate limits with canonical 429 envelope.
    """
    from app.services.job_service import JobService
    test_user = rate_limit_setup["user"]
    token = create_access_token(subject=str(test_user.id))
    headers = {"Authorization": f"Bearer {token}"}

    # Mock quick JobService return so test executes swiftly
    async def _dummy_process_job(*args, **kwargs):
        class DummyJob:
            id = uuid.uuid4()
            user_id = test_user.id
            title = "Test Job"
            company = "Test Co"
            raw_text = "Python engineer"
            structured_data = {}
            embedding = [0.1] * 384
            created_at = datetime.now(UTC)
            is_active = True
        return DummyJob()

    monkeypatch.setattr(JobService, "process_and_create_job", _dummy_process_job)

    # Temporarily set AI_RATE_LIMIT to 3/minute for fast testing
    original_ai_limit = settings.AI_RATE_LIMIT
    settings.AI_RATE_LIMIT = "3/minute"
    limiter.reset()
    limiter.enabled = True

    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            payload = {"title": "Software Engineer", "raw_text": "Python and FastAPI developer"}

            # Send 3 requests
            for _ in range(3):
                res = await client.post("/api/v1/jobs/analyze", json=payload, headers=headers)
                assert res.status_code == 201

            # 4th request must be rate limited
            res4 = await client.post("/api/v1/jobs/analyze", json=payload, headers=headers)
            assert res4.status_code == 429
            data = res4.json()
            assert data["error"]["code"] == "RATE_LIMIT_EXCEEDED"
            assert "Retry-After" in res4.headers
    finally:
        settings.AI_RATE_LIMIT = original_ai_limit
        limiter.reset()
