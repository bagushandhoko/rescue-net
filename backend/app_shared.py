import os
import hashlib
import hmac
import psycopg
from cryptography.fernet import Fernet
from fastapi import HTTPException

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://rescuenet_user@localhost:5432/rescuenet_db"
)

def get_conn():
    return psycopg.connect(DATABASE_URL)

def rows_to_dicts(cur):
    columns = [desc[0] for desc in cur.description]
    return [dict(zip(columns, row)) for row in cur.fetchall()]


PASSWORD_SCRYPT_N = 16384
PASSWORD_SCRYPT_R = 8
PASSWORD_SCRYPT_P = 1


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.scrypt(
        password.encode("utf-8"), salt=salt,
        n=PASSWORD_SCRYPT_N, r=PASSWORD_SCRYPT_R, p=PASSWORD_SCRYPT_P, dklen=32,
    )
    return f"scrypt${PASSWORD_SCRYPT_N}${PASSWORD_SCRYPT_R}${PASSWORD_SCRYPT_P}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    if not stored:
        return False
    try:
        algo, n, r, p, salt_hex, hash_hex = stored.split("$")
        if algo != "scrypt":
            return False
        expected = bytes.fromhex(hash_hex)
        dk = hashlib.scrypt(
            password.encode("utf-8"), salt=bytes.fromhex(salt_hex),
            n=int(n), r=int(r), p=int(p), dklen=len(expected),
        )
        return hmac.compare_digest(dk, expected)
    except (ValueError, TypeError):
        return False


def hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def resolve_session_user(session_token: str):
    """Look up an active, non-expired session and its user from the DB.

    This is the single source of truth for "who is making this request" -
    callers must never trust a client-supplied role header instead.
    """
    if not session_token:
        return None
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
        SELECT
          s.id AS session_id,
          s.session_token,
          s.status AS session_status,
          s.created_at AS session_created_at,
          s.expires_at,
          u.*
        FROM user_sessions s
        JOIN user_accounts u ON u.id = s.user_id
        WHERE s.session_token = %s
          AND s.status = 'active'
          AND s.deleted_at IS NULL
          AND u.deleted_at IS NULL
          AND (s.expires_at IS NULL OR s.expires_at > NOW())
        LIMIT 1;
        """, (session_token,))
        rows = rows_to_dicts(cur)
        return rows[0] if rows else None

def get_ai_key_fernet():
    secret = os.getenv("AI_KEY_ENCRYPTION_SECRET")
    if not secret:
        raise HTTPException(
            status_code=500,
            detail="AI key encryption secret is not configured"
        )
    return Fernet(secret.encode())

def encrypt_ai_key(api_key: str) -> str:
    return get_ai_key_fernet().encrypt(api_key.encode()).decode()

def decrypt_ai_key(encrypted_api_key: str) -> str:
    return get_ai_key_fernet().decrypt(encrypted_api_key.encode()).decode()
