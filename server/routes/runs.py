"""手动执行、失败重试与运行记录。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from ..dependencies import CsrfAdmin, CurrentAdmin, DbSession
from ..jobs import enqueue_accounts, enqueue_all, enqueue_failed
from ..models import Account, AuditEvent, Run
from ..schemas import RunResponse


router = APIRouter(prefix="/api/runs", tags=["runs"])


def _response(run: Run, alias: str | None = None) -> RunResponse:
    data = RunResponse.model_validate(run).model_dump()
    data["account_alias"] = alias or (run.account.alias if run.account else None)
    return RunResponse(**data)


@router.get("", response_model=list[RunResponse])
def list_runs(
    _admin: CurrentAdmin,
    db: DbSession,
    limit: int = Query(default=100, ge=1, le=500),
):
    runs = db.scalars(select(Run).order_by(Run.created_at.desc()).limit(limit)).all()
    return [_response(run) for run in runs]


@router.post("/account/{account_id}", response_model=list[RunResponse], status_code=status.HTTP_202_ACCEPTED)
def run_account(account_id: int, admin: CsrfAdmin, db: DbSession):
    account = db.get(Account, account_id)
    if account is None or not account.enabled:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "账号不存在或已停用")
    created = enqueue_accounts(db, [account_id], trigger="manual")
    if not created:
        raise HTTPException(status.HTTP_409_CONFLICT, "该账号已有任务正在执行")
    db.add(AuditEvent(actor=admin.username, action="run.account", target_type="account", target_id=str(account_id)))
    db.commit()
    return [_response(run, account.alias) for run in created]


@router.post("/all", response_model=list[RunResponse], status_code=status.HTTP_202_ACCEPTED)
def run_all(admin: CsrfAdmin, db: DbSession):
    created = enqueue_all(db, trigger="manual_bulk")
    db.add(AuditEvent(actor=admin.username, action="run.all", detail=f"queued={len(created)}"))
    db.commit()
    return [_response(run) for run in created]

@router.post("/failed", response_model=list[RunResponse], status_code=status.HTTP_202_ACCEPTED)
def retry_failed(admin: CsrfAdmin, db: DbSession):
    created = enqueue_failed(db)
    db.add(AuditEvent(actor=admin.username, action="run.failed", detail=f"queued={len(created)}"))
    db.commit()
    return [_response(run) for run in created]
