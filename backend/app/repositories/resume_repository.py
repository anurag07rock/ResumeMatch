from typing import List, Optional
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.resume import Resume
from app.repositories.base import BaseRepository

class ResumeRepository(BaseRepository[Resume]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Resume, session)

    async def get_by_user_id(
        self, user_id: uuid.UUID, skip: int = 0, limit: int = 50
    ) -> List[Resume]:
        result = await self.session.execute(
            select(Resume)
            .where(Resume.user_id == user_id)
            .order_by(Resume.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_user_resume(
        self, resume_id: uuid.UUID, user_id: uuid.UUID
    ) -> Optional[Resume]:
        result = await self.session.execute(
            select(Resume).where(
                Resume.id == resume_id, Resume.user_id == user_id
            )
        )
        return result.scalars().first()
