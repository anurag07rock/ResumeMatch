"""
Natural Language Processing & Skill Extraction Service
ResumeMatch — Explainable AI-Powered Resume-to-Job Matching Platform

Provides deterministic, boundary-guarded technical skill extraction from
raw text, resume parsing outputs, and job descriptions.
Adheres strictly to the architectural and engineering governance in AGENTS.md:
- Uses the curated canonical skill taxonomy (data/skills_taxonomy.json).
- Preserves technical tokens like C++, C#, .NET, Node.js, and CI/CD without mangling.
- Enforces strict boundary guards to eliminate false positives from substrings.
- Maps aliases to canonical names and deduplicates repeated mentions.
- Classifies job description requirements into 'required_skills' vs 'preferred_skills'.
- Zero third-party cloud LLM calls; zero PII logging; deterministic execution.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Dict, List, Optional, Set, Tuple, Union

from pydantic import BaseModel, Field

from app.services.pdf_parser import PDFParseResult
from app.services.taxonomy_service import TaxonomyService, TaxonomySkill, taxonomy_service


# ---------------------------------------------------------------------------
# Structured Result Contracts
# ---------------------------------------------------------------------------

class ExtractedSkill(BaseModel):
    """Represents a single canonical skill identified in the document."""
    canonical_name: str = Field(..., description="Canonical display name of the skill")
    category: str = Field(..., description="Domain category (e.g. Databases, Languages)")
    matched_terms: List[str] = Field(default_factory=list, description="Unique aliases/terms that matched this skill")
    count: int = Field(default=1, description="Total occurrences found in the text")
    evidence_snippets: List[str] = Field(default_factory=list, description="Contextual text snippets where skill appeared")


class SkillExtractionResult(BaseModel):
    """Complete envelope of extracted skills from a document or text block."""
    skills: List[ExtractedSkill] = Field(default_factory=list, description="Extracted skills sorted deterministically")
    canonical_skills: List[str] = Field(default_factory=list, description="List of unique canonical skill names")
    total_unique_skills: int = Field(default=0, description="Total number of unique canonical skills found")
    total_mentions: int = Field(default=0, description="Total mentions across all skills")
    by_category: Dict[str, List[str]] = Field(default_factory=dict, description="Map of category -> canonical skill names")
    has_skills: bool = Field(default=False, description="True if at least one skill was identified")


class JobSkillExtractionResult(BaseModel):
    """Structured requirement breakdown extracted from a job description."""
    required_skills: List[str] = Field(default_factory=list, description="Canonical skills identified in required sections")
    preferred_skills: List[str] = Field(default_factory=list, description="Canonical skills identified in preferred sections")
    all_skills: SkillExtractionResult = Field(..., description="Complete extraction result for the full job description")


# ---------------------------------------------------------------------------
# Skill Disambiguation & Context Guard Rules
# ---------------------------------------------------------------------------

DISAMBIGUATION_NEGATIVE_PATTERNS: Dict[str, List[re.Pattern]] = {
    "C": [
        re.compile(r"(?i)\bC[- ](?:level|suite)\b"),
        re.compile(r"(?i)\b(?:vitamin|schedule|appendix|exhibit|figure|table|section)\s+C\b"),
        re.compile(r"\([cC]\)"),
        re.compile(r"(?i)\bC\s*&\s*[A-Z]\b"),
    ],
    "R": [
        re.compile(r"(?i)\bR\s*&\s*D\b"),
        re.compile(r"(?i)\bR\s+and\s+D\b"),
        re.compile(r"(?i)\b(?:vitamin|schedule|appendix|exhibit|figure|table|section)\s+R\b"),
        re.compile(r"(?i)\bR[- ](?:rated|rating)\b"),
    ],
    "D": [
        re.compile(r"(?i)\bR\s*&\s*D\b"),
        re.compile(r"(?i)\bR\s+and\s+D\b"),
        re.compile(r"(?i)\b(?:vitamin|schedule|appendix|exhibit|figure|table|section)\s+D\b"),
        re.compile(r"(?i)\b[23][- ]?D\b"),
    ],
    "Go": [
        re.compile(r"(?i)\b(?:to|can|will|shall|must|should|could|would|let's|lets|ready\s+to|have\s+to|want\s+to|need\s+to)\s+Go\b"),
        re.compile(r"\bGo\s+(?:ahead|to|through|beyond|forward|for|live|with|into|over|under|out|in|back|away|up|down|on|off|fast|slow)\b"),
        re.compile(r"(?i)\bGo[- ]to\b"),
        re.compile(r"\bGo\s+and\s+(?:see|check|do|find|get|apply|talk)\b"),
    ],
    "Move": [
        re.compile(r"(?i)\b(?:to|will|can|must|should|could|would|let's|lets|help\s+to|make\s+a)\s+Move\b"),
        re.compile(r"\bMove\s+(?:to|forward|from|into|on|fast|out|ahead|the\s+needle|with|up|down|back|away|towards|around|quickly)\b"),
    ],
}


# ---------------------------------------------------------------------------
# Skill Extractor Service
# ---------------------------------------------------------------------------

class SkillExtractor:
    """
    Deterministic technical skill extractor powered by the canonical taxonomy.
    Uses combined regex matching with non-overlapping span protection and
    defensible disambiguation guards to eliminate false positives and compound-term shadowing.
    """

    def __init__(self, service: Optional[TaxonomyService] = None) -> None:
        self.taxonomy = service or taxonomy_service
        self._cs_pattern: Optional[re.Pattern] = None
        self._ci_pattern: Optional[re.Pattern] = None
        self._cs_map: Dict[str, TaxonomySkill] = {}
        self._ci_map: Dict[str, TaxonomySkill] = {}
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """
        Compiles high-performance combined regex search patterns for all skills and aliases.
        Terms are sorted by token length descending to prioritize compound skills (e.g. 'React Native')
        over sub-terms (e.g. 'React').
        """
        cs_terms: List[str] = []
        ci_terms: List[str] = []
        self._cs_map = {}
        self._ci_map = {}

        for skill in self.taxonomy.skills:
            items = [(skill.canonical_name, skill)] + [(a, skill) for a in skill.aliases]
            for term, sk in items:
                clean_term = term.strip()
                if not clean_term:
                    continue
                if sk.case_sensitive:
                    cs_terms.append(clean_term)
                    self._cs_map[clean_term] = sk
                else:
                    ci_terms.append(clean_term)
                    self._ci_map[clean_term.lower()] = sk

        # Sort terms length descending to ensure longer compound phrases are prioritized
        cs_terms_sorted = sorted(list(set(cs_terms)), key=len, reverse=True)
        ci_terms_sorted = sorted(list(set(ci_terms)), key=len, reverse=True)

        # Technical boundary guards:
        # (?<![a-zA-Z0-9#+]) ensures no preceding alphanumeric, #, or +
        # (?![a-zA-Z0-9#+]) ensures no succeeding alphanumeric, #, or +
        cs_pattern_str = r"(?<![a-zA-Z0-9#+])(?:" + "|".join(re.escape(t) for t in cs_terms_sorted) + r")(?![a-zA-Z0-9#+])"
        ci_pattern_str = r"(?<![a-zA-Z0-9#+])(?:" + "|".join(re.escape(t) for t in ci_terms_sorted) + r")(?![a-zA-Z0-9#+])"

        self._cs_pattern = re.compile(cs_pattern_str)
        self._ci_pattern = re.compile(ci_pattern_str, re.IGNORECASE)

    @staticmethod
    def _normalize_text_for_nlp(text: str) -> str:
        """
        Normalizes text while strictly preserving technical tokens.
        - Unicode NFKC normalization.
        - Replaces non-standard whitespace and tabs with single space.
        - Preserves punctuation essential to tech tokens (+, #, ., -, /).
        """
        if not text:
            return ""
        # Unicode normalization (e.g. accented characters, special dashes)
        text = unicodedata.normalize("NFKC", text)
        # Normalize newlines
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        return text

    @staticmethod
    def _extract_evidence_snippet(text: str, start: int, end: int, window: int = 50) -> str:
        """Extracts a short snippet of surrounding context without leaking unnecessary text."""
        left = max(0, start - window)
        right = min(len(text), end + window)
        snippet = text[left:right].strip()
        # Collapse excessive newlines inside snippet
        snippet = re.sub(r"\s+", " ", snippet)
        return snippet

    def extract_skills(self, text: str) -> SkillExtractionResult:
        """
        Extracts canonical skills from a raw string with boundary verification.
        Deduplicates occurrences while tracking frequency and contextual evidence.
        Guarantees that compound terms (e.g. 'React Native') do not double-count sub-terms ('React').
        """
        if not text or not text.strip():
            return SkillExtractionResult(
                skills=[],
                canonical_skills=[],
                total_unique_skills=0,
                total_mentions=0,
                by_category={},
                has_skills=False,
            )

        normalized = self._normalize_text_for_nlp(text)

        # Collect candidate matches: (start, end, term_text, skill)
        candidates: List[Tuple[int, int, str, TaxonomySkill]] = []

        if self._cs_pattern:
            for m in self._cs_pattern.finditer(normalized):
                term_text = m.group()
                sk = self._cs_map.get(term_text)
                if sk:
                    candidates.append((m.start(), m.end(), term_text, sk))

        if self._ci_pattern:
            for m in self._ci_pattern.finditer(normalized):
                term_text = m.group()
                sk = self._ci_map.get(term_text.lower())
                if sk:
                    candidates.append((m.start(), m.end(), term_text, sk))

        # Sort candidates: earlier in text first; for identical start, longer span first
        candidates.sort(key=lambda c: (c[0], -(c[1] - c[0])))

        # Track non-overlapping accepted spans and skill matches:
        # canonical_name -> {"skill": TaxonomySkill, "matched_terms": set(), "count": int, "snippets": []}
        accepted_spans: List[Tuple[int, int]] = []
        skill_matches: Dict[str, Dict] = {}

        for start, end, term_text, skill in candidates:
            # 1. Defensible disambiguation check for ambiguous short words/letters
            neg_patterns = DISAMBIGUATION_NEGATIVE_PATTERNS.get(term_text, [])
            if any(not (end <= nm.start() or start >= nm.end()) for pat in neg_patterns for nm in pat.finditer(normalized)):
                continue

            # 2. Overlap check against previously accepted longer/earlier spans
            if any(not (end <= a_s or start >= a_e) for a_s, a_e in accepted_spans):
                continue

            # Accept match
            accepted_spans.append((start, end))

            can_name = skill.canonical_name
            if can_name not in skill_matches:
                skill_matches[can_name] = {
                    "skill": skill,
                    "matched_terms": set(),
                    "count": 0,
                    "snippets": [],
                }

            entry = skill_matches[can_name]
            entry["matched_terms"].add(term_text)
            entry["count"] += 1

            if len(entry["snippets"]) < 2:
                snippet = self._extract_evidence_snippet(normalized, start, end)
                if snippet and snippet not in entry["snippets"]:
                    entry["snippets"].append(snippet)

        # Build structured results sorted deterministically by canonical name
        sorted_canonical = sorted(skill_matches.keys(), key=lambda s: s.lower())
        results_list: List[ExtractedSkill] = []
        by_category_map: Dict[str, List[str]] = {}
        total_mentions = 0

        for can_name in sorted_canonical:
            data = skill_matches[can_name]
            cat = data["skill"].category
            results_list.append(
                ExtractedSkill(
                    canonical_name=can_name,
                    category=cat,
                    matched_terms=sorted(list(data["matched_terms"])),
                    count=data["count"],
                    evidence_snippets=data["snippets"],
                )
            )
            total_mentions += data["count"]

            if cat not in by_category_map:
                by_category_map[cat] = []
            by_category_map[cat].append(can_name)

        # Sort category names
        by_category_sorted = {cat: sorted(by_category_map[cat]) for cat in sorted(by_category_map.keys())}

        return SkillExtractionResult(
            skills=results_list,
            canonical_skills=sorted_canonical,
            total_unique_skills=len(results_list),
            total_mentions=total_mentions,
            by_category=by_category_sorted,
            has_skills=len(results_list) > 0,
        )

    def extract_skills_from_resume(
        self, resume_input: str | PDFParseResult
    ) -> SkillExtractionResult:
        """
        Extracts skills from a resume input, accepting either raw text or a PDFParseResult.
        """
        if isinstance(resume_input, PDFParseResult):
            text_to_parse = resume_input.cleaned_text
        elif isinstance(resume_input, str):
            text_to_parse = resume_input
        else:
            raise TypeError(f"Expected str or PDFParseResult, got {type(resume_input).__name__}")

        return self.extract_skills(text_to_parse)

    def extract_skills_from_job(self, job_text: str) -> JobSkillExtractionResult:
        """
        Analyzes a job description text, partitioning it into required vs. preferred
        sections and returning classified skill requirements.
        """
        all_result = self.extract_skills(job_text)
        if not all_result.has_skills:
            return JobSkillExtractionResult(
                required_skills=[],
                preferred_skills=[],
                all_skills=all_result,
            )

        # Section-based classification
        lines = job_text.split("\n")
        req_lines: List[str] = []
        pref_lines: List[str] = []
        current_section = "neutral"

        req_header_pattern = re.compile(
            r"^\s*(?:[\d\.\-\*#]+\s*)?(?:minimum\s+)?(?:requirements|required|qualifications|must[- ]have|what\s+you(?:'ll|\s+will)\s+need|basic\s+qualifications)\b",
            re.IGNORECASE,
        )
        pref_header_pattern = re.compile(
            r"^\s*(?:[\d\.\-\*#]+\s*)?(?:preferred|nice[- ]to[- ]have|bonus|plus|desired\s+qualifications|good\s+to\s+have)\b",
            re.IGNORECASE,
        )
        neutral_header_pattern = re.compile(
            r"^\s*(?:[\d\.\-\*#]+\s*)?(?:about\s+(?:us|the\s+company|our\s+team)|benefits|perks|compensation|how\s+to\s+apply|equal\s+opportunity|diversity|about\s+the\s+role)\b",
            re.IGNORECASE,
        )

        for line in lines:
            line_stripped = line.strip()
            if not line_stripped:
                continue

            if pref_header_pattern.search(line_stripped):
                current_section = "preferred"
                continue
            elif req_header_pattern.search(line_stripped):
                current_section = "required"
                continue
            elif neutral_header_pattern.search(line_stripped):
                current_section = "neutral"
                continue

            if current_section == "preferred":
                pref_lines.append(line_stripped)
            elif current_section == "required":
                req_lines.append(line_stripped)

        req_text = "\n".join(req_lines)
        pref_text = "\n".join(pref_lines)

        req_result = self.extract_skills(req_text)
        pref_result = self.extract_skills(pref_text)

        required_canonical = set(req_result.canonical_skills)
        preferred_canonical = set(pref_result.canonical_skills)

        # Any skill not clearly under preferred defaults to required if under required section,
        # or defaults to required if no section headers were found.
        if not required_canonical and not preferred_canonical:
            # If no section headings detected, all skills are treated as required
            required_skills = sorted(list(all_result.canonical_skills))
            preferred_skills = []
        else:
            # Preferred skills cannot overlap with required skills
            preferred_canonical = preferred_canonical - required_canonical
            # Skills in unclassified sections belong to required
            unclassified = set(all_result.canonical_skills) - preferred_canonical
            required_skills = sorted(list(unclassified))
            preferred_skills = sorted(list(preferred_canonical))

        return JobSkillExtractionResult(
            required_skills=required_skills,
            preferred_skills=preferred_skills,
            all_skills=all_result,
        )


# Default module-level extractor singleton
skill_extractor = SkillExtractor()
