FROM node:22-alpine AS deps

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

# ── Test stage ────────────────────────────────────────────────────────────────
FROM deps AS test

COPY . .
CMD ["sh", "-c", "npm run type-check && npm run test:unit"]

# ── Build stage ───────────────────────────────────────────────────────────────
FROM deps AS build

# Baked into the bundle and shown in the UI (see vite.config.ts / src/version.ts).
ARG GIT_COMMIT=dev
ENV GIT_COMMIT=$GIT_COMMIT

COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
HEALTHCHECK --interval=15s --timeout=5s --retries=5 \
    CMD wget -qO- http://localhost/ >/dev/null 2>&1 || exit 1
