"""S3 laporan ganda (2026-11-02): three residents report the same incident → one main report, people counted
once (largest count, not the sum), one posko handles it; only posko managers / Control Centre may link."""

import frappe

from rescue_net import api_report_duplicates as rd
from rescue_net.tests.factories import RNTestCase, _insert, as_user, make_actor, make_world


class TestReportDuplicates(RNTestCase):
    def setUp(self):
        super().setUp()
        self.w = make_world()
        self.mgr = make_actor(posko=self.w.posko_a)
        self.other = make_actor(posko=self.w.posko_b)
        self.warga = make_actor(role="masyarakat")

        def rep(people, lat, lng, title):
            return _insert("RN Community Report", title=title, description="Rumah roboh, warga mengungsi",
                           disaster_event=self.w.event.name, report_type="korban", affected_people_count=people,
                           latitude=lat, longitude=lng, has_coordinates=1, posko=self.w.posko_a.name,
                           village_name="Desa Uji", reporter_user=self.warga.account, status="submitted")
        self.a = rep(40, -6.900, 107.600, "Rumah roboh RT 02")
        self.b = rep(55, -6.901, 107.601, "Banyak rumah rusak di RT 02")
        self.c = rep(38, -6.902, 107.599, "Warga RT 02 butuh tenda")
        self.far = rep(10, -7.300, 108.200, "Longsor desa lain")

    def test_candidates_close_in_place(self):
        with as_user(self.mgr.user):
            names = [c["name"] for c in rd.report_duplicate_candidates(self.c.name)["candidates"]]
        self.assertEqual(sorted(names), sorted([self.a.name, self.b.name]))
        self.assertNotIn(self.far.name, names)

    def test_only_manager_links(self):
        with as_user(self.other.user), self.assertRaises(frappe.PermissionError):
            rd.mark_report_duplicate(self.b.name, self.a.name)
        with as_user(self.warga.user), self.assertRaises(frappe.PermissionError):
            rd.report_duplicate_candidates(self.a.name)
        # a manager of another posko serving the same disaster may look, but not link reports it does not handle
        frappe.db.set_value("RN Community Report", self.c.name, "posko", self.w.posko_b.name)
        with as_user(make_actor(posko=self.w.posko_b).user):
            self.assertTrue(rd.report_duplicate_candidates(self.a.name)["candidates"])

    def test_people_counted_once_and_board(self):
        with as_user(self.mgr.user):
            rd.mark_report_duplicate(self.b.name, self.a.name)
            r = rd.mark_report_duplicate(self.c.name, self.b.name)  # copy of a copy → goes to the main report
        self.assertEqual(r["duplicate_of"], self.a.name)
        self.assertEqual(r["group_people"], 55)  # largest, not 40+55+38
        self.assertEqual(frappe.db.get_value("RN Community Report", self.c.name, "consolidation_status"), "duplicate")
        self.assertTrue(frappe.get_all("RN Community Report Update", filters={"report": self.b.name}))

        from rescue_net.control_centre.bencana_aktif import _ba_jiwa_categories
        cats = _ba_jiwa_categories(self.w.event.name, self.w.event.name, {}, {}, {})
        korban = [c for c in cats if c["key"] == "laporan_korban"][0]
        titles = [i["title"] for i in korban["items"]]
        self.assertIn(self.a.title, titles)
        self.assertNotIn(self.b.title, titles)
        self.assertNotIn(self.c.title, titles)
        self.assertEqual([i["count"] for i in korban["items"] if i["title"] == self.a.title], [55])

        with as_user(self.mgr.user):
            rd.unmark_report_duplicate(self.c.name)
        self.assertFalse(frappe.db.get_value("RN Community Report", self.c.name, "duplicate_of"))

    def test_no_cycle(self):
        with as_user(self.mgr.user):
            rd.mark_report_duplicate(self.b.name, self.a.name)
            with self.assertRaisesRegex(frappe.ValidationError, "dirinya"):
                rd.mark_report_duplicate(self.a.name, self.b.name)


class TestRoutingServedEvents(RNTestCase):
    def test_posko_serving_event_via_served_events_gets_report(self):
        from rescue_net.services.report_routing import best_posko
        from rescue_net.tests.factories import make_event, make_org, make_posko

        main_ev, other_ev = make_event(event_status="active"), make_event(event_status="active")
        p = make_posko(other_ev, make_org(), latitude=4.1446, longitude=96.1269, posko_type="logistics")
        p.append("served_events", {"disaster_event": main_ev.name})
        p.save(ignore_permissions=True)
        posko, score, reason = best_posko({"disaster_event": main_ev.name, "latitude": 4.1440, "longitude": 96.1290,
                                            "report_type": "affected_need_help"})
        self.assertEqual(posko, p.name, reason)
