"""swu学工系统打卡独立实现。"""

from .client import FreshmanCheckinClient, build_checkin_payload
from .idm_auth import build_ehall_login_url, get_ehall_ticket_url, login_idm

__all__ = [
    "FreshmanCheckinClient",
    "build_checkin_payload",
    "build_ehall_login_url",
    "get_ehall_ticket_url",
    "login_idm",
]
