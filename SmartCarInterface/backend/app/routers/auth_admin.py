from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import (
    get_password_hash,
    verify_password,
    create_access_token,
    require_admin,
)
from app.models.entities import User
from app.schemas.dto import UserCreate, UserLogin, UserResponse, UserStatusUpdate

router = APIRouter(prefix="/api", tags=["Użytkownicy i Panel Administratora"])


@router.post("/auth/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register_user(payload: UserCreate, db: Session = Depends(get_db)):
    """Rejestracja nowego konta użytkownika w systemie."""
    existing = (
        db.query(User)
        .filter((User.username == payload.username) | (User.email == payload.email))
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Użytkownik o podanym loginie lub adresie e-mail już istnieje."
        )

    user = User(
        username=payload.username,
        email=payload.email,
        password_hash=get_password_hash(payload.password),
        role="driver",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/auth/login")
def login_user(payload: UserLogin, db: Session = Depends(get_db)):
    """Logowanie użytkownika i generowanie tokenu JWT."""
    user = db.query(User).filter(User.username == payload.username).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nieprawidłowa nazwa użytkownika lub hasło."
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Konto zostało dezaktywowane przez administratora."
        )

    token = create_access_token({"sub": user.username, "role": user.role, "user_id": user.id})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role,
            "is_active": user.is_active,
        },
    }


@router.get("/admin/users", response_model=List[UserResponse])
def list_all_users(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """[Panel Administratora] Pobiera spis wszystkich zarejestrowanych użytkowników."""
    return db.query(User).order_by(User.id.asc()).all()


@router.patch("/admin/users/{user_id}/status", response_model=UserResponse)
def change_user_status(
    user_id: int,
    payload: UserStatusUpdate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """[Panel Administratora] Zmienia status użytkownika (aktywny / nieaktywny) oraz opcjonalnie rolę."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Użytkownik nie istnieje.")

    user.is_active = payload.is_active
    if payload.role:
        user.role = payload.role

    db.commit()
    db.refresh(user)
    return user
