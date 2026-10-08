from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.taxonomy import SkillTaxonomy
from app.repositories.base import BaseRepository

class SkillRepository(BaseRepository[SkillTaxonomy]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(SkillTaxonomy, session)

    async def get_by_canonical_name(self, name: str) -> Optional[SkillTaxonomy]:
        result = await self.session.execute(
            select(SkillTaxonomy).where(
                SkillTaxonomy.canonical_name.ilike(name.strip())
            )
        )
        return result.scalars().first()

    async def get_by_category(self, category: str) -> List[SkillTaxonomy]:
        result = await self.session.execute(
            select(SkillTaxonomy)
            .where(SkillTaxonomy.category.ilike(category.strip()))
            .order_by(SkillTaxonomy.canonical_name.asc())
        )
        return list(result.scalars().all())
