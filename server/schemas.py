"""API 请求与响应结构。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=8, max_length=256)


class SessionResponse(BaseModel):
    username: str
    csrf_token: str


class AccountCreate(BaseModel):
    alias: str = Field(min_length=1, max_length=80)
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=256)
    enabled: bool = True


class AccountUpdate(BaseModel):
    alias: str | None = Field(default=None, min_length=1, max_length=80)
    username: str | None = Field(default=None, min_length=1, max_length=128)
    password: str | None = Field(default=None, min_length=1, max_length=256)
    enabled: bool | None = None


class AccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    alias: str
    username_hint: str
    enabled: bool
    created_at: datetime
    updated_at: datetime


class InviteCreate(BaseModel):
    expires_in_hours: int = Field(default=24, ge=1, le=168)


class InviteResponse(BaseModel):
    id: int
    expires_at: datetime
    used_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime


class InviteCreated(InviteResponse):
    invite_url: str


class InviteEnroll(BaseModel):
    alias: str = Field(min_length=1, max_length=80)
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=256)


class RunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    account_id: int
    trigger: str
    status: str
    attempt_count: int
    message: str | None
    checkin_time: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    account_alias: str | None = None


class NotificationSettingsUpdate(BaseModel):
    webhook_url: str | None = Field(default=None, max_length=1024)
    signing_secret: str | None = Field(default=None, max_length=512)
    notify_manual_runs: bool = False


class NotificationSettingsResponse(BaseModel):
    webhook_configured: bool
    signing_secret_configured: bool
    notify_manual_runs: bool
