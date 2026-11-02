"""加密应用设置的读写帮助。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from .models import AppSetting
from .security import CredentialCipher


def get_setting(db: Session, cipher: CredentialCipher, key: str, default: str = "") -> str:
    record = db.get(AppSetting, key)
    if record is None:
        return default
    return cipher.decrypt(record.encrypted_value)


def set_setting(db: Session, cipher: CredentialCipher, key: str, value: str) -> None:
    record = db.get(AppSetting, key)
    encrypted = cipher.encrypt(value)
    if record is None:
        db.add(AppSetting(key=key, encrypted_value=encrypted))
    else:
        record.encrypted_value = encrypted
