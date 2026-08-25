import os
import re
import time
import uuid
import secrets
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app_shared import (
    get_conn,
    rows_to_dicts,
    hash_password,
    verify_password,
    hash_token,
    resolve_session_user,
)

router = APIRouter(tags=["auth"])

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Personas selectable at self-registration. command_center is deliberately
# excluded - that privilege is never self-assignable from a public form.
PUBLIC_SELF_REGISTER_ROLES = {
    "viewer", "volunteer", "donor",
}

OPERATOR_REQUEST_ROLES = {
    "posko_operator", "medical_operator", "shelter_operator",
}

SESSION_TTL = timedelta(days=7)
REFRESH_TTL = timedelta(days=30)


# ---------------------------------------------------------------------
# Minimal in-process rate limiter (fixed window). No new dependency /
# framework - resets on process restart, which is acceptable for a P0
# login/register abuse brake. Keyed by client IP + bucket name.
# ---------------------------------------------------------------------
_rate_buckets = defaultdict(deque)


def _check_rate_limit(key: str, limit: int, window_seconds: int):
    now = time.time()
    bucket = _rate_buckets[key]
    while bucket and bucket[0] < now - window_seconds:
        bucket.popleft()
    if len(bucket) >= limit:
        raise HTTPException(status_code=429, detail="Too many attempts, please try again later")
    bucket.append(now)


def _client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _write_audit_event(cur, action: str, actor_user_id: Optional[str], actor_role: Optional[str],
                        object_table: str, object_id: Optional[str], request: Optional[Request] = None):
    cur.execute("""
    INSERT INTO audit_events
    (id, actor_user_id, actor_role, action, object_table, object_id, ip_address, user_agent)
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s);
    """, (
        "audit-" + uuid.uuid4().hex[:12], actor_user_id, actor_role, action, object_table, object_id,
        (request.client.host if request and request.client else None),
        (request.headers.get("user-agent") if request else None),
    ))


def _create_session(cur, user_id: str):
    session_id = "sess-" + uuid.uuid4().hex[:12]
    session_token = "rn-" + uuid.uuid4().hex + secrets.token_hex(8)
    refresh_token = "rnrt-" + secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + SESSION_TTL
    refresh_expires_at = datetime.utcnow() + REFRESH_TTL

    cur.execute("""
    INSERT INTO user_sessions
    (id, user_id, session_token, status, expires_at, refresh_token_hash, refresh_expires_at)
    VALUES (%s,%s,%s,'active',%s,%s,%s)
    RETURNING *;
    """, (session_id, user_id, session_token, expires_at, hash_token(refresh_token), refresh_expires_at))
    session = rows_to_dicts(cur)[0]
    return session, session_token, refresh_token


def _public_user(user: dict) -> dict:
    return {
        "id": user["id"],
        "username": user["username"],
        "display_name": user["display_name"],
        "role": user["role"],
        "requested_role": user.get("requested_role"),
        "role_request_status": user.get("role_request_status"),
        "organization_id": user.get("organization_id"),
        "posko_id": user.get("posko_id"),
        "phone": user.get("phone"),
        "email": user.get("email"),
    }


def _public_session(session: dict) -> dict:
    # Never expose refresh_token_hash (or any other internal credential
    # material) in an API response - only session_token/refresh_token
    # returned at issuance time are meant to leave the server.
    return {
        "id": session["id"],
        "user_id": session["user_id"],
        "status": session["status"],
        "created_at": session["created_at"],
        "expires_at": session["expires_at"],
    }


# ---------------------------------------------------------------------
# Roles catalog (unchanged - live contract)
# ---------------------------------------------------------------------

@router.get("/auth/roles")
def get_auth_roles():
    return {
        "roles": [
            {
                "role": "command_center",
                "label": "Command Center",
                "scope": "all_disaster_event",
                "can_verify": True,
                "can_view_sensitive": True,
            },
            {
                "role": "posko_operator",
                "label": "Posko Operator",
                "scope": "assigned_posko",
                "can_verify": False,
                "can_view_sensitive": False,
            },
            {
                "role": "medical_operator",
                "label": "Medical Operator",
                "scope": "assigned_medical_posko",
                "can_verify": False,
                "can_view_sensitive": True,
            },
            {
                "role": "shelter_operator",
                "label": "Shelter Operator",
                "scope": "assigned_shelter",
                "can_verify": False,
                "can_view_sensitive": False,
            },
            {
                "role": "donor",
                "label": "Donor",
                "scope": "own_programs_and_public_transparency",
                "can_verify": False,
                "can_view_sensitive": False,
            },
            {
                "role": "volunteer",
                "label": "Volunteer",
                "scope": "own_assignment",
                "can_verify": False,
                "can_view_sensitive": False,
            },
            {
                "role": "viewer",
                "label": "Viewer",
                "scope": "public",
                "can_verify": False,
                "can_view_sensitive": False,
            },
        ]
    }


# ---------------------------------------------------------------------
# Real auth
# ---------------------------------------------------------------------

class RegisterRequest(BaseModel):
    full_name: str
    email: str
    phone: str
    password: str
    initial_role: Optional[str] = "viewer"
    kelompok_choice: str = "individual"  # "individual" | an organization id | "new"
    new_organization_name: Optional[str] = None
    new_organization_type: Optional[str] = None
    new_organization_contact: Optional[str] = None


class LoginRequest(BaseModel):
    identifier: str  # email or username
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


def _slugify_username(email: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", email.split("@")[0].lower()).strip("-") or "user"
    return base


@router.post("/auth/register")
def register(payload: RegisterRequest, request: Request):
    _check_rate_limit("register:" + _client_key(request), limit=10, window_seconds=600)

    full_name = payload.full_name.strip()
    email = payload.email.strip().lower()
    phone = payload.phone.strip()
    password = payload.password

    if not full_name:
        raise HTTPException(status_code=400, detail="full_name is required")
    if not EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail="Invalid email address")
    if not phone:
        raise HTTPException(status_code=400, detail="phone is required")
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    requested_initial_role = (payload.initial_role or "viewer").strip()

    if requested_initial_role in PUBLIC_SELF_REGISTER_ROLES:
        effective_role = requested_initial_role
        requested_role = None
        role_request_status = "not_required"
    elif requested_initial_role in OPERATOR_REQUEST_ROLES:
        # Operator roles are NEVER self-granted.
        # Registration records the request but the effective account remains viewer
        # until an authorized approval workflow promotes it.
        effective_role = "viewer"
        requested_role = requested_initial_role
        role_request_status = "pending"
    else:
        effective_role = "viewer"
        requested_role = None
        role_request_status = "none"

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT 1 FROM user_accounts WHERE lower(email) = %s AND deleted_at IS NULL LIMIT 1;", (email,))
        if rows_to_dicts(cur):
            raise HTTPException(status_code=409, detail="An account with this email already exists")

        username = _slugify_username(email)
        cur.execute("SELECT 1 FROM user_accounts WHERE username = %s LIMIT 1;", (username,))
        if rows_to_dicts(cur):
            username = f"{username}-{uuid.uuid4().hex[:6]}"

        user_id = "user-" + uuid.uuid4().hex[:12]
        password_hash = hash_password(password)

        cur.execute("""
        INSERT INTO user_accounts
        (id, username, display_name, phone, email, role, organization_id, posko_id,
         status, password_hash, requested_role, role_request_status)
        VALUES (%s,%s,%s,%s,%s,%s,NULL,NULL,'active',%s,%s,%s)
        RETURNING *;
        """, (
            user_id, username, full_name, phone, email,
            effective_role, password_hash, requested_role, role_request_status
        ))
        user = rows_to_dicts(cur)[0]

        kelompok_choice = (payload.kelompok_choice or "individual").strip()

        if kelompok_choice == "individual":
            pass

        elif kelompok_choice == "new":
            org_name = (payload.new_organization_name or "").strip()
            org_type = (payload.new_organization_type or "").strip()
            if not org_name or not org_type:
                raise HTTPException(status_code=400, detail="new_organization_name and new_organization_type are required")

            org_id = "org-" + uuid.uuid4().hex[:12]
            cur.execute("""
            INSERT INTO organizations
            (id, name, organization_type, trust_level, status, identity_verification_status, contact_person, created_by_user_id)
            VALUES (%s,%s,%s,'unverified','pending','unverified',%s,%s)
            RETURNING *;
            """, (org_id, org_name, org_type, payload.new_organization_contact, user_id))

            membership_id = "orgmem-" + uuid.uuid4().hex[:12]
            cur.execute("""
            INSERT INTO organization_memberships
            (id, user_id, organization_id, membership_role, status, approved_at, approved_by)
            VALUES (%s,%s,%s,'owner','approved',NOW(),%s);
            """, (membership_id, user_id, org_id, user_id))

        else:
            org_id = kelompok_choice
            cur.execute("SELECT id FROM organizations WHERE id = %s AND deleted_at IS NULL LIMIT 1;", (org_id,))
            if not rows_to_dicts(cur):
                raise HTTPException(status_code=400, detail="Selected kelompok does not exist")

            membership_id = "orgmem-" + uuid.uuid4().hex[:12]
            cur.execute("""
            INSERT INTO organization_memberships
            (id, user_id, organization_id, membership_role, status)
            VALUES (%s,%s,%s,'member','pending');
            """, (membership_id, user_id, org_id))

        session, session_token, refresh_token = _create_session(cur, user_id)
        _write_audit_event(cur, "register", user_id, effective_role, "user_accounts", user_id, request)
        conn.commit()

    return {
        "status": "registered",
        "session_token": session_token,
        "refresh_token": refresh_token,
        "user": _public_user(user),
        "session": _public_session(session),
    }


@router.post("/auth/login")
def login(payload: LoginRequest, request: Request):
    rate_key = "login:" + _client_key(request)
    _check_rate_limit(rate_key, limit=10, window_seconds=300)

    identifier = payload.identifier.strip().lower()
    generic_error = HTTPException(status_code=401, detail="Invalid credentials")

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
        SELECT * FROM user_accounts
        WHERE (lower(email) = %s OR username = %s)
          AND status = 'active'
          AND deleted_at IS NULL
        LIMIT 1;
        """, (identifier, identifier))
        rows = rows_to_dicts(cur)

        if not rows:
            raise generic_error

        user = rows[0]

        if user.get("locked_until") and user["locked_until"] > datetime.utcnow():
            _write_audit_event(cur, "login_failure", user["id"], user.get("role"), "user_accounts", user["id"], request)
            conn.commit()
            raise generic_error

        if not user.get("password_hash") or not verify_password(payload.password, user["password_hash"]):
            failed = int(user.get("failed_login_count") or 0) + 1
            locked_until = datetime.utcnow() + timedelta(minutes=15) if failed >= 5 else None
            cur.execute("""
            UPDATE user_accounts SET failed_login_count = %s, locked_until = %s, updated_at = NOW()
            WHERE id = %s;
            """, (failed, locked_until, user["id"]))
            _write_audit_event(cur, "login_failure", user["id"], user.get("role"), "user_accounts", user["id"], request)
            conn.commit()
            raise generic_error

        cur.execute("""
        UPDATE user_accounts
        SET failed_login_count = 0, locked_until = NULL, last_login_at = NOW(), updated_at = NOW()
        WHERE id = %s
        RETURNING *;
        """, (user["id"],))
        user = rows_to_dicts(cur)[0]

        session, session_token, refresh_token = _create_session(cur, user["id"])
        _write_audit_event(cur, "login_success", user["id"], user.get("role"), "user_accounts", user["id"], request)
        conn.commit()

    return {
        "status": "logged_in",
        "session_token": session_token,
        "refresh_token": refresh_token,
        "user": _public_user(user),
        "session": _public_session(session),
    }


@router.post("/auth/refresh")
def refresh(payload: RefreshRequest, request: Request):
    _check_rate_limit("refresh:" + _client_key(request), limit=30, window_seconds=300)

    token_hash = hash_token(payload.refresh_token)

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
        SELECT s.*, u.role AS user_role
        FROM user_sessions s
        JOIN user_accounts u ON u.id = s.user_id
        WHERE s.refresh_token_hash = %s
          AND s.status = 'active'
          AND s.deleted_at IS NULL
          AND u.deleted_at IS NULL
          AND s.refresh_expires_at IS NOT NULL
          AND s.refresh_expires_at > NOW()
        LIMIT 1;
        """, (token_hash,))
        rows = rows_to_dicts(cur)
        if not rows:
            raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

        old_session = rows[0]

        cur.execute("UPDATE user_sessions SET status = 'revoked' WHERE id = %s;", (old_session["id"],))

        cur.execute("SELECT * FROM user_accounts WHERE id = %s AND deleted_at IS NULL LIMIT 1;", (old_session["user_id"],))
        user_rows = rows_to_dicts(cur)
        if not user_rows:
            conn.commit()
            raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
        user = user_rows[0]

        session, session_token, new_refresh_token = _create_session(cur, user["id"])
        conn.commit()

    return {
        "status": "refreshed",
        "session_token": session_token,
        "refresh_token": new_refresh_token,
        "user": _public_user(user),
        "session": _public_session(session),
    }


@router.post("/auth/logout")
def logout(request: Request):
    session_token = request.headers.get("X-RN-Session-Token")
    if not session_token:
        raise HTTPException(status_code=401, detail="Session token required")

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
        UPDATE user_sessions SET status = 'revoked'
        WHERE session_token = %s AND status = 'active'
        RETURNING user_id;
        """, (session_token,))
        rows = rows_to_dicts(cur)
        if rows:
            cur.execute("SELECT role FROM user_accounts WHERE id = %s LIMIT 1;", (rows[0]["user_id"],))
            role_rows = rows_to_dicts(cur)
            _write_audit_event(
                cur, "logout", rows[0]["user_id"],
                role_rows[0]["role"] if role_rows else None,
                "user_sessions", None, request,
            )
        conn.commit()

    return {"status": "logged_out"}


@router.get("/auth/me")
def auth_me_header(request: Request):
    session_token = request.headers.get("X-RN-Session-Token")
    if not session_token:
        raise HTTPException(status_code=401, detail="Session token required")

    row = resolve_session_user(session_token)
    if not row:
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    return {
        "authenticated": True,
        "session_token": row["session_token"],
        "user": _public_user(row),
        "session": {
            "id": row["session_id"],
            "status": row["session_status"],
            "created_at": row["session_created_at"],
            "expires_at": row["expires_at"],
        },
    }


# ---------------------------------------------------------------------
# Legacy demo-login. Disabled by default in production; only usable when
# the deployment explicitly opts in via RN_ALLOW_DEMO_LOGIN=true.
# ---------------------------------------------------------------------

class DemoLoginRequest(BaseModel):
    username: str


def _demo_login_allowed() -> bool:
    return os.getenv("RN_ALLOW_DEMO_LOGIN", "false").lower() in {"1", "true", "yes", "on"}


@router.post("/auth/demo-login")
def demo_login(payload: DemoLoginRequest, request: Request):
    if not _demo_login_allowed():
        raise HTTPException(status_code=403, detail="Demo login is disabled in this environment")

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
        SELECT *
        FROM user_accounts
        WHERE username = %s
          AND status = 'active'
          AND deleted_at IS NULL
        LIMIT 1;
        """, (payload.username,))
        rows = rows_to_dicts(cur)

        if not rows:
            raise HTTPException(status_code=404, detail="User not found")

        user = rows[0]
        session, session_token, refresh_token = _create_session(cur, user["id"])
        _write_audit_event(cur, "demo_login", user["id"], user.get("role"), "user_accounts", user["id"], request)
        conn.commit()

        return {
            "status": "logged_in",
            "session_token": session_token,
            "refresh_token": refresh_token,
            "user": _public_user(user),
            "session": _public_session(session),
        }


@router.get("/auth/me/{session_token}")
def auth_me(session_token: str):
    row = resolve_session_user(session_token)
    if not row:
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    return {
        "authenticated": True,
        "session_token": row["session_token"],
        "user": _public_user(row),
        "session": {
            "id": row["session_id"],
            "status": row["session_status"],
            "created_at": row["session_created_at"],
            "expires_at": row["expires_at"],
        },
    }
