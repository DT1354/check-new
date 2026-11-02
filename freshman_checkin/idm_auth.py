"""登录swu IDM，并建立用于联邦认证的 requests.Session。"""

from __future__ import annotations

import re
import urllib.parse
from collections.abc import Callable

import requests

from .des import strEnc


IDM_LOGIN_PAGE = "http://idm.swu.edu.cn/am/UI/Login"
IDM_LOGIN_POST = "https://idm.swu.edu.cn/am/UI/Login"
IDM_CAPTCHA_URL = "https://idm.swu.edu.cn/am/validate.code"
IDM_CAPTCHA_VERIFY_URL = "https://idm.swu.edu.cn/am/validatecode/verify.do"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
UAAAP_CAS_LOGIN_URL = "https://uaaap.swu.edu.cn/cas/login"
EHALL_HOST = "ehallxgdt.swu.edu.cn"
APP_SERVICE_URL = (
    "https://ehallxgdt.swu.edu.cn/"
    "xsfwdt/sys/swmcqdkappswu/*default/index.do"
)
PORTAL_SERVICE_URL = (
    "https://ehallxgdt.swu.edu.cn/"
    "xsfwdt/sys/swmxggzptapp/*default/index.do"
)

# IDM 登录页要求的 OAuth 回跳参数。它是公开的应用配置，不含用户凭据或会话。
_GOTO_B64 = (
    "aHR0cDovL2lkbS5zd3UuZWR1LmNuL2FtL29hdXRoMi9hdXRob3JpemU/"
    "c2VydmljZT1pbml0U2VydmljZSZyZXNwb25zZV90eXBlPWNvZGUmY2xp"
    "ZW50X2lkPTdjMXpva29samw5YmJpaG82eXVvJnNjb3BlPXVpZCtjbit1"
    "c2VySWRDb2RlJnJlZGlyZWN0X3VyaT1odHRwcyUzQSUyRiUyRnVhYWFw"
    "LnN3dS5lZHUuY24lMkZjYXMlMkZsb2dpbiUzRnNlcnZpY2UlM0RodHRw"
    "cyUyNTNBJTI1MkYlMjUyRnVhYWFwLnN3dS5lZHUuY24lMjUyRmNhcyUy"
    "NTJGb2F1dGhyLjAlMjUyRmNhbGxiYWNrQXV0aG9yaXplJTI2b3JpZ2lu"
    "YWxSZXF1ZXN0VXJsJTNEaHR0cHMlMjUzQSUyNTJGJTI1MkZ1YWFhcC5z"
    "d3UuZWR1LmNuJTI1MkZjYXMlMjUyRm9hdXRoMi4wJTI1MkZhdXRob3Jp"
    "emUlMjUzRmNsaWVudF9pZCUyNTNEeXpzbWhzJTI1MjZyZWRpcmVjdF91"
    "cmklMjUzRGh0dHBzJTI1MjUzQSUyNTI1MkYlMjUyNTJGb2Yuc3d1LmVk"
    "dS5jbiUyNTI1M0E0NDMlMjUyNTJGY2FzJTI1MjUyRm9hdXRoJTI1MjUy"
    "RmNhbGxiYWNrJTI1MjUyRlNXVV9DQVMyX0ZBREVSQUwlMjUyNnN0YXRl"
    "JTI1M0Q1ZTU2M2JiY2E1MjM0ZTA0YmRjM2JkODEzMTc0OWVjNSUyNTI2"
    "c2NvcGUlMjUzRHNpbXBsZSUyNTI2ZmVkZXJhbEVuYWJsZSUzRHRydWUm"
    "ZGVjaXNpb249QWxsb3c="
)


def _default_captcha_solver(image: bytes) -> str:
    import ddddocr

    return ddddocr.DdddOcr(show_ad=False).classification(image)


def login_idm(
    username: str,
    password: str,
    *,
    captcha_solver: Callable[[bytes], str] | None = None,
    timeout: float = 20,
) -> requests.Session:
    """使用账号、密码和验证码登录 IDM，返回保留认证 Cookie 的会话。

    该会话用于后续 UAAAP/CAS 联邦认证，不保存用户凭据。
    """
    if not username or not password:
        raise ValueError("username 和 password 不能为空")

    solver = captcha_solver or _default_captcha_solver
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    login_page = session.get(
        IDM_LOGIN_PAGE,
        params={"goto": _GOTO_B64, "service": "initService"},
        timeout=timeout,
    )
    login_page.raise_for_status()
    match = re.search(r'id="random"[^>]*value="([^"]+)"', login_page.text)
    if not match:
        raise RuntimeError("无法从 IDM 登录页获取 random DES 密钥")
    random_key = match.group(1)

    captcha = session.get(IDM_CAPTCHA_URL, timeout=timeout)
    captcha.raise_for_status()
    captcha_code = solver(captcha.content).strip()
    if not captcha_code:
        raise RuntimeError("验证码识别结果为空")

    verify = session.post(
        IDM_CAPTCHA_VERIFY_URL,
        data={"validateCode": captcha_code},
        timeout=timeout,
    )
    verify.raise_for_status()
    try:
        verify_data = verify.json()
    except ValueError as exc:
        raise RuntimeError("IDM 验证码校验返回了非 JSON 响应") from exc
    if verify_data.get("state") != "success":
        raise RuntimeError("验证码校验失败")

    response = session.post(
        IDM_LOGIN_POST,
        data={
            "IDToken1": strEnc(username, random_key, "", ""),
            "IDToken2": strEnc(password, random_key, "", ""),
            "IDToken3": "",
            "goto": _GOTO_B64,
            "gotoOnFail": "",
            "SunQueryParamsString": "c2VydmljZT1pbml0U2VydmljZQ==",
            "encoded": "false",
            "validateCode": captcha_code,
            "gx_charset": "UTF-8",
        },
        allow_redirects=False,
        timeout=timeout,
    )
    if response.status_code != 302:
        raise RuntimeError(f"IDM 登录失败: HTTP {response.status_code}")
    if not session.cookies.get("iPlanetDirectoryPro"):
        raise RuntimeError("IDM 登录未返回 iPlanetDirectoryPro Cookie")
    return session


def get_ehall_ticket_url(
    session: requests.Session,
    *,
    service_url: str = APP_SERVICE_URL,
    timeout: float = 20,
    max_redirects: int = 10,
) -> str:
    """通过 IDM 联邦会话让 UAAAP 为 eHall service 签发 CAS ticket。

    返回 ticket 落地 URL，但不在 requests 中消费它；随后交给浏览器执行
    eHall 的 412 JavaScript 安全挑战。
    """
    current_url = UAAAP_CAS_LOGIN_URL + "?" + urllib.parse.urlencode(
        {"service": service_url, "federalEnable": "true"}
    )

    for _ in range(max_redirects):
        response = session.get(
            current_url,
            allow_redirects=False,
            timeout=timeout,
        )
        if response.status_code not in {301, 302, 303, 307, 308}:
            raise RuntimeError(
                "UAAAP 未能签发 eHall ticket: "
                f"HTTP {response.status_code} @ {urllib.parse.urlparse(current_url).netloc}"
            )
        location = response.headers.get("Location")
        if not location:
            raise RuntimeError("UAAAP 重定向响应缺少 Location")
        next_url = urllib.parse.urljoin(current_url, location)
        parsed = urllib.parse.urlparse(next_url)
        query = urllib.parse.parse_qs(parsed.query)
        if parsed.hostname == EHALL_HOST and query.get("ticket"):
            return next_url
        current_url = next_url

    raise RuntimeError("获取 eHall ticket 时重定向次数过多")


def build_ehall_login_url(service_url: str = PORTAL_SERVICE_URL) -> str:
    """构造浏览器使用的 UAAAP 联邦登录入口。

    浏览器持有 IDM Cookie 后访问此 URL，会自动取得 CAS ticket 并回到目标
    eHall service，避免跨 User-Agent 传递 ticket。
    """
    return UAAAP_CAS_LOGIN_URL + "?" + urllib.parse.urlencode(
        {"service": service_url, "federalEnable": "true"}
    )
