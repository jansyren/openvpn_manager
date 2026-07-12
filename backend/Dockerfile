FROM python:3.12-slim AS base

WORKDIR /app

RUN pip install uv

# ── Test stage ────────────────────────────────────────────────────────────────
FROM base AS test

COPY pyproject.toml uv.lock ./
RUN uv sync --extra dev

COPY . .

# Generate throw-away RSA keys so Settings can load during tests
RUN uv run python generate_test_keys.py

ENV JWT_PRIVATE_KEY_PATH=/app/test_private.pem \
    JWT_PUBLIC_KEY_PATH=/app/test_public.pem \
    DATABASE_URL=sqlite+aiosqlite:///./test.db \
    APP_SECRET_KEY=test-secret-key-at-least-32-characters! \
    SSH_KEY_ENCRYPTION_SECRET=test-ssh-encryption-secret-at-least-32 \
    RATE_LIMIT_ENABLED=false

CMD ["uv", "run", "pytest", "-v"]

# ── Production stage ──────────────────────────────────────────────────────────
FROM base AS production

COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev

COPY . .

# Build metadata surfaced via /api/v1/system/info (git_commit / build_time).
ARG GIT_COMMIT=unknown
ARG BUILD_TIME=unknown
ENV GIT_COMMIT=$GIT_COMMIT \
    BUILD_TIME=$BUILD_TIME

# Run as a non-root user; ensure app dir (incl. the backups volume mount point)
# is writable by it.
RUN chmod +x entrypoint.sh \
    && useradd -r -u 10001 -m appuser \
    && mkdir -p /app/backups \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=5 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health', timeout=3).status==200 else 1)"

CMD ["./entrypoint.sh"]
