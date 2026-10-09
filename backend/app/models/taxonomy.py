from datetime import UTC, datetime
import uuid
from typing import List
from sqlalchemy import DateTime, String
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

class SkillTaxonomy(Base):
    __tablename__ = "skill_taxonomy"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    canonical_name: Mapped[str] = mapped_column(
        String(150), unique=True, nullable=False, index=True
    )
    category: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True
    )
    aliases: Mapped[List[str]] = mapped_column(
        ARRAY(String), default=list, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    # Many-to-many relationships via association tables
    resumes: Mapped[List["Resume"]] = relationship(
        "Resume",
        secondary="resume_skills",
        back_populates="skills",
    )
    jobs: Mapped[List["Job"]] = relationship(
        "Job",
        secondary="job_skills",
        back_populates="skills",
    )
