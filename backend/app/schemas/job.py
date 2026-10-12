from datetime import UTC, datetime
import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator


class JobCreateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, populate_by_name=True)

    title: str = Field(..., min_length=1, max_length=255, description="Job title / position name")
    company: Optional[str] = Field(default=None, max_length=255, description="Company or hiring organization")
    raw_text: Optional[str] = Field(default=None, description="Full job description text to parse and index")
    description: Optional[str] = Field(default=None, description="Job description text (alias for raw_text)")

    @model_validator(mode="before")
    @classmethod
    def sync_text_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if not data.get("raw_text") and data.get("description"):
                data["raw_text"] = data["description"]
            elif not data.get("description") and data.get("raw_text"):
                data["description"] = data["raw_text"]
        return data

    @model_validator(mode="after")
    def validate_content_presence(self) -> "JobCreateRequest":
        text = self.raw_text or self.description
        if not text or len(text.strip()) < 10:
            raise ValueError("Job description text ('raw_text' or 'description') must be at least 10 characters long.")
        if not self.raw_text:
            self.raw_text = text.strip()
        return self


class StructuredRequirements(BaseModel):
    model_config = ConfigDict(extra="allow")

    required_skills: List[str] = Field(default_factory=list)
    preferred_skills: List[str] = Field(default_factory=list)
    minimum_experience_years: Optional[float] = None
    minimum_education_level: Optional[str] = None


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore")

    id: uuid.UUID = Field(..., description="Unique job identifier")
    user_id: Optional[uuid.UUID] = Field(default=None, description="Creator/owner user UUID")
    title: str = Field(..., description="Job title")
    company: Optional[str] = Field(default=None, description="Company name")
    raw_text: Optional[str] = Field(default=None, description="Raw job description text")
    structured_data: Dict[str, Any] = Field(default_factory=dict, description="Parsed structured requirements JSONB")
    structured_requirements: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Normalized requirements for matching"
    )

    # Canonical diagnostic and explainability breakdown fields
    skills_breakdown: Dict[str, Any] = Field(
        default_factory=dict,
        description="Canonical skills breakdown and required/preferred ontology extractions"
    )
    experience_breakdown: Dict[str, Any] = Field(
        default_factory=dict,
        description="Canonical experience breakdown and minimum duration requirements"
    )
    education_breakdown: Dict[str, Any] = Field(
        default_factory=dict,
        description="Canonical education breakdown and degree level requirements"
    )
    explanation: Dict[str, Any] = Field(
        default_factory=dict,
        description="Canonical explainable summary and requirement extraction rationale"
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), description="Creation timestamp")

    @model_validator(mode="before")
    @classmethod
    def extract_canonical_breakdowns(cls, data: Any) -> Any:
        if hasattr(data, "structured_data") and isinstance(data.structured_data, dict):
            sd = data.structured_data
            return {
                "id": getattr(data, "id", None),
                "user_id": getattr(data, "user_id", None),
                "title": getattr(data, "title", ""),
                "company": getattr(data, "company", None),
                "raw_text": getattr(data, "raw_text", ""),
                "structured_data": sd,
                "structured_requirements": sd.get("structured_requirements") or getattr(data, "structured_requirements", None),
                "skills_breakdown": sd.get("skills_breakdown", {}),
                "experience_breakdown": sd.get("experience_breakdown", {}),
                "education_breakdown": sd.get("education_breakdown", {}),
                "explanation": sd.get("explanation", {}),
                "created_at": getattr(data, "created_at", None),
            }
        elif isinstance(data, dict):
            sd = data.get("structured_data", {})
            if isinstance(sd, dict):
                for k in ["skills_breakdown", "experience_breakdown", "education_breakdown", "explanation", "structured_requirements"]:
                    if not data.get(k) and k in sd:
                        data[k] = sd[k]
        return data
