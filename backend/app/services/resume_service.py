from datetime import UTC, datetime
import re
from typing import Any, Dict, List, Optional
import uuid
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.dependencies import verify_tenant_ownership
from app.models.resume import Resume
from app.models.user import User
from app.repositories.resume_repository import ResumeRepository
from app.services.embedding_service import embedding_service
from app.services.nlp_extractor import skill_extractor
from app.services.pdf_parser import (
    PDFCorruptedError,
    PDFEmptyTextError,
    PDFInvalidFormatError,
    PDFPageLimitExceededError,
    PDFParserError,
    PDFSizeLimitExceededError,
    extract_text_from_pdf,
)


def _extract_education_level(text: str) -> str:
    """Detects highest educational degree mentioned in the resume text."""
    lower = text.lower()
    if any(k in lower for k in ["ph.d", "phd", "doctorate", "doctor of philosophy"]):
        return "Doctorate"
    if any(k in lower for k in ["master", "master's", "m.s.", "m.tech", "mba", "msc"]):
        return "Master's"
    if any(k in lower for k in ["bachelor", "bachelor's", "b.s.", "b.tech", "b.e.", "bsc", "undergraduate"]):
        return "Bachelor's"
    if any(k in lower for k in ["associate", "associate's"]):
        return "Associate"
    if any(k in lower for k in ["high school", "secondary school", "diploma", "ged"]):
        return "High School"
    return "Unspecified"


def _extract_experience_years(text: str) -> float:
    """Extracts candidate years of experience heuristic from text."""
    matches = re.findall(
        r"(\d+(?:\.\d+)?)\+?\s*years?(?:\s+of)?(?:\s+(?:professional\s+)?experience)?",
        text,
        re.IGNORECASE,
    )
    if matches:
        try:
            years = [float(m) for m in matches if 0.0 <= float(m) <= 50.0]
            if years:
                return max(years)
        except ValueError:
            pass
    return 0.0


class ResumeService:
    """
    Coordinates PDF ingestion sandboxing, NLP skill extraction,
    neural vector embedding generation, and repository persistence.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.resume_repo = ResumeRepository(session)

    async def process_and_create_resume(
        self,
        user_id: uuid.UUID,
        filename: str,
        file_bytes: bytes,
    ) -> Resume:
        """
        Executes end-to-end resume ingestion:
        1. PyMuPDF Sandboxed Parsing & Magic Header Validation
        2. NLP Skill Extraction from Cleaned Text
        3. 384-dimensional Semantic Embedding Generation
        4. Persistence via ResumeRepository
        """
        # 1. PDF Parsing with Security Guards
        try:
            parse_result = extract_text_from_pdf(file_bytes)
        except PDFSizeLimitExceededError as exc:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File exceeds maximum allowed size limit: {str(exc)}",
            ) from exc
        except PDFPageLimitExceededError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Document exceeds maximum page limit: {str(exc)}",
            ) from exc
        except PDFEmptyTextError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"PDF contains no extractable text: {str(exc)}",
            ) from exc
        except PDFCorruptedError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"PDF is corrupted or password-protected: {str(exc)}",
            ) from exc
        except (PDFInvalidFormatError, PDFParserError) as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid PDF file format: {str(exc)}",
            ) from exc

        # 2. NLP Extraction
        skill_res = skill_extractor.extract_skills(parse_result.cleaned_text)
        exp_years = _extract_experience_years(parse_result.cleaned_text)
        edu_level = _extract_education_level(parse_result.cleaned_text)

        skills_breakdown = {
            "extracted_skills": skill_res.canonical_skills,
            "by_category": skill_res.by_category,
            "total_skills": skill_res.total_unique_skills,
            "total_mentions": skill_res.total_mentions,
        }
        experience_breakdown = {
            "detected_years": exp_years,
            "has_experience_stated": exp_years > 0.0,
        }
        education_breakdown = {
            "detected_level": edu_level,
        }
        explanation = {
            "summary": (
                f"Successfully parsed resume '{filename}' with {parse_result.total_pages} page(s), "
                f"{skill_res.total_unique_skills} canonical skill(s) identified, and "
                f"{exp_years} reported year(s) of experience."
            ),
            "char_count": parse_result.char_count,
            "word_count": parse_result.word_count,
            "total_pages": parse_result.total_pages,
        }

        # 3. Dense Vector Embedding Generation
        embedding_vector = embedding_service.generate_embedding(parse_result.cleaned_text)

        # 4. Persistence via ResumeRepository
        structured_data: Dict[str, Any] = {
            "skills": skill_res.canonical_skills,
            "experience_years": exp_years,
            "education_level": edu_level,
            "skills_breakdown": skills_breakdown,
            "experience_breakdown": experience_breakdown,
            "education_breakdown": education_breakdown,
            "explanation": explanation,
        }

        resume_record = Resume(
            user_id=user_id,
            original_filename=filename,
            file_size_bytes=len(file_bytes),
            parsed_text=parse_result.cleaned_text,
            structured_data=structured_data,
            embedding=embedding_vector,
        )

        persisted = await self.resume_repo.create(resume_record)
        return persisted

    async def get_user_resumes(
        self,
        user_id: uuid.UUID,
        skip: int = 0,
        limit: int = 50,
    ) -> List[Resume]:
        """Returns all resumes belonging to the specified user."""
        return await self.resume_repo.get_by_user_id(user_id=user_id, skip=skip, limit=limit)

    async def get_resume_by_id(
        self,
        resume_id: uuid.UUID,
        current_user: User,
    ) -> Resume:
        """
        Retrieves a resume by ID, strictly enforcing tenant isolation.
        """
        resume = await self.resume_repo.get_by_id(resume_id)
        if resume is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Resume '{resume_id}' not found.",
            )
        verify_tenant_ownership(resume.user_id, current_user)
        return resume

    async def delete_resume_by_id(
        self,
        resume_id: uuid.UUID,
        current_user: User,
    ) -> None:
        """
        Hard-deletes a resume by ID with tenant ownership verification.
        Cascade rules expunge all associated matches and vectors.
        """
        resume = await self.resume_repo.get_by_id(resume_id)
        if resume is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Resume '{resume_id}' not found.",
            )
        verify_tenant_ownership(resume.user_id, current_user)
        await self.resume_repo.delete(resume)
