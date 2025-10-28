from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, text
from sqlalchemy.sql import func

from .base import Base


class Tutoria(Base):
    __tablename__ = "Tutorias"
    id_tutoria = Column(Integer, primary_key=True, index=True)
    id_estudiante = Column(Integer, ForeignKey("Usuarios.id_usuario"), nullable=False)
    id_profesor = Column(Integer, ForeignKey("Usuarios.id_usuario"), nullable=False)
    id_asignatura = Column(
        Integer, ForeignKey("Asignaturas.id_asignatura"), nullable=False
    )
    fecha_hora_inicio = Column(DateTime(timezone=True), nullable=False)
    fecha_hora_fin = Column(DateTime(timezone=True), nullable=False)
    modalidad = Column(String(20), nullable=False)  # 'presencial', 'videollamada'
    fecha_solicitud = Column(DateTime(timezone=True), server_default=text("now()"))
    fecha_confirmacion = Column(DateTime(timezone=True), nullable=True)
    fecha_cancelacion = Column(DateTime(timezone=True), nullable=True)
