import os

from pymongo import ASCENDING, DESCENDING
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response

from apps.auth.routers import router as auth_router
from apps.cart.routers import router as cart_router
from apps.category.routers import router as cat_router
from apps.order.routers import router as order_router
from apps.payment.routers import router as payment_router
from apps.product.routers import router as product_router
from apps.coupons.routers import router as coupon_router
from apps.admin.routers import router as admin_router
from dependencies import limiter
from logger import get_logger
from middleware import AdminMiddleware, SecurityHeadersMiddleware
from dotenv import load_dotenv
from db import db, client as mongo_client

_log = get_logger("main")

# Prometheus metrics
REQUEST_COUNT = Counter("http_requests_total", "Total HTTP requests", ["method", "endpoint", "status"])
REQUEST_LATENCY = Histogram("http_request_duration_seconds", "HTTP request latency", ["method", "endpoint"])

# ---------------------------------------------------------------------------
load_dotenv()
# Env var validation with safe defaults
# ---------------------------------------------------------------------------
REQUIRED_ENV = {
    'JWT_SECRET_KEY': 'change-me-in-production',
    'ALGORITHM': 'HS256',
    'MONGODB_URL': 'mongodb://mongo:27017',
    'MONGODB_DB': 'fastapi_shop',
}
for key, default in REQUIRED_ENV.items():
    if key not in os.environ:
        os.environ[key] = default

if os.environ['ALGORITHM'] not in ('HS256', 'HS384', 'HS512', 'RS256', 'RS384', 'RS512'):
    raise ValueError(f"Unsupported JWT algorithm: {os.environ['ALGORITHM']}")

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(title="fastapi_shop", version="1.0.0")

# Rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.on_event("startup")
async def create_indexes():
    user_collection = db['user']
    await user_collection.create_index([("username", ASCENDING)], unique=True)
    await db['category'].create_index([("name", ASCENDING)])
    await db['category'].create_index([("slug", ASCENDING)], unique=True)
    await db['product'].create_index([("name", ASCENDING)])
    await db['product'].create_index([("slug", ASCENDING)])
    await db['product'].create_index([("category_id", ASCENDING)])
    await db['order'].create_index([("created", DESCENDING)])
    await db['coupon'].create_index([("code", ASCENDING)], unique=True)
    await db['product'].create_index([("name", "text"), ("description", "text")], default_language="english")
    await db['verification_tokens'].create_index("token_hash", unique=True)
    await db['verification_tokens'].create_index("expires_at", expireAfterSeconds=0)
    await db['reset_tokens'].create_index("token_hash", unique=True)
    await db['reset_tokens'].create_index("expires_at", expireAfterSeconds=0)


@app.on_event("shutdown")
async def shutdown_event():
    mongo_client.close()


app.mount("/static", StaticFiles(directory="static"), name="static")

# ---------------------------------------------------------------------------
# CORS — restricted to configured origins
# ---------------------------------------------------------------------------
_cors_origins = os.environ.get('CORS_ORIGINS', 'http://localhost,http://localhost:8080')
origins = [o.strip() for o in _cors_origins.split(',') if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-CSRF-Token"],
)

# ---------------------------------------------------------------------------
# Security headers (innermost → runs last on response, first to set headers)
# ---------------------------------------------------------------------------
app.add_middleware(SecurityHeadersMiddleware)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(cat_router, tags=["Category"], prefix="/category")
app.include_router(product_router, tags=["Product"], prefix="/product")
app.include_router(cart_router, tags=["Cart"], prefix="/cart")
app.include_router(order_router, tags=["Order"], prefix="/order")
app.include_router(payment_router, tags=["Payment"], prefix="/payment")
app.include_router(auth_router, tags=["Auth"], prefix="/user")
app.include_router(coupon_router, tags=["Coupon"], prefix="/coupon")
app.include_router(admin_router, tags=["Admin"], prefix="/admin")

# ---------------------------------------------------------------------------
# Admin auth + CSRF middleware (outermost — runs first on request)
# ---------------------------------------------------------------------------
app.add_middleware(AdminMiddleware)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    errors = exc.errors()
    if not errors:
        return JSONResponse(status_code=422, content={"detail": "Validation error"})
    if 'email' in errors[0]['loc']:
        error_msg = errors[0]['ctx']['reason']
        response = RedirectResponse(url=request.url, status_code=303)
        response.set_cookie('error_msg', error_msg)
        return response
    detail = errors[0].get('msg', 'Validation error')
    return JSONResponse(status_code=422, content={"detail": detail})


@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/product", status_code=303)


@app.get("/health", include_in_schema=False)
async def health():
    status = {"status": "ok"}
    try:
        await db.command("ping")
        status["mongodb"] = "ok"
    except Exception:
        status["mongodb"] = "error"
        status["status"] = "degraded"
    try:
        from recommender import _redis
        await _redis.ping()
        status["redis"] = "ok"
    except Exception:
        status["redis"] = "error"
        status["status"] = "degraded"
    return JSONResponse(status)


@app.get("/metrics", include_in_schema=False)
async def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
