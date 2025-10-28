from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Time

from .base import Base


class DisponibilidadDocente(Base):
    __tablename__ = "DisponibilidadDocente"

    id_disponibilidad = Column(Integer, primary_key=True, index=True)
    id_profesor = Column(Integer, ForeignKey("Usuarios.id_usuario"), nullable=False)
    id_asignatura = Column(
        Integer, ForeignKey("Asignaturas.id_asignatura"), nullable=False
    )
    dia_semana = Column(String(10), nullable=False)
    hora_inicio = Column(Time, nullable=False)
    hora_fin = Column(Time, nullable=False)
