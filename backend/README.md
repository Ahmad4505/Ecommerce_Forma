# Forma Django backend

This backend integrates the existing React marketplace. Its visual components,
styles, GSAP effects and Three.js scenes are retained. The active application is
`src/marketplace-main.jsx`; older alternate frontend modules remain historical.

The implementation and verification ledger is [BACKEND_PROGRESS.md](../BACKEND_PROGRESS.md).
This is **not yet a verified production deployment**. Local PostgreSQL, role
logins and the disposable Playwright audit have now been verified; see
[TEST_RESULTS.md](../TEST_RESULTS.md) and [FUNCTIONAL_AUDIT.md](../FUNCTIONAL_AUDIT.md).
Redis, production mail delivery and external payment gateways are not production-verified.
The existing local backend trusts port 5176: run `npm run dev -- --port 5176` and
open http://127.0.0.1:5176. For other environments, keep the frontend port aligned
with FRONTEND_URL, CORS_ALLOWED_ORIGINS and CSRF_TRUSTED_ORIGINS.

## Windows / VS Code setup

Run PowerShell from the repository root. Python 3.14 and Node are available here.
The virtual environment and Python dependencies have already been created locally.
To reproduce:

```powershell
python -m venv backend/.venv
backend/.venv/Scripts/python -m pip install -r backend/requirements.txt
backend/.venv/Scripts/python scripts/init-backend-env.py
Copy-Item .env.example .env.local
```

`init-backend-env.py` writes a unique secret to ignored `backend/.env`, preserving
an existing file. Set `DATABASE_URL` to your local database; URL-encode reserved
characters in its password. Keep every real credential out of Git.

Install PostgreSQL using the [official Windows download](https://www.postgresql.org/download/windows/),
then use SQL Shell (psql), connected as a local database administrator:

```sql
CREATE ROLE ecommerce LOGIN;
\password ecommerce
CREATE DATABASE ecommerce OWNER ecommerce;
```

Choose a unique local password at the prompt. Set, for example:
`DATABASE_URL=postgresql://ecommerce:YOUR_URL_ENCODED_PASSWORD@localhost:5432/ecommerce`.
Do not run CREATE DATABASE against an existing project database. Use that database's
existing connection details instead. These instructions never drop databases.

Alternatively, after installing Docker Desktop, start the provided infrastructure:

```powershell
$env:POSTGRES_PASSWORD = Read-Host 'Choose a local PostgreSQL password'
docker compose up -d db redis
```

Set the same database password in `backend/.env` and `REDIS_URL=redis://localhost:6379/0`.
Without Redis, DEBUG development uses an in-process cache; production requires Redis.

```powershell
backend/.venv/Scripts/python backend/manage.py migrate
backend/.venv/Scripts/python backend/manage.py seed_demo
backend/.venv/Scripts/python backend/manage.py runserver localhost:8000
```

In another terminal:

```powershell
npm ci
npm run dev
```

The default frontend launcher reads Django's public `FRONTEND_URL` and uses its
configured loopback host/port. The current development origin is
**http://127.0.0.1:5176**, with Django at **http://127.0.0.1:8000**. Use the same
hostname on both sides for session cookies and CSRF. The development API default
follows the browser hostname on port 8000; set `VITE_API_BASE_URL` only when an
override is needed. For a same-origin production proxy use `/api/` and rebuild.

## Local demo accounts

| Email | Role | Store status |
| --- | --- | --- |
| admin@ecommerce.test | ADMIN, staff, superuser | — |
| vendor@ecommerce.test | VENDOR | APPROVED |
| customer@ecommerce.test | CUSTOMER | — |
| pending.vendor@ecommerce.test | VENDOR | PENDING |

`seed_demo` creates accounts only under DEBUG. It reads `DEMO_ADMIN_PASSWORD`,
`DEMO_VENDOR_PASSWORD`, `DEMO_CUSTOMER_PASSWORD`, `DEMO_PENDING_PASSWORD` from your
environment or ignored backend `.env`. Empty values generate unique random
passwords printed once on account creation. Save them in your password manager.
Subsequent seeds preserve existing passwords and records. Use `changepassword`
if a generated password is lost:

```powershell
backend/.venv/Scripts/python backend/manage.py changepassword customer@ecommerce.test
```

The seed creates 60 products, ten categories, five approved stores, a pending
store, reviews, a sample delivered order, a banner and WELCOME10. Development
photos reuse existing `public/images` Unsplash files; provenance source IDs and
the license URL are stored on image records. Photography is illustrative;
exact product/material matching and original photographer attribution must be
reviewed before use as a real commercial catalog. The existing fallback SVG is used
if an image fails. Product image URLs beginning `/images/` resolve on the frontend.

## Authentication and permissions

The browser authenticates with Django HttpOnly session cookies. Fetch
`GET /api/auth/csrf/`, then send its `csrfToken` in `X-CSRFToken` for unsafe
requests. Login rotates CSRF; retrieve it again after login. Axios handles this.
No authentication tokens or authenticated user objects are persisted in localStorage.
Guest cart/wishlist and explicitly local UI preferences may use localStorage.

Registration sends a verification link and does not authenticate an unverified user.
Reset/verification tokens are random, hashed at rest, expire after one hour, and
are consumed under a row lock. Password changes invalidate old Django sessions.
Emails use a durable outbox. To print local messages and links:

```powershell
backend/.venv/Scripts/python backend/manage.py deliver_notifications
```

For queued production delivery on Linux/WSL, with Redis and SMTP configured:

```text
celery -A config.celery:app worker --loglevel=INFO
celery -A config.celery:app beat --loglevel=INFO
```

Run one mail delivery scheduler. Delivery is at least once; SMTP interruption can
result in a duplicate message. Console output includes private recovery links.

Django 6.1 email configuration uses `MAILERS`. Existing `EMAIL_BACKEND`,
`EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`,
`EMAIL_USE_TLS` and `EMAIL_TIMEOUT` environment inputs remain supported without
renaming or rewriting `.env`; settings map them into the default mailer. SMTP
options are supplied only to the SMTP backend. The default development console
backend prints verification/reset links; isolated tests use the in-memory mailer.
No transport connection is made merely by reading settings. Production SMTP
delivery still requires separate configuration and verification. See Django's
[mailers migration guide](https://docs.djangoproject.com/en/dev/howto/mailers-migration/).

Vendor registration is multipart at `/api/vendor-applications/`. Required fields
are documented in OpenAPI and shown at `/vendor-register`. Applications begin
PENDING. Admin review is `/admin/vendors`, with an additional Django admin at
`/internal-admin/`. Decisions require ADMIN + staff + `vendors.approve_vendor`.
Pending, rejected and suspended stores cannot manage products or fulfillment.
Roles and ownership are checked on every protected API request.

## Commerce rules

Prices, discounts, shipping and currency come from backend records. Inventory is
reserved when an order is created. Checkout locks the customer, product rows in
stable order, and vendor rows. The idempotency key is unique per customer; reuse
it for identical retries. Changed requests with the same key return 409.
No order may oversell stock through this service.

Shipping is charged once for the parent multi-vendor order: $8 below a $150
pre-discount subtotal by default. Settings are editable. Vendors see only their
own line snapshots and shipping address needed for fulfillment, without other
vendors' items or whole-order amounts. Each store advances Processing → Shipped →
Delivered after successful payment. Parent status advances when all stores qualify.

Only unpaid, unshipped orders without an in-progress real provider payment can
be cancelled; stock restores once. An external payment must be reconciled before
releasing inventory, even if a webhook has not arrived. Paid orders
need administrator refund assistance. No automatic reservation expiry is implemented:
abandoned unpaid orders currently require cancellation. Taxes, marketplace payouts,
commissions, disputes, returns logistics and legal invoicing need business-specific
requirements before real trading.

## Payment adapters and activation limits

All real adapters are **sandbox/test only**, disabled unless named in
`ENABLED_PAYMENT_PROVIDERS`. Never enable mock mode in production; settings enforce
`DEBUG and MOCK_PAYMENTS_ENABLED`. The local mock makes no financial transaction.
The payment form collects no raw card data. An order success route never proves
payment; verification calls the provider on the server.

Official documentation reviewed for this implementation:

- [PayPal Orders API](https://developer.paypal.com/api/rest/integration/orders-api)
  and [webhook verification](https://developer.paypal.com/api/webhooks/v1).
- [Checkout.com hosted payments reference](https://api-reference.checkout.com/tag/hosted-payments-page)
  and [signature verification](https://support.checkout.com/hc/en-us/articles/29686673313426-Verify-a-webhook-was-sent-by-Checkout-com).
- [HyperPay integration options](https://www.hyperpay.com/integration-guide/),
  linking to its [widget guide](https://hyperpay.docs.oppwa.com/integrations/widget).
  The detailed HyperPay site could not be fetched in this environment.

PayPal requires client ID, secret and registered webhook ID. It uses Orders v2,
server capture, idempotent request IDs, amount/currency/reference checks and PayPal's
signature verification API. Register capture event webhooks at
`/api/payments/webhooks/paypal/` and test retries/capture failures in sandbox.

Checkout.com requires its account-specific sandbox base URL, secret and webhook
signing key, plus hosted-page access enabled by Checkout.com. It uses hosted
payments, raw-body HMAC-SHA256 verification and gateway payment detail retrieval.
Configure `/api/payments/webhooks/checkout/`. Signed gateway IDs are verified by
the provider API, including captured status, amount, reference and currency.

HyperPay requires an entity ID and bearer token for the test environment. Checkout
creation and server verification are provided, with a frontend COPYandPAY page.
**Encrypted HyperPay webhooks are not implemented**: that route returns 503,
pending merchant-specific documentation and sandbox fixtures. Browser callbacks
can trigger server-side status verification, never mark payment paid directly.
Confirm regional test host, result-code mapping, callback widget behavior and
merchant contract before enabling this adapter. Live hosts are not implemented.

Settlement currently supports configured two-decimal USD/EUR/GBP/SAR/AED only.
Provider account/country/currency support must be confirmed independently. Checkout
currently defaults hosted billing country to US; proper ISO country selection is
needed for other merchant markets.

Admins can request partial/full refunds at
`POST /api/payments/{id}/refunds/` with `amount`, `reason`, `idempotency_key`.
Captured funds and idempotency are checked. Mock/completed synchronous refunds are
recorded as successful; asynchronous gateway acknowledgements remain PENDING.
`reconcile_refunds` (also scheduled by Celery beat) polls trusted provider refund
status and records each completed refund once. Its real-provider mappings still
require sandbox validation. Do not retry
with a new key to work around an unknown result. These adapters are code-complete
only for the flows described here, not certified or end-to-end gateway-tested.

## API and validation

Swagger UI: `/api/docs/`; schema: `/api/schema/`; internal admin:
`/internal-admin/`; health: `/health/ready/`. Documentation is admin-restricted
under DEBUG=False. Most REST lists return `count`, `next`, `previous`, `results`.
`page_size` is capped at 100. Products support search, ordering, category/vendor/
status/featured filters and `/products/{id}/related/`.

The compatibility `/api/bootstrap/` projection contains bounded, scoped view data
for the existing frontend, capped at 100 records per collection. Server list APIs
are paginated; full frontend pagination across datasets beyond this compatibility
cap remains a deployment limitation. Current customer/vendor dashboard charts
derive from the scoped response; `/api/analytics/` computes server aggregates.

Uploads accept JPEG/PNG/WebP under 2 MB, dimensions 32–6000 pixels, decode and verify
content, then re-encode with UUID names. Up to eight product images are supported
by both the API and the existing frontend upload control. Browser-fetched remote URLs must allow CORS; a local upload is more reliable.
User remote image URLs are not fetched by Django, preventing an SSRF fetch path.

Structured API errors use `{error: {status, details}}`. Django handlers avoid
debug output in production. The thirteen new React error routes are previews
under `/errors/{status}`. SPA navigation cannot set document HTTP status; the
provided Nginx template maps initial error documents and infrastructure errors
to real HTTP statuses with standalone fallback pages.

## Tests and verification

```powershell
Push-Location backend
.venv/Scripts/python -m pytest -q
# PostgreSQL test user must have CREATEDB, or use a dedicated test database owner.
.venv/Scripts/python -m pytest --ds=config.postgres_test_settings -q
Pop-Location
npm test
npm run build
backend/.venv/Scripts/python backend/manage.py check
backend/.venv/Scripts/python backend/manage.py makemigrations --check --dry-run
backend/.venv/Scripts/python backend/manage.py spectacular --file backend/schema.yml
```

The normal pytest configuration deliberately uses in-memory SQLite. The concurrency
test skips unless PostgreSQL is active; SQLite results do not prove row-lock behavior.
Use a dedicated local/test DB role for the PostgreSQL command, not production credentials.

For disposable browser integration tests, with ports 8000 and 5175 free:

```powershell
backend/.venv/Scripts/python backend/manage.py migrate --settings=config.smoke_settings
backend/.venv/Scripts/python scripts/prepare-backend-smoke.py
backend/.venv/Scripts/python backend/manage.py runserver localhost:8000 --settings=config.smoke_settings --noreload
# Another terminal:
npm run dev
# A third terminal:
npm run test:integration
```

Smoke settings are explicitly test-only, with data/credentials under ignored
`.setup/`. The preparation script resets only the disposable pending application
to PENDING so the approval test can be repeated. Never use smoke
settings with real customer data. Historical prototype tests are retained under
`tests/legacy`; old browser fixtures target the former universal-password prototype
and are not evidence of backend correctness.

## Production deployment prerequisites

Use Linux/WSL/container Gunicorn; Gunicorn is not a native Windows development
server. `backend/Dockerfile` is supplied. Apply migrations explicitly, collect
static files, then run the image behind TLS Nginx using
`deployment/nginx.conf.example` as an environment-specific template.

Set DEBUG=False, unique secret, PostgreSQL URL, Redis URL, explicit hosts/origins,
SMTP, secure frontend URL and `TRUST_PROXY=True` **only** behind a private trusted
proxy that overwrites X-Forwarded-Proto. Block direct public access to Gunicorn.
Build frontend with `/api/`. Run `check --deploy`; configure backups/restore,
monitoring, private media storage, log retention and operational alerting. The
provided CSP keeps Three.js/GSAP working without broad script eval permissions;
payment-provider CSP must be validated against actual sandbox responses.

Nginx/Docker/Redis/SMTP deployment and real gateway tests have not run here. The
remaining limits above and the PostgreSQL concurrency test are release gates.


## Current functional audit tests

`npm run test:e2e` (also `npm run test:integration`) starts a temporary Django live
server and React server against pytest's disposable PostgreSQL database. It does
not approve vendors or place orders in the development database. Generated test
credentials and uploaded images stay in test temporary storage. Browser results
are written to ignored `.functional-audit-results/browser-run.log`.

For all backend checks plus the browser harness in PowerShell:

```powershell
$env:RUN_BROWSER_AUDIT = '1'
backend/.venv/Scripts/python -m pytest backend -q --ds=config.postgres_test_settings
npm test
npm run build
```

The configured PostgreSQL role needs permission to create the dedicated test
database. The regular SQLite test configuration intentionally skips the
PostgreSQL concurrency case and opt-in browser harness. Legacy mock browser
suites are retained for history and excluded from playwright.audit.config.js.
