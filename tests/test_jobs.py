import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from server.checkin_runner import RunnerResult
from server.config import Settings
from server.database import Database
from server.jobs import enqueue_accounts, enqueue_all
from server.models import Account, Run
from server.scheduler import enqueue_daily
from server.security import CredentialCipher, generate_master_key
from server.worker import process_one


class JobTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        database_path = Path(self.temporary_directory.name) / "jobs.db"
        self.master_key = generate_master_key()
        self.cipher = CredentialCipher(self.master_key)
        self.database = Database(f"sqlite:///{database_path.as_posix()}")
        self.database.create_all()
        self.settings = Settings(
            environment="test",
            database_url=f"sqlite:///{database_path.as_posix()}",
            frontend_origin="http://localhost:5173",
            master_key=self.master_key,
            cookie_secure=False,
            automatic_retry_delay_seconds=0,
        )
        with self.database.session() as db:
            for index in range(2):
                db.add(
                    Account(
                        alias=f"同学 {index}",
                        username_encrypted=self.cipher.encrypt(f"user{index}"),
                        password_encrypted=self.cipher.encrypt(f"pass{index}"),
                        username_hint=f"••••{index}",
                    )
                )
            db.commit()

    def tearDown(self) -> None:
        self.database.engine.dispose()
        self.temporary_directory.cleanup()

    def test_duplicate_active_account_is_not_enqueued(self) -> None:
        with self.database.session() as db:
            first = enqueue_accounts(db, [1], trigger="manual")
            second = enqueue_accounts(db, [1], trigger="manual")
            self.assertEqual(len(first), 1)
            self.assertEqual(second, [])

    def test_daily_enqueue_is_idempotent(self) -> None:
        now = datetime(2026, 11, 2, 21, 5, tzinfo=ZoneInfo("Asia/Shanghai"))
        self.assertEqual(enqueue_daily(self.database, now), 2)
        self.assertEqual(enqueue_daily(self.database, now), 0)

    def test_automatic_failure_retries_once_with_fresh_calls(self) -> None:
        with self.database.session() as db:
            enqueue_all(db, trigger="automatic", batch_key="auto:2026-11-02")
        calls = []

        def runner(username, password, **_kwargs):
            calls.append((username, password))
            if len(calls) == 1:
                raise RuntimeError(f"temporary failure for {username}")
            return RunnerResult("success", "打卡成功", "21:05")

        processed = process_one(
            self.database,
            self.cipher,
            self.settings,
            runner=runner,
            sleeper=lambda _seconds: None,
        )
        self.assertTrue(processed)
        self.assertEqual(len(calls), 2)
        with self.database.session() as db:
            run = db.scalar(__import__("sqlalchemy").select(Run).order_by(Run.id))
            self.assertEqual(run.status, "success")
            self.assertEqual(run.attempt_count, 2)

    def test_manual_failure_does_not_retry_or_leak_credentials(self) -> None:
        with self.database.session() as db:
            enqueue_accounts(db, [1], trigger="manual")
        calls = 0

        def runner(username, password, **_kwargs):
            nonlocal calls
            calls += 1
            raise RuntimeError(f"bad credentials {username} {password}")

        process_one(self.database, self.cipher, self.settings, runner=runner)
        self.assertEqual(calls, 1)
        with self.database.session() as db:
            run = db.scalar(__import__("sqlalchemy").select(Run))
            self.assertEqual(run.status, "failed")
            self.assertNotIn("user0", run.message)
            self.assertNotIn("pass0", run.message)


if __name__ == "__main__":
    unittest.main()
