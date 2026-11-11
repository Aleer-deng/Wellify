# Wellify — Django backend

A runnable wellness incentive API built with Python, Django 5.2 LTS, Django REST Framework and the Python Stellar SDK. The REST API uses `/api/v1/`; Django's staff administration is at `/admin/`.

This is a project implementation, not a HIPAA/GDPR compliance certification. Real provider integrations, production security operations, legal requirements, and a deployment review remain necessary before collecting sensitive health data.

## Local setup (Windows PowerShell)

Requires Python 3.11–3.13. Use `python`, as the Windows `py` launcher may not be configured.

```powershell
cd "C:\Users\LE KO\OneDrive\Desktop\Digital Heealth\Back-End"
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
# In .env, generate DJANGO_SECRET_KEY and configure HTTPS origins.
# For HTTP development on your own computer only, explicitly use WELLIFY_DEBUG=True
# and set FRONTEND_ORIGINS/WELLIFY_FRONTEND_URL to the HTTP localhost origins.
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py seed_demo
.\.venv\Scripts\python.exe manage.py createsuperuser
.\.venv\Scripts\python.exe manage.py runserver
```

Open `http://127.0.0.1:8000/api/v1/status/` to check the API, and `/admin/` for staff management. No default password or administrator is created. `seed_demo` adds three prototype rewards and a challenge, not users or free points. SQLite works out of the box; migrations are committed.

On macOS/Linux, use `.venv/bin/python` instead of `.\.venv\Scripts\python.exe`.

## Implemented behavior

- Registration with normalized unique email, Django password validation and hashed passwords.
- Login/logout with server-side sessions, HTTP-only session cookies, CSRF validation on login/registration and authenticated writes, and configurable CORS origins.
- Current-user profile, daily/weekly goals, paginated activity history, and approved activity summaries.
- Activity sync with record deduplication, date/range validation, review status and staff approval/rejection.
- Challenges, membership, and one-time completion claims based on approved activity dated within the challenge and on/after joining.
- Double-entry point posting with an offsetting issuance/redemption system account, nonnegative user balances, reconciliation command and read-only ledger admin.
- Stock-controlled redemption with atomic debit, price snapshot, UUID idempotency keys, staff fulfillment and notifications.
- Notifications, read state, simulated subscription plans, staff user/catalog/challenge management, reports and application audit events.
- Stellar Testnet wallet ownership proof and read-only balances. No private keys or health data are written to Stellar.

## Authentication and React integration

The React app connects to this API using cookie sessions and CSRF tokens. Its Vite server proxies `/api` to `http://127.0.0.1:8000`. Open `http://127.0.0.1:5173` for the frontend. Balances, activity, catalog, redemptions, notifications, and admin actions use server data; the old browser demo balances are ignored.

Use the same hostname in both applications, for example `localhost:5173` and `localhost:8000`. Browsers treat `localhost` and `127.0.0.1` as different sites. Every fetch needs `credentials: 'include'`.

```js
const base = 'http://localhost:8000/api/v1';
let csrfToken;

async function api(path, method = 'GET', body) {
  const response = await fetch(`${base}${path}`, {
    method,
    credentials: 'include',
    headers: {
      ...(body === undefined ? {} : { 'Content-Type': 'application/json' }),
      ...(['GET', 'HEAD', 'OPTIONS'].includes(method) ? {} : { 'X-CSRFToken': csrfToken }),
    },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  if (response.status === 204) return;
  const data = await response.json();
  if (!response.ok) throw new Error(JSON.stringify(data));
  if (data.csrfToken) csrfToken = data.csrfToken;
  return data;
}

await api('/auth/csrf/');
await api('/auth/register/', 'POST', {
  name: 'Jamie Davis', email: 'jamie@example.com', password: 'use-a-strong-unique-password',
});
// Registration logs the user in. Login rotates CSRF too; retain the returned token.
const summary = await api('/health/summary/');
const catalog = await api('/rewards/'); // { count, next, previous, results }
// Save this UUID until the request outcome is known. Reuse it for retries.
const key = crypto.randomUUID();
await api('/rewards/redeem/', 'POST', { reward_id: 1, idempotency_key: key });
```

New users start with **zero** points, so the redemption above succeeds only after sufficient approved earnings. Re-fetch authoritative balance and redemption history after a successful request. Use `/profile/` to restore a session after a page reload. Log out with POST `/auth/logout/` and clear frontend user state.

## Google, Apple and Microsoft sign-in

The login and registration pages include Google, Apple (Mac/iPhone Apple accounts), and Microsoft options. Buttons start a CSRF-protected provider redirect and return to the React app with the same Django session used by password login. Until credentials are configured, selecting a provider explains that email/password sign-in is still available.

Install the updated requirements and run `python manage.py migrate` using your virtual environment to create django-allauth's tables. Existing password accounts continue to work.

Set `WELLIFY_FRONTEND_URL` in `.env` to your frontend origin, then register provider apps and set their server-side credentials:

| Provider | Environment variables | Registered callback path |
| --- | --- | --- |
| Google | `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | `/api/v1/auth/social/google/login/callback/` |
| Apple | `APPLE_CLIENT_ID` (Services ID), `APPLE_KEY_ID`, `APPLE_TEAM_ID`, `APPLE_PRIVATE_KEY` (downloaded .p8 contents, literal `\n` between lines) | `/api/v1/auth/social/apple/login/callback/` |
| Microsoft | `MICROSOFT_CLIENT_ID`, `MICROSOFT_CLIENT_SECRET` | `/api/v1/auth/social/microsoft/login/callback/` |

For Google/Microsoft local development through Vite, register the full callback URL, for example `http://127.0.0.1:5173/api/v1/auth/social/google/login/callback/`. Keep the browser, frontend return URL, and callback on the same hostname and port; `/api` is proxied to Django. For production use the public HTTPS origin. Apple requires an Apple Developer setup with a Services ID, Sign in with Apple key, verified domain and HTTPS return URL; use a public HTTPS development domain for Apple testing. Microsoft app registration should support both personal and organizational accounts if both are intended.

Restart Django after changing credentials. `GET /api/v1/auth/providers/` reports provider availability without exposing secrets. Do not also configure the same provider through allauth's Social Applications admin when using environment credentials: duplicate configurations are ambiguous.

New social accounts receive goals, an Explorer subscription, a welcome notification and **zero points**, with an unusable password. Existing accounts are never linked solely by matching email; use the original sign-in method if the email is already registered. Cancelled/failed sign-ins return to the login page with a readable error. Provider credentials are required to test the real provider consent/callback flow; local automated tests cover configuration, CSRF, account initialization, duplicate-email protection and suspended accounts.

Provider setup references: [Google](https://docs.allauth.org/en/latest/socialaccount/providers/google.html), [Apple](https://docs.allauth.org/en/latest/socialaccount/providers/apple.html), [Microsoft](https://docs.allauth.org/en/latest/socialaccount/providers/microsoft.html).

## API endpoints

All paths below are relative to `/api/v1/` and have trailing slashes. All except status, CSRF, provider availability, registration and login require a session. Lists use page-number pagination unless stated otherwise.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `status/` | Service status |
| GET | `auth/csrf/` | Get CSRF token and cookie |
| GET | `auth/providers/` | Public provider names and configured availability |
| POST | `auth/register/` | `{name,email,password}`; create user/session |
| POST | `auth/login/` | `{email,password}`; email accepts an email or username; create session |
| POST | `auth/logout/` | Invalidate current session |
| GET / PATCH | `profile/` | View/edit `name`, `city`, `bio`; email read-only |
| GET / PUT | `goals/` | List/upsert `{period:"daily"|"weekly",target}` |
| POST | `health/sync/` | Submit one incremental activity record |
| GET | `health/records/` | Current user's activity records |
| GET | `health/summary/` | Today's totals, weekly totals, seven daily buckets, goals and balance |
| GET | `challenges/` | Active challenge catalog |
| GET | `challenges/memberships/` | Current user's memberships (unpaginated) |
| POST | `challenges/{id}/join/` | Idempotently join |
| POST | `challenges/{id}/claim/` | Claim completion once |
| GET | `rewards/` | Active catalog with current stock |
| GET | `rewards/balance/` | Server-authoritative points |
| GET | `rewards/history/` | Current user's signed ledger entries |
| POST | `rewards/redeem/` | `{reward_id,idempotency_key}` |
| GET | `rewards/redemptions/` | Current user's requests and fulfillment status |
| GET / PATCH | `notifications/`, `notifications/{id}/` | List / update `{read:true}` |
| GET / PUT | `subscription/` | View / select `{plan:"explorer"|"plus"|"community"}`; simulation only |
| POST | `wallet/challenge/` | Get an exact message for ownership proof |
| POST | `wallet/verify/` | `{address,signature}`; signature is base64 Ed25519 over the UTF-8 challenge |
| GET | `wallet/` | Verified linked wallet and live Testnet balances |
| GET / PATCH | `admin/users/`, `admin/users/{id}/` | Staff user list/search and nonstaff account status |
| GET / POST / PATCH / PUT | `admin/rewards/`, `admin/rewards/{id}/` | Staff reward management |
| GET / POST / PATCH / PUT | `admin/challenges/`, `admin/challenges/{id}/` | Staff challenge management |
| GET | `admin/activities/` | Staff activity review queue |
| POST | `admin/activities/{id}/review/` | `{decision:"approve"|"reject"}` |
| GET | `admin/redemptions/` | Staff fulfillment queue |
| POST | `admin/redemptions/{id}/fulfill/` | Mark manual fulfillment complete |
| GET | `admin/reports/` | Counts, points redeemed and global ledger net |

Staff endpoints require `is_staff=True`. Django admin also allows staff to manage records according to Django permissions. There are no public role-promotion endpoints. Profile email changes and staff account suspension are intentionally restricted to separate administrative workflows.

### Activity contract and points rules

```json
{
  "external_id": "device-record-unique-123",
  "source": "health_connect",
  "date": "2026-11-06",
  "steps": 10000,
  "active_minutes": 45
}
```

Send **incremental, nonoverlapping records**, not repeated daily cumulative snapshots. The date must be within the last 31 days and cannot be future-dated. Sources supported as labels: `manual`, `health_connect`, `healthkit`, `fitbit`, `garmin`. These labels do not establish provider authenticity; OAuth/device integrations are not implemented. Staff must review records before rewards are granted.

The unique record identity is `(user, source, external_id)`. An identical retry returns the original record; a changed payload with the same identity returns 409. Per-record and per-day approved totals are limited to 100,000 steps and 1,440 minutes. Bounds and deduplication are basic safeguards, not a complete anti-fraud engine.

Approvals award one point per 100 approved daily steps using cumulative rounding. Re-reviewing a finalized record never awards twice. Approved records cannot be edited through the API. The same steps can contribute to a challenge bonus, which is paid only once per membership. Challenge qualification includes the calendar day of joining because activity has date-level granularity.

### Ledger and fulfillment

Each reward transfer creates exactly two entries, with net zero, and updates both cached balances in one database transaction. The issuance system account may be negative; user accounts cannot be negative. Stock, points debit, redemption request and notification commit or roll back together. A redemption UUID is scoped to its user and cannot be reused for a different reward.

Ledger records are exposed read-only in Django admin and the API. Reconcile regularly:

```powershell
.\.venv\Scripts\python.exe manage.py check_ledger
```

This is application-enforced posting integrity, not tamper-proof database storage. Direct SQL or privileged code can still change rows. Production requires database permissions, controlled migrations, independent audit storage, backups and reconciliation alerts. Holds, expirations, cancellation/refunds and third-party voucher delivery are not implemented. Staff fulfillment records a manual action and does not contact a payout provider.

## Stellar and HRW

The backend always reads Stellar **Testnet**, and its internal point ledger is separate from on-chain HRW. Set `HRW_ISSUER_PUBLIC_KEY` to the token issuer's public key, matching frontend `VITE_HRW_ISSUER`. Ownership proof is a custom short-lived, single-use signature challenge, not a SEP-10 implementation. The client must sign the exact raw UTF-8 message; a wallet's prefixed/hashing message-signing scheme requires a matching verifier before integration. The existing Freighter frontend connection does not automatically link a backend wallet.

No minting, distribution worker, payment execution, seed storage or points-to-token conversion is implemented. The frontend already supports Testnet trustline signing. Keep issuer/distributor private keys out of this repository and out of all `VITE_` variables. Future distribution needs an outbox, persistent signed-transaction identity, retry reconciliation, a protected signer and an explicit conversion policy.

## Tests

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe manage.py test wellness --noinput
```

Tests cover CSRF, password storage, session logout, inactive users, input validation, duplicate sync, access isolation, staff permissions, approval rules, ledger integrity, reward retry/rollback, challenge claims, subscriptions, notifications and wallet signatures. Network failure is mocked. PostgreSQL-only concurrent redemption tests are skipped on SQLite; run the suite against PostgreSQL before deploying. SQLite is for local development and may return lock errors under concurrent writes. Use `python manage.py test --settings=config.test_settings` for the explicit HTTP-only test configuration.

## PostgreSQL and deployment

Set the `POSTGRES_*` variables from `.env.example` to use PostgreSQL. The same ORM migrations work for both databases. PostgreSQL database credentials need a test-database creation permission to run Django tests.

For production:

1. Set `WELLIFY_DEBUG=False`, a strong random `DJANGO_SECRET_KEY`, specific `ALLOWED_HOSTS` and exact HTTPS `FRONTEND_ORIGINS`.
2. Use PostgreSQL, apply migrations, create administrator accounts and run tests/reconciliation. Set up database backups and restore testing.
3. Run `collectstatic` and `check --deploy`. Serve using a production WSGI/ASGI server behind HTTPS; do not use `runserver` publicly. A deployment-specific WSGI server is not included in requirements.
4. Use the frontend and API on the same site for the current SameSite=Lax cookie setup. Configure cross-site cookies/CSRF separately if hosting on different sites. Only trust forwarded HTTPS headers from a proxy you control.
5. Replace the default per-process cache with a shared cache and enforce edge rate limits before multi-worker deployment. DRF's throttles are approximate abuse controls, not a denial-of-service defense.
6. Establish consent, data retention/export/deletion policies, audit review, operational access controls, telemetry encryption/storage protections and provider-specific verification before using real health data. The implementation does not claim automatic encryption at rest, mTLS, or complete data-access auditing.

Redis/BullMQ, TimescaleDB, wearable OAuth ingestion, push delivery, real subscription billing, team leaderboards and third-party payouts are future integrations. Email verification needs additional configuration. Password reset is available at `/auth/password-reset/` and requires working SMTP settings; links expire after 30 minutes and become invalid after use.

## Security configuration

Debug is off by default. Production refuses missing/placeholder signing keys and HTTP frontend origins. Generate a unique key with `python -c "import secrets; print(secrets.token_urlsafe(64))"` and keep it in the backend `.env` or a server secret manager. Never put private credentials in `VITE_` variables; the frontend build accepts only the public API path and public Stellar issuer. Use same-origin `/api/v1` in production.

Production requires a real TLS ingress; Django redirects HTTP but does not issue TLS certificates. If the ingress strips untrusted forwarding headers and supplies the actual scheme, set `WELLIFY_TRUST_PROXY=True` and keep the Django port private. Configure HTTPS provider callbacks and SMTP credentials. Serve `/auth/` to Django for reset forms, plus `/api/`, `/admin/`, and collected admin static assets. Restart the backend after changing environment values. Existing sessions may need a new login after signing-key changes.

Login API limits remain 10 requests/minute/IP. Admin and reset forms also have a 10/minute/IP limit. Multiple application workers require a shared Django cache via `WELLIFY_CACHE_BACKEND`/`WELLIFY_CACHE_LOCATION`; the default memory cache is per process. Apply ingress request/body limits as well. File uploads are unsupported and rejected; request bodies are capped at 256 KiB. Staff APIs remain staff-only, and personal data queries are scoped to the current user. Production database users must have minimal privileges, and database ports/files must not be public.

See [the security report](../SECURITY_REPORT.md) for verification and outstanding deployment checks.

## References

- [Django 5.2 documentation](https://docs.djangoproject.com/en/5.2/)
- [DRF authentication and CSRF](https://www.django-rest-framework.org/api-guide/authentication/)
- [Python Stellar SDK](https://stellar-sdk.readthedocs.io/)

## License

No project license has been selected. Add a license before public distribution.
