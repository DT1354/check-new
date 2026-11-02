"""一次性邀请与公开录入。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select

from ..dependencies import CsrfAdmin, CurrentAdmin, DbSession
from ..models import Account, AuditEvent, Invite
from ..schemas import (
    AccountResponse,
    InviteCreate,
    InviteCreated,
    InviteEnroll,
    InviteResponse,
)
from ..security import generate_token, hash_token
from .accounts import _hint


router = APIRouter(prefix="/api/invites", tags=["invites"])


def _serialize(invite: Invite) -> InviteResponse:
    return InviteResponse.model_validate(invite, from_attributes=True)


@router.get("", response_model=list[InviteResponse])
def list_invites(_admin: CurrentAdmin, db: DbSession):
    records = db.scalars(select(Invite).order_by(Invite.created_at.desc())).all()
    return [_serialize(record) for record in records]


@router.post("", response_model=InviteCreated, status_code=status.HTTP_201_CREATED)
def create_invite(payload: InviteCreate, admin: CsrfAdmin, request: Request, db: DbSession):
    token = generate_token()
    now = datetime.now(timezone.utc)
    invite = Invite(
        token_hash=hash_token(token),
        expires_at=now + timedelta(hours=payload.expires_in_hours),
        created_by=admin.id,
    )
    db.add(invite)
    db.flush()
    db.add(AuditEvent(actor=admin.username, action="invite.create", target_type="invite", target_id=str(invite.id)))
    db.commit()
    db.refresh(invite)
    data = _serialize(invite).model_dump()
    data["invite_url"] = f"{request.app.state.settings.frontend_origin}/invite/{token}"
    return InviteCreated(**data)


@router.post("/{invite_id}/revoke", response_model=InviteResponse)
def revoke_invite(invite_id: int, admin: CsrfAdmin, db: DbSession):
    invite = db.get(Invite, invite_id)
    if invite is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "邀请不存在")
    if invite.used_at is None:
        invite.revoked_at = datetime.now(timezone.utc)
    db.add(AuditEvent(actor=admin.username, action="invite.revoke", target_type="invite", target_id=str(invite.id)))
    db.commit()
    db.refresh(invite)
    return _serialize(invite)


def _valid_invite(token: str, db: DbSession) -> Invite:
    invite = db.scalar(select(Invite).where(Invite.token_hash == hash_token(token)))
    now = datetime.now(timezone.utc)
    if invite is None or invite.used_at is not None or invite.revoked_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "邀请无效或已使用")
    expires_at = invite.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= now:
        raise HTTPException(status.HTTP_410_GONE, "邀请已过期")
    return invite


@router.get("/{token}/status")
def invite_status(token: str, db: DbSession):
    invite = _valid_invite(token, db)
    return {"valid": True, "expires_at": invite.expires_at}


@router.post("/{token}/enroll", response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
def enroll(token: str, payload: InviteEnroll, request: Request, db: DbSession):
    host = request.client.host if request.client else "unknown"
    if not request.app.state.rate_limiter.allow(f"invite:{host}", limit=10, window_seconds=600):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "尝试次数过多，请稍后再试")
    invite = _valid_invite(token, db)
    cipher = db.info["credential_cipher"]
    username = payload.username.strip()
    account = Account(
        alias=payload.alias.strip(),
        username_encrypted=cipher.encrypt(username),
        password_encrypted=cipher.encrypt(payload.password),
        username_hint=_hint(username),
        enabled=True,
    )
    db.add(account)
    db.flush()
    invite.used_at = datetime.now(timezone.utc)
    invite.account_id = account.id
    db.add(AuditEvent(actor="invite", action="account.enroll", target_type="account", target_id=str(account.id)))
    db.commit()
    db.refresh(account)
    return account
