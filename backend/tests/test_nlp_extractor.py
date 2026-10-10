"""
Unit & Integration Tests for Skill Taxonomy and NLP Skill Extractor
ResumeMatch — Explainable AI-Powered Resume-to-Job Matching Platform

Validates:
1. Taxonomy catalog loading, size invariants (>= 1,200), and categories.
2. Canonical skill matches.
3. Alias-to-canonical resolution.
4. Case-insensitivity for standard skills.
5. Punctuation-sensitive technical tokens (C++, C#, .NET, Node.js, CI/CD).
6. Word-boundary false positive prevention (C in cloud, Go in good, .NET in internet).
7. Case-sensitive matching overrides for short/ambiguous tokens (C, Go, R).
8. Duplicate mention deduplication and frequency count aggregation.
9. Empty inputs and text with zero recognized skills.
10. Realistic synthetic resume extraction and category grouping.
11. Job description requirements vs. preferred skill classification.
12. Unicode and multiline text handling.
13. Seamless integration with PDF parser output (PDFParseResult).
14. Idempotent database seeding into PostgreSQL skill_taxonomy table.
"""

import io
from typing import AsyncGenerator
import pytest
import pytest_asyncio
import pymupdf
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.models.taxonomy import SkillTaxonomy
from app.services.pdf_parser import extract_text_from_pdf
from app.services.taxonomy_service import TaxonomyService, taxonomy_service
from app.services.nlp_extractor import (
    SkillExtractor,
    skill_extractor,
)


# ---------------------------------------------------------------------------
# Test Helpers & Database Fixture (Strictly using resumematch_test)
# ---------------------------------------------------------------------------

def create_synthetic_pdf(text_content: str) -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((50, 72), text_content)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


@pytest_asyncio.fixture
async def test_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provides an isolated session strictly connected to resumematch_test."""
    test_url = settings.get_test_database_url()
    assert "resumematch_test" in test_url, "Must connect strictly to test database"
    engine = create_async_engine(test_url, poolclass=NullPool)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)

    async with session_factory() as session:
        yield session
        await session.rollback()

    # Clean up test rows
    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE TABLE resume_skills, job_skills, skill_taxonomy CASCADE;"))
    await engine.dispose()


# ---------------------------------------------------------------------------
# 1. Taxonomy Catalog Tests
# ---------------------------------------------------------------------------

def test_taxonomy_catalog_size_and_metadata():
    """Verify that taxonomy contains at least 1,200 curated skills across 12 categories."""
    assert taxonomy_service.total_skills >= 1200, f"Expected >= 1200 skills, got {taxonomy_service.total_skills}"
    assert taxonomy_service.metadata is not None
    assert len(taxonomy_service.metadata.categories) == 12

    # Verify key canonical skills exist
    assert taxonomy_service.get_by_canonical_name("Python") is not None
    assert taxonomy_service.get_by_canonical_name("PostgreSQL") is not None
    assert taxonomy_service.get_by_canonical_name("C++") is not None
    assert taxonomy_service.get_by_canonical_name("Docker") is not None
    assert taxonomy_service.get_by_canonical_name("Kubernetes") is not None


def test_taxonomy_alias_resolution():
    """Verify alias mapping correctly resolves to canonical names."""
    assert taxonomy_service.resolve_alias("postgres") == "PostgreSQL"
    assert taxonomy_service.resolve_alias("k8s") == "Kubernetes"
    assert taxonomy_service.resolve_alias("golang") == "Go"
    assert taxonomy_service.resolve_alias("js") == "JavaScript"
    assert taxonomy_service.resolve_alias("sklearn") == "scikit-learn"


# ---------------------------------------------------------------------------
# 2. NLP Extractor Core Matching Tests
# ---------------------------------------------------------------------------

def test_canonical_skill_matches():
    """Verify basic canonical skill extraction."""
    text_sample = "Experienced software engineer specializing in Python and PostgreSQL."
    result = skill_extractor.extract_skills(text_sample)

    assert result.has_skills is True
    assert "Python" in result.canonical_skills
    assert "PostgreSQL" in result.canonical_skills
    assert result.total_unique_skills == 2


def test_alias_to_canonical_mapping():
    """Verify that aliases are mapped to canonical names."""
    text_sample = "Building microservices using golang, k8s, and postgres."
    result = skill_extractor.extract_skills(text_sample)

    assert "Go" in result.canonical_skills
    assert "Kubernetes" in result.canonical_skills
    assert "PostgreSQL" in result.canonical_skills

    # Inspect matched terms metadata
    go_skill = next(s for s in result.skills if s.canonical_name == "Go")
    assert "golang" in go_skill.matched_terms


def test_case_insensitive_matching_for_standard_skills():
    """Verify case-insensitivity for non-ambiguous skills."""
    text_sample = "Proficient in DOCKER, fastAPI, and pytorch."
    result = skill_extractor.extract_skills(text_sample)

    assert "Docker" in result.canonical_skills
    assert "FastAPI" in result.canonical_skills
    assert "PyTorch" in result.canonical_skills


def test_punctuation_and_technical_tokens():
    """Verify technical tokens with symbols (+, #, ., -, /) are extracted accurately."""
    text_sample = "Full-stack developer with C++, C#, .NET Core, Node.js, and CI/CD automation."
    result = skill_extractor.extract_skills(text_sample)

    assert "C++" in result.canonical_skills
    assert "C#" in result.canonical_skills
    assert ".NET Core" in result.canonical_skills
    assert "Node.js" in result.canonical_skills
    assert "CI/CD" in result.canonical_skills


def test_word_boundary_false_positive_prevention():
    """Verify that short skills do not match substrings inside common words."""
    # 'C' in cloud / create; 'Go' in good / going; '.NET' in internet; 'Python' in cpython
    text_sample = "The cloud architect is going to create good software by browsing the internet with cpython."
    result = skill_extractor.extract_skills(text_sample)

    assert "C" not in result.canonical_skills
    assert "Go" not in result.canonical_skills
    assert ".NET Core" not in result.canonical_skills
    assert "Python" not in result.canonical_skills


def test_case_sensitive_acronym_overrides():
    """Verify case-sensitive matching for single-letter and common-word skills (C, Go, R)."""
    # 1. Real mentions
    valid_text = "Primary languages include C, Go, and R for analytics."
    result_valid = skill_extractor.extract_skills(valid_text)
    assert "C" in result_valid.canonical_skills
    assert "Go" in result_valid.canonical_skills
    assert "R" in result_valid.canonical_skills

    # 2. Lowercase ordinary English words
    false_text = "Let us go to the store and read section c or look for r."
    result_false = skill_extractor.extract_skills(false_text)
    assert "Go" not in result_false.canonical_skills
    assert "C" not in result_false.canonical_skills
    assert "R" not in result_false.canonical_skills


def test_duplicate_mention_deduplication():
    """Verify repeated mentions are aggregated under a single canonical entry with correct counts."""
    text_sample = (
        "Python is my main language. I have 5 years of Python experience, "
        "and I frequently contribute to python3 open-source projects."
    )
    result = skill_extractor.extract_skills(text_sample)

    assert "Python" in result.canonical_skills
    python_entry = next(s for s in result.skills if s.canonical_name == "Python")
    assert python_entry.count == 3
    assert "Python" in python_entry.matched_terms
    assert "python3" in python_entry.matched_terms
    assert len(python_entry.evidence_snippets) >= 1


def test_empty_input_and_no_skills_text():
    """Verify proper behavior when no skills exist or input is empty."""
    # 1. Empty string
    empty_result = skill_extractor.extract_skills("")
    assert empty_result.has_skills is False
    assert empty_result.total_unique_skills == 0
    assert empty_result.canonical_skills == []

    # 2. English text with zero tech skills
    no_skills_text = "The quick brown fox jumps over the lazy dog."
    no_skill_result = skill_extractor.extract_skills(no_skills_text)
    assert no_skill_result.has_skills is False
    assert no_skill_result.total_unique_skills == 0


def test_realistic_synthetic_resume_extraction():
    """Verify multi-section synthetic resume extraction and category grouping."""
    synthetic_resume = """
    Jane Doe | Senior Backend Engineer | New York, NY
    
    PROFESSIONAL SUMMARY
    Backend engineer with 6+ years designing scalable distributed systems in Python, Go, and Java.
    
    TECHNICAL SKILLS
    - Languages: Python, Go, Java, TypeScript
    - Frameworks & APIs: FastAPI, Django, Spring Boot, GraphQL, gRPC
    - Databases: PostgreSQL, Redis, MongoDB, pgvector
    - Cloud & DevOps: AWS, Docker, Kubernetes, Terraform, GitHub Actions
    - Architecture: Microservices Architecture, Event-Driven Architecture, Kafka
    
    EXPERIENCE
    Staff Software Engineer at Acme Cloud (2021 - Present)
    - Architected real-time streaming pipelines using Apache Kafka and Redis.
    - Containerized legacy applications using Docker and deployed on Kubernetes clusters.
    """
    result = skill_extractor.extract_skills(synthetic_resume)

    assert result.has_skills is True
    assert result.total_unique_skills >= 15

    expected_skills = [
        "Python", "Go", "Java", "TypeScript", "FastAPI", "Django", "Spring Boot",
        "GraphQL", "gRPC", "PostgreSQL", "Redis", "MongoDB", "AWS", "Docker",
        "Kubernetes", "Terraform", "GitHub Actions", "Apache Kafka"
    ]
    for skill in expected_skills:
        assert skill in result.canonical_skills, f"Expected skill '{skill}' was not extracted"

    # Category grouping
    assert "Databases & Storage" in result.by_category
    assert "PostgreSQL" in result.by_category["Databases & Storage"]
    assert "Cloud & Infrastructure" in result.by_category
    assert "AWS" in result.by_category["Cloud & Infrastructure"]


def test_job_description_required_vs_preferred_classification():
    """Verify job description requirement classification into required vs preferred skills."""
    synthetic_job = """
    Job Title: Senior Backend Developer
    Company: Tech Innovations Inc.
    
    Requirements:
    - 5+ years of experience with Python and FastAPI
    - Strong database background in PostgreSQL and Redis
    - Hands-on experience with Docker and Linux
    
    Preferred Qualifications:
    - Experience with Kubernetes and Terraform is a major plus
    - Familiarity with AWS and Apache Kafka
    - Knowledge of GraphQL and TypeScript
    """
    job_result = skill_extractor.extract_skills_from_job(synthetic_job)

    assert "Python" in job_result.required_skills
    assert "FastAPI" in job_result.required_skills
    assert "PostgreSQL" in job_result.required_skills
    assert "Redis" in job_result.required_skills
    assert "Docker" in job_result.required_skills

    assert "Kubernetes" in job_result.preferred_skills
    assert "Terraform" in job_result.preferred_skills
    assert "Apache Kafka" in job_result.preferred_skills

    # No overlap between required and preferred
    overlap = set(job_result.required_skills).intersection(set(job_result.preferred_skills))
    assert len(overlap) == 0


def test_unicode_and_multiline_handling():
    """Verify that non-English accents and international formatting are parsed cleanly."""
    unicode_resume = (
        "Candidat: François Müller\n"
        "Compétences Clés: Vue.js, Django, PostgreSQL, Scikit-learn, PyTorch\n"
        "Spécialisation: Architecture de Microservices et Conteneurs Docker."
    )
    result = skill_extractor.extract_skills(unicode_resume)

    assert "Vue.js" in result.canonical_skills
    assert "Django" in result.canonical_skills
    assert "PostgreSQL" in result.canonical_skills
    assert "scikit-learn" in result.canonical_skills
    assert "PyTorch" in result.canonical_skills
    assert "Docker" in result.canonical_skills


def test_integration_with_pdf_parser_output():
    """Verify end-to-end integration: PDF bytes -> extract_text_from_pdf -> extract_skills_from_resume."""
    pdf_text = "John Smith | Software Developer\nSkills: Python, React, AWS, Docker, PostgreSQL."
    pdf_bytes = create_synthetic_pdf(pdf_text)

    # 1. Parse PDF
    pdf_result = extract_text_from_pdf(pdf_bytes)
    assert pdf_result.has_extractable_text is True

    # 2. Extract skills from PDF result
    skill_result = skill_extractor.extract_skills_from_resume(pdf_result)
    assert skill_result.has_skills is True
    assert "Python" in skill_result.canonical_skills
    assert "React" in skill_result.canonical_skills
    assert "AWS" in skill_result.canonical_skills
    assert "Docker" in skill_result.canonical_skills
    assert "PostgreSQL" in skill_result.canonical_skills


# ---------------------------------------------------------------------------
# 3. Database Seeding Idempotency Tests (Isolated on resumematch_test)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_idempotent_taxonomy_database_seeding(test_db_session: AsyncSession):
    """
    Verify that seeding the database from TaxonomyService inserts all skills
    and runs idempotently on subsequent calls without constraint errors.
    """
    # First seed
    count_1 = await taxonomy_service.seed_database(test_db_session)
    assert count_1 >= 1200

    # Query database to confirm persisted records
    res = await test_db_session.execute(select(SkillTaxonomy))
    rows = res.scalars().all()
    assert len(rows) == taxonomy_service.total_skills

    # Second seed (idempotent run)
    count_2 = await taxonomy_service.seed_database(test_db_session)
    # Zero modifications should be needed on an unmodified catalog
    assert count_2 == 0

    # Total row count must remain unchanged
    res_after = await test_db_session.execute(select(SkillTaxonomy))
    rows_after = res_after.scalars().all()
    assert len(rows_after) == len(rows)


# ---------------------------------------------------------------------------
# 4. Task 3.1 Regression Tests: Disambiguation, Overlaps, Counts & Boundaries
# ---------------------------------------------------------------------------

def test_disambiguation_go_r_c_move_technical_vs_ordinary():
    """
    Verify single-letter and ordinary-word skill names (Go, R, C, Move, D)
    are extracted in valid technical contexts and rejected in ordinary English.
    """
    # 1. Technical Contexts
    tech_text_1 = "Senior Go and Move developer building decentralized smart contracts on Aptos."
    res_tech_1 = skill_extractor.extract_skills(tech_text_1)
    assert "Go" in res_tech_1.canonical_skills
    assert "Move" in res_tech_1.canonical_skills

    tech_text_2 = "Proficient in C, C++, and R for high-performance statistical modeling."
    res_tech_2 = skill_extractor.extract_skills(tech_text_2)
    assert "C" in res_tech_2.canonical_skills
    assert "C++" in res_tech_2.canonical_skills
    assert "R" in res_tech_2.canonical_skills

    # 2. Ordinary Language Contexts (False Positives Must Be Blocked)
    ordinary_text_1 = "Go ahead and apply. Move to our team in New York."
    res_ord_1 = skill_extractor.extract_skills(ordinary_text_1)
    assert "Go" not in res_ord_1.canonical_skills
    assert "Move" not in res_ord_1.canonical_skills

    ordinary_text_2 = "The CEO is a C level executive in R&D."
    res_ord_2 = skill_extractor.extract_skills(ordinary_text_2)
    assert "C" not in res_ord_2.canonical_skills
    assert "R" not in res_ord_2.canonical_skills
    assert "D" not in res_ord_2.canonical_skills

    ordinary_text_3 = "Let us go forward, make a move, and read Appendix C."
    res_ord_3 = skill_extractor.extract_skills(ordinary_text_3)
    assert "Go" not in res_ord_3.canonical_skills
    assert "Move" not in res_ord_3.canonical_skills
    assert "C" not in res_ord_3.canonical_skills


def test_overlapping_terms_react_vs_react_native():
    """
    Verify compound terms (e.g. 'React Native') do not cause false sub-term
    extractions ('React') when the standalone term does not exist independently.
    """
    # 1. Only compound skill mentioned
    compound_only = "Specialized mobile software engineer building applications with React Native."
    res_compound = skill_extractor.extract_skills(compound_only)
    assert "React Native" in res_compound.canonical_skills
    assert "React" not in res_compound.canonical_skills
    assert res_compound.total_unique_skills == 1

    # 2. Both compound and standalone skill mentioned independently
    both_skills = "We build our web applications using React and our mobile apps with React Native."
    res_both = skill_extractor.extract_skills(both_skills)
    assert "React" in res_both.canonical_skills
    assert "React Native" in res_both.canonical_skills
    assert res_both.total_unique_skills == 2

    # Verify counts: each should be exactly 1
    react_skill = next(s for s in res_both.skills if s.canonical_name == "React")
    react_native_skill = next(s for s in res_both.skills if s.canonical_name == "React Native")
    assert react_skill.count == 1
    assert react_native_skill.count == 1
    assert res_both.total_mentions == 2


def test_overlapping_terms_cloud_storage():
    """Verify Google Cloud Storage does not shadow-match Google Cloud Platform via alias."""
    text_sample = "Archival storage configured using Google Cloud Storage buckets."
    res = skill_extractor.extract_skills(text_sample)
    assert "Google Cloud Storage" in res.canonical_skills
    assert "Google Cloud Platform" not in res.canonical_skills


def test_evidence_snippets_and_exact_mention_counts():
    """
    Verify reported mention counts strictly equal actual non-overlapping occurrences
    and evidence snippets provide localized surrounding context.
    """
    text_sample = (
        "We rely on Docker for containerization. Our Docker images are optimized. "
        "Every engineer runs Docker locally before pushing to Kubernetes."
    )
    res = skill_extractor.extract_skills(text_sample)
    assert "Docker" in res.canonical_skills
    assert "Kubernetes" in res.canonical_skills

    docker_entry = next(s for s in res.skills if s.canonical_name == "Docker")
    # Docker appears exactly 3 times
    assert docker_entry.count == 3
    # Exactly up to 2 distinct evidence snippets captured
    assert len(docker_entry.evidence_snippets) == 2
    for snippet in docker_entry.evidence_snippets:
        assert "Docker" in snippet

    k8s_entry = next(s for s in res.skills if s.canonical_name == "Kubernetes")
    # Kubernetes appears exactly 1 time
    assert k8s_entry.count == 1
    assert len(k8s_entry.evidence_snippets) == 1

    assert res.total_mentions == 4


def test_job_description_classification_edge_cases():
    """
    Verify job description section parsing handles reordered sections,
    unheaded text, and neutral concluding sections.
    """
    # 1. Reordered sections: Preferred first, Requirements second
    reordered_job = """
    Job Opportunity: Backend Lead
    
    Nice-to-Have Skills:
    - Experience with GraphQL and Redis
    
    Minimum Requirements:
    - 5+ years of Python and PostgreSQL experience
    """
    res_reordered = skill_extractor.extract_skills_from_job(reordered_job)
    assert "Python" in res_reordered.required_skills
    assert "PostgreSQL" in res_reordered.required_skills
    assert "GraphQL" in res_reordered.preferred_skills
    assert "Redis" in res_reordered.preferred_skills
    assert len(set(res_reordered.required_skills).intersection(set(res_reordered.preferred_skills))) == 0

    # 2. Unheaded unstructured job text: All skills default to required
    unstructured_job = "We are seeking a developer proficient in TypeScript, React, and AWS."
    res_unstructured = skill_extractor.extract_skills_from_job(unstructured_job)
    assert set(res_unstructured.required_skills) == {"AWS", "React", "TypeScript"}
    assert res_unstructured.preferred_skills == []

    # 3. Neutral concluding section does not pollute requirements
    job_with_benefits = """
    Requirements:
    - Must know Java and Spring Boot
    
    About Us & Benefits:
    - Acme Corp is an equal opportunity employer providing health benefits.
    """
    res_benefits = skill_extractor.extract_skills_from_job(job_with_benefits)
    assert "Java" in res_benefits.required_skills
    assert "Spring Boot" in res_benefits.required_skills
    assert res_benefits.preferred_skills == []

