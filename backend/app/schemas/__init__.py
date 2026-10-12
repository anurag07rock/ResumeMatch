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
    StructuredRequirements,
)
from app.schemas.match import (
    MatchListItem,
    MatchRequest,
    MatchResponse,
)
from app.schemas.resume import (
    ResumeListItem,
    ResumeResponse,
    ResumeUploadResponse,
)

__all__ = [
    # Auth
    "UserRegisterRequest",
    "UserLoginRequest",
    "TokenResponse",
    "UserResponse",
    # Common Envelopes
    "ErrorDetail",
    "ErrorResponse",
    "ErrorEnvelope",
    "SuccessResponse",
    "ResponseEnvelope",
    # Resume
    "ResumeUploadResponse",
    "ResumeResponse",
    "ResumeListItem",
    # Job
    "JobCreateRequest",
    "JobResponse",
    "StructuredRequirements",
    # Match
    "MatchRequest",
    "MatchResponse",
    "MatchListItem",
]
