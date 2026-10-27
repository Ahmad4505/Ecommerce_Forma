# Forma — Multi-Vendor Marketplace

A premium, responsive React shopping prototype with a curated public storefront and separate customer, vendor, and administrator workspaces. Forty products, eight categories, five independent vendors, reviews, orders, promotions, and banners are included.

## Installation and commands

Node **22.12+** and npm 10+ are recommended. The workspace was built and verified on Node 20.15; Drei's unused camera-controls dependency reports a Node 22 engine advisory on this older runtime.

```sh
npm install
npm run dev
npm run build
npm run preview
npm test
npm run test:e2e
```

- Development: **http://127.0.0.1:5175/**.
- Production preview: **http://127.0.0.1:4175/**.
- Production output: `dist-forma/`.
- Vite prints another available port if its configured port is occupied.
- Browser tests expect the development URL above. Set `PLAYWRIGHT_BASE_URL` to test another server. Set `CHROME_PATH` to override the installed Windows Chrome executable in `playwright.forma.config.js`.

`.npmrc` keeps npm's cache in this workspace. `scripts/forma-run.mjs` runs Vite using the standard React and Tailwind plugins, with a narrowly scoped realpath fallback and dependency resolver for restricted Windows environments. Its isolated `node_modules/.vite-forma` cache prevents concurrent Vite servers from overwriting optimized dependencies.

## Demo accounts

| Role | Email | Password | Workspace |
| --- | --- | --- | --- |
| Customer | customer@forma.demo | Demo123! | `/account` |
| Vendor | vendor@forma.demo | Demo123! | `/vendor` |
| Admin | admin@forma.demo | Demo123! | `/admin` |

The sign-in page also has one-click access buttons. Registration creates customers; administrators create vendor accounts. All newly created accounts also use the universal demo password **Demo123!**. Registration validates the entered password but discards it. Passwords, secrets, and production tokens are never stored.

**This is browser-local demonstration authentication. localStorage sessions and client-side role checks are not secure production authentication or authorization. Use fictitious personal information.**

## Technologies

React 19, Vite 6, JavaScript, Tailwind CSS 4 with `@tailwindcss/vite`, React Router 7, GSAP and ScrollTrigger, Three.js, React Three Fiber 9, Drei 10, Lucide React, Zustand, React Hook Form, Zod, Axios, and React Hot Toast. Analytics use lightweight accessible HTML/CSS rather than an extra chart dependency. Playwright and Node's test runner provide verification.

## Active project structure

```text
index.html
src/
  marketplace-main.jsx          # Selected entry, lazy routes, titles, role guards
  components/
    Layout.jsx                  # Storefront, menu, search, bag, newsletter, footer
    DashboardLayout.jsx         # Role-specific sidebar, header and account menus
    ProductCard.jsx             # Cards, wishlist, quick view and add-to-bag
    Analytics.jsx               # Animated statistics and data-driven sales charts
    ui.jsx                      # Modal, error boundary, image fallback and reveals
    three/Scene.jsx             # Procedural lounge chair and animated lighting
  pages/
    Home.jsx                    # Full editorial homepage
    Shop.jsx                    # Collection, categories, vendor stores and search
    Product.jsx                 # Gallery, variants, purchases and reviews
    Access.jsx                  # Sign-in, registration, demo recovery interfaces
    Commerce.jsx                # Cart, discount codes and validated demo checkout
    Account.jsx                 # Profiles, addresses, wishlist, orders, preferences
    Management.jsx              # Vendor and administrator management screens
    Info.jsx                    # About, contact, FAQ, policies and 404
  hooks/useOverlayMotion.js     # GSAP navigation and drawer lifecycle
  data/marketplace.js           # Related seed records
  services/marketplaceApi.js    # Mock operations, persistence, authorization, Axios
  store/marketplaceStore.js     # Persistent demo session, cart and wishlist
  styles/index.css             # Responsive design system and Tailwind entry
public/images/                  # Locally cached, sourced product photography
scripts/forma-run.mjs
tests/services.test.js
tests/browser/
playwright.forma.config.js
```

The Vite launcher selects `src/marketplace-main.jsx`, including when `index.html` references the conventional `src/main.jsx`. These `marketplace` modules and the pages above are the selected application. Other source variants are retained in the shared workspace and are not part of this application's bundle.

## Available pages

Public routes: `/`, `/shop`, `/categories`, `/category/:category`, `/product/:slug`, `/search?q=`, `/vendors`, `/vendor/:vendorId`, `/offers`, `/wishlist`, `/about`, `/contact`, `/faq`, `/privacy`, `/terms`, and a 404 fallback.

Authentication: `/login`, `/register`, `/forgot-password`, `/reset-password`.

Customer: `/account`, `/account/profile`, `/account/orders`, `/account/orders/:id`, `/account/wishlist`, `/account/addresses`, `/account/settings`, `/cart`, and customer-only `/checkout`. `/customer` redirects to `/account`. Checkout confirmation appears on the new order's detail page.

Vendor: `/vendor`, `/vendor/products`, `/vendor/products/new`, `/vendor/products/:id/edit`, `/vendor/inventory`, `/vendor/orders`, `/vendor/orders/:id`, `/vendor/analytics`, `/vendor/store`, `/vendor/reviews`.

Admin: `/admin`, `/admin/customers`, `/admin/vendors`, `/admin/vendors/new`, `/admin/vendors/:id/edit`, `/admin/products`, `/admin/products/new`, `/admin/products/:id/edit`, `/admin/categories`, `/admin/orders`, `/admin/orders/:id`, `/admin/reports`, `/admin/promotions`, `/admin/banners`, `/admin/product-reports`, `/admin/settings`.

## Implemented features

- Complete editorial homepage: announcement, sticky navigation, animated hero, interactive 3D chair, categories, featured products, bestsellers, arrivals, promotional features, independent brands, offers, testimonials, newsletter and footer.
- GSAP text reveals, ScrollTrigger entrances and parallax, animated navigation and cart drawer, gallery transitions, dashboard entrances and count-up statistics. Hover zoom, selected variants and wishlist feedback use lightweight CSS. Effects respect reduced motion and clean up on unmount.
- Procedural Three.js lounge chair in the hero and promotional studio; pointer-follow rotation, gentle motion, animated lighting, realistic materials, contact shadows, lazy scene loading, mobile pixel-ratio cap and WebGL fallback. No external model files.
- Text/category/price/rating filtering, sorting, pagination, quick view, product galleries, finish variants, wishlist and stock-aware bag actions.
- Persistent cart, quantity updates, removal, combined stock validation across variants, active discount codes, shipping calculation, guest checkout redirect and retained bag after sign-in.
- Validated shipping, saved address selection, simulated payment methods, service-side price recomputation, stock reduction, confirmation, order history, tracking, eligible cancellation and stock restoration.
- Customer profile editing, address CRUD, notification preferences and reviews restricted to delivered purchases.
- Vendor-scoped product CRUD, image upload, inventory, store details, product categories, reviews, order fulfillment and sales analytics. Vendor fulfillment is recorded per store; overall status advances when every store reaches the appropriate stage.
- Admin customer editing, vendor creation/editing/activation/suspension, global products, categories, orders, sales reports, promotion CRUD, homepage banners, product reports and platform shipping/newsletter settings. Suspending a store hides its products and blocks its demo sign-in.
- Responsive grids, navigation and sidebars; searchable tables; profile and notification menus; reusable confirmation dialogs; loading, validation, error and empty states; semantic controls; focus indicators; image fallbacks; dynamic titles and a global error boundary.

## Mock API and persistence

`src/services/marketplaceApi.js` is the mock service boundary. `readDB()` initializes the related records from `src/data/marketplace.js`; mutations commit to `forma-marketplace-db-v2` in localStorage. Zustand stores the demo session, bag and wishlist under `forma-marketplace-session-v2`. Preferences and sample newsletter/contact submissions use additional `forma-` keys. Clear those keys in browser site storage to reset the demo.

The browser's shared demo bag is retained across sign-ins. The default code **WELCOME10** gives 10% off while active. Shipping is **$8**, or free for a pre-discount subtotal of **$150+**. Administrators can edit these values. Orders snapshot product names, prices and vendor IDs so they remain readable after product deletion.

The Axios `client` is prepared using `VITE_API_BASE_URL` from `.env.example`. The prototype does not call a backend. Contact, newsletter and recovery forms send no messages; payments create no charge and orders trigger no physical shipment.

## Future Django REST Framework integration

1. Copy `.env.example` to `.env` and configure `VITE_API_BASE_URL` for your DRF deployment. Replace service operations with asynchronous Axios requests and add mutation loading/error states and data invalidation.
2. Model users, vendor memberships, products, categories, images, addresses, orders, order lines, store fulfillment, reviews, promotions and banners. Preserve stable IDs and map serializer responses to the frontend's normalized shapes.
3. Replace the universal demo password and browser session with secure server authentication. For Django cookie sessions, use HttpOnly cookies, CSRF protection, suitable CORS and credential settings. Never trust a local role field.
4. Enforce object-level permissions and scoped querysets for customers, vendors and administrators. Check store suspension on the server. Keep route guards for interface behavior only.
5. Compute prices, discounts, inventory reservations and fulfillment transitions transactionally on the server. Never trust browser-submitted totals, stock, ownership or prices.
6. Replace base64 demo uploads with validated multipart uploads to managed storage. Add backend pagination/filtering, rate limits, audit logs, real email recovery and request cancellation.
7. Integrate real payments as a separate backend phase with server validation and verified webhooks. Keep the demo labels until the real flow is implemented and tested.
8. Deploy `dist-forma/` with an `index.html` fallback for React Router routes. Configure appropriate caching, CSP, monitoring and an accessibility/security review before production.

## Known limitations

This is a functional frontend prototype, not a production commerce service. Browser records are editable, local to one browser, subject to storage quotas and not backed up. No real backend, payments, emails, delivery, password recovery, tax engine or cross-device synchronization exists. Uploaded images are limited to JPEG/PNG/WebP under 750 KB and stored in browser data.

Unsplash photographs are cached in `public/images/` for dependable loading. They illustrate the design and may differ from described products. User-supplied invalid images use an SVG fallback. Google Fonts and user-supplied remote URLs need network access. The procedural 3D module is lazy loaded but substantial; Vite reports a chunk-size advisory. Analytics show saved local demo activity. Preference switches persist locally without sending notifications.

## Verification

See [VERIFICATION.md](../VERIFICATION.md) for completed checks. The selected application's service tests and browser tests cover role scoping, inventory, checkout, persistence, customer/vendor/admin workflows, public routes, every dashboard route, overlays, keyboard closing, reduced motion and mobile overflow. Additional visual checks cover desktop, tablet, mobile, image loading, WebGL and GSAP visibility.
