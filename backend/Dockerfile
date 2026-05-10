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
    SSH_KEY_ENCRYPTION_SECRET=test-ssh-encryption-secret

CMD ["uv", "run", "pytest", "-v"]

# ── Production stage ──────────────────────────────────────────────────────────
FROM base AS production

COPY pyproject.toml .
RUN uv sync --no-dev

COPY . .

RUN chmod +x entrypoint.sh

EXPOSE 8000

CMD ["./entrypoint.sh"]
