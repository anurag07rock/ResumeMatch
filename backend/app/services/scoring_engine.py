"""
Hybrid Scoring Engine Service
ResumeMatch — Explainable AI-Powered Resume-to-Job Matching Platform

Implements the calibrated hybrid matching architecture defined in AGENTS.md
and docs/AI_ML_ARCHITECTURE.md:
- Semantic Similarity: 50% (dense vector cosine similarity mapped to [0, 100])
- Skills Match: 30% (deterministic recall on required and preferred skills)
- Experience Match: 10% (years delta with non-linear under-qualification penalty curve)
- Education Match: 10% (degree hierarchy step matching)

Strict Architectural Governance Adherence:
- 100% deterministic reproducibility given identical inputs.
- Strict canonical field names: 'skills_breakdown', 'experience_breakdown',
  'education_breakdown', 'explanation'.
- Zero fabrication: explanations and breakdowns derive strictly from calculated
  intersections and metrics.
- Comprehensive boundary checking: non-finite values (NaN/Inf), negative numbers,
  and out-of-range inputs raise explicit controlled errors.
- Internal high precision; formatted presentation rounding at output boundaries.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import numpy as np
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Default Weights & Calibrations
# ---------------------------------------------------------------------------

DEFAULT_SCORE_WEIGHTS: Dict[str, float] = {
    "semantic": 0.50,
    "skills": 0.30,
    "experience": 0.10,
    "education": 0.10,
}

# Semantic Cosine Calibration: maps cosine range [tau_min, tau_max] to [0, 100]
SEMANTIC_TAU_MIN: float = 0.20
SEMANTIC_TAU_MAX: float = 0.85

# Degree Hierarchy Ordinal Scale (0 to 5)
DEGREE_HIERARCHY: Dict[str, int] = {
    # Rank 5: Doctorate
    "doctorate": 5,
    "ph.d.": 5,
    "phd": 5,
    "doctor of philosophy": 5,
    "doctor": 5,
    "post-doc": 5,
    "postdoc": 5,
    "md": 5,
    "m.d.": 5,
    "jd": 5,
    "j.d.": 5,

    # Rank 4: Master's
    "master": 4,
    "master's": 4,
    "masters": 4,
    "m.s.": 4,
    "ms": 4,
    "m.a.": 4,
    "ma": 4,
    "mba": 4,
    "m.b.a.": 4,
    "m.tech": 4,
    "mtech": 4,
    "master of science": 4,
    "master of arts": 4,
    "master of business administration": 4,
    "msc": 4,
    "m.sc.": 4,
    "meng": 4,
    "m.eng": 4,

    # Rank 3: Bachelor's
    "bachelor": 3,
    "bachelor's": 3,
    "bachelors": 3,
    "b.s.": 3,
    "bs": 3,
    "b.a.": 3,
    "ba": 3,
    "b.tech": 3,
    "btech": 3,
    "b.e.": 3,
    "be": 3,
    "bachelor of science": 3,
    "bachelor of arts": 3,
    "bachelor of engineering": 3,
    "bachelor of technology": 3,
    "bsc": 3,
    "b.sc.": 3,
    "beng": 3,
    "b.eng": 3,

    # Rank 2: Associate
    "associate": 2,
    "associate's": 2,
    "associates": 2,
    "a.s.": 2,
    "as": 2,
    "a.a.": 2,
    "aa": 2,
    "associate degree": 2,
    "associate of science": 2,
    "associate of arts": 2,

    # Rank 1: High School
    "high school": 1,
    "secondary": 1,
    "secondary school": 1,
    "diploma": 1,
    "ged": 1,
    "high school diploma": 1,

    # Rank 0: Unspecified
    "unspecified": 0,
    "none": 0,
    "not detected": 0,
}

RANK_TO_CANONICAL_NAME: Dict[int, str] = {
    5: "Doctorate",
    4: "Master's",
    3: "Bachelor's",
    2: "Associate",
    1: "High School",
    0: "Unspecified",
}


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class ScoringEngineError(Exception):
    """Base exception for scoring engine errors."""
    pass


class InvalidInputError(ScoringEngineError, ValueError):
    """Raised when scoring input is invalid, non-finite, or out-of-range."""
    pass


# ---------------------------------------------------------------------------
# Data Transfer Objects & Result Schemas
# ---------------------------------------------------------------------------

class ScoreWeights(BaseModel):
    """Normalized scoring component weights summing to 1.0."""
    semantic: float = Field(default=0.50, ge=0.0, le=1.0)
    skills: float = Field(default=0.30, ge=0.0, le=1.0)
    experience: float = Field(default=0.10, ge=0.0, le=1.0)
    education: float = Field(default=0.10, ge=0.0, le=1.0)


class SubScores(BaseModel):
    """Normalized sub-scores bounded in [0.0, 100.0]."""
    semantic_score: float = Field(..., ge=0.0, le=100.0)
    skills_score: float = Field(..., ge=0.0, le=100.0)
    experience_score: float = Field(..., ge=0.0, le=100.0)
    education_score: float = Field(..., ge=0.0, le=100.0)


class SkillsBreakdown(BaseModel):
    """Canonical skills breakdown contract."""
    matched_required: List[str] = Field(default_factory=list)
    matched_preferred: List[str] = Field(default_factory=list)
    missing_critical: List[str] = Field(default_factory=list)
    missing_preferred: List[str] = Field(default_factory=list)
    match_rate_required: float = Field(default=0.0, ge=0.0, le=1.0)
    match_rate_preferred: float = Field(default=0.0, ge=0.0, le=1.0)


class ExperienceBreakdown(BaseModel):
    """Canonical experience breakdown contract."""
    candidate_years: float = Field(default=0.0, ge=0.0)
    required_years: float = Field(default=0.0, ge=0.0)
    delta_years: float = Field(default=0.0)
    status: str = Field(default="MEETS_REQUIREMENT")


class EducationBreakdown(BaseModel):
    """Canonical education breakdown contract."""
    candidate_level: str = Field(default="Unspecified")
    required_level: str = Field(default="Unspecified")
    candidate_rank: int = Field(default=0, ge=0, le=5)
    required_rank: int = Field(default=0, ge=0, le=5)
    status: str = Field(default="FULLY_ALIGNED")


class ExplanationDetails(BaseModel):
    """Canonical explanation contract."""
    summary: str = Field(...)
    key_strengths: List[str] = Field(default_factory=list)
    growth_areas: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)


class MatchResult(BaseModel):
    """Complete match result envelope following the canonical OpenAPI contract."""
    overall_score: float = Field(..., ge=0.0, le=100.0)
    raw_overall_score: float = Field(..., ge=0.0, le=100.0)
    fit_category: str = Field(...)
    sub_scores: SubScores = Field(...)
    score_weights: ScoreWeights = Field(...)
    skills_breakdown: SkillsBreakdown = Field(...)
    experience_breakdown: ExperienceBreakdown = Field(...)
    education_breakdown: EducationBreakdown = Field(...)
    explanation: ExplanationDetails = Field(...)

    def to_db_record(self) -> Dict[str, Any]:
        """Maps match result to the PostgreSQL 'matches' table schema."""
        return {
            "overall_score": self.overall_score,
            "semantic_score": self.sub_scores.semantic_score,
            "skills_score": self.sub_scores.skills_score,
            "experience_score": self.sub_scores.experience_score,
            "education_score": self.sub_scores.education_score,
            "breakdown": {
                "skills_breakdown": self.skills_breakdown.model_dump(),
                "experience_breakdown": self.experience_breakdown.model_dump(),
                "education_breakdown": self.education_breakdown.model_dump(),
            },
            "explanation": self.explanation.model_dump(),
        }


# ---------------------------------------------------------------------------
# Scoring Engine Implementation
# ---------------------------------------------------------------------------

class ScoringEngine:
    """
    Deterministic hybrid scoring engine for candidate resume and job matching.
    Decoupled from network I/O, database writes, and web handlers.
    """

    def __init__(self, default_weights: Optional[Dict[str, float]] = None) -> None:
        self.weights = self._validate_and_normalize_weights(
            default_weights or DEFAULT_SCORE_WEIGHTS
        )

    # -----------------------------------------------------------------------
    # Validation Utilities
    # -----------------------------------------------------------------------

    @staticmethod
    def _validate_and_normalize_weights(weights: Dict[str, float]) -> ScoreWeights:
        """Validates that all 4 component weights exist, are finite non-negative numbers, and sum to 1.0."""
        expected_keys = {"semantic", "skills", "experience", "education"}
        if not isinstance(weights, dict):
            raise InvalidInputError("Weights must be a dictionary.")

        missing_keys = expected_keys - set(weights.keys())
        if missing_keys:
            raise InvalidInputError(f"Missing required weight keys: {sorted(list(missing_keys))}")

        normalized_vals: Dict[str, float] = {}
        for key in expected_keys:
            val = weights[key]
            if not isinstance(val, (int, float)) or isinstance(val, bool):
                raise InvalidInputError(f"Weight '{key}' must be a numeric value, got {type(val).__name__}.")
            if not math.isfinite(val):
                raise InvalidInputError(f"Weight '{key}' must be a finite number, got {val}.")
            if val < 0.0:
                raise InvalidInputError(f"Weight '{key}' cannot be negative, got {val}.")
            normalized_vals[key] = float(val)

        total = sum(normalized_vals.values())
        if abs(total - 1.0) > 1e-4:
            raise InvalidInputError(
                f"Weights must sum to 1.0 (received sum: {total:.4f})."
            )

        return ScoreWeights(**normalized_vals)

    @staticmethod
    def parse_education_level(level: Optional[Union[str, int]]) -> Tuple[int, str]:
        """
        Parses degree string or integer ordinal rank into (rank, canonical_name).
        Ranks:
        5 - Doctorate / Ph.D.
        4 - Master's
        3 - Bachelor's
        2 - Associate
        1 - High School
        0 - Unspecified
        """
        if level is None:
            return 0, RANK_TO_CANONICAL_NAME[0]

        if isinstance(level, int):
            if level < 0 or level > 5:
                raise InvalidInputError(f"Education ordinal rank must be between 0 and 5, got {level}.")
            return level, RANK_TO_CANONICAL_NAME.get(level, "Unspecified")

        if not isinstance(level, str):
            raise InvalidInputError(f"Education level must be str, int, or None; got {type(level).__name__}.")

        cleaned = level.strip().lower()
        if not cleaned:
            return 0, RANK_TO_CANONICAL_NAME[0]

        # Exact match in degree hierarchy
        if cleaned in DEGREE_HIERARCHY:
            r = DEGREE_HIERARCHY[cleaned]
            return r, RANK_TO_CANONICAL_NAME[r]

        # Substring search sorted by descending rank to pick the highest credential mentioned
        for kw, r in sorted(DEGREE_HIERARCHY.items(), key=lambda item: -item[1]):
            if kw in cleaned:
                return r, RANK_TO_CANONICAL_NAME[r]

        return 0, level.strip()

    # -----------------------------------------------------------------------
    # Component Scoring Methods
    # -----------------------------------------------------------------------

    def calculate_semantic_score(
        self,
        resume_vector: Optional[Union[List[float], np.ndarray]] = None,
        job_vector: Optional[Union[List[float], np.ndarray]] = None,
        raw_cosine_similarity: Optional[float] = None,
        tau_min: float = SEMANTIC_TAU_MIN,
        tau_max: float = SEMANTIC_TAU_MAX,
    ) -> float:
        """
        Calculates normalized semantic similarity score [0.0, 100.0] using cosine similarity.
        Either precomputed raw_cosine_similarity or both resume_vector and job_vector must be provided.
        """
        if raw_cosine_similarity is not None:
            if not isinstance(raw_cosine_similarity, (int, float)) or isinstance(raw_cosine_similarity, bool):
                raise InvalidInputError("raw_cosine_similarity must be a numeric value.")
            if not math.isfinite(raw_cosine_similarity):
                raise InvalidInputError("raw_cosine_similarity must be a finite number.")
            if raw_cosine_similarity < -1.0 or raw_cosine_similarity > 1.0:
                raise InvalidInputError(f"Cosine similarity must be within [-1.0, 1.0], got {raw_cosine_similarity}.")
            cosine = float(raw_cosine_similarity)
        else:
            if resume_vector is None or job_vector is None:
                raise InvalidInputError(
                    "Semantic scoring requires either both resume_vector and job_vector, "
                    "or a precomputed raw_cosine_similarity."
                )

            rv = np.asarray(resume_vector, dtype=np.float64)
            jv = np.asarray(job_vector, dtype=np.float64)

            if rv.ndim != 1 or jv.ndim != 1:
                raise InvalidInputError("Embedding vectors must be 1-dimensional arrays.")
            if rv.shape[0] != jv.shape[0]:
                raise InvalidInputError(
                    f"Vector dimension mismatch: resume has {rv.shape[0]} dimensions, "
                    f"job has {jv.shape[0]} dimensions."
                )
            if rv.shape[0] == 0:
                raise InvalidInputError("Embedding vectors cannot be empty.")
            if not np.all(np.isfinite(rv)):
                raise InvalidInputError("resume_vector contains non-finite values (NaN or Inf).")
            if not np.all(np.isfinite(jv)):
                raise InvalidInputError("job_vector contains non-finite values (NaN or Inf).")

            norm_rv = np.linalg.norm(rv)
            norm_jv = np.linalg.norm(jv)
            if norm_rv == 0.0 or norm_jv == 0.0:
                raise InvalidInputError("Embedding vector norm is zero; cannot compute cosine similarity.")

            cosine = float(np.dot(rv, jv) / (norm_rv * norm_jv))
            # Clip numerical precision drift
            cosine = max(-1.0, min(1.0, cosine))

        # Calibrate [tau_min, tau_max] -> [0.0, 100.0]
        if tau_max <= tau_min:
            raise InvalidInputError("tau_max must be strictly greater than tau_min.")

        clamped = max(0.0, min(1.0, (cosine - tau_min) / (tau_max - tau_min)))
        return float(clamped * 100.0)

    def calculate_skills_score(
        self,
        candidate_skills: Union[List[str], Set[str]],
        required_skills: Union[List[str], Set[str]],
        preferred_skills: Optional[Union[List[str], Set[str]]] = None,
    ) -> Tuple[float, SkillsBreakdown]:
        """
        Calculates deterministic skill match score and generates canonical skills_breakdown.
        Weights required skills at 75% and preferred skills at 25% when both are present.
        If only required skills are specified, required recall constitutes 100% of skills score.
        """
        if not isinstance(candidate_skills, (list, set, tuple)):
            raise InvalidInputError(f"candidate_skills must be an iterable, got {type(candidate_skills).__name__}.")
        if not isinstance(required_skills, (list, set, tuple)):
            raise InvalidInputError(f"required_skills must be an iterable, got {type(required_skills).__name__}.")
        if preferred_skills is not None and not isinstance(preferred_skills, (list, set, tuple)):
            raise InvalidInputError(f"preferred_skills must be an iterable, got {type(preferred_skills).__name__}.")

        # Normalize casing and strip whitespace
        def _normalize_set(items: Optional[Union[List[str], Set[str]]]) -> Set[str]:
            if not items:
                return set()
            normalized = set()
            for it in items:
                if not isinstance(it, str):
                    raise InvalidInputError(f"Skill entry must be a string, got {type(it).__name__}.")
                s = it.strip()
                if s:
                    normalized.add(s)
            return normalized

        cand_set = _normalize_set(candidate_skills)
        req_set = _normalize_set(required_skills)
        pref_raw = _normalize_set(preferred_skills)

        # Build case-insensitive lookup dictionaries for exact matching
        cand_map = {s.lower(): s for s in cand_set}

        # Preferred skills should not double-count skills already in required
        pref_set = {s for s in pref_raw if s.lower() not in {r.lower() for r in req_set}}

        # Partition required
        matched_req = [req for req in req_set if req.lower() in cand_map]
        missing_req = [req for req in req_set if req.lower() not in cand_map]

        # Partition preferred
        matched_pref = [pref for pref in pref_set if pref.lower() in cand_map]
        missing_pref = [pref for pref in pref_set if pref.lower() not in cand_map]

        # Deterministic sorting
        matched_req.sort()
        missing_req.sort()
        matched_pref.sort()
        missing_pref.sort()

        # Recall computation
        recall_req = len(matched_req) / len(req_set) if len(req_set) > 0 else 0.0
        recall_pref = len(matched_pref) / len(pref_set) if len(pref_set) > 0 else 0.0

        if len(req_set) > 0 and len(pref_set) > 0:
            score = (0.75 * recall_req + 0.25 * recall_pref) * 100.0
        elif len(req_set) > 0 and len(pref_set) == 0:
            score = recall_req * 100.0
        elif len(req_set) == 0 and len(pref_set) > 0:
            score = recall_pref * 100.0
        else:
            # Missing/unspecified skills in job description: score 0.0 per rule
            score = 0.0

        breakdown = SkillsBreakdown(
            matched_required=matched_req,
            matched_preferred=matched_pref,
            missing_critical=missing_req,
            missing_preferred=missing_pref,
            match_rate_required=round(recall_req, 4),
            match_rate_preferred=round(recall_pref, 4),
        )

        return float(max(0.0, min(100.0, score))), breakdown

    def calculate_experience_score(
        self,
        candidate_years: Optional[Union[int, float]],
        required_years: Optional[Union[int, float]],
    ) -> Tuple[float, ExperienceBreakdown]:
        """
        Calculates experience score with non-linear penalty for under-qualification.
        Formulation:
        - If candidate_years >= required_years: 100.0
        - If 0 < candidate_years < required_years: (candidate_years / required_years)^1.2 * 100
        - If candidate_years == 0 and required_years <= 1: 40.0
        - If candidate_years == 0 and required_years > 1: 10.0
        """
        # Validate candidate years
        if candidate_years is not None:
            if not isinstance(candidate_years, (int, float)) or isinstance(candidate_years, bool):
                raise InvalidInputError(f"candidate_years must be numeric, got {type(candidate_years).__name__}.")
            if not math.isfinite(candidate_years):
                raise InvalidInputError("candidate_years must be a finite number.")
            if candidate_years < 0.0:
                raise InvalidInputError("candidate_years cannot be negative.")
            yc = float(candidate_years)
        else:
            yc = 0.0

        # Validate required years
        if required_years is not None:
            if not isinstance(required_years, (int, float)) or isinstance(required_years, bool):
                raise InvalidInputError(f"required_years must be numeric, got {type(required_years).__name__}.")
            if not math.isfinite(required_years):
                raise InvalidInputError("required_years must be a finite number.")
            if required_years < 0.0:
                raise InvalidInputError("required_years cannot be negative.")
            yr = float(required_years)
        else:
            yr = 0.0

        delta = round(yc - yr, 2)

        if yr <= 0.0:
            score = 100.0
            status = "MEETS_REQUIREMENT"
        elif yc >= yr:
            score = 100.0
            status = "EXCEEDS_REQUIREMENT" if yc > yr else "MEETS_REQUIREMENT"
        elif yc > 0.0:
            score = ((yc / yr) ** 1.2) * 100.0
            status = "BELOW_REQUIREMENT"
        else:
            score = 40.0 if yr <= 1.0 else 10.0
            status = "BELOW_REQUIREMENT"

        breakdown = ExperienceBreakdown(
            candidate_years=round(yc, 2),
            required_years=round(yr, 2),
            delta_years=delta,
            status=status,
        )

        return float(max(0.0, min(100.0, score))), breakdown

    def calculate_education_score(
        self,
        candidate_level: Optional[Union[str, int]],
        required_level: Optional[Union[str, int]],
    ) -> Tuple[float, EducationBreakdown]:
        """
        Calculates education fit score using ordinal hierarchy:
        - Rc >= Rr: 100.0
        - Rc == Rr - 1: 85.0
        - Rc == Rr - 2: 60.0
        - Rc < Rr - 2: 30.0
        If job requires no degree (Rr == 0), score is 100.0.
        """
        rc, cand_display = self.parse_education_level(candidate_level)
        rr, req_display = self.parse_education_level(required_level)

        if rr == 0:
            score = 100.0
            status = "FULLY_ALIGNED"
        elif rc >= rr:
            score = 100.0
            status = "FULLY_ALIGNED"
        elif rc == rr - 1:
            score = 85.0
            status = "PARTIALLY_ALIGNED"
        elif rc == rr - 2:
            score = 60.0
            status = "BELOW_REQUIREMENT"
        else:
            score = 30.0
            status = "BELOW_REQUIREMENT"

        breakdown = EducationBreakdown(
            candidate_level=cand_display,
            required_level=req_display,
            candidate_rank=rc,
            required_rank=rr,
            status=status,
        )

        return float(max(0.0, min(100.0, score))), breakdown

    # -----------------------------------------------------------------------
    # Explainability & Diagnostic Attribution (Zero Fabrication)
    # -----------------------------------------------------------------------

    @staticmethod
    def _generate_explanation(
        overall_score: float,
        fit_category: str,
        sub_scores: SubScores,
        skills_breakdown: SkillsBreakdown,
        experience_breakdown: ExperienceBreakdown,
        education_breakdown: EducationBreakdown,
    ) -> ExplanationDetails:
        """
        Generates deterministic, evidence-based explanation narrative and gap attribution.
        Derived strictly from calculated scores and entity intersections.
        """
        key_strengths: List[str] = []
        growth_areas: List[str] = []
        recommendations: List[str] = []

        # 1. Skills Evidence
        tot_req = len(skills_breakdown.matched_required) + len(skills_breakdown.missing_critical)
        if tot_req > 0:
            match_pct = round(skills_breakdown.match_rate_required * 100, 1)
            if skills_breakdown.match_rate_required == 1.0:
                key_strengths.append(
                    f"Candidate matches 100% of required technical competencies "
                    f"({', '.join(skills_breakdown.matched_required[:5])})."
                )
            elif skills_breakdown.match_rate_required >= 0.6:
                key_strengths.append(
                    f"Candidate matches {len(skills_breakdown.matched_required)} of {tot_req} "
                    f"required skills ({match_pct}%) including {', '.join(skills_breakdown.matched_required[:4])}."
                )

        if skills_breakdown.matched_preferred:
            key_strengths.append(
                f"Demonstrates preferred proficiencies: {', '.join(skills_breakdown.matched_preferred[:4])}."
            )

        if skills_breakdown.missing_critical:
            missing_preview = ", ".join(skills_breakdown.missing_critical[:4])
            growth_areas.append(
                f"Missing {len(skills_breakdown.missing_critical)} required skill(s): {missing_preview}."
            )
            recommendations.append(
                f"Highlight hands-on project exposure or certifications covering {missing_preview}."
            )

        if skills_breakdown.missing_preferred:
            growth_areas.append(
                f"Missing preferred skill(s): {', '.join(skills_breakdown.missing_preferred[:4])}."
            )

        # 2. Experience Evidence
        yc = experience_breakdown.candidate_years
        yr = experience_breakdown.required_years
        delta = experience_breakdown.delta_years

        if yr > 0:
            if yc >= yr:
                if delta > 0:
                    key_strengths.append(
                        f"{yc:.1f} years of verified experience exceeds the {yr:.1f}-year baseline (delta: +{delta:.1f} yrs)."
                    )
                else:
                    key_strengths.append(
                        f"{yc:.1f} years of verified experience meets the required {yr:.1f}-year threshold."
                    )
            else:
                growth_areas.append(
                    f"Experience of {yc:.1f} years falls below the required {yr:.1f} years (gap: {abs(delta):.1f} yrs)."
                )
                recommendations.append(
                    "Emphasize technical project depth and velocity of delivery to offset the experience delta."
                )

        # 3. Education Evidence
        cand_level = education_breakdown.candidate_level
        req_level = education_breakdown.required_level
        if education_breakdown.required_rank > 0:
            if education_breakdown.status == "FULLY_ALIGNED":
                key_strengths.append(
                    f"Holds {cand_level} credential, meeting the {req_level} baseline requirement."
                )
            elif education_breakdown.status == "PARTIALLY_ALIGNED":
                growth_areas.append(
                    f"Position prefers {req_level}, while candidate holds {cand_level}."
                )
                recommendations.append(
                    f"Emphasize specialized coursework or industry accomplishments to balance the {req_level} preference."
                )
            else:
                growth_areas.append(
                    f"Education credential ({cand_level}) does not meet the {req_level} requirement."
                )

        # 4. Semantic Relevance
        if sub_scores.semantic_score >= 80.0:
            key_strengths.append(
                f"Strong holistic domain alignment ({sub_scores.semantic_score:.1f}%) with job description."
            )
        elif sub_scores.semantic_score < 45.0:
            growth_areas.append(
                f"Moderate to low overall semantic vocabulary alignment ({sub_scores.semantic_score:.1f}%)."
            )

        # Summary line
        summary = (
            f"Compatibility rating: {overall_score:.1f}% ({fit_category}). "
            f"Evaluated across semantic similarity ({sub_scores.semantic_score:.1f}%), "
            f"technical skills ({sub_scores.skills_score:.1f}%), "
            f"experience ({sub_scores.experience_score:.1f}%), "
            f"and education ({sub_scores.education_score:.1f}%)."
        )

        return ExplanationDetails(
            summary=summary,
            key_strengths=key_strengths,
            growth_areas=growth_areas,
            recommendations=recommendations,
        )

    # -----------------------------------------------------------------------
    # High-Level Orchestration
    # -----------------------------------------------------------------------

    def compute_match(
        self,
        candidate_skills: Union[List[str], Set[str]],
        required_skills: Union[List[str], Set[str]],
        preferred_skills: Optional[Union[List[str], Set[str]]] = None,
        candidate_years: Optional[Union[int, float]] = None,
        required_years: Optional[Union[int, float]] = None,
        candidate_education: Optional[Union[str, int]] = None,
        required_education: Optional[Union[str, int]] = None,
        resume_vector: Optional[Union[List[float], np.ndarray]] = None,
        job_vector: Optional[Union[List[float], np.ndarray]] = None,
        raw_cosine_similarity: Optional[float] = None,
        weights: Optional[Dict[str, float]] = None,
    ) -> MatchResult:
        """
        Executes complete hybrid match scoring between candidate data and job requirements.
        Returns a validated MatchResult adhering strictly to canonical schema contracts.
        """
        # Resolve weights (uses instance weights if not customized)
        score_weights = (
            self._validate_and_normalize_weights(weights)
            if weights is not None
            else self.weights
        )

        # 1. Component calculations
        sem_score = self.calculate_semantic_score(
            resume_vector=resume_vector,
            job_vector=job_vector,
            raw_cosine_similarity=raw_cosine_similarity,
        )
        skills_score, skills_bd = self.calculate_skills_score(
            candidate_skills=candidate_skills,
            required_skills=required_skills,
            preferred_skills=preferred_skills,
        )
        exp_score, exp_bd = self.calculate_experience_score(
            candidate_years=candidate_years,
            required_years=required_years,
        )
        edu_score, edu_bd = self.calculate_education_score(
            candidate_level=candidate_education,
            required_level=required_education,
        )

        # 2. Composite score calculation (applied exactly once)
        raw_composite = (
            score_weights.semantic * sem_score
            + score_weights.skills * skills_score
            + score_weights.experience * exp_score
            + score_weights.education * edu_score
        )
        bounded_composite = float(max(0.0, min(100.0, raw_composite)))
        presentation_overall = round(bounded_composite, 1)

        # 3. Fit category classification
        if bounded_composite >= 80.0:
            fit_category = "STRONG_MATCH"
        elif bounded_composite >= 65.0:
            fit_category = "MODERATE_MATCH"
        elif bounded_composite >= 50.0:
            fit_category = "LOW_MATCH"
        else:
            fit_category = "NO_MATCH"

        sub_scores = SubScores(
            semantic_score=round(sem_score, 1),
            skills_score=round(skills_score, 1),
            experience_score=round(exp_score, 1),
            education_score=round(edu_score, 1),
        )

        # 4. Evidence-based explanation
        explanation = self._generate_explanation(
            overall_score=presentation_overall,
            fit_category=fit_category,
            sub_scores=sub_scores,
            skills_breakdown=skills_bd,
            experience_breakdown=exp_bd,
            education_breakdown=edu_bd,
        )

        return MatchResult(
            overall_score=presentation_overall,
            raw_overall_score=bounded_composite,
            fit_category=fit_category,
            sub_scores=sub_scores,
            score_weights=score_weights,
            skills_breakdown=skills_bd,
            experience_breakdown=exp_bd,
            education_breakdown=edu_bd,
            explanation=explanation,
        )


# Singleton instance for general use
scoring_engine = ScoringEngine()
