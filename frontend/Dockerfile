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

COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
