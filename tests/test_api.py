import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from server.app import create_app
from server.config import Settings
from server.models import Admin, Invite
from server.security import PasswordService, generate_master_key


class ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        database_path = Path(self.temporary_directory.name) / "api.db"
        settings = Settings(
            environment="test",
            database_url=f"sqlite:///{database_path.as_posix()}",
            frontend_origin="http://localhost:5173",
            master_key=generate_master_key(),
            cookie_secure=False,
        )
        self.app = create_app(settings)
        self.client_context = TestClient(self.app)
        self.client = self.client_context.__enter__()
        with self.app.state.database.session() as db:
            db.add(Admin(username="owner", password_hash=PasswordService().hash("very-secure-password")))
            db.commit()

    def tearDown(self) -> None:
        self.client_context.__exit__(None, None, None)
        self.temporary_directory.cleanup()

    def login(self) -> str:
        response = self.client.post(
            "/api/auth/login",
            json={"username": "owner", "password": "very-secure-password"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn("HttpOnly", response.headers["set-cookie"])
        return response.json()["csrf_token"]

    def test_authentication_and_csrf(self) -> None:
        self.assertEqual(self.client.get("/api/accounts").status_code, 401)
        csrf = self.login()
        self.assertEqual(self.client.get("/api/accounts").status_code, 200)
        without_csrf = self.client.post(
            "/api/accounts",
            json={"alias": "A", "username": "20260001", "password": "secret"},
        )
        self.assertEqual(without_csrf.status_code, 403)
        logout = self.client.post("/api/auth/logout", headers={"X-CSRF-Token": csrf})
        self.assertEqual(logout.status_code, 204)
        self.assertEqual(self.client.get("/api/accounts").status_code, 401)

    def test_account_credentials_are_encrypted_and_never_returned(self) -> None:
        csrf = self.login()
        response = self.client.post(
            "/api/accounts",
            headers={"X-CSRF-Token": csrf},
            json={"alias": "同学 A", "username": "2026123456", "password": "plain-password"},
        )
        self.assertEqual(response.status_code, 201, response.text)
        serialized = response.text
        self.assertNotIn("2026123456", serialized)
        self.assertNotIn("plain-password", serialized)
        self.assertEqual(response.json()["username_hint"], "••••3456")

        with self.app.state.database.session() as db:
            from server.models import Account

            account = db.get(Account, response.json()["id"])
            self.assertNotEqual(account.username_encrypted, "2026123456")
            self.assertNotEqual(account.password_encrypted, "plain-password")
            self.assertEqual(self.app.state.cipher.decrypt(account.username_encrypted), "2026123456")

    def test_invite_is_single_use(self) -> None:
        csrf = self.login()
        created = self.client.post(
            "/api/invites",
            headers={"X-CSRF-Token": csrf},
            json={"expires_in_hours": 24},
        )
        self.assertEqual(created.status_code, 201, created.text)
        token = created.json()["invite_url"].rsplit("/", 1)[-1]
        enrolled = self.client.post(
            f"/api/invites/{token}/enroll",
            json={"alias": "新同学", "username": "20269999", "password": "secret"},
        )
        self.assertEqual(enrolled.status_code, 201, enrolled.text)
        repeated = self.client.post(
            f"/api/invites/{token}/enroll",
            json={"alias": "第二次", "username": "20268888", "password": "secret"},
        )
        self.assertEqual(repeated.status_code, 404)
        with self.app.state.database.session() as db:
            invite = db.query(Invite).one()
            self.assertIsNotNone(invite.used_at)


if __name__ == "__main__":
    unittest.main()
