"""BMKG early warning: parsing, threshold, idempotent intake, draft event is
never public, banner is guest-safe."""

import json

import frappe

from rescue_net import api_early_warning as ew_api
from rescue_net import api_events
from rescue_net.services import early_warning as ew
from rescue_net.tests.factories import RNTestCase, as_guest, make_event, make_posko


def payload(mag="5.6", depth="10 km", coords="-6.20,106.80", dt="2026-10-09T01:02:03+00:00", area="Pusat gempa di laut 30 km Barat Daya Banten"):
    return {"Infogempa": {"gempa": {"DateTime": dt, "Coordinates": coords, "Magnitude": mag,
                                     "Kedalaman": depth, "Wilayah": area, "Potensi": "tidak berpotensi tsunami"}}}


class TestEarlyWarning(RNTestCase):
    def test_parse_handles_single_list_and_garbage(self):
        self.assertEqual(len(ew.parse_quakes(payload())), 1)
        lst = {"Infogempa": {"gempa": [payload()["Infogempa"]["gempa"], {"Magnitude": "x"}]}}
        self.assertEqual(len(ew.parse_quakes(lst)), 1)
        self.assertEqual(ew.parse_quakes({}), [])

    def test_threshold(self):
        q = ew.parse_quakes(payload())[0]
        self.assertTrue(ew.meets_threshold(q))
        self.assertFalse(ew.meets_threshold(ew.parse_quakes(payload(mag="4.2"))[0]))
        self.assertFalse(ew.meets_threshold(ew.parse_quakes(payload(depth="300 km"))[0]))
        self.assertFalse(ew.meets_threshold(ew.parse_quakes(payload(coords="40.0,10.0"))[0]))

    def test_intake_is_idempotent_and_creates_one_draft(self):
        self.assertEqual(ew.process([payload()]), 1)
        self.assertEqual(ew.process([payload(), payload()]), 0)
        w = frappe.get_all("RN Early Warning", fields=["name", "draft_event", "meets_threshold"])[0]
        self.assertTrue(w.meets_threshold)
        ev = frappe.get_doc("RN Disaster Event", w.draft_event)
        self.assertEqual(ev.event_status, "draft")
        self.assertIn("DRAF", ev.title)

    def test_below_threshold_stored_without_draft(self):
        ew.process([payload(mag="4.1")])
        w = frappe.get_all("RN Early Warning", fields=["draft_event", "meets_threshold"])[0]
        self.assertFalse(w.meets_threshold)
        self.assertFalse(w.draft_event)

    def test_nearby_poskos_by_radius(self):
        ev = make_event()
        near = make_posko(ev, latitude=-6.3, longitude=106.9)
        far = make_posko(ev, latitude=-2.0, longitude=120.0)
        names = [p["posko"] for p in ew.nearby_poskos(ew.parse_quakes(payload())[0])]
        self.assertIn(near.name, names)
        self.assertNotIn(far.name, names)

    def test_draft_event_not_in_public_disaster_list(self):
        ew.process([payload()])
        with as_guest():
            ids = [d["title"] for d in api_events.disasters()["disasters"]]
        self.assertFalse([t for t in ids if "DRAF BMKG" in t])

    def test_guest_banner_shows_only_public_facts(self):
        ew.process([payload()])
        with as_guest():
            b = ew_api.banner()
        self.assertEqual(len(b["warnings"]), 1)
        w = b["warnings"][0]
        self.assertTrue(w["unverified"])
        blob = json.dumps(b)
        for secret in ("draft_event", "nearby_poskos", "raw", "legacy"):
            self.assertNotIn(secret, blob)

    def test_review_is_system_manager_only(self):
        ew.process([payload()])
        name = frappe.get_all("RN Early Warning", pluck="name")[0]
        with as_guest(), self.assertRaises(frappe.PermissionError):
            ew_api.review(name, "dismissed")
        self.assertEqual(ew_api.review(name, "dismissed")["status"], "dismissed")  # Administrator in tests
