# Backend implementation progress

## Phase 1 — inspected / plan recorded

Active entry: index.html → src/main.jsx → src/marketplace-main.jsx. The alternate
src/app/App.jsx application is retained and is not the active bundle.

Existing pages: Home, Shop/categories/vendors/search/offers/wishlist, Product,
Access (login/register/recovery), Commerce (cart/checkout), Account (profile,
addresses/orders/wishlist/preferences), Management (products/inventory/vendors,
categories/promotions/banners/reports/settings), Info (static pages/404).
Components include Layout, DashboardLayout, ProductCard, Analytics, ui,
useHomepageMotion, useOverlayMotion, and three/Scene. Preserve all visual assets,
CSS, GSAP motion and Three.js scenes.

Routing: public storefront; /account customer; /vendor vendor; /admin admin.
Vendor self-registration and pending approval pages are missing. Only 404 exists.

Data boundary: src/services/marketplaceApi.js. Accounts use a universal mock
password. src/store/marketplaceStore.js persists user/cart/wishlist. Database
records use forma-marketplace-db-v2. Category/settings forms write snapshots
directly; account preferences, contact and newsletter also use browser storage.
Orders and stock are browser mutations. Payment and recovery are placeholders.
No backend or database migrations exist. Frontend shapes are camelCase, roles
lowercase, IDs strings, categories strings, order states title case.

Plan: create isolated backend/config and domain apps; PostgreSQL as persistent
default; explicit SQLite test settings only. Implement custom user/session/CSRF,
vendor approval, scoped catalog, transactional orders, payment adapters,
notifications/audit, idempotent local seeding. Replace active mock service with
async API and refresh normalized view data; retain layout and components. Add
missing workflow/error pages using existing classes. Test authorization/CSRF/
inventory/payment boundaries, build frontend, document actual limitations.

Environment discovery: Python 3.14.4 present. PostgreSQL/Redis/Docker not found
on PATH or as named services. No existing databases will be deleted. Provider
credentials have not been supplied; real gateways must remain disabled.

## Phase 2 — implemented; PostgreSQL runtime blocked

Virtual environment created. Installed Django 6.1.2, DRF, psycopg, Pillow, Redis,
Celery, spectacular and test/deployment dependencies. Exact installed versions in
backend/requirements.txt. Default settings use PostgreSQL and environment secrets.
SQLite is explicitly confined to test/smoke settings. Initial migrations generated
and applied to isolated test databases. No PostgreSQL instance was found.

## Phase 3 — implemented / tested

Custom email User with three roles; password validation/hashing, email verification,
single-use expiring reset tokens, session login/logout, CSRF retrieval and enforcement,
auth/IP throttles and account attempt lockout. No browser auth tokens or user persistence.

## Phase 4 — implemented / tested

Vendor multipart registration, image validation, PENDING default, decision permission,
atomic approval/rejection/suspension, self-approval prevention and audit records.
React registration/pending/review table added using existing design classes.

## Phase 5 — implemented / tested

Catalog, categories, decimal prices/discount constraints, inventory, image uploads,
archival, search/filter/sort/pagination, related products. Approved-store visibility
and owner-only writes enforced by server. Image re-encoding strips supplied metadata.

## Phase 6 — implemented / tested

Database cart/wishlist/addresses, order snapshots, stock reservation, idempotency,
multi-vendor fulfillment scoping, cancellation with single stock restoration,
delivered-purchase reviews. Shipping charged once per parent order; unpaid unshipped
orders alone are cancellable. Paid orders require admin refund assistance.

## Phase 7 — code implemented; external sandbox verification outstanding

Separate PayPal/Checkout.com/HyperPay adapters and local mock. Server verification,
PayPal signature verification API, Checkout HMAC, duplicate event protection,
payment records and refund requests. Real adapters disabled without explicit config.
HyperPay encrypted webhook handler deliberately fails closed: full official widget/
webhook documentation could not be retrieved, so merchant encryption details remain
unimplemented. No real-provider success claimed. Async refund reconciliation command
and Celery task added; trusted-provider result mappings need sandbox verification.

## Phase 8 — implemented

Durable notification outbox, local console delivery command, Celery delivery task,
audit records for decisions, orders, management and refunds. SMTP configurable.
Delivery is at least once; provider email deduplication not yet implemented.

## Phase 9 — implemented / tested

Idempotent local-only seed: 60 products, 10 categories, 5 approved stores plus one
pending application, reviews, sample paid order, promotion and banner. Four primary
accounts authenticate in automated tests; passwords from environment or generated
once. Existing cached Unsplash photos reused with source metadata. Exact-product
photo matching/licensing provenance beyond existing source IDs still needs review.

## Phase 10 — implemented; browser smoke passed

Active service/store now use session-aware async API. Existing catalog/account/
management handlers await mutations. Category/settings no longer write browser DB.
Guest cart alone may persist locally. Existing CSS, GSAP and Three.js retained.
Compatibility bootstrap is bounded to 100 records; full paginated dashboard/catalog
navigation beyond this dataset needs frontend work before large-scale deployment.

## Phase 11 — implemented; React routes verified

13 React error views, route fallback, structured API errors and Django error template.
Standalone fallback HTML and Nginx configuration added. SPA views themselves do
not set HTTP status; Nginx template maps document routes/status codes. Nginx has
not been installed or tested in this environment.

## Phase 12 — suite passing

25 passed, 1 PostgreSQL-only concurrency test skipped (SQLite test environment).
Covers registration, tokens, CSRF login/logout/cart, approval/suspension, ownership,
price validation, malicious uploads, stock/idempotency, order scoping, mock payments,
invalid/duplicate webhook signatures, throttling and four seeded account scenarios,
partial refunds, reconciliation idempotency, private projection data and image files.
Six frontend service/utility tests also pass. The seed photo files decode correctly.

## Phase 13 — local checks passed; infrastructure verification blocked

Django check passes; SQLite test migrations pass; React build passes with existing
Three.js chunk advisory. OpenAPI generation: zero errors and zero warnings.
Django check and production check --deploy pass (configuration checks only;
no Redis/PostgreSQL connection implied). No migration drift. Browser smoke passed
twice against disposable SQLite: catalog + image, four roles, vendor approval,
vendor dashboard, customer cart/mock payment/order, all thirteen error routes and
unknown-route fallback; no JavaScript page errors. Actual PostgreSQL connection
attempt to localhost:5432 timed out. Concurrency test remains skipped.

## Phase 14 — documentation written

backend/README.md documents Windows venv/PostgreSQL/migrations/seeding/email/API/
tests/startup, generated credentials, deployment and payment activation limits.
Main README now points to it and labels previous prototype documentation historical.
Dockerfile, infrastructure compose template, Nginx TLS/CSP/rate/error template,
local-secret initializer and ignored environment files added.

## Remaining release gates (do not mark fully production-ready)

- Install/configure PostgreSQL and Redis; apply migrations and seed on PostgreSQL;
  run postgres_test_settings including concurrent checkout against real row locks.
- Supply sandbox merchant credentials, register public HTTPS webhooks, validate all
  three providers, partial refunds and provider-specific currencies/country handling.
- Implement HyperPay encrypted webhooks from retrievable merchant documentation.
- Validate Nginx/Docker/SMTP/Celery deployment and provider CSP in the target environment.
- Replace bounded bootstrap compatibility reads with full paginated frontend queries
  before using datasets above 100 records per collection.
- Audit exact-product photography/provenance for commercial catalog use; photos here
  reuse the existing illustrative assets rather than claiming exact SKU identity.
- Add reservation expiry/business policy for abandoned orders, tax/payout/commission/
  returns rules as required before real financial transactions.

No source control repository was present (`git status` reports not a repository),
so Git diff checks could not run. No existing user database was deleted or replaced.

## PostgreSQL activation follow-up — 2026-10-24

User installed PostgreSQL 18 and configured backend/.env for ecommerce_db.
Verified normal config.settings loads DATABASE_URL from that file exactly, without
displaying its username/password or changing the file. Connected successfully to
PostgreSQL 18.6. The database was initially empty.

- `manage.py check`: passed before and after changes.
- `manage.py migrate --noinput`: all migrations applied successfully.
- Database introspection: all 29 expected model tables plus django_migrations
  exist (30 total); no missing tables and no pending migrations.
- Seeded missing development data: 8 users, 60 products, 10 categories, five
  approved vendors plus one pending application, and one sample order.
- Fixed seed failure: lowercase settings.env is not exposed by Django Settings.
  Read loaded environment variables directly; generate passwords when absent.
- Fixed seed rerun safety: existing secondary vendor passwords are now preserved.
- Fixed browser login throttling: routine session/CSRF GETs no longer consume
  the stricter login/registration/reset POST attempt budget.
- Five focused regression tests passed using isolated SQLite test settings.
- Started ordinary Django server (no smoke/test settings), readiness HTTP 200.
- Started existing React Vite development server, document HTTP 200.
- Real browser verification against PostgreSQL passed: four demo role logins,
  pending-vendor redirect, catalog/photography, browser CORS requests, CSRF token
  retrieval, missing-CSRF rejection, and CSRF-protected logout.
- Pending vendor remains PENDING. No approval/order/checkout mutations were run
  against the seeded PostgreSQL data during browser verification.

Generated local demo credentials are in ignored
`.setup/postgresql-demo-accounts-created.txt`; contents were not printed to tool
output. The initial failed seed left an empty ignored log file and no records,
because its transaction rolled back. Existing secrets were not overwritten.
No database/data was deleted, and no production build/project rebuild was run.

Both development servers remain running at http://localhost:8000 and
http://localhost:5175. Run commands from the repository root:

```powershell
backend/.venv/Scripts/python backend/manage.py runserver localhost:8000
npm run dev
```

This resolves PostgreSQL connectivity/migrations/seeding and browser API activation
gates above. PostgreSQL concurrency tests, Redis runtime, deployment and real
payment-provider verification remain outside this follow-up's completed checks.

## Frontend origin / duplicate-server fix — 2026-10-24

User's active React origin is http://127.0.0.1:5176, backend
http://127.0.0.1:8000. Reproduced the connection fallback in Chromium: requests to
the hardcoded localhost:8000 auth/session endpoint failed with net::ERR_FAILED.
Direct API calls returned 60 products, but the responding stale Django process
allowed localhost:5175 rather than the active 5176 origin.

Netstat showed TWO Django listeners on port 8000. Stopped only the older
agent-started Django process using its existing exec session. The remaining
user-started Django process already loads the correct existing .env: both
127.0.0.1:5176 and localhost:5176 allowed for CORS and CSRF. PostgreSQL 18.6
connects to ecommerce_db. No environment secret or database record was changed.

Changed active Axios default: development API hostname now follows the browser
hostname on port 8000, retaining withCredentials and CSRF handling. This avoids
localhost/127.0.0.1 SameSite cookie mismatch. Explicit VITE_API_BASE_URL still
overrides the default; production defaults to /api/ behind its reverse proxy.
Updated frontend .env.example to describe this behavior.

Inspected Vite config and custom launcher: no API proxy is configured. Direct
development API requests are intentional and verified against explicit CORS.
A proxy is not needed for this correction. An attempted restart of the existing
Vite process was denied by Windows; kept that process running and applied the
client fix via hot reload. No final Vite/launcher changes were required. The
separate port-5175 development server was left untouched.

Verification:
- Django check: passed. PostgreSQL connection: passed. GET /api/bootstrap/: 200,
  60 products.
- Chromium connection fallback: absent; failed API requests: zero.
- Real React sign-in passed for customer, vendor, admin and pending vendor, with
  correct workspace/pending redirects; pending vendor status was not modified.
- Homepage product cards and photograph loading passed.
- Browser API reads, CSRF retrieval, CSRF-less logout rejection (403), protected
  logout (204) passed; credentials remain enabled.
- CORS POST preflight: 200 for both configured port-5176 hostnames, explicit
  matching Access-Control-Allow-Origin, credentials true, X-CSRFToken allowed.
- Six frontend tests passed. No production build was run; CSS/GSAP/Three.js unchanged.

Working URLs: http://127.0.0.1:5176 and http://127.0.0.1:8000/api/bootstrap/.
