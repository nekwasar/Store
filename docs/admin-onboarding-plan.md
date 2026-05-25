# Admin Onboarding Flow — Enterprise Implementation Plan

**Part of M3 (Auth Hardening)** — replaces the hardcoded superuser bootstrap in `main.py:26-32`.  
**Priority**: M3.1 (must be done before any other M3 item — the current bootstrap is the only way to create an admin).

---

## Flow Overview

```
Server CLI                     Browser                          MongoDB
----------                     -------                          -------
1. ./scripts/create-setup-token
   → generates crypto token
   → stores in DB with TTL    ─────────────────────────────→   setup_tokens collection
   → prints URL to stdout
   → URL: https://store.com/setup?token=<token>

2.                              Admin opens URL in browser
                                GET /setup?token=<token>
                                → token validated            ─→  setup_tokens (lookup + not expired)
                                → signup form rendered
                                ← username + password fields

3.                              Admin fills form + submits
                                POST /setup
                                body: {token, username, password}
                                → token re-validated         ─→  setup_tokens (atomic consume)
                                → password hashed (bcrypt)
                                → user created                ─→  users collection
                                → token deleted               ─→  setup_tokens (remove)
                                ← 303 redirect to /user/login
                                ← flash: "Account created. Login."

4.                              Admin redirected to login
                                Logs in with credentials
                                → normal JWT flow
                                → /admin dashboard
```

---

## Architecture

### 1. Token Model (`apps/auth/models.py`)

```python
class SetupToken(BaseModel):
    token: str          # SHA-256 hash of random bytes
    created_at: datetime
    expires_at: datetime  # 15 minutes from creation
    used: bool = False
```

**MongoDB collection**: `setup_tokens`  
**TTL index**: `expires_at` expires after 0 seconds (MongoDB auto-deletes expired documents)  
**Storage**: Store SHA-256 hash, not the raw secret. The URL contains the raw secret; the DB stores the hash. Prevents token theft from DB dump.

### 2. CLI Script (`scripts/create-setup-token`)

```python
#!/usr/bin/env python3
"""
Usage: python scripts/create-setup-token [--expires-minutes 15] [--base-url https://store.com]

Generates a one-time admin setup URL. Must be run on the server.
"""
import secrets, hashlib, os, sys, argparse
from datetime import datetime, timedelta, timezone
from pymongo import MongoClient, ASCENDING

# --- Generate cryptographically secure token ---
raw_token = secrets.token_urlsafe(32)       # 43 chars, 192 bits entropy
token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

# --- Store in MongoDB ---
expires = datetime.now(timezone.utc) + timedelta(minutes=15)
client = MongoClient(os.environ['MONGODB_URL'])
db = client[os.environ['MONGODB_DB']]
db.setup_tokens.create_index([("expires_at", ASCENDING)], expireAfterSeconds=0)
db.setup_tokens.insert_one({
    "token_hash": token_hash,
    "created_at": datetime.now(timezone.utc),
    "expires_at": expires,
    "used": False,
})

# --- Print URL ---
base_url = args.base_url.rstrip('/')
print(f"\n  Admin setup URL (expires in {args.expires_minutes} min):\n")
print(f"  {base_url}/setup?token={raw_token}\n")
print(f"  Share this URL only with the intended administrator.\n")
```

### 3. GET `/setup` Route (`apps/auth/routers.py`)

```python
@router.get("/setup")
async def setup_page(request: Request, token: str = Query(...)):
    if not token:
        raise HTTPException(400, "Missing token")

    token_hash = hashlib.sha256(token.encode()).hexdigest()
    stored = await setup_collection.find_one({
        "token_hash": token_hash,
        "used": False,
        "expires_at": {"$gt": datetime.now(timezone.utc)},
    })
    if not stored:
        return templates.TemplateResponse("user/auth/setup.html", {
            "request": request,
            "messages": [Message("Invalid or expired setup token.", "danger")],
            "token": token,   # keep token for resubmission if user refreshes
        })

    return templates.TemplateResponse("user/auth/setup.html", {
        "request": request,
        "token": token,
    })
```

### 4. POST `/setup` Route (`apps/auth/routers.py`)

```python
@router.post("/setup")
async def setup_create(request: Request, token: str = Form(...), username: str = Form(...), password: str = Form(...)):
    # Validate token (again, don't trust client)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    stored = await setup_collection.find_one_and_update(
        {
            "token_hash": token_hash,
            "used": False,
            "expires_at": {"$gt": datetime.now(timezone.utc)},
        },
        {"$set": {"used": True}},   # atomic consume — prevents race
    )
    if not stored:
        return templates.TemplateResponse("user/auth/setup.html", {
            "request": request,
            "messages": [Message("Invalid, expired, or already-used setup token.", "danger")],
        })

    # Validate input
    if len(username) < 3 or len(username) > 32:
        return templates.TemplateResponse("user/auth/setup.html", {
            "request": request,
            "messages": [Message("Username must be 3-32 characters.")],
            "token": token,
        })
    if len(password) < 8:
        return templates.TemplateResponse("user/auth/setup.html", {
            "request": request,
            "messages": [Message("Password must be at least 8 characters.")],
            "token": token,
        })

    # Check for duplicate username
    existing = await user_collection.find_one({"username": username})
    if existing:
        return templates.TemplateResponse("user/auth/setup.html", {
            "request": request,
            "messages": [Message("Username already taken.")],
            "token": token,
        })

    # Create admin user with hashed password
    hashed = hash_password(password)
    await user_collection.insert_one({
        "username": username,
        "password": hashed,
        "created_at": datetime.now(timezone.utc),
        "is_admin": True,
    })

    # Delete consumed token (cleanup)
    await setup_collection.delete_one({"token_hash": token_hash})

    # Redirect to login with success flash
    response = RedirectResponse(url="/user/login", status_code=303)
    response.set_cookie("setup_success", "1")
    return response
```

### 5. Security Properties

| Property | Implementation |
|----------|---------------|
| **Token entropy** | 192 bits (`secrets.token_urlsafe(32)`) |
| **Token in URL** | Raw secret (not hashed). Hash stored in DB. URL has one copy; DB has the other. |
| **Single-use** | `find_one_and_update` with `used: False` → atomic consume. Replay impossible. |
| **Expiration** | 15-minute TTL. MongoDB TTL index auto-deletes expired docs. |
| **Rate limiting** | 5 attempts per IP per 15 minutes on POST `/setup` (add in M3 rate limiting) |
| **No leaked tokens in logs** | Token in query string (not path). GET requests logged by nginx by default — acceptable because token is single-use and short-lived. For extra security: accept token via POST body only (requires JS on setup page). |
| **Brute force resistance** | 192-bit keyspace + 5-attempt rate limit + 15-min expiry. Infeasible. |
| **DB dump resistance** | DB stores SHA-256 hash, not raw token. |

### 6. Template (`templates/user/auth/setup.html`)

```html
{% extends "shop/base.html" %}
{% block title %}Admin Account Setup{% endblock %}
{% block content %}
<div class="container mt-5">
  <div class="row">
    <div class="col-md-6 offset-md-3">
      <div class="card">
        <div class="card-header"><h4>Create Admin Account</h4></div>
        <div class="card-body">
          {% if messages %}
            {% for m in messages %}
              <div class="alert alert-{{ m.tags }}">{{ m }}</div>
            {% endfor %}
          {% endif %}
          <form method="post">
            <input type="hidden" name="token" value="{{ token }}">
            <div class="mb-3">
              <label class="form-label">Username</label>
              <input type="text" name="username" class="form-control"
                     minlength="3" maxlength="32" required autofocus>
            </div>
            <div class="mb-3">
              <label class="form-label">Password</label>
              <input type="password" name="password" class="form-control"
                     minlength="8" required>
            </div>
            <button type="submit" class="btn btn-primary w-100">Create Admin Account</button>
          </form>
        </div>
      </div>
    </div>
  </div>
</div>
{% endblock %}
```

### 7. Login Page — Flash on Successful Setup

On the login page, check for `setup_success` cookie:

```python
@router.get("/login")
async def login(request: Request, ...):
    context = {"request": request, "cart": current_cart}
    if request.cookies.get("setup_success") == "1":
        context["messages"] = [Message("Admin account created. Please log in.", "success")]
        response = templates.TemplateResponse("user/auth/login.html", context)
        response.delete_cookie("setup_success")
        return response
    return templates.TemplateResponse("user/auth/login.html", context)
```

### 8. Removal of Old Bootstrap

Remove from `main.py`:
- The `while True` retry loop (lines 26-32 in current code)
- The `REQUIRED_ENV` entries for `SUPERUSER_USERNAME` and `SUPERUSER_PASSWORD`
- The `user_collection.update_one(upsert=True)` block
- The `from apps.auth.routers import hash_password` import (if only used there)

### 9. Files Changed

| File | Change |
|------|--------|
| `scripts/create-setup-token` | **NEW** — CLI token generator |
| `main.py` | Remove superuser bootstrap block |
| `apps/auth/routers.py` | Add `GET /setup` + `POST /setup` + login flash |
| `apps/auth/models.py` | Add `SetupToken` model |
| `templates/user/auth/setup.html` | **NEW** — signup form |
| `templates/user/auth/login.html` | Add `setup_success` message block |
| `milestone.md` | Add M3.1 entry |

---

## Dependency Chain

This is **M3.1** — it replaces the current bootstrap which is the only way to create the first admin. Once this is implemented:
- The old `main.py` superuser loop is dead code and can be removed
- No hardcoded credentials anywhere
- Admin accounts are created securely via one-time URLs
- Foundation is laid for user registration (M8/G22)
