"""10f tahap 2: catatan eksplisit posko (barang/kemasan tidak diterima) — hak ubah, privasi, tampil hanya untuk posko publik."""

import json

import frappe

from rescue_net import api_public_needs as pn
from rescue_net.tests.factories import RNTestCase, as_guest, as_user, make_actor, make_event, make_posko


class TestPublicNeedsNotes(RNTestCase):
    def setUp(self):
        super().setUp()
        self.ev = make_event()
        self.pub = make_posko(self.ev, public_detail="public", city_name="Kota Uji")
        self.priv = make_posko(self.ev, public_detail="private")
        self.mgr = make_actor(posko=self.pub)
        self.mgr_priv = make_actor(posko=self.priv)
        self.outsider = make_actor()

    def board(self):
        with as_guest():
            return pn.board(event=self.ev.name)

    def test_manager_sets_note_and_guest_sees_it(self):
        with as_user(self.mgr.user):
            r = pn.set_public_notes(self.pub.name, "pakaian bekas", "kardus basah")
        self.assertTrue(r["public"])
        n = self.board()["notes"]
        self.assertEqual(len(n), 1)
        self.assertEqual(n[0]["not_needed"], "pakaian bekas")
        self.assertEqual(n[0]["not_accepted_packaging"], "kardus basah")
        self.assertEqual(n[0]["posko"], self.pub.name)

    def test_private_posko_note_never_reaches_guest(self):
        with as_user(self.mgr_priv.user):
            pn.set_public_notes(self.priv.name, "RAHASIA-CATATAN", "")
        self.assertNotIn("RAHASIA-CATATAN", json.dumps(self.board()))

    def test_outsider_and_guest_cannot_write(self):
        with as_user(self.outsider.user):
            with self.assertRaises(frappe.PermissionError):
                pn.set_public_notes(self.pub.name, "x", "")
        with as_user(self.mgr_priv.user):  # pengelola posko LAIN
            with self.assertRaises(frappe.PermissionError):
                pn.set_public_notes(self.pub.name, "x", "")
        with as_guest():
            with self.assertRaises(Exception):
                pn.set_public_notes(self.pub.name, "x", "")
            with self.assertRaises(Exception):
                pn.my_editable_poskos()

    def test_contact_like_and_too_long_rejected(self):
        with as_user(self.mgr.user):
            for bad in ("hubungi 0812-3456-7890", "kirim ke a@b.co", "lihat https://x.id", "www.contoh.id"):
                with self.assertRaises(frappe.ValidationError):
                    pn.set_public_notes(self.pub.name, bad, "")
            with self.assertRaises(frappe.ValidationError):
                pn.set_public_notes(self.pub.name, "a" * 501, "")

    def test_editable_list_only_own_poskos(self):
        with as_user(self.mgr.user):
            names = [p["posko"] for p in pn.my_editable_poskos()]
        self.assertIn(self.pub.name, names)
        self.assertNotIn(self.priv.name, names)

    def test_clearing_note_removes_it(self):
        with as_user(self.mgr.user):
            pn.set_public_notes(self.pub.name, "a", "b")
            pn.set_public_notes(self.pub.name, "", "")
        self.assertEqual(self.board()["notes"], [])
