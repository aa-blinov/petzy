# Petzy frontend

The Petzy web app: React 18 + TypeScript, built with Vite, installable as a PWA. How to run the whole project, the API and deployment is in the [root README](../README.md).

## Commands

```bash
npm install
npm run dev       # http://localhost:5173, /api proxied to http://localhost:5001
npm run build     # type check + production build into dist/
npm run preview   # serve dist/ on http://localhost:4173, same /api proxy
npm run lint
```

Run the API next to it with `.venv/bin/python scripts/dev_local.py` (in-memory database, demo data, `admin` / `test1234`).

`VITE_API_URL` overrides the API base (default `/api`, same origin). Production builds need nothing set: nginx serves the app and the API from one origin.

## Stack

antd-mobile (UI), TanStack Query (server state), React Router, React Hook Form + Zod (forms), @dnd-kit (tile reordering), lucide-react (icons), vite-plugin-pwa with a hand-written service worker (`src/sw.ts`, `injectManifest`).

## Layout

```text
src/
  pages/        one component per route (App.tsx lists them)
  components/   shared UI: cards, sheets, dialogs, the undo bar, tab bar
  services/     API calls, one file per area (pets, medications, documents, …)
  hooks/        session, selected pet, event types, invites
  utils/        dates, species, stock maths, public pages, service worker updates
  content/      help.ts, the in-app help (Настройки → «Справка»)
  styles/       globals.css: tokens, dark theme, antd overrides
  sw.ts         offline cache, push notifications, update takeover
public/         icons, manifest assets, theme-init.js (theme before first paint)
```

## Notes

- **UI text** is Russian. Keep labels in «» exactly as on screen: the help refers to them.
- **Local wall-clock time.** Dates and times go to the API as the user sees them (`YYYY-MM-DD`, `HH:MM`), never via `toISOString()`, which is UTC.
- **Content-Security-Policy.** Production serves the app with one (`nginx/security-headers.conf`): scripts from this origin only, so no inline `<script>`. Styles may be inline.
- **Updates.** A new release reaches an open app through `utils/swUpdate.ts`: it checks when the app returns to the screen and hourly, then reloads on a main tab.
