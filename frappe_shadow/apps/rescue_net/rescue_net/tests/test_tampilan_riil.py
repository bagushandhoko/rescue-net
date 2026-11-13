"""Tombol tampilan di Home (owner 2026-11-13): "Lihat Simulasi" / "Riil Data Bencana", pilihan PER PENGUNJUNG.

- tanpa cookie -> simulasi tampil (bawaan);
- cookie rn_tampilan=riil -> data simulasi disembunyikan hanya untuk pengunjung itu (penyaring sama dgn Mode Operasional);
- akun demo TIDAK diblokir oleh pilihan pengunjung (hanya saklar super admin);
- cache tamu memisahkan salinan riil dan simulasi.
"""

from types import SimpleNamespace
from unittest import mock

import frappe

from rescue_net.services import drill
from rescue_net.services.guest_cache import guest_cache
from rescue_net.tests.factories import RNTestCase, as_guest
from rescue_net.tests.test_operational_mode import LABEL_SENT, SENT, OperationalBase

CALLS = []


@guest_cache(30)
def _feed():
    CALLS.append(1)
    return {"riil": drill.simulation_hidden(), "n": len(CALLS)}


class _Cookie:
    def __init__(self, value):
        self.value = value

    def __enter__(self):
        self.old = getattr(frappe.local, "request", None)
        self.old_ip = getattr(frappe.local, "request_ip", None)
        frappe.local.request_ip = "127.0.0.1"
        cookies = {drill.VIEW_COOKIE: self.value} if self.value is not None else {}
        frappe.local.request = SimpleNamespace(cookies=cookies, path="/api/method/x")
        return self

    def __exit__(self, *a):
        frappe.local.request = self.old
        frappe.local.request_ip = self.old_ip


class TestViewerChoice(OperationalBase):
    def test_default_and_simulasi_show_simulation(self):
        for v in (None, "simulasi", "apa-saja"):
            with _Cookie(v):
                self.assertFalse(drill.viewer_wants_real(), v)
                self.assertFalse(drill.simulation_hidden(), v)
                self.assertEqual(drill.view_suffix(), "")
                blobs = self.public_blobs()
                self.assertIn(SENT, blobs["disasters"], v)

    def test_riil_hides_simulation_for_this_visitor_only(self):
        with _Cookie("riil"):
            self.assertTrue(drill.simulation_hidden())
            self.assertFalse(drill.operational_mode())  # saklar global tidak berubah
            blobs = self.public_blobs()
            for key, text in blobs.items():
                self.assertNotIn(SENT, text, key)
                self.assertNotIn(LABEL_SENT, text, key)
            self.assertIn(self.real.event.title, blobs["disasters"])
        with _Cookie(None):  # pengunjung lain tetap melihat simulasi
            self.assertIn(SENT, self.public_blobs()["disasters"])

    def test_riil_choice_does_not_block_demo_accounts(self):
        with _Cookie("riil"):
            lm = SimpleNamespace(user="ld1.demo@rescue-net.local")
            drill.block_demo_login(lm)  # tidak error: hanya Mode Operasional yang memblokir

    def test_operational_mode_overrides_choice(self):
        self._mode(True)
        with _Cookie(None):
            self.assertTrue(drill.simulation_hidden())
            self.assertEqual(drill.view_suffix(), "")  # semua orang sama -> satu salinan cache

    def test_guest_cache_keeps_views_apart(self):
        CALLS.clear()
        store = {}
        fake = mock.Mock()
        fake.get_value.side_effect = store.get
        fake.set_value.side_effect = lambda k, v, expires_in_sec=None: store.__setitem__(k, v)
        old_flag, frappe.flags.in_test = frappe.flags.in_test, False
        try:
            with mock.patch.object(frappe, "cache", return_value=fake), as_guest():
                with _Cookie(None):
                    a = _feed()
                with _Cookie("riil"):
                    b = _feed()
                with _Cookie(None):
                    c = _feed()
        finally:
            frappe.flags.in_test = old_flag
        self.assertFalse(a["riil"])
        self.assertTrue(b["riil"])
        self.assertEqual(a, c)  # salinan simulasi dipakai ulang
        self.assertEqual(len(CALLS), 2)


class TestDropHiddenRows(OperationalBase):
    def rows(self):
        return [
            frappe._dict(name="a", disaster_event=self.real.event.name, posko=self.real.posko_a.name, title="nyata"),
            frappe._dict(name="b", disaster_event=self.sim.name, title="di bencana simulasi"),
            frappe._dict(name="c", posko=self.sim_posko.name, title="di posko simulasi"),
            frappe._dict(name="d", posko=self.label_posko.name, title="posko berlabel"),
            frappe._dict(name="e", title="[SIMULASI] berlabel"),
        ]

    def test_simulasi_view_keeps_all(self):
        with _Cookie(None):
            self.assertEqual(len(drill.drop_hidden_rows(self.rows())), 5)

    def test_riil_view_keeps_only_real(self):
        with _Cookie("riil"):
            self.assertEqual([r.name for r in drill.drop_hidden_rows(self.rows())], ["a"])
