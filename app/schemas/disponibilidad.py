from datetime import datetime

from pydantic import BaseModel
from datetime import time

class DisponibilidadDocenteBase(BaseModel):
    id_profesor: int
    fecha_hora_inicio: datetime
    fecha_hora_fin: datetime


class DisponibilidadCreate(BaseModel):
    id_profesor: int
    id_asignatura: int
    dia_semana: str  # ej: 'lunes'
    hora_inicio: time
    hora_fin: time


class DisponibilidadRead(DisponibilidadCreate):
    id_disponibilidad: int
    id_profesor: int
    dia_semana: str
    hora_inicio: time
    hora_fin: time

    class Config:
        orm_mode = True


class HorarioLibre(BaseModel):
    inicio: time
    fin: time
