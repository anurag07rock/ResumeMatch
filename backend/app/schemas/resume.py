from datetime import UTC, datetime
import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator


class ResumeUploadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore")

    id: uuid.UUID = Field(..., description="Unique resume identifier")
    original_filename: str = Field(..., description="Original name of the uploaded PDF file")
    file_size_bytes: int = Field(..., description="Size of uploaded file in bytes")
    parsed_data: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Parsed entity payload")
    
    # Canonical diagnostic and explainability breakdown fields
    skills_breakdown: Dict[str, Any] = Field(
        default_factory=dict,
        description="Canonical skills breakdown and ontology extractions"
    )
    experience_breakdown: Dict[str, Any] = Field(
        default_factory=dict,
        description="Canonical experience breakdown and duration calculations"
    )
    education_breakdown: Dict[str, Any] = Field(
        default_factory=dict,
        description="Canonical education breakdown and credential analysis"
    )
    explanation: Dict[str, Any] = Field(
        default_factory=dict,
        description="Canonical explainable summary and entity parsing rationale"
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ResumeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore")

    id: uuid.UUID = Field(..., description="Unique resume identifier")
    user_id: Optional[uuid.UUID] = Field(default=None, description="Owner user UUID")
    original_filename: str = Field(..., description="Original name of the uploaded PDF file")
    file_size_bytes: int = Field(..., description="Size of file in bytes")
    parsed_text: Optional[str] = Field(default=None, description="Cleaned extracted plain text")
    structured_data: Dict[str, Any] = Field(default_factory=dict, description="Structured parsed JSONB payload")

    # Canonical diagnostic and explainability breakdown fields
    skills_breakdown: Dict[str, Any] = Field(
        default_factory=dict,
        description="Canonical skills breakdown and entity extractions"
    )
    experience_breakdown: Dict[str, Any] = Field(
        default_factory=dict,
        description="Canonical experience breakdown and duration metrics"
    )
    education_breakdown: Dict[str, Any] = Field(
        default_factory=dict,
        description="Canonical education breakdown and degree levels"
    )
    explanation: Dict[str, Any] = Field(
        default_factory=dict,
        description="Canonical explainability notes for the resume"
    )
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: Optional[datetime] = Field(default=None, description="Last update timestamp")

    @model_validator(mode="before")

    @classmethod
    def extract_breakdowns_from_model(cls, data: Any) -> Any:
        if hasattr(data, "structured_data") and isinstance(data.structured_data, dict):
            sd = data.structured_data
            return {
                "id": getattr(data, "id", None),
                "user_id": getattr(data, "user_id", None),
                "original_filename": getattr(data, "original_filename", ""),
                "file_size_bytes": getattr(data, "file_size_bytes", 0),
                "parsed_text": getattr(data, "parsed_text", ""),
                "structured_data": sd,
                "skills_breakdown": sd.get("skills_breakdown", {}),
                "experience_breakdown": sd.get("experience_breakdown", {}),
                "education_breakdown": sd.get("education_breakdown", {}),
                "explanation": sd.get("explanation", {}),
                "created_at": getattr(data, "created_at", None),
                "updated_at": getattr(data, "updated_at", None),
            }
        elif isinstance(data, dict):
            sd = data.get("structured_data", {})
            if isinstance(sd, dict):
                for k in ["skills_breakdown", "experience_breakdown", "education_breakdown", "explanation"]:
                    if not data.get(k) and k in sd:
                        data[k] = sd[k]
        return data



class ResumeListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore")

    id: uuid.UUID = Field(..., description="Unique resume identifier")
    original_filename: str = Field(..., description="Original filename")
    file_size_bytes: int = Field(..., description="File size in bytes")
    created_at: datetime = Field(..., description="Upload timestamp")
