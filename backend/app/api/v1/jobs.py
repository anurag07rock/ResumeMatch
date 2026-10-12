from typing import List, Optional
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.dependencies import get_current_user
from app.core.limiter import limiter
from app.db.session import get_db
from app.models.user import User
from app.schemas.common import SuccessResponse
from app.schemas.job import (
    JobCreateRequest,
    JobResponse,
)
from app.services.job_service import JobService

router = APIRouter(prefix="/jobs", tags=["Jobs"])


@router.post(
    "/analyze",
    response_model=JobResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Analyze and store job description",
    description="Ingests a job description, extracts required and preferred technical skills, determines minimum experience and education requirements, generates 384-d embeddings, and persists the record.",
)
@limiter.limit(lambda: settings.AI_RATE_LIMIT)
async def analyze_job(
    request: Request,
    payload: JobCreateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> JobResponse:
    """
    Ingests and parses job description text:
    - Extracts required & preferred canonical skills
    - Determines experience duration and credential thresholds
    - Generates 384-dimensional dense semantic vector
    - Persists linked to current user
    """
    service = JobService(session)
    job = await service.process_and_create_job(
        user_id=current_user.id,
        title=payload.title,
        raw_text=payload.raw_text or payload.description or "",
        company=payload.company,
    )
    return JobResponse.model_validate(job)



@router.get(
    "/",
    response_model=List[JobResponse],
    status_code=status.HTTP_200_OK,
    summary="List user jobs",
    description="Retrieves jobs created by the authenticated user with pagination.",
)
@router.get(
    "",
    response_model=List[JobResponse],
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
async def list_jobs(
    skip: int = Query(0, ge=0, description="Offset count"),
    limit: int = Query(50, ge=1, le=100, description="Max return count"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> List[JobResponse]:
    """
    Returns jobs belonging to the authenticated tenant.
    """
    service = JobService(session)
    jobs = await service.get_user_jobs(
        user_id=current_user.id,
        skip=skip,
        limit=limit,
    )
    return [JobResponse.model_validate(j) for j in jobs]


@router.get(
    "/{job_id}",
    response_model=JobResponse,
    status_code=status.HTTP_200_OK,
    summary="Get job details",
    description="Fetches full details of a specific job record.",
)
async def get_job_detail(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> JobResponse:
    """
    Retrieves full details of a single job description.
    """
    service = JobService(session)
    job = await service.get_job_by_id(job_id=job_id, current_user=current_user)
    return JobResponse.model_validate(job)


@router.delete(
    "/{job_id}",
    response_model=SuccessResponse[dict],
    status_code=status.HTTP_200_OK,
    summary="Delete job description",
    description="Permanently deletes a job record with ownership verification.",
)
async def delete_job(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> SuccessResponse[dict]:
    """
    Deletes a job description record.
    """
    service = JobService(session)
    await service.delete_job_by_id(job_id=job_id, current_user=current_user)
    return SuccessResponse(data={"message": f"Job '{job_id}' permanently deleted."})
