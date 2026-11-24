"""owner 2026-11-24: di bencana SIMULASI semua pengguna login (akun RN aktif) boleh mengubah data; bencana riil tidak."""

import frappe

from rescue_net import access_policy as ap
from rescue_net.tests.factories import RNTestCase, as_guest, as_user, make_actor, make_posko


class TestSimOpenEdit(RNTestCase):
    def _event(self, sim):
        from rescue_net.tests.factories import make_event
        ev = make_event()
        if sim:
            from rescue_net.services import drill
            names = set(drill._json_list(drill.EXTRA_KEY)) | {ev.name}
            frappe.db.set_default(drill.EXTRA_KEY, frappe.as_json(sorted(names)))
        return ev

    def _actor(self):
        a = make_actor()
        return frappe._dict(name=a.account.name if hasattr(a.account, "name") else a.account), a.user

    def test_sim_posko_open_for_any_logged_in_user(self):
        posko = make_posko(event=self._event(True))
        actor, user = self._actor()
        with as_user(user):
            self.assertTrue(ap.can_manage_posko(actor, posko.name))

    def test_real_posko_unchanged(self):
        posko = make_posko(event=self._event(False))
        actor, user = self._actor()
        with as_user(user):
            self.assertFalse(ap.can_manage_posko(actor, posko.name))

    def test_guest_never(self):
        posko = make_posko(event=self._event(True))
        with as_guest():
            self.assertFalse(ap.sim_open_posko(None, posko.name))

    def test_switch_off(self):
        posko = make_posko(event=self._event(True))
        actor, user = self._actor()
        frappe.db.set_default("rn_sim_open_edit", "0")
        try:
            with as_user(user):
                self.assertFalse(ap.can_manage_posko(actor, posko.name))
        finally:
            frappe.db.set_default("rn_sim_open_edit", "1")

    def test_without_sim_open_hides_sim_access(self):
        """owner 24 Nov 16:05: halaman program menampilkan tampilan publik dulu untuk akses simulasi terbuka."""
        posko = make_posko(event=self._event(True))
        actor, user = self._actor()
        with as_user(user):
            self.assertTrue(ap.can_manage_posko(actor, posko.name))
            self.assertFalse(ap.without_sim_open(ap.can_manage_posko, actor, posko.name))
            self.assertTrue(ap.can_manage_posko(actor, posko.name))      # flag dikembalikan
