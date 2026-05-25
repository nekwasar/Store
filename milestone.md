# fastapi_shop — Implementation Milestones

**128 findings. Strict dependency order. Each milestone unblocks the next.**

---

## MILESTONE 0 — Critical Security ✅ DONE

These are exploitable at runtime with no prerequisites. Must fix before anything else.

| Order | ID | Area | Action | File:Line |
|-------|----|------|--------|-----------|
| 0.1 | B1 | RCE | Replace `eval(delete)` with `json.loads()` or `[ObjectId(x) for x in delete.split(',')]` | `db.py:32` |
| 0.2 | B2 | Auth | Hash passwords with `passlib[bcrypt]` — never store/compare plaintext | `apps/auth/routers.py:42`, `main.py:28-29` |
| 0.3 | B3 | Auth | Add `exp` claim to JWT (e.g., `datetime.utcnow() + timedelta(hours=1)`) | `apps/auth/routers.py:24` |
| 0.4 | B4 | Startup | Add unique index on `user.username`, replace `insert_one` with `update_one(upsert=True)`, hash the password before insert | `main.py:26-32`, `apps/auth/models.py` |

**Blocker for**: M3 (auth hardening), M5 (admin CRUD security)

---

## MILESTONE 1 — App Must Stay Up ✅ DONE

App cannot be tested or developed if it crashes on startup or can't connect to dependencies.

| Order | ID | Area | Action |
|-------|----|------|--------|
| 1.1 | G10 | Startup | Add max retries + timeout to `while True` DB-connect loop (currently loops forever if DB down) | `main.py:26-32` |
| 1.2 | B34 | Startup | Add defaults for `JWT_SECRET_KEY` and `ALGORITHM` env vars — app crashes if either is unset | `middleware.py:18`, `apps/auth/routers.py:24` |
| 1.3 | B17 | Startup | Guard `STRIPE_SECRET_KEY` env var access — `"_test_" in None` → TypeError | `utils.py:44` |
| 1.4 | B30 | Startup | Guard `int(os.environ.get('SMTP_PORT'))` — crashes if SMTP_PORT unset | `celery_tasks.py:28,65` |
| 1.5 | B22 | DB | `await` all `create_index()` calls (category, product, coupon, order) — zero indexes exist now | `apps/category/models.py:11`, `apps/product/models.py:15-17`, `apps/coupons/models.py:13`, `apps/order/models.py:17` |
| 1.6 | H26 | DB | Add Redis connection timeout + retry config to `recommender.py` | `recommender.py:7-9` |
| 1.7 | G27 | Ops | Add `healthcheck` directives to all docker-compose services | `docker-compose.yml` |
| 1.8 | H11 | Ops | Add `restart: always` to redis, nginx, rabbitmq (only mongo has it) | `docker-compose.yml` |
| 1.9 | G16 | DB | Add MongoDB connection pool tuning and retry on transient failures | `db.py` |
| 1.10 | G17 | Ops | Add FastAPI shutdown event to drain Celery tasks and close DB/Redis connections | `main.py` |

**Blocker for**: Everything else (can't test if app doesn't stay running)

---

## MILESTONE 2 — Kill All 500 Crashes ✅ DONE

Every GET/POST route must return a proper HTTP code. No user-facing 500s.

| Order | ID | Area | Action | File:Line |
|-------|----|------|--------|-----------|
| 2.1 | B5, B6 | Router | Wrap `ObjectId(cart_id)` and `ObjectId(coupon_id)` in try/except → return 400 instead of 500 | `dependencies.py:16,23` |
| 2.2 | B7 | Router | Guard `get_user_from_token(None)` in middleware — return 307 redirect instead of TypeError 500 | `middleware.py:30` |
| 2.3 | B8 | Router | Use `request.headers.get('referer', '/product')` instead of direct key access → no KeyError | `apps/cart/routers.py:21` |
| 2.4 | B9 | Router | Guard empty POST body in category create — return 422 if `category is None` | `apps/category/routers.py:9-11` |
| 2.5 | B13 | Router | Wrap `ObjectId(_id)` in product detail → return 404 instead of 500 for invalid hex | `apps/product/routers.py:43` |
| 2.6 | B18 | Router | Handle `valid_from=None` in coupon create/edit — return 422 instead of TypeError 500 | `apps/coupons/models.py:63,73` |
| 2.7 | B19 | Router | Guard `OrderSchema(**None)` in payment routes → redirect to cart if no order cookie | `apps/payment/routers.py:28,79` |
| 2.8 | B20 | Router | Guard `get_coupon_by_id("")` in admin order routes → skip coupon if empty string | `apps/admin/routers.py:243`, `apps/order/models.py:230` |
| 2.9 | B14 | Router | Replace bare `except Exception as e: Message(e.detail)` with specific exception handlers | `apps/admin/routers.py:158,256` |
| 2.10 | B15 | Router | Guard `ObjectId(self.cart['_id'])` with `.get('_id')` → return early if no _id | `apps/cart/cart.py:99` |
| 2.11 | B29 | Router | Fix validation exception handler to handle ALL validation errors, not just email → return proper 422 | `main.py:62-68` |
| 2.12 | B16 | Celery | `await` the `cart_collection.delete_many()` in the Celery task → expired carts actually get cleaned | `celery_tasks.py:42` |

**Blocker for**: M5 (business logic), M6 (adding features to unstable routes is wasted work)

---

## MILESTONE 3 — Auth & Security Hardening ✅ DONE

Auth works but is trivially broken. Must fix before exposing admin to any real use.

| Order | ID | Area | Action | File:Line |
|-------|----|------|--------|-----------|
| **3.0** | **NEW** | **Auth** | **Enterprise admin onboarding: one-time setup token via CLI script → `/setup` route → admin signup page (username+password) → auto-redirect to login. Replaces hardcoded `main.py` superuser bootstrap. Full plan: `docs/admin-onboarding-plan.md`** | `scripts/create-setup-token` (new), `apps/auth/routers.py`, `templates/user/auth/setup.html` (new), `main.py` (remove old bootstrap) |
| 3.1 | B34, H7 | Auth | Validate JWT `ALGORITHM` against allowlist `["HS256", "RS256"]` — reject `"none"` | `middleware.py:18`, `apps/auth/routers.py:24` |
| 3.2 | B3, H2 | Auth | JWT `exp` claim already added in M0.3 — verify it here. Add refresh token mechanism. | `apps/auth/routers.py:24` |
| 3.3 | B26 | Auth | Invalid login should return HTTP 401 + JSON error, not 200 + HTML login page | `apps/auth/routers.py:43-44` |
| 3.4 | G11 | Auth | Add CSRF tokens to all admin POST forms (category, product, order, coupon create/edit/delete) | `apps/admin/routers.py`, all POST endpoints |
| 3.5 | G5 | Auth | Add rate limiting middleware — throttle login (5/min), API (100/min), cart (30/min) | `main.py` (new middleware) |
| 3.6 | G23 | Auth | Add JWT blacklist on logout (server-side invalidation), token expiry enforcement | `apps/auth/routers.py:58`, `middleware.py` |
| 3.7 | G2 | Auth | Already fixed in M0.2 — verify bcrypt is everywhere | `apps/auth/routers.py` |
| 3.8 | H3 | Config | Narrow CORS: replace `allow_methods=["*"]` and `allow_headers=["*"]` with explicit lists; origins from env | `main.py:37-48` |
| 3.9 | G18 | Config | Add security headers: CSP, X-Frame-Options, X-Content-Type-Options, Strict-Transport-Security | `main.py` (new middleware) |
| 3.10 | H17 | Config | Add security headers in nginx as defense-in-depth layer | `conf/nginx.conf` |

**Blocker for**: M5 (admin CRUD operations without auth hardening is dangerous)

---

## MILESTONE 4 — Data Model Integrity ✅ DONE

Fix schemas, types, and data representations so business logic operates on correct data.

| Order | ID | Area | Action | File:Line |
|-------|----|------|--------|-----------|
| 4.1 | B11, I4 | Schema | Stop storing `created`/`updated` as `str` — store as native `datetime`. Fix both orders and products. | `apps/order/models.py:181-182`, `apps/product/models.py:108-109` |
| 4.2 | B12 | Schema | `ProductSchema.created`/`updated` must match what's stored (both native datetime) | `apps/product/models.py:28-29` |
| 4.3 | I8, B33 | Schema | Unify product price to `Decimal` throughout: store as Decimal, compare as Decimal, send to Stripe as Decimal → `int(round(price * 100))` | `apps/cart/cart.py:58,71,87`, `apps/product/models.py` |
| 4.4 | H34 | Schema | Fix Stripe `unit_amount` precision: `int(round(item.price * 100))` not `int(item.price * 100)` | `apps/payment/routers.py:52` |
| 4.5 | I7 | Schema | Change `quantities: list[str]` → `list[int]` in `OrderCreateSchema` — remove all manual `int()` casts | `apps/order/models.py:91` |
| 4.6 | I13, I14 | Schema | Make `get_product_by_id`, `get_product_by_slug`, `get_valid_coupon_*` return helper-processed dicts (consistent string ObjectId) — same as all other getters | `apps/product/models.py:163-172`, `apps/coupons/models.py:87-104` |
| 4.7 | I16 | Schema | Add missing fields (`stripe_id`, `stripe_url`, `discount`) to `order_helper` output | `apps/order/models.py:135-149` |
| 4.8 | B32 | Schema | Remove `active=True` hardcode in `create_coupon` — respect the form value | `apps/coupons/models.py:66` |
| 4.9 | H41 | Schema | Change `cart.copy()` (shallow) to `copy.deepcopy(cart)` in `_populate_cart_with_products` → stops mutation of original DB document | `apps/cart/cart.py:46-62` |
| 4.10 | H35 | Schema | Validate `items` non-empty before creating order — reject empty-cart orders with 422 | `apps/order/routers.py:36-38` |
| 4.11 | H29 | Schema | Fix product index on `("id", ASCENDING)` → should be `("_id", ASCENDING)` or remove (MongoDB auto-indexes `_id`) | `apps/product/models.py:15` |

**Blocker for**: M5 (business logic operates on inconsistent data), M6 (features need correct data types)

---

## MILESTONE 5 — Business Logic Fixes ✅ DONE

Core store operations. Cart, order, payment, coupon flows must be correct.

| Order | ID | Area | Action | File:Line |
|-------|----|------|--------|-----------|
| 5.1 | H38 | Order | Re-validate coupon at order-creation time (not just cart-load time) — use `get_valid_coupon_by_id` | `apps/order/models.py:190-193` |
| 5.2 | H37 | Payment | Add Stripe webhook idempotency — deduplicate by `event.id` to prevent double emails and double Redis scores | `apps/payment/routers.py:108-126` |
| 5.3 | H31 | Payment | Check if Stripe coupon already exists before creating a new one → prevents duplicate-name errors on retry | `apps/payment/routers.py:61-69` |
| 5.4 | B21 | Routing | Fix category `/{slug}` shadowing `/{_id}` — merge into one endpoint that tries ObjectId first, then slug | `apps/category/routers.py:21,29` |
| 5.5 | B35 | Cart | Replace `request.cookies.pop('coupon_id', None)` with `response.delete_cookie('coupon_id')` where needed | `dependencies.py:23` |
| 5.6 | G20 | Product | Add `stock_quantity` field — replace `available` boolean with inventory tracking, auto-set `available=False` at zero | `apps/product/models.py` |
| 5.7 | G21 | Order | Add order status workflow: `pending → confirmed → paid → shipped → delivered → cancelled` | `apps/order/models.py` |
| 5.8 | B23 | Product | Guard `os.remove` against empty image path → skip if `not image_path` | `db.py:17-18` |
| 5.9 | B24, B25 | Email | Fix MIME typo `octate-stream` → `octet-stream` and header `Content-Decomposition` → `Content-Disposition` | `celery_tasks.py:58,62` |
| 5.10 | B36 | Utils | Replace Pydantic v1 `__get_validators__` in `PyObjectId` with Pydantic v2 `__get_pydantic_core_schema__` or remove if unused | `utils.py:13` |
| 5.11 | B27, B28 | Admin | Fix wrong entity name in messages: "Product"→"Category" in category edit, "Category not found"→"Product not found" in product detail | `apps/admin/routers.py:90`, `apps/product/routers.py:61` |

**Blocker for**: M6 (performance layer depends on correct business logic)

---

## MILESTONE 6 — Performance ## MILESTONE 6 — Performance & Observability Observability ✅ DONE

App logic works. Now make it fast, traceable, and monitorable.

| Order | ID | Area | Action | File:Line |
|-------|----|------|--------|-----------|
| 6.1 | H25, B35→async | Redis | Replace sync `redis.Redis` with `redis.asyncio.Redis` — unblocks event loop on every recommendation call | `recommender.py:3,7-9` |
| 6.2 | I/O | I/O | Replace sync `open()`/`os.remove()` in `save_image` and `delete_product_image` with `aiofiles` | `utils.py:33`, `db.py:20` |
| 6.3 | G7 | API | Add `?page=1&per_page=20` pagination to public `/product/` and `/product/{category_slug}` endpoints | `apps/product/routers.py:22,31` |
| 6.4 | G15 | Cache | Add Redis caching for product listings and category data (TTL 5min, invalidate on admin edit) | New caching layer |
| 6.5 | G6 | Logging | Replace all `print(e)` with structured logging (`structlog` or `logging` with JSON formatter) — log all requests, errors, admin actions | `main.py`, `apps/payment/routers.py:98,103`, all routers |
| 6.6 | G14 | Monitor | Add Prometheus metrics endpoint (package already installed) — request count, latency, error rate, DB query time | `main.py` (new `/metrics` route) |
| 6.7 | G19 | Audit | Log all admin CRUD operations: who, what, when, old value, new value | `apps/admin/routers.py` |
| 6.8 | H43 | Health | Expand `/health` to check MongoDB, Redis, RabbitMQ connectivity — return 503 if any are down | `main.py:76-78` |

**Blocker for**: M7 (can't tune production if you can't observe)

---

## MILESTONE 7 — Production DevOps ✅ DONE

Docker, nginx, config — everything needed to deploy safely.

| Order | ID | Area | Action | File:Line |
|-------|----|------|--------|-----------|
| 7.1 | H9 | Docker | Remove `--reload` from production CMD | `Dockerfile:17` |
| 7.2 | H10 | Docker | Build image once, reference in celery/celery-beat via `image:` instead of rebuilding 3x | `docker-compose.yml` |
| 7.3 | H12 | Docker | Remove RabbitMQ management port (15672) exposure — internal-only or behind auth | `docker-compose.yml` |
| 7.4 | H13 | Config | Fix `.env.project.template` — use actual example values (`sk_test_...`) not descriptions | `.env.project.template` |
| 7.5 | H14 | Nginx | Add MIME types for JS, PNG, JPG, SVG, TTF, WOFF2 in `/static/` location | `conf/nginx.conf:21` |
| 7.6 | H15 | Nginx | Remove redundant `if` + duplicate `proxy_pass` block in `/` location | `conf/nginx.conf:13-16` |
| 7.7 | H16 | Nginx | Add `client_max_body_size 10M` for product image uploads | `conf/nginx.conf` |
| 7.8 | H18 | Nginx | Add `proxy_set_header X-Real-IP $remote_addr` and `X-Forwarded-Proto $scheme` | `conf/nginx.conf` |
| 7.9 | H19 | Config | Add default `CELERY_BROKER_URL` fallback if env var unset | `celery_tasks.py:15` |
| 7.10 | H20 | Config | Add SMTP connection timeout (e.g., 10s) | `celery_tasks.py:28,65` |
| 7.11 | H21 | Config | Make email `From` address separately configurable (`EMAIL_FROM`) — decouple from `GMAIL_USER` | `celery_tasks.py:24,50` |
| 7.12 | H22 | Config | Lazy-load Stripe API key (supports key rotation without restart) | `apps/payment/routers.py:21` |
| 7.13 | H23 | Config | Make Stripe API version configurable via `STRIPE_API_VERSION` env var | `apps/payment/routers.py:22` |
| 7.14 | H42, H30 | Config | Make nginx proxy pass URL, cart expiration timeout, and other hardcoded values configurable via env | Multiple files |
| 7.15 | G32 | Ops | Add database backup script + cron/scheduled task | New tooling |
| 7.16 | G25 | Config | Add `CELERY_RESULT_BACKEND` for task result tracking | `celery_tasks.py` |

**Blocker for**: Production deployment

---

## MILESTONE 8 — Features ## MILESTONE 8 — Features & Completeness Completeness ✅ DONE

Now add the missing features needed for a real store.

| Order | ID | Area | Action |
|-------|----|------|--------|
| 8.1 | G8 | Product | Add product search endpoint with MongoDB text index (`$text` query) |
| 8.2 | G22 | Auth | Add public user registration endpoint with email verification |
| 8.3 | G24 | Product | Add product variant support (size, color) — variant-level pricing and inventory |
| 8.4 | G25 | Coupon | Add coupon types: fixed-amount, minimum-purchase, category-specific, first-order-only |
| 8.5 | G9 | Media | Add image resize/thumbnail generation on upload, serve thumbnails in product lists |
| 8.6 | H27, H28 | Media | Fix image validation: accept `.jpeg/.JPG`, validate by MIME type not extension, preserve original format |
| 8.7 | G26 | Payment | Make currency configurable — extract `'cad'` to env var `STRIPE_CURRENCY` |
| 8.8 | G28 | Cart | Add abandoned cart email reminder (Celery beat task for carts expiring soon) |
| 8.9 | G30 | Export | Add CSV export for orders (admin) and products |
| 8.10 | G31 | Docs | Add OpenAPI descriptions, examples, and response models to all endpoints |
| 8.11 | G12 | API | Add `/api/v1/` prefix to all API routes (keep shop pages at current path) |
| 8.12 | G13 | Tests | Add pytest test suite — at minimum: auth flow, cart flow, order creation, admin CRUD |

**Blocker for**: Going live with real customers

---

## MILESTONE 9 — Code Quality ## MILESTONE 9 — Code Quality & Polish Polish ✅ DONE

Clean up the mess. No functional changes, just readability and maintainability.

| Order | ID | Area | Action | File:Line |
|-------|----|------|--------|-----------|
| 9.1 | I1 | Cleanup | Merge duplicate `User` model — keep one in `apps/auth/models.py`, import in admin router | `apps/auth/models.py`, `apps/admin/models.py` |
| 9.2 | I2 | Cleanup | Rename duplicate `login` GET/POST functions to `login_page` / `login_action` | `apps/auth/routers.py:33,38` |
| 9.3 | I3 | Cleanup | Remove `response_model=dict` from all TemplateResponse endpoints (no-op but confusing) | `apps/admin/routers.py` (all route decorators) |
| 9.4 | I5 | Cleanup | Unify email construction — use `EmailMessage` or `MIMEMultipart` consistently | `celery_tasks.py:21,46` |
| 9.5 | I6 | Cleanup | Remove unused `oauth2_scheme` from auth router (only used in middleware) | `apps/auth/routers.py:20` |
| 9.6 | I9 | Cleanup | Create a `constants.py` with collection name constants instead of magic strings everywhere | New file |
| 9.7 | I10 | Cleanup | Replace `if delete[0] == 'on'` hack with proper form serialization | `apps/admin/routers.py:422` |
| 9.8 | I11 | Cleanup | Remove redundant second `load_dotenv()` call in main.py | `main.py:23` |
| 9.9 | I12 | Cleanup | Remove or fix broken `OrderItemSchema.get_total_price()` (copy-paste from CartManager) | `apps/order/models.py:30-32` |
| 9.10 | I15 | Cleanup | Merge `CategoryCreateSchema` into `CategorySchema` (identical fields) — add `as_form` to CategorySchema | `apps/category/models.py:15,28` |
| 9.11 | H32 | Cleanup | Remove debug import `from pprint import pprint` | `apps/admin/routers.py:1` |
| 9.12 | B37 | Cleanup | Move `AdminMiddleware` before router inclusion (or use per-route Depends) so CORS works on admin | `main.py:50-59` |
| 9.13 | B31 | Cleanup | Replace `request.url._url` (private attribute) with `str(request.url)` | `apps/payment/routers.py:38-39` |
| 9.14 | B39→pdf | Cleanup | Use correct NotoSans TTF files for Bold/Italic/BoldItalic font variants in PDF | `pdf.py:56-59` |
| 9.15 | H33 | Cleanup | Move static mount to `/static-assets/` or keep `/static` but document it | `main.py:35` |

---

---

## MILESTONE 10 — Build Tooling Foundation (Vite + Sass + Docker)

Install and configure Vite as the frontend build system, add Dart Sass for Bootstrap theme customization, and integrate the build into Docker so the production image serves compiled assets.

### Implementation

- Install Vite with the `@vitejs/plugin-legacy` plugin (for wide browser support). Do NOT use webpack, parcel, or any other bundler — Vite is the industry standard for fast dev builds with native ES module HMR.
- Create a `static_src/` directory at the project root. Move `static/css/style.css` into `static_src/scss/style.scss`. Vite will watch `static_src/` and output compiled production assets to `static/dist/`.
- Create a `vite.config.js` at the project root. Configure:
  - Entry point: `static_src/js/main.js` (new file — will be the Alpine.js entry point in M12)
  - CSS entry: `static_src/scss/style.scss` (imports Bootstrap and custom overrides, will be wired in M11)
  - Output dir: `static/dist/` with hashed filenames in production
  - Dev server: disabled (we use Jinja2 server-rendered HTML, no SPA dev server needed)
- Install Dart Sass (`sass` npm package) as a dev dependency. Bootstrap customization in M11 requires Sass — do NOT skip this step.
- Create a `package.json` with `scripts: { "dev": "vite build --watch", "build": "vite build" }`. The `dev` script runs in the foreground (used in development), `build` runs once (used in Docker).
- Update `.dockerignore` to exclude `node_modules`, `static_src/` from the final image (only `static/dist/` is needed).
- Update `Dockerfile`:
  - Add a `builder` stage: `FROM node:20-alpine`, copy `package.json` + `package-lock.json`, run `npm ci`, copy `static_src/`, run `npm run build`.
  - Keep the final stage as `python:3.11-alpine`. Copy `static/dist/` from the builder stage into the final image at `/code/static/dist/`.
  - Do NOT install Node.js in the final Python image — that defeats the purpose of multi-stage.
- Update `main.py` static mount: mount `static/dist/` at `/static/` instead of the raw `static/` directory. This means all compiled assets are served from hashed filenames.
- Update `base.html`: replace hardcoded CDN Bootstrap CSS link with `{{ url_for('static', path='dist/css/style.css') }}` (the Vite-compiled bundle that includes Bootstrap + custom theme).
- Keep CDN Bootstrap JS for now (will be replaced in M12 when Alpine.js arrives). The JavaScript bundle from Vite is not yet needed since there is no JS entry point.

### Best Practices

- Use `npm ci` (not `npm install`) in Docker — `npm ci` is deterministic, faster, and fails if `package-lock.json` is out of sync with `package.json`.
- Pin exact npm package versions in `package.json` (no `^` or `~` ranges). Frontend builds must be reproducible across environments.
- Keep the Vite config minimal. Do NOT add plugins like `vite-plugin-react`, `@vitejs/plugin-vue`, or any SPA-related tooling — this is a server-rendered Jinja2 app.
- The builder stage must use `--from=node:20-alpine AS builder` and copy artifacts with `--from=builder`. Do NOT merge build stages into the Python image.
- Hash filenames in production (Vite does this by default with `[hash]` in the filename pattern). Do NOT disable hashing — it's critical for cache busting.
- The `static_src/` directory must be part of the project repo. The `static/dist/` directory should be in `.gitignore` (build artifact).
- Configure `@` alias in `vite.config.js` pointing to `static_src/` for clean imports.

### Flaws to Avoid

- Do NOT run Vite dev server in production. The `dev` script with `--watch` is for local development only. The Docker CMD must use `npm run build`.
- Do NOT put `node_modules` in the final image. Multi-stage build must copy only `static/dist/`.
- Do NOT skip `@vitejs/plugin-legacy`. Without it, the app breaks on older browsers because Vite emits modern ES modules by default.
- Do NOT use `require()` or CommonJS in `vite.config.js` — use ESM (`export default`).
- Do NOT use `postcss-preset-env` or autoprefixer as a separate step — Vite handles CSS processing natively with `css.postcss` config if needed, but for this project it's unnecessary since Bootstrap already includes vendor prefixes.
- Do NOT add TypeScript yet — that's a future concern. Keep all frontend JS as vanilla ES modules or Alpine.js inline scripts.

### Verification / Expected Output

- `npm run build` produces `static/dist/assets/index-<hash>.js` and `static/dist/assets/style-<hash>.css`.
- The Docker multi-stage build completes without errors. The final image is smaller than before (only hashed assets, no node_modules).
- `curl http://localhost:8989/static/dist/assets/style-<hash>.css` returns compiled CSS (confirm the file is served correctly by nginx/FastAPI static mount).
- The page loads without 404s on any static asset.
- `base.html` correctly loads the Vite-compiled CSS. The page renders with Bootstrap styles (same as before, since we haven't changed the theme yet).
- Running `npm run dev` in the background and making a change to `static_src/scss/style.scss` triggers a rebuild (Vite watch mode works).

---

## MILESTONE 11 — Bootstrap Theme via Sass (Custom Palette + Local Build)

Replace the CDN Bootstrap CSS with a locally compiled version that uses a custom color palette, typography, border-radius, and spacing scale. The entire Bootstrap source is pulled in via npm and compiled through Dart Sass.

### Implementation

- Install Bootstrap as an npm dependency (`bootstrap@5.3.x`). Do NOT use the CDN version after this milestone — Bootstrap will be compiled locally.
- Create `static_src/scss/bootstrap-custom.scss`. This file imports Bootstrap's source Sass but overrides the default theme variables BEFORE the import.
- Override the following Bootstrap defaults in `_variables.scss` or directly before the import:
  - `$primary`: Replace Bootstrap blue with a modern indigo (`#4F46E5`) or teal (`#0D9488`) palette. Pick ONE and be consistent — do not mix.
  - `$secondary`: A warm gray (`#6B7280`) or slate (`#475569`).
  - `$success`, `$danger`, `$warning`, `$info`: Tune these to harmonize with the primary palette. Use a color harmonizer tool or Tailwind's palette as reference.
  - `$font-family-sans-serif`: Use a modern system font stack (`Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`). Import Inter from Google Fonts via CSS `@import` in the compiled SCSS.
  - `$border-radius`: Increase to `0.5rem` (8px) for a softer, modern look. Keep `$border-radius-lg` at `0.75rem` and `$border-radius-sm` at `0.25rem`.
  - `$enable-shadows`: Set to `true`. Bootstrap disables box-shadows by default; enabling them gives cards, dropdowns, and modals subtle depth.
  - `$box-shadow`: Customize to `0 1px 3px 0 rgb(0 0 0 / 0.1)` (Tailwind-inspired subtle shadow).
  - `$spacer`: Keep at `1rem` (16px) but adjust `$spacers` map if needed for consistent vertical rhythm.
  - `$navbar-height`: May need adjustment with new font sizes.
  - `$btn-border-radius`: Match `$border-radius` for consistency.
  - `$card-border-radius`: Set to `$border-radius-lg`.
  - `$card-box-shadow`: Add a custom shadow for card elevation.
  - `$table-border-radius`: Cards and tables should look cohesive.
- After the variable overrides, import Bootstrap's full SCSS: `@import "bootstrap/scss/bootstrap";`.
- In `static_src/scss/style.scss`, add `@import "bootstrap-custom";` at the top, followed by any custom component styles (card tweaks, navbar overrides, etc.).
- Remove the CDN Bootstrap CSS `<link>` from `base.html`. Replace it with `{{ url_for('static', path='dist/assets/style-<hash>.css') }}` (the Vite-compiled output that now includes the custom Bootstrap theme).
- Keep the Bootstrap JS CDN `<script>` tags for now (will be replaced with Alpine.js in M12). The CSS is decoupled from JS — you can swap CSS independently.
- Test every page to confirm the new palette renders correctly: product list, product detail, cart, checkout, all admin CRUD forms, login, register, setup.

### Best Practices

- Use a color palette generator (e.g., Coolors, Tailwind Palette) to pick harmonious primary/secondary/accent colors. Do NOT guess colors by eye — use a systematic approach.
- Override Bootstrap variables BEFORE the `@import "bootstrap"` statement. If you override after the import, Sass compilation will use the defaults instead of your values.
- Use semantic color naming in your overrides. Document the palette in comments so future developers understand the color system.
- Test color contrast ratios for accessibility — all text/background combinations must meet WCAG AA (contrast ratio >= 4.5:1 for normal text). Use a contrast checker tool.
- Keep the custom `style.scss` small. Most styling should come from Bootstrap's component classes. Only add custom CSS when Bootstrap's utilities cannot achieve the desired look.
- Use Bootstrap's utility classes in templates wherever possible (`text-primary`, `bg-primary-subtle`, `shadow-sm`, `rounded-3`, etc.) instead of writing custom CSS.
- Import Inter from Google Fonts using a CSS `@import` in the SCSS, NOT via a `<link>` tag in the HTML. Keeping font loading in the CSS bundle avoids an extra HTTP request.

### Flaws to Avoid

- Do NOT import Bootstrap's entire CSS via CDN AND compile it locally — that doubles the CSS payload and causes style conflicts. After M11, there is ONE CSS file.
- Do NOT use `!important` in custom styles. Bootstrap's source order and specificity are designed to be overridden cleanly via variables.
- Do NOT override Bootstrap's `$enable-*` variables to `false` without testing thoroughly. Disabling `$enable-negative-margins`, for example, will break utility classes used in templates.
- Do NOT change `$grid-breakpoints` unless you fully understand responsive design implications. The default breakpoints (576/768/992/1200/1400) are well-tested.
- Do NOT use CSS custom properties (CSS variables) to override Bootstrap theme colors at the `:root` level — Bootstrap's Sass variables are compiled at build time and CSS custom properties will not override them unless Bootstrap's CSS variable mode is explicitly enabled.
- Do NOT forget to remove the old `style.css` from the `static/` directory after M11 is verified. Leftover orphaned CSS files cause confusion.

### Verification / Expected Output

- All pages render with the new color palette. Primary buttons are indigo/teal, not Bootstrap blue. Cards have rounded corners and subtle shadows.
- The compiled CSS file is smaller than CDN Bootstrap + old `style.css` combined (because dead Bootstrap components can be excluded via `$enable-*` variables and selective imports).
- No Flash of Unstyled Content (FOUC) — the font (Inter) preloads correctly and the page renders immediately with the themed CSS.
- Inspect any page and confirm Bootstrap variables use your custom values (e.g., `--bs-primary: #4F46E5` if using CSS variables mode, or verify rendered color via computed styles).
- All hover, focus, active, disabled states use the new palette (buttons, links, form controls, nav items).
- Color contrast for primary text on primary backgrounds passes WCAG AA (use a browser devtools accessibility audit).
- The old `https://cdn.jsdelivr.net/npm/bootstrap@5.3.1/dist/css/bootstrap.min.css` no longer appears in any network request.

---

## MILESTONE 12 — Remove jQuery CDN + Rewrite Navbar/Cart/Alerts in Alpine.js

Remove the ancient jQuery 1.7.1 and jQuery UI 1.8.16 CDN scripts from every page. Rewrite all interactive behavior that currently depends on jQuery using Alpine.js — a lightweight reactive framework that pairs naturally with server-rendered Jinja2 templates.

### Implementation

- Install Alpine.js via npm (`alpinejs`). Do NOT use the CDN version — bundle it with Vite and load from the local compiled JS bundle.
- Create `static_src/js/main.js` as the Vite JS entry point:
  ```js
  import Alpine from 'alpinejs'
  window.Alpine = Alpine
  Alpine.start()
  ```
  This is the only JavaScript entry point for the entire app going forward.
- Update `base.html`:
  - Remove ALL CDN script tags: jQuery, jQuery UI, Popper.js, Bootstrap JS bundle, Bootstrap JS standalone.
  - Keep the Bootstrap CSS (now from local Vite build via M11) and Bootstrap Icons CDN (Bootstrap Icons has no JS dependency, safe to keep as CDN).
  - Add the Vite JS bundle script: `<script src="{{ url_for('static', path='dist/assets/main-<hash>.js') }}" defer></script>`.
  - Keep individual page-level `<script>` tags only if they use vanilla JS (no jQuery dependency). These will be migrated to Alpine in later milestones.
- Migrate the navbar cart badge to Alpine:
  - The current `{% with total_items=cart|length %} ... {% endwith %}` block is static server-rendered. This is fine — no JS needed for the initial render.
  - For dynamic cart updates (adding items without full page reload), use Alpine `x-data` with `x-text` to update the badge count via a fetch response. This is deferred — M12 only handles static replacement of jQuery patterns.
- Migrate `bootstrap_alert.js` to Alpine:
  - Remove the script tag for `bootstrap_alert.js`.
  - In any template that uses `appendAlert()`, replace with an Alpine component:
    ```html
    <div x-data="{ alerts: [] }">
      <template x-for="alert in alerts">
        <div class="alert alert-dismissible" x-bind:class="'alert-' + alert.type" x-text="alert.message">
          <button type="button" class="btn-close" @click="alerts = alerts.filter(a => a !== alert)"></button>
        </div>
      </template>
    </div>
    ```
    JavaScript that previously called `appendAlert(message, type)` now pushes to the Alpine `alerts` array.
- Migrate the mobile navbar toggle (hamburger menu):
  - Bootstrap 5's navbar toggler works via data attributes (`data-bs-toggle="collapse"`) — it does NOT depend on jQuery. This already works with vanilla Bootstrap JS.
  - However, Bootstrap JS CDN is removed in this milestone. The collapse functionality must be reimplemented in Alpine or you must include Bootstrap JS as an npm dependency (recommended).
  - Preferred approach: Install `@popperjs/core` and `bootstrap` as npm packages, import Bootstrap JS into `main.js`: `import 'bootstrap'`. This replaces the CDN Bootstrap JS with a locally bundled version that works with Alpine.js.
  - Test: navbar hamburger toggle on mobile, dropdown menus, modal dialogs, tooltips, popovers — all Bootstrap JS features must work.

### Best Practices

- Alpine.js components should be self-contained with `x-data`. Do NOT create global Alpine stores in M12 — keep component state local.
- Use `x-init` for one-time setup and `x-effect` for reactive side effects. Do NOT mix Alpine with imperative DOM manipulation.
- Keep Alpine template attributes in the HTML, NOT in JavaScript. The whole point of Alpine is co-location of behavior with markup.
- Import Bootstrap JS as an ES module in `main.js`, NOT as a separate script tag. This ensures proper load order and avoids duplicate Bootstrap instances.
- When removing jQuery-dependent code, verify that the replacement works at least as well. Regression-test all interactive elements.
- Use `defer` on the main JS script tag. Do NOT use `async` — Alpine needs DOM ready before initializing.

### Flaws to Avoid

- Do NOT keep jQuery CDN script "just in case" — if any jQuery-dependent code remains, it will crash after jQuery is removed. Audit ALL templates for `$`, `jQuery`, `.click()`, `.on()`, `.each()`, `.val()`, `.attr()`, `.addClass()`, `.removeClass()`.
- Do NOT add jQuery as an npm dependency as a "replacement" for the CDN. The goal is to ELIMINATE jQuery, not move it.
- Do NOT use Alpine `x-data` on the `<body>` tag — this creates a single monolithic component. Scope Alpine components to the smallest possible DOM subtree.
- Do NOT use Alpine `x-ref` for DOM access unless absolutely necessary. Alpine's reactive data model should eliminate most direct DOM manipulation.
- Do NOT include Bootstrap JS from CDN AND from npm — the two instances will conflict, causing duplicate event handlers and broken toggles.

### Verification / Expected Output

- Open the browser network tab and confirm: NO requests to `ajax.googleapis.com/ajax/libs/jquery/1.7.1/jquery.js`, `jquery-ui.js`, or `cdn.jsdelivr.net/npm/bootstrap@5.3.1/dist/js/bootstrap.bundle.min.js`.
- The navbar hamburger menu works on mobile viewport (collapses/expands).
- Alpine `x-data` components initialize correctly (visible in browser devtools as `x-data` attributes on DOM elements).
- The page has zero JavaScript console errors.
- Bootstrap dropdowns, modals, tooltips (e.g., admin table rows) still function.
- The `static/dist/assets/main-<hash>.js` file loads and parses correctly (check via browser Sources tab).
- Product list, product detail, cart, checkout, admin CRUD pages all render and their interactive elements work.

---

## MILESTONE 12.5 — Rewrite Checkbox Master/Child, Clipboard, All oninput Validators in Alpine

Continue the jQuery removal by migrating the admin-specific interactive behaviors that currently live in `static/js/`. This includes the master/child checkbox pattern, clipboard copy with snackbar, and all `oninput` form validators.

### Implementation

- Migrate `list_rows_delete.js` to Alpine:
  - On every admin list page (product, category, order, coupon), add an Alpine component wrapping the table:
    ```html
    <div x-data="checkboxList()">
      <!-- master checkbox -->
      <input type="checkbox" id="masterCheckbox" @change="toggleAll">
      <!-- child checkboxes -->
      <template x-for="item in items">
        <input type="checkbox" class="childCheckbox" x-model="item.checked"
               @change="updateMaster">
      </template>
      <!-- disabled state on submit button -->
      <button :disabled="!anyChecked" type="submit">Delete Selected</button>
    </div>
    ```
  - Define the `checkboxList()` Alpine component in a separate file `static_src/js/components/checkbox-list.js`.
  - Import and register it in `main.js`: `Alpine.data('checkboxList', checkboxList)`.
- Migrate clipboard copy (`id-copy-link`) to Alpine:
  - Replace the click event on `.id-copy-link` with an Alpine `@click.prevent` handler.
  - Use the modern `navigator.clipboard.writeText()` API (already used in the current code — this behavior stays the same).
  - Replace the snackbar DOM manipulation with an Alpine `x-show` + `x-transition`:
    ```html
    <div x-data="{ showSnackbar: false }">
      <a href="#" @click.prevent="copyId(item._id); showSnackbar = true;
             setTimeout(() => showSnackbar = false, 2000)">
        Copy ID
      </a>
      <div x-show="showSnackbar" x-transition.duration.500ms>
        ID Copied!
      </div>
    </div>
    ```
- Migrate `discount_validator.js`, `price_validator.js`, `quantity_validator.js` to Alpine:
  - Remove all `oninput="validateX(this)"` attributes from template inputs.
  - Add Alpine `x-on:input` handlers that call validation methods on the Alpine component.
  - Replace the `appendAlert()` calls (which wrote to a DOM element) with Alpine reactive state — a `validationErrors` array that renders inline error messages next to each field.
  - Example:
    ```html
    <input type="number" x-model="form.price"
           @input="if (form.price < 0) validationErrors.push('Price must be >= 0')">
    <template x-for="err in validationErrors">
      <div class="text-danger small" x-text="err"></div>
    </template>
    ```
- Migrate `next_page_select.js` to Alpine:
  - The `setNextPageValue()` function checks required fields before submitting. Replace with Alpine form validation:
    ```html
    <form x-data="formSubmit()" @submit.prevent="submitWithPage">
      <input type="hidden" name="next_page" x-model="nextPage">
      <!-- all required inputs have x-bind:required -->
      <button @click="nextPage='edit'">Save & Edit</button>
      <button @click="nextPage='create'">Save & Create New</button>
    </form>
    ```
- Delete all 6 old JS files from `static/js/`: `bootstrap_alert.js`, `list_rows_delete.js`, `discount_validator.js`, `price_validator.js`, `quantity_validator.js`, `next_page_select.js`. These are fully replaced by Alpine components.
- Remove the `<script src="{{ url_for('static', path='js/...') }}">` tags from all templates where they were included.

### Best Practices

- Each Alpine component should be in its own file under `static_src/js/components/`. This keeps the codebase organized for when the component count grows.
- Use Alpine's `$el`, `$refs`, `$watch` sparingly. Prefer reactive properties on the data object.
- Component functions should return a plain object (not a class or constructor). Alpine calls them as factories.
- Validation should be reactive (instant feedback as the user types) but debounced for API calls. Use Alpine `$watch` or `x-on:input.debounce` for debounced validation.
- Inline validation errors should appear next to the relevant field, NOT in a global alert at the top of the page. This is a UX best practice.

### Flaws to Avoid

- Do NOT use `eval()` or `new Function()` in Alpine components — this is a security anti-pattern and defeats Alpine's reactive system.
- Do NOT mix Alpine `x-model` with native `oninput` attributes on the same element — they will conflict.
- Do NOT keep the old JS files as "backup" — delete them from the repo. Dead code accumulates and confuses future maintainers.
- Do NOT use jQuery-style class manipulation (`classList.add/remove`) inside Alpine components — use `x-bind:class` instead.
- Do NOT use Alpine `x-init` for async operations without error handling. If an API call fails, the component should show an error state.
- Do NOT use `document.querySelector` inside Alpine components — use Alpine's reactivity to manage DOM state.

### Verification / Expected Output

- Master checkbox selects/deselects all child checkboxes. Unchecking any child unchecks the master. Re-checking all children re-checks the master.
- The "Delete Selected" submit button is disabled when zero checkboxes are checked and enabled when at least one is checked.
- Clicking "Copy ID" copies the document ID to clipboard and shows a "Copied!" toast that auto-hides after 2 seconds.
- Price input rejects non-numeric values and negative numbers with an inline red error message below the field.
- Discount input rejects values outside 0-100 with an inline error.
- Quantity input rejects values less than 1 with an inline error.
- The "Save & Continue Editing" / "Save & Create New" buttons validate required fields before submitting; if required fields are empty, an inline message appears and the form does NOT submit.
- Zero HTTP requests to old `static/js/*.js` files (all 6 deleted files return 404 — update or remove the script tags).
- The browser console has zero errors when navigating between admin list, create, and edit pages.

---

## MILESTONE 13 — Modern UI Component Libraries (Choices.js + Flatpickr + Notyf + Dropzone)

Replace the remaining jQuery UI widgets (autocomplete, datepicker) with modern, lightweight alternatives. Add a proper toast notification system and a modern file upload experience.

### Implementation

- Install Choices.js via npm (`choices.js`). Choices.js replaces jQuery UI Autocomplete for all `<select>` elements in admin forms (category selector in product create/edit, coupon type selector, etc.).
  - In `static_src/js/main.js`, import Choices and make it available: `import Choices from 'choices.js'`.
  - Create a `static_src/js/components/choices.js` Alpine component:
    ```js
    export default () => ({
      init() {
        new Choices(this.$el, {
          searchEnabled: true,
          removeItemButton: true,
          shouldSort: false,
        })
      }
    })
    ```
  - Apply `x-data="choices"` to any `<select>` element that needs autocomplete/search behavior. This replaces `$.autocomplete()` from jQuery UI.
  - Style Choices.js to match the Bootstrap theme (use SCSS overrides in `style.scss` — Choices.js uses BEM classes that can be targeted).
- Install Flatpickr via npm (`flatpickr`). Flatpickr replaces jQuery UI Datepicker for date inputs (coupon valid_from/valid_until, order date filters).
  - In `static_src/js/main.js`, import Flatpickr: `import flatpickr from 'flatpickr'`.
  - Create a `static_src/js/components/datepicker.js` Alpine component:
    ```js
    export default () => ({
      init() {
        flatpickr(this.$el, {
          enableTime: false,
          dateFormat: 'Y-m-d',
          minDate: 'today',
        })
      }
    })
    ```
  - Apply `x-data="datepicker"` to any `<input type="text">` that should be a date picker.
  - Import Flatpickr CSS in the SCSS: `@import "flatpickr/dist/flatpickr.min.css"` and create a theme override to match the Bootstrap palette.
- Install Notyf via npm (`notyf`). Notyf replaces the custom snackbar and the Bootstrap alert placeholder for toast notifications.
  - In `static_src/js/main.js`, import Notyf: `import { Notyf } from 'notyf'`.
  - Create a global Alpine store or a simple module that exposes a `notify(message, type)` function.
  - Replace ALL occurrences of `appendAlert()` and the snackbar element with `notyf.success(message)` or `notyf.error(message)`.
  - Import Notyf CSS: `@import "notyf/notyf.min.css"` and customize colors to match the theme.
- Install Dropzone.js via npm (`dropzone`). Dropzone replaces the basic file input for product image uploads.
  - Create a `static_src/js/components/dropzone.js` Alpine component:
    ```js
    export default (maxFiles = 1) => ({
      init() {
        new Dropzone(this.$el, {
          maxFiles,
          acceptedFiles: 'image/png,image/jpeg,image/webp',
          maxFileSize: 10, // MB
          dictDefaultMessage: 'Drop image here or click to upload',
        })
      }
    })
    ```
  - Apply `x-data="dropzone()"` to the image upload `<form>` element in admin product create/edit.
  - Style Dropzone to match the Bootstrap card theme (rounded borders, subtle shadow).
- For all four libraries, import their CSS in the main SCSS bundle (NOT as separate `<link>` tags). This keeps the number of HTTP requests to a minimum.

### Best Practices

- Each third-party library must be wrapped in an Alpine component for lifecycle management. Alpine's `init()` lifecycle hook is the correct place to initialize DOM-dependent widgets.
- Unwrap/destroy library instances in Alpine's `destroy()` lifecycle hook to prevent memory leaks when Alpine re-renders the component.
- Library CSS should be imported in `style.scss` and overridden to match the Bootstrap theme. Do NOT accept default styling — it will clash with the custom palette from M11.
- For Choices.js, enable `searchEnabled: true` but disable `shouldSort` (alphabetical sorting is confusing for option lists that have a logical order).
- For Flatpickr, use `enableTime: false` for date-only fields (coupon dates). If time input is needed later, add `enableTime: true` selectively.
- For Notyf, configure `position: { x: 'right', y: 'top' }` and `duration: 4000` as sane defaults.
- For Dropzone, set `acceptedFiles` to match the server-side validation from M8 (png/jpeg/webp). Reject files on the client side BEFORE upload.

### Flaws to Avoid

- Do NOT use jQuery UI CDN as a fallback for any of these libraries. Remove ALL traces of jQuery UI — CSS, JS, and theme files.
- Do NOT initialize Choices.js/Flatpickr/Dropzone imperatively on DOM elements that are conditionally rendered by Alpine (`x-if`, `x-for`). Alpine's `init()` lifecycle handles this correctly because it runs after the element is added to the DOM.
- Do NOT use library CDN scripts — always bundle through Vite. CDN scripts bypass Vite's dependency management and create version drift.
- Do NOT import entire library CSS if a minimal CSS file is available (e.g., Flatpickr has `flatpickr.min.css` — use that, not the themes bundle).
- Do NOT forget to remove the old jQuery UI CSS link (`http://ajax.googleapis.com/ajax/libs/jqueryui/1.8.16/themes/ui-lightness/jquery-ui.css`) from `base.html` — it's loaded over HTTP, which causes mixed content warnings.

### Verification / Expected Output

- All `<select>` elements in admin forms now have search/filter behavior via Choices.js (previously plain `<select>` or jQuery UI autocomplete).
- Date inputs in coupon forms open a Flatpickr calendar when clicked. Selecting a date fills the input in `YYYY-MM-DD` format.
- Form submissions show a Notyf toast (top-right, auto-dismiss) on success (green) or error (red), instead of the old inline Bootstrap alert.
- Product image upload in admin shows a Drag & Drop zone with preview. Uploaded images show a thumbnail preview before the form is submitted.
- Zero HTTP requests to jQuery UI CSS or JS files.
- All four libraries' CSS is bundled in the main `style-<hash>.css` file (confirm via network tab — one CSS file only, not five).
- Mobile-friendly: Choices.js search, Flatpickr calendar, Dropzone drag area all work on touch devices.

---

## MILESTONE 14 — Card-Based Layouts + Skeleton Loaders + Spinners + Spacing/Typography Consistency

Apply a consistent visual design language across all 31 templates. This milestone is purely visual — no functional changes, no new behavior. The goal is that every page looks like it belongs to the same professional store.

### Implementation

- Establish a card-based layout pattern:
  - Product list: Each product is a Bootstrap card with `card-img-top`, `card-body`, `card-footer`. Cards are laid out in a responsive grid (`row-cols-1 row-cols-md-2 row-cols-lg-3 row-cols-xl-4 g-4`).
  - Product detail: Card layout with image left, details right (use `row` + `col`), full-width description below.
  - Cart items: Each cart item is a horizontal card (image thumbnail + title + quantity + price + remove button).
  - Checkout: Order summary as a card in the right column, form in the left column.
  - Admin list pages: Each table row should have `align-middle` and consistent padding. Consider converting key admin pages (product list) to card grid with an optional table toggle.
  - Auth pages: Login/register/setup are centered cards (max-width 450px, centered vertically with `min-height: 100vh` + flex).
  - Admin dashboard: Stats cards with icons in a grid (4 columns on desktop, 2 on tablet, 1 on mobile).
- Add skeleton loaders for async content:
  - Product list page: Before Alpine fetches/hydrates, show a CSS-only skeleton grid (pulsing gray rectangles matching the card aspect ratio).
  - Implementation: Use a CSS `@keyframes pulse` animation on `background: linear-gradient(...)` with `background-size: 200%`. Apply to placeholder divs that match the card dimensions.
  - Skeletons are visible for ~300-500ms while the page loads. This prevents layout shift (CLS) and improves perceived performance.
  - Use Bootstrap's `placeholder` class (available in Bootstrap 5.3) with `placeholder-glow` for consistent skeleton styling.
- Add loading spinners on form submissions:
  - On any admin form submit (create/edit), show a spinner overlay on the submit button and disable it to prevent double-submission.
  - Use Alpine: `x-data="{ loading: false }"` with `@click="loading = true"` on submit buttons. Show `<span x-show="loading" class="spinner-border spinner-border-sm"></span>` inside the button.
  - This applies to: all admin CRUD forms, coupon forms, order forms, login, register.
- Apply consistent spacing and typography:
  - Section headings: All `<h1>`–`<h6>` tags across templates should use consistent size/weight hierarchy. Use Bootstrap typography classes (`fs-1` through `fs-6`, `fw-bold`, `text-muted`).
  - Vertical spacing: Ensure consistent `mb-*` and `mt-*` between sections. The content area (inside `.container`) should have `py-4` (padding top/bottom 24px).
  - Horizontal padding: Cards inside the container should have `g-3` (gutters). No card should touch the edge of the viewport on mobile.
  - Responsive font sizes: Ensure text is readable at all breakpoints. Use `fs-md-5` or similar responsive font size classes.
  - Links and buttons: Consistent hover underline/none pattern. Nav links should have `text-decoration-none` with a bottom border on hover (not underline).
- Hover transitions:
  - Product cards: `transition: transform 0.2s, box-shadow 0.2s` on hover — subtle scale(1.02) + elevated shadow.
  - Admin table rows: `:hover` background change (already partially done with `.table-row:hover`), but use `table-hover` Bootstrap class instead of custom CSS.
  - Buttons: Bootstrap already has button hover transitions. Do NOT override unless necessary.
  - Nav links: Smooth color transition on hover (0.15s ease).

### Best Practices

- Use Bootstrap utility classes for spacing (`m-*`, `p-*`, `g-*`, `gap-*`) instead of writing custom CSS. The `style.scss` should add at most 20-30 lines of custom styles for this milestone.
- Skeleton loaders must match the exact dimensions of the content they replace (same border-radius, same aspect ratio). Misaligned skeletons cause more CLS, not less.
- Spinners in buttons must use the `spinner-border` or `spinner-grow` Bootstrap component classes. Do NOT create custom spinner CSS.
- Card `box-shadow` should use Bootstrap's `shadow-sm` class by default and `shadow` on hover. This is consistent with the theme from M11.
- Every page must be tested at 3 viewport widths: 375px (mobile), 768px (tablet), 1440px (desktop). Cards, grids, and tables must not overflow or have horizontal scroll.

### Flaws to Avoid

- Do NOT add animations that slow down page interaction. The hover scale effect must use `transform` (GPU-accelerated) not `width`/`height` (triggers layout).
- Do NOT add skeleton loaders to every page — only pages where content loads asynchronously (product list, admin dashboard with charts). Static pages (login, 404) do not need skeletons.
- Do NOT use `!important` in card hover transitions. Bootstrap's utility classes have low specificity and can be overridden by a well-structured CSS cascade.
- Do NOT add the same shadow to every element — cards get shadows, but navbars, footers, and buttons should not have box-shadow unless they are elevated elements (dropdowns, modals).
- Do NOT change layout structure in this milestone (e.g., converting a table to a card grid is a layout change, not a styling change). Pure visual polish only.
- Do NOT use CSS `transition` on `display` or `visibility` properties — these are not animatable. Use `opacity` and `transform` instead.

### Verification / Expected Output

- Every page uses the card-based layout pattern appropriate to its content. No page uses raw unstyled Bootstrap containers with no cards.
- Product list shows skeleton placeholders on initial page load (for <500ms) before content renders.
- Form submit buttons in admin show a spinner when clicked and are disabled until the response returns.
- All pages have consistent vertical rhythm: same heading styles, same paragraph spacing, same card padding.
- Hovering over a product card produces a subtle lift effect (scale + shadow). Hovering over a table row changes background color.
- At 375px viewport, no text is cut off, no cards overflow, and the layout stacks vertically correctly.
- At 1440px viewport, the layout uses the full width gracefully with appropriate gutters.
- Lighthouse "Layout Shift" score is 0 (or negligible) on the product list page.
- Lighthouse "Best Practices" score is 100.

---

## MILESTONE 14.5 — Apply Hover Transitions, Shadows, Border-Radius Across All Templates

Continue the visual polish from M14 by ensuring every interactive element in every template has consistent hover/focus/active states. This is the micro-interactions milestone — small visual details that distinguish a professional store from a hobby project.

### Implementation

- Audit every `<a>`, `<button>`, `<input>`, `<select>`, `<textarea>`, and card element across all 31 templates for consistent interaction states:
  - Hover state: Every clickable element must have a visual hover indicator (color change, underline, shadow, or scale).
  - Focus state: Every form input must have a visible focus ring (Bootstrap's `$input-focus-box-shadow` already provides this — verify it matches the theme color from M11).
  - Active state: Buttons and links must have a visual active/pressed state (Bootstrap provides this by default for `.btn` — verify it's enabled).
- Specific applied patterns:
  - Admin table rows: `table-hover` class on all `<table>` elements. Clickable rows get `cursor: pointer` and `:hover` background change.
  - Admin sidebar links (if any): Left border on active item, background color change on hover.
  - Product list cards: `transition: box-shadow 0.2s ease-in-out` — hover elevates the shadow from `shadow-sm` to `shadow`.
  - Navbar links: Underline or bottom-border animation on hover (`background-size` trick or `border-bottom` transition).
  - Button hover: Bootstrap provides `:hover` states for all `.btn-*` classes — do NOT override unless the theme colors need adjustment.
  - Pagination links: `:hover` background matches the primary theme color.
  - Form input focus: The focus ring (`box-shadow`) should use the primary color at ~25% opacity (Bootstrap's default is good — just verify).
  - Dropdown items (if implemented): `:hover` background matches the primary color at low opacity.
- Add subtle entrance animations for page content:
  - Card grid items: `animation: fadeInUp 0.3s ease-out` with staggered delay (`animation-delay: calc(var(--index) * 0.05s)`) for a cascading reveal.
  - The `fadeInUp` keyframe: `from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); }`.
  - This should be subtle — not a distracting gimmick. Use `@media (prefers-reduced-motion: reduce)` to disable animations for accessibility.
- Verify and standardize border-radius:
  - Check every card, modal, dropdown, tooltip, popover, and input group across the app.
  - Cards: `rounded-3` or `rounded-4` (depending on the scale from M11).
  - Inputs: `rounded-2` (default) — do NOT change unless the theme specifies a larger radius.
  - Buttons: `rounded-2` (consistent with inputs).
  - Modals: `rounded-3` to match cards.
  - Dropdowns: `rounded-2`.
  - Tooltips/popovers: `rounded-1` (smaller radius — they are tiny elements).
  - Badges: `rounded-pill` if they should be pill-shaped (cart count badge), `rounded-1` otherwise.

### Best Practices

- Use CSS custom properties for transition durations and easing functions so they are consistent across the entire app:
  ```scss
  :root {
    --transition-fast: 150ms ease;
    --transition-base: 200ms ease;
    --transition-slow: 300ms ease;
  }
  ```
  Apply them with `transition: transform var(--transition-base);`
- Use `will-change: transform` sparingly — only on elements that animate during interaction (card hover, modal open). Do NOT add `will-change` to every element — it consumes GPU memory.
- For the staggered card entrance animation, use a CSS counter or inline `style="--index: 0"` on each card. Alpine can set `:style="'--index: ' + index"` in `x-for` loops.
- Respect `prefers-reduced-motion: reduce`. Wrap all animations in `@media (prefers-reduced-motion: no-preference)` and add a simple `opacity: 1` fallback.
- Use `transform: scale()` for card hover — it's GPU-accelerated and does NOT trigger repaint. Do NOT use `width`/`height` changes for hover effects.

### Flaws to Avoid

- Do NOT add transitions to every CSS property — only the ones that change on interaction. Adding `transition: all 0.2s` to `*` is a performance anti-pattern.
- Do NOT use `box-shadow` transitions on more than 5-10 visible elements at a time. Multiple shadow transitions cause repaint jank on low-end devices.
- Do NOT animate elements that are not interactable (static text, background decorations). Animations should only communicate interactivity.
- Do NOT use `translate3d()` (3D transforms) just to force GPU acceleration — 2D `translate/scale` with `will-change` is sufficient and uses less GPU memory.
- Do NOT add entrance animations on pages where the user expects immediate interaction (login form, checkout). Entrance animations on auth pages feel slow and annoying.
- Do NOT override Bootstrap's built-in `transition` properties on `.btn`, `.collapse`, `.modal`, `.carousel` — Bootstrap's transitions are well-tested and performant.

### Verification / Expected Output

- Every interactive element (link, button, input, card, table row) has a visible hover/focus/active state.
- Hovering over a product card: shadow deepens, card lifts ~2px.
- Hovering over admin table rows: background color changes to a subtle tint of the primary color.
- Clicking any button: visible active/pressed state (Bootstrap default).
- Tabbing through form inputs: each input gets a visible focus ring in the theme primary color.
- Page content on product list fades in with a subtle upward stagger effect (first card appears first, next cards follow at 50ms intervals).
- When `prefers-reduced-motion: reduce` is enabled (OS accessibility setting), ALL animations and transitions are disabled — no movement whatsoever.
- Lighthouse "Accessibility" score is 100 (no animations hinder accessibility).
- All border-radius values are consistent across the app: cards `rounded-3`, inputs `rounded-2`, buttons `rounded-2`, badges `rounded-pill`.

---

## MILESTONE 15 — Admin Dashboard Overhaul (Chart.js + Stats Cards + Recent Orders + Audit Log UI)

Transform the admin home page from a bare-bones list of links into a real dashboard with data visualizations, key metrics, and actionable information. This is the single most impactful page for store operators.

### Implementation

- Install Chart.js via npm (`chart.js`). Chart.js is the most popular open-source charting library and integrates well with Alpine.js.
  - Import in `main.js`: `import { Chart, registerables } from 'chart.js'; Chart.register(...registerables)`.
  - Create a `static_src/js/components/revenue-chart.js` Alpine component:
    ```js
    export default () => ({
      chart: null,
      init() {
        this.chart = new Chart(this.$el, {
          type: 'line',
          data: {
            labels: [], // populated from API
            datasets: [{
              label: 'Revenue',
              data: [],
              borderColor: '#4F46E5',
              tension: 0.3,
            }]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: { y: { beginAtZero: true } },
          }
        })
      },
      destroy() {
        if (this.chart) this.chart.destroy()
      }
    })
    ```
  - Apply `x-data="revenueChart" x-init="fetch('/admin/api/revenue').then(r => r.json()).then(d => { /* update chart */ })"` to the chart canvas.
- Create admin API endpoints for dashboard data:
  - `GET /admin/api/stats`: Returns `{ "total_revenue": 1234.56, "total_orders": 42, "total_products": 150, "total_users": 12 }`. All from MongoDB aggregation.
  - `GET /admin/api/revenue?period=7d`: Returns daily revenue for the last N days as `[{ "date": "2024-01-01", "revenue": 123.45 }, ...]`. Must be cached (Redis, 5-min TTL) since this is an aggregation-heavy query.
  - `GET /admin/api/recent-orders?limit=5`: Returns the 5 most recent orders with status, total, customer name, and date.
  - `GET /admin/api/popular-products?limit=5`: Returns top 5 products by order count with name, image, and total sold.
- Build the dashboard layout in `admin/home.html`:
  - Top row: 4 stat cards in a responsive grid (`col-lg-3 col-md-6`):
    - Total Revenue (with `$` prefix and currency symbol, formatted with 2 decimals)
    - Total Orders
    - Active Products
    - Registered Users
    - Each card has an icon (Bootstrap Icons), a large number, and a small label. Use `card bg-primary-subtle` or similar with `text-primary-emphasis`.
  - Middle row: Revenue chart (left, `col-lg-8`) and Popular Products (right, `col-lg-4` as a list with small images).
  - Bottom row: Recent Orders table (full width, `col-12`).
- Fetch dashboard data with Alpine on page load:
  - Use `x-init` to fetch all API endpoints in parallel with `Promise.all()`.
  - Show skeleton loaders (from M14) while data loads.
  - Handle errors: if an API call fails, show a "Failed to load" alert with a retry button.
  - Auto-refresh: Set a 60-second interval (`setInterval`) to re-fetch stats data (but NOT chart data — chart data refreshes every 5 minutes).
- Add audit log viewer:
  - Create a new admin page `GET /admin/audit-log` that reads from the audit log collection (M6.7 creates these logs).
  - Display as a table: Timestamp, Admin user, Action (Create/Edit/Delete), Entity type (Product/Order/Coupon), Entity ID, Summary of changes.
  - Add search by admin username and filter by action type.
  - Paginate with 50 entries per page.
  - Add link to audit log from admin sidebar/navbar.

### Best Practices

- Chart.js charts MUST be destroyed in Alpine's `destroy()` lifecycle hook. If the component is re-initialized without destroying the old chart, Chart.js leaks canvas elements and memory.
- Admin API endpoints should use caching (`@cached(ttl=300)` decorator) because dashboard data doesn't change between requests. Only the current session's stats need real-time accuracy.
- Stats cards should show `--` or a skeleton while loading, NOT a flash of zeros. Use Alpine's `x-init` to fetch data and populate `x-text` bindings after the response arrives.
- Revenue chart should have a period selector (7d, 30d, 90d, 1y) that re-fetches data and updates the chart. Store the selected period in Alpine state.
- Responsive: The chart should collapse to full-width below 768px (charts in narrow columns are unreadable).
- Accessible: Chart.js supports `aria-label` on the canvas. Provide a text-based data table below the chart as a fallback for screen readers.

### Flaws to Avoid

- Do NOT run aggregation queries on the main thread synchronously — admin dashboard API calls must be async and cached. Heavy aggregations (revenue by day) should use a pre-computed cache or a materialized view.
- Do NOT render the chart in the server-side HTML — Chart.js requires a client-side canvas. The template should have `<canvas x-data="revenueChart"></canvas>` and Alpine handles rendering.
- Do NOT load ALL orders/products/users into memory to compute stats. Use MongoDB aggregation pipeline with `$group`, `$sum`, `$count` stages — the database does the computation, not Python.
- Do NOT hardcode currency symbol — use `STRIPE_CURRENCY` from env to determine the symbol. A helper function in the template or a passed context variable handles this.
- Do NOT show real names or email addresses in the audit log without considering GDPR/privacy — the audit log is an internal admin tool, but still avoid exposing PII unnecessarily.
- Do NOT allow the audit log to grow unbounded — add a TTL index on the audit log collection so entries older than 90 days are automatically deleted.

### Verification / Expected Output

- `GET /admin/` shows 4 stat cards with live data (revenue, orders, products, users).
- Stat cards load within 1 second (cached). Skeleton loaders show while data is being fetched.
- Revenue chart renders a line chart with the last 7 days of revenue. Selecting "30d" re-fetches and redraws.
- Popular Products list shows top 5 products with thumbnails and order counts.
- Recent Orders table shows the last 5 orders with status badges (color-coded: pending=yellow, paid=green, shipped=blue, cancelled=red).
- `GET /admin/audit-log` shows a paginated table of admin actions with search/filter.
- Chart.js canvas renders without JavaScript errors. The chart is responsive (resizes with the window).
- All admin API endpoints return JSON (not HTML) — confirm with `curl http://localhost:8989/admin/api/stats` returns `{"total_revenue": ...}`.
- Audit log TTL index exists: `db.audit_logs.createIndex({"created": 1}, {expireAfterSeconds: 7776000})` (90 days).

---

## MILESTONE 16 — Product List & Search UX (Category Filters, Sort, Search Suggestions, Pagination Styling)

Transform the product listing page from a simple grid into a full-featured product discovery experience. Add client-side category filtering, sort controls, live search suggestions, and polished pagination.

### Implementation

- Category filter pills/tabs:
  - On the product list page, show a row of category filter pills above the product grid.
  - Each pill is a `<button>` or `<a>` with `x-data` that toggles an active state and filters the product list.
  - "All" pill is selected by default. Clicking "All" shows all products. Clicking a specific category filters to that category.
  - Implementation approach:
    - Server-side: Pass `categories` list to the template context (already exists).
    - Client-side: Use Alpine to fetch `GET /product/?category=<slug>` when a pill is clicked, and replace the product grid content.
    - Alternative (simpler, recommended): Make each pill a `<a href="/product/{slug}">` link with `?page=1`. The server renders the filtered list. Add Alpine to highlight the active pill based on the current URL.
  - The simpler approach is preferred for now — server-rendered, no client-side state management needed. Alpine only handles the active pill visual state.
- Sort dropdown:
  - Add a "Sort by" `<select>` dropdown next to the category pills.
  - Options: "Newest" (default), "Price: Low to High", "Price: High to Low", "Name: A-Z".
  - Each option navigates to `?sort=<key>` when selected. Use Alpine `x-on:change` to redirect with the new sort parameter.
  - The server handles sorting in the MongoDB query: `collection.find().sort(sort_field, direction)`.
  - Add a `sort` query parameter handler in `apps/product/routers.py` product list endpoint.
- Search suggestions with debounce:
  - Add a search bar in the navbar or above the product grid (if in the navbar, it appears on all pages; if above the grid, only on product list).
  - As the user types, use Alpine `x-on:input.debounce.300ms` to call `GET /product/search?q=<query>&limit=5` and show a dropdown of suggestions.
  - Suggestions display: product thumbnail (small), product name, price. Clicking navigates to product detail.
  - The suggestions dropdown is positioned absolutely below the search input, with `x-show` and `x-transition`.
  - Closing: Clicking outside the suggestion box closes it (`@click.away` on the Alpine component).
  - The server already has `/product/search?q=` from M8.1. Add a `limit` query parameter if not present.
- Pagination styling:
  - The current pagination is likely bare-bootstrap. Enhance it:
    - Show page numbers with active state highlighted in the theme primary color.
    - Show "Previous" and "Next" buttons (disabled on first/last page).
    - Show total page count: "Page 3 of 12" next to the pagination controls.
    - Add a "Per page" selector (12, 24, 48, 96) that re-fetches with the new limit.
  - This is entirely server-rendered — the pagination links are `<a href="?page=N&per_page=M">` tags. Alpine is only needed if you add a "Per page" selector (watching the select change and navigating).
- Empty state:
  - When a category has no products, or a search returns no results, show a friendly empty state illustration (use Bootstrap Icons for the graphic) with a "Browse all products" link.

### Best Practices

- The search bar with suggestions should be a reusable Alpine component (`x-data="searchSuggestions"`) that can be placed in the navbar or anywhere.
- Server-side search should use MongoDB `$text` index with `$search` operator (already done in M8.1). Do NOT use regex-based search for the suggestion endpoint — `$text` is much faster on large datasets.
- The suggestions API endpoint should return a small payload (max 5 results, minimal fields). Keep the response under 2KB for fast rendering.
- Sort options must be validated server-side — do NOT pass raw sort field names from the client to MongoDB. Use an allowlist: `{"newest": ("created", -1), "price_asc": ("price", 1), ...}`.
- The "Per page" selector must cap at a maximum value (e.g., 96) to prevent abuse.

### Flaws to Avoid

- Do NOT fetch ALL products client-side and filter/sort in JavaScript. This breaks with large catalogs (1000+ products). Always filter and sort server-side.
- Do NOT use Alpine `x-for` to render the entire product grid — server-rendered HTML is faster for initial page load. Alpine should only enhance interactive elements (filters, sort, suggestions).
- Do NOT use `$text` search without a text index — MongoDB will return an error. Verify the text index exists on `(name, description)` from M8.1.
- Do NOT show the suggestions dropdown when the search input is empty or has fewer than 2 characters. This prevents a flash of irrelevant results.
- Do NOT forget to handle the case where no products match the current filter/sort — the empty state must be user-friendly, not a bare "0 results" message.

### Verification / Expected Output

- Product list page shows category filter pills. Clicking "Electronics" filters to electronics products only. The active pill has the theme primary color background.
- Sort dropdown changes the product order. "Price: Low to High" sorts ascending. The selected sort option persists in the URL.
- Search bar in navbar: Typing "shoe" shows a dropdown with up to 5 product suggestions (thumbnail + name + price). Clicking a suggestion navigates to the product detail page.
- Pagination shows "Page 1 of 5" with Previous/Next buttons. Clicking "2" goes to page 2. The current page is highlighted.
- "Per page" selector: Changing to 24 increases the number of products per row/page.
- Empty category or search returns: Shows an illustration (bi-search or bi-box) with "No products found. Try a different category or search term." and a link to all products.
- All filtering/sorting actions update the URL (so the page state is shareable/bookmarkable).
- The search suggestions dropdown closes when clicking outside the search input.

---

## MILESTONE 17 — Auth Pages Redesign (Centered Cards, Google Button, Inline Validation, Forgot Password Placeholder)

Redesign the login, register, and setup pages to look professional and feel polished. These are often the first pages a user sees — they must inspire confidence.

### Implementation

- Centered card layout for all auth pages:
  - Wrap the form in a `.card` with `shadow`, `rounded-3`, and `border-0`.
  - Center the card on the page: use a full-viewport flex container:
    ```html
    <div class="min-vh-100 d-flex align-items-center justify-content-center bg-light">
      <div class="card shadow" style="max-width: 450px; width: 100%;">
        <div class="card-body p-4 p-md-5">
          <!-- form here -->
        </div>
      </div>
    </div>
    ```
  - The `bg-light` background contrasts with the white card, giving visual depth.
  - Logo/brand at the top of the card: Use the "My Shop" text or a simple SVG logo with `mb-4`.
- Inline form validation:
  - Each field has a `<div class="invalid-feedback">` or Alpine-managed error text directly below the input.
  - Server-side validation errors are returned as JSON (or form errors) and rendered inline via Alpine:
    ```html
    <div x-data="{ error: '' }">
      <input :class="{ 'is-invalid': error }" @input="error = ''">
      <div class="invalid-feedback" x-text="error"></div>
    </div>
    ```
  - Client-side validation: Email format, password minimum length (8), username length (3-32). Validate on `blur` (not on every keystroke — avoid annoying the user).
  - Password field: Show a toggle button (eye icon) to show/hide password. Use Bootstrap Icons `bi-eye`/`bi-eye-slash` and Alpine `x-on:click` to toggle `type="password"` / `type="text"`.
  - Password strength indicator (optional but nice): A colored bar below the password field that goes from red (weak) to green (strong) as the user types. Use a simple heuristic (length + has uppercase + has lowercase + has digit + has special char).
- Google OAuth button styling:
  - If `GOOGLE_CLIENT_ID` is configured (`x-data="{ googleEnabled: true }"`), show a Google sign-in button styled to Google's brand guidelines:
    - White background, 1px border, Google logo SVG (or "G" icon), "Sign in with Google" text.
    - Full-width button, same height as the "Login" button, so they align in a stacked layout.
  - If Google OAuth is NOT configured, hide the button entirely. Do NOT show a disabled/styled-but-broken button.
  - Position: Above the "or" divider, before the email/password form.
  - Add the "or" divider as `hr` with centered "or" text using Bootstrap's `position: relative` + `overflow: hidden` trick or simply `<div class="text-center text-muted my-3">or</div>`.
- "Forgot Password" placeholder:
  - Below the password field and above the submit button, add a "Forgot password?" link styled as small text (`text-muted`).
  - The link navigates to a `GET /user/forgot-password` page that shows a "Coming soon — enter your email to get notified" form (placeholder only — backend does not send reset emails yet). This sets expectation without crashing.
  - Alternatively, just show the link with `href="#"` and an Alpine `@click.prevent` that shows a "Password reset coming soon" Notyf toast. This is simpler and avoids building a placeholder page.
- Registration page enhancements:
  - Add a "Confirm password" field with client-side match validation (Alpine `x-on:input` compares with password field).
  - Show a small helper text below each field: "Must be 3-32 characters" for username, "We'll never share your email" for email, "At least 8 characters" for password.
  - Terms of service checkbox: Required checkbox with a link to "/terms" (placeholder). Unchecked = form cannot submit.
- Redirect behavior:
  - After login, redirect to the page the user was trying to access (use `next` query parameter), or to `/product/` if no `next`.
  - After registration, redirect to login page with a success message ("Account created! Please log in.").
- Loading state on submit:
  - Submit button shows a spinner and is disabled while the request is in flight (Alpine `x-data="{ loading: false }"`).
  - Prevent double-submission (user cannot click twice).

### Best Practices

- Auth forms must be full-width on mobile (the `max-width: 450px` constraint is fine — on mobile, the card fills the viewport width with 16px padding). Verify at 375px.
- Password show/hide toggle must preserve input state (using Alpine `x-model` on the password field and toggling `type` is safe — Alpine preserves input value during re-render).
- The "or" divider must use semantic HTML (`<hr>` with CSS overlay) rather than just a `<div>` with text, for accessibility.
- Google OAuth button must follow Google's branding guidelines: full Google logo or "G" icon, exact colors, proper spacing. Do NOT use a custom-colored button that says "Google".
- Inline validation errors must disappear as soon as the user starts typing (Alpine `@input="error = ''"`). Showing stale errors is a common UX failure.
- The `next` redirect parameter must be validated — only allow redirects to relative paths (same origin) to prevent open redirect vulnerabilities.

### Flaws to Avoid

- Do NOT serve auth pages over HTTP in production. This milestone is a visual update only — the server should already enforce HTTPS (via nginx from M3/M7).
- Do NOT hardcode redirect URLs — always use `url_for()` in FastAPI to generate redirect paths.
- Do NOT show the Google OAuth button if `GOOGLE_CLIENT_ID` is not configured — this would lead to a 500 error when clicked (as noted in the current bug list). Check the env var server-side and pass `google_enabled` to the template context.
- Do NOT implement "Remember me" functionality in this milestone — that requires JWT token lifetime management, which is a backend concern outside the frontend scope.
- Do NOT store user credentials in Alpine state (`x-model`) without HTTPS — credentials in transit must be encrypted. This is handled by nginx HTTPS termination, not by the frontend.

### Verification / Expected Output

- Login page shows a centered card with email/username input, password input with show/hide toggle, "Forgot password?" link, and Login button.
- If Google OAuth is configured, the Google sign-in button appears above the email/password form. If not configured, the button is absent.
- Registration page shows username, email, password, confirm password fields. Confirm password field validates match on input.
- Form submission: Button shows spinner, is disabled. Server errors appear inline below the relevant field.
- After successful registration: Redirect to login page with a success toast (Notyf).
- After successful login: Redirect to the `next` URL, or `/product/` if no `next`.
- "Forgot password?" click shows a Notyf toast: "Password reset coming soon."
- On mobile (375px), the auth card fills the viewport width with 16px padding on each side.
- The password toggle works: clicking the eye icon switches between text and password input types.
- No console errors on auth pages.

---

## MILESTONE 18 — Cart & Checkout UX Overhaul (Offcanvas Cart, Checkout Steps, Order Summary, Stripe Styling)

Revamp the shopping cart and checkout flow to match modern e-commerce UX standards. The goal is to make the cart accessible from any page, show clear progress through checkout, and make the Stripe payment form look like part of the store.

### Implementation

- Offcanvas cart (slide-in from right):
  - Replace or augment the full-page `/cart/` detail page with a Bootstrap Offcanvas component that slides in from the right when the user clicks the cart icon in the navbar.
  - The offcanvas contains: a list of cart items (each with thumbnail, name, quantity stepper, price, remove button), a subtotal at the bottom, and a "View Full Cart" / "Checkout" button.
  - Use Alpine to manage the offcanvas state: `x-data="{ cartOpen: false }"` on the body or a wrapper. The cart icon triggers `cartOpen = true`. The offcanvas uses `x-show="cartOpen"` with Bootstrap offcanvas classes.
  - Quantity stepper: Alpine `x-on:click` + / - buttons that call `POST /cart/add/` or `POST /cart/remove/` and update the offcanvas content dynamically (fetch the updated cart HTML and swap with `x-html`).
  - If the user is not on the cart page and adds an item, the offcanvas slides in automatically with a brief "Item added!" animation.
  - Keep the full `/cart/` detail page for users who want a full-page view (it shows more details: per-item total, coupon input, shipping estimate, etc.).
- Checkout progress steps:
  - On the checkout page (`/order/create/`), add a progress indicator at the top with 4 steps: "Cart" → "Details" → "Payment" → "Confirmation".
  - Each step is a circle with a number and a label below. Completed steps are filled (primary color), current step is outlined (primary color with bold text), future steps are grayed out.
  - Use CSS (flexbox) for the step layout, not a Bootstrap component. The steps are purely visual — each step corresponds to a distinct page/state.
  - Implementation:
    - Step 1 (Cart): Checkmark (icon), active if on `/cart/`.
    - Step 2 (Details): Checkmark or number 2, active if on `/order/create/`.
    - Step 3 (Payment): Number 3, active if on `/payment/process/`.
    - Step 4 (Confirmation): Number 4, active if on `/payment/completed/`.
  - Pass a `checkout_step` variable from the server to mark which step is active.
- Order summary sidebar on checkout:
  - On the checkout page, the right column shows a sticky order summary card:
    - List of items (name, qty, line total)
    - Subtotal
    - Coupon discount (if applied, shown as a negative amount)
    - Shipping (if applicable, or "Free")
    - Total (bold, large font)
    - A note: "All prices in [currency]"
  - This summary updates when the coupon changes (Alpine fetch + re-render).
  - The summary is `position: sticky; top: 1rem` so it follows the user as they scroll the checkout form on the left.
- Stripe payment form styling:
  - Stripe's Elements API render an iframe for the card number, expiry, CVC. You cannot style the iframe directly, but you can customize the `style` object passed to `elements.create('card', { style: { ... } })`.
  - Match the Stripe Elements style to the Bootstrap theme:
    ```js
    const style = {
      base: {
        fontSize: '16px',
        fontFamily: '"Inter", system-ui, sans-serif',
        color: '#212529',
        '::placeholder': { color: '#6c757d' },
        ':-webkit-autofill': { color: '#212529' },
      },
      invalid: { color: '#dc3545' },
    }
    ```
  - Wrap the Stripe card element in a Bootstrap form group with label "Card Details" and a styled div (`form-control border rounded-2 p-3 bg-white`).
  - Add a "Pay Now" button that shows a spinner while processing. Disable the button after first click to prevent double charges.
  - Show validation errors (Stripe returns them in real-time via the `change` event) inline below the card element.
- Order confirmation page:
  - Show a success animation (checkmark icon that scales in, using CSS animation).
  - Order number prominently displayed.
  - Summary of what was ordered.
  - "Continue Shopping" button (links to product list).
  - Email confirmation note: "A confirmation email has been sent to [email]."

### Best Practices

- The offcanvas cart should fetch its content from the server (HTMX-style) instead of maintaining client-side state. Alpine fetches `GET /cart/offcanvas-content` (returns HTML fragment) and swaps it into the offcanvas body.
- Quantity stepper buttons should be debounced (300ms) to prevent rapid-fire requests when the user clicks rapidly.
- Stripe Elements must be loaded asynchronously. Load the Stripe.js library only on pages that use it (payment process page), not in the global bundle.
- The Stripe publishable key should be passed to the template from the server via a context variable, NOT hardcoded in JavaScript.
- The checkout progress steps must be accessible: each step circle should have `aria-label="Step N: Step Name"` and `aria-current="step"` on the current step.
- The order summary should show the coupon code and discount amount in a readable format: "Coupon SAVE20: -$4.00".

### Flaws to Avoid

- Do NOT store cart state in Alpine or localStorage — the cart is server-managed (cart data stored in MongoDB, accessed via cookie). The offcanvas cart fetches fresh content from the server every time it opens.
- Do NOT show payment processing errors in an alert — show them inline next to the Stripe card element. Stripe provides specific error types (card_declined, expired_card, etc.) that should be shown verbatim.
- Do NOT navigate away from the payment page until Stripe confirms the payment is complete. The "processing" overlay should block navigation.
- Do NOT forget to handle the Stripe webhook redirect back to the store — the user may be redirected to `/payment/completed/` after successful payment, or `/payment/canceled/` if they cancel.
- Do NOT remove the full-page cart — the offcanvas is a convenience overlay. Users who want to see a detailed cart or enter a coupon code need the full page.

### Verification / Expected Output

- Clicking the cart icon in the navbar: Offcanvas slides in from right with cart items, subtotal, and Checkout button.
- Adding an item to cart from product detail page: Offcanvas auto-opens with a brief "Item added!" animation.
- Quantity stepper in offcanvas: Clicking +/- updates the quantity (server call) and the subtotal updates.
- Checkout page shows 4 progress steps at the top. "Cart" and "Details" are completed (green/filled), "Payment" is current (outlined), "Confirmation" is gray.
- Order summary sidebar is sticky and shows item list, subtotal, discount, total. Applying a coupon updates the summary.
- Stripe payment form: Card input is styled to match the Bootstrap theme (Inter font, correct colors, rounded borders).
- "Pay Now" button is disabled after first click, shows a spinner.
- Successful payment: Redirects to `/payment/completed/` with checkmark animation, order number, and "Continue Shopping" button.
- Canceled payment: Redirects to `/payment/canceled/` with a "Return to cart" link and a message that no charge was made.
- No console errors on any cart/checkout page.

---

## MILESTONE 19 — Mobile Polish (Hamburger Animation, Touch Tables, CLS Fixes, 375/768/1440 Testing)

Go through every template and fix mobile-specific issues. The store must look and feel native on a phone — not like a desktop site squished into a small screen.

### Implementation

- Hamburger menu animation:
  - Replace Bootstrap's default navbar-toggler icon (three horizontal bars) with an animated hamburger that transitions to an "X" when the menu is open.
  - CSS implementation: Three `<span>` bars inside the toggler button, each with `transition: transform 0.3s, opacity 0.3s`. When the menu is open (`.collapsed` class is absent), the top bar rotates 45deg, the middle bar fades out, and the bottom bar rotates -45deg.
  - This is a pure CSS solution — no JavaScript needed. Bootstrap's `aria-expanded` attribute on the toggler button indicates state.
  - Alternative: Use Alpine to toggle a class on the hamburger icon.
- Touch-friendly table rows:
  - Admin tables (product, category, order, coupon list): Rows must be tappable with a finger — minimum touch target 48px height. Use `py-2` or `py-3` on `<td>` elements to add padding.
  - Checkbox targets: The checkbox itself is small (16x16px). Wrap the checkbox in a `<label>` that extends the touch area to at least 44x44px (WCAG minimum).
  - Sortable columns: On mobile, horizontal scrolling tables are acceptable (wrap in `table-responsive`) but each row should have enough vertical padding that tapping the correct row is easy.
- Image aspect-ratio containers (prevent CLS):
  - Product list card images: Use `aspect-ratio: 1 / 1` on the image container (or `16/9` for landscape). Set via CSS: `aspect-ratio: 1; object-fit: cover; width: 100%;`.
  - This prevents the browser from allocating zero height to images while they load, which causes Cumulative Layout Shift (CLS).
  - On product detail: Main image should have `aspect-ratio: 4 / 3` or `1 / 1` depending on the image aspect ratio from uploads.
  - Fallback for browsers that don't support `aspect-ratio` (very old): Use the padding-bottom hack (`padding-bottom: 100%; position: relative; > img { position: absolute; }`).
- Responsive grid audit:
  - Product list grid: At 375px, show 1 column (full-width cards). At 576px, 2 columns. At 992px, 3 columns. At 1400px, 4 columns.
  - Admin dashboard stats: At 375px, each stat card is full-width. At 768px, 2x2 grid. At 992px+, 4 columns.
  - Checkout page: At 375px, order summary collapses below the form (stacks vertically). The sticky sidebar does NOT work on mobile — use `position: static` on `< 768px`.
  - Admin forms: At 375px, form inputs are full-width. The "Save & Edit" / "Save & Create New" buttons should stack vertically, not side-by-side.
  - Auth pages: Card is already centered and constrained to 450px. At 375px, it fills the viewport with 16px padding. Verify.
- Touch-friendly interactive elements:
  - Quantity stepper (+/- buttons): Minimum 44x44px tap target. Currently they may be small `<a>` tags — make them `<button>` elements with `min-width: 44px; min-height: 44px`.
  - Remove buttons (cart, admin): Same tap target requirement.
  - Add to cart button: Full-width on mobile (`w-100`), centered text.
- Viewport testing:
  - Test ALL 31 templates at 375px (iPhone SE), 768px (iPad), 1440px (desktop). Create a checklist and tick off each page.
  - Fix any page that has: horizontal scrollbar, text overflow, overlapping elements, broken grid, misaligned buttons, or touch targets under 44px.
  - Use Chrome DevTools device emulation for testing. On 375px, use the "iPhone SE" preset. On 768px, use "iPad Mini". On 1440px, use the responsive mode set to 1440x900.

### Best Practices

- Use `@media (pointer: coarse)` to detect touch devices and add larger touch targets only on devices that need them. Desktop users see normal-sized controls.
- For the hamburger animation, use `transition: transform 0.3s cubic-bezier(0.68, -0.55, 0.27, 1.55)` for a nice elastic feel.
- CLS prevention via `aspect-ratio` should be applied globally to ALL `<img>` tags that load dynamically (product images, thumbnails). Use a CSS rule: `.product-card img { aspect-ratio: 1; object-fit: cover; }`.
- Use Bootstrap's responsive utility classes (`d-none d-md-block`, `w-100 w-md-auto`, etc.) instead of writing custom media query CSS wherever possible.

### Flaws to Avoid

- Do NOT use `@media (max-width: 576px)` for mobile-specific styles — Bootstrap's breakpoints are `sm=576, md=768, lg=992, xl=1200, xxl=1400`. Use `@include media-breakpoint-down(md)` (Sass mixin) for mobile styles.
- Do NOT disable zoom on mobile (`user-scalable=no`). This is an accessibility violation and prevents users from zooming in on small text or images.
- Do NOT use fixed-width containers on mobile — always use `container-fluid` or `container` with no max-width override on small screens.
- Do NOT test on only one mobile device — iPhone SE (375px), iPhone Pro Max (430px), and Android (360-412px) all have different widths. Test the extreme edges (360px and 430px).
- Do NOT ship a hamburger animation that only works on WebKit — test on Chrome Android, Firefox Android, and Safari iOS.

### Verification / Expected Output

- At 375px (iPhone SE):
  - Product list: 1 column, cards fill width.
  - Navbar: Hamburger visible, tapping it opens menu with smooth animation (bars → X).
  - Admin tables: Horizontal scroll works (table-responsive wraps properly). Rows are at least 48px tall.
  - Cart offcanvas: Fills 85% of screen width (not 400px on a 375px screen).
  - Auth pages: Card fills viewport width with 16px padding on left/right.
  - Checkout: Order summary collapses below the form (no right column on mobile).
  - All touch targets >= 44x44px.
- At 768px (iPad Mini):
  - Product list: 2 columns.
  - Navbar: Hamburger visible (Bootstrap considers < 992px as mobile for the navbar collapse).
  - Admin dashboard: 2x2 stat card grid.
  - No horizontal scrolling except on admin tables (which are wrapped in `table-responsive`).
- At 1440px:
  - Product list: 4 columns.
  - Checkout: Two-column layout (form left, summary right). Summary is sticky.
  - Admin dashboard: 4 stat cards in a row.
- CLS score: Zero on all pages (verified via Lighthouse).
- Hamburger animation: Bars animate smoothly to X on open, and back to bars on close.
- All 31 templates pass the responsive audit checklist.

---

## MILESTONE 20 — Performance & Final Polish (Lazy Images, Font Swap, Vite Prod Hash, Lighthouse 90+)

The final performance optimization pass. Make the store load fast on slow connections, optimize every byte, and achieve a Lighthouse score of 90+ on Performance, 100 on Accessibility, and 100 on Best Practices.

### Implementation

- Lazy-load product images:
  - Add `loading="lazy"` to all product `<img>` tags (product list cards, related products, admin thumbnails).
  - Exception: The "above the fold" product image on product detail page should NOT be lazy — use `loading="eager"` or omit (eager is default).
  - Add `decoding="async"` to all product images for faster decoding.
  - Verify that lazy loading works correctly with the `aspect-ratio` containers from M19 (no layout shift from lazy images).
- Font display strategy:
  - For Google Fonts (Inter), use `display=swap` in the font URL or CSS `@import` to ensure text is visible immediately in a fallback font while the custom font loads.
  - Add `font-display: swap` to any `@font-face` declarations.
  - Preload the Inter font in `<head>` with a `<link rel="preload" as="font" crossorigin>` tag so the browser starts downloading it early.
  - Check: The "swap" strategy prevents invisible text (FOIT — Flash of Invisible Text). Users see the fallback font (system UI font) immediately, then the page swaps to Inter when it loads.
- Vite production build optimization:
  - Configure Vite's `build.rollupOptions.output.manualChunks` to split third-party libraries into a separate chunk (vendors) so they are cached independently.
  - Enable CSS code splitting in Vite (default is on for async chunks) — ensure critical CSS is inlined or loaded early.
  - Configure `build.cssMinify` to `'esbuild'` (default) for fast CSS minification.
  - Configure `build.minify` to `'terser'` for better tree-shaking and smaller JS bundles (terser is slower but produces smaller output than esbuild).
  - Set `build.target` to `'es2015'` for wide browser compatibility (with `@vitejs/plugin-legacy` from M10, this covers all browsers supported by Bootstrap 5).
  - Enable `build.report` to generate a bundle analysis report (`npx vite-bundle-analyzer` or Vite's built-in `--report`).
  - Ensure output filenames use `[name]-[hash]` pattern for long-term caching.
  - Set `build.assetsInlineLimit` to `4096` (4KB) — files under 4KB are inlined as base64 in CSS/JS to reduce HTTP requests.
  - Set `build.chunkSizeWarningLimit` to `250` KB — if any chunk exceeds this, investigate splitting further.
- nginx cache headers:
  - Add `expires` headers for static assets: `location /static/ { expires 1y; add_header Cache-Control "public, immutable"; }`.
  - Since filenames are hashed (Vite handles this), the `immutable` directive tells browsers they never need to revalidate — the hash changes when content changes.
  - Add `add_header Vary "Accept-Encoding"` for compressed assets.
- Lighthouse audit:
  - Run Lighthouse on all critical pages: Product list, Product detail, Cart, Checkout, Admin dashboard, Login, Register.
  - Target scores:
    - Performance: ≥ 90 (on mobile throttling — Slow 4G, 4x CPU slowdown)
    - Accessibility: 100
    - Best Practices: 100
    - SEO: 100
  - Fix any issues flagged by Lighthouse:
    - Render-blocking resources: Inline critical CSS or use `media` attribute on non-critical CSS.
    - Unused CSS: Use PurgeCSS (Vite plugin) to remove unused Bootstrap classes if the bundle is >50KB of CSS.
    - Proper `alt` text on all images.
    - Proper `aria-label` on all interactive elements.
    - Semantic heading hierarchy (h1 → h2 → h3, no skips).
    - Meta description tag on every page.
    - Viewport meta tag (`width=device-width, initial-scale=1`).
    - Proper `lang` attribute on `<html>` (already `lang="en"`).
    - `meta charset="utf-8"` (already present).
    - Links have discernible text (no bare URLs).
- JavaScript optimization:
  - Ensure Alpine.js is loaded with `defer` (not `async`) — DOM must be ready before Alpine initializes.
  - Ensure all third-party libraries (Choices.js, Flatpickr, Notyf, Dropzone, Chart.js) are imported as ES modules and tree-shaken by Vite.
  - Remove any unused imports in `main.js`.
  - Verify that the main JS bundle is under 100KB (gzipped). If over 100KB, investigate code splitting or deferred loading for heavy components (Chart.js, Dropzone).
- Final cleanup:
  - Remove all remaining inline `<script>` tags from templates — replace with Alpine components or move to `main.js`.
  - Remove all remaining CDN script links (Bootstrap Icons CSS CDN is optional — it can be bundled locally or kept as CDN for simplicity).
  - Remove old `static/css/style.css` if it still exists (should have been replaced by `static/dist/assets/style-<hash>.css`).
  - Remove old `static/js/` directory entirely (all JS logic is now in Alpine components or `main.js`).

### Best Practices

- Lighthouse audits must be run on the PRODUCTION build (`npm run build`), not the development build. Dev builds are unminified and include source maps — they do not represent real performance.
- Use Chrome Incognito mode for Lighthouse audits to avoid extension interference.
- Audit on MOBILE (Slow 4G throttling) for the Performance score — this is the more realistic and stricter test.
- For CSS-in-JS or inline styles: Keep critical CSS (above-the-fold styles) under 14KB (the initial TCP congestion window). Use Vite's `critical` plugin or `vite-plugin-critical` if needed.
- For the `immutable` cache directive, ensure Vite hash filenames are truly content-addressed (hash changes when content changes). Vite does this by default with `[hash]`.
- The bundle analysis report (`npm run build -- --report`) should be saved as `docs/bundle-report.html` for future reference.

### Flaws to Avoid

- Do NOT add `loading="lazy"` to the first image on the page (hero image, main product image above the fold). This delays Largest Contentful Paint (LCP).
- Do NOT use `font-display: block` or `font-display: fallback` — `swap` is the best UX choice for a store where text readability is critical.
- Do NOT disable `gzip` or `brotli` compression on nginx for static assets. Verify compression is enabled for JS, CSS, SVG, TTF, WOFF2.
- Do NOT use `Cache-Control: no-cache` on hashed static assets — they should be `public, immutable` with a 1-year expiry. The hash acts as the version.
- Do NOT add all images eagerly loaded just to improve Lighthouse — lazy loading IS the correct pattern. Lighthouse expects lazy loading on below-the-fold images.
- Do NOT sacrifice image quality for performance. Use modern formats (WebP) with `<picture>` element and fallback to JPEG/PNG. The existing system uses PNG/JPEG — consider WebP conversion as a future optimization.

### Verification / Expected Output

- Lighthouse on each critical page:
  - Performance ≥ 90 (mobile)
  - Accessibility: 100
  - Best Practices: 100
  - SEO: 100
- Lighthouse report shows zero opportunities for significant improvement (no render-blocking resources, no unused CSS/JS, properly sized images).
- Network tab: All static assets (JS, CSS, images) have `Cache-Control: public, immutable, max-age=31536000` headers and 200 (from cache) on repeat visits.
- Font loading: Inter font loads via `display=swap`. No FOIT (Flash of Invisible Text) — text is visible immediately in fallback font.
- Bundle size: Main JS bundle (gzipped) < 100KB. CSS bundle (gzipped) < 50KB.
- Image loading: Below-the-fold product images have `loading="lazy"`. The main product image does NOT have `loading="lazy"`.
- `npm run build` produces a report file showing bundle composition and chunk sizes.
- Old `static/js/` directory is deleted (if empty). Old `static/css/` directory is deleted (if empty). All assets are served from `static/dist/`.
- Zero console errors, zero network 404s, zero mixed content warnings.

---

## Frontend Upgrade Summary

| Milestone | Description | Sessions | Depends On | Unblocks |
|-----------|-------------|----------|------------|----------|
| M10 | Build tooling (Vite + Sass + Docker) | 1 | M9 | M11 |
| M11 | Bootstrap theme via Sass | 1 | M10 | M14 |
| M12 | Remove jQuery + rewrite navbar/cart/alerts in Alpine | 2 | M10 | M12.5, M13 |
| M12.5 | Rewrite checkbox/clipboard/validators in Alpine | 1 | M12 | M13 |
| M13 | Choices.js + Flatpickr + Notyf + Dropzone | 1 | M12, M12.5 | M14 |
| M14 | Card layouts + skeletons + spinners + spacing/typography | 2 | M11, M13 | M14.5 |
| M14.5 | Hover transitions + shadows + border-radius consistency | 1 | M14 | M15 |
| M15 | Admin dashboard overhaul (Chart.js + stats + audit log) | 1 | M14.5 | — |
| M16 | Product list UX (filters, sort, search suggestions, pagination) | 1 | M14.5 | — |
| M17 | Auth pages redesign (centered cards, Google button, inline validation) | 0.5 | M14.5 | — |
| M18 | Cart/checkout overhaul (offcanvas, progress steps, Stripe styling) | 1 | M14.5 | M19 |
| M19 | Mobile polish (hamburger animation, touch tables, CLS fixes) | 1 | M15–M18 | M20 |
| M20 | Performance + Lighthouse 90+ (lazy images, font swap, caching) | 1 | M19 | Launch |
| **Total** | | **13.5 sessions** | | |
