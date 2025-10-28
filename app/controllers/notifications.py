from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.deps import get_db
from app.models.notificacion import Notificacion
from app.schemas.notificacion import NotificacionCreate, NotificacionRead

router = APIRouter()


@router.post("/", response_model=NotificacionRead, status_code=status.HTTP_201_CREATED)
async def create_notification(
    notification_in: NotificacionCreate, db: AsyncSession = Depends(get_db)
):
    noti = Notificacion(**notification_in.dict())
    db.add(noti)
    await db.commit()
    await db.refresh(noti)
    return noti


@router.get("/user/{user_id}", response_model=list[NotificacionRead])
async def list_notifications(
    user_id: int,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    base_query = (
        select(Notificacion)
        .where(
            (Notificacion.id_estudiante == user_id)
            | (Notificacion.id_profesor == user_id)
        )
        .order_by(Notificacion.fecha_creacion.desc())
    )
    result = await db.execute(base_query.limit(limit).offset(offset))
    return result.scalars().all()


@router.patch("/{notification_id}/read", response_model=NotificacionRead)
async def mark_as_read(notification_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Notificacion).where(Notificacion.id_notificacion == notification_id)
    )
    noti = result.scalar_one_or_none()
    if not noti:
        raise HTTPException(status_code=404, detail="Notificación no encontrada")
    noti.leida = True
    await db.commit()
    await db.refresh(noti)
    return noti


@router.patch("/user/{user_id}/read_all", response_model=int)
async def mark_all_as_read(user_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Notificacion).where(
            (
                (Notificacion.id_estudiante == user_id)
                | (Notificacion.id_profesor == user_id)
            )
            & (Notificacion.leida.is_(False))
        )
    )
    notis = result.scalars().all()
    count = 0
    for n in notis:
        n.leida = True
        count += 1
    if count:
        await db.commit()
    return count
