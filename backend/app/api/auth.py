"""Register, sign in, refresh, sign out."""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from ..core.auth import current_user
from ..core.config import settings
from ..core.database import get_db
from ..core.security import (
    ACCESS_TOKEN_MINUTES, AuthError, MIN_PASSWORD_CHARS, create_access_token,
    create_refresh_token, decode_token, hash_password, verify_password,
)
from ..models.users import User, UserRole

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["Auth"])


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=MIN_PASSWORD_CHARS)
    display_name: str = ""


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


def _tokens(user: User) -> dict:
    return {
        "access_token": create_access_token(user.id, user.role),
        "refresh_token": create_refresh_token(user.id, user.token_version),
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_MINUTES * 60,
    }


def _public(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name or "",
        "role": user.role,
    }


@router.post("/register", status_code=201)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    """Create an account.

    The first account to exist becomes the admin: someone has to be able
    to ingest sources and generate content, and there is no bootstrap step
    otherwise. Every account after it is a student.
    """
    if not settings.auth_configured:
        raise HTTPException(503, "Authentication is not configured on this server")

    email = payload.email.lower().strip()
    if db.query(User.id).filter(User.email == email).first():
        raise HTTPException(409, "An account with that email already exists")

    try:
        password_hash = hash_password(payload.password)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    first = db.query(User.id).first() is None
    user = User(
        email=email,
        display_name=payload.display_name.strip()[:120],
        password_hash=password_hash,
        role=UserRole.ADMIN if first else UserRole.STUDENT,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    logger.info("Registered %s as %s", email, user.role)
    return {"user": _public(user), **_tokens(user)}


@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """Exchange an email and password for tokens."""
    if not settings.auth_configured:
        raise HTTPException(503, "Authentication is not configured on this server")

    user = db.query(User).filter(User.email == payload.email.lower().strip()).first()

    # The password is verified even when no account matched, so the reply
    # takes the same time either way and does not reveal which emails are
    # registered.
    placeholder = "$2b$12$" + "." * 53
    ok = verify_password(payload.password, user.password_hash if user else placeholder)

    if user is None or not ok or not user.is_active:
        raise HTTPException(401, "That email and password do not match")

    user.last_login_at = datetime.utcnow()
    db.commit()
    return {"user": _public(user), **_tokens(user)}


@router.post("/refresh")
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    """Trade a refresh token for a new access token.

    The token's version must still match the account's. That is what makes
    "sign out everywhere" work without a blacklist to store and sweep.
    """
    try:
        claims = decode_token(payload.refresh_token, expect="refresh")
    except AuthError as exc:
        raise HTTPException(401, str(exc)) from exc

    user = db.query(User).filter(User.id == int(claims["sub"])).first()
    if user is None or not user.is_active:
        raise HTTPException(401, "That session is no longer valid")
    if claims.get("ver") != user.token_version:
        raise HTTPException(401, "That session was signed out")

    return {"user": _public(user), **_tokens(user)}


@router.post("/logout", status_code=204)
def logout(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Sign out of every device.

    Bumping the version invalidates all refresh tokens at once. Access
    tokens already issued stay valid until they expire, which is the
    trade-off that keeps authorisation free of a database read.
    """
    user.token_version = (user.token_version or 0) + 1
    db.commit()


@router.get("/me")
def me(user: User = Depends(current_user)):
    return _public(user)
