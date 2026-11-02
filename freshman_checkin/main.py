"""新生打卡命令行入口。"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

from .client import FreshmanCheckinClient
from .idm_auth import build_ehall_login_url, login_idm


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def status_summary(data: dict) -> dict:
    config = data.get("CONFIG_INFO") or {}
    qd_info = data.get("QD_INFO") or {}
    return {
        "already_checked_in": str(qd_info.get("HAS_QD")) == "1",
        "in_time": str(config.get("IN_TIME")) == "1",
        "window": f"{config.get('DKKSSJ', '?')}-{config.get('DKJSSJ', '?')}",
        "locations": len(data.get("DD_LIST") or []),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="西南大学新生自动打卡")
    parser.add_argument("--username", "-u")
    parser.add_argument("--password", "-p")
    parser.add_argument("--status-only", action="store_true", help="只查询，不提交")
    parser.add_argument("--force", action="store_true", help="忽略前端时间标记提交")
    parser.add_argument("--headed", action="store_true", help="显示浏览器窗口")
    parser.add_argument(
        "--external-chrome",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="独立启动系统 Chrome 后通过 CDP 连接，降低自动化启动指纹",
    )
    parser.add_argument(
        "--native-fingerprint",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="不注入移动 UA 或 stealth，使用浏览器原生指纹",
    )
    parser.add_argument(
        "--external-headful",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="外部 Chrome 使用完整图形引擎并把窗口移到屏幕外",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=60,
        help="eHall 页面等待超时秒数",
    )
    parser.add_argument(
        "--browser-channel",
        default=os.environ.get("PLAYWRIGHT_CHANNEL"),
        help="Playwright 浏览器通道，如 msedge、chrome；留空使用 Chromium",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    load_dotenv(root / ".env")
    username = args.username or os.environ.get("SWU_USERNAME")
    password = args.password or os.environ.get("SWU_PASSWORD")
    if not username or not password:
        log.error("请通过 .env 或命令行提供 SWU_USERNAME 和 SWU_PASSWORD")
        return 2

    try:
        log.info("使用账号密码登录 IDM ...")
        idm_session = login_idm(username, password)
        log.info("IDM 登录成功，由浏览器完成 UAAAP ticket 与 eHall 安全验证 ...")
        entry_url = build_ehall_login_url()
        with FreshmanCheckinClient(
            idm_session,
            entry_url=entry_url,
            headless=not args.headed,
            browser_channel=args.browser_channel,
            external_chrome=args.external_chrome,
            external_headful=args.external_headful,
            native_fingerprint=args.native_fingerprint,
            timeout_ms=args.timeout_seconds * 1000,
        ) as client:
            role = client.prepare_role()
            log.info("当前角色: %s", role.get("ROLENAME", "未知"))
            if args.status_only:
                print(json.dumps(status_summary(client.get_status()), ensure_ascii=False))
                return 0

            result = client.checkin(force=args.force)
            if result.already_checked_in:
                log.info("今日已经打卡")
            elif result.submitted:
                log.info("新生打卡成功，并已通过二次查询确认")
            return 0
    except Exception as exc:
        log.error("新生打卡失败: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
