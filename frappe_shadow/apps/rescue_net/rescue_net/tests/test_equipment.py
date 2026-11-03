"""Owner 2026-11-03: Posko Alat Kerja / Support — an inventory of tools with detailed specs per category."""

import json

import frappe

from rescue_net import api_equipment as api
from rescue_net import api_recovery_support as rs
from rescue_net.tests.factories import (RNTestCase, api_call, as_guest, as_user, make_actor, make_event, make_org,
                                        make_posko)


class TestEquipmentPosko(RNTestCase):
    def setUp(self):
        super().setUp()
        self.event = make_event(event_status="active")
        self.org = make_org(verification_status="verified")
        self.posko = make_posko(self.event, self.org, posko_type="equipment")
        self.other_posko = make_posko(self.event, self.org)
        self.manager = make_actor(org=self.org, org_role="owner", posko=self.posko)
        self.stranger = make_actor(role="citizen")

    def genset(self, **kw):
        args = dict(posko=self.posko.name, category="genset", resource_name="Genset 50 kVA #1", quantity=2,
                    brand="Perkins", model="P50", manufacture_year=2020, serial_number="GS-SERIAL-77",
                    tool_condition="baik",
                    specs=json.dumps({"power_kva": "50", "phase": "3 fase", "fuel_type": "solar", "fuel_use_lph": "11.5",
                                      "not_a_genset_key": "x"}),
                    operator_included=1, operator_count=1)
        args.update(kw)
        with as_user(self.manager.user):
            return api.save_equipment(**args)["resource_profile"]

    def test_specs_saved_cleaned_and_shown(self):
        rp = self.genset()
        row = frappe.db.get_value("RN Resource Profile", rp, ["owner_type", "owner_id", "specs", "unit", "disaster_event"],
                                  as_dict=True)
        self.assertEqual((row.owner_type, row.owner_id, row.disaster_event), ("posko", self.posko.name, self.event.name))
        self.assertEqual(json.loads(row.specs), {"power_kva": 50, "phase": "3 fase", "fuel_type": "solar", "fuel_use_lph": 11.5})
        self.assertEqual(row.unit, "unit")
        with as_guest():
            d = api_call("rescue_net.api_equipment.posko_equipment", posko=self.posko.name)
        t = d["tools"][0]
        self.assertIn({"label": "Kapasitas", "value": "50 kVA"}, t["spec_rows"])
        self.assertIsNone(t["serial_number"])                      # identity number for its managers only
        self.assertFalse(d["can_manage"])
        self.assertEqual(d["summary"][0]["group"], "Listrik & Penerangan")
        self.assertEqual(d["totals"]["units"], 2)
        with as_user(self.manager.user):
            self.assertEqual(api.posko_equipment(self.posko.name)["tools"][0]["serial_number"], "GS-SERIAL-77")
        with as_guest():
            dd = api_call("rescue_net.api_recovery_support.tool_detail", resource_profile=rp)
        self.assertEqual(dd["condition_label"], "Baik / siap pakai")
        self.assertIn("Konsumsi BBM", [x["label"] for x in dd["spec_rows"]])
        with as_guest():
            lst = api_call("rescue_net.api_equipment.equipment_poskos", disaster_event=self.event.name)
        self.assertIn(self.posko.name, [p["name"] for p in lst["poskos"]])

    def test_bad_specs_refused(self):
        for bad in ({"power_kva": "lima puluh"}, {"phase": "5 fase"}, {"power_kva": -1}):
            with self.assertRaises(frappe.ValidationError, msg=str(bad)):
                self.genset(specs=json.dumps(bad))
        with self.assertRaises(frappe.ValidationError):
            self.genset(manufacture_year=1800)
        with self.assertRaises(frappe.ValidationError):
            self.genset(category="kapal_selam")

    def test_only_posko_managers(self):
        with as_user(self.stranger.user), self.assertRaises(frappe.PermissionError):
            api.save_equipment(self.posko.name, category="tenda", resource_name="Tenda peleton")
        with as_guest(), self.assertRaises(frappe.PermissionError):
            api_call("rescue_net.api_equipment.save_equipment", posko=self.posko.name, resource_name="x")
        rp = self.genset()
        with as_user(self.stranger.user), self.assertRaises(frappe.PermissionError):
            rs.upload_tool_photo(rp, "a.png", "")
        # a tool of this posko cannot be edited through another posko
        other_mgr = make_actor(org=self.org, org_role="member", posko=self.other_posko)
        with as_user(self.manager.user):
            api.save_equipment(self.posko.name, resource_profile=rp,
                               specs=json.dumps({"power_kva": 60}), resource_name="Genset 60 kVA")
        self.assertEqual(json.loads(frappe.db.get_value("RN Resource Profile", rp, "specs")), {"power_kva": 60})
        tent = None
        with as_user(self.manager.user):
            tent = api.save_equipment(self.posko.name, category="tenda", resource_name="Tenda peleton",
                                      specs=json.dumps({"tent_type": "peleton", "capacity_people": 40}))["resource_profile"]
            with self.assertRaises(frappe.PermissionError):
                api.save_equipment(self.other_posko.name, resource_profile=tent, resource_name="dibajak")
        self.assertTrue(other_mgr)

    def test_several_photos(self):
        import base64
        def png(i):                      # different bytes: Frappe stores identical files once
            return base64.b64encode(b"\x89PNG\r\n\x1a\n" + bytes([i]) * 32).decode()
        rp = self.genset()
        with as_user(self.manager.user):
            for i in range(rs.MAX_PHOTOS):
                r = rs.upload_tool_photo(rp, f"foto-{i}.png", png(i))
            self.assertEqual(len(r["photos"]), rs.MAX_PHOTOS)
            with self.assertRaises(frappe.ValidationError):
                rs.upload_tool_photo(rp, "kebanyakan.png", png(99))
            first, second = r["photos"][0]["url"], r["photos"][1]["url"]
            r = rs.remove_tool_photo(rp, first)
        self.assertEqual(frappe.db.get_value("RN Resource Profile", rp, "photo_url"), second)
        with as_user(self.stranger.user), self.assertRaises(frappe.PermissionError):
            rs.remove_tool_photo(rp, second)
        with as_guest():
            d = api_call("rescue_net.api_recovery_support.tool_detail", resource_profile=rp)
        self.assertEqual(len(d["photos"]), rs.MAX_PHOTOS - 1)
