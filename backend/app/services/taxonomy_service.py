"""
Skill Taxonomy Service
ResumeMatch — Explainable AI-Powered Resume-to-Job Matching Platform

Loads, indexes, and manages the curated technical skills taxonomy.
Adheres to architectural guidelines:
- Loads curated taxonomy from data/skills_taxonomy.json (1,731+ skills across 12 domains).
- Provides fast, case-insensitive in-memory alias-to-canonical indexing.
- Supports idempotent database seeding into the PostgreSQL `skill_taxonomy` table.
- Zero external network dependencies.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Set

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.taxonomy import SkillTaxonomy


# Resolves to <workspace_root>/data/skills_taxonomy.json
# (taxonomy_service.py -> services -> app -> backend -> <root>)
DEFAULT_TAXONOMY_PATH = (
    Path(__file__).resolve().parents[3] / "data" / "skills_taxonomy.json"
)


class TaxonomySkill(BaseModel):
    """Structured representation of an individual canonical skill entry."""
    canonical_name: str = Field(..., description="Canonical display name of the skill")
    category: str = Field(..., description="Standard industry category")
    aliases: List[str] = Field(default_factory=list, description="Alternative names, acronyms, and variants")
    case_sensitive: bool = Field(default=False, description="True for ambiguous acronyms (e.g. C, R, Go)")


class TaxonomyMetadata(BaseModel):
    """Metadata describing taxonomy provenance and scope."""
    version: str = "1.0.0"
    total_skills: int = 0
    categories: List[str] = Field(default_factory=list)
    provenance: str = ""


class TaxonomyService:
    """
    Singleton-capable taxonomy management service.
    Maintains compiled fast-lookup tables for canonical skills and alias mapping.
    """

    def __init__(self, json_path: Optional[Path] = None) -> None:
        self.json_path = json_path or DEFAULT_TAXONOMY_PATH
        self._skills: List[TaxonomySkill] = []
        self._canonical_map: Dict[str, TaxonomySkill] = {}  # lowercase canonical -> TaxonomySkill
        self._alias_map: Dict[str, str] = {}  # lowercase alias -> canonical_name
        self._metadata: Optional[TaxonomyMetadata] = None
        self._loaded: bool = False
        self._load()

    def _load(self) -> None:
        """Loads and indexes the skills taxonomy from the JSON catalog."""
        if not self.json_path.exists():
            raise FileNotFoundError(f"Taxonomy catalog file not found at: {self.json_path}")

        with open(self.json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        meta_dict = data.get("metadata", {})
        self._metadata = TaxonomyMetadata(
            version=data.get("version", "1.0.0"),
            total_skills=meta_dict.get("total_skills", 0),
            categories=meta_dict.get("categories", []),
            provenance=meta_dict.get("provenance", ""),
        )

        raw_skills = data.get("skills", [])
        self._skills = []
        self._canonical_map = {}
        self._alias_map = {}

        for item in raw_skills:
            skill = TaxonomySkill(
                canonical_name=item["canonical_name"],
                category=item["category"],
                aliases=item.get("aliases", []),
                case_sensitive=item.get("case_sensitive", False),
            )
            self._skills.append(skill)
            can_lower = skill.canonical_name.lower()
            self._canonical_map[can_lower] = skill

            # Map canonical name to itself
            self._alias_map[can_lower] = skill.canonical_name

            # Map all aliases to canonical name
            for alias in skill.aliases:
                self._alias_map[alias.lower()] = skill.canonical_name

        self._loaded = True

    @property
    def skills(self) -> List[TaxonomySkill]:
        """Returns all canonical taxonomy skills."""
        return self._skills

    @property
    def total_skills(self) -> int:
        """Returns the total number of canonical skills loaded."""
        return len(self._skills)

    @property
    def metadata(self) -> Optional[TaxonomyMetadata]:
        """Returns catalog metadata."""
        return self._metadata

    def get_by_canonical_name(self, name: str) -> Optional[TaxonomySkill]:
        """Looks up a skill by exact canonical name (case-insensitive)."""
        return self._canonical_map.get(name.strip().lower())

    def resolve_alias(self, term: str) -> Optional[str]:
        """Resolves an alias or synonym to its canonical skill name."""
        return self._alias_map.get(term.strip().lower())

    def get_skills_by_category(self, category: str) -> List[TaxonomySkill]:
        """Returns all skills belonging to a specific category."""
        target = category.strip().lower()
        return [s for s in self._skills if s.category.lower() == target]

    async def seed_database(self, session: AsyncSession) -> int:
        """
        Idempotently seeds or updates the `skill_taxonomy` table in PostgreSQL.
        Returns the number of skills inserted or updated.
        """
        # Fetch existing skills in database
        result = await session.execute(select(SkillTaxonomy))
        existing_records = {row.canonical_name.lower(): row for row in result.scalars().all()}

        count = 0
        for skill in self._skills:
            can_lower = skill.canonical_name.lower()
            if can_lower in existing_records:
                record = existing_records[can_lower]
                # Update aliases and category if modified
                if set(record.aliases) != set(skill.aliases) or record.category != skill.category:
                    record.aliases = skill.aliases
                    record.category = skill.category
                    count += 1
            else:
                new_record = SkillTaxonomy(
                    canonical_name=skill.canonical_name,
                    category=skill.category,
                    aliases=skill.aliases,
                )
                session.add(new_record)
                count += 1

        await session.flush()
        return count


# Default module-level singleton instance
taxonomy_service = TaxonomyService()
