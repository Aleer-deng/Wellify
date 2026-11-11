# Wellify frontend — Django connection

The React app uses the Django API for registration/login/logout, session restoration, profiles, goals, approved activity summaries, activity submissions, challenges, points, rewards, redemptions, notifications, subscription selection, and staff administration.

## Start both servers

Backend terminal:

```powershell
cd "C:\Users\LE KO\OneDrive\Desktop\Digital Heealth\Back-End"
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

Frontend terminal:

```powershell
cd "C:\Users\LE KO\OneDrive\Desktop\Digital Heealth\Front-End"
npm.cmd install
npm.cmd run dev
```

Open **http://127.0.0.1:5173/**. Log in with your existing Django email or username and password, or register a new account. The frontend shows Administration only for staff accounts; Django independently enforces staff access on every admin API request.

Vite proxies `/api` to `http://127.0.0.1:8000`. Cookies and CSRF requests use the frontend origin, avoiding local cross-origin cookie setup. If you changed `vite.config.js` while Vite was running, restart it. Both servers must stay running.

## Data behavior

- New accounts start with zero points. Old `hrw-*` browser demo data is ignored and never sent to the server.
- Manual activity submissions stay pending until approved by staff. Approval adds server points and updates activity totals.
- Set daily/weekly goals, join challenges, and claim qualifying rewards from approved activity.
- Redemptions use a UUID request key; retrying an interrupted request in the same dialog reuses it. The backend checks balance and stock atomically.
- Profile changes, notifications and subscription selection are saved by Django. Billing remains simulated.
- Staff can manage users, rewards and challenges, review activities, mark manually delivered rewards fulfilled, and export report totals.
- Server errors are shown without replacing failed data with fake successful results. Use Refresh to load changes made in another browser/account.
- Sessions are restored through `/profile/` after reload. An expired/invalid session returns the app to login. Logout invalidates the Django session.

Goals use two existing API requests (daily then weekly). If the second request fails, the first goal may already be saved; the UI refreshes to show the server state.

## Stellar

Freighter connection, Testnet funding, balances and HRW trustline signing remain available under My wallet. Set `VITE_HRW_ISSUER` to a valid token issuer public key and restart Vite. Private keys stay in Freighter.

The points ledger is managed by Django and is separate from on-chain HRW. A Freighter connection is local to the browser session and does not complete the backend's separate wallet-ownership challenge or convert points into tokens. No automatic token distribution, real voucher delivery, wearable sensor integration, or real billing is implemented.

## Configuration and deployment

`VITE_API_BASE_URL` defaults to `/api/v1`. In production, configure the web server to proxy `/api` to Django, or supply an HTTPS API origin and configure Django CORS/CSRF and cookies for the actual domains. The Vite dev proxy is not part of `dist/`. Never put backend keys or signing seeds in `VITE_` variables.

Build with `npm.cmd run build`; output is `dist/`. `npm.cmd run preview` also uses the local API proxy for development preview.

## Browser integration test

```powershell
npm.cmd run test:e2e
```

Uses installed Google Chrome, a test frontend on port 5174, and an isolated Django server on port 8011. Django's Python environment must already exist at `../Back-End/.venv`. The fixture refuses to run against any database except `.test-state/browser.sqlite3`, which it resets before each run. It never resets the normal backend database or uses your administrator password. Stop any conflicting services on these test ports first.

The test covers registration, session restoration, staff-only navigation, goals, challenge membership, pending activity, staff approval, point earnings, redemption, ledger balance, profile persistence, mobile navigation, and logout. Real Freighter transactions require separate manual checks.

