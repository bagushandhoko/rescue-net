"""Jejak Audit (2026-10-26): sensitive changes are listed for System Manager
and Control Centre only; secret values are masked."""

import frappe

from rescue_net.api_audit import audit_trail
from rescue_net.tests.factories import RNTestCase, as_guest, as_user, make_actor, make_world


class TestAuditTrail(RNTestCase):
    def setUp(self):
        super().setUp()
        self.w = make_world()
        doc = frappe.get_doc("RN Posko", self.w.posko_a.name)
        doc.title = (doc.title or "Posko") + " (ubah uji)"
        # Frappe skips Version rows under tests unless asked (production records them)
        doc.save(ignore_permissions=True, ignore_version=False)

    def test_system_manager_sees_the_change(self):
        rows = audit_trail(doctype="RN Posko", docname=self.w.posko_a.name)["rows"]
        self.assertTrue(rows)
        self.assertTrue(any(c["field"] == "title" for c in rows[0]["changes"]))
        self.assertEqual(rows[0]["doctype_label"], "Posko")

    def test_posko_operator_and_guest_are_refused(self):
        with as_user(make_actor(posko=self.w.posko_a).user), self.assertRaises(frappe.PermissionError):
            audit_trail()
        with as_guest(), self.assertRaises(frappe.PermissionError):
            audit_trail()

    def test_control_centre_may_read(self):
        cc = make_actor(role="command_center")
        with as_user(cc.user):
            self.assertTrue(audit_trail(doctype="RN Posko")["rows"])

    def test_secret_values_are_masked(self):
        from rescue_net.api_audit import _changes
        out, _ = _changes('{"changed": [["verification_pin", "1234", "5678"], ["title", "a", "b"]]}')
        self.assertEqual(out[0]["old"], "•••")
        self.assertEqual(out[1]["new"], "b")

    def test_unknown_doctype_refused(self):
        with self.assertRaises(frappe.ValidationError):
            audit_trail(doctype="User")
