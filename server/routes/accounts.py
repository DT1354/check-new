"""加密保存的学校账号管理。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from ..dependencies import CsrfAdmin, CurrentAdmin, DbSession
from ..models import Account, AuditEvent
from ..schemas import AccountCreate, AccountResponse, AccountUpdate


router = APIRouter(prefix="/api/accounts", tags=["accounts"])


def _hint(username: str) -> str:
    return f"••••{username[-4:]}" if len(username) > 4 else "••••"


@router.get("", response_model=list[AccountResponse])
def list_accounts(_admin: CurrentAdmin, db: DbSession):
    return list(db.scalars(select(Account).order_by(Account.created_at.desc())))


@router.post("", response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
def create_account(payload: AccountCreate, admin: CsrfAdmin, db: DbSession):
    credential_cipher = db.info["credential_cipher"]
    account = Account(
        alias=payload.alias.strip(),
        username_encrypted=credential_cipher.encrypt(payload.username.strip()),
        password_encrypted=credential_cipher.encrypt(payload.password),
        username_hint=_hint(payload.username.strip()),
        enabled=payload.enabled,
    )
    db.add(account)
    db.flush()
    db.add(AuditEvent(actor=admin.username, action="account.create", target_type="account", target_id=str(account.id)))
    db.commit()
    db.refresh(account)
    return account


@router.patch("/{account_id}", response_model=AccountResponse)
def update_account(account_id: int, payload: AccountUpdate, admin: CsrfAdmin, db: DbSession):
    account = db.get(Account, account_id)
    if account is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "账号不存在")
    cipher = db.info["credential_cipher"]
    if payload.alias is not None:
        account.alias = payload.alias.strip()
    if payload.username is not None:
        username = payload.username.strip()
        account.username_encrypted = cipher.encrypt(username)
        account.username_hint = _hint(username)
    if payload.password is not None:
        account.password_encrypted = cipher.encrypt(payload.password)
    if payload.enabled is not None:
        account.enabled = payload.enabled
    db.add(AuditEvent(actor=admin.username, action="account.update", target_type="account", target_id=str(account.id)))
    db.commit()
    db.refresh(account)
    return account


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(account_id: int, admin: CsrfAdmin, db: DbSession):
    account = db.get(Account, account_id)
    if account is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "账号不存在")
    db.add(AuditEvent(actor=admin.username, action="account.delete", target_type="account", target_id=str(account.id)))
    db.delete(account)
    db.commit()
