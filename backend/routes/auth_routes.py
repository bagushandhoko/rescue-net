from datetime import datetime
from typing import Optional
import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app_shared import get_conn, rows_to_dicts

router = APIRouter(tags=["auth"])

class DemoLoginRequest(BaseModel):
    username: str

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

@router.post("/auth/demo-login")
def demo_login(payload: DemoLoginRequest):
    session_id = "sess-" + uuid.uuid4().hex[:12]
    token = "rn-demo-" + uuid.uuid4().hex

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

        cur.execute("""
        INSERT INTO user_sessions
        (id, user_id, session_token, status, expires_at)
        VALUES
        (%s,%s,%s,'active', NOW() + INTERVAL '7 days')
        RETURNING *;
        """, (session_id, user["id"], token))
        session = rows_to_dicts(cur)[0]

        conn.commit()

        return {
            "status": "logged_in",
            "session_token": token,
            "user": {
                "id": user["id"],
                "username": user["username"],
                "display_name": user["display_name"],
                "role": user["role"],
                "organization_id": user.get("organization_id"),
                "posko_id": user.get("posko_id"),
                "phone": user.get("phone"),
                "email": user.get("email"),
            },
            "session": session,
        }

@router.get("/auth/me/{session_token}")
def auth_me(session_token: str):
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

        if not rows:
            raise HTTPException(status_code=401, detail="Invalid or expired session")

        row = rows[0]

        return {
            "authenticated": True,
            "session_token": row["session_token"],
            "user": {
                "id": row["id"],
                "username": row["username"],
                "display_name": row["display_name"],
                "role": row["role"],
                "organization_id": row.get("organization_id"),
                "posko_id": row.get("posko_id"),
                "phone": row.get("phone"),
                "email": row.get("email"),
            },
            "session": {
                "id": row["session_id"],
                "status": row["session_status"],
                "created_at": row["session_created_at"],
                "expires_at": row["expires_at"],
            },
        }
