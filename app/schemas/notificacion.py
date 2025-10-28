from datetime import datetime
from pydantic import BaseModel
from typing import Optional


class NotificacionBase(BaseModel):
    id_estudiante: Optional[int] = None
    id_profesor: Optional[int] = None
    titulo: str
    descripcion: Optional[str] = None
    tipo: Optional[str] = None


class NotificacionCreate(NotificacionBase):
    pass


class NotificacionRead(NotificacionBase):
    id_notificacion: int
    leida: bool
    fecha_creacion: datetime

    class Config:
        orm_mode = True
