from datetime import UTC, datetime
import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator


class MatchRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    resume_id: uuid.UUID = Field(..., description="UUID of the resume to evaluate")
    job_id: Optional[uuid.UUID] = Field(default=None, description="UUID of existing persisted job")
    job_text: Optional[str] = Field(default=None, min_length=10, description="Inline raw job text if matching on-the-fly")
    job_title: Optional[str] = Field(default=None, max_length=255, description="Inline job title if matching on-the-fly")
    save_result: bool = Field(default=True, description="Whether to persist match result to the database")


class MatchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore", populate_by_name=True)

    match_id: Optional[uuid.UUID] = Field(default=None, description="Unique match evaluation UUID")

    # Preserved score metrics
    semantic_score: float = Field(..., ge=0.0, le=100.0, description="Semantic similarity sub-score [0, 100]")
    skill_score: float = Field(..., ge=0.0, le=100.0, description="Skills alignment sub-score [0, 100]")
    skills_score: float = Field(..., ge=0.0, le=100.0, description="Canonical skills score alias")
    experience_score: float = Field(..., ge=0.0, le=100.0, description="Experience alignment sub-score [0, 100]")
    education_score: float = Field(..., ge=0.0, le=100.0, description="Education credential sub-score [0, 100]")
    final_score: float = Field(..., ge=0.0, le=100.0, description="Final calibrated composite match score [0, 100]")
    overall_score: float = Field(..., ge=0.0, le=100.0, description="Canonical composite score alias")

    fit_category: Optional[str] = Field(default=None, description="Qualitative fit tier (e.g., STRONG_MATCH)")

    # Canonical diagnostic and explainability breakdowns
    skills_breakdown: Dict[str, Any] = Field(default_factory=dict, description="Canonical skills breakdown")
    experience_breakdown: Dict[str, Any] = Field(default_factory=dict, description="Canonical experience breakdown")
    education_breakdown: Dict[str, Any] = Field(default_factory=dict, description="Canonical education breakdown")
    explanation: Dict[str, Any] = Field(default_factory=dict, description="Canonical explanation details")

    sub_scores: Optional[Dict[str, float]] = Field(default=None, description="Sub-scores dictionary")
    score_weights: Optional[Dict[str, float]] = Field(default=None, description="Normalized scoring component weights")
    created_at: Optional[datetime] = Field(default_factory=lambda: datetime.now(UTC), description="Evaluation timestamp")

    @model_validator(mode="before")
    @classmethod
    def sync_score_aliases(cls, data: Any) -> Any:
        # 1. Handle ORM Match instance
        if hasattr(data, "overall_score") and hasattr(data, "breakdown") and not isinstance(data, dict):
            bd = getattr(data, "breakdown", {}) or {}
            sub = bd.get("sub_scores", {})
            sem = getattr(data, "semantic_score", 0.0)
            sk = getattr(data, "skills_score", 0.0)
            exp = getattr(data, "experience_score", 0.0)
            edu = getattr(data, "education_score", 0.0)
            ov = getattr(data, "overall_score", 0.0)
            return {
                "match_id": getattr(data, "id", None),
                "semantic_score": sem,
                "skill_score": sk,
                "skills_score": sk,
                "experience_score": exp,
                "education_score": edu,
                "final_score": ov,
                "overall_score": ov,
                "fit_category": bd.get("fit_category") or ("STRONG_MATCH" if ov >= 80 else ("MODERATE_MATCH" if ov >= 65 else "LOW_MATCH")),
                "skills_breakdown": bd.get("skills_breakdown", {}),
                "experience_breakdown": bd.get("experience_breakdown", {}),
                "education_breakdown": bd.get("education_breakdown", {}),
                "explanation": getattr(data, "explanation", {}) or {},
                "sub_scores": sub if sub else {
                    "semantic_score": sem,
                    "skills_score": sk,
                    "experience_score": exp,
                    "education_score": edu,
                },
                "score_weights": bd.get("score_weights"),
                "created_at": getattr(data, "created_at", None),
            }

        if isinstance(data, dict):
            # Synchronize final_score <-> overall_score
            if "final_score" not in data and "overall_score" in data:
                data["final_score"] = data["overall_score"]
            elif "overall_score" not in data and "final_score" in data:
                data["overall_score"] = data["final_score"]

            # Synchronize skill_score <-> skills_score
            if "skill_score" not in data and "skills_score" in data:
                data["skill_score"] = data["skills_score"]
            elif "skills_score" not in data and "skill_score" in data:
                data["skills_score"] = data["skill_score"]

            # Handle sub_scores mapping if sub_scores dict is provided
            if "sub_scores" in data and isinstance(data["sub_scores"], dict):
                subs = data["sub_scores"]
                for key in ["semantic_score", "experience_score", "education_score"]:
                    if key not in data and key in subs:
                        data[key] = subs[key]
                if "skill_score" not in data and "skills_score" in subs:
                    data["skill_score"] = subs["skills_score"]
                if "skills_score" not in data and "skills_score" in subs:
                    data["skills_score"] = subs["skills_score"]
        return data



class MatchListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore")

    match_id: uuid.UUID = Field(..., description="Unique match evaluation UUID")
    resume_id: uuid.UUID = Field(..., description="Resume UUID")
    job_id: uuid.UUID = Field(..., description="Job UUID")
    overall_score: float = Field(..., description="Final overall match score")
    fit_category: Optional[str] = Field(default=None, description="Fit category")
    created_at: datetime = Field(..., description="Match timestamp")
