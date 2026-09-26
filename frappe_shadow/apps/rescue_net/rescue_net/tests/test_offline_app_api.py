"""Endpoints the offline app needed when FastAPI was retired (phase 3):
event list, device registration, unit catalogue / normaliser, admin areas
without the FastAPI fallback."""

import frappe

from rescue_net import api_admin_areas, api_device, api_events
from rescue_net.tests.factories import RNTestCase, _insert, api_call, as_guest, as_user, make_actor, make_event, make_posko, make_world


class TestOfflineAppApi(RNTestCase):
    def test_disasters_keeps_the_old_shape(self):
        ev = make_event(title="Banjir Uji", event_status="active")
        with as_guest():
            out = api_call("rescue_net.api_events.disasters")
        row = next(d for d in out["disasters"] if d["name"] == ev.name)
        self.assertEqual((row["title"], row["event_status"], row["id"]), ("Banjir Uji", "active", ev.legacy_id))
        self.assertEqual(api_events.health()["backend"], "frappe")

    def test_device_registration_needs_login_and_stays_with_its_owner(self):
        with as_guest(), self.assertRaises(frappe.PermissionError):
            api_call("rescue_net.api_device.register_device", payload='{"device_id": "d-1"}')
        w = make_world()
        op = make_actor(posko=w.posko_a)
        with as_user(op.user):
            out = api_device.register_device({"device_id": "hp-uji-1", "member_name": "Operator",
                                              "disaster_event_id": w.event.name})
            again = api_device.register_device({"device_id": "hp-uji-1"})
        self.assertEqual(out["device"], again["device"])
        self.assertEqual(out["posko"]["id"], w.posko_a.name)
        other = make_actor()
        with as_user(other.user), self.assertRaises(frappe.PermissionError):
            api_device.register_device({"device_id": "hp-uji-1"})

    def test_unit_catalog_and_normalize(self):
        _insert("RN Unit Conversion", conversion_name="Beras karung uji", enabled=1, scope_type="canonical_group",
                canonical_group="beras", from_unit="karung", to_base_unit="kg", factor=50, certainty="standar")
        cat = api_device.unit_catalog()["conversions"]
        self.assertTrue(any(c["from_unit"] == "karung" and c["multiplier"] == 50 for c in cat))
        out = api_device.unit_normalize("Beras", 3, "Karung")
        self.assertEqual(out["canonical_unit"], "karung")

    def test_admin_areas_come_from_frappe_only(self):
        _insert("RN Admin Area", code="99", area_name="Provinsi Uji", level="province", enabled=1)
        rows = api_admin_areas.get_children(level="province")
        self.assertTrue(any(r["code"] == "99" for r in rows))
