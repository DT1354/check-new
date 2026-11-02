"""飞书自定义机器人签名与消息发送。"""

from __future__ import annotations

import base64
import hashlib
import hmac
import time
from typing import Any, Callable

import requests


def make_signature(timestamp: int | str, secret: str) -> str:
    string_to_sign = f"{timestamp}\n{secret}".encode("utf-8")
    digest = hmac.new(string_to_sign, digestmod=hashlib.sha256).digest()
    return base64.b64encode(digest).decode("ascii")


def build_payload(
    title: str,
    lines: list[str],
    *,
    secret: str = "",
    timestamp: int | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "msg_type": "interactive",
        "card": {
            "header": {"title": {"tag": "plain_text", "content": title}, "template": "blue"},
            "elements": [
                {"tag": "div", "text": {"tag": "lark_md", "content": "\n".join(lines)}}
            ],
        },
    }
    if secret:
        current = int(timestamp if timestamp is not None else time.time())
        payload["timestamp"] = str(current)
        payload["sign"] = make_signature(current, secret)
    return payload


def send_message(
    webhook_url: str,
    title: str,
    lines: list[str],
    *,
    secret: str = "",
    post: Callable[..., Any] = requests.post,
) -> None:
    try:
        response = post(
            webhook_url,
            json=build_payload(title, lines, secret=secret),
            timeout=10,
        )
        response.raise_for_status()
    except requests.RequestException:
        # requests 的异常文本常包含完整 Webhook URL，不能进入日志或 API 响应。
        raise RuntimeError("飞书网络请求失败") from None
    data = response.json()
    if data.get("code", data.get("StatusCode", 0)) not in (0, None):
        raise RuntimeError(f"飞书机器人返回失败: {data.get('msg') or data.get('StatusMessage')}")
