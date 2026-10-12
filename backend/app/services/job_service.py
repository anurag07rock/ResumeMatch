from datetime import UTC, datetime
import re
from typing import Any, Dict, List, Optional
import uuid
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.dependencies import verify_tenant_ownership
from app.models.job import Job
from app.models.user import User
from app.repositories.job_repository import JobRepository
from app.services.embedding_service import embedding_service
from app.services.nlp_extractor import skill_extractor


def _extract_minimum_education_level(text: str) -> str:
    """Detects minimum required degree level in a job description."""
    lower = text.lower()
    if any(k in lower for k in ["ph.d", "phd", "doctorate", "doctor of philosophy"]):
        return "Doctorate"
    if any(k in lower for k in ["master's", "masters", "master", "m.s.", "m.tech", "mba", "msc"]):
        return "Master's"
    if any(k in lower for k in ["bachelor's", "bachelors", "bachelor", "b.s.", "b.tech", "b.e.", "bsc", "undergraduate degree"]):
        return "Bachelor's"
    if any(k in lower for k in ["associate", "associate's"]):
        return "Associate"
    if any(k in lower for k in ["high school", "secondary school", "diploma", "ged"]):
        return "High School"
    return "Unspecified"


def _extract_minimum_experience_years(text: str) -> float:
    """Extracts minimum required years of experience from job text."""
    matches = re.findall(
        r"(?:(?:at\s+least|minimum|min\.?|requires?|with)\s+)?(\d+(?:\.\d+)?)\+?\s*years?(?:\s+of)?(?:\s+(?:relevant|work|professional)?\s*experience)?",
        text,
        re.IGNORECASE,
    )
    if matches:
        try:
            years = [float(m) for m in matches if 0.0 <= float(m) <= 50.0]
            if years:
                return min(years) if len(years) > 1 and "minimum" in text.lower() else max(years)
        except ValueError:
            pass
    return 0.0


class JobService:
    """
    Coordinates Job Description ingestion, NLP requirement parsing,
    neural vector embedding generation, and repository persistence.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.job_repo = JobRepository(session)

    async def process_and_create_job(
        self,
        user_id: Optional[uuid.UUID],
        title: str,
        raw_text: str,
        company: Optional[str] = None,
    ) -> Job:
        """
        Executes end-to-end job description analysis pipeline:
        1. Input validation
        2. NLP requirement extraction (required vs preferred skills)
        3. Experience & education requirement analysis
        4. 384-dimensional dense vector embedding generation
        5. Persistence via JobRepository
        """
        cleaned_title = title.strip()
        cleaned_text = raw_text.strip()

        if not cleaned_title:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Job title cannot be empty.",
            )

        if len(cleaned_text) < 10:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Job description text must contain at least 10 characters.",
            )

        # 1. NLP Requirement Extraction
        job_skill_res = skill_extractor.extract_skills_from_job(cleaned_text)
        min_exp_years = _extract_minimum_experience_years(cleaned_text)
        min_edu_level = _extract_minimum_education_level(cleaned_text)

        # 2. Canonical Breakdowns
        skills_breakdown = {
            "required_skills": job_skill_res.required_skills,
            "preferred_skills": job_skill_res.preferred_skills,
            "total_required": len(job_skill_res.required_skills),
            "total_preferred": len(job_skill_res.preferred_skills),
            "all_canonical_skills": job_skill_res.all_skills.canonical_skills,
            "by_category": job_skill_res.all_skills.by_category,
        }
        experience_breakdown = {
            "minimum_years": min_exp_years,
            "has_minimum_requirement": min_exp_years > 0.0,
        }
        education_breakdown = {
            "minimum_level": min_edu_level,
        }
        explanation = {
            "summary": (
                f"Analyzed job description for '{cleaned_title}'. "
                f"Extracted {len(job_skill_res.required_skills)} required skill(s), "
                f"{len(job_skill_res.preferred_skills)} preferred skill(s), "
                f"{min_exp_years} minimum year(s) of experience, and "
                f"'{min_edu_level}' education credential requirement."
            ),
            "required_skills_count": len(job_skill_res.required_skills),
            "preferred_skills_count": len(job_skill_res.preferred_skills),
        }
        structured_requirements = {
            "required_skills": job_skill_res.required_skills,
            "preferred_skills": job_skill_res.preferred_skills,
            "minimum_experience_years": min_exp_years,
            "minimum_education_level": min_edu_level,
        }

        # 3. Dense Vector Embedding Generation
        embedding_vector = embedding_service.generate_embedding(cleaned_text)

        # 4. Persistence
        structured_data: Dict[str, Any] = {
            "required_skills": job_skill_res.required_skills,
            "preferred_skills": job_skill_res.preferred_skills,
            "minimum_experience_years": min_exp_years,
            "minimum_education_level": min_edu_level,
            "structured_requirements": structured_requirements,
            "skills_breakdown": skills_breakdown,
            "experience_breakdown": experience_breakdown,
            "education_breakdown": education_breakdown,
            "explanation": explanation,
        }

        job = Job(
            user_id=user_id,
            title=cleaned_title,
            company=company.strip() if company else None,
            raw_text=cleaned_text,
            structured_data=structured_data,
            embedding=embedding_vector,
        )

        persisted = await self.job_repo.create(job)
        return persisted

    async def get_user_jobs(
        self,
        user_id: uuid.UUID,
        skip: int = 0,
        limit: int = 50,
    ) -> List[Job]:
        """Returns jobs belonging to the authenticated user."""
        return await self.job_repo.get_by_user_id(user_id=user_id, skip=skip, limit=limit)

    async def get_job_by_id(
        self,
        job_id: uuid.UUID,
        current_user: Optional[User] = None,
    ) -> Job:
        """
        Retrieves a job by ID. If user is provided and job is private to a tenant,
        verifies ownership.
        """
        job = await self.job_repo.get_by_id(job_id)
        if job is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job '{job_id}' not found.",
            )
        if current_user is not None and job.user_id is not None:
            verify_tenant_ownership(job.user_id, current_user)
        return job

    async def delete_job_by_id(
        self,
        job_id: uuid.UUID,
        current_user: User,
    ) -> None:
        """
        Hard-deletes a job with tenant ownership verification.
        """
        job = await self.job_repo.get_by_id(job_id)
        if job is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job '{job_id}' not found.",
            )
        if job.user_id is not None:
            verify_tenant_ownership(job.user_id, current_user)
        await self.job_repo.delete(job)
