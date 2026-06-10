import os
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
