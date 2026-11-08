"""Owner 2026-11-08: 🔔 kotak pemberitahuan — people waiting for a decision hear about it."""

import frappe

from rescue_net import api_community_cluster as cc
from rescue_net import api_donor_program as dp
from rescue_net import api_inbox as inbox
from rescue_net import api_saran
from rescue_net.tests.factories import RNTestCase, as_guest, as_user, make_actor, make_event, make_org, make_posko, make_user


def _subjects(user):
    with as_user(user):
        return [i["subject"] for i in inbox.my_notifications()["items"]]


class TestInbox(RNTestCase):
    def setUp(self):
        super().setUp()
        self.event = make_event(event_status="active")
        self.org = make_org(verification_status="verified")
        self.posko = make_posko(self.event, self.org)
        self.owner = make_actor(org=self.org, org_role="owner", posko=self.posko)
        self.person = make_actor(role="")

    def test_membership_request_and_decision_and_placement(self):
        with as_user(self.person.user):
            m = cc.request_membership(self.org.name)["name"]
        self.assertTrue(any("Permohonan anggota baru" in s for s in _subjects(self.owner.user)))
        with as_user(self.owner.user):
            cc.decide_membership(m, "approve")
            cc.assign_member_to_posko(self.posko.name, self.person.account)
        subs = _subjects(self.person.user)
        self.assertTrue(any("disetujui" in s for s in subs))
        self.assertTrue(any("ditempatkan di posko" in s for s in subs))
        with as_user(self.person.user):
            self.assertGreater(inbox.my_notifications()["unread"], 0)
            inbox.mark_notifications_read()
            self.assertEqual(inbox.my_notifications()["unread"], 0)

    def test_donation_notifies_initiator_then_donor(self):
        with as_user(self.owner.user):
            prog = dp.create_special_program(self.event.name, "Air bersih", owner_type="organization",
                                             owner_id=self.org.name)["program"]
        donor = make_actor()
        with as_user(donor.user):
            don = dp.create_cash_donation(prog, 50_000)["donation"]
        self.assertTrue(any("Donasi baru" in s for s in _subjects(self.owner.user)))
        with as_user(self.owner.user):
            dp.decide_cash_donation(don, "confirm")
        self.assertTrue(any("sudah diterima" in s for s in _subjects(donor.user)))

    def test_new_saran_reaches_super_admin_and_guest_sees_nothing(self):
        admin = make_user(roles=("System Manager",))
        with as_guest():
            api_saran.submit_suggestion(body="Tolong tambah fitur cetak laporan harian posko.", category="usul",
                                        title="Cetak laporan harian")
            self.assertEqual(inbox.my_notifications(), {"logged_in": False, "unread": 0, "items": []})
        self.assertTrue(any("Saran baru" in s for s in _subjects(admin)))
