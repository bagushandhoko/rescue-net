"""Test data factories.

Every test builds its own world with these helpers — never rely on production
or simulation records. All inserts bypass DocType permissions (like the API
code does) and are rolled back by FrappeTestCase after each test.

A typical world:

    w = make_world()            # event + org A (posko A) + org B (posko B)
    op = make_actor(posko=w.posko_a)                 # posko operator of A
    owner = make_actor(org=w.org_a, org_role="owner")  # org A owner
    outsider = make_actor()                          # logged-in, no affiliation
    with as_user(op.user): ...
"""

from contextlib import contextmanager
from unittest import mock

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import now_datetime


class RNTestCase(FrappeTestCase):
    """Base class for every rescue_net test. Several endpoints call
    frappe.db.commit() themselves (fulfill_need, …); inside a test that
    would persist the test's data past its rollback, so commit is a no-op
    here and every test is rolled back on tearDown."""

    def setUp(self):
        super().setUp()
        patcher = mock.patch.object(frappe.db, "commit", lambda *a, **kw: None)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(frappe.db.rollback)
        self.addCleanup(frappe.set_user, "Administrator")


def uid(prefix="t"):
    return f"{prefix}-{frappe.generate_hash(length=8)}"


def _insert(doctype, **fields):
    doc = frappe.get_doc({"doctype": doctype, **fields})
    doc.insert(ignore_permissions=True)
    return doc


def make_event(**fields):
    legacy = fields.pop("legacy_id", None) or uid("event")
    return _insert(
        "RN Disaster Event",
        legacy_id=legacy,
        title=fields.pop("title", f"Test Event {legacy}"),
        **fields,
    )


def make_org(**fields):
    return _insert("RN Organization", title=fields.pop("title", uid("Org")), **fields)


def make_posko(event=None, org=None, **fields):
    return _insert(
        "RN Posko",
        title=fields.pop("title", uid("Posko")),
        disaster_event=event.name if event else None,
        organization=org.name if org else None,
        **fields,
    )


def make_user(email=None, roles=()):
    email = email or f"{uid('user')}@test.rescue-net.local"
    user = frappe.get_doc({
        "doctype": "User",
        "email": email,
        "first_name": email.split("@")[0],
        "send_welcome_email": 0,
        "enabled": 1,
    })
    for role in roles:
        user.append("roles", {"role": role})
    user.insert(ignore_permissions=True)
    return user.name


def make_actor(role="posko_operator", org=None, org_role="member", posko=None,
               assignment_role="operator", user=None, **account_fields):
    """A logged-in Rescue-Net actor: Frappe User + active RN User Account,
    optionally an approved org membership and/or posko assignment.
    Returns frappe._dict(user=, account=)."""
    user = user or make_user()
    account = _insert(
        "RN User Account",
        title=user,
        frappe_user=user,
        email=user,
        role=role,
        status="active",
        **account_fields,
    )
    if org:
        _insert(
            "RN Organization Membership",
            user_account=account.name,
            organization=org.name,
            membership_role=org_role,
            status="approved",
        )
    if posko:
        _insert(
            "RN Posko Assignment",
            user_account=account.name,
            posko=posko.name,
            assignment_role=assignment_role,
            status="approved",
        )
    return frappe._dict(user=user, account=account.name)


def make_world():
    """Event with two organisations, each running one posko."""
    event = make_event()
    org_a = make_org(title=uid("Org A"))
    org_b = make_org(title=uid("Org B"))
    posko_a = make_posko(event, org_a, title=uid("Posko A"))
    posko_b = make_posko(event, org_b, title=uid("Posko B"))
    return frappe._dict(event=event, org_a=org_a, org_b=org_b, posko_a=posko_a, posko_b=posko_b)


def make_transport_space(posko, **fields):
    return _insert(
        "RN Transport Space",
        title=fields.pop("title", uid("Truk")),
        coordination_posko=posko.name,
        provider_name=fields.pop("provider_name", "Truk Uji"),
        transport_status=fields.pop("transport_status", "available"),
        **fields,
    )


def make_medical_case(posko, **fields):
    return _insert(
        "RN Medical Case",
        posko=posko.name,
        patient_code=fields.pop("patient_code", uid("PX")),
        complaint=fields.pop("complaint", "Demam tinggi (data uji)"),
        case_status=fields.pop("case_status", "active"),
        triage_status=fields.pop("triage_status", "yellow"),
        observed_at=now_datetime(),
        **fields,
    )


@contextmanager
def as_user(user):
    """Run the block as `user` ("Guest" for anonymous), then switch back."""
    previous = frappe.session.user
    frappe.set_user(user)
    try:
        yield
    finally:
        frappe.set_user(previous)


def as_guest():
    return as_user("Guest")


def walk(value, path=""):
    """Yield (path, key, item) for every dict key anywhere in a response."""
    if isinstance(value, dict):
        for key, item in value.items():
            yield path, key, item
            yield from walk(item, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for i, item in enumerate(value):
            yield from walk(item, f"{path}[{i}]")


def contains_value(value, needle):
    """True when `needle` appears as (part of) any string anywhere in `value`."""
    if isinstance(value, str):
        return needle in value
    if isinstance(value, dict):
        return any(contains_value(v, needle) for v in value.values())
    if isinstance(value, (list, tuple)):
        return any(contains_value(v, needle) for v in value)
    return False



def api_call(cmd, **kwargs):
    """Call a whitelisted method the way /api/method/<cmd> does — resolve it,
    apply Frappe's own whitelist / allow_guest check for the current session
    user, then call it with the form arguments (frappe.handler.execute_cmd
    minus the HTTP-verb check, which needs a live request)."""
    frappe.local.form_dict = frappe._dict(kwargs)
    method = frappe.get_attr(frappe.override_whitelisted_method(cmd))
    frappe.is_whitelisted(method)
    return frappe.call(method, **frappe.local.form_dict)


def known_bug(bug_id):
    """Mark a test that documents a CONFIRMED, owner-reported bug that is not
    fixed yet. Stricter than unittest.expectedFailure:
      - the assertion failing (the bug) → reported as a skip "KNOWN <bug_id>";
      - any other exception → a normal test error (a broken test is not hidden);
      - the test passing → FAILS, telling you to remove the marker."""
    import functools
    import unittest

    def deco(fn):
        @functools.wraps(fn)
        def wrapper(self, *args, **kwargs):
            try:
                fn(self, *args, **kwargs)
            except AssertionError as e:
                raise unittest.SkipTest(f"KNOWN {bug_id}: {str(e)[:120]}")
            raise AssertionError(f"{bug_id} looks fixed — remove @known_bug from {fn.__name__}")

        return wrapper

    return deco
