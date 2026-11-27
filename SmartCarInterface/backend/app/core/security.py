import os
from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import jwt, JWTError
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.entities import User

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "super_tajny_klucz_jwt_smart_car_interface")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
# Wskazuje na endpoint formularzowy OAuth2 (kompatybilny z przyciskiem "Authorize" w Swagger UI)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token", auto_error=False)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_user_from_token_str(token: Optional[str], db: Session) -> Optional[User]:
    """Dekoduje surowy token JWT i zwraca aktywnego uzytkownika z bazy (lub None)."""
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: Optional[str] = payload.get("sub")
        if not username:
            return None
    except JWTError:
        return None

    user = db.query(User).filter(User.username == username).first()
    if not user or not user.is_active:
        return None
    return user


def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Weryfikuje naglowek Authorization: Bearer <JWT> i zwraca zalogowanego uzytkownika."""
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Brak tokenu autoryzacyjnego. Zaloguj sie, aby uzyskac dostep.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: Optional[str] = payload.get("sub")
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Nieprawidlowy token autoryzacyjny.",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token wygasl lub jest nieprawidlowy.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Uzytkownik przypisany do tokenu nie istnieje.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Konto uzytkownika jest nieaktywne.",
        )
    return user


def require_driver_or_admin(current_user: User = Depends(get_current_user)) -> User:
    """Wymaga roli 'driver' lub 'admin' (blokuje role 'guest' przeznaczona tylko do odczytu)."""
    if current_user.role not in ("admin", "driver"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Brak uprawnien do sterowania pojazdem (wymagana rola: driver lub admin).",
        )
    return current_user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Wymaga roli administratora ('admin')."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Wymagane uprawnienia administratora.",
        )
    return current_user
