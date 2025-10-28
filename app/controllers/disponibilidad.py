import unicodedata
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import Date, cast, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.deps import get_db
from app.models.disponibilidad import DisponibilidadDocente
from app.models.tutorias import Tutoria
from app.schemas.disponibilidad import (
    DisponibilidadCreate,
    DisponibilidadRead,
    HorarioLibre,
)

router = APIRouter()


# Crear disponibilidad
@router.post(
    "/", response_model=DisponibilidadRead, status_code=status.HTTP_201_CREATED
)
async def create_disponibilidad(
    disponibilidad_in: DisponibilidadCreate,
    db: AsyncSession = Depends(get_db),
):
    disponibilidad = DisponibilidadDocente(
        id_profesor=disponibilidad_in.id_profesor,
        id_asignatura=disponibilidad_in.id_asignatura,
        dia_semana=disponibilidad_in.dia_semana,
        hora_inicio=disponibilidad_in.hora_inicio,
        hora_fin=disponibilidad_in.hora_fin,
    )
    db.add(disponibilidad)
    await db.commit()
    await db.refresh(disponibilidad)
    return DisponibilidadRead(
        id_disponibilidad=disponibilidad.id_disponibilidad,
        id_profesor=disponibilidad.id_profesor,
        id_asignatura=disponibilidad.id_asignatura,
        dia_semana=disponibilidad.dia_semana,
        hora_inicio=disponibilidad.hora_inicio,
        hora_fin=disponibilidad.hora_fin,
    )


# Listar disponibilidad por profesor (todas sus asignaturas)
@router.get(
    "/asignatura/{id_asignatura}/profesor/{id_profesor}",
    response_model=list[DisponibilidadRead],
)
async def list_disponibilidad_docente_asignatura(
    id_asignatura: int,
    id_profesor: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(DisponibilidadDocente).where(
            DisponibilidadDocente.id_profesor == id_profesor,
            DisponibilidadDocente.id_asignatura == id_asignatura,
        )
    )
    return result.scalars().all()


@router.get(
    "/asignatura/{id_asignatura}/profesor/{id_profesor}/libres",
    response_model=list[HorarioLibre],
)
async def list_horarios_libres(
    id_asignatura: int,
    id_profesor: int,
    fecha: date = Query(..., description="Fecha en formato YYYY-MM-DD"),
    db: AsyncSession = Depends(get_db),
):
    dias = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]
    dia_semana = dias[fecha.weekday()]
    print(
        f"Buscando franjas para: {dia_semana}, fecha={fecha}, profesor={id_profesor}, asignatura={id_asignatura}"
    )

    q_disp = await db.execute(
        select(DisponibilidadDocente).where(
            DisponibilidadDocente.id_profesor == id_profesor,
            DisponibilidadDocente.id_asignatura == id_asignatura,
            DisponibilidadDocente.dia_semana == dia_semana,
        )
    )
    franjas = q_disp.scalars().all()
    print(f"Franjas encontradas: {franjas}")
    # 2) Trae las tutorías ocupadas ese día
    q_tuts = await db.execute(
        select(Tutoria).where(
            Tutoria.id_profesor == id_profesor,
            Tutoria.id_asignatura == id_asignatura,
            cast(Tutoria.fecha_hora_inicio, Date) == fecha,
        )
    )
    tuts = q_tuts.scalars().all()

    ocupado_times = [
        (tut.fecha_hora_inicio.time(), tut.fecha_hora_fin.time()) for tut in tuts
    ]

    libres: list[dict] = []
    for f in franjas:
        inicio_dt = datetime.combine(fecha, f.hora_inicio)
        fin_dt = datetime.combine(fecha, f.hora_fin)

        current_slot_start_dt = inicio_dt
        while current_slot_start_dt + timedelta(hours=1) <= fin_dt:
            slot_inicio_time = current_slot_start_dt.time()
            slot_fin_dt = current_slot_start_dt + timedelta(hours=1)
            slot_fin_time = slot_fin_dt.time()

            is_slot_ocupado = False
            for tut_start_time, tut_end_time in ocupado_times:
                if slot_inicio_time < tut_end_time and tut_start_time < slot_fin_time:
                    is_slot_ocupado = True
                    break

            if not is_slot_ocupado:
                libres.append(
                    {
                        "inicio": slot_inicio_time.strftime("%H:%M:%S"),
                        "fin": slot_fin_time.strftime("%H:%M:%S"),
                    }
                )
            current_slot_start_dt += timedelta(hours=1)
    return libres


def normaliza_dia(d: str) -> str:
    return (
        unicodedata.normalize("NFKD", d)
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
        .strip()
    )


@router.get(
    "/asignatura/{id_asignatura}/profesor/{id_profesor}/dias", response_model=list[str]
)
async def dias_disponibles_docente_asignatura(
    id_asignatura: int,
    id_profesor: int,
    db: AsyncSession = Depends(get_db),
):
    q = await db.execute(
        select(DisponibilidadDocente.dia_semana).where(
            DisponibilidadDocente.id_profesor == id_profesor,
            DisponibilidadDocente.id_asignatura == id_asignatura,
        )
    )
    dias = [row[0] for row in q.fetchall()]
    # Quita duplicados por si acaso
    return list(sorted(set(dias)))


# New endpoint: list free dates for a profesor
@router.get(
    "/asignatura/{id_asignatura}/profesor/{id_profesor}/dias_libres",
    response_model=list[str],
)
async def list_dias_libres(
    id_asignatura: int,
    id_profesor: int,
    start: date = Query(..., description="Fecha de inicio YYYY-MM-DD"),
    end: date = Query(..., description="Fecha de fin YYYY-MM-DD"),
    db: AsyncSession = Depends(get_db),
):  # Fetch configured availability days for the profesor
    q_disp = await db.execute(
        select(DisponibilidadDocente.dia_semana).where(
            DisponibilidadDocente.id_profesor == id_profesor,
            DisponibilidadDocente.id_asignatura == id_asignatura,
        )
    )
    dias_config = [row[0].lower() for row in q_disp.fetchall()]

    # Map Spanish day names to weekday numbers (0=Monday)
    map_dia = {
        "lunes": 0,
        "martes": 1,
        "miercoles": 2,
        "jueves": 3,
        "viernes": 4,
        "sabado": 5,
        "domingo": 6,
    }
    disponibles_weekdays = {map_dia[d] for d in dias_config if d in map_dia}

    libres: list[str] = []
    current = start
    while current <= end:
        wd = current.weekday()
        # Check if profesor works this weekday
        if wd in disponibles_weekdays:  # Check if any tutoria exists on this date
            q_tut = await db.execute(
                select(func.count())
                .select_from(Tutoria)
                .where(
                    Tutoria.id_profesor == id_profesor,
                    Tutoria.id_asignatura == id_asignatura,
                    cast(Tutoria.fecha_hora_inicio, Date) == current,
                )
            )
            total = q_tut.scalar_one()
            if total == 0:
                libres.append(current.isoformat())
        current += timedelta(days=1)
    # Sort dates descending
    libres.sort(reverse=True)
    return libres


@router.get("/{id_profesor}", response_model=list[DisponibilidadRead])
async def get_disponibilidad_by_docente(
    id_profesor: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(DisponibilidadDocente).where(
            DisponibilidadDocente.id_profesor == id_profesor
        )
    )
    return result.scalars().all()


@router.delete("/{id_disponibilidad}", status_code=204)
async def delete_disponibilidad(
    id_disponibilidad: int,
    db: AsyncSession = Depends(get_db),
):
    disponibilidad = await db.get(DisponibilidadDocente, id_disponibilidad)
    if not disponibilidad:
        raise HTTPException(status_code=404, detail="Disponibilidad no encontrada")
    await db.delete(disponibilidad)
    await db.commit()
    return None


@router.put("/{id_disponibilidad}", response_model=DisponibilidadRead)
async def update_disponibilidad(
    id_disponibilidad: int,
    disponibilidad_in: DisponibilidadCreate,
    db: AsyncSession = Depends(get_db),
):
    """Actualiza una franja de disponibilidad.
    Se reutiliza el schema `DisponibilidadCreate` para simplicidad.
    """
    disponibilidad = await db.get(DisponibilidadDocente, id_disponibilidad)
    if not disponibilidad:
        raise HTTPException(status_code=404, detail="Disponibilidad no encontrada")

    disponibilidad.id_profesor = disponibilidad_in.id_profesor
    disponibilidad.id_asignatura = disponibilidad_in.id_asignatura
    disponibilidad.dia_semana = disponibilidad_in.dia_semana
    disponibilidad.hora_inicio = disponibilidad_in.hora_inicio
    disponibilidad.hora_fin = disponibilidad_in.hora_fin
    await db.commit()
    await db.refresh(disponibilidad)
    return DisponibilidadRead(
        id_disponibilidad=disponibilidad.id_disponibilidad,
        id_profesor=disponibilidad.id_profesor,
        id_asignatura=disponibilidad.id_asignatura,
        dia_semana=disponibilidad.dia_semana,
        hora_inicio=disponibilidad.hora_inicio,
        hora_fin=disponibilidad.hora_fin,
    )
