from datetime import UTC, datetime
import uuid
import pytest
from pydantic import ValidationError
from app.schemas.auth import (
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)
from app.schemas.common import (
    ErrorDetail,
    ErrorEnvelope,
    ErrorResponse,
    ResponseEnvelope,
    SuccessResponse,
)
from app.schemas.job import (
    JobCreateRequest,
    JobResponse,
)
from app.schemas.match import (
    MatchRequest,
    MatchResponse,
)
from app.schemas.resume import (
    ResumeResponse,
    ResumeUploadResponse,
)


class TestAuthSchemas:
    """Tests Pydantic validation for authentication schemas."""

    def test_user_register_request_valid(self):
        req = UserRegisterRequest(
            email="candidate@example.com",
            password="StrongPassword123!",
            full_name="Jane Doe",
        )
        assert req.email == "candidate@example.com"
        assert req.full_name == "Jane Doe"

    def test_user_register_request_invalid_email(self):
        with pytest.raises(ValidationError):
            UserRegisterRequest(
                email="not-an-email",
                password="StrongPassword123!",
            )

    def test_user_register_request_password_too_short(self):
        with pytest.raises(ValidationError):
            UserRegisterRequest(
                email="candidate@example.com",
                password="short",
            )

    def test_user_login_request_valid(self):
        req = UserLoginRequest(
            email="candidate@example.com",
            password="StrongPassword123!",
        )
        assert req.email == "candidate@example.com"

    def test_token_response_serialization(self):
        token_resp = TokenResponse(
            access_token="acc.token.jwt",
            refresh_token="ref.token.jwt",
            token_type="bearer",
        )
        assert token_resp.access_token == "acc.token.jwt"
        assert token_resp.token_type == "bearer"

    def test_user_response_fields(self):
        uid = uuid.uuid4()
        now = datetime.now(UTC)
        user_resp = UserResponse(
            id=uid,
            email="user@example.com",
            created_at=now,
        )
        assert user_resp.id == uid
        assert user_resp.email == "user@example.com"
        assert user_resp.created_at == now


class TestCommonEnvelopes:
    """Tests API success and error envelope structures."""

    def test_error_envelope_structure(self):
        envelope = ErrorEnvelope(
            error=ErrorDetail(
                code="RESOURCE_NOT_FOUND",
                message="The requested resume was not found.",
                details={"resume_id": "123e4567-e89b-12d3-a456-426614174000"},
            )
        )
        data = envelope.model_dump()
        assert "error" in data
        assert data["error"]["code"] == "RESOURCE_NOT_FOUND"
        assert data["error"]["message"] == "The requested resume was not found."
        assert data["error"]["details"]["resume_id"] == "123e4567-e89b-12d3-a456-426614174000"

    def test_success_envelope_structure(self):
        resp = ResponseEnvelope(data={"key": "value"})
        dumped = resp.model_dump()
        assert "data" in dumped
        assert dumped["data"] == {"key": "value"}


class TestResumeSchemas:
    """Tests canonical field requirements for resume schemas."""

    def test_resume_upload_response_canonical_fields(self):
        resp = ResumeUploadResponse(
            id=uuid.uuid4(),
            original_filename="resume.pdf",
            file_size_bytes=1024,
            skills_breakdown={"matched": ["Python"]},
            experience_breakdown={"years": 5.0},
            education_breakdown={"level": "Bachelor's"},
            explanation={"summary": "Strong fit"},
        )
        dumped = resp.model_dump()
        # Verify strict canonical field presence
        assert "skills_breakdown" in dumped
        assert "experience_breakdown" in dumped
        assert "education_breakdown" in dumped
        assert "explanation" in dumped

    def test_resume_response_canonical_fields(self):
        uid = uuid.uuid4()
        resp = ResumeResponse(
            id=uid,
            original_filename="resume.pdf",
            file_size_bytes=1024,
            skills_breakdown={"Python": True},
            experience_breakdown={"years": 3.0},
            education_breakdown={"degree": "BS"},
            explanation={"notes": "Parsed successfully"},
            created_at=datetime.now(UTC),
        )
        dumped = resp.model_dump()
        assert "skills_breakdown" in dumped
        assert "experience_breakdown" in dumped
        assert "education_breakdown" in dumped
        assert "explanation" in dumped


class TestJobSchemas:
    """Tests Job creation and response schemas."""

    def test_job_create_request_valid(self):
        job_req = JobCreateRequest(
            title="Senior Backend Engineer",
            company="Tech Corp",
            raw_text="We need a Python and FastAPI expert with 5+ years experience.",
        )
        assert job_req.title == "Senior Backend Engineer"
        assert job_req.company == "Tech Corp"

    def test_job_create_request_requires_title_and_text(self):
        with pytest.raises(ValidationError):
            JobCreateRequest(
                title="",
                raw_text="short",
            )


class TestMatchSchemas:
    """Tests Match response schema, score preservation, and canonical field contracts."""

    def test_match_response_score_preservation(self):
        match_resp = MatchResponse(
            semantic_score=85.0,
            skill_score=90.0,
            experience_score=95.0,
            education_score=100.0,
            final_score=89.5,
            skills_breakdown={"matched_required": ["Python"]},
            experience_breakdown={"delta_years": 1.0},
            education_breakdown={"status": "FULLY_ALIGNED"},
            explanation={"summary": "Candidate is an excellent match."},
        )
        # Check preserved scores
        assert match_resp.semantic_score == 85.0
        assert match_resp.skill_score == 90.0
        assert match_resp.skills_score == 90.0
        assert match_resp.experience_score == 95.0
        assert match_resp.education_score == 100.0
        assert match_resp.final_score == 89.5
        assert match_resp.overall_score == 89.5

        # Check canonical breakdown fields
        dumped = match_resp.model_dump()
        assert "skills_breakdown" in dumped
        assert "experience_breakdown" in dumped
        assert "education_breakdown" in dumped
        assert "explanation" in dumped

    def test_match_response_sub_scores_dict_mapping(self):
        match_resp = MatchResponse(
            overall_score=82.0,
            sub_scores={
                "semantic_score": 80.0,
                "skills_score": 85.0,
                "experience_score": 75.0,
                "education_score": 90.0,
            },
            skills_breakdown={},
            experience_breakdown={},
            education_breakdown={},
            explanation={"summary": "Good match"},
        )
        assert match_resp.final_score == 82.0
        assert match_resp.skill_score == 85.0
        assert match_resp.semantic_score == 80.0

    def test_match_response_score_bounds(self):
        with pytest.raises(ValidationError):
            MatchResponse(
                semantic_score=105.0,  # exceeds 100.0
                skill_score=90.0,
                experience_score=95.0,
                education_score=100.0,
                final_score=89.5,
                skills_breakdown={},
                experience_breakdown={},
                education_breakdown={},
                explanation={},
            )
