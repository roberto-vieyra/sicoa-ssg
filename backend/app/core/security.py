from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select

from backend.app.db.models import User

hasher = PasswordHasher()
bearer = HTTPBearer(auto_error=False)
DUMMY_HASH = hasher.hash("invalid-account-timing-guard")


def get_db(request: Request):
    with request.app.state.sessions() as session:
        yield session


def verify_password(password, encoded):
    try:
        return hasher.verify(encoded, password)
    except (VerificationError, InvalidHashError):
        return False


def issue_token(user, settings):
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": user.username,
            "iat": now,
            "nbf": now,
            "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
            "iss": "sicoa-ssg",
            "aud": "sicoa-ssg-lan",
        },
        settings.jwt_secret,
        algorithm="HS256",
    )


def current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db=Depends(get_db),
):
    denied = HTTPException(
        401, "Sesión inválida o expirada.", headers={"WWW-Authenticate": "Bearer"}
    )
    if not credentials:
        raise denied
    try:
        payload = jwt.decode(
            credentials.credentials,
            request.app.state.settings.jwt_secret,
            algorithms=["HS256"],
            issuer="sicoa-ssg",
            audience="sicoa-ssg-lan",
            options={"require": ["sub", "exp", "iat", "nbf"]},
        )
    except jwt.PyJWTError as error:
        raise denied from error
    user = db.scalar(select(User).where(User.username == payload["sub"], User.active.is_(True)))
    if user is None:
        raise denied
    return user


def require_dispatcher(user):
    if user.role not in {"Administrador", "Oficialia_Despachador"}:
        raise HTTPException(403, "Se requiere el rol Administrador u Oficialía.")


def check_scope(user, record):
    if user.role == "Responsable_Area" and record.area_asignada != user.area:
        raise HTTPException(403, "Este oficio pertenece a otra área.")


def require_writer(user, record=None):
    if user.role == "Auditor":
        raise HTTPException(403, "El rol Auditor es de consulta.")
    if record is not None:
        check_scope(user, record)
