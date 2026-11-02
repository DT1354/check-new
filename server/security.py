"""密码、会话令牌及敏感配置的安全原语。"""

from __future__ import annotations

import base64
import hashlib
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


_CIPHER_VERSION = b"\x01"
_ASSOCIATED_DATA = b"check-new.credentials.v1"


def generate_master_key() -> str:
    """生成可放入 Credential 文件的 256 位密钥。"""
    return base64.urlsafe_b64encode(AESGCM.generate_key(bit_length=256)).decode("ascii")


def generate_token(byte_length: int = 32) -> str:
    return secrets.token_urlsafe(byte_length)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class CredentialCipher:
    """使用 AES-256-GCM 加密需要可逆读取的账号密钥。"""

    def __init__(self, encoded_key: str) -> None:
        try:
            key = base64.urlsafe_b64decode(encoded_key.encode("ascii"))
        except Exception as exc:
            raise ValueError("APP_MASTER_KEY 不是有效的 Base64 密钥") from exc
        if len(key) != 32:
            raise ValueError("APP_MASTER_KEY 解码后必须正好是 32 字节")
        self._cipher = AESGCM(key)

    def encrypt(self, plaintext: str) -> str:
        nonce = secrets.token_bytes(12)
        ciphertext = self._cipher.encrypt(
            nonce, plaintext.encode("utf-8"), _ASSOCIATED_DATA
        )
        return base64.urlsafe_b64encode(
            _CIPHER_VERSION + nonce + ciphertext
        ).decode("ascii")

    def decrypt(self, encoded: str) -> str:
        raw = base64.urlsafe_b64decode(encoded.encode("ascii"))
        if len(raw) < 30 or raw[:1] != _CIPHER_VERSION:
            raise ValueError("不支持或已损坏的密文")
        plaintext = self._cipher.decrypt(raw[1:13], raw[13:], _ASSOCIATED_DATA)
        return plaintext.decode("utf-8")


class PasswordService:
    def __init__(self) -> None:
        self._hasher = PasswordHasher()

    def hash(self, password: str) -> str:
        return self._hasher.hash(password)

    def verify(self, password_hash: str, password: str) -> bool:
        try:
            return self._hasher.verify(password_hash, password)
        except (VerifyMismatchError, InvalidHashError):
            return False
