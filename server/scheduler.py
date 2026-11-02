"""每天由 systemd timer 调用一次的幂等入队入口。"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from .config import Settings
from .database import Database
from .jobs import enqueue_all


def enqueue_daily(database: Database, now: datetime | None = None) -> int:
    local_now = now or datetime.now(ZoneInfo("Asia/Shanghai"))
    batch_key = f"auto:{local_now.date().isoformat()}"
    with database.session() as db:
        return len(enqueue_all(db, trigger="automatic", batch_key=batch_key))


def main() -> int:
    settings = Settings.from_env()
    database = Database(settings.database_url)
    database.create_all()
    count = enqueue_daily(database)
    print(f"今日自动任务已入队: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
