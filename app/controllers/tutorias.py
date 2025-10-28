from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.params import Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.schemas.tutorias import TutoriaCreate, TutoriaRead, TutoriaReschedule
from app.services.tutorias import TutoriaService
from app.models.notificacion import Notificacion
from app.core.ws_manager import manager

router = APIRouter()


@router.post("/", response_model=TutoriaRead, status_code=status.HTTP_201_CREATED)
async def create_tutoria(tutoria_in: TutoriaCreate, db: AsyncSession = Depends(get_db)):
    # Forzamos que los campos sean obligatorios (Pydantic ya lo hace, pero doble check)
    if not tutoria_in.id_estudiante or not tutoria_in.id_profesor:
        raise HTTPException(
            status_code=400, detail="Estudiante y Profesor son obligatorios"
        )
    try:
        tutoria = await TutoriaService.create(db, tutoria_in)
        # Create notifications for student and professor with descripcion (enriched names available in tutoria dict)
        asig = tutoria.get("titulo")
        profesor_nombre = tutoria.get("profesor")
        estudiante_nombre = tutoria.get("estudiante")
        inicio = tutoria.get("fecha_hora_inicio")
        notif_student = Notificacion(
            id_estudiante=tutoria["id_estudiante"],
            titulo="Tutoría agendada",
            descripcion=(
                f"Has agendado {asig} con {profesor_nombre} el {inicio}"
                if asig and profesor_nombre
                else f"Has agendado una tutoría el {inicio}"
            ),
            tipo="CREATED",
        )
        notif_profesor = Notificacion(
            id_profesor=tutoria["id_profesor"],
            titulo="Nueva tutoría agendada",
            descripcion=(
                f"{estudiante_nombre} agendó {asig} para el {inicio}"
                if estudiante_nombre and asig
                else f"Se agendó una tutoría para el {inicio}"
            ),
            tipo="CREATED",
        )
        db.add_all([notif_student, notif_profesor])
        await db.commit()
        await db.refresh(notif_student)
        await db.refresh(notif_profesor)
        # Broadcast notifications asynchronously (fire and forget)
        await manager.send_personal(
            tutoria["id_estudiante"],
            {
                "type": "notification",
                "id": notif_student.id_notificacion,
                "titulo": notif_student.titulo,
                "descripcion": notif_student.descripcion,
                "leida": notif_student.leida,
                "fecha_creacion": str(notif_student.fecha_creacion),
                "tipo": notif_student.tipo,
            },
        )
        await manager.send_personal(
            tutoria["id_profesor"],
            {
                "type": "notification",
                "id": notif_profesor.id_notificacion,
                "titulo": notif_profesor.titulo,
                "descripcion": notif_profesor.descripcion,
                "leida": notif_profesor.leida,
                "fecha_creacion": str(notif_profesor.fecha_creacion),
                "tipo": notif_profesor.tipo,
            },
        )
        return tutoria
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/estudiante/{id_estudiante}", response_model=list[TutoriaRead])
async def list_tutorias_estudiante(
    id_estudiante: int, db: AsyncSession = Depends(get_db)
):
    return await TutoriaService.get_by_estudiante(db, id_estudiante)


@router.get("/profesor/{id_profesor}", response_model=list[TutoriaRead])
async def list_tutorias_profesor(id_profesor: int, db: AsyncSession = Depends(get_db)):
    return await TutoriaService.get_by_profesor(db, id_profesor)


@router.get("/calendar", response_model=list[TutoriaRead])
async def calendar(
    usuario_id: int = Query(..., description="ID del usuario"),
    from_date: str = Query(..., description="Fecha inicio (YYYY-MM-DD)"),
    to_date: str = Query(..., description="Fecha fin (YYYY-MM-DD)"),
    db: AsyncSession = Depends(get_db),
):
    return await TutoriaService.get_by_user_and_range(
        db, usuario_id, from_date, to_date
    )


@router.delete("/{id_tutoria}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tutoria(id_tutoria: int, db: AsyncSession = Depends(get_db)):
    # Fetch tutoria details before deletion for notification context
    tutoria_data = await TutoriaService.get_by_id(db, id_tutoria)
    deleted = await TutoriaService.delete(db, id_tutoria)
    if not deleted:
        raise HTTPException(status_code=404, detail="Tutoria no encontrada")
    if tutoria_data:
        asig = tutoria_data.get("titulo")
        profesor_nombre = tutoria_data.get("profesor")
        estudiante_nombre = tutoria_data.get("estudiante")
        inicio = tutoria_data.get("fecha_hora_inicio")
        notif_student = Notificacion(
            id_estudiante=tutoria_data["id_estudiante"],
            titulo="Tutoría cancelada",
            descripcion=(
                f"Se canceló {asig} con {profesor_nombre} prevista para {inicio}"
                if asig and profesor_nombre
                else "Una tutoría fue cancelada"
            ),
            tipo="CANCELED",
        )
        notif_profesor = Notificacion(
            id_profesor=tutoria_data["id_profesor"],
            titulo="Tutoría cancelada",
            descripcion=(
                f"{estudiante_nombre} canceló {asig} prevista para {inicio}"
                if estudiante_nombre and asig
                else "Una tutoría fue cancelada"
            ),
            tipo="CANCELED",
        )
        db.add_all([notif_student, notif_profesor])
        await db.commit()
        await db.refresh(notif_student)
        await db.refresh(notif_profesor)
        await manager.send_personal(
            tutoria_data["id_estudiante"],
            {
                "type": "notification",
                "id": notif_student.id_notificacion,
                "titulo": notif_student.titulo,
                "descripcion": notif_student.descripcion,
                "leida": notif_student.leida,
                "fecha_creacion": str(notif_student.fecha_creacion),
                "tipo": notif_student.tipo,
            },
        )
        await manager.send_personal(
            tutoria_data["id_profesor"],
            {
                "type": "notification",
                "id": notif_profesor.id_notificacion,
                "titulo": notif_profesor.titulo,
                "descripcion": notif_profesor.descripcion,
                "leida": notif_profesor.leida,
                "fecha_creacion": str(notif_profesor.fecha_creacion),
                "tipo": notif_profesor.tipo,
            },
        )
    return None


@router.patch("/reschedule/{id_tutoria}", response_model=TutoriaRead)
async def reschedule_tutoria(
    id_tutoria: int,
    reschedule_in: TutoriaReschedule,
    db: AsyncSession = Depends(get_db),
):
    tutoria = await TutoriaService.reschedule(db, id_tutoria, reschedule_in)
    if not tutoria:
        raise HTTPException(
            status_code=404, detail="Tutoria no encontrada o no se puede reprogramar"
        )
    asig = tutoria.get("titulo")
    profesor_nombre = tutoria.get("profesor")
    estudiante_nombre = tutoria.get("estudiante")
    inicio = tutoria.get("fecha_hora_inicio")
    notif_student = Notificacion(
        id_estudiante=tutoria["id_estudiante"],
        titulo="Tutoría reprogramada",
        descripcion=(
            f"Reprogramaste {asig} con {profesor_nombre} para {inicio}"
            if asig and profesor_nombre
            else "Reprogramaste una tutoría"
        ),
        tipo="RESCHEDULED",
    )
    notif_profesor = Notificacion(
        id_profesor=tutoria["id_profesor"],
        titulo="Tutoría reprogramada",
        descripcion=(
            f"{estudiante_nombre} reprogramó {asig} para {inicio}"
            if estudiante_nombre and asig
            else "Una tutoría fue reprogramada"
        ),
        tipo="RESCHEDULED",
    )
    db.add_all([notif_student, notif_profesor])
    await db.commit()
    await db.refresh(notif_student)
    await db.refresh(notif_profesor)
    await manager.send_personal(
        tutoria["id_estudiante"],
        {
            "type": "notification",
            "id": notif_student.id_notificacion,
            "titulo": notif_student.titulo,
            "descripcion": notif_student.descripcion,
            "leida": notif_student.leida,
            "fecha_creacion": str(notif_student.fecha_creacion),
            "tipo": notif_student.tipo,
        },
    )
    await manager.send_personal(
        tutoria["id_profesor"],
        {
            "type": "notification",
            "id": notif_profesor.id_notificacion,
            "titulo": notif_profesor.titulo,
            "descripcion": notif_profesor.descripcion,
            "leida": notif_profesor.leida,
            "fecha_creacion": str(notif_profesor.fecha_creacion),
            "tipo": notif_profesor.tipo,
        },
    )
    return tutoria


@router.get("/", response_model=list[TutoriaRead])
async def list_tutorias(db: AsyncSession = Depends(get_db)):
    return await TutoriaService.get_all(db)
