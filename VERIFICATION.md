# Verification — Forma Marketplace

Verified on Windows with Node 20.15, npm 10.7 and installed Chrome. Node 22.12+ is recommended for the current Drei dependency tree.

## Completed

- `npm install --no-audit --no-fund`: **exit 0**. The existing Node runtime produces an engine advisory for camera-controls; installation completes.
- Vite development server: **running at http://127.0.0.1:5175/**. Shop rendering and customer sign-in were checked directly with no uncaught browser errors.
- Production build: **completed**, generating `dist-forma/`. The lazy 3D scene produces a size advisory, approximately 892 KB before compression and 241 KB compressed.
- Unit/service verification: **13 tests passed** across `services.test.js`, `api.test.js` and `shop.test.js`. The selected marketplace's seven service tests cover records, roles, vendor ownership, checkout totals, combined-variant stock limits, suspension, fulfillment, cancellation and purchased-product reviews.
- Selected application browser suite: **6 tests passed (1.6 minutes)** using `playwright.forma.config.js` against port 5175.

## Browser coverage

1. Search and sorting, guest bag preservation, sign-in redirect, discount application, validated checkout, order confirmation, persistence after reload and cancellation.
2. Vendor product creation, editing, inventory updates, persistence and deletion.
3. Administrator vendor creation, suspension, persistence and blocked suspended-vendor sign-in.
4. Public pages, categories, storefronts, policies, recovery interfaces, 404, mobile navigation and horizontal-overflow checks.
5. Every customer, vendor and admin dashboard route and detail screen; all role-specific mobile sidebars; cross-role route denial.
6. Quick view, Escape dismissal, wishlist, cart drawer, quantity updates, search overlay and reduced-motion interaction.

## Visual/runtime checks

`tests/visual-check.mjs` passed against the production preview on port 4175. It checked 1440×1100 desktop, 768×1024 tablet and 390×844 mobile layouts, including the shop, with no horizontal overflow. All 28 homepage photographs loaded without using fallback images. Two procedural WebGL canvases rendered. GSAP hero text and ScrollTrigger product reveals became visible with motion enabled. The run recorded no uncaught JavaScript errors or failed HTTP responses. Screenshots are in `tests/screenshots/forma-desktop.png`, `forma-tablet.png` and `forma-mobile.png`.

## Scope of the result

These checks validate the frontend prototype and its browser-local mock behavior. They do not establish production security, actual payment processing, real delivery, backend concurrency, email delivery, assistive-technology certification or cross-device persistence. No real payment or email provider was connected or tested.
