"""FastAPI application factory."""
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.core.exceptions import AppError, app_error_handler, http_exception_handler
from app.core.logging import RequestLoggingMiddleware, configure_logging

from app.routers import auth, backup, certificates, clients, deploy, easyrsa, ldap, pam, routes, servers, system, users, vpn_instances


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()
    configure_logging(debug=settings.app_debug)

    # Ensure backup storage directory exists
    settings.backup_storage_path.mkdir(parents=True, exist_ok=True)

    yield


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="OpenVPN Manager",
        version="0.1.0",
        description="OpenVPN server management API",
        docs_url="/api/docs" if not settings.is_production else None,
        redoc_url="/api/redoc" if not settings.is_production else None,
        openapi_url="/api/openapi.json" if not settings.is_production else None,
        lifespan=lifespan,
    )

    # ── Security headers middleware ─────────────────────────────────────────
    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if settings.is_production:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )
        return response

    # ── CORS ────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )

    # ── Request logging ─────────────────────────────────────────────────────
    app.add_middleware(RequestLoggingMiddleware)

    # ── Exception handlers ──────────────────────────────────────────────────
    app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(HTTPException, http_exception_handler)  # type: ignore[arg-type]

    # ── Routers ─────────────────────────────────────────────────────────────
    api_prefix = "/api/v1"
    app.include_router(auth.router, prefix=api_prefix)
    app.include_router(servers.router, prefix=api_prefix)
    app.include_router(vpn_instances.router, prefix=api_prefix)
    app.include_router(routes.router, prefix=api_prefix)
    app.include_router(clients.router, prefix=api_prefix)
    app.include_router(certificates.router, prefix=api_prefix)
    app.include_router(pam.router, prefix=api_prefix)
    app.include_router(easyrsa.router, prefix=api_prefix)
    app.include_router(backup.router, prefix=api_prefix)
    app.include_router(deploy.router, prefix=api_prefix)
    app.include_router(system.router, prefix=api_prefix)
    app.include_router(users.router, prefix=api_prefix)
    app.include_router(ldap.router, prefix=api_prefix)

    # Health check at root (no auth required)
    @app.get("/health", include_in_schema=False)
    async def root_health() -> dict:
        return {"status": "ok"}

    return app


app = create_app()
