import hashlib
import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Annotated

import bcrypt
import jwt
from fastapi import APIRouter, Form, HTTPException, Query, Request, Depends
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from authlib.integrations.starlette_client import OAuth

from apps.auth.models import User
from apps.cart.cart import CartManager
from apps.cart.routers import get_current_cart
from celery_tasks import send_verification_email, send_password_reset_email
from db import db
from dependencies import templates, limiter
from utils import Message

router = APIRouter()

user_collection = db['user']
setup_collection = db['setup_tokens']
verification_collection = db['verification_tokens']
reset_collection = db['reset_tokens']

JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'change-me-in-production')
JWT_ALGORITHM = os.environ.get('ALGORITHM', 'HS256')
if JWT_ALGORITHM not in ('HS256', 'HS384', 'HS512', 'RS256', 'RS384', 'RS512'):
    raise ValueError(f"Unsupported JWT algorithm: {JWT_ALGORITHM}")

JWT_EXPIRE_MINUTES = int(os.environ.get('JWT_EXPIRE_MINUTES', '60'))

oauth = OAuth()
oauth.register(
    name='google',
    client_id=os.environ.get('GOOGLE_CLIENT_ID', ''),
    client_secret=os.environ.get('GOOGLE_CLIENT_SECRET', ''),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'},
)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))


def create_jwt(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    to_encode.setdefault("jti", secrets.token_hex(16))
    to_encode.setdefault("iat", datetime.now(timezone.utc))
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRE_MINUTES)
    to_encode["exp"] = expire
    return jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_jwt(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None


async def get_user_by_login(login: str):
    user = await user_collection.find_one({"username": login})
    if not user:
        user = await user_collection.find_one({"email": login})
    if user:
        return User(**user)
    return None


async def get_user_by_email(email: str):
    user = await user_collection.find_one({"email": email})
    if user:
        return User(**user)
    return None


def generate_csrf_token() -> str:
    return secrets.token_hex(32)


def _set_auth_cookies(response, username: str):
    token = create_jwt({"sub": username})
    csrf_token = generate_csrf_token()
    response.set_cookie("token", token, httponly=True, samesite="lax", secure=False)
    response.set_cookie("csrf_token", csrf_token, httponly=False, samesite="lax", secure=False)
    return response


# ---------------------------------------------------------------------------
# LOGIN / LOGOUT
# ---------------------------------------------------------------------------
@router.get("/login")
async def login_page(request: Request, current_cart: CartManager = Depends(get_current_cart)):
    google_enabled = bool(os.environ.get('GOOGLE_CLIENT_ID'))
    next_url = request.query_params.get("next", "")
    if next_url and not next_url.startswith("/"):
        next_url = ""
    context = {"request": request, "cart": current_cart, "google_enabled": google_enabled}
    if next_url:
        context["next"] = next_url
    if request.cookies.get("setup_success") == "1":
        context["messages"] = [Message("Admin account created. Please log in.", "success")]
    if request.cookies.get("registered") == "1":
        context["messages"] = [Message("Account created. Please log in.", "success")]
    if request.cookies.get("password_reset") == "1":
        context["messages"] = [Message("Password reset successfully. Please log in.", "success")]
    response = templates.TemplateResponse("user/auth/login.html", context)
    if request.cookies.get("setup_success") == "1":
        response.delete_cookie("setup_success")
    if request.cookies.get("registered") == "1":
        response.delete_cookie("registered")
    if request.cookies.get("password_reset") == "1":
        response.delete_cookie("password_reset")
    return response


@router.post("/login")
@limiter.limit("10/minute")
async def login(
    request: Request,
    user_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    current_cart: CartManager = Depends(get_current_cart),
):
    user = await get_user_by_login(user_data.username)
    if user is None or not verify_password(user_data.password, user.password):
        google_enabled = bool(os.environ.get('GOOGLE_CLIENT_ID'))
        return templates.TemplateResponse(
            "user/auth/login.html",
            {"request": request, "cart": current_cart, "google_enabled": google_enabled,
             "messages": [Message("Invalid email/username or password")]},
            status_code=200,
        )
    user_doc = await user_collection.find_one({"username": user.username})
    if user_doc and not user_doc.get("verified") and not user_doc.get("is_admin"):
        google_enabled = bool(os.environ.get('GOOGLE_CLIENT_ID'))
        return templates.TemplateResponse(
            "user/auth/login.html",
            {"request": request, "cart": current_cart, "google_enabled": google_enabled,
             "messages": [Message("Please verify your email before logging in. Check your inbox.", "warning")]},
            status_code=200,
        )
    next_url = request.query_params.get("next", "/admin")
    if not next_url.startswith("/"):
        next_url = "/admin"
    response = RedirectResponse(url=next_url, status_code=303)
    return _set_auth_cookies(response, user.username)


@router.get("/login/google")
async def login_google(request: Request):
    redirect_uri = str(request.url_for('google_callback'))
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/login/google/callback")
async def google_callback(request: Request):
    try:
        token = await oauth.google.authorize_access_token(request)
    except Exception:
        return RedirectResponse(url="/user/login?error=oauth_failed", status_code=303)

    user_info = token.get('userinfo')
    if not user_info:
        return RedirectResponse(url="/user/login?error=no_userinfo", status_code=303)

    email = user_info.get('email')
    name = user_info.get('name', email.split('@')[0] if email else 'user')
    google_id = user_info.get('sub')

    if not email:
        return RedirectResponse(url="/user/login?error=no_email", status_code=303)

    user = await get_user_by_email(email)
    if not user:
        username = email.split('@')[0]
        existing = await user_collection.find_one({"username": username})
        if existing:
            username = f"{username}_{secrets.token_hex(4)}"
        await user_collection.insert_one({
            "username": username,
            "email": email,
            "password": "",
            "oauth_provider": "google",
            "oauth_id": google_id,
            "created_at": datetime.now(timezone.utc),
            "verified": True,
        })

    response = RedirectResponse(url="/admin", status_code=303)
    return _set_auth_cookies(response, user.username if user else username)


@router.get("/logout")
async def logout(request: Request):
    token = request.cookies.get("token")
    response = RedirectResponse(url="/product", status_code=303)
    response.delete_cookie("token")
    response.delete_cookie("csrf_token")
    if token:
        payload = decode_jwt(token)
        if payload and "jti" in payload:
            from middleware import blacklist_token
            blacklist_token(payload["jti"], payload.get("exp"))
    return response


@router.post("/refresh")
async def refresh_token(request: Request):
    token = request.cookies.get("token")
    if not token:
        raise HTTPException(status_code=401, detail="No token provided")
    payload = decode_jwt(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    response = JSONResponse({"status": "ok"})
    return _set_auth_cookies(response, payload["sub"])


# ---------------------------------------------------------------------------
# REGISTRATION
# ---------------------------------------------------------------------------
@router.get("/register")
async def register_page(request: Request):
    google_enabled = bool(os.environ.get('GOOGLE_CLIENT_ID'))
    return templates.TemplateResponse("user/auth/register.html", {"request": request, "google_enabled": google_enabled})


@router.post("/register")
@limiter.limit("5/hour")
async def register_action(request: Request):
    form = await request.form()
    username = form.get("username", "")
    email = form.get("email", "")
    password = form.get("password", "")
    errors = []
    if not username or len(username) < 3 or len(username) > 32:
        errors.append("Username must be 3-32 characters.")
    if not email or "@" not in email or len(email) < 5:
        errors.append("Please provide a valid email address.")
    if not password or len(password) < 8:
        errors.append("Password must be at least 8 characters.")
    if await user_collection.find_one({"username": username}):
        errors.append("Username already taken.")
    if await user_collection.find_one({"email": email}):
        errors.append("Email already registered.")
    if errors:
        return templates.TemplateResponse("user/auth/register.html", {
            "request": request, "messages": [Message(e) for e in errors],
        })
    hashed = hash_password(password)
    await user_collection.insert_one({
        "username": username, "email": email, "password": hashed,
        "created_at": datetime.now(timezone.utc), "verified": False,
    })
    token = secrets.token_urlsafe(48)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    await verification_collection.insert_one({
        "email": email,
        "token_hash": token_hash,
        "expires_at": datetime.now(timezone.utc) + timedelta(hours=24),
        "used": False,
    })
    base_url = f"{request.url.scheme}://{request.url.netloc}"
    send_verification_email.delay(email, token, base_url)
    return templates.TemplateResponse("user/auth/verify_sent.html", {
        "request": request, "email": email,
    })


# ---------------------------------------------------------------------------
# ADMIN SETUP
# ---------------------------------------------------------------------------
@router.get("/setup")
async def setup_page(request: Request, token: str = Query(default="")):
    if not token:
        return templates.TemplateResponse("user/auth/setup.html", {
            "request": request, "token": None,
            "messages": [Message("No setup token provided.", "warning")],
        })
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    stored = await setup_collection.find_one({
        "token_hash": token_hash, "used": False,
        "expires_at": {"$gt": datetime.now(timezone.utc)},
    })
    if not stored:
        return templates.TemplateResponse("user/auth/setup.html", {
            "request": request, "token": None,
            "messages": [Message("Invalid, expired, or already-used setup token.", "danger")],
        })
    return templates.TemplateResponse("user/auth/setup.html", {"request": request, "token": token})


@router.post("/setup")
async def setup_create(
    request: Request,
    token: str = Form(...),
    username: str = Form(...),
    email: str = Form(default=""),
    password: str = Form(...),
):
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    stored = await setup_collection.find_one_and_update(
        {"token_hash": token_hash, "used": False, "expires_at": {"$gt": datetime.now(timezone.utc)}},
        {"$set": {"used": True}},
    )
    if not stored:
        return templates.TemplateResponse("user/auth/setup.html", {
            "request": request, "token": None,
            "messages": [Message("Invalid, expired, or already-used setup token.", "danger")],
        })
    errors = []
    if len(username) < 3 or len(username) > 32:
        errors.append("Username must be 3-32 characters.")
    if len(password) < 8:
        errors.append("Password must be at least 8 characters.")
    if errors:
        return templates.TemplateResponse("user/auth/setup.html", {
            "request": request, "token": token, "messages": [Message(e) for e in errors],
        })
    if await user_collection.find_one({"username": username}):
        return templates.TemplateResponse("user/auth/setup.html", {
            "request": request, "token": token, "messages": [Message("Username already taken.")],
        })
    await user_collection.insert_one({
        "username": username, "email": email or None, "password": hash_password(password),
        "created_at": datetime.now(timezone.utc), "is_admin": True,
    })
    await setup_collection.delete_one({"token_hash": token_hash})
    response = RedirectResponse(url="/user/login", status_code=303)
    response.set_cookie("setup_success", "1")
    return response


# ---------------------------------------------------------------------------
# EMAIL VERIFICATION
# ---------------------------------------------------------------------------
@router.get("/verify")
async def verify_email(request: Request, token: str = Query(default="")):
    if not token:
        return templates.TemplateResponse("user/auth/verify_result.html", {
            "request": request,
            "success": False,
            "message": "No verification token provided.",
        })
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    stored = await verification_collection.find_one({
        "token_hash": token_hash, "used": False,
        "expires_at": {"$gt": datetime.now(timezone.utc)},
    })
    if not stored:
        return templates.TemplateResponse("user/auth/verify_result.html", {
            "request": request,
            "success": False,
            "message": "Invalid, expired, or already-used verification token.",
        })
    email = stored["email"]
    await user_collection.update_one(
        {"email": email},
        {"$set": {"verified": True, "updated_at": datetime.now(timezone.utc)}},
    )
    await verification_collection.update_one(
        {"_id": stored["_id"]},
        {"$set": {"used": True}},
    )
    return templates.TemplateResponse("user/auth/verify_result.html", {
        "request": request,
        "success": True,
        "message": "Email verified successfully! You can now log in.",
    })


@router.post("/resend-verification")
@limiter.limit("3/hour")
async def resend_verification(request: Request, email: str = Form(...)):
    user = await user_collection.find_one({"email": email})
    if not user:
        return JSONResponse({"status": "error", "message": "Email not found."}, status_code=404)
    if user.get("verified"):
        return JSONResponse({"status": "ok", "message": "Email already verified."})
    token = secrets.token_urlsafe(48)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    await verification_collection.insert_one({
        "email": email,
        "token_hash": token_hash,
        "expires_at": datetime.now(timezone.utc) + timedelta(hours=24),
        "used": False,
    })
    base_url = f"{request.url.scheme}://{request.url.netloc}"
    send_verification_email.delay(email, token, base_url)
    return JSONResponse({"status": "ok", "message": "Verification email sent."})


# ---------------------------------------------------------------------------
# PASSWORD RESET
# ---------------------------------------------------------------------------
@router.get("/forgot-password")
async def forgot_password_page(request: Request):
    return templates.TemplateResponse("user/auth/forgot_password.html", {"request": request})


@router.post("/forgot-password")
@limiter.limit("3/hour")
async def forgot_password_action(request: Request, email: str = Form(...)):
    user = await user_collection.find_one({"email": email})
    if not user:
        return templates.TemplateResponse("user/auth/forgot_password.html", {
            "request": request,
            "messages": [Message("If that email is registered, a reset link has been sent.", "info")],
        })
    token = secrets.token_urlsafe(48)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    await reset_collection.insert_one({
        "email": email,
        "token_hash": token_hash,
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=15),
        "used": False,
    })
    base_url = f"{request.url.scheme}://{request.url.netloc}"
    send_password_reset_email.delay(email, token, base_url)
    return templates.TemplateResponse("user/auth/forgot_password.html", {
        "request": request,
        "messages": [Message("If that email is registered, a reset link has been sent.", "info")],
    })


@router.get("/reset-password")
async def reset_password_page(request: Request, token: str = Query(default="")):
    if not token:
        return templates.TemplateResponse("user/auth/reset_password.html", {
            "request": request, "token": None,
            "messages": [Message("No reset token provided.", "warning")],
        })
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    stored = await reset_collection.find_one({
        "token_hash": token_hash, "used": False,
        "expires_at": {"$gt": datetime.now(timezone.utc)},
    })
    if not stored:
        return templates.TemplateResponse("user/auth/reset_password.html", {
            "request": request, "token": None,
            "messages": [Message("Invalid, expired, or already-used reset token.", "danger")],
        })
    return templates.TemplateResponse("user/auth/reset_password.html", {
        "request": request, "token": token,
    })


@router.post("/reset-password")
@limiter.limit("5/hour")
async def reset_password_action(
    request: Request,
    token: str = Form(...),
    password: str = Form(...),
    confirm: str = Form(...),
):
    if password != confirm:
        return templates.TemplateResponse("user/auth/reset_password.html", {
            "request": request, "token": token,
            "messages": [Message("Passwords do not match.")],
        })
    if len(password) < 8:
        return templates.TemplateResponse("user/auth/reset_password.html", {
            "request": request, "token": token,
            "messages": [Message("Password must be at least 8 characters.")],
        })
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    stored = await reset_collection.find_one_and_update(
        {"token_hash": token_hash, "used": False, "expires_at": {"$gt": datetime.now(timezone.utc)}},
        {"$set": {"used": True}},
    )
    if not stored:
        return templates.TemplateResponse("user/auth/reset_password.html", {
            "request": request, "token": None,
            "messages": [Message("Invalid, expired, or already-used reset token.", "danger")],
        })
    await user_collection.update_one(
        {"email": stored["email"]},
        {"$set": {"password": hash_password(password), "updated_at": datetime.now(timezone.utc)}},
    )
    await reset_collection.delete_one({"_id": stored["_id"]})
    response = RedirectResponse(url="/user/login", status_code=303)
    response.set_cookie("password_reset", "1")
    return response


@router.get("/csrf-token")
async def get_csrf_token(request: Request):
    csrf_token = request.cookies.get("csrf_token") or generate_csrf_token()
    if not request.cookies.get("csrf_token"):
        response = JSONResponse({"csrf_token": csrf_token})
        response.set_cookie("csrf_token", csrf_token, httponly=False, samesite="lax", secure=False)
        return response
    return JSONResponse({"csrf_token": csrf_token})
