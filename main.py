from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.controllers.asignaturas import router as asignaturas_router
from app.controllers.auth import router as auth
from app.controllers.disponibilidad import router as disponibilidad
from app.controllers.roles import router as roles_router
from app.controllers.tutorias import router as tutorias_router
from app.controllers.users import router as users_router
from app.controllers.notifications import router as notifications_router
from app.models.roles import Role
from app.core.ws_manager import manager
from jose import jwt, JWTError
from app.core import security


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        await seed_roles(session)
    yield


app = FastAPI(title="UFPSTutor API", lifespan=lifespan)

app.include_router(roles_router, prefix="/roles", tags=["Roles"])
app.include_router(users_router, prefix="/users", tags=["Usuarios"])
app.include_router(asignaturas_router, prefix="/asignaturas", tags=["Asignaturas"])
app.include_router(tutorias_router, prefix="/tutorias", tags=["Tutorias"])
app.include_router(auth, prefix="/auth", tags=["auth"])
app.include_router(
    disponibilidad, prefix="/disponibilidad", tags=["DisponibilidadDocente"]
)
app.include_router(
    notifications_router, prefix="/notifications", tags=["Notificaciones"]
)

origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://ufpstutor.vercel.app",
    "https://ufpstutorv2.vercel.app",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.websocket("/ws/notifications")
async def websocket_notifications(
    websocket: WebSocket, token: str = Query(..., description="JWT access token")
):
    # Authenticate via token (query param for simplicity)
    try:
        secret = security.SECRET_KEY or ""
        algorithm = security.ALGORITHM or "HS256"
        payload = jwt.decode(token, secret, algorithms=[algorithm])
        user_id = payload.get("sub")
        if not user_id:
            await websocket.close(code=4401)
            return
    except JWTError:
        await websocket.close(code=4401)
        return

    await manager.connect(int(user_id), websocket)
    try:
        while True:
            # Keep-alive / ignore incoming messages
            await websocket.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(int(user_id), websocket)
    except Exception:
        await manager.disconnect(int(user_id), websocket)


@app.get("/health", tags=["General"])
async def health_check():
    return {"status": "ok"}


async def seed_roles(db: AsyncSession):
    roles = ["ADMINISTRADOR", "PROFESOR", "ESTUDIANTE"]
    for nombre in roles:
        result = await db.execute(select(Role).where(Role.nombre_rol == nombre))
        rol = result.scalars().first()
        if not rol:
            db.add(Role(nombre_rol=nombre))
    await db.commit()


if __name__ == "__main__":
    import os

    app_env = os.getenv("APP_ENV", "development")
    # Railway and similar platforms inject the PORT environment variable
    port = int(os.getenv("PORT", 8000))

    if app_env == "production":
        uvicorn.run("app.main:app", host="0.0.0.0", port=port)
    else:  # development
        uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)
