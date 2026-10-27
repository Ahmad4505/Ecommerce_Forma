# Backend verification — 2026-10-24

| Check | Actual result |
| --- | --- |
| Django installed | 6.1.2 in backend/.venv |
| Django system check | Pass |
| Production check --deploy | Pass with production configuration; not a connectivity check |
| Migration drift | No changes detected |
| Migrations applied | Pass on disposable SQLite test/smoke databases |
| PostgreSQL connectivity | Attempted localhost:5432; timed out; not verified |
| Backend pytest | 25 passed, 1 PostgreSQL concurrency test skipped |
| Frontend npm test | 6 passed |
| OpenAPI export | Generated backend/schema.yml, zero warnings/errors |
| Frontend production build | Pass; existing large Three.js chunk advisory |
| Browser integration | Passed twice against explicitly disposable SQLite data |
| Browser checks | Products, image, four accounts, approval, vendor products, cart, mock payment, order, 13 error views, unknown route, no page errors |
| Demo seed | Idempotent; 60 products, 10 categories, 5 approved stores + pending store |
| Existing photo assets | All seeded image paths exist and decode |
| Payment providers | Disabled without configuration; no external sandbox transaction performed |
| HyperPay encrypted webhook | Not implemented; fails closed with 503 |
| Redis/Celery/SMTP/Nginx/Docker | Configuration/code provided; runtime not verified |
| Git diff | Unavailable: workspace is not a Git repository |

SQLite cannot establish PostgreSQL locking correctness. Static configuration checks
do not establish deployment security. Existing photo files are illustrative and
their exact SKU identity/provenance needs commercial review. See README and the
root BACKEND_PROGRESS.md for activation steps and remaining release gates.

## PostgreSQL follow-up — 2026-10-24 (supersedes initial connectivity result)

Normal Django settings now connect successfully to the user's ecommerce_db on
PostgreSQL 18.6. DATABASE_URL matches backend/.env; no credentials were printed
and that file was not changed. The database initially contained no tables.

All migrations applied: 29 expected model tables + django_migrations, 30 total,
zero missing tables, zero pending migrations. Django check passes. Seed completed:
60 products, 10 categories, 8 users, 5 approved stores + 1 pending application,
and 1 sample order. Generated passwords are only in ignored
`.setup/postgresql-demo-accounts-created.txt`.

Two activation failures were fixed: settings.env access in seed_demo and routine
session/CSRF reads exhausting the login throttle budget. Seed reruns also preserve
existing secondary vendor passwords. Five focused regression tests passed using
disposable SQLite test settings.

Actual browser verification using normal Django + PostgreSQL passed for customer,
vendor, admin and pending-vendor login, correct redirects, browser CORS/API reads,
60 catalog records, image loading, CSRF retrieval/rejection and protected logout.
Django readiness and React both return HTTP 200. No pending application approval
or new order was performed. Servers remain running on localhost:8000 and :5175.
No existing data/secrets were deleted/overwritten and no rebuild was performed.

The PostgreSQL concurrency test and real gateway/deployment checks were not run
as part of this follow-up; the earlier skipped concurrency result remains unchanged.

## Active frontend connection — port 5176

Resolved a reproduced browser API failure at http://127.0.0.1:5176. Two Django
processes shared port 8000; the stale process served the old localhost:5175 CORS
configuration. Stopped that older agent-owned process and retained the current
backend, which correctly loads both port-5176 origins from the existing .env.
The Axios development default now uses the page's hostname on port 8000 instead
of hardcoding localhost. This also keeps session cookies on the same site.

Chromium verification passed for homepage products/photos, all four account
logins/redirects, browser catalog requests, CSRF enforcement and logout. The
connection fallback disappeared with zero failed API requests. CORS preflights
pass for localhost:5176 and 127.0.0.1:5176 with credentials enabled. PostgreSQL
18.6 connectivity, bootstrap (60 products), Django check and six frontend tests
pass. No rebuild, design changes, CSRF relaxation or database deletions occurred.

The existing Vite process hot-reloaded the client change; no frontend restart
was needed. Final Vite configuration intentionally has no API proxy, since direct
same-host development API access now works with explicit CORS/CSRF settings.
