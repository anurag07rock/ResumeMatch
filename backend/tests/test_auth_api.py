from datetime import UTC, datetime, timedelta
import uuid
from typing import Optional
from httpx import ASGITransport, AsyncClient
import pytest
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
)
from app.db.session import get_db
from app.main import app
from app.models.user import User
from app.repositories.user_repository import UserRepository


class MockUserStorage:
    """Thread-safe in-memory store simulating database persistence for tests."""
    def __init__(self):
        self.users_by_email = {}
        self.users_by_id = {}

    def get_by_email(self, email: str) -> Optional[User]:
        return self.users_by_email.get(email.lower().strip())

    def get_by_id(self, id_: uuid.UUID) -> Optional[User]:
        return self.users_by_id.get(id_)

    def create(self, user: User) -> User:
        if not user.id:
            user.id = uuid.uuid4()
        if not user.created_at:
            user.created_at = datetime.now(UTC)
        if not user.updated_at:
            user.updated_at = datetime.now(UTC)
        self.users_by_email[user.email.lower().strip()] = user
        self.users_by_id[user.id] = user
        return user


@pytest.fixture
def mock_storage(monkeypatch):
    """Overrides UserRepository data access methods with in-memory storage."""
    storage = MockUserStorage()

    async def _mock_get_by_email(self, email: str):
        return storage.get_by_email(email)

    async def _mock_get_by_id(self, id_: uuid.UUID):
        return storage.get_by_id(id_)

    async def _mock_create(self, instance: User):
        return storage.create(instance)

    monkeypatch.setattr(UserRepository, "get_by_email", _mock_get_by_email)
    monkeypatch.setattr(UserRepository, "get_by_id", _mock_get_by_id)
    monkeypatch.setattr(UserRepository, "create", _mock_create)

    # Override get_db with dummy async generator to avoid live DB connections
    async def _dummy_get_db():
        class DummySession:
            async def commit(self): pass
            async def rollback(self): pass
            async def close(self): pass
        yield DummySession()

    app.dependency_overrides[get_db] = _dummy_get_db
    yield storage
    app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_successful_registration(mock_storage):
    """Tests POST /api/v1/auth/register with valid payload."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "candidate@example.com",
                "password": "StrongPassword123!",
                "full_name": "Jane Doe",
            },
        )

    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "candidate@example.com"
    assert data["full_name"] == "Jane Doe"
    assert "id" in data
    assert "created_at" in data
    assert "password" not in data
    assert "hashed_password" not in data


@pytest.mark.asyncio
async def test_duplicate_email_rejection(mock_storage):
    """Tests POST /api/v1/auth/register rejects already registered email with canonical 400 error."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # First registration
        res1 = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "duplicate@example.com",
                "password": "StrongPassword123!",
            },
        )
        assert res1.status_code == 201

        # Second registration with duplicate email
        res2 = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "DUPLICATE@example.com",
                "password": "AnotherStrongPassword123!",
            },
        )

    assert res2.status_code == 400
    data = res2.json()
    assert "error" in data
    assert data["error"]["code"] == "BAD_REQUEST"
    assert "already exists" in data["error"]["message"].lower()


@pytest.mark.asyncio
async def test_invalid_password_rejection(mock_storage):
    """Tests POST /api/v1/auth/register rejects passwords failing complexity requirements."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Missing symbols and digits
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "candidate@example.com",
                "password": "alllowercaseandnumbers123",
            },
        )

    assert response.status_code == 422
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_successful_login(mock_storage):
    """Tests POST /api/v1/auth/login returns valid access and refresh tokens."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Register user
        reg_resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "login_test@example.com",
                "password": "StrongPassword123!",
            },
        )
        assert reg_resp.status_code == 201

        # Login
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "login_test@example.com",
                "password": "StrongPassword123!",
            },
        )

    assert login_resp.status_code == 200
    data = login_resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] == 3600


@pytest.mark.asyncio
async def test_wrong_password_rejection(mock_storage):
    """Tests POST /api/v1/auth/login returns 401 when given an incorrect password."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        await client.post(
            "/api/v1/auth/register",
            json={
                "email": "wrong_pw@example.com",
                "password": "StrongPassword123!",
            },
        )

        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "wrong_pw@example.com",
                "password": "IncorrectPassword123!",
            },
        )

    assert response.status_code == 401
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "UNAUTHORIZED"
    assert "invalid email or password" in data["error"]["message"].lower()


@pytest.mark.asyncio
async def test_access_and_refresh_token_generation(mock_storage):
    """Validates the structure and claims of issued access and refresh tokens."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        reg = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "tokens_check@example.com",
                "password": "StrongPassword123!",
            },
        )
        user_id = reg.json()["id"]

        login = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "tokens_check@example.com",
                "password": "StrongPassword123!",
            },
        )
        tokens = login.json()

    # Decode and verify access token
    access_payload = decode_token(tokens["access_token"])
    assert access_payload["sub"] == user_id
    assert access_payload["type"] == "access"

    # Decode and verify refresh token
    refresh_payload = decode_token(tokens["refresh_token"])
    assert refresh_payload["sub"] == user_id
    assert refresh_payload["type"] == "refresh"


@pytest.mark.asyncio
async def test_protected_me_endpoint_success(mock_storage):
    """Tests GET /api/v1/auth/me returns current user profile with valid Bearer token."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        reg = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "me_user@example.com",
                "password": "StrongPassword123!",
                "full_name": "Me User",
            },
        )
        user_data = reg.json()

        login = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "me_user@example.com",
                "password": "StrongPassword123!",
            },
        )
        token = login.json()["access_token"]

        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    profile = response.json()
    assert profile["id"] == user_data["id"]
    assert profile["email"] == "me_user@example.com"
    assert profile["full_name"] == "Me User"


@pytest.mark.asyncio
async def test_protected_me_missing_token_rejection(mock_storage):
    """Tests GET /api/v1/auth/me returns 401 when no token is provided."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/v1/auth/me")

    assert response.status_code == 401
    data = response.json()
    assert data["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_invalid_jwt_rejection(mock_storage):
    """Tests GET /api/v1/auth/me rejects an invalid/tampered JWT."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid.malformed.token"},
        )

    assert response.status_code == 401
    data = response.json()
    assert data["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_expired_token_rejection(mock_storage):
    """Tests GET /api/v1/auth/me rejects expired tokens with 401."""
    # Seed a user
    user = User(
        id=uuid.uuid4(),
        email="expired@example.com",
        hashed_password=hash_password("StrongPassword123!"),
        is_active=True,
    )
    mock_storage.create(user)

    # Create expired token
    expired_token = create_access_token(
        subject=str(user.id),
        expires_delta=timedelta(seconds=-30),
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {expired_token}"},
        )

    assert response.status_code == 401
    data = response.json()
    assert data["error"]["code"] == "UNAUTHORIZED"
    assert "expired" in data["error"]["message"].lower()


@pytest.mark.asyncio
async def test_refresh_token_rejected_on_access_route(mock_storage):
    """Tests GET /api/v1/auth/me rejects refresh tokens when access token is expected."""
    user = User(
        id=uuid.uuid4(),
        email="refresh_as_access@example.com",
        hashed_password=hash_password("StrongPassword123!"),
        is_active=True,
    )
    mock_storage.create(user)

    refresh_token = create_refresh_token(subject=str(user.id))

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {refresh_token}"},
        )

    assert response.status_code == 401
    data = response.json()
    assert data["error"]["code"] == "UNAUTHORIZED"
    assert "access token is required" in data["error"]["message"].lower()
