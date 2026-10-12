from typing import List, Optional
import uuid
from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.dependencies import get_current_user
from app.core.limiter import limiter
from app.db.session import get_db
from app.models.user import User
from app.schemas.common import SuccessResponse
from app.schemas.resume import (
    ResumeResponse,
    ResumeUploadResponse,
)
from app.services.resume_service import ResumeService

router = APIRouter(prefix="/resumes", tags=["Resumes"])


@router.post(
    "/upload",
    response_model=ResumeUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and process resume PDF",
    description="Uploads a PDF resume, executes sandboxed PyMuPDF extraction, NLP skill parsing, dense embeddings, and persistence.",
)
@limiter.limit(lambda: settings.AI_RATE_LIMIT)
async def upload_resume(
    request: Request,
    file: UploadFile = File(..., description="Resume PDF file (max 5 MB)"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ResumeUploadResponse:
    """
    Protected resume upload endpoint:
    - Enforces Bearer JWT authentication
    - Validates file presence and content type
    - Sandboxes PyMuPDF text extraction
    - Executes NLP skill extraction and generates 384-d embeddings
    - Persists parsed record linked to current user
    """
    if not file or not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No file was uploaded.",
        )

    # Basic filename validation
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files (.pdf) are supported.",
        )

    # Stream read with size boundary
    file_bytes = await file.read()
    if not file_bytes or len(file_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty (0 bytes).",
        )

    if len(file_bytes) > settings.MAX_PDF_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum allowed limit of {settings.MAX_PDF_SIZE_BYTES} bytes.",
        )

    service = ResumeService(session)
    resume = await service.process_and_create_resume(
        user_id=current_user.id,
        filename=file.filename,
        file_bytes=file_bytes,
    )

    sd = resume.structured_data or {}
    return ResumeUploadResponse(
        id=resume.id,
        original_filename=resume.original_filename,
        file_size_bytes=resume.file_size_bytes,
        parsed_data=sd,
        skills_breakdown=sd.get("skills_breakdown", {}),
        experience_breakdown=sd.get("experience_breakdown", {}),
        education_breakdown=sd.get("education_breakdown", {}),
        explanation=sd.get("explanation", {}),
        created_at=resume.created_at,
    )


@router.get(
    "/",
    response_model=List[ResumeResponse],
    status_code=status.HTTP_200_OK,
    summary="List authenticated user resumes",
    description="Retrieves all resumes uploaded by the current user with pagination.",
)
@router.get(
    "",
    response_model=List[ResumeResponse],
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
async def list_resumes(
    skip: int = Query(0, ge=0, description="Offset record count"),
    limit: int = Query(50, ge=1, le=100, description="Page limit"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> List[ResumeResponse]:
    """
    Retrieves candidate resumes strictly scoped to the authenticated tenant.
    """
    service = ResumeService(session)
    resumes = await service.get_user_resumes(
        user_id=current_user.id,
        skip=skip,
        limit=limit,
    )
    return [ResumeResponse.model_validate(r) for r in resumes]


@router.get(
    "/{resume_id}",
    response_model=ResumeResponse,
    status_code=status.HTTP_200_OK,
    summary="Get resume details",
    description="Fetches full details of a specific resume, enforcing tenant ownership.",
)
async def get_resume_detail(
    resume_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ResumeResponse:
    """
    Retrieves full details of a single resume record with anti-IDOR enforcement.
    """
    service = ResumeService(session)
    resume = await service.get_resume_by_id(resume_id, current_user)
    return ResumeResponse.model_validate(resume)


@router.delete(
    "/{resume_id}",
    response_model=SuccessResponse[dict],
    status_code=status.HTTP_200_OK,
    summary="Delete resume",
    description="Hard-deletes a resume, its parsed text, embeddings, and associated match records.",
)
async def delete_resume(
    resume_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> SuccessResponse[dict]:
    """
    Permanently deletes a resume record complying with GDPR Right to Be Forgotten.
    """
    service = ResumeService(session)
    await service.delete_resume_by_id(resume_id, current_user)
    return SuccessResponse(data={"message": f"Resume '{resume_id}' permanently deleted."})
