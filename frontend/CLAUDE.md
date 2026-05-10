## Frontend Commands

```bash
npm install
npm run dev           # Vite dev server (port 5173, proxies /api to backend)
npm run build         # Type-check + production build
npm run test:unit     # Vitest unit tests
npm run test:e2e      # Playwright end-to-end tests
npm run lint          # ESLint with auto-fix
npm run type-check    # Vue TSC type checking
```

## Architecture

- **`api/`** — 12 Axios client modules; `client.ts` has JWT interceptors and auto-refresh on 401
- **`stores/`** — Pinia: `auth.ts` (session/token state), `servers.ts`
- **`router/index.ts`** — Auth guards (`requiresAuth`, `requiresSuperuser`)
- **`views/`** — Feature pages grouped by domain: servers, clients, certificates, backup, deploy, vpn, routes, pam, easyrsa, users
- **`types/index.ts`** — All shared TypeScript interfaces
