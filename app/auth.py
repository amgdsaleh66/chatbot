"""
auth.py - المصادقة باستخدام JWT
"""
from datetime import datetime, timedelta
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .models import AsyncSessionLocal, User, get_db

# ─── Password Hashing ──────────────────────────────────────────────
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


# ─── JWT ───────────────────────────────────────────────────────────

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode["exp"] = expire
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="انتهت صلاحية الرمز، يرجى تسجيل الدخول مجدداً",
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="رمز مصادقة غير صالح",
        )


# ─── Dependencies ──────────────────────────────────────────────────

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """FastAPI dependency - يتحقق من JWT في HTTP requests"""
    payload = decode_token(credentials.credentials)
    username: str = payload.get("sub", "")
    if not username:
        raise HTTPException(status_code=401, detail="بيانات الرمز غير صالحة")

    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="المستخدم غير موجود أو غير نشط")
    return user


async def get_current_user_ws(token: str, db: AsyncSession) -> Optional[User]:
    """للاستخدام داخل WebSocket (لا يستخدم Depends)"""
    try:
        payload = decode_token(token)
        username: str = payload.get("sub", "")
        if not username:
            return None
        result = await db.execute(select(User).where(User.username == username))
        user = result.scalar_one_or_none()
        return user if (user and user.is_active) else None
    except HTTPException:
        return None
    except Exception:
        return None