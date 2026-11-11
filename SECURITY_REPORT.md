# Wellify security report

Date: 7 November 2026. Scope: the local Django backend and React frontend. Changes have not been deployed to a public host.

## Changes and reviewed controls

| Request | Result |
| --- | --- |
| Keep private API keys on the server | Provider credentials remain backend environment variables; provider responses disclose availability only. Frontend builds reject unapproved `VITE_` variables. Only the API URL and public Stellar issuer address are allowed. Added ignore rules for secrets, private key files, local databases and generated dependencies. |
| Users see only their own data | Reviewed user-scoped profile, goals, activity, summary, ledger, redemption, notification, membership and wallet queries. Added a regression check against reading/modifying another user's notification. Staff management endpoints intentionally access other accounts. This is API authorization, not database-native row-level security. |
| HTTPS and secure sessions | Debug defaults to false and the local backend `.env` was hardened. HTTPS redirects, HSTS, secure HTTP-only session/CSRF cookies, SameSite session cookies and origin restrictions are enabled for production. Production refuses weak signing keys and HTTP frontend origins. A weak local signing key is replaced when found; values are never printed. |
| Server validation | Existing DRF serializers and Django forms validate registration, profiles, goals, activity dates/ranges, challenges, reward stock/prices, plans, and passwords. Wallet signatures are verified server-side. Added reset-form password validation tests and a tampered-price/user test. Unknown price/user fields cannot change redemption ownership or the amount charged. |
| XSS defenses | React renders user values as escaped text; no raw HTML insertion was found. Added production frontend CSP, backend CSP, anti-framing, no-sniff, referrer and permissions headers. Sensitive backend responses are marked no-store/private. Inline scripts are disallowed; inline styles remain allowed for existing UI/admin styles. |
| SQL injection | Reviewed database access: application queries use the Django ORM and bound parameters. No application raw/interpolated SQL execution was found. Added a SQL-payload login regression test. |
| Login limits and CSRF | Existing login/registration API limit is 10/minute/IP; existing anonymous/user API limits remain. Added a 10/minute/IP limit for Django admin login and reset forms. Throttle identity ignores caller-supplied forwarded IP headers. CSRF remains required on login, registration and authenticated writes; reset forms use Django CSRF tokens. |
| Expiring password resets | Added `/auth/password-reset/` and Django reset-confirm routes/templates. Tokens expire after 1,800 seconds and are invalid after a password change. SMTP settings are server-only; no console-mail backend logs reset links. Tests cover expiry, one use, CSRF, email generation and weak-password rejection. |
| Upload limits | There is no file-upload product feature. Multipart forms containing files are rejected, including HTML files; ordinary forms remain supported. Declared request bodies above 256 KiB are rejected before parsing. Field counts are capped at 50. Apply equivalent limits at the ingress, including streamed requests. |
| Admin access | Retained Django's active-staff and model-permission checks and staff-only API permissions. Added admin/API access-denial and admin-login throttle regression tests. No public promotion endpoint exists. |
| Server prices | Redemption already locks the reward and account, reads current price/stock from the database, records a price snapshot, and debits points atomically with idempotency. Added a forged client price/owner test. Subscription billing remains simulated. |

## Dependencies

- Backend: upgraded Django REST Framework from 3.16.1 to 3.18.3 in the environment and both requirement files. Raised the Django minimum to the already installed 5.2.19. Other locked packages were checked rather than updated speculatively.
- Frontend: changed Stellar SDK from the vulnerable 14.x dependency tree to 16.4.1 and updated the npm lockfile. The new dependency tree removes the vulnerable `toml` dependency and other obsolete transitive dependencies. All declared direct packages have application, build, test or PostgreSQL deployment uses, so none were removed arbitrarily.
- npm audit of the updated lockfile: zero known advisories.
- OSV query of all 30 pinned Python packages after the DRF upgrade: zero known advisories. This is an advisory database check, not a guarantee of absence of vulnerabilities.
- Python dependency compatibility check: passed (`pip check`).

## Secret scan and rotation

`security_audit.py` scans selected source/config files and reports locations/types only, never matched values. Its optional `--online` mode checks the backend lockfile against OSV. It excludes dependency/build directories and deliberately excludes the backend's local environment files, which are the intended server-side secret store.

The working-tree scan identified a README example password, not a live credential. The predictable development fallback signing key was removed; debug-only fallback keys are now random. The local environment hardening replaces missing/weak signing keys without displaying them. No live provider credential was identified in the scanned working tree, so no external provider credentials were revoked or replaced.

**Git history was not scanned:** this workspace has no `.git` directory and no Git executable was available. A real clone, including all refs, is required to check historical commits and tracked environment files. Any actual historical credentials must be revoked at their issuer and replaced in the server environment; history deletion alone does not revoke credentials. The heuristic working-tree scan cannot certify historical or complete secret absence.

## Verification

- Final backend security and application suite after DRF upgrade: 52 tests run, 50 passed, two PostgreSQL-only concurrency tests skipped on SQLite. Includes the forwarded-IP spoofing regression. The reset test was rerun successfully after adding the password-length constraint.
- Django `check --deploy`: no issues.
- Existing tests cover activity ownership, permissions, CSRF, hashing, sessions, ledger integrity, stock rollback, reward retries, challenge claims, provider configuration and wallet signatures.
- Frontend build and browser checks are **blocked**. The C: drive repeatedly ran out of space during dependency extraction; a running build tool also held an initial file lock. `node_modules` is incomplete, including a truncated native Rollup binary, and must be restored before the frontend can run reliably. The manifest and lockfile are intact. A clean lockfile audit does not verify SDK compatibility or browser behavior. `node --check Front-End/vite.config.js` passed.
- Recovery attempts removed only generated npm download caches, npm temporary package backups, Vite's dependency cache, and unused generated SDK artifacts. Transparent NTFS compression was applied to generated dependencies to recover space. No personal files or application database records were deleted. The initial Vite process was no longer running when its identity was checked, so no user process was stopped by this task. It could not be restored with the incomplete dependency tree.

## Deployment and remaining requirements

1. Configure a real HTTPS hostname and TLS ingress for the frontend and backend, and HTTPS OAuth callback URLs. Django redirects requests; it does not issue a TLS certificate. Do not expose Vite's development server publicly. Serve the built frontend, collected admin assets, and proxy `/api/`, `/admin/` and `/auth/` appropriately.
2. Set `WELLIFY_TRUST_PROXY=True` only if the private ingress removes untrusted forwarding headers and supplies the real request scheme. Default throttling uses the direct peer address; configure real-client rate limiting at the ingress when it proxies multiple users.
3. Use a shared Django cache for multiple application workers. The default local-memory throttle is per process and cannot provide a global multi-worker limit. Apply additional rate/body/header limits at the ingress.
4. Configure SMTP, sender identity and actual reset-email delivery. Tests use an in-memory mail backend; no live reset email was sent. Use the same trusted HTTPS hostname for reset links and the app.
5. Keep database ports private, database credentials server-only, and database roles least-privileged. The local SQLite file is not a substitute for production database access controls. Run the skipped concurrency tests on PostgreSQL.
6. Supply a Git clone/history to complete historical secret scanning and any provider-side credential rotation. No external credential service has been accessed or modified.
7. Free at least 500 MB (preferably 1 GB) on C:, stop any Vite process holding dependency binaries open, then run `npm ci`, `npm run build`, and `npm run test:e2e` from `Front-End`. SDK browser compatibility and the production CSP remain unverified until these pass. Do not deploy the old `dist` output: rebuild it with the security changes first. Restore the development server with `npm run dev` only after dependency installation succeeds. Keep debug disabled for deployment; HTTP development requires the explicit local override described below.

HTTP local development is an explicit opt-in using `WELLIFY_DEBUG=True` and matching HTTP localhost origins. The test configuration is separate: `python manage.py test --settings=config.test_settings --noinput`. Production defaults stay secure.

## References

- [Django deployment checklist](https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/)
- [Django security and authentication settings](https://docs.djangoproject.com/en/5.2/ref/settings/)
- [DRF body-size advisory](https://github.com/advisories/GHSA-2m8g-3cmr-wg3w)
- [DRF content negotiation advisory](https://github.com/advisories/GHSA-33wh-fxxf-88vv)
- [Stellar dependency advisory](https://github.com/advisories/GHSA-82x6-q7mm-w9cf)
