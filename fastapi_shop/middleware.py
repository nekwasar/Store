import os
import secrets

import jwt
import redis
from fastapi import Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordBearer
from starlette.middleware.base import BaseHTTPMiddleware

from db import db

user_collection = db['user']
oauth2_scheme = OAuth2PasswordBearer(tokenUrl='token')

JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'change-me-in-production')
JWT_ALGORITHM = os.environ.get('ALGORITHM', 'HS256')
if JWT_ALGORITHM not in ('HS256', 'HS384', 'HS512', 'RS256', 'RS384', 'RS512'):
    raise ValueError(f"Unsupported JWT algorithm: {JWT_ALGORITHM}")

# Redis for JWT blacklist
_redis = redis.Redis(
    host=os.environ.get('REDIS_HOST', 'redis'),
    port=int(os.environ.get('REDIS_PORT', '6379')),
    db=int(os.environ.get('REDIS_BLACKLIST_DB', '1')),
    socket_connect_timeout=3,
    socket_timeout=3,
)

ALLOWED_ORIGINS = os.environ.get('ALLOWED_ORIGINS', '').split(',') if os.environ.get('ALLOWED_ORIGINS') else []

# ---------------------------------------------------------------------------
# JWT blacklist
# ---------------------------------------------------------------------------
from typing import Optional, Union


def blacklist_token(jti: str, exp: Optional[Union[int, float]] = None):
    try:
        _redis.setex(f"bl:{jti}", 86400, "1")
        if exp:
            import time
            ttl = max(1, int(exp - time.time()))
            _redis.expire(f"bl:{jti}", ttl)
    except Exception:
        pass


def is_blacklisted(jti: str) -> bool:
    try:
        return bool(_redis.exists(f"bl:{jti}"))
    except Exception:
        return False


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------
def get_user_from_token(token):
    if token is None:
        return None
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        if is_blacklisted(payload.get("jti", "")):
            return None
        return payload.get("sub")
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None


def _same_origin(request: Request) -> bool:
    origin = request.headers.get("origin")
    if not origin:
        referer = request.headers.get("referer", "")
        if not referer:
            return True
        base = f"{request.url.scheme}://{request.url.netloc}"
        return referer.startswith(base)
    netloc = request.url.netloc
    if origin == f"http://{netloc}" or origin == f"https://{netloc}":
        return True
    if origin in ALLOWED_ORIGINS:
        return True
    port = request.url.port
    if port:
        if origin == f"http://localhost:{port}" or origin == f"https://localhost:{port}":
            return True
    if origin in (f"http://{h}" for h in ALLOWED_ORIGINS):
        return True
    if origin in (f"https://{h}" for h in ALLOWED_ORIGINS):
        return True
    return False


# ---------------------------------------------------------------------------
# Admin middleware (auth + CSRF via Origin check + JWT blacklist)
# ---------------------------------------------------------------------------
class AdminMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if request.url.path.startswith("/admin"):
            token = request.cookies.get("token")
            user_subject = get_user_from_token(token)
            if not user_subject:
                return RedirectResponse(url="/user/login")

            if request.method in ("POST", "PUT", "PATCH", "DELETE"):
                if not _same_origin(request):
                    return RedirectResponse(url="/user/login")

        response = await call_next(request)

        # Set CSRF cookie on GET responses for logged-in users
        if (
            request.method == "GET"
            and not request.cookies.get("csrf_token")
            and request.cookies.get("token")
            and not request.url.path.startswith("/static")
        ):
            csrf_token = secrets.token_hex(32)
            response.set_cookie(
                "csrf_token", csrf_token,
                httponly=False, samesite="lax", secure=False,
            )

        return response


# ---------------------------------------------------------------------------
# Security headers middleware
# ---------------------------------------------------------------------------
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response
