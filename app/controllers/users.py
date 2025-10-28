from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.deps import get_db
from app.models.users import User
from app.schemas.users import UserCreate, UserRead, UserUpdate
from app.models.roles import Role
from app.services.users import UserService

router = APIRouter()


@router.post("/", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(user_in: UserCreate, db: AsyncSession = Depends(get_db)):
    db_user = User(
        nombre=user_in.nombre,
        apellido=user_in.apellido,
        email=user_in.email,
        contrasena=user_in.contrasena,  # Recuerda hashear en producción
        id_rol=user_in.id_rol,
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user


@router.get("/", response_model=list[UserRead])
async def list_users(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User))
    return result.scalars().all()


@router.get("/profesores", response_model=list[UserRead])
async def list_profesores(db: AsyncSession = Depends(get_db)):
    # Find role id for PROFESOR then filter users
    role_result = await db.execute(select(Role).where(Role.nombre_rol == "PROFESOR"))
    role = role_result.scalar_one_or_none()
    if not role:
        return []
    result = await db.execute(select(User).where(User.id_rol == role.id_rol))
    return result.scalars().all()


@router.get("/{user_id}", response_model=UserRead)
async def get_user(user_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.id_usuario == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.patch("/{user_id}", response_model=UserRead)
async def update_user(
    user_id: int, user_in: UserUpdate, db: AsyncSession = Depends(get_db)
):
    # Fetch existing user
    result = await db.execute(select(User).where(User.id_usuario == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Email uniqueness check if updating email
    if user_in.email and user_in.email != user.email:
        exists_q = await db.execute(
            select(User).where(User.email == str(user_in.email))
        )
        exists_user = exists_q.scalar_one_or_none()
        if exists_user is not None:
            existing_id = getattr(exists_user, "id_usuario", None)
            if existing_id is not None and int(existing_id) != int(user_id):
                raise HTTPException(status_code=400, detail="Email ya está en uso")

    # Apply partial updates
    if user_in.nombre is not None:
        setattr(user, "nombre", user_in.nombre)
    if user_in.apellido is not None:
        setattr(user, "apellido", user_in.apellido)
    if user_in.email is not None:
        setattr(user, "email", str(user_in.email))
    if user_in.contrasena is not None:
        # Nota: en producción, hashear la contraseña
        setattr(user, "contrasena", user_in.contrasena)
    if user_in.id_rol is not None:
        setattr(user, "id_rol", int(user_in.id_rol))

    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.delete("/{user_id}", status_code=204)
async def delete_user(user_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.id_usuario == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    await db.delete(user)
    await db.commit()


@router.post("/init-users", tags=["Init"])
async def create_default_users(db: AsyncSession = Depends(get_db)):
    # Utilidad para buscar rol por nombre
    async def get_role_id(nombre_rol):
        result = await db.execute(select(Role).where(Role.nombre_rol == nombre_rol))
        role = result.scalar_one_or_none()
        if not role:
            raise Exception(f"Role '{nombre_rol}' not found")
        return role.id_rol

    usuarios = [
        {
            "nombre": "admin",
            "apellido": "admin",
            "email": "admin@admin.com",
            "contrasena": "admin",
            "id_rol": await get_role_id("ADMINISTRADOR"),
        },
        {
            "nombre": "estudiante",
            "apellido": "estudiante",
            "email": "estudiante@estudiante.com",
            "contrasena": "estudiante",
            "id_rol": await get_role_id("ESTUDIANTE"),
        },
        {
            "nombre": "profesor",
            "apellido": "profesor",
            "email": "profesor@profesor.com",
            "contrasena": "profesor",
            "id_rol": await get_role_id("PROFESOR"),
        },
    ]

    results = []
    for u in usuarios:
        user = await UserService.get_by_email(db, u["email"])
        if not user:
            user = await UserService.create(db, UserCreate(**u))
            results.append({"email": user.email, "id_usuario": user.id_usuario})
        else:
            results.append(
                {
                    "email": user.email,
                    "id_usuario": user.id_usuario,
                    "msg": "Ya existía",
                }
            )
    return results
