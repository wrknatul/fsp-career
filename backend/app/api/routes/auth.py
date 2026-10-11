from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import AppSettings, CurrentUser, DbSession
from app.core.config import Settings
from app.core.errors import AppError, error_responses, field_validation_error
from app.core.security import (
    burn_password_check,
    create_access_token,
    hash_password,
    verify_password,
)
from app.core.timeutil import utcnow
from app.models import Candidate, Employer, User
from app.schemas.auth import AuthResponse, LoginRequest, RegisterRequest
from app.schemas.common import User as UserSchema

router = APIRouter(prefix="/auth", tags=["Авторизация"])


def _find_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email))


def _auth_response(user: User, settings: Settings) -> AuthResponse:
    return AuthResponse(
        access_token=create_access_token(user.id, user.role, settings),
        user=UserSchema.model_validate(user),
    )


def _email_taken() -> AppError:
    return AppError("EMAIL_TAKEN", "Эта почта уже зарегистрирована", 409)


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=201,
    summary="Регистрация",
    description=(
        "Создаёт аккаунт соискателя или работодателя и сразу возвращает токен. "
        "Нужно явно согласиться на обработку персональных данных (`consent: true`). "
        "Для соискателя `show_profile` определяет, виден ли профиль работодателям "
        "(по умолчанию нет). Для работодателя обязательно `company_name`. "
        "Почта приводится к нижнему регистру."
    ),
    responses=error_responses(
        {
            409: "EMAIL_TAKEN — такая почта уже зарегистрирована",
            422: "VALIDATION_ERROR — данные не прошли проверку; "
            "CONSENT_REQUIRED — нет согласия на обработку данных",
        }
    ),
)
def register(body: RegisterRequest, db: DbSession, settings: AppSettings) -> AuthResponse:
    if body.consent is not True:
        raise AppError(
            "CONSENT_REQUIRED",
            "Для регистрации нужно согласие на обработку персональных данных",
            422,
        )
    if body.role == "employer" and not body.company_name:
        raise field_validation_error(
            [(["body", "company_name"], "Укажите название компании")],
        )
    if _find_user_by_email(db, body.email) is not None:
        raise _email_taken()

    now = utcnow()
    user = User(
        email=body.email,
        password_hash=hash_password(body.password, settings.BCRYPT_ROUNDS),
        role=body.role,
        full_name=body.full_name,
        consent_at=now,
        created_at=now,
    )
    if body.role == "candidate":
        user.candidate = Candidate(
            work_formats=[],
            relocation=False,
            visible=body.show_profile,
            category=None,
            updated_at=now,
        )
    else:
        # The contract has no way to edit the employer profile, so the contacts shown after an
        # accepted offer start as the account holder's name and e-mail.
        user.employer = Employer(
            company_name=body.company_name or "",
            contact_name=body.full_name,
            contact_email=body.email,
            verified=False,
        )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        # Lost a race against a parallel registration with the same e-mail.
        db.rollback()
        raise _email_taken() from exc
    return _auth_response(user, settings)


@router.post(
    "/login",
    response_model=AuthResponse,
    summary="Вход",
    description="Проверяет почту и пароль и возвращает токен доступа.",
    responses=error_responses(
        {
            401: "INVALID_CREDENTIALS — неверная почта или пароль",
            422: "VALIDATION_ERROR — данные не прошли проверку",
        }
    ),
)
def login(body: LoginRequest, db: DbSession, settings: AppSettings) -> AuthResponse:
    user = _find_user_by_email(db, body.email)
    if user is None:
        # Same work as for a real account, so the response time does not reveal the e-mail.
        burn_password_check(body.password, settings.BCRYPT_ROUNDS)
    elif verify_password(body.password, user.password_hash):
        return _auth_response(user, settings)
    raise AppError("INVALID_CREDENTIALS", "Неверная почта или пароль", 401)


@router.get(
    "/me",
    response_model=UserSchema,
    summary="Текущий пользователь",
    description="Возвращает аккаунт, которому принадлежит токен.",
    responses=error_responses({401: "UNAUTHORIZED — нет токена, он неверный или истёк"}),
)
def me(user: CurrentUser) -> UserSchema:
    return UserSchema.model_validate(user)
