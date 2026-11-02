"""FastAPI 依赖：数据库、管理员会话和 CSRF。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Admin, AdminSession
from .security import hash_token


SESSION_COOKIE = "checkin_session"
CSRF_COOKIE = "checkin_csrf"


def get_db(request: Request):
    with request.app.state.database.session_factory() as session:
        yield session


DbSession = Annotated[Session, Depends(get_db)]


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def get_admin_session(
    request: Request,
    db: DbSession,
) -> tuple[Admin, AdminSession]:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "尚未登录")
    record = db.scalar(
        select(AdminSession).where(AdminSession.token_hash == hash_token(token))
    )
    if record is None or _as_utc(record.expires_at) <= datetime.now(timezone.utc):
        if record is not None:
            db.delete(record)
            db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "会话已过期")
    admin = db.get(Admin, record.admin_id)
    if admin is None or admin.disabled:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "管理员不可用")
    return admin, record


def get_current_admin(
    pair: Annotated[tuple[Admin, AdminSession], Depends(get_admin_session)],
) -> Admin:
    return pair[0]


def require_csrf(
    request: Request,
    pair: Annotated[tuple[Admin, AdminSession], Depends(get_admin_session)],
) -> Admin:
    token = request.headers.get("X-CSRF-Token", "")
    if not token or hash_token(token) != pair[1].csrf_hash:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "CSRF 校验失败")
    return pair[0]


CurrentAdmin = Annotated[Admin, Depends(get_current_admin)]
CsrfAdmin = Annotated[Admin, Depends(require_csrf)]
