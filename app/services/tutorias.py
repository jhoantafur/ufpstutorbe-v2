from datetime import datetime, timezone

from sqlalchemy import and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import aliased

from app.models.asignaturas import Asignatura
from app.models.profesor_asignatura import ProfesorAsignatura
from app.models.disponibilidad import DisponibilidadDocente
from app.models.tutorias import Tutoria
from app.models.users import User


class TutoriaService:
    @staticmethod
    async def get_all(db: AsyncSession):
        # Fetch tutorias with profesor, estudiante and asignatura names in a single query
        P = aliased(User)  # Profesor
        E = aliased(User)  # Estudiante
        stmt = (
            select(
                Tutoria,
                P.nombre.label("p_nombre"),
                P.apellido.label("p_apellido"),
                E.nombre.label("e_nombre"),
                E.apellido.label("e_apellido"),
                Asignatura.nombre_asignatura.label("asig_nombre"),
            )
            .join(P, Tutoria.id_profesor == P.id_usuario)
            .join(E, Tutoria.id_estudiante == E.id_usuario)
            .join(Asignatura, Tutoria.id_asignatura == Asignatura.id_asignatura)
        )
        result = await db.execute(stmt)
        rows = result.all()
        tutorias = []
        for tutoria, p_nombre, p_apellido, e_nombre, e_apellido, asig_nombre in rows:
            tutorias.append(
                {
                    "id_tutoria": tutoria.id_tutoria,
                    "id_estudiante": tutoria.id_estudiante,
                    "id_profesor": tutoria.id_profesor,
                    "id_asignatura": tutoria.id_asignatura,
                    "fecha_hora_inicio": tutoria.fecha_hora_inicio,
                    "fecha_hora_fin": tutoria.fecha_hora_fin,
                    "modalidad": tutoria.modalidad,
                    "titulo": asig_nombre,
                    "profesor": f"{p_nombre} {p_apellido}",
                    "estudiante": f"{e_nombre} {e_apellido}",
                }
            )
        return tutorias

    @staticmethod
    async def get_by_id(db: AsyncSession, tutoria_id: int):
        result = await db.execute(
            select(Tutoria).where(Tutoria.id_tutoria == tutoria_id)
        )
        tutoria = result.scalar_one_or_none()
        if tutoria:
            return await TutoriaService.enriched_tutoria(db, tutoria)
        return None

    @staticmethod
    async def create(db: AsyncSession, tutoria_in):
        # Validate professor is assigned to asignatura
        rel_result = await db.execute(
            select(ProfesorAsignatura).where(
                and_(
                    ProfesorAsignatura.id_profesor == tutoria_in.id_profesor,
                    ProfesorAsignatura.id_asignatura == tutoria_in.id_asignatura,
                )
            )
        )
        relation = rel_result.scalar_one_or_none()
        if not relation:
            raise ValueError(
                "El profesor no está asignado a la asignatura seleccionada"
            )

        # Validate availability: find any disponibilidad record for weekday matching time window
        inicio = tutoria_in.fecha_hora_inicio
        fin = tutoria_in.fecha_hora_fin
        # Ensure timezone aware comparisons simplified (convert to naive for weekday/time extraction)
        local_inicio = inicio
        local_fin = fin
        dia_semana = local_inicio.strftime("%A").lower()  # e.g., monday
        # Map English to Spanish stored maybe; handle both
        traducciones = {
            "monday": "lunes",
            "tuesday": "martes",
            "wednesday": "miercoles",
            "thursday": "jueves",
            "friday": "viernes",
            "saturday": "sabado",
            "sunday": "domingo",
        }
        dia_semana_es = traducciones.get(dia_semana, dia_semana)

        disp_stmt = select(DisponibilidadDocente).where(
            and_(
                DisponibilidadDocente.id_profesor == tutoria_in.id_profesor,
                DisponibilidadDocente.id_asignatura == tutoria_in.id_asignatura,
                DisponibilidadDocente.dia_semana.ilike(dia_semana_es),
                DisponibilidadDocente.hora_inicio <= local_inicio.time(),
                DisponibilidadDocente.hora_fin >= local_fin.time(),
            )
        )
        disp_result = await db.execute(disp_stmt)
        disponibilidad = disp_result.scalar_one_or_none()
        if not disponibilidad:
            raise ValueError("El profesor no tiene disponibilidad para ese horario")

        # Validate no overlapping tutoria for professor or student
        overlap_stmt = select(Tutoria).where(
            and_(
                or_(
                    Tutoria.id_profesor == tutoria_in.id_profesor,
                    Tutoria.id_estudiante == tutoria_in.id_estudiante,
                ),
                Tutoria.fecha_hora_inicio < fin,
                Tutoria.fecha_hora_fin > inicio,
            )
        )
        overlap_result = await db.execute(overlap_stmt)
        if overlap_result.scalar_one_or_none():
            raise ValueError(
                "Existe una tutoría que se sobrepone en el horario indicado"
            )

        db_tutoria = Tutoria(**tutoria_in.dict())
        db.add(db_tutoria)
        await db.commit()
        await db.refresh(db_tutoria)
        return await TutoriaService.enriched_tutoria(db, db_tutoria)

    @staticmethod
    async def delete(db: AsyncSession, tutoria_id: int):
        tutoria = await TutoriaService.get_by_id(db, tutoria_id)
        if tutoria:
            # get_by_id returns enriched dict, need to fetch the actual model instance
            result = await db.execute(
                select(Tutoria).where(Tutoria.id_tutoria == tutoria_id)
            )
            tutoria_obj = result.scalar_one_or_none()
            if tutoria_obj:
                await db.delete(tutoria_obj)
                await db.commit()
        return tutoria

    @staticmethod
    async def get_by_estudiante(db: AsyncSession, id_estudiante: int):
        result = await db.execute(
            select(Tutoria).where(Tutoria.id_estudiante == id_estudiante)
        )
        tutorias = result.scalars().all()
        return [await TutoriaService.enriched_tutoria(db, t) for t in tutorias]

    @staticmethod
    async def get_by_profesor(db: AsyncSession, id_profesor: int):
        result = await db.execute(
            select(Tutoria).where(Tutoria.id_profesor == id_profesor)
        )
        tutorias = result.scalars().all()
        return [await TutoriaService.enriched_tutoria(db, t) for t in tutorias]

    @staticmethod
    async def enriched_tutoria(db: AsyncSession, tutoria: Tutoria):
        # Busca nombres de profesor y estudiante, y nombre de la asignatura
        result = await db.execute(
            select(User).where(User.id_usuario == tutoria.id_profesor)
        )
        profesor = result.scalar_one_or_none()
        result = await db.execute(
            select(User).where(User.id_usuario == tutoria.id_estudiante)
        )
        estudiante = result.scalar_one_or_none()
        result = await db.execute(
            select(Asignatura).where(Asignatura.id_asignatura == tutoria.id_asignatura)
        )
        asignatura = result.scalar_one_or_none()

        return {
            "id_tutoria": tutoria.id_tutoria,
            "id_estudiante": tutoria.id_estudiante,
            "id_profesor": tutoria.id_profesor,
            "id_asignatura": tutoria.id_asignatura,
            "fecha_hora_inicio": tutoria.fecha_hora_inicio,
            "fecha_hora_fin": tutoria.fecha_hora_fin,
            "modalidad": tutoria.modalidad,
            "titulo": asignatura.nombre_asignatura if asignatura else None,
            "profesor": f"{profesor.nombre} {profesor.apellido}" if profesor else None,
            "estudiante": (
                f"{estudiante.nombre} {estudiante.apellido}" if estudiante else None
            ),
        }

    @staticmethod
    async def get_by_user_and_range(
        db: AsyncSession, usuario_id: int, from_date: str, to_date: str
    ):
        # from_date y to_date son strings tipo 'YYYY-MM-DD'
        from_dt = datetime.fromisoformat(from_date)
        to_dt = datetime.fromisoformat(to_date)

        stmt = select(Tutoria).where(
            and_(
                or_(
                    Tutoria.id_estudiante == usuario_id,
                    Tutoria.id_profesor == usuario_id,
                ),
                Tutoria.fecha_hora_inicio >= from_dt,
                Tutoria.fecha_hora_fin <= to_dt,
            )
        )
        result = await db.execute(stmt)
        tutorias = result.scalars().all()
        return [await TutoriaService.enriched_tutoria(db, t) for t in tutorias]

    @staticmethod
    async def reschedule(db: AsyncSession, tutoria_id: int, reschedule_in):
        result = await db.execute(
            select(Tutoria).where(Tutoria.id_tutoria == tutoria_id)
        )
        tutoria = result.scalar_one_or_none()
        if not tutoria:
            return None
        now = datetime.now(timezone.utc)
        tutoria_fecha_inicio = tutoria.fecha_hora_inicio
        if tutoria_fecha_inicio.tzinfo is None:
            tutoria_fecha_inicio = tutoria_fecha_inicio.replace(tzinfo=timezone.utc)
        # Only allow reschedule if tutoria is more than 24h away
        if (tutoria_fecha_inicio - now).total_seconds() < 24 * 3600:
            # Not allowed to reschedule if tutoria is less than 24h away
            return None
        tutoria.fecha_hora_inicio = reschedule_in.fecha_hora_inicio
        tutoria.fecha_hora_fin = reschedule_in.fecha_hora_fin
        await db.commit()
        await db.refresh(tutoria)
        return await TutoriaService.enriched_tutoria(db, tutoria)
