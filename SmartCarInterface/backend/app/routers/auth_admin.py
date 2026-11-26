from typing import List
from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import (
    get_password_hash,
    verify_password,
    create_access_token,
    get_current_user,
    require_admin,
)
from app.models.entities import User
from app.schemas.dto import UserCreate, UserLogin, UserResponse, UserStatusUpdate

router = APIRouter(prefix="/api", tags=["Użytkownicy, Autoryzacja i Panel Administratora"])


def _authenticate_and_issue_token(username: str, password: str, db: Session) -> dict:
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nieprawidłowa nazwa użytkownika lub hasło.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Konto zostało dezaktywowane przez administratora.",
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


@router.post("/auth/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register_user(payload: UserCreate, db: Session = Depends(get_db)):
    """[Public] Rejestracja nowego konta użytkownika (201 Created lub 409 Conflict)."""
    existing = (
        db.query(User)
        .filter((User.username == payload.username) | (User.email == payload.email))
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Użytkownik o podanym loginie lub adresie e-mail już istnieje.",
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


@router.post("/auth/login", status_code=status.HTTP_200_OK)
def login_user(payload: UserLogin, db: Session = Depends(get_db)):
    """[Public / JSON] Logowanie użytkownika (React Native / Symulator) i wydanie tokenu JWT."""
    return _authenticate_and_issue_token(payload.username, payload.password, db)


@router.post("/auth/token", status_code=status.HTTP_200_OK)
def login_oauth2_form(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """[Public / OAuth2 Form] Logowanie formularzem kompatybilne z przyciskiem Authorize w Swagger UI."""
    return _authenticate_and_issue_token(form_data.username, form_data.password, db)


@router.get("/auth/me", response_model=UserResponse, status_code=status.HTTP_200_OK)
def get_my_profile(current_user: User = Depends(get_current_user)):
    """[JWT] Zwraca dane aktualnie zalogowanego użytkownika na podstawie tokenu Bearer."""
    return current_user


@router.get("/admin/users", response_model=List[UserResponse], status_code=status.HTTP_200_OK)
def list_all_users(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """[Panel Administratora / GET] Pobiera spis wszystkich zarejestrowanych użytkowników."""
    return db.query(User).order_by(User.id.asc()).all()


@router.get("/admin/users/{user_id}", response_model=UserResponse, status_code=status.HTTP_200_OK)
def get_user_by_id(
    user_id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """[Panel Administratora / GET] Pobiera szczegóły pojedynczego użytkownika (404 jeśli brak)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Użytkownik o ID={user_id} nie istnieje.",
        )
    return user


@router.patch("/admin/users/{user_id}/status", response_model=UserResponse, status_code=status.HTTP_200_OK)
def change_user_status(
    user_id: int,
    payload: UserStatusUpdate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """[Panel Administratora / PATCH] Zmienia status użytkownika (aktywny / nieaktywny) oraz opcjonalnie rolę."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Użytkownik o ID={user_id} nie istnieje.",
        )

    user.is_active = payload.is_active
    if payload.role:
        user.role = payload.role

    db.commit()
    db.refresh(user)
    return user


@router.delete("/admin/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """[Panel Administratora / DELETE] Usuwa konto użytkownika (204 No Content, blokuje usunięcie własnego konta)."""
    if admin.id == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Administrator nie może usunąć własnego konta.",
        )
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Użytkownik o ID={user_id} nie istnieje.",
        )
    db.delete(user)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
