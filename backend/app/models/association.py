"""
Many-to-many association tables linking resumes/jobs to the skill taxonomy.

These are SQLAlchemy Core Table objects (not ORM models) used as the
``secondary`` argument in relationship() declarations on Resume, Job,
and SkillTaxonomy.
"""
from sqlalchemy import Column, ForeignKey, Table
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base

resume_skills = Table(
    "resume_skills",
    Base.metadata,
    Column(
        "resume_id",
        UUID(as_uuid=True),
        ForeignKey("resumes.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "skill_id",
        UUID(as_uuid=True),
        ForeignKey("skill_taxonomy.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

job_skills = Table(
    "job_skills",
    Base.metadata,
    Column(
        "job_id",
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "skill_id",
        UUID(as_uuid=True),
        ForeignKey("skill_taxonomy.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)
