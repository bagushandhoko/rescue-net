"""Profil Kerja Organisasi (owner 2026-11-08): halaman publik ringkasan kerja organisasi + ortom.
Tamu melihat peran & angka, tanpa kontak, nama pasien, atau daftar anggota; organisasi tertutup hanya angka gabungan."""
import json

import frappe

from rescue_net import api_org_profile
from rescue_net.control_centre import org as cc_org
from rescue_net.tests.factories import RNTestCase, _insert, as_guest, as_user, make_actor, make_event, make_medical_case, make_org, make_posko


class TestOrgProfile(RNTestCase):
    def setUp(self):
        super().setUp()
        self.event = make_event(event_status="active")
        self.root = make_org(title="Induk Uji", privacy_mode="open", verification_status="official_verified",
                             contact_person="Kontak Rahasia Induk")
        self.child = make_org(title="Ortom Uji", privacy_mode="open", parent_organization=self.root.name)
        self.closed = make_org(title="Ortom Tertutup", privacy_mode="closed", parent_organization=self.root.name)
        self.rs = make_posko(self.event, self.root, posko_type="medical", latitude=0.8, longitude=102.0,
                             officer_in_charge_phone="+62811-0000-7777")
        self.dapur = make_posko(self.event, self.child, posko_type="kitchen", latitude=0.79, longitude=102.05)
        self.tutup = make_posko(self.event, self.closed, posko_type="transport", latitude=-7.3, longitude=112.7)
        make_medical_case(self.rs, patient_name="Pasien Rahasia Sekali")
        make_medical_case(self.tutup, patient_name="Pasien Tertutup")
        _insert("RN Kitchen Production", posko=self.dapur.name, meal_name="Nasi", portions=450, disaster_event=self.event.name)
        self.member = make_actor(org=self.root)

    def profile(self, **kw):
        with as_guest():
            return api_org_profile.org_profile(self.root.name, **kw)

    def test_guest_sees_roles_and_map_of_root_and_children(self):
        p = self.profile()
        ids = {x["id"] for x in p["poskos"]}
        self.assertEqual(ids, {self.rs.name, self.dapur.name, self.tutup.name})
        self.assertEqual(p["totals"]["porsi"], 450)
        self.assertEqual(p["totals"]["organisasi"], 3)
        types = {r["type"]: r for r in p["roles"]}
        self.assertEqual(types["kitchen"]["metrics"].get("porsi"), 450)
        self.assertTrue(all(x["lat"] is not None for x in p["poskos"]))

    def test_no_contact_patient_or_member_names_for_guest(self):
        blob = json.dumps(self.profile(), default=str)
        for secret in ("+62811-0000-7777", "Pasien Rahasia Sekali", "Pasien Tertutup", "Kontak Rahasia Induk", self.member.user):
            self.assertNotIn(secret, blob)

    def test_closed_org_posko_has_no_detail_metrics(self):
        p = self.profile()
        tutup = next(x for x in p["poskos"] if x["id"] == self.tutup.name)
        self.assertFalse(tutup["open"])
        self.assertNotIn("metrics", tutup)
        rs = next(x for x in p["poskos"] if x["id"] == self.rs.name)
        self.assertEqual(rs["metrics"].get("pasien"), 1)

    def test_event_filter(self):
        other = make_event(event_status="active")
        make_posko(other, self.root, posko_type="logistics")
        self.assertEqual(len(self.profile(disaster_event=self.event.name)["poskos"]), 3)

    def test_org_detail_member_list_only_for_members(self):
        with as_guest():
            self.assertEqual(cc_org.org_detail(self.root.name)["members"], [])
        stranger = make_actor()
        with as_user(stranger.user):
            self.assertEqual(cc_org.org_detail(self.root.name)["members"], [])
