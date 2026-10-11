"""Shared FastAPI dependencies: settings, database session and the current user."""

from __future__ import annotations

from typing import Annotated

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError, unauthorized
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models import Candidate, Employer, User

# auto_error=False: a missing header must produce our own 401 in the unified format.
bearer_scheme = HTTPBearer(
    auto_error=False,
    description="Токен из `/auth/login` или `/auth/register`: `Authorization: Bearer <token>`",
)


def get_app_settings(request: Request) -> Settings:
    """Settings of the running application (`create_app(settings)`)."""
    return request.app.state.settings


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> User:
    """The user behind the bearer token; 401 `UNAUTHORIZED` for anything wrong with it."""
    if credentials is None or not credentials.credentials:
        raise unauthorized()
    try:
        payload = decode_access_token(credentials.credentials, settings)
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, ValueError, KeyError) as exc:
        raise unauthorized("Токен недействителен или истёк") from exc
    user = db.get(User, user_id)
    if user is None:
        raise unauthorized("Токен недействителен или истёк")
    return user


def require_candidate(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Candidate:
    """The current user's candidate row; 403 `FORBIDDEN` for other roles."""
    if user.role != "candidate":
        raise AppError("FORBIDDEN", "Доступно только соискателям", 403)
    candidate = db.scalar(select(Candidate).where(Candidate.user_id == user.id))
    if candidate is None:
        raise AppError("NOT_FOUND", "Профиль соискателя не найден", 404)
    return candidate


def require_employer(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Employer:
    """The current user's employer row; 403 `FORBIDDEN` for other roles."""
    if user.role != "employer":
        raise AppError("FORBIDDEN", "Доступно только работодателям", 403)
    employer = db.scalar(select(Employer).where(Employer.user_id == user.id))
    if employer is None:
        raise AppError("NOT_FOUND", "Профиль работодателя не найден", 404)
    return employer


DbSession = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_app_settings)]
CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentCandidate = Annotated[Candidate, Depends(require_candidate)]
CurrentEmployer = Annotated[Employer, Depends(require_employer)]
