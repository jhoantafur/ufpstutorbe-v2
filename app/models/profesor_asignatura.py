from sqlalchemy import Column, Integer, ForeignKey, UniqueConstraint, Sequence
from .base import Base


class ProfesorAsignatura(Base):
    __tablename__ = "ProfesorAsignatura"
    # Explicit sequence for portability; if already exists DB will use existing sequence.
    id = Column(
        Integer, Sequence("profesor_asignatura_id_seq"), primary_key=True, index=True
    )
    id_profesor = Column(Integer, ForeignKey("Usuarios.id_usuario"), nullable=False)
    id_asignatura = Column(
        Integer, ForeignKey("Asignaturas.id_asignatura"), nullable=False
    )
    __table_args__ = (
        UniqueConstraint(
            "id_profesor", "id_asignatura", name="_profesor_asignatura_uc"
        ),
    )
