"""管理员登录会话。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import delete, select

from ..dependencies import (
    CSRF_COOKIE,
    CsrfAdmin,
    DbSession,
    SESSION_COOKIE,
    get_admin_session,
)
from ..models import Admin, AdminSession
from ..schemas import LoginRequest, SessionResponse
from ..security import generate_token, hash_token


router = APIRouter(prefix="/api/auth", tags=["auth"])


def _client_key(request: Request, suffix: str) -> str:
    host = request.client.host if request.client else "unknown"
    return f"{suffix}:{host}"


@router.post("/login", response_model=SessionResponse)
def login(payload: LoginRequest, request: Request, response: Response, db: DbSession):
    limiter = request.app.state.rate_limiter
    if not limiter.allow(_client_key(request, "login"), limit=10, window_seconds=600):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "尝试次数过多，请稍后再试")
    admin = db.scalar(select(Admin).where(Admin.username == payload.username))
    if (
        admin is None
        or admin.disabled
        or not request.app.state.passwords.verify(admin.password_hash, payload.password)
    ):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "用户名或密码不正确")
    now = datetime.now(timezone.utc)
    db.execute(delete(AdminSession).where(AdminSession.expires_at <= now))
    token = generate_token()
    csrf = generate_token()
    db.add(
        AdminSession(
            admin_id=admin.id,
            token_hash=hash_token(token),
            csrf_hash=hash_token(csrf),
            expires_at=now + timedelta(hours=request.app.state.settings.session_ttl_hours),
        )
    )
    db.commit()
    response.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        secure=request.app.state.settings.cookie_secure,
        samesite="lax",
        max_age=request.app.state.settings.session_ttl_hours * 3600,
        path="/",
    )
    response.set_cookie(
        CSRF_COOKIE,
        csrf,
        httponly=True,
        secure=request.app.state.settings.cookie_secure,
        samesite="lax",
        max_age=request.app.state.settings.session_ttl_hours * 3600,
        path="/",
    )
    return SessionResponse(username=admin.username, csrf_token=csrf)


@router.get("/session", response_model=SessionResponse)
def session_info(request: Request, pair=Depends(get_admin_session)):
    admin, session = pair
    csrf = request.cookies.get(CSRF_COOKIE, "")
    if not csrf or hash_token(csrf) != session.csrf_hash:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "会话信息不完整")
    return SessionResponse(username=admin.username, csrf_token=csrf)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    admin: CsrfAdmin,
    request: Request,
    db: DbSession,
):
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        db.execute(delete(AdminSession).where(AdminSession.token_hash == hash_token(token)))
        db.commit()
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")
    response.status_code = status.HTTP_204_NO_CONTENT
