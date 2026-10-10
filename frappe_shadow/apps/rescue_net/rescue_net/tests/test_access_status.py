"""Status akses & infrastruktur (Fase 10e): hak lapor, basi otomatis, riwayat append-only, ringkasan publik tanpa pelapor."""

import json

import frappe
from frappe.utils import add_to_date, now_datetime

from rescue_net import api_access_status as api
from rescue_net.services import access_status as svc
from rescue_net.tests.factories import RNTestCase, _insert, as_guest, as_user, make_actor, make_event, make_posko, make_world


class AccessBase(RNTestCase):
    def setUp(self):
        super().setUp()
        self.w = make_world()
        self.op_a = make_actor(posko=self.w.posko_a)
        self.op_other = make_actor(posko=make_posko(make_event()))          # posko di event lain
        self.cit = make_actor(role="citizen")

    def report(self, user=None, **kw):
        args = dict(disaster_event=self.w.event.name, kind="bridge", place_name="Jembatan Kali Besar", status="closed",
                    posko=self.w.posko_a.name)
        args.update(kw)
        with as_user(user or self.op_a.user):
            return api.report(**args)


class TestReporting(AccessBase):
    def test_posko_manager_reports_others_cannot(self):
        self.assertTrue(self.report()["ok"])
        for user, kw in ((self.cit.user, {}), (self.op_other.user, {}), (self.op_a.user, {"posko": self.w.posko_b.name})):
            with self.assertRaises(frappe.PermissionError):
                self.report(user=user, **kw)
        with as_guest(), self.assertRaises(frappe.ValidationError):
            api.report(self.w.event.name, "road", "Jl X", "open")

    def test_input_is_validated_and_notes_have_no_contacts(self):
        for bad in ({"kind": "teleport"}, {"status": "broken"}, {"place_name": ""}, {"valid_hours": 0},
                    {"valid_hours": 24 * 31}, {"note": "hubungi 081234567890"}, {"segment": "lihat https://x.id"},
                    {"posko": make_posko(make_event()).name}):
            with self.assertRaises(frappe.ValidationError):
                self.report(**bad)
        self.assertEqual(frappe.db.count("RN Access Status", {"disaster_event": self.w.event.name}), 0)

    def test_area_defaults_from_posko_when_known(self):
        n = self.report()["name"]
        self.assertIsNone(frappe.db.get_value("RN Access Status", n, "admin_area_id"))   # posko uji tanpa kode wilayah


class TestCurrentAndStale(AccessBase):
    def test_latest_report_wins_and_history_is_kept(self):
        self.report(status="closed")
        later = self.report(status="open")["name"]
        frappe.db.set_value("RN Access Status", later, "observed_at", add_to_date(now_datetime(), minutes=5))
        cur = svc.current_statuses(self.w.event.name)
        self.assertEqual([(r["place_name"], r["effective_status"]) for r in cur], [("Jembatan Kali Besar", "open")])
        with as_user(self.op_a.user):
            hist = api.history(self.w.event.name, "bridge", "Jembatan Kali Besar")["rows"]
        self.assertEqual([h["status"] for h in hist], ["open", "closed"])               # kapan pulih terlihat

    def test_expired_report_becomes_unknown_with_age(self):
        n = self.report(status="closed")["name"]
        frappe.db.set_value("RN Access Status", n, {"observed_at": add_to_date(now_datetime(), hours=-30),
                                                    "valid_until": add_to_date(now_datetime(), hours=-6)})
        r = svc.current_statuses(self.w.event.name)[0]
        self.assertEqual((r["stale"], r["effective_status"]), (1, "unknown"))
        self.assertGreaterEqual(r["age_hours"], 30)

    def test_records_are_append_only(self):
        n = self.report()["name"]
        doc = frappe.get_doc("RN Access Status", n)
        doc.status = "open"
        with self.assertRaises(frappe.ValidationError):
            doc.save(ignore_permissions=True)
        with self.assertRaises(frappe.ValidationError):
            frappe.get_doc("RN Access Status", n).delete()


class TestVerificationAndPublic(AccessBase):
    def test_only_verifier_or_system_manager_verifies(self):
        n = self.report()["name"]
        with as_user(self.cit.user), self.assertRaises(frappe.PermissionError):
            api.verify(n)
        api.verify(n)                                                                    # Administrator = System Manager
        self.assertEqual(frappe.db.get_value("RN Access Status", n, "verification_status"), "verified")

    def test_public_board_is_aggregate_without_reporter_coordinates_or_notes(self):
        self.report(note="Banjir setinggi dada", segment="Km 12", latitude=-6.5, longitude=106.5)
        self.report(kind="power", place_name="Gardu A", status="open")
        with as_guest():
            b = api.board(self.w.event.name)
        blob = json.dumps(b, default=str)
        for secret in ("Banjir setinggi dada", "-6.5", "106.5", self.op_a.account, "reported_by", "latitude"):
            self.assertNotIn(secret, blob)
        self.assertEqual({s["kind"]: s["closed"] for s in b["summary"]}, {"bridge": 1, "power": 0})
        self.assertEqual([i["place_name"] for i in b["items"]], ["Jembatan Kali Besar"])    # hanya tertutup/terbatas

    def test_logged_in_list_needs_login_and_drill_event_is_invisible_to_guests(self):
        self.report()
        with as_guest(), self.assertRaises(frappe.ValidationError):
            api.list_status(self.w.event.name)
        drill = make_event(is_drill=1)
        _insert("RN Access Status", disaster_event=drill.name, kind="road", place_name="Jl Latihan", status="closed",
                observed_at=now_datetime(), valid_until=add_to_date(now_datetime(), hours=5))
        with as_guest():
            self.assertEqual(api.board(drill.name), {"event": drill.name, "summary": [], "items": []})


class TestFlowWarning(AccessBase):
    def test_closed_access_in_same_area_warns_but_never_blocks(self):
        from rescue_net.services import admin_areas
        from rescue_net.tests.test_admin_areas import FILE, rows

        admin_areas.import_rows(rows(FILE), "uji", dry_run=False)
        # posko A di desa 91.71.02.1001, posko B di provinsi lain-nya (tanpa kode)
        frappe.db.set_value("RN Posko", self.w.posko_a.name, "admin_area_id", "91.71.02.1001")
        self.report(admin_area_id="91.71")                                 # jembatan putus di tingkat kota
        warn = svc.access_warnings(self.w.posko_a.name)
        self.assertEqual([w["place_name"] for w in warn], ["Jembatan Kali Besar"])
        self.assertEqual(svc.access_warnings(self.w.posko_b.name), [])      # posko tanpa kode wilayah: tak ada tebakan
        later = self.report(place_name="Jembatan Kali Besar", status="open", admin_area_id="91.71")["name"]
        frappe.db.set_value("RN Access Status", later, "observed_at", add_to_date(now_datetime(), minutes=5))
        self.assertEqual(svc.access_warnings(self.w.posko_a.name), [])      # pulih -> peringatan hilang

    def test_create_flow_returns_warnings_and_still_creates(self):
        from rescue_net import api_logistics
        from rescue_net.services import admin_areas
        from rescue_net.tests.test_admin_areas import FILE, rows

        admin_areas.import_rows(rows(FILE), "uji", dry_run=False)
        frappe.db.set_value("RN Posko", self.w.posko_a.name, "admin_area_id", "91.71.02.1001")
        self.report(admin_area_id="91.71")
        with as_user(self.op_a.user):
            r = api_logistics.create_flow(self.w.posko_a.name, "Beras", quantity=5, unit="karung")
        self.assertTrue(frappe.db.exists("RN Distribution Flow", r["flow"]))
        self.assertEqual([x["kind"] for x in r["access_warnings"]], ["bridge"])

    def test_related_area_codes_by_prefix(self):
        self.assertTrue(svc._area_related("11", "11.01.02"))
        self.assertTrue(svc._area_related("11.01.02", "11.01"))
        self.assertFalse(svc._area_related("11.01", "12.01"))
        self.assertFalse(svc._area_related(None, "11"))
