from datetime import UTC, datetime
import io
from typing import Dict, List, Optional
import uuid
from httpx import ASGITransport, AsyncClient
import pymupdf
import pytest
from app.core.config import settings
from app.core.security import create_access_token, hash_password
from app.db.session import get_db
from app.main import app
from app.models.resume import Resume
from app.models.user import User
from app.repositories.resume_repository import ResumeRepository
from app.repositories.user_repository import UserRepository


# ---------------------------------------------------------------------------
# Test Helpers for In-Memory PDF Generation
# ---------------------------------------------------------------------------

def create_in_memory_pdf(pages_text: List[str]) -> bytes:
    """Programmatically creates valid PDF bytes containing text per page."""
    doc = pymupdf.open()
    for text in pages_text:
        page = doc.new_page()
        if text:
            page.insert_text((50, 72), text)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def create_encrypted_pdf(text: str = "Confidential text") -> bytes:
    """Programmatically creates an AES-256 encrypted PDF in memory."""
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((50, 72), text)
    pdf_bytes = doc.tobytes(
        encryption=pymupdf.PDF_ENCRYPT_AES_256,
        user_pw="secret_pass",
    )
    doc.close()
    return pdf_bytes


# ---------------------------------------------------------------------------
# In-Memory Storage Simulator for Fast, Isolated Unit/Integration Tests
# ---------------------------------------------------------------------------

class MockStorage:
    def __init__(self):
        self.users: Dict[uuid.UUID, User] = {}
        self.users_by_email: Dict[str, User] = {}
        self.resumes: Dict[uuid.UUID, Resume] = {}

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
        self.users_by_email[email.lower().strip()] = user
        return user


@pytest.fixture
def mock_storage(monkeypatch):
    storage = MockStorage()

    # Mock UserRepository methods
    async def _mock_get_by_id_user(self, id_: uuid.UUID):
        return storage.users.get(id_)

    async def _mock_get_by_email(self, email: str):
        return storage.users_by_email.get(email.lower().strip())

    monkeypatch.setattr(UserRepository, "get_by_id", _mock_get_by_id_user)
    monkeypatch.setattr(UserRepository, "get_by_email", _mock_get_by_email)

    # Mock ResumeRepository methods
    async def _mock_create_resume(self, instance: Resume):
        if not instance.id:
            instance.id = uuid.uuid4()
        if not instance.created_at:
            instance.created_at = datetime.now(UTC)
        if not instance.updated_at:
            instance.updated_at = datetime.now(UTC)
        storage.resumes[instance.id] = instance
        return instance

    async def _mock_get_by_id_resume(self, id_: uuid.UUID):
        return storage.resumes.get(id_)

    async def _mock_get_by_user_id(self, user_id: uuid.UUID, skip: int = 0, limit: int = 50):
        matching = [r for r in storage.resumes.values() if r.user_id == user_id]
        matching.sort(key=lambda r: r.created_at, reverse=True)
        return matching[skip : skip + limit]

    async def _mock_delete_resume(self, instance: Resume):
        storage.resumes.pop(instance.id, None)

    monkeypatch.setattr(ResumeRepository, "create", _mock_create_resume)
    monkeypatch.setattr(ResumeRepository, "get_by_id", _mock_get_by_id_resume)
    monkeypatch.setattr(ResumeRepository, "get_by_user_id", _mock_get_by_user_id)
    monkeypatch.setattr(ResumeRepository, "delete", _mock_delete_resume)

    # Override get_db to dummy session
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
async def test_upload_without_jwt_rejected():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        files = {"file": ("resume.pdf", b"%PDF-1.4 dummy", "application/pdf")}
        response = await client.post("/api/v1/resumes/upload", files=files)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_upload_with_invalid_jwt_rejected():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        files = {"file": ("resume.pdf", b"%PDF-1.4 dummy", "application/pdf")}
        response = await client.post(
            "/api/v1/resumes/upload",
            files=files,
            headers={"Authorization": "Bearer invalid.jwt.token"},
        )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Upload Pipeline Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_valid_pdf_upload_succeeds_and_runs_pipeline(mock_storage):
    user = mock_storage.add_user("candidate@example.com")
    token = create_access_token(subject=str(user.id))

    resume_text = (
        "Jane Doe\n"
        "Senior Backend Engineer with 5 years of experience in Python, FastAPI, and PostgreSQL.\n"
        "Graduated with a Bachelor's in Computer Science."
    )
    pdf_bytes = create_in_memory_pdf([resume_text])

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        files = {"file": ("Jane_Doe_Resume.pdf", pdf_bytes, "application/pdf")}
        response = await client.post(
            "/api/v1/resumes/upload",
            files=files,
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 201
    data = response.json()
    assert data["original_filename"] == "Jane_Doe_Resume.pdf"
    assert "skills_breakdown" in data
    assert "experience_breakdown" in data
    assert "education_breakdown" in data
    assert "explanation" in data

    # Verify extracted skills
    extracted = data["skills_breakdown"].get("extracted_skills", [])
    assert "Python" in extracted
    assert "FastAPI" in extracted

    # Verify experience detection
    assert data["experience_breakdown"].get("detected_years") == 5.0

    # Verify education detection
    assert data["education_breakdown"].get("detected_level") == "Bachelor's"

    # Verify record in storage has 384-d embedding
    persisted = mock_storage.resumes[uuid.UUID(data["id"])]
    assert persisted.embedding is not None
    assert len(persisted.embedding) == 384


@pytest.mark.asyncio
async def test_invalid_pdf_rejected(mock_storage):
    user = mock_storage.add_user("candidate2@example.com")
    token = create_access_token(subject=str(user.id))

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Non-PDF binary
        files = {"file": ("fake.pdf", b"This is plain text without magic bytes", "application/pdf")}
        response = await client.post(
            "/api/v1/resumes/upload",
            files=files,
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 400
    data = response.json()
    assert data["error"]["code"] == "BAD_REQUEST"


@pytest.mark.asyncio
async def test_oversized_pdf_rejected(mock_storage):
    user = mock_storage.add_user("candidate3@example.com")
    token = create_access_token(subject=str(user.id))

    oversized_bytes = b"%PDF-1.5 " + b"0" * (settings.MAX_PDF_SIZE_BYTES + 10)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        files = {"file": ("huge.pdf", oversized_bytes, "application/pdf")}
        response = await client.post(
            "/api/v1/resumes/upload",
            files=files,
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 413
    data = response.json()
    assert data["error"]["code"] == "PAYLOAD_TOO_LARGE"


@pytest.mark.asyncio
async def test_encrypted_pdf_rejected(mock_storage):
    user = mock_storage.add_user("candidate4@example.com")
    token = create_access_token(subject=str(user.id))

    encrypted_bytes = create_encrypted_pdf("Secret content")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        files = {"file": ("locked.pdf", encrypted_bytes, "application/pdf")}
        response = await client.post(
            "/api/v1/resumes/upload",
            files=files,
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 422
    data = response.json()
    assert data["error"]["code"] in ["UNPROCESSABLE_ENTITY", "VALIDATION_ERROR"]


@pytest.mark.asyncio
async def test_empty_pdf_rejected(mock_storage):
    user = mock_storage.add_user("candidate5@example.com")
    token = create_access_token(subject=str(user.id))

    # Single blank page without any text
    empty_bytes = create_in_memory_pdf([""])

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        files = {"file": ("blank.pdf", empty_bytes, "application/pdf")}
        response = await client.post(
            "/api/v1/resumes/upload",
            files=files,
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Tenant Ownership & Anti-IDOR Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_user_can_view_own_resume(mock_storage):
    user = mock_storage.add_user("owner@example.com")
    token = create_access_token(subject=str(user.id))

    pdf_bytes = create_in_memory_pdf(["Valid resume text for John Doe with Python"])
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        up = await client.post(
            "/api/v1/resumes/upload",
            files={"file": ("my_resume.pdf", pdf_bytes, "application/pdf")},
            headers={"Authorization": f"Bearer {token}"},
        )
        resume_id = up.json()["id"]

        detail = await client.get(
            f"/api/v1/resumes/{resume_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert detail.status_code == 200
    res_data = detail.json()
    assert res_data["id"] == resume_id
    assert res_data["original_filename"] == "my_resume.pdf"
    assert "skills_breakdown" in res_data


@pytest.mark.asyncio
async def test_user_cannot_view_another_users_resume(mock_storage):
    user1 = mock_storage.add_user("user1@example.com")
    user2 = mock_storage.add_user("user2@example.com")

    token1 = create_access_token(subject=str(user1.id))
    token2 = create_access_token(subject=str(user2.id))

    pdf_bytes = create_in_memory_pdf(["User 1 resume text"])
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # User 1 uploads
        up = await client.post(
            "/api/v1/resumes/upload",
            files={"file": ("user1_resume.pdf", pdf_bytes, "application/pdf")},
            headers={"Authorization": f"Bearer {token1}"},
        )
        resume_id = up.json()["id"]

        # User 2 tries to access User 1's resume
        forbidden_response = await client.get(
            f"/api/v1/resumes/{resume_id}",
            headers={"Authorization": f"Bearer {token2}"},
        )

    assert forbidden_response.status_code == 403
    data = forbidden_response.json()
    assert data["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_user_cannot_delete_another_users_resume(mock_storage):
    user1 = mock_storage.add_user("victim@example.com")
    user2 = mock_storage.add_user("attacker@example.com")

    token1 = create_access_token(subject=str(user1.id))
    token2 = create_access_token(subject=str(user2.id))

    pdf_bytes = create_in_memory_pdf(["Victim resume"])
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        up = await client.post(
            "/api/v1/resumes/upload",
            files={"file": ("victim_resume.pdf", pdf_bytes, "application/pdf")},
            headers={"Authorization": f"Bearer {token1}"},
        )
        resume_id = up.json()["id"]

        # Attacker tries to delete victim's resume
        del_resp = await client.delete(
            f"/api/v1/resumes/{resume_id}",
            headers={"Authorization": f"Bearer {token2}"},
        )

    assert del_resp.status_code == 403
    assert uuid.UUID(resume_id) in mock_storage.resumes  # Still present


# ---------------------------------------------------------------------------
# CRUD Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_resumes_scoped_to_user(mock_storage):
    user1 = mock_storage.add_user("lister1@example.com")
    user2 = mock_storage.add_user("lister2@example.com")

    token1 = create_access_token(subject=str(user1.id))
    token2 = create_access_token(subject=str(user2.id))

    pdf_bytes1 = create_in_memory_pdf(["Lister 1 Doc"])
    pdf_bytes2 = create_in_memory_pdf(["Lister 2 Doc"])

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # User 1 uploads 2 resumes
        await client.post(
            "/api/v1/resumes/upload",
            files={"file": ("doc1.pdf", pdf_bytes1, "application/pdf")},
            headers={"Authorization": f"Bearer {token1}"},
        )
        await client.post(
            "/api/v1/resumes/upload",
            files={"file": ("doc2.pdf", pdf_bytes1, "application/pdf")},
            headers={"Authorization": f"Bearer {token1}"},
        )

        # User 2 uploads 1 resume
        await client.post(
            "/api/v1/resumes/upload",
            files={"file": ("doc3.pdf", pdf_bytes2, "application/pdf")},
            headers={"Authorization": f"Bearer {token2}"},
        )

        # List User 1 resumes
        list1 = await client.get("/api/v1/resumes/", headers={"Authorization": f"Bearer {token1}"})
        # List User 2 resumes
        list2 = await client.get("/api/v1/resumes/", headers={"Authorization": f"Bearer {token2}"})

    assert list1.status_code == 200
    assert len(list1.json()) == 2

    assert list2.status_code == 200
    assert len(list2.json()) == 1


@pytest.mark.asyncio
async def test_delete_resume_permanent_removal(mock_storage):
    user = mock_storage.add_user("deleter@example.com")
    token = create_access_token(subject=str(user.id))

    pdf_bytes = create_in_memory_pdf(["Document to be deleted"])

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        up = await client.post(
            "/api/v1/resumes/upload",
            files={"file": ("delete_me.pdf", pdf_bytes, "application/pdf")},
            headers={"Authorization": f"Bearer {token}"},
        )
        resume_id = up.json()["id"]

        del_resp = await client.delete(
            f"/api/v1/resumes/{resume_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert del_resp.status_code == 200
        assert "data" in del_resp.json()

        # Subsequent GET should return 404
        get_again = await client.get(
            f"/api/v1/resumes/{resume_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert get_again.status_code == 404
