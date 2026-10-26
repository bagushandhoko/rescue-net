"""Production WSGI entry for gunicorn (2026-10-26, load test).

`bench serve` (the development server) handled one request at a time: at 50
concurrent visitors the Control Centre took ~15 s. gunicorn runs several
worker processes. This module keeps what `bench serve --site` did: one fixed
site (requests from LAN to :8095 carry an IP Host header) and /assets +
/files served for Desk.

    cd sites && gunicorn ... rescue_net.wsgi:application
"""

import os

import frappe.app as _app

_app._site = os.environ.get("RN_SITE", "osiun.localhost")
_app._sites_path = os.environ.get("SITES_PATH", ".")

application = _app.application_with_statics()
