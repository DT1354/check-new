"""FastAPI 应用工厂。"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import Settings
from .database import Database
from .rate_limit import RateLimiter
from .routes import accounts, auth, invites, runs, settings as settings_routes
from .security import CredentialCipher, PasswordService


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    database = Database(settings.database_url)
    cipher = CredentialCipher(settings.master_key)
    # SQLAlchemy Session.info makes the cipher available without a module global.
    database.session_factory.configure(info={"credential_cipher": cipher})

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        database.create_all()
        yield
        database.engine.dispose()

    app = FastAPI(
        title="SWU 新生打卡控制台",
        version="1.0.0",
        docs_url=None if settings.environment == "production" else "/docs",
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.database = database
    app.state.cipher = cipher
    app.state.passwords = PasswordService()
    app.state.rate_limiter = RateLimiter()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "X-CSRF-Token"],
    )
    app.include_router(auth.router)
    app.include_router(accounts.router)
    app.include_router(invites.router)
    app.include_router(runs.router)
    app.include_router(settings_routes.router)

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    return app
