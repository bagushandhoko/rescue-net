"""Kelola Posko hub (owner 2026-11-01): managers only, pending counts, warnings, button gate."""

import frappe

from rescue_net import api_posko_manage as pm
from rescue_net.tests.factories import RNTestCase, _insert, as_guest, as_user, make_actor, make_world


class TestPoskoManage(RNTestCase):
    def setUp(self):
        super().setUp()
        self.w = make_world()
        self.mgr = make_actor(posko=self.w.posko_a)
        self.other = make_actor(posko=self.w.posko_b)

    def test_only_manager_opens_hub(self):
        with as_user(self.other.user), self.assertRaises(frappe.PermissionError):
            pm.manage_hub(self.w.posko_a.name)
        with as_guest(), self.assertRaises(Exception):
            pm.manage_hub(self.w.posko_a.name)
        with as_user(self.mgr.user):
            h = pm.manage_hub(self.w.posko_a.name)
        self.assertEqual(h["posko"], self.w.posko_a.name)
        self.assertTrue(any(t["key"] == "settings" for t in h["tools"]))
        self.assertTrue(any("kontak" in w for w in h["warnings"]))  # factory posko has no phone

    def test_button_gate(self):
        with as_guest():
            self.assertFalse(pm.can_manage(self.w.posko_a.name)["can_manage"])
        with as_user(self.other.user):
            self.assertFalse(pm.can_manage(self.w.posko_a.name)["can_manage"])
        with as_user(self.mgr.user):
            self.assertTrue(pm.can_manage(self.w.posko_a.name)["can_manage"])

    def test_list_and_pending_counts(self):
        frappe.db.set_value("RN Posko", self.w.posko_a.name, "officer_in_charge_phone", "0812-0000-1111")
        rel = make_actor(role="relawan")
        prof = _insert("RN Volunteer Profile", user_account=rel.account, disaster_event=self.w.event.name,
                       volunteer_name="Uji", contact="0812", main_skill="medis")
        _insert("RN Volunteer Booking", booking_kind="posko", status="requested", volunteer=prof.name,
                user_account=rel.account, disaster_event=self.w.event.name, posko=self.w.posko_a.name)
        with as_user(self.mgr.user):
            mine = pm.my_managed_poskos()["poskos"]
            h = pm.manage_hub(self.w.posko_a.name)
        names = [p["posko"] for p in mine]
        self.assertIn(self.w.posko_a.name, names)
        self.assertNotIn(self.w.posko_b.name, names)
        self.assertEqual(h["pending"]["relawan"], 1)
        self.assertFalse(any("kontak" in w for w in h["warnings"]))

    def test_expiring_stock_counted(self):
        from frappe.utils import add_days, nowdate
        from rescue_net.services.expiry import record_lot
        frappe.get_doc({"doctype": "RN Stock Observation", "title": "Oralit uji", "posko": self.w.posko_a.name, "item_name": "Oralit",
                        "unit": "sachet", "quantity": 100, "observed_at": frappe.utils.now_datetime()}).insert(ignore_permissions=True)
        record_lot(self.w.posko_a.name, "Oralit", "sachet", 30, add_days(nowdate(), -1))
        with as_user(self.mgr.user):
            h = pm.manage_hub(self.w.posko_a.name)
        self.assertGreaterEqual(h["pending"]["kedaluwarsa"], 1)

    def test_armada_list_for_owner_only(self):
        sp = _insert("RN Transport Space", title="Truk Posko A", provider_name="Truk Posko A", disaster_event=self.w.event.name,
                     coordination_posko=self.w.posko_a.name, transport_type="darat", capacity_weight_kg=1000,
                     transport_status="available", booking_policy="pin_verify", departure_at="2099-01-01 08:00:00")
        _insert("RN Transport Booking", transport_space=sp.name, disaster_event=self.w.event.name, status="requested",
                cargo_desc="Beras", qty_weight_kg=100, verification_pin="ABC123", booked_by_type="posko")
        with as_user(self.other.user), self.assertRaises(frappe.PermissionError):
            pm.armada_list(self.w.posko_a.name)
        with as_user(self.mgr.user):
            r = pm.armada_list(self.w.posko_a.name)
            h = pm.manage_hub(self.w.posko_a.name)
        a = r["armada"][0]
        self.assertEqual((a["name"], a["avail"], len(a["requested"])), (sp.name, "tersedia", 1))
        self.assertTrue(a["requested"][0]["needs_pin"])
        self.assertNotIn("ABC123", frappe.as_json(r))            # the PIN stays with the booker
        self.assertEqual(h["pending"]["pesanan_armada"], 1)

    def test_workbench_owner_tools(self):
        from rescue_net.logistics.needs_offers import create_need, create_stock_observation
        with as_user(self.other.user), self.assertRaises(frappe.PermissionError):
            pm.workbench(self.w.posko_a.name)
        with as_user(self.mgr.user):
            create_need(self.w.posko_a.name, "Air minum", quantity=200, unit="liter", quantity_mode="exact")
            create_stock_observation(self.w.posko_a.name, "Beras", quantity=50, unit="kg", quantity_mode="exact")
            create_stock_observation(self.w.posko_a.name, "Beras", quantity=40, unit="kg", quantity_mode="exact")
            w = pm.workbench(self.w.posko_a.name)
        self.assertIn("Air minum", [n["item_name"] for n in w["needs"]])
        beras = [s for s in w["stock"] if s["item"] == "Beras"]
        self.assertEqual(len(beras), 1)                       # latest per item only
        self.assertIn("operational_status", w["contact"])


class TestArmadaPengaturan(RNTestCase):
    """owner 2026-11-23: pengelola posko mengatur ukuran ruang muat, jenis barang, jadwal, rute sendiri."""

    def setUp(self):
        super().setUp()
        self.w = make_world()
        self.mgr = make_actor(posko=self.w.posko_a)
        self.other = make_actor(posko=self.w.posko_b)
        self.sp = _insert("RN Transport Space", title="Truk A", provider_name="Truk A", disaster_event=self.w.event.name,
                          coordination_posko=self.w.posko_a.name, transport_type="darat", capacity_weight_kg=1000,
                          capacity_committed_kg=300, own_load_kg=100, transport_status="available",
                          booking_policy="pin_verify", departure_at="2099-01-01 08:00:00")

    def _upd(self, **kw):
        from rescue_net.logistics.transport import update_transport_space
        return update_transport_space(self.sp.name, **kw)

    def test_owner_sets_capacity_route_types_schedule(self):
        with as_user(self.mgr.user):
            self._upd(provider_name="Truk Besar A", transport_type="darat", route_origin="Meulaboh",
                      route_destination="Calang", capacity_weight_kg="2000", capacity_volume_m3="12",
                      accepted_cargo_types='["pangan","air","PANGAN"]', departure_at="2099-01-02 07:00:00",
                      cargo_cutoff_at="2099-01-02 05:00:00")
            r = pm.armada_list(self.w.posko_a.name)
        d = frappe.get_doc("RN Transport Space", self.sp.name)
        self.assertEqual((d.title, d.route_origin, d.capacity_weight_kg, d.capacity_volume_m3, d.accepted_cargo_types),
                         ("Truk Besar A", "Meulaboh", 2000, 12, "pangan,air"))
        st = r["armada"][0]["settings"]
        self.assertEqual(st["accepted_cargo_types"], ["pangan", "air"])
        self.assertEqual(st["left_m3"], 12)
        self.assertIn("pangan", r["cargo_types"])

    def test_capacity_cannot_drop_below_booked(self):
        with as_user(self.mgr.user), self.assertRaises(frappe.ValidationError):
            self._upd(capacity_weight_kg="350")      # 100 muatan sendiri + 300 dipesan = 400
        with as_user(self.mgr.user):
            self._upd(capacity_weight_kg="400")

    def test_unknown_cargo_type_and_bad_type_rejected(self):
        with as_user(self.mgr.user), self.assertRaises(frappe.ValidationError):
            self._upd(accepted_cargo_types="pangan,senjata")
        with as_user(self.mgr.user), self.assertRaises(frappe.ValidationError):
            self._upd(transport_type="roket")

    def test_other_posko_cannot_edit(self):
        with as_user(self.other.user), self.assertRaises(frappe.PermissionError):
            self._upd(capacity_weight_kg="5000")

    def test_public_finder_shows_and_filters_cargo_types(self):
        from rescue_net import api_armada
        frappe.db.set_value("RN Transport Space", self.sp.name, "accepted_cargo_types", "medis")
        with as_guest():
            all_rows = api_armada.armada_finder(disaster_event=self.w.event.name)
            pangan = api_armada.armada_finder(disaster_event=self.w.event.name, cargo_type="pangan")
        mine = [a for a in all_rows["rows"] if a["name"] == self.sp.name] if isinstance(all_rows, dict) else []
        self.assertTrue(mine and mine[0]["cargo_types"] == ["Obat & alat medis"])
        self.assertFalse([a for a in pangan["rows"] if a["name"] == self.sp.name])
