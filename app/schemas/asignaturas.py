from pydantic import BaseModel


class AsignaturaCreate(BaseModel):
    nombre_asignatura: str


class AsignaturaRead(BaseModel):
    id_asignatura: int
    nombre_asignatura: str

    class Config:
        orm_mode = True


class ProfesorAsignado(BaseModel):
    id_usuario: int
    nombre: str
    apellido: str | None = None
    email: str | None = None

    class Config:
        orm_mode = True


class AsignarProfesorRequest(BaseModel):
    id_profesor: int

    class Config:
        orm_mode = True
