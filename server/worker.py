"""单进程串行任务 Worker。"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from datetime import datetime, timezone

from sqlalchemy import func, select

from .checkin_runner import RunnerResult, run_checkin, safe_error_message
from .config import Settings
from .database import Database
from .feishu import send_message
from .jobs import claim_next
from .models import Account, Run
from .security import CredentialCipher
from .settings_store import get_setting, set_setting


log = logging.getLogger(__name__)


def _try_batch_notification(db, cipher: CredentialCipher, run: Run) -> None:
    if run.trigger != "automatic" or not run.batch_key:
        return
    pending = db.scalar(
        select(func.count(Run.id)).where(
            Run.batch_key == run.batch_key,
            Run.status.in_(("queued", "running")),
        )
    )
    if pending:
        return
    if get_setting(db, cipher, "last_notified_batch") == run.batch_key:
        return
    webhook = get_setting(db, cipher, "feishu_webhook")
    if not webhook:
        return
    secret = get_setting(db, cipher, "feishu_secret")
    rows = db.execute(
        select(Run.status, func.count(Run.id))
        .where(Run.batch_key == run.batch_key)
        .group_by(Run.status)
    ).all()
    counts = dict(rows)
    total = sum(counts.values())
    lines = [
        f"**批次** {run.batch_key.removeprefix('auto:')}",
        f"**总计** {total}",
        f"**成功** {counts.get('success', 0) + counts.get('already_checked', 0)}",
        f"**失败** {counts.get('failed', 0) + counts.get('out_of_time', 0)}",
    ]
    send_message(webhook, "SWU 新生打卡日报", lines, secret=secret)
    set_setting(db, cipher, "last_notified_batch", run.batch_key)
    db.commit()


def _try_manual_notification(db, cipher: CredentialCipher, run: Run, alias: str) -> None:
    if run.trigger == "automatic":
        return
    if get_setting(db, cipher, "notify_manual_runs", "false") != "true":
        return
    webhook = get_setting(db, cipher, "feishu_webhook")
    if not webhook:
        return
    secret = get_setting(db, cipher, "feishu_secret")
    label = {
        "success": "成功",
        "already_checked": "今日已打卡",
        "failed": "失败",
        "out_of_time": "非打卡时段",
    }.get(run.status, run.status)
    send_message(
        webhook,
        "SWU 手动打卡结果",
        [f"**账号** {alias}", f"**结果** {label}", f"**说明** {run.message or '—'}"],
        secret=secret,
    )


def process_one(
    database: Database,
    cipher: CredentialCipher,
    settings: Settings,
    *,
    runner: Callable[..., RunnerResult] = run_checkin,
    sleeper: Callable[[float], None] = time.sleep,
) -> bool:
    with database.session() as db:
        run = claim_next(db)
        if run is None:
            return False
        account = db.get(Account, run.account_id)
        if account is None or not account.enabled:
            run.status = "failed"
            run.message = "账号不存在或已停用"
            run.finished_at = datetime.now(timezone.utc)
            db.commit()
            return True
        username = cipher.decrypt(account.username_encrypted)
        password = cipher.decrypt(account.password_encrypted)
        max_attempts = 2 if run.trigger == "automatic" else 1
        for attempt in range(1, max_attempts + 1):
            run.attempt_count = attempt
            db.commit()
            try:
                result = runner(
                    username,
                    password,
                    timeout_seconds=settings.browser_timeout_seconds,
                )
                run.status = result.status
                run.message = result.message
                run.checkin_time = result.checkin_time
                break
            except Exception as exc:
                message = safe_error_message(exc, username, password)
                if attempt < max_attempts:
                    sleeper(settings.automatic_retry_delay_seconds)
                    continue
                run.status = "out_of_time" if "不在打卡时间" in message else "failed"
                run.message = message
        run.finished_at = datetime.now(timezone.utc)
        db.commit()
        try:
            _try_batch_notification(db, cipher, run)
            _try_manual_notification(db, cipher, run, account.alias)
        except Exception:
            log.exception("飞书通知发送失败")
        return True


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    settings = Settings.from_env()
    database = Database(settings.database_url)
    database.create_all()
    cipher = CredentialCipher(settings.master_key)
    log.info("串行任务 Worker 已启动")
    while True:
        if not process_one(database, cipher, settings):
            time.sleep(settings.worker_poll_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
