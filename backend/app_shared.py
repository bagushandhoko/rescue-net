"""
Shared helpers for Rescue-Net API modules.

Prepared for gradual backend refactor.
Current runtime still uses main.py routes.
Future route modules can import these helpers.
"""

import os
import psycopg

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://rescuenet_user:CHANGE_ME@localhost:5432/rescuenet_db"
)

def get_conn():
    return psycopg.connect(DATABASE_URL)

def rows_to_dicts(cur):
    columns = [desc[0] for desc in cur.description]
    return [dict(zip(columns, row)) for row in cur.fetchall()]
