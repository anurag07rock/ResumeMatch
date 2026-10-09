"""add_skill_associations

Revision ID: 0002_add_skill_assoc
Revises: 0001_initial_schema
Create Date: 2026-10-09 15:50:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0002_add_skill_assoc'
down_revision: Union[str, None] = '0001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Association table: resume_skills
    op.create_table(
        'resume_skills',
        sa.Column('resume_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('resumes.id', ondelete='CASCADE'),
                  primary_key=True),
        sa.Column('skill_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('skill_taxonomy.id', ondelete='CASCADE'),
                  primary_key=True),
    )

    # 2. Association table: job_skills
    op.create_table(
        'job_skills',
        sa.Column('job_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('jobs.id', ondelete='CASCADE'),
                  primary_key=True),
        sa.Column('skill_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('skill_taxonomy.id', ondelete='CASCADE'),
                  primary_key=True),
    )


def downgrade() -> None:
    op.drop_table('job_skills')
    op.drop_table('resume_skills')
