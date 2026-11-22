"""Kartu keluarga + penerimaan per putaran (10b langkah 3): satu penerimaan per keluarga per putaran,
putaran ditetapkan koordinator, QR hanya token buram, tanpa data pribadi, tanpa akses tamu."""

import json

import frappe
from frappe.utils import add_to_date, now_datetime

from rescue_net import api_aid_card as ac
from rescue_net.tests.factories import RNTestCase, _insert, as_guest, as_user, make_actor, make_posko, make_world


class TestAidCard(RNTestCase):
    def setUp(self):
        super().setUp()
        self.w = make_world()
        self.shelter = make_posko(self.w.event, self.w.org_a, posko_type="shelter")
        self.other = make_posko(self.w.event, self.w.org_b, posko_type="shelter")
        self.op = make_actor(posko=self.shelter)
        self.op_other = make_actor(posko=self.other)
        self.outsider = make_actor()
        self.hh = self.household("KK-001")
        with as_user(self.op.user):
            self.round = ac.create_round(self.shelter.name, "Sembako Hari 1", item_note="paket sembako")["round"]
            self.token = ac.issue_card(self.hh.name)["token"]

    def household(self, code, posko=None, status="checked_in"):
        return _insert("RN Shelter Household", posko=(posko or self.shelter).name, household_code=code, members_count=4,
                       household_status=status, check_in_at=now_datetime(), notes="ANGGOTA-SENTINEL")

    def test_one_receipt_per_family_per_round(self):
        with as_user(self.op.user):
            self.assertTrue(ac.check_card(self.token, self.round)["ok"])
            r1 = ac.record_receipt(self.token, self.round)
            self.assertEqual(r1["state"], "recorded")
            r2 = ac.record_receipt(self.token, self.round)
            self.assertEqual(r2["state"], "already")
            self.assertTrue(r2["received_at"])
            self.assertEqual(ac.check_card(self.token, self.round)["state"], "already")
        self.assertEqual(frappe.db.count("RN Aid Receipt", {"round": self.round}), 1)

    def test_new_round_allows_again(self):
        with as_user(self.op.user):
            ac.record_receipt(self.token, self.round)
            r2 = ac.create_round(self.shelter.name, "Sembako Hari 2")["round"]
            self.assertEqual(ac.record_receipt(self.token, r2)["state"], "recorded")

    def test_offline_replay_is_idempotent(self):
        with as_user(self.op.user):
            a = ac.record_receipt(self.token, self.round, offline_id="dev-1")
            b = ac.record_receipt(self.token, self.round, offline_id="dev-1")
        self.assertEqual(a["state"], "recorded")
        self.assertTrue(b["duplicate"])
        self.assertEqual(frappe.db.count("RN Aid Receipt", {"round": self.round}), 1)

    def test_only_coordinator_creates_and_closes_rounds(self):
        for u in (self.outsider.user, self.op_other.user):
            with as_user(u):
                with self.assertRaises(frappe.PermissionError):
                    ac.create_round(self.shelter.name, "Curang")
                with self.assertRaises(frappe.PermissionError):
                    ac.set_round_status(self.round, "closed")
        with as_guest():
            with self.assertRaises(Exception):
                ac.create_round(self.shelter.name, "Tamu")

    def test_closed_round_and_window_reject(self):
        with as_user(self.op.user):
            ac.set_round_status(self.round, "closed")
            self.assertEqual(ac.record_receipt(self.token, self.round)["state"], "closed")
            ac.set_round_status(self.round, "open")
            future = ac.create_round(self.shelter.name, "Besok", opens_at=add_to_date(now_datetime(), days=1))["round"]
            self.assertEqual(ac.check_card(self.token, future)["state"], "closed")
        self.assertEqual(frappe.db.count("RN Aid Receipt", {"round": self.round}), 0)

    def test_card_rules(self):
        with as_user(self.op.user):
            self.assertEqual(ac.check_card("RNK-ZZZZZZZZ", self.round)["state"], "invalid")
            same = ac.issue_card(self.hh.name)
            self.assertTrue(same["reused"])
            self.assertEqual(same["token"], self.token)
            new = ac.issue_card(self.hh.name, reissue=1)
            self.assertNotEqual(new["token"], self.token)
            self.assertEqual(ac.check_card(self.token, self.round)["state"], "revoked")
            self.assertEqual(ac.check_card(new["token"], self.round)["state"], "eligible")

    def test_wrong_posko_and_departed_family(self):
        with as_user(self.op_other.user):
            other_round = ac.create_round(self.other.name, "Putaran lain")["round"]
            self.assertEqual(ac.check_card(self.token, other_round)["state"], "wrong_posko")
        frappe.db.set_value("RN Shelter Household", self.hh.name, "household_status", "checked_out")
        with as_user(self.op.user):
            self.assertEqual(ac.check_card(self.token, self.round)["state"], "not_present")
            with self.assertRaises(frappe.ValidationError):
                ac.issue_card(self.hh.name, reissue=1)

    def test_scan_rights_and_no_personal_data(self):
        with as_user(self.outsider.user):
            with self.assertRaises(frappe.PermissionError):
                ac.check_card(self.token, self.round)
            with self.assertRaises(frappe.PermissionError):
                ac.record_receipt(self.token, self.round)
        with as_guest():
            with self.assertRaises(Exception):
                ac.check_card(self.token, self.round)
        with as_user(self.op.user):
            blob = json.dumps([ac.check_card(self.token, self.round), ac.record_receipt(self.token, self.round),
                               ac.list_receipts(self.round), ac.list_households(self.shelter.name)])
        self.assertNotIn("ANGGOTA-SENTINEL", blob)

    def test_receipts_append_only(self):
        with as_user(self.op.user):
            ac.record_receipt(self.token, self.round)
        name = frappe.db.get_value("RN Aid Receipt", {"round": self.round}, "name")
        doc = frappe.get_doc("RN Aid Receipt", name)
        doc.items_note = "ubah"
        with self.assertRaises(frappe.ValidationError):
            doc.save(ignore_permissions=True)
        with self.assertRaises(frappe.ValidationError):
            frappe.delete_doc("RN Aid Receipt", name, ignore_permissions=True)

    def test_unique_key_blocks_direct_duplicate(self):
        with as_user(self.op.user):
            ac.record_receipt(self.token, self.round)
        with self.assertRaises((frappe.DuplicateEntryError, frappe.UniqueValidationError)):
            _insert("RN Aid Receipt", round=self.round, household=self.hh.name,
                    round_household="%s:%s" % (self.round, self.hh.name), received_at=now_datetime())

    def test_my_shelters_lists_only_own(self):
        with as_user(self.op.user):
            names = [s["name"] for s in ac.my_shelters()]
        self.assertIn(self.shelter.name, names)
        self.assertNotIn(self.other.name, names)
