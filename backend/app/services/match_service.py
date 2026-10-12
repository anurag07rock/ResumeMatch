from typing import Any, Dict, List, Optional
import uuid
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.dependencies import verify_tenant_ownership
from app.models.match import Match
from app.models.user import User
from app.repositories.job_repository import JobRepository
from app.repositories.match_repository import MatchRepository
from app.repositories.resume_repository import ResumeRepository
from app.schemas.match import MatchResponse
from app.services.job_service import JobService
from app.services.scoring_engine import scoring_engine


class MatchService:
    """
    Coordinates candidate resume and job matching:
    - Enforces tenant isolation for both resumes and jobs
    - Supports saved job matching and on-the-fly job ingestion
    - Executes deterministic neural and heuristic scoring via ScoringEngine
    - Persists match audit trails through MatchRepository
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.match_repo = MatchRepository(session)
        self.resume_repo = ResumeRepository(session)
        self.job_repo = JobRepository(session)

    async def create_match(
        self,
        current_user: User,
        resume_id: uuid.UUID,
        job_id: Optional[uuid.UUID] = None,
        job_text: Optional[str] = None,
        job_title: Optional[str] = None,
        save_result: bool = True,
    ) -> MatchResponse:
        """
        Executes hybrid match scoring between a user's resume and a job description.
        Validates ownership and prevents cross-tenant access.
        """
        # 1. Validate Resume and Ownership
        resume = await self.resume_repo.get_by_id(resume_id)
        if resume is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Resume '{resume_id}' not found.",
            )
        verify_tenant_ownership(resume.user_id, current_user)

        # 2. Resolve Job (Existing or On-The-Fly)
        if job_id is not None:
            job = await self.job_repo.get_by_id(job_id)
            if job is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Job '{job_id}' not found.",
                )
            if job.user_id is not None:
                verify_tenant_ownership(job.user_id, current_user)
        elif job_text and len(job_text.strip()) >= 10:
            job_svc = JobService(self.session)
            job = await job_svc.process_and_create_job(
                user_id=current_user.id,
                title=job_title or "Target Job Opportunity",
                raw_text=job_text,
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Either 'job_id' or 'job_text' (at least 10 characters) must be provided for matching.",
            )

        # 3. Extract Candidate and Job Features
        resume_sd = resume.structured_data or {}
        candidate_skills = resume_sd.get("skills", [])
        candidate_years = resume_sd.get("experience_years", 0.0)
        candidate_education = resume_sd.get("education_level", "Unspecified")
        resume_vector = resume.embedding

        job_sd = job.structured_data or {}
        required_skills = job_sd.get("required_skills", [])
        preferred_skills = job_sd.get("preferred_skills", [])
        required_years = job_sd.get("minimum_experience_years", 0.0)
        required_education = job_sd.get("minimum_education_level", "Unspecified")
        job_vector = job.embedding

        # 4. Execute Scoring Engine
        match_result = scoring_engine.compute_match(
            candidate_skills=candidate_skills,
            required_skills=required_skills,
            preferred_skills=preferred_skills,
            candidate_years=candidate_years,
            required_years=required_years,
            candidate_education=candidate_education,
            required_education=required_education,
            resume_vector=resume_vector,
            job_vector=job_vector,
        )

        # 5. Persistence
        if save_result:
            db_payload = match_result.to_db_record()
            match_record = Match(
                user_id=current_user.id,
                resume_id=resume.id,
                job_id=job.id,
                overall_score=db_payload["overall_score"],
                semantic_score=db_payload["semantic_score"],
                skills_score=db_payload["skills_score"],
                experience_score=db_payload["experience_score"],
                education_score=db_payload["education_score"],
                breakdown=db_payload["breakdown"],
                explanation=db_payload["explanation"],
            )
            persisted = await self.match_repo.create(match_record)
            return MatchResponse.model_validate(persisted)

        # Non-persisted transient evaluation
        transient_dict = match_result.to_db_record()
        transient_dict["match_id"] = None
        transient_dict["fit_category"] = match_result.fit_category
        transient_dict["skills_breakdown"] = match_result.skills_breakdown.model_dump()
        transient_dict["experience_breakdown"] = match_result.experience_breakdown.model_dump()
        transient_dict["education_breakdown"] = match_result.education_breakdown.model_dump()
        transient_dict["score_weights"] = match_result.score_weights.model_dump()
        transient_dict["sub_scores"] = match_result.sub_scores.model_dump()
        return MatchResponse.model_validate(transient_dict)

    async def get_user_matches(
        self,
        user_id: uuid.UUID,
        skip: int = 0,
        limit: int = 50,
    ) -> List[Match]:
        """Returns match evaluations scoped to the authenticated user."""
        return await self.match_repo.get_by_user_id(user_id=user_id, skip=skip, limit=limit)

    async def get_match_by_id(
        self,
        match_id: uuid.UUID,
        current_user: User,
    ) -> Match:
        """Retrieves a single match evaluation with tenant ownership verification."""
        match = await self.match_repo.get_by_id(match_id)
        if match is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Match evaluation '{match_id}' not found.",
            )
        verify_tenant_ownership(match.user_id, current_user)
        return match

    async def delete_match(
        self,
        match_id: uuid.UUID,
        current_user: User,
    ) -> None:
        """Deletes a match evaluation record with ownership verification."""
        match = await self.match_repo.get_by_id(match_id)
        if match is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Match evaluation '{match_id}' not found.",
            )
        verify_tenant_ownership(match.user_id, current_user)
        await self.match_repo.delete(match)
