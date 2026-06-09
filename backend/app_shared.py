"""
Shared helpers for Rescue-Net API modules.

Initial refactor stage:
- main.py still owns runtime app and routes.
- route modules will gradually import shared helpers from here.
"""

# This file is intentionally minimal for now.
# Next stage will move:
# - get_conn
# - rows_to_dicts
# - AI encryption helpers
