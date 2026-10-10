"""
Unit Tests for Hybrid Scoring Engine
ResumeMatch — Explainable AI-Powered Resume-to-Job Matching Platform

Validates:
1. Component weight calibration (50% semantic, 30% skills, 10% experience, 10% education).
2. Isolated component impact on overall composite score.
3. Perfect, partial, and zero-match boundary conditions.
4. Semantic score calibration curve ([tau_min, tau_max] -> [0, 100]) and cosine checks.
5. Deterministic skills recall for required and preferred requirements.
6. Experience penalty curve (non-linear 1.2 exponent and zero-experience floors).
7. Education hierarchy matching across ordinal ranks 0 to 5.
8. Comprehensive boundary validation (rejecting negative, non-finite, and out-of-range inputs).
9. Evidence-based explanation generation with zero hallucination/fabrication.
10. Deterministic reproducibility across repeated invocations.
11. Compatibility with PostgreSQL matches table JSON schema.
"""

import math
import numpy as np
import pytest

from app.services.scoring_engine import (
    DEFAULT_SCORE_WEIGHTS,
    EducationBreakdown,
    ExperienceBreakdown,
    ExplanationDetails,
    InvalidInputError,
    MatchResult,
    ScoreWeights,
    ScoringEngine,
    SkillsBreakdown,
    SubScores,
    scoring_engine,
)


# ---------------------------------------------------------------------------
# 1. Weight Calibration & Configuration Tests
# ---------------------------------------------------------------------------

def test_default_weights_configuration():
    """Verify default component weights are strictly 50/30/10/10 and sum to 1.0."""
    engine = ScoringEngine()
    assert engine.weights.semantic == 0.50
    assert engine.weights.skills == 0.30
    assert engine.weights.experience == 0.10
    assert engine.weights.education == 0.10
    total = (
        engine.weights.semantic
        + engine.weights.skills
        + engine.weights.experience
        + engine.weights.education
    )
    assert math.isclose(total, 1.0, rel_tol=1e-5)


def test_custom_weights_acceptance():
    """Verify valid custom weights summing to 1.0 are accepted."""
    custom = {
        "semantic": 0.40,
        "skills": 0.40,
        "experience": 0.10,
        "education": 0.10,
    }
    engine = ScoringEngine(default_weights=custom)
    assert engine.weights.semantic == 0.40
    assert engine.weights.skills == 0.40


def test_invalid_weights_rejected():
    """Verify invalid weights (not summing to 1.0, negative, non-finite, or missing keys) are rejected."""
    # Sum != 1.0
    with pytest.raises(InvalidInputError, match="Weights must sum to 1.0"):
        ScoringEngine(
            default_weights={"semantic": 0.5, "skills": 0.5, "experience": 0.5, "education": 0.5}
        )

    # Negative weight
    with pytest.raises(InvalidInputError, match="cannot be negative"):
        ScoringEngine(
            default_weights={"semantic": -0.1, "skills": 0.7, "experience": 0.2, "education": 0.2}
        )

    # Non-finite weight
    with pytest.raises(InvalidInputError, match="must be a finite number"):
        ScoringEngine(
            default_weights={"semantic": float("nan"), "skills": 0.3, "experience": 0.1, "education": 0.1}
        )

    # Missing key
    with pytest.raises(InvalidInputError, match="Missing required weight keys"):
        ScoringEngine(
            default_weights={"semantic": 0.7, "skills": 0.3}
        )


# ---------------------------------------------------------------------------
# 2. Individual Component Isolated Impact (50 / 30 / 10 / 10)
# ---------------------------------------------------------------------------

def test_isolated_component_weights_impact():
    """
    Verify each component contributes exactly its designated percentage weight:
    - Semantic (100) -> 50.0
    - Skills (100) -> 30.0
    - Experience (100) -> 10.0
    - Education (100) -> 10.0
    """
    engine = ScoringEngine()

    # 1. Semantic alone
    res_sem = engine.compute_match(
        candidate_skills=[],
        required_skills=["Python"],  # 0% match
        candidate_years=0,
        required_years=10,  # low match
        candidate_education=0,
        required_education=5,  # low match
        raw_cosine_similarity=0.85,  # 100% semantic
    )
    # semantic contributes 0.50 * 100 = 50.0
    # skills = 0.30 * 0 = 0
    # exp = 0.10 * 10 = 1.0
    # edu = 0.10 * 30 = 3.0
    # total = 54.0
    assert res_sem.sub_scores.semantic_score == 100.0
    assert math.isclose(res_sem.overall_score, 54.0, abs_tol=0.2)

    # 2. Skills alone (perfect skills, semantic 0, exp/edu lowest possible)
    res_skills = engine.compute_match(
        candidate_skills=["Python", "PostgreSQL"],
        required_skills=["Python", "PostgreSQL"],  # 100% skills
        candidate_years=0,
        required_years=10,
        candidate_education=0,
        required_education=5,
        raw_cosine_similarity=0.10,  # 0% semantic
    )
    # semantic = 0
    # skills = 0.30 * 100 = 30.0
    # exp = 0.10 * 10 = 1.0
    # edu = 0.10 * 30 = 3.0
    # total = 34.0
    assert res_skills.sub_scores.skills_score == 100.0
    assert res_skills.sub_scores.semantic_score == 0.0
    assert math.isclose(res_skills.overall_score, 34.0, abs_tol=0.2)


# ---------------------------------------------------------------------------
# 3. Perfect Match, Partial Match & Zero Match
# ---------------------------------------------------------------------------

def test_perfect_match_yields_100():
    """Verify candidate exceeding all requirements achieves 100.0 overall score."""
    engine = ScoringEngine()
    res = engine.compute_match(
        candidate_skills=["Python", "FastAPI", "PostgreSQL", "Docker", "AWS"],
        required_skills=["Python", "FastAPI", "PostgreSQL"],
        preferred_skills=["Docker", "AWS"],
        candidate_years=7.0,
        required_years=5.0,
        candidate_education="Master's",
        required_education="Bachelor's",
        raw_cosine_similarity=0.90,  # >= 0.85 -> 100.0
    )

    assert res.overall_score == 100.0
    assert res.raw_overall_score == 100.0
    assert res.fit_category == "STRONG_MATCH"
    assert res.sub_scores.semantic_score == 100.0
    assert res.sub_scores.skills_score == 100.0
    assert res.sub_scores.experience_score == 100.0
    assert res.sub_scores.education_score == 100.0

    # Breakdown verification
    assert res.skills_breakdown.match_rate_required == 1.0
    assert res.skills_breakdown.match_rate_preferred == 1.0
    assert len(res.skills_breakdown.missing_critical) == 0
    assert res.experience_breakdown.status == "EXCEEDS_REQUIREMENT"
    assert res.experience_breakdown.delta_years == 2.0
    assert res.education_breakdown.status == "FULLY_ALIGNED"


def test_zero_match_boundary():
    """Verify completely unqualified candidate produces low composite score."""
    engine = ScoringEngine()
    res = engine.compute_match(
        candidate_skills=["Cooking", "Guitar"],
        required_skills=["C++", "CUDA", "LLVM"],
        preferred_skills=["Vulkan"],
        candidate_years=0.0,
        required_years=8.0,
        candidate_education="High School",
        required_education="Doctorate",
        raw_cosine_similarity=0.10,  # <= 0.20 -> 0.0
    )

    # semantic: 0.0 * 0.50 = 0.0
    # skills: 0.0 * 0.30 = 0.0
    # exp: 10.0 * 0.10 = 1.0 (cand=0, req=8)
    # edu: 30.0 * 0.10 = 3.0 (rank 1 vs rank 5, delta=4 > 2)
    # composite: 4.0
    assert res.sub_scores.semantic_score == 0.0
    assert res.sub_scores.skills_score == 0.0
    assert res.sub_scores.experience_score == 10.0
    assert res.sub_scores.education_score == 30.0
    assert res.overall_score == 4.0
    assert res.fit_category == "NO_MATCH"
    assert len(res.skills_breakdown.missing_critical) == 3


def test_partial_match_calculation():
    """Verify partial match calculations combine accurately."""
    engine = ScoringEngine()
    # 50% skills (1 of 2 required matched, no preferred)
    # 5.0 years req, 2.5 years cand -> (2.5/5.0)^1.2 * 100 = (0.5)^1.2 * 100 = 43.527
    # Education: Bachelor's (3) for Master's (4) -> 85.0
    # Semantic: cosine 0.525 -> (0.525 - 0.20)/(0.85 - 0.20) * 100 = 50.0
    res = engine.compute_match(
        candidate_skills=["Python"],
        required_skills=["Python", "Go"],
        candidate_years=2.5,
        required_years=5.0,
        candidate_education="Bachelor's",
        required_education="Master's",
        raw_cosine_similarity=0.525,
    )

    assert math.isclose(res.sub_scores.semantic_score, 50.0, abs_tol=0.1)
    assert math.isclose(res.sub_scores.skills_score, 50.0, abs_tol=0.1)
    assert math.isclose(res.sub_scores.experience_score, 43.5, abs_tol=0.2)
    assert math.isclose(res.sub_scores.education_score, 85.0, abs_tol=0.1)

    # Expected composite: 0.50*50.0 + 0.30*50.0 + 0.10*43.53 + 0.10*85.0 = 25 + 15 + 4.35 + 8.5 = 52.85
    assert math.isclose(res.overall_score, 52.9, abs_tol=0.2)
    assert res.fit_category == "LOW_MATCH"


# ---------------------------------------------------------------------------
# 4. Semantic Similarity Calibration & Vector Tests
# ---------------------------------------------------------------------------

def test_semantic_score_calibration_curve():
    """Verify clamp to [0, 100] across [tau_min=0.20, tau_max=0.85]."""
    engine = ScoringEngine()

    assert engine.calculate_semantic_score(raw_cosine_similarity=0.20) == 0.0
    assert engine.calculate_semantic_score(raw_cosine_similarity=0.15) == 0.0
    assert engine.calculate_semantic_score(raw_cosine_similarity=-0.50) == 0.0

    assert engine.calculate_semantic_score(raw_cosine_similarity=0.85) == 100.0
    assert engine.calculate_semantic_score(raw_cosine_similarity=0.99) == 100.0
    assert engine.calculate_semantic_score(raw_cosine_similarity=1.0) == 100.0

    # Midpoint
    mid_cos = 0.20 + 0.5 * (0.85 - 0.20)  # 0.525
    assert math.isclose(engine.calculate_semantic_score(raw_cosine_similarity=mid_cos), 50.0)


def test_semantic_score_from_vector_inputs():
    """Verify semantic scoring accepts 1D numpy arrays and python lists."""
    engine = ScoringEngine()

    v1 = [1.0, 0.0, 0.0]
    v2 = [1.0, 0.0, 0.0]
    # Cosine = 1.0 -> 100.0
    assert engine.calculate_semantic_score(resume_vector=v1, job_vector=v2) == 100.0

    # Orthogonal vectors: Cosine = 0.0 -> <= 0.20 -> 0.0
    v3 = [0.0, 1.0, 0.0]
    assert engine.calculate_semantic_score(resume_vector=v1, job_vector=v3) == 0.0


def test_semantic_vector_validation_errors():
    """Verify vector dimension mismatches, NaN/Inf, and zero norm raise InvalidInputError."""
    engine = ScoringEngine()

    # Dimension mismatch
    with pytest.raises(InvalidInputError, match="dimension mismatch"):
        engine.calculate_semantic_score(resume_vector=[1.0, 0.0], job_vector=[1.0, 0.0, 0.0])

    # Non-finite values
    with pytest.raises(InvalidInputError, match="non-finite values"):
        engine.calculate_semantic_score(resume_vector=[float("nan"), 1.0], job_vector=[1.0, 1.0])

    # Zero norm
    with pytest.raises(InvalidInputError, match="norm is zero"):
        engine.calculate_semantic_score(resume_vector=[0.0, 0.0], job_vector=[1.0, 1.0])

    # Out of range cosine
    with pytest.raises(InvalidInputError, match="Cosine similarity must be within"):
        engine.calculate_semantic_score(raw_cosine_similarity=1.5)

    # Missing inputs
    with pytest.raises(InvalidInputError, match="requires either both"):
        engine.calculate_semantic_score()


# ---------------------------------------------------------------------------
# 5. Skills Score & Overlap Tests
# ---------------------------------------------------------------------------

def test_skills_score_required_and_preferred():
    """Verify 75% required / 25% preferred weighting and deduplication."""
    engine = ScoringEngine()

    cand = ["Python", "Docker", "AWS"]
    req = ["Python", "FastAPI"]  # 1 of 2 matched -> 50%
    pref = ["Docker", "Kubernetes"]  # 1 of 2 matched -> 50%

    score, bd = engine.calculate_skills_score(cand, req, pref)

    # 0.75 * 50 + 0.25 * 50 = 50.0
    assert score == 50.0
    assert bd.matched_required == ["Python"]
    assert bd.missing_critical == ["FastAPI"]
    assert bd.matched_preferred == ["Docker"]
    assert bd.missing_preferred == ["Kubernetes"]
    assert bd.match_rate_required == 0.5
    assert bd.match_rate_preferred == 0.5


def test_skills_score_case_insensitivity():
    """Verify skill matching is case-insensitive and trims whitespace."""
    engine = ScoringEngine()
    cand = ["  python  ", "Postgresql", "DOCKER "]
    req = ["Python", "PostgreSQL"]

    score, bd = engine.calculate_skills_score(cand, req)
    assert score == 100.0
    assert bd.matched_required == ["PostgreSQL", "Python"]
    assert bd.missing_critical == []


def test_skills_score_preferred_subset_deduplication():
    """Verify skills listed in both required and preferred are not counted twice."""
    engine = ScoringEngine()
    cand = ["Python"]
    req = ["Python"]
    pref = ["Python", "Docker"]  # Python is redundant

    score, bd = engine.calculate_skills_score(cand, req, pref)
    # pref becomes only ["Docker"] -> 0 of 1 matched
    # score = 0.75 * 100 + 0.25 * 0 = 75.0
    assert score == 75.0
    assert bd.matched_required == ["Python"]
    assert bd.matched_preferred == []
    assert bd.missing_preferred == ["Docker"]


def test_skills_score_empty_job_requirements():
    """Verify job with no skills returns 0.0 rather than fake 100%."""
    engine = ScoringEngine()
    score, bd = engine.calculate_skills_score(
        candidate_skills=["Python", "Go"],
        required_skills=[],
        preferred_skills=[],
    )
    assert score == 0.0
    assert bd.matched_required == []


# ---------------------------------------------------------------------------
# 6. Experience Score & Edge Cases
# ---------------------------------------------------------------------------

def test_experience_score_under_qualification_curve():
    """Verify non-linear 1.2 penalty curve for experience gaps."""
    engine = ScoringEngine()

    # Half required experience: (2.5 / 5.0)^1.2 * 100 = 43.53
    s1, bd1 = engine.calculate_experience_score(candidate_years=2.5, required_years=5.0)
    assert math.isclose(s1, 43.53, abs_tol=0.1)
    assert bd1.status == "BELOW_REQUIREMENT"
    assert bd1.delta_years == -2.5

    # 4 of 5 years: (4.0 / 5.0)^1.2 * 100 = (0.8)^1.2 * 100 = 76.51
    s2, bd2 = engine.calculate_experience_score(candidate_years=4.0, required_years=5.0)
    assert math.isclose(s2, 76.51, abs_tol=0.1)


def test_experience_score_zero_years_floors():
    """Verify candidate with 0 years receives 40% if req <= 1.0, or 10% if req > 1.0."""
    engine = ScoringEngine()

    # req <= 1.0 -> 40.0
    s_entry, bd_entry = engine.calculate_experience_score(candidate_years=0.0, required_years=1.0)
    assert s_entry == 40.0
    assert bd_entry.status == "BELOW_REQUIREMENT"

    # req > 1.0 -> 10.0
    s_mid, bd_mid = engine.calculate_experience_score(candidate_years=0.0, required_years=3.0)
    assert s_mid == 10.0
    assert bd_mid.status == "BELOW_REQUIREMENT"


def test_experience_score_missing_and_zero_requirements():
    """Verify missing/0 required years treats any candidate as meeting requirements."""
    engine = ScoringEngine()

    # No experience required
    s, bd = engine.calculate_experience_score(candidate_years=3.0, required_years=0.0)
    assert s == 100.0
    assert bd.status == "MEETS_REQUIREMENT"

    # Missing candidate years defaults to 0.0
    s_none, bd_none = engine.calculate_experience_score(candidate_years=None, required_years=2.0)
    assert s_none == 10.0
    assert bd_none.candidate_years == 0.0


def test_experience_validation_errors():
    """Verify negative and non-finite experience values raise InvalidInputError."""
    engine = ScoringEngine()

    with pytest.raises(InvalidInputError, match="cannot be negative"):
        engine.calculate_experience_score(candidate_years=-2.0, required_years=5.0)

    with pytest.raises(InvalidInputError, match="cannot be negative"):
        engine.calculate_experience_score(candidate_years=2.0, required_years=-1.0)

    with pytest.raises(InvalidInputError, match="must be a finite number"):
        engine.calculate_experience_score(candidate_years=float("inf"), required_years=5.0)


# ---------------------------------------------------------------------------
# 7. Education Hierarchy & Matching Tests
# ---------------------------------------------------------------------------

def test_education_hierarchy_parsing():
    """Verify degree string mapping to ordinal ranks."""
    engine = ScoringEngine()

    assert engine.parse_education_level("Ph.D. in Computer Science") == (5, "Doctorate")
    assert engine.parse_education_level("Master of Science in Software Engineering") == (4, "Master's")
    assert engine.parse_education_level("Bachelor of Arts") == (3, "Bachelor's")
    assert engine.parse_education_level("B.S.") == (3, "Bachelor's")
    assert engine.parse_education_level("Associate Degree") == (2, "Associate")
    assert engine.parse_education_level("High School Diploma") == (1, "High School")
    assert engine.parse_education_level("Unspecified") == (0, "Unspecified")
    assert engine.parse_education_level(None) == (0, "Unspecified")
    assert engine.parse_education_level(4) == (4, "Master's")


def test_education_scoring_step_penalties():
    """
    Verify education ordinal step scoring:
    - Rc >= Rr: 100.0
    - Rc == Rr - 1: 85.0
    - Rc == Rr - 2: 60.0
    - Rc < Rr - 2: 30.0
    - Rr == 0: 100.0
    """
    engine = ScoringEngine()

    # Rc >= Rr (Doctorate for Master's role)
    s1, bd1 = engine.calculate_education_score(candidate_level=5, required_level=4)
    assert s1 == 100.0
    assert bd1.status == "FULLY_ALIGNED"

    # Rc == Rr - 1 (Bachelor's for Master's role)
    s2, bd2 = engine.calculate_education_score(candidate_level=3, required_level=4)
    assert s2 == 85.0
    assert bd2.status == "PARTIALLY_ALIGNED"

    # Rc == Rr - 2 (Associate for Master's role)
    s3, bd3 = engine.calculate_education_score(candidate_level=2, required_level=4)
    assert s3 == 60.0
    assert bd3.status == "BELOW_REQUIREMENT"

    # Rc < Rr - 2 (High school for Master's role)
    s4, bd4 = engine.calculate_education_score(candidate_level=1, required_level=4)
    assert s4 == 30.0
    assert bd4.status == "BELOW_REQUIREMENT"

    # No requirement (Rr = 0)
    s5, bd5 = engine.calculate_education_score(candidate_level=0, required_level=0)
    assert s5 == 100.0
    assert bd5.status == "FULLY_ALIGNED"


def test_education_validation_errors():
    """Verify invalid integer ranks raise InvalidInputError."""
    engine = ScoringEngine()

    with pytest.raises(InvalidInputError, match="must be between 0 and 5"):
        engine.parse_education_level(6)

    with pytest.raises(InvalidInputError, match="must be between 0 and 5"):
        engine.parse_education_level(-1)


# ---------------------------------------------------------------------------
# 8. Explainability, Zero Fabrication & Canonical Field Names
# ---------------------------------------------------------------------------

def test_canonical_contract_field_names():
    """Verify MatchResult uses strictly the required canonical field names."""
    engine = ScoringEngine()
    res = engine.compute_match(
        candidate_skills=["Python", "Docker"],
        required_skills=["Python", "Kubernetes"],
        candidate_years=4.0,
        required_years=3.0,
        candidate_education="Bachelor's",
        required_education="Bachelor's",
        raw_cosine_similarity=0.75,
    )

    data = res.model_dump()
    # Canonical field names check
    assert "skills_breakdown" in data
    assert "experience_breakdown" in data
    assert "education_breakdown" in data
    assert "explanation" in data

    # Prohibited field names check
    assert "skills_analysis" not in data
    assert "structured_requirements" not in data
    assert "explanation_narrative" not in data


def test_explanation_contains_zero_fabrications():
    """
    Verify explanation contains only factual evidence derived from inputs,
    referencing actual matched/missing skills, exact years delta, and degrees.
    """
    engine = ScoringEngine()
    res = engine.compute_match(
        candidate_skills=["Python", "FastAPI"],
        required_skills=["Python", "FastAPI", "Terraform"],
        preferred_skills=["AWS"],
        candidate_years=6.0,
        required_years=5.0,
        candidate_education="Bachelor's",
        required_education="Master's",
        raw_cosine_similarity=0.70,
    )

    expl = res.explanation
    combined_text = " ".join(expl.key_strengths + expl.growth_areas + expl.recommendations)

    # 1. Factually matched skills appear
    assert "Python" in combined_text or "FastAPI" in combined_text

    # 2. Factually missing skills appear
    assert "Terraform" in combined_text

    # 3. Verified years appear
    assert "6.0" in combined_text and "5.0" in combined_text

    # 4. Verified degree levels appear
    assert "Master's" in combined_text and "Bachelor's" in combined_text

    # 5. Fabricated skills do NOT appear
    assert "Kubernetes" not in combined_text
    assert "C++" not in combined_text
    assert "Doctorate" not in combined_text


def test_db_record_mapping():
    """Verify to_db_record matches PostgreSQL matches table schema."""
    engine = ScoringEngine()
    res = engine.compute_match(
        candidate_skills=["Python"],
        required_skills=["Python"],
        candidate_years=3.0,
        required_years=3.0,
        candidate_education="Bachelor's",
        required_education="Bachelor's",
        raw_cosine_similarity=0.85,
    )

    record = res.to_db_record()
    assert "overall_score" in record
    assert "semantic_score" in record
    assert "skills_score" in record
    assert "experience_score" in record
    assert "education_score" in record
    assert "breakdown" in record
    assert "explanation" in record

    # Breakdown sub-keys
    assert "skills_breakdown" in record["breakdown"]
    assert "experience_breakdown" in record["breakdown"]
    assert "education_breakdown" in record["breakdown"]


# ---------------------------------------------------------------------------
# 9. Deterministic Reproducibility
# ---------------------------------------------------------------------------

def test_deterministic_reproducibility():
    """Verify repeated runs on identical inputs yield 100% identical outputs."""
    engine = ScoringEngine()

    args = {
        "candidate_skills": ["Python", "Docker", "SQL", "Git"],
        "required_skills": ["Python", "SQL", "Kubernetes"],
        "preferred_skills": ["Docker", "AWS"],
        "candidate_years": 4.5,
        "required_years": 4.0,
        "candidate_education": "Bachelor's",
        "required_education": "Master's",
        "raw_cosine_similarity": 0.72,
    }

    first = engine.compute_match(**args).model_dump()
    for _ in range(25):
        current = engine.compute_match(**args).model_dump()
        assert first == current
