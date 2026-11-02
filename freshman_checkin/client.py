"""在真实浏览器会话中处理 eHall 安全层并调用新生打卡接口。"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path
from dataclasses import dataclass
from typing import Any

import requests
from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright
from playwright_stealth import Stealth


BASE_URL = "https://ehallxgdt.swu.edu.cn"
APP_PATH = "/xsfwdt/sys/swmcqdkappswu/*default/index.do"
APP_URL = BASE_URL + APP_PATH
GET_ROLES_PATH = "/xsfwdt/sys/swpubapp/NewMobileAPIController/getUserRoles.do"
SET_ROLE_PATH = "/xsfwdt/sys/swpubapp/NewMobileAPIController/setAppRole.do"
GET_STATUS_PATH = (
    "/xsfwdt/sys/swmcqdkappswu/MobileJrqdController/getKqInfo.do"
)
SUBMIT_PATH = "/xsfwdt/sys/swmcqdkappswu/MobileJrqdController/addKqInfo.do"
APP_ID = "7888298217184847"
APP_NAME = "swmcqdkappswu"
DEFAULT_EHALL_USER_AGENT = (
    "Mozilla/5.0 (Linux; U; Android 16; zh-CN; 2407FRK8EC "
    "Build/BP2A.250605.031.A3) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Version/4.0 Chrome/100.0.4896.58 UWS/5.12.14.0 Mobile Safari/537.36 "
    "AliApp(DingTalk/8.3.17.20) com.alibaba.android.rimet/55041109 "
    "Channel/10002068 language/en-US abi/64 xpn/xiaomi UT4Aplus/0.2.25 "
    "colorScheme/dark"
)


def build_checkin_payload(status_data: dict[str, Any]) -> dict[str, Any]:
    """从 getKqInfo 的地点配置构造无需前端定位 SDK 的提交数据。"""
    locations = status_data.get("DD_LIST") or []
    if not locations:
        raise RuntimeError("getKqInfo 未返回可用打卡地点")
    location = locations[0]
    required = ("DDDM", "QDDD", "JDZB", "WDZB")
    missing = [key for key in required if location.get(key) in (None, "")]
    if missing:
        raise RuntimeError(f"打卡地点缺少字段: {', '.join(missing)}")
    return {
        "DDDM": location["DDDM"],
        "QDDZ": location["QDDD"],
        "JDZB": float(location["JDZB"]),
        "WDZB": float(location["WDZB"]),
    }


def _cookie_to_playwright(cookie: requests.cookies.Cookie) -> dict[str, Any]:
    item: dict[str, Any] = {
        "name": cookie.name,
        "value": cookie.value,
        "domain": cookie.domain,
        "path": cookie.path or "/",
        "secure": bool(cookie.secure),
    }
    if cookie.expires and cookie.expires > 0:
        item["expires"] = float(cookie.expires)
    return item


@dataclass
class CheckinResult:
    already_checked_in: bool
    submitted: bool
    status: dict[str, Any]


class FreshmanCheckinClient:
    """新生打卡客户端。

    requests.Session 负责 IDM 登录；Playwright 负责执行 eHall 的 412 安全
    挑战和为 XHR 自动附加 ZUY2FAwZ。
    """

    def __init__(
        self,
        idm_session: requests.Session,
        *,
        entry_url: str,
        headless: bool = True,
        browser_channel: str | None = None,
        external_chrome: bool = False,
        external_headful: bool = False,
        native_fingerprint: bool = False,
        timeout_ms: int = 60_000,
    ) -> None:
        self.idm_session = idm_session
        self.entry_url = entry_url
        self.headless = headless
        self.browser_channel = browser_channel or os.environ.get(
            "PLAYWRIGHT_CHANNEL"
        )
        self.external_chrome = external_chrome
        self.external_headful = external_headful
        self.native_fingerprint = native_fingerprint
        self.timeout_ms = timeout_ms
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._external_process: subprocess.Popen | None = None
        self._external_profile: tempfile.TemporaryDirectory | None = None
        self.page: Page | None = None
        self._response_trace: list[tuple[int, str]] = []

    def __enter__(self) -> "FreshmanCheckinClient":
        try:
            self.open()
        except Exception:
            self.close()
            raise
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def open(self) -> None:
        if self.page is not None:
            return
        self._playwright = sync_playwright().start()
        context_kwargs: dict[str, Any] = {
            "user_agent": os.environ.get(
                "FRESHMAN_BROWSER_USER_AGENT", DEFAULT_EHALL_USER_AGENT
            ),
            "locale": "en-US",
            "timezone_id": "Asia/Shanghai",
            "viewport": {"width": 393, "height": 873},
            "device_scale_factor": 3.25,
            "is_mobile": True,
            "has_touch": True,
        }
        if self.external_chrome:
            self._start_external_chrome()
        else:
            launch_kwargs: dict[str, Any] = {
                "headless": self.headless,
                "args": [
                    "--disable-blink-features=AutomationControlled",
                    "--disable-features=UserAgentClientHint",
                ],
            }
            if self.browser_channel:
                launch_kwargs["channel"] = self.browser_channel
            self._browser = self._playwright.chromium.launch(**launch_kwargs)
            debug_har = os.environ.get("FRESHMAN_DEBUG_HAR")
            if debug_har:
                context_kwargs.update(
                    record_har_path=debug_har,
                    record_har_content="embed",
                    record_har_mode="full",
                )
            self._context = self._browser.new_context(**context_kwargs)
        assert self._context is not None
        if not self.native_fingerprint:
            self._context.add_init_script(
                """
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                Object.defineProperty(navigator, 'platform', {get: () => 'Linux aarch64'});
                Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
                """
            )

            def strip_desktop_client_hints(route) -> None:
                headers = {
                    key: value
                    for key, value in route.request.headers.items()
                    if not key.lower().startswith("sec-ch-ua")
                }
                route.continue_(headers=headers)

            self._context.route("**/*", strip_desktop_client_hints)
            Stealth(
                chrome_runtime=True,
                navigator_platform_override="Linux aarch64",
                navigator_user_agent_override=context_kwargs["user_agent"],
                sec_ch_ua_override='"Chromium";v="100", "Google Chrome";v="100"',
                webgl_vendor_override="Qualcomm",
                webgl_renderer_override="Adreno (TM) 750",
            ).apply_stealth_sync(self._context)

        cookies = [
            _cookie_to_playwright(cookie)
            for cookie in self.idm_session.cookies
            if cookie.domain
        ]
        if cookies:
            self._context.add_cookies(cookies)
        self.page = self._context.new_page()
        self.page.set_default_timeout(self.timeout_ms)
        cdp = self._context.new_cdp_session(self.page)
        if not self.native_fingerprint:
            cdp.send(
                "Network.setUserAgentOverride",
                {
                    "userAgent": context_kwargs["user_agent"],
                    "acceptLanguage": "en-US,en;q=0.9",
                    "platform": "Linux aarch64",
                    "userAgentMetadata": {
                        "brands": [
                            {"brand": "Chromium", "version": "100"},
                            {"brand": "Google Chrome", "version": "100"},
                        ],
                        "fullVersion": "100.0.4896.58",
                        "platform": "Android",
                        "platformVersion": "16.0.0",
                        "architecture": "arm",
                        "model": "2407FRK8EC",
                        "mobile": True,
                    },
                },
            )
            cdp.send(
                "Emulation.setDeviceMetricsOverride",
                {
                    "width": 393,
                    "height": 873,
                    "deviceScaleFactor": 3.25,
                    "mobile": True,
                    "screenWidth": 393,
                    "screenHeight": 873,
                },
            )
        cdp.send("Emulation.setTimezoneOverride", {"timezoneId": "Asia/Shanghai"})
        cdp.send("Emulation.setLocaleOverride", {"locale": "en-US"})

        def record_response(response) -> None:
            parsed = urllib.parse.urlparse(response.request.url)
            host = parsed.netloc
            if host.endswith("swu.edu.cn"):
                query_keys = sorted(urllib.parse.parse_qs(parsed.query))
                suffix = f"?[{','.join(query_keys)}]" if query_keys else ""
                self._response_trace.append(
                    (response.status, parsed.path + suffix)
                )

        self.page.on("response", record_response)
        self.page.goto(self.entry_url, wait_until="domcontentloaded", timeout=self.timeout_ms)
        if "swmcqdkappswu" not in self.entry_url:
            self._wait_for_page("swmxggzptapp", "门户认证落地页")
            self.page.goto(APP_URL, wait_until="domcontentloaded", timeout=self.timeout_ms)
        self._wait_for_page("swmcqdkappswu", "新生打卡应用")

    def _start_external_chrome(self) -> None:
        assert self._playwright is not None
        executable = self._find_chrome_executable()
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]

        self._external_profile = tempfile.TemporaryDirectory(
            prefix="freshman-checkin-chrome-"
        )
        command = [
            executable,
            f"--remote-debugging-port={port}",
            f"--user-data-dir={self._external_profile.name}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-background-networking",
            "--disable-component-update",
            "--disable-features=UserAgentClientHint",
            "--window-size=393,873",
        ]
        if self.external_headful:
            command.append("--window-position=-32000,-32000")
        else:
            command.append("--headless=new")
        command.append("about:blank")
        creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        self._external_process = subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
        )
        endpoint = f"http://127.0.0.1:{port}"
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if self._external_process.poll() is not None:
                raise RuntimeError("外部 Chrome 在 CDP 连接前退出")
            try:
                with urllib.request.urlopen(endpoint + "/json/version", timeout=1):
                    break
            except OSError:
                time.sleep(0.2)
        else:
            raise RuntimeError("等待外部 Chrome CDP 端口超时")
        self._browser = self._playwright.chromium.connect_over_cdp(endpoint)
        if not self._browser.contexts:
            raise RuntimeError("外部 Chrome 未提供默认浏览器上下文")
        self._context = self._browser.contexts[0]

    @staticmethod
    def _find_chrome_executable() -> str:
        configured = os.environ.get("CHROME_PATH")
        candidates = [
            configured,
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            "/usr/bin/google-chrome",
            "/usr/bin/google-chrome-stable",
            "/usr/bin/chromium",
            "/usr/bin/chromium-browser",
        ]
        for candidate in candidates:
            if candidate and Path(candidate).is_file():
                return candidate
        raise RuntimeError("未找到系统 Chrome；可通过 CHROME_PATH 指定")

    def close(self) -> None:
        if self._context is not None and not self.external_chrome:
            self._context.close()
        if self._browser is not None:
            self._browser.close()
        if self._playwright is not None:
            self._playwright.stop()
        if self._external_process is not None and self._external_process.poll() is None:
            self._external_process.terminate()
            try:
                self._external_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._external_process.kill()
        if self._external_profile is not None:
            self._external_profile.cleanup()
        self.page = None
        self._context = None
        self._browser = None
        self._playwright = None
        self._external_process = None
        self._external_profile = None

    def _wait_for_page(self, url_marker: str, label: str) -> None:
        assert self.page is not None
        deadline = time.monotonic() + self.timeout_ms / 1000
        while time.monotonic() < deadline:
            if (
                self.page.url.startswith(BASE_URL)
                and url_marker in self.page.url
            ):
                try:
                    if self.page.locator("router-view").count() > 0:
                        return
                except Exception:
                    pass
            self.page.wait_for_timeout(500)
        trace = ", ".join(f"{status}:{path}" for status, path in self._response_trace[-8:])
        raise RuntimeError(
            f"eHall {label}未在超时时间内完成登录和安全验证"
            + (f"；最近响应: {trace}" if trace else "")
        )

    def _api_post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        if self.page is None:
            raise RuntimeError("浏览器会话尚未打开")
        result = self.page.evaluate(
            """
            ({path, payload}) => new Promise((resolve, reject) => {
              const xhr = new XMLHttpRequest();
              xhr.open('POST', path, true);
              xhr.withCredentials = true;
              xhr.setRequestHeader('Accept', 'application/json, text/plain, */*');
              xhr.setRequestHeader(
                'Content-Type',
                'application/x-www-form-urlencoded;charset=UTF-8'
              );
              xhr.onload = () => resolve({status: xhr.status, text: xhr.responseText});
              xhr.onerror = () => reject(new Error('XHR network error'));
              const body = new URLSearchParams();
              body.set('data', JSON.stringify(payload));
              xhr.send(body.toString());
            })
            """,
            {"path": path, "payload": payload},
        )
        if result["status"] != 200:
            raise RuntimeError(f"eHall API {path} 返回 HTTP {result['status']}")
        try:
            data = json.loads(result["text"])
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"eHall API {path} 返回了非 JSON 响应") from exc
        if str(data.get("code")) != "0":
            raise RuntimeError(f"eHall API {path} 失败: {data.get('msg', '未知错误')}")
        return data

    def prepare_role(self) -> dict[str, Any]:
        roles_response = self._api_post(GET_ROLES_PATH, {"APPID": APP_ID})
        roles = roles_response.get("data") or []
        if not roles:
            raise RuntimeError("新生应用未返回可用用户角色")
        role = roles[0]
        role_id = role.get("ROLEID")
        if not role_id:
            raise RuntimeError("用户角色缺少 ROLEID")
        self._api_post(
            SET_ROLE_PATH,
            {"APPID": APP_ID, "APPNAME": APP_NAME, "ROLEID": role_id},
        )
        return role

    def get_status(self) -> dict[str, Any]:
        response = self._api_post(GET_STATUS_PATH, {})
        data = response.get("data")
        if not isinstance(data, dict):
            raise RuntimeError("getKqInfo 响应缺少 data")
        return data

    def submit(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._api_post(SUBMIT_PATH, payload)

    def checkin(self, *, force: bool = False) -> CheckinResult:
        status = self.get_status()
        qd_info = status.get("QD_INFO") or {}
        if str(qd_info.get("HAS_QD")) == "1":
            return CheckinResult(True, False, status)

        config = status.get("CONFIG_INFO") or {}
        if not force and str(config.get("IN_TIME")) != "1":
            start = config.get("DKKSSJ", "?")
            end = config.get("DKJSSJ", "?")
            raise RuntimeError(f"当前不在打卡时间内（{start}-{end}）")

        self.submit(build_checkin_payload(status))
        verified = self.get_status()
        if str((verified.get("QD_INFO") or {}).get("HAS_QD")) != "1":
            raise RuntimeError("提交接口返回成功，但再次查询仍显示未打卡")
        return CheckinResult(False, True, verified)
