import logging
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.router import api_router
from app.core.config import settings
from app.core.limiter import limiter
from app.core.security import SecurityError
from app.db.session import get_db
from app.services.embedding_service import EmbeddingServiceError
from app.services.pdf_parser import (
    PDFCorruptedError,
    PDFEmptyTextError,
    PDFInvalidFormatError,
    PDFPageLimitExceededError,
    PDFParserError,
    PDFSizeLimitExceededError,
)
from app.services.scoring_engine import ScoringEngineError

logger = logging.getLogger("resumematch.api")

HTTP_STATUS_CODE_MAP = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    409: "CONFLICT",
    413: "PAYLOAD_TOO_LARGE",
    422: "VALIDATION_ERROR",
    429: "RATE_LIMIT_EXCEEDED",
    500: "INTERNAL_SERVER_ERROR",
    503: "SERVICE_UNAVAILABLE",
}


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    environment: str


class DatabaseHealthResponse(BaseModel):
    status: str
    database: str
    details: str


from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="ResumeMatch API",
    description="Explainable AI-Powered Resume-to-Job Matching Platform",
    version="0.1.0",
)

# CORS configuration adhering to settings.BACKEND_CORS_ORIGINS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Attach SlowAPI limiter state
app.state.limiter = limiter


# ---------------------------------------------------------------------------
# Global Exception Handlers (Canonical Error Envelope)
# ---------------------------------------------------------------------------

@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """
    Handles SlowAPI rate limit exceeded events with canonical error envelope.
    """
    detail_msg = f"Rate limit exceeded: {exc.detail}"
    logger.warning("Rate limit exceeded on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={
            "error": {
                "code": "RATE_LIMIT_EXCEEDED",
                "message": detail_msg,
                "details": {"limit": str(exc.detail)},
            },
            "detail": detail_msg,
        },
        headers={"Retry-After": "60"},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """
    Handles request schema validation failures with canonical error envelope.
    """
    errors = jsonable_encoder(exc.errors())
    logger.info("Request validation failed on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request validation failed.",
                "details": errors,
            },
            "detail": errors,
        },
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """
    Handles standard HTTP exceptions with canonical error envelope.
    """
    code = HTTP_STATUS_CODE_MAP.get(exc.status_code, "HTTP_ERROR")
    message = exc.detail if isinstance(exc.detail, str) else "An HTTP error occurred."
    details = exc.detail if isinstance(exc.detail, (dict, list)) else {}
    headers = getattr(exc, "headers", None)

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "details": details,
            },
            "detail": exc.detail,
        },
        headers=headers,
    )


@app.exception_handler(SecurityError)
async def security_exception_handler(request: Request, exc: SecurityError) -> JSONResponse:
    """
    Handles security core exceptions (e.g. token expired, invalid signature).
    """
    logger.warning("Security error on %s %s: %s", request.method, request.url.path, str(exc))
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={
            "error": {
                "code": "SECURITY_ERROR",
                "message": str(exc),
                "details": {},
            },
            "detail": str(exc),
        },
        headers={"WWW-Authenticate": "Bearer"},
    )


@app.exception_handler(IntegrityError)
async def integrity_exception_handler(request: Request, exc: IntegrityError) -> JSONResponse:
    """
    Handles database integrity violations without leaking internal schemas or SQL queries.
    """
    logger.error("Database integrity error on %s %s: %s", request.method, request.url.path, type(exc).__name__)
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={
            "error": {
                "code": "CONFLICT",
                "message": "A database integrity constraint was violated.",
                "details": {},
            },
            "detail": "A database integrity constraint was violated.",
        },
    )


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    """
    Handles database errors without leaking internal connection details or stack traces.
    """
    logger.error("Database error on %s %s: %s", request.method, request.url.path, type(exc).__name__)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "DATABASE_ERROR",
                "message": "A database error occurred while processing the request.",
                "details": {},
            },
            "detail": "A database error occurred while processing the request.",
        },
    )


@app.exception_handler(PDFParserError)
async def pdf_parser_exception_handler(request: Request, exc: PDFParserError) -> JSONResponse:
    """
    Handles PDF parsing security violations and file validation errors.
    """
    logger.warning("PDF parser error on %s %s: %s", request.method, request.url.path, str(exc))
    if isinstance(exc, PDFSizeLimitExceededError):
        code = "PAYLOAD_TOO_LARGE"
        status_code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    elif isinstance(exc, (PDFPageLimitExceededError, PDFCorruptedError, PDFEmptyTextError)):
        code = "UNPROCESSABLE_ENTITY"
        status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    else:
        code = "BAD_REQUEST"
        status_code = status.HTTP_400_BAD_REQUEST

    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": str(exc),
                "details": {},
            },
            "detail": str(exc),
        },
    )


@app.exception_handler(EmbeddingServiceError)
async def embedding_service_exception_handler(request: Request, exc: EmbeddingServiceError) -> JSONResponse:
    """
    Handles AI embedding model loading and inference errors gracefully.
    """
    logger.error("Embedding service error on %s %s: %s", request.method, request.url.path, str(exc))
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "error": {
                "code": "AI_SERVICE_UNAVAILABLE",
                "message": "The AI embedding service is currently unavailable.",
                "details": {},
            },
            "detail": "The AI embedding service is currently unavailable.",
        },
    )


@app.exception_handler(ScoringEngineError)
async def scoring_engine_exception_handler(request: Request, exc: ScoringEngineError) -> JSONResponse:
    """
    Handles scoring engine arithmetic and domain validation failures.
    """
    logger.error("Scoring engine calculation error on %s %s: %s", request.method, request.url.path, str(exc))
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "code": "SCORING_ERROR",
                "message": str(exc),
                "details": {},
            },
            "detail": str(exc),
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Handles unexpected internal exceptions ensuring zero stack traces or internal leaks.
    """
    logger.error("Unhandled internal exception on %s %s: %s", request.method, request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected server error occurred.",
                "details": {},
            },
            "detail": "An unexpected server error occurred.",
        },
    )


# ---------------------------------------------------------------------------
# Route Registrations
# ---------------------------------------------------------------------------

app.include_router(api_router, prefix=settings.API_V1_STR)


# ---------------------------------------------------------------------------
# Health Check Endpoints
# ---------------------------------------------------------------------------

@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check() -> HealthResponse:
    """
    Service health check endpoint indicating that the FastAPI backend is running.
    """
    return HealthResponse(
        status="healthy",
        service="resumematch-backend",
        version="0.1.0",
        environment=settings.ENVIRONMENT,
    )


@app.get("/health/db", response_model=DatabaseHealthResponse, tags=["Health"])
async def database_health_check(
    db: AsyncSession = Depends(get_db),
) -> DatabaseHealthResponse:
    """
    Database readiness check endpoint verifying active connectivity to the database.
    """
    try:
        result = await db.execute(text("SELECT 1"))
        val = result.scalar()
        if val == 1:
            return DatabaseHealthResponse(
                status="healthy",
                database="connected",
                details="Database connection verified successfully",
            )
        raise Exception("Unexpected query result from database")
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database connection unavailable: {str(exc)}",
        )
