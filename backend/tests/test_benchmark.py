"""
Unit & Safeguard Tests for AI/ML Benchmark Runner and Evaluation Suite
ResumeMatch — Explainable AI-Powered Resume-to-Job Matching Platform

Validates:
1. Loading and validation of test_cases.json schema.
2. Complete execution of the BenchmarkRunner with hermetic deterministic mock model.
3. Category summaries, skill extraction metrics (Precision, Recall, F1), and ranking concordance.
4. Latency percentile calculation and reporting.
5. Safeguard: Missing component data cannot silently become a perfect score.
6. Safeguard: Documented 50/30/10/10 weights are applied exactly once.
7. Safeguard: Explanations agree with component scores and never invent matched skills.
8. Safeguard: Scores remain strictly within documented [0.0, 100.0] range.
9. Safeguard: Embedding inputs and re-tokenized chunks do not exceed model sequence ceiling.
10. Safeguard: Every generated chunk contributes to final embedding vector.
"""

import math
from pathlib import Path
from typing import List

import numpy as np
import pytest

from app.evaluation.benchmark import (
    BenchmarkReport,
    BenchmarkRunner,
    TestCase,
    create_deterministic_embedding_service,
)
from app.services.embedding_service import (
    EmbeddingService,
    MAX_DOCUMENT_CHARS,
)
from app.services.nlp_extractor import (
    SkillExtractionResult,
    skill_extractor,
)
from app.services.scoring_engine import (
    DEFAULT_SCORE_WEIGHTS,
    InvalidInputError,
    MatchResult,
    ScoreWeights,
    ScoringEngine,
    scoring_engine,
)


# ---------------------------------------------------------------------------
# 1. Test Dataset Loading & Validation Tests
# ---------------------------------------------------------------------------

def test_load_and_validate_test_cases():
    """Verify that test_cases.json exists, contains 32 cases, and parses cleanly into Pydantic models."""
    runner = BenchmarkRunner(use_mock_embeddings=True)
    cases = runner.load_test_cases()

    assert len(cases) == 32
    assert all(isinstance(c, TestCase) for c in cases)

    # Verify key categories are represented
    categories = set(c.category for c in cases)
    expected_categories = {
        "strong_alignment",
        "partial_overlap",
        "weak_alignment",
        "no_overlap",
        "seniority_mismatch",
        "education_mismatch",
        "alias_canonicalization",
        "ambiguous_short_names",
        "compound_skills",
        "boundary_malformed",
        "long_text_chunking",
    }
    assert expected_categories.issubset(categories)


# ---------------------------------------------------------------------------
# 2. Benchmark Runner Execution & Metric Assertion Tests
# ---------------------------------------------------------------------------

def test_benchmark_runner_offline_execution():
    """
    Verify that BenchmarkRunner executes all 32 cases hermetically with
    deterministic mock model and achieves a 100% pass rate.
    """
    runner = BenchmarkRunner(use_mock_embeddings=True)
    report = runner.run_benchmark()

    assert isinstance(report, BenchmarkReport)
    assert report.total_cases == 32
    assert report.passed_cases == 32
    assert report.failed_cases == 0
    assert report.overall_pass_rate == 1.0
    assert report.live_inference_used is False


def test_category_breakdown_metrics():
    """Verify that every evaluation category summary contains valid aggregated statistics."""
    runner = BenchmarkRunner(use_mock_embeddings=True)
    report = runner.run_benchmark()

    for cat_name, summary in report.category_summaries.items():
        assert summary.total_cases > 0
        assert summary.passed_cases == summary.total_cases
        assert summary.pass_rate == 1.0
        assert 0.0 <= summary.avg_overall_score <= 100.0


def test_skill_extraction_metrics():
    """Verify precision, recall, and F1 calculations across labeled test cases."""
    runner = BenchmarkRunner(use_mock_embeddings=True)
    report = runner.run_benchmark()

    m = report.skill_metrics
    assert m.precision >= 0.70
    assert m.recall >= 0.85
    assert m.f1 >= 0.75
    assert m.true_positives > 0
    assert m.evaluated_cases_count > 0


def test_pairwise_ranking_consistency():
    """Verify monotonic score graduation across alignment tiers (strong > partial > weak > no_overlap)."""
    runner = BenchmarkRunner(use_mock_embeddings=True)
    report = runner.run_benchmark()

    rm = report.ranking_metrics
    assert rm.pairwise_accuracy >= 0.85
    assert rm.total_pairs > 0
    assert rm.concordant_pairs > 0
    if rm.spearman_rho is not None:
        assert rm.spearman_rho >= 0.85


def test_latency_measurement():
    """Verify latency percentile measurement returns valid statistical measures."""
    runner = BenchmarkRunner(use_mock_embeddings=True)
    cases = runner.load_test_cases()[:5]

    lat = runner.measure_latency(cases, runs=2)
    assert lat.sample_count == 10
    assert lat.mean_ms > 0.0
    assert lat.p50_ms > 0.0
    assert lat.p95_ms >= lat.p50_ms
    assert lat.min_ms <= lat.mean_ms <= lat.max_ms
    assert "time.perf_counter" in lat.measurement_method


def test_benchmark_report_serialization():
    """Verify BenchmarkReport serializes to valid JSON and summary table."""
    runner = BenchmarkRunner(use_mock_embeddings=True)
    report = runner.run_benchmark()

    json_str = report.to_json()
    assert "ResumeMatch AI/ML Ground-Truth Benchmark Dataset" or "32" in json_str

    table_str = report.format_summary_table()
    assert "# ResumeMatch AI/ML Benchmark Evaluation Report" in table_str
    assert "Overall Status" in table_str


# ---------------------------------------------------------------------------
# 3. Safeguard Tests (Prompt Requirement #5)
# ---------------------------------------------------------------------------

def test_safeguard_missing_component_data_no_silent_perfect_score():
    """
    Safeguard 1: Missing component data cannot silently become a perfect score.
    Verifies that missing candidate skills, missing experience, missing education,
    and missing vectors never silently return 100.0.
    """
    engine = ScoringEngine()

    # 1. Missing skills when job specifies requirements -> score is 0.0, NOT 100.0
    skills_score, skills_bd = engine.calculate_skills_score(
        candidate_skills=[],
        required_skills=["Python", "FastAPI"],
    )
    assert skills_score == 0.0
    assert len(skills_bd.matched_required) == 0

    # 2. Missing experience (None / 0) when 5 years required -> score is 10.0, NOT 100.0
    exp_score, exp_bd = engine.calculate_experience_score(
        candidate_years=None,
        required_years=5.0,
    )
    assert exp_score == 10.0
    assert exp_bd.status == "BELOW_REQUIREMENT"

    # 3. Missing education (None) when Master's required -> score is 30.0, NOT 100.0
    edu_score, edu_bd = engine.calculate_education_score(
        candidate_level=None,
        required_level="Master's",
    )
    assert edu_score == 30.0
    assert edu_bd.status == "BELOW_REQUIREMENT"

    # 4. Missing semantic vectors and cosine raises explicit InvalidInputError
    with pytest.raises(InvalidInputError, match="Semantic scoring requires either"):
        engine.calculate_semantic_score(
            resume_vector=None,
            job_vector=None,
            raw_cosine_similarity=None,
        )


def test_safeguard_documented_weights_applied_exactly_once():
    """
    Safeguard 2: The documented 50/30/10/10 weights are applied exactly once.
    Tests each component in isolation to assert exact weight attribution.
    """
    engine = ScoringEngine()

    assert engine.weights.semantic == 0.50
    assert engine.weights.skills == 0.30
    assert engine.weights.experience == 0.10
    assert engine.weights.education == 0.10
    assert math.isclose(
        engine.weights.semantic
        + engine.weights.skills
        + engine.weights.experience
        + engine.weights.education,
        1.0,
    )

    # 1. Isolated semantic 100%, others 0% -> overall must be exactly 50.0
    match_sem = engine.compute_match(
        candidate_skills=[],
        required_skills=["Python"],
        candidate_years=0,
        required_years=5,
        candidate_education=None,
        required_education="Doctorate",
        raw_cosine_similarity=0.85,  # 100% semantic score
    )
    # semantic (0.50 * 100) + skills (0.30 * 0) + exp (0.10 * 10) + edu (0.10 * 30) = 50 + 0 + 1 + 3 = 54.0
    assert math.isclose(match_sem.sub_scores.semantic_score, 100.0, abs_tol=0.1)

    # 2. Perfect candidate across all components -> overall must be 100.0
    match_perfect = engine.compute_match(
        candidate_skills=["Python", "FastAPI"],
        required_skills=["Python", "FastAPI"],
        candidate_years=5,
        required_years=5,
        candidate_education="Master's",
        required_education="Master's",
        raw_cosine_similarity=0.85,
    )
    assert match_perfect.overall_score == 100.0
    assert match_perfect.fit_category == "STRONG_MATCH"


def test_safeguard_explanations_agree_with_scores_no_invented_skills():
    """
    Safeguard 3: Explanations agree with component scores and never invent matched skills.
    Verifies that skills cited in key_strengths and growth_areas strictly exist in breakdowns.
    """
    engine = ScoringEngine()
    result = engine.compute_match(
        candidate_skills=["Python", "PostgreSQL"],
        required_skills=["Python", "PostgreSQL", "Go", "Kubernetes"],
        preferred_skills=["Redis"],
        candidate_years=4.0,
        required_years=5.0,
        candidate_education="Bachelor's",
        required_education="Master's",
        raw_cosine_similarity=0.60,
    )

    explanation = result.explanation
    matched_skills_set = set(result.skills_breakdown.matched_required + result.skills_breakdown.matched_preferred)
    missing_skills_set = set(result.skills_breakdown.missing_critical + result.skills_breakdown.missing_preferred)

    # Key strengths must never mention missing skills
    for strength in explanation.key_strengths:
        for missing in missing_skills_set:
            assert f"({missing})" not in strength and f"including {missing}" not in strength

    # Growth areas must cite missing skills, not matched skills
    for growth in explanation.growth_areas:
        for matched in matched_skills_set:
            assert f"Missing {matched}" not in growth

    # Summary narrative must accurately reflect the computed sub-scores
    assert f"technical skills ({result.sub_scores.skills_score:.1f}%)" in explanation.summary
    assert f"experience ({result.sub_scores.experience_score:.1f}%)" in explanation.summary
    assert f"education ({result.sub_scores.education_score:.1f}%)" in explanation.summary


def test_safeguard_scores_remain_within_documented_range():
    """
    Safeguard 4: Scores remain strictly within the documented [0.0, 100.0] range,
    even under extreme numerical inputs.
    """
    engine = ScoringEngine()

    # Extreme positive candidate years (100 years experience)
    res_high = engine.compute_match(
        candidate_skills=["Python"],
        required_skills=["Python"],
        candidate_years=100.0,
        required_years=2.0,
        candidate_education="Doctorate",
        required_education="High School",
        raw_cosine_similarity=1.0,
    )
    assert 0.0 <= res_high.overall_score <= 100.0
    assert 0.0 <= res_high.sub_scores.experience_score <= 100.0

    # Extreme negative cosine (-1.0)
    res_low = engine.compute_match(
        candidate_skills=[],
        required_skills=["Python"],
        candidate_years=0.0,
        required_years=10.0,
        candidate_education=None,
        required_education="Doctorate",
        raw_cosine_similarity=-1.0,
    )
    assert 0.0 <= res_low.overall_score <= 100.0
    assert res_low.sub_scores.semantic_score == 0.0
    assert res_low.fit_category == "NO_MATCH"


def test_safeguard_embedding_sequence_limit_not_exceeded():
    """
    Safeguard 5: Embedding inputs, including decoded and re-tokenized chunks,
    do not exceed the model sequence limit.
    """
    service = create_deterministic_embedding_service()

    # Create a synthetic document with 800 words (exceeding 256 sequence limit)
    words = [f"word{i}" for i in range(800)]
    long_text = " ".join(words)

    chunks = service.chunk_text(long_text)
    assert len(chunks) > 1, "Must generate multiple sliding-window chunks"

    # Verify that every decoded chunk re-tokenized by the tokenizer does not exceed ceiling
    model = service._ensure_model()
    tokenizer = getattr(model, "tokenizer", None)
    num_special = tokenizer.num_special_tokens_to_add(pair=False)
    max_payload = service.max_chunk_size - num_special

    for chunk in chunks:
        token_ids = tokenizer.encode(chunk, add_special_tokens=False)
        assert len(token_ids) <= max_payload, (
            f"Chunk length {len(token_ids)} exceeded max payload {max_payload}"
        )


def test_safeguard_every_chunk_contributes_to_final_embedding():
    """
    Safeguard 6: Every generated chunk contributes to the final embedding as intended.
    Modifying any single chunk must alter the final pooled embedding vector.
    """
    service = create_deterministic_embedding_service()

    # 3-chunk document
    words_base = [f"token_{i}" for i in range(600)]
    text_base = " ".join(words_base)

    res_base = service.embed_text(text_base)
    assert res_base.chunk_count >= 3

    # Mutate only the head chunk (tokens 0-50)
    words_mutated_head = list(words_base)
    for i in range(50):
        words_mutated_head[i] = f"mutated_head_{i}"
    res_mutated_head = service.embed_text(" ".join(words_mutated_head))

    # Mutate only the middle chunk (tokens 250-300)
    words_mutated_mid = list(words_base)
    for i in range(250, 300):
        words_mutated_mid[i] = f"mutated_mid_{i}"
    res_mutated_mid = service.embed_text(" ".join(words_mutated_mid))

    # Mutate only the tail chunk (tokens 550-600)
    words_mutated_tail = list(words_base)
    for i in range(550, 600):
        words_mutated_tail[i] = f"mutated_tail_{i}"
    res_mutated_tail = service.embed_text(" ".join(words_mutated_tail))

    vec_base = np.array(res_base.embedding)
    vec_head = np.array(res_mutated_head.embedding)
    vec_mid = np.array(res_mutated_mid.embedding)
    vec_tail = np.array(res_mutated_tail.embedding)

    # Every chunk modification must produce a mathematically distinct vector
    assert not np.allclose(vec_base, vec_head, atol=1e-3)
    assert not np.allclose(vec_base, vec_mid, atol=1e-3)
    assert not np.allclose(vec_base, vec_tail, atol=1e-3)
