from typing import List, Optional
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.match import Match
from app.repositories.base import BaseRepository

class MatchRepository(BaseRepository[Match]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Match, session)

    async def get_by_user_id(
        self, user_id: uuid.UUID, skip: int = 0, limit: int = 50
    ) -> List[Match]:
        result = await self.session.execute(
            select(Match)
            .where(Match.user_id == user_id)
            .order_by(Match.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_resume_and_job(
        self, resume_id: uuid.UUID, job_id: uuid.UUID
    ) -> Optional[Match]:
        result = await self.session.execute(
            select(Match).where(
                Match.resume_id == resume_id, Match.job_id == job_id
            )
        )
        return result.scalars().first()
