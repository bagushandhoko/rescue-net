"""Kode lacak acak (QR): Flow baru dapat token, kode lama tetap berlaku, token tidak bisa ditebak dari nama."""

import frappe

from rescue_net import api_logistics as api
from rescue_net.control_centre import distribusi as dist
from rescue_net.services.trace import ALPHABET, LENGTH
from rescue_net.tests.factories import RNTestCase, as_guest, as_user, make_actor, make_world


class TestTraceToken(RNTestCase):
    def setUp(self):
        super().setUp()
        self.w = make_world()
        self.op = make_actor(posko=self.w.posko_a)
        with as_user(self.op.user):
            self.flow = api.create_flow(self.w.posko_a.name, "Beras 5 kg", quantity=10, unit="karung")["flow"]

    def token(self):
        return frappe.db.get_value("RN Distribution Flow", self.flow, "trace_token")

    def test_new_flow_gets_random_token(self):
        t = self.token()
        self.assertEqual(len(t), LENGTH)
        self.assertTrue(all(c in ALPHABET for c in t))
        self.assertNotEqual(t, self.flow[-8:].upper())

    def test_trace_code_uses_token_and_resolves(self):
        code = dist._distribusi_trace(self.flow)
        self.assertEqual(code, "RN-" + self.token())
        self.assertEqual(dist._resolve_flow_by_trace(code), self.flow)
        self.assertEqual(dist._resolve_flow_by_trace(self.token().lower()), self.flow)

    def test_legacy_label_still_resolves(self):
        self.assertEqual(dist._resolve_flow_by_trace("RN-" + self.flow[-8:].upper()), self.flow)

    def test_guest_flow_trace_by_token_and_unknown_code(self):
        with as_guest():
            res = dist.flow_trace(trace="RN-" + self.token())
            self.assertEqual(res["flow"], self.flow)
            self.assertEqual(res["trace"], "RN-" + self.token())
            with self.assertRaises(frappe.DoesNotExistError):
                dist.flow_trace(trace="RN-ZZZZZZZZ")

    def test_untokened_flow_falls_back_to_legacy_code(self):
        frappe.db.set_value("RN Distribution Flow", self.flow, "trace_token", None)
        self.assertEqual(dist._distribusi_trace(self.flow), "RN-" + self.flow[-8:].upper())
        self.assertEqual(dist._resolve_flow_by_trace("RN-" + self.flow[-8:]), self.flow)
