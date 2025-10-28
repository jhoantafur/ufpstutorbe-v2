from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.asignaturas import Asignatura


class AsignaturaService:
    @staticmethod
    async def get_all(db: AsyncSession):
        result = await db.execute(select(Asignatura))
        return result.scalars().all()

    @staticmethod
    async def get_by_id(db: AsyncSession, asignatura_id: int):
        result = await db.execute(
            select(Asignatura).where(Asignatura.id_asignatura == asignatura_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def create(db: AsyncSession, asignatura_in):
        db_asignatura = Asignatura(**asignatura_in.dict())
        db.add(db_asignatura)
        await db.commit()
        await db.refresh(db_asignatura)
        return db_asignatura

    @staticmethod
    async def delete(db: AsyncSession, asignatura_id: int):
        asignatura = await AsignaturaService.get_by_id(db, asignatura_id)
        if asignatura:
            await db.delete(asignatura)
            await db.commit()
        return asignatura
