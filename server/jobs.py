"""持久化任务的创建、领取与幂等控制。"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import Account, Run


ACTIVE_STATUSES = ("queued", "running")
FAILED_STATUSES = ("failed", "out_of_time")


def enqueue_accounts(
    db: Session,
    account_ids: list[int],
    *,
    trigger: str,
    batch_key: str | None = None,
) -> list[Run]:
    created: list[Run] = []
    for account_id in dict.fromkeys(account_ids):
        account = db.get(Account, account_id)
        if account is None or not account.enabled:
            continue
        active = db.scalar(
            select(Run.id).where(
                Run.account_id == account_id,
                Run.status.in_(ACTIVE_STATUSES),
            )
        )
        if active is not None:
            continue
        if batch_key is not None:
            existing_batch = db.scalar(
                select(Run.id).where(
                    Run.account_id == account_id,
                    Run.batch_key == batch_key,
                )
            )
            if existing_batch is not None:
                continue
        run = Run(
            account_id=account_id,
            trigger=trigger,
            batch_key=batch_key,
            status="queued",
        )
        db.add(run)
        db.flush()
        created.append(run)
    db.commit()
    return created


def enqueue_all(db: Session, *, trigger: str, batch_key: str | None = None) -> list[Run]:
    account_ids = list(
        db.scalars(select(Account.id).where(Account.enabled.is_(True)).order_by(Account.id))
    )
    return enqueue_accounts(db, account_ids, trigger=trigger, batch_key=batch_key)


def enqueue_failed(db: Session) -> list[Run]:
    latest_run_ids = (
        select(Run.account_id, func.max(Run.id).label("run_id"))
        .group_by(Run.account_id)
        .subquery()
    )
    latest_ids = list(
        db.scalars(
            select(Run.account_id)
            .join(latest_run_ids, Run.id == latest_run_ids.c.run_id)
            .where(Run.status.in_(FAILED_STATUSES))
            .order_by(Run.id.desc())
        )
    )
    return enqueue_accounts(db, latest_ids, trigger="manual_retry")


def claim_next(db: Session) -> Run | None:
    run = db.scalar(
        select(Run)
        .where(Run.status == "queued")
        .order_by(Run.created_at, Run.id)
        .limit(1)
    )
    if run is None:
        return None
    run.status = "running"
    run.started_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(run)
    return run
