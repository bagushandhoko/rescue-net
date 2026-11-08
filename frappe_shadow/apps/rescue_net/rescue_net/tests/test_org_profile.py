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

    def test_partner_carrier_and_confirmed_donors(self):
        other = make_org(title="Mitra Angkut", privacy_mode="closed")
        hub = make_posko(self.event, other, posko_type="transport")
        space = _insert("RN Transport Space", title="Pesawat Uji", coordination_posko=hub.name, provider_name="Pesawat Uji", disaster_event=self.event.name)
        fl = _insert("RN Distribution Flow", title="Kiriman uji", source_posko=self.dapur.name, destination_posko=self.rs.name, item_name="Masker",
                     quantity=10, unit="pcs", flow_status="planned", transport_space=space.name, disaster_event=self.event.name)
        frappe.db.set_value("RN Distribution Flow", fl.name, "flow_status", "received")  # status akhir tanpa jalur penuh
        prog = _insert("RN Donor Program", program_name="Program Uji", owner_type="organization", owner_id=self.root.name,
                       disaster_event=self.event.name, budget_target=1000, budget_received=300, status="active")
        don = _insert("RN Cash Donation", donor_program=prog.name, amount=300, status="pending", donor_name="Rahasia Donatur", is_anonymous=1)
        frappe.db.set_value("RN Cash Donation", don.name, "status", "received")  # = dikonfirmasi penyelenggara
        p = self.profile()
        self.assertIn("Mitra Angkut", [x["title"] for x in p["partners"]])
        self.assertIn("angkutan", next(x for x in p["partners"] if x["title"] == "Mitra Angkut")["peran"])
        self.assertEqual(next(x for x in p["programs"] if x["id"] == prog.name)["donatur"], 1)
        self.assertNotIn("Rahasia Donatur", json.dumps(p, default=str))

    def test_org_detail_member_list_only_for_members(self):
        with as_guest():
            self.assertEqual(cc_org.org_detail(self.root.name)["members"], [])
        stranger = make_actor()
        with as_user(stranger.user):
            self.assertEqual(cc_org.org_detail(self.root.name)["members"], [])


class TestCommunityActivity(RNTestCase):
    """Owner 2026-11-09: kegiatan masyarakat umum per bencana — aktivitas saja, tanpa data pribadi."""

    def test_activity_without_personal_data(self):
        from rescue_net import api_donor_program as dp
        event = make_event(event_status="active")
        org = make_org(verification_status="official_verified")
        posko = make_posko(event, org)
        owner = make_actor(org=org, org_role="owner", posko=posko)
        with as_user(owner.user):
            prog = dp.create_special_program(event.name, "Air bersih", owner_type="organization", owner_id=org.name,
                                             status="active")["program"]
        donor = make_actor(phone="+62811-7777-1234")
        with as_user(donor.user):
            don = dp.create_cash_donation(prog, 25_000, donor_name="Nama Rahasia Uji")["donation"]
        with as_user(owner.user):
            dp.decide_cash_donation(don, "confirm")
        with as_guest():
            r = api_org_profile.community_activity(event.name)
        self.assertEqual(r["donasi"]["jumlah"], 1)
        self.assertEqual(r["donasi"]["total"], 25_000)
        blob = json.dumps(r, default=str)
        self.assertNotIn("Nama Rahasia Uji", blob)
        self.assertNotIn("7777", blob)


class TestActivityHistory(RNTestCase):
    """Owner 2026-11-09: riwayat kegiatan bisa ditelusuri per organisasi / posko; organisasi tertutup hanya angka."""

    def test_trace_open_vs_closed(self):
        event = make_event(event_status="active")
        open_org = make_org(title="Org Terbuka Uji", privacy_mode="open")
        closed_org = make_org(title="Org Tertutup Uji", privacy_mode="closed")
        p_open = make_posko(event, open_org, posko_type="kitchen")
        p_closed = make_posko(event, closed_org, posko_type="kitchen")
        for p in (p_open, p_closed):
            _insert("RN Kitchen Production", disaster_event=event.name, posko=p.name, meal_name="Nasi", portions=120)
        with as_guest():
            r_open = api_org_profile.activity_history(event.name, "organisasi", open_org.name)
            r_closed = api_org_profile.activity_history(event.name, "organisasi", closed_org.name)
            r_posko = api_org_profile.activity_history(event.name, "posko", p_open.name)
        self.assertEqual(r_open["total"], 1)
        self.assertIn("120 porsi", r_open["items"][0]["teks"])
        self.assertEqual(r_closed["total"], 1)          # counted …
        self.assertEqual(r_closed["items"], [])         # … but not itemised for outsiders
        self.assertEqual(r_posko["items"][0]["posko"], p_open.name)
        member = make_actor(org=closed_org, org_role="member")
        with as_user(member.user):
            self.assertEqual(len(api_org_profile.activity_history(event.name, "organisasi", closed_org.name)["items"]), 1)


class TestEcosystemPerformance(RNTestCase):
    def test_child_rolls_into_root_and_counts(self):
        event = make_event(event_status="active")
        root = make_org(title="Induk Kinerja", privacy_mode="open")
        child = make_org(title="Anak Kinerja", privacy_mode="closed", parent_organization=root.name)
        p = make_posko(event, child, posko_type="kitchen")
        _insert("RN Kitchen Production", disaster_event=event.name, posko=p.name, meal_name="Nasi", portions=80)
        with as_guest():
            r = api_org_profile.ecosystem_performance(event.name)
        rows = {x["id"]: x for x in r["pihak"]}
        self.assertIn(root.name, rows)
        self.assertNotIn(child.name, rows)
        self.assertEqual(rows[root.name]["porsi"], 80)
        self.assertEqual(rows[root.name]["anak"], ["Anak Kinerja"])
