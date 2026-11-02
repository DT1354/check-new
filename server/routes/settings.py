"""飞书通知设置。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from ..dependencies import CsrfAdmin, CurrentAdmin, DbSession
from ..feishu import send_message
from ..schemas import NotificationSettingsResponse, NotificationSettingsUpdate
from ..settings_store import get_setting, set_setting


router = APIRouter(prefix="/api/settings", tags=["settings"])


def _read(db, cipher) -> NotificationSettingsResponse:
    return NotificationSettingsResponse(
        webhook_configured=bool(get_setting(db, cipher, "feishu_webhook")),
        signing_secret_configured=bool(get_setting(db, cipher, "feishu_secret")),
        notify_manual_runs=get_setting(db, cipher, "notify_manual_runs", "false") == "true",
    )


@router.get("/notifications", response_model=NotificationSettingsResponse)
def get_notifications(_admin: CurrentAdmin, request: Request, db: DbSession):
    return _read(db, request.app.state.cipher)


@router.put("/notifications", response_model=NotificationSettingsResponse)
def update_notifications(
    payload: NotificationSettingsUpdate,
    _admin: CsrfAdmin,
    request: Request,
    db: DbSession,
):
    cipher = request.app.state.cipher
    if payload.webhook_url is not None:
        webhook = payload.webhook_url.strip()
        if webhook and not webhook.startswith("https://open.feishu.cn/open-apis/bot/v2/hook/"):
            raise HTTPException(422, "Webhook 必须是飞书自定义机器人 HTTPS 地址")
        set_setting(db, cipher, "feishu_webhook", webhook)
    if payload.signing_secret is not None:
        set_setting(db, cipher, "feishu_secret", payload.signing_secret.strip())
    set_setting(
        db,
        cipher,
        "notify_manual_runs",
        "true" if payload.notify_manual_runs else "false",
    )
    db.commit()
    return _read(db, cipher)


@router.post("/notifications/test")
def test_notification(_admin: CsrfAdmin, request: Request, db: DbSession):
    cipher = request.app.state.cipher
    webhook = get_setting(db, cipher, "feishu_webhook")
    if not webhook:
        raise HTTPException(422, "请先保存飞书 Webhook")
    secret = get_setting(db, cipher, "feishu_secret")
    try:
        send_message(webhook, "SWU 新生打卡", ["通知连接正常。"], secret=secret)
    except Exception as exc:
        raise HTTPException(502, f"飞书通知失败: {str(exc)[:200]}") from exc
    return {"sent": True}
