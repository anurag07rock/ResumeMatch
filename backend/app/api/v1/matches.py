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
from app.schemas.match import (
    MatchRequest,
    MatchResponse,
)
from app.services.match_service import MatchService

router = APIRouter(prefix="/match", tags=["Matching"])


@router.post(
    "",
    response_model=MatchResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute hybrid matching",
    description="Executes calibrated hybrid scoring between a resume and job description (by job ID or inline text).",
)
@router.post(
    "/",
    response_model=MatchResponse,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
@limiter.limit(lambda: settings.AI_RATE_LIMIT)
async def execute_match(
    request: Request,
    payload: MatchRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> MatchResponse:
    """
    Executes hybrid matching:
    - Semantic dense vector cosine similarity (mapped [0, 100])
    - Technical skills recall (required and preferred)
    - Experience alignment with non-linear penalty curves
    - Education credential step ranking
    - Evidence-based explanation and gap diagnostics
    """
    service = MatchService(session)
    return await service.create_match(
        current_user=current_user,
        resume_id=payload.resume_id,
        job_id=payload.job_id,
        job_text=payload.job_text,
        job_title=payload.job_title,
        save_result=payload.save_result,
    )


@router.get(
    "/history",
    response_model=List[MatchResponse],
    status_code=status.HTTP_200_OK,
    summary="Get user match history",
    description="Returns chronological match evaluations conducted by the authenticated user.",
)
async def get_match_history(
    skip: int = Query(0, ge=0, description="Offset count"),
    limit: int = Query(50, ge=1, le=100, description="Page limit"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> List[MatchResponse]:
    """
    Returns match history records scoped strictly to the current user.
    """
    service = MatchService(session)
    matches = await service.get_user_matches(
        user_id=current_user.id,
        skip=skip,
        limit=limit,
    )
    return [MatchResponse.model_validate(m) for m in matches]


@router.get(
    "/{match_id}",
    response_model=MatchResponse,
    status_code=status.HTTP_200_OK,
    summary="Get match evaluation details",
    description="Fetches the explainable diagnostics and breakdown of a specific match evaluation.",
)
async def get_match_detail(
    match_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> MatchResponse:
    """
    Retrieves full diagnostics of a single match run with anti-IDOR enforcement.
    """
    service = MatchService(session)
    match = await service.get_match_by_id(match_id=match_id, current_user=current_user)
    return MatchResponse.model_validate(match)


@router.delete(
    "/{match_id}",
    response_model=SuccessResponse[dict],
    status_code=status.HTTP_200_OK,
    summary="Delete match evaluation",
    description="Permanently deletes a match record.",
)
async def delete_match(
    match_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> SuccessResponse[dict]:
    """
    Deletes a historical match record.
    """
    service = MatchService(session)
    await service.delete_match(match_id=match_id, current_user=current_user)
    return SuccessResponse(data={"message": f"Match '{match_id}' permanently deleted."})
