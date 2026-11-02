import tempfile
import unittest
from pathlib import Path

from sqlalchemy import inspect

from server.database import Database


class DatabaseTests(unittest.TestCase):
    def test_creates_all_expected_tables_and_enables_wal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.db"
            database = Database(f"sqlite:///{path.as_posix()}")
            database.create_all()

            table_names = set(inspect(database.engine).get_table_names())
            self.assertEqual(
                table_names,
                {
                    "accounts",
                    "admins",
                    "admin_sessions",
                    "app_settings",
                    "audit_events",
                    "invites",
                    "runs",
                },
            )
            with database.engine.connect() as connection:
                mode = connection.exec_driver_sql("PRAGMA journal_mode").scalar_one()
            self.assertEqual(mode.lower(), "wal")
            database.engine.dispose()


if __name__ == "__main__":
    unittest.main()
