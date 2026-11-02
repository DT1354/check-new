"""应用配置与密钥加载。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _as_bool(value: str | None, *, default: bool) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"无法识别的布尔值: {value}")


def _read_master_key(environment: str) -> str:
    explicit_file = os.environ.get("APP_MASTER_KEY_FILE")
    credential_dir = os.environ.get("CREDENTIALS_DIRECTORY")
    candidates = [
        Path(explicit_file) if explicit_file else None,
        Path(credential_dir) / "app_master_key" if credential_dir else None,
    ]
    for candidate in candidates:
        if candidate and candidate.is_file():
            value = candidate.read_text(encoding="utf-8").strip()
            if value:
                return value
    value = os.environ.get("APP_MASTER_KEY", "").strip()
    if value:
        return value
    if environment == "test":
        return ""
    raise RuntimeError(
        "缺少 APP_MASTER_KEY；生产环境请通过 systemd Credential 或密钥文件提供"
    )


@dataclass(frozen=True, slots=True)
class Settings:
    environment: str
    database_url: str
    frontend_origin: str
    master_key: str
    cookie_secure: bool
    session_ttl_hours: int = 24
    invite_ttl_hours: int = 24
    worker_poll_seconds: float = 2.0
    automatic_retry_delay_seconds: float = 10.0
    browser_timeout_seconds: int = 90

    @classmethod
    def from_env(cls) -> "Settings":
        environment = os.environ.get("APP_ENV", "development").strip().lower()
        frontend_origin = os.environ.get(
            "FRONTEND_ORIGIN", "http://localhost:5173"
        ).strip().rstrip("/")
        if not frontend_origin.startswith(("http://", "https://")):
            raise ValueError("FRONTEND_ORIGIN 必须是完整的 http(s) 地址")
        if environment == "production" and not frontend_origin.startswith("https://"):
            raise ValueError("生产环境 FRONTEND_ORIGIN 必须使用 HTTPS")
        return cls(
            environment=environment,
            database_url=os.environ.get(
                "DATABASE_URL", "sqlite:///./data/checkin.db"
            ).strip(),
            frontend_origin=frontend_origin,
            master_key=_read_master_key(environment),
            cookie_secure=_as_bool(
                os.environ.get("COOKIE_SECURE"), default=environment == "production"
            ),
            session_ttl_hours=int(os.environ.get("SESSION_TTL_HOURS", "24")),
            invite_ttl_hours=int(os.environ.get("INVITE_TTL_HOURS", "24")),
            worker_poll_seconds=float(os.environ.get("WORKER_POLL_SECONDS", "2")),
            automatic_retry_delay_seconds=float(
                os.environ.get("AUTOMATIC_RETRY_DELAY_SECONDS", "10")
            ),
            browser_timeout_seconds=int(
                os.environ.get("BROWSER_TIMEOUT_SECONDS", "90")
            ),
        )
