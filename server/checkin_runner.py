"""把已验证的单账号打卡核心包装成 Worker 可调用函数。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from freshman_checkin.client import FreshmanCheckinClient
from freshman_checkin.idm_auth import build_ehall_login_url, login_idm


@dataclass(frozen=True, slots=True)
class RunnerResult:
    status: str
    message: str
    checkin_time: str | None = None


def _checkin_time(status: dict[str, Any]) -> str | None:
    info = status.get("QD_INFO") or {}
    for key in ("QDSJ", "DKSJ", "QDSJ_DISPLAY"):
        if info.get(key):
            return str(info[key])
    return None


def run_checkin(
    username: str,
    password: str,
    *,
    timeout_seconds: int = 90,
    status_only: bool = False,
    force: bool = False,
) -> RunnerResult:
    """每次调用都新建并关闭 IDM 与 Chrome 会话。"""
    idm_session = login_idm(username, password)
    with FreshmanCheckinClient(
        idm_session,
        entry_url=build_ehall_login_url(),
        external_chrome=True,
        external_headful=True,
        native_fingerprint=True,
        timeout_ms=timeout_seconds * 1000,
    ) as client:
        client.prepare_role()
        if status_only:
            status = client.get_status()
            return RunnerResult("validated", "账号验证成功", _checkin_time(status))
        result = client.checkin(force=force)
        if result.already_checked_in:
            return RunnerResult(
                "already_checked", "今天已经打卡", _checkin_time(result.status)
            )
        return RunnerResult("success", "打卡成功", _checkin_time(result.status))


def safe_error_message(exc: Exception, *sensitive_values: str) -> str:
    message = str(exc).strip() or exc.__class__.__name__
    for value in sensitive_values:
        if value:
            message = message.replace(value, "[已隐藏]")
    return message[:500]
