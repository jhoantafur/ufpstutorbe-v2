from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class TutoriaBase(BaseModel):
    id_estudiante: int
    id_profesor: int
    id_asignatura: int
    fecha_hora_inicio: str
    fecha_hora_fin: str
    modalidad: str


class TutoriaCreate(BaseModel):
    id_estudiante: int
    id_profesor: int
    id_asignatura: int
    fecha_hora_inicio: datetime
    fecha_hora_fin: datetime
    modalidad: str


class TutoriaRead(BaseModel):
    id_tutoria: int
    id_estudiante: int
    id_profesor: int
    id_asignatura: int
    fecha_hora_inicio: datetime
    fecha_hora_fin: datetime
    modalidad: str

    class Config:
        orm_mode = True
class TutoriaReschedule(BaseModel):
    fecha_hora_inicio: datetime
    fecha_hora_fin: datetime
