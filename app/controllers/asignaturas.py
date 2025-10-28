from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_, delete
from sqlalchemy.exc import IntegrityError

from app.core.deps import get_db
from app.models.asignaturas import Asignatura
from app.models.profesor_asignatura import ProfesorAsignatura
from app.models.disponibilidad import DisponibilidadDocente
from app.models.users import User
from app.models.roles import Role
from app.schemas.asignaturas import (
    AsignaturaCreate,
    AsignaturaRead,
    ProfesorAsignado,
    AsignarProfesorRequest,
)

router = APIRouter()


@router.post("/", response_model=AsignaturaRead, status_code=status.HTTP_201_CREATED)
async def create_asignatura(
    asignatura_in: AsignaturaCreate, db: AsyncSession = Depends(get_db)
):
    db_asignatura = Asignatura(nombre_asignatura=asignatura_in.nombre_asignatura)
    db.add(db_asignatura)
    await db.commit()
    await db.refresh(db_asignatura)
    return db_asignatura


@router.get("/", response_model=list[AsignaturaRead])
async def list_asignaturas(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Asignatura))
    return result.scalars().all()


@router.get("/{asignatura_id}", response_model=AsignaturaRead)
async def get_asignatura(asignatura_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Asignatura).where(Asignatura.id_asignatura == asignatura_id)
    )
    asignatura = result.scalar_one_or_none()
    if not asignatura:
        raise HTTPException(status_code=404, detail="Asignatura not found")
    return asignatura


@router.get("/profesor/{id_profesor}", response_model=list[AsignaturaRead])
async def get_asignaturas_by_profesor(
    id_profesor: int, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Asignatura)
        .join(
            ProfesorAsignatura,
            Asignatura.id_asignatura == ProfesorAsignatura.id_asignatura,
        )
        .where(ProfesorAsignatura.id_profesor == id_profesor)
    )
    return result.scalars().all()


@router.delete("/{asignatura_id}", status_code=204)
async def delete_asignatura(asignatura_id: int, db: AsyncSession = Depends(get_db)):
    # Ensure the asignatura exists
    result = await db.execute(
        select(Asignatura).where(Asignatura.id_asignatura == asignatura_id)
    )
    asignatura = result.scalar_one_or_none()
    if not asignatura:
        raise HTTPException(status_code=404, detail="Asignatura not found")

    # First, remove relationships that reference this asignatura to avoid FK violations
    await db.execute(
        delete(DisponibilidadDocente).where(
            DisponibilidadDocente.id_asignatura == asignatura_id
        )
    )
    await db.execute(
        delete(ProfesorAsignatura).where(
            ProfesorAsignatura.id_asignatura == asignatura_id
        )
    )

    # Then delete the asignatura itself
    await db.delete(asignatura)
    try:
        await db.commit()
    except IntegrityError:
        # Rollback the transaction and return a conflict if other entities still reference this asignatura
        await db.rollback()
        # Most likely there are Tutorias referencing this asignatura
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "No se puede eliminar la asignatura porque existen registros relacionados (por ejemplo, tutorías). "
                "Elimine o reasigne esos registros antes de intentar nuevamente."
            ),
        )


@router.get("/{asignatura_id}/profesores", response_model=list[ProfesorAsignado])
async def list_profesores_asignatura(
    asignatura_id: int,
    only_with_availability: bool = Query(
        False,
        description="Return only profesores that currently have at least one availability slot configured for this asignatura.",
    ),
    db: AsyncSession = Depends(get_db),
):
    # Ensure asignatura exists
    result = await db.execute(
        select(Asignatura).where(Asignatura.id_asignatura == asignatura_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Asignatura not found")

    base_query = (
        select(User)
        .join(ProfesorAsignatura, User.id_usuario == ProfesorAsignatura.id_profesor)
        .where(ProfesorAsignatura.id_asignatura == asignatura_id)
    )
    if only_with_availability:
        # Import locally to avoid circular import
        from app.models.disponibilidad import DisponibilidadDocente
        from sqlalchemy import exists, select as sel

        base_query = base_query.where(
            exists(
                sel(1)
                .select_from(DisponibilidadDocente)
                .where(
                    and_(
                        DisponibilidadDocente.id_profesor
                        == ProfesorAsignatura.id_profesor,
                        DisponibilidadDocente.id_asignatura == asignatura_id,
                    )
                )
            )
        )

    result = await db.execute(base_query)
    return result.scalars().all()


@router.post(
    "/{asignatura_id}/profesores", response_model=ProfesorAsignado, status_code=201
)
async def asignar_profesor_a_asignatura(
    asignatura_id: int,
    data: AsignarProfesorRequest,
    db: AsyncSession = Depends(get_db),
):
    # Validate asignatura
    result = await db.execute(
        select(Asignatura).where(Asignatura.id_asignatura == asignatura_id)
    )
    asignatura = result.scalar_one_or_none()
    if not asignatura:
        raise HTTPException(status_code=404, detail="Asignatura not found")

    # Validate profesor exists and has role PROFESOR
    result = await db.execute(select(User).where(User.id_usuario == data.id_profesor))
    profesor = result.scalar_one_or_none()
    if not profesor:
        raise HTTPException(status_code=404, detail="Profesor not found")

    # Optional: verify role name equals PROFESOR
    role_result = await db.execute(select(Role).where(Role.id_rol == profesor.id_rol))
    role = role_result.scalar_one_or_none()
    if role is not None:
        # Compare attribute explicitly to avoid SQLAlchemy truthiness issues
        if getattr(role, "nombre_rol", None) != "PROFESOR":
            raise HTTPException(status_code=400, detail="User is not a profesor")

    # Check existing relation
    rel_result = await db.execute(
        select(ProfesorAsignatura).where(
            and_(
                ProfesorAsignatura.id_profesor == data.id_profesor,
                ProfesorAsignatura.id_asignatura == asignatura_id,
            )
        )
    )
    relation = rel_result.scalar_one_or_none()
    if not relation:
        relation = ProfesorAsignatura(
            id_profesor=data.id_profesor, id_asignatura=asignatura_id
        )
        db.add(relation)
        try:
            await db.commit()
        except IntegrityError:
            # Another request inserted concurrently; rollback and continue
            await db.rollback()
    # Return profesor info
    result = await db.execute(select(User).where(User.id_usuario == data.id_profesor))
    profesor = result.scalar_one_or_none()
    return profesor


@router.delete("/{asignatura_id}/profesores/{id_profesor}", status_code=204)
async def desasignar_profesor_de_asignatura(
    asignatura_id: int, id_profesor: int, db: AsyncSession = Depends(get_db)
):
    rel_result = await db.execute(
        select(ProfesorAsignatura).where(
            and_(
                ProfesorAsignatura.id_profesor == id_profesor,
                ProfesorAsignatura.id_asignatura == asignatura_id,
            )
        )
    )
    relation = rel_result.scalar_one_or_none()
    if not relation:
        # Idempotent delete
        return
    await db.delete(relation)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
