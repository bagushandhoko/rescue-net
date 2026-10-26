"""Short shared cache for guest-only public feeds.

Load test 2026-10-26 (S10): public API capacity topped out near 53 req/s with
CPU full; the three heaviest guest feeds are identical for every guest, so a
guest gets a copy at most `ttl` seconds old. Logged-in users and tests always
get a fresh build."""

import functools
import hashlib
import json

import frappe


def guest_cache(ttl=30):
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            if frappe.session.user != "Guest" or frappe.flags.in_test:
                return fn(*args, **kwargs)
            raw = json.dumps([args, kwargs], sort_keys=True, default=str)
            key = "rn_guest:%s.%s:%s" % (fn.__module__, fn.__name__, hashlib.sha1(raw.encode()).hexdigest()[:16])
            hit = frappe.cache().get_value(key)
            if hit is not None:
                return hit
            out = fn(*args, **kwargs)
            frappe.cache().set_value(key, out, expires_in_sec=ttl)
            return out
        return wrapper
    return deco
