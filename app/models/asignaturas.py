from sqlalchemy import Column, Integer, String

from .base import Base


class Asignatura(Base):
    __tablename__ = "Asignaturas"
    id_asignatura = Column(Integer, primary_key=True, index=True)
    nombre_asignatura = Column(String(100), unique=True, nullable=False)
