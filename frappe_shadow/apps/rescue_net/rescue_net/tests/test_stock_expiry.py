"""Kedaluwarsa stok (Fase 10d): lot dari penerimaan, alokasi FEFO, stok kedaluwarsa tak terhitung tersedia."""

import frappe
from frappe.utils import add_days, add_to_date, now_datetime, nowdate

from rescue_net import api_kitchen
from rescue_net import api_logistics as api
from rescue_net import api_public_needs, api_stock_expiry
from rescue_net.services import expiry
from rescue_net.tests.factories import _insert, as_guest, as_user
from rescue_net.tests.test_logistics_chain import LogisticsTestCase

ITEM, UNIT = "Beras 5 kg", "karung"


class ExpiryBase(LogisticsTestCase):
    def posko(self):
        return self.w.posko_a.name

    def snapshot(self, qty, item=ITEM, unit=UNIT):
        _insert("RN Stock Observation", title=f"{item} - uji", posko=self.posko(), disaster_event=self.w.event.name,
                item_name=item, quantity=qty, unit=unit, quantity_mode="exact", stock_state="available",
                observed_at=add_to_date(now_datetime(), hours=-1))

    def lot(self, qty, days, batch=None, item=ITEM):
        return expiry.record_lot(self.posko(), item, UNIT, qty, add_days(nowdate(), days), batch, self.w.event.name, "uji")


class TestLotsFromReceipts(ExpiryBase):
    def _offer_with_expiry(self, days):
        offer = self.offer_to_a()
        frappe.db.set_value("RN Aid Offer", offer, {"expiry_date": add_days(nowdate(), days), "batch_no": "B-7"})
        return offer

    def test_direct_offer_receipt_records_lot_with_expiry_and_batch(self):
        offer = self._offer_with_expiry(20)
        with as_user(self.op_a.user):
            api.receive_aid_offer_and_update_stock(offer)
        lot = frappe.get_all("RN Stock Batch", filters={"posko": self.posko()}, fields=["quantity", "batch_no", "expiry_date", "source"])
        self.assertEqual([(l.quantity, l.batch_no) for l in lot], [(10, "B-7")])
        self.assertEqual(str(lot[0].expiry_date), add_days(nowdate(), 20))

    def test_flow_receipt_copies_expiry_from_its_offer(self):
        offer = self._offer_with_expiry(15)
        flow = self.flow_to_a(offer=offer)
        self.move(flow, "assigned_pickup", "dispatched", "arrived_at_posko")
        with as_user(self.op_a.user):
            api.receive_flow_and_update_stock(flow, 10, UNIT)
        self.assertEqual(frappe.db.count("RN Stock Batch", {"posko": self.posko()}), 1)

    def test_offer_without_expiry_records_nothing_and_receipt_still_works(self):
        offer = self.offer_to_a()
        with as_user(self.op_a.user):
            api.receive_aid_offer_and_update_stock(offer)
        self.assertEqual(frappe.db.count("RN Stock Batch", {"posko": self.posko()}), 0)


class TestFefoAllocation(ExpiryBase):
    def test_remaining_stock_sits_in_latest_expiring_lots(self):
        self.lot(10, -5, "LAMA")      # sudah kedaluwarsa
        self.lot(10, 10, "BARU")
        self.snapshot(10)             # 10 tersisa: FEFO -> yang lama sudah habis dipakai, sisa di lot baru
        self.assertEqual(expiry.expired_quantity(self.posko(), ITEM, UNIT), 0)
        self.snapshot(15)             # 15 tersisa: 10 di lot baru + 5 di lot lama (kedaluwarsa)
        self.assertEqual(expiry.expired_quantity(self.posko(), ITEM, UNIT), 5)
        lots = expiry.lots_status(self.posko(), ITEM, UNIT)
        self.assertEqual([(l["batch_no"], l["quantity"]) for l in lots], [("LAMA", 5), ("BARU", 10)])  # urut FEFO

    def test_stock_beyond_lots_is_treated_as_undated(self):
        self.lot(4, -1)
        self.snapshot(30)
        self.assertEqual(expiry.expired_quantity(self.posko(), ITEM, UNIT), 4)
        self.assertEqual(sum(l["quantity"] for l in expiry.lots_status(self.posko(), ITEM, UNIT)), 4)

    def test_kitchen_usage_is_taken_from_the_oldest_lot_first(self):
        self.lot(10, -2, "LAMA")
        self.lot(10, 30, "BARU")
        self.snapshot(20)
        with as_user(self.op_a.user):
            api_kitchen.create_production(self.posko(), "Nasi", 50, [{"item_name": ITEM, "quantity": 10, "unit": UNIT}])
        self.assertEqual(expiry.expired_quantity(self.posko(), ITEM, UNIT), 0)   # 10 terpakai = lot lama habis

    def test_no_lots_or_unit_mismatch_never_raises(self):
        self.assertEqual(expiry.lots_status(self.posko(), ITEM, UNIT), [])
        self.lot(5, -1)
        self.snapshot(5, unit="kg")                  # satuan snapshot beda -> tak bisa dialokasikan, tidak error
        self.assertEqual(expiry.expired_quantity(self.posko(), ITEM, UNIT), 0)


class TestReportAndBoard(ExpiryBase):
    def test_report_states_and_medical_window(self):
        self.snapshot(50)
        self.lot(10, -1, "X")
        self.lot(10, 20, "Y")
        self.lot(30, 100, "Z")
        r = expiry.expiring_report(self.posko())
        self.assertEqual({row["batch_no"]: row["state"] for row in r["rows"]}, {"X": "expired", "Y": "soon", "Z": "ok"})
        self.assertEqual((r["expired"], r["soon"]), (1, 1))
        self.assertEqual((expiry.window_days("Obat batuk"), expiry.window_days("Beras")), (60, 30))

    def test_operator_only_and_add_lot_does_not_change_stock(self):
        self.snapshot(8)
        with as_user(self.op_a.user):
            out = api_stock_expiry.add_lot(self.posko(), ITEM, UNIT, 8, add_days(nowdate(), 5), "M1")
            self.assertEqual(out["report"]["soon"], 1)
            with self.assertRaises(frappe.ValidationError):
                api_stock_expiry.add_lot(self.posko(), ITEM, UNIT, 8, None)
        for u in (self.op_b.user, self.member_a.user):
            with as_user(u), self.assertRaises(frappe.PermissionError):
                api_stock_expiry.expiring(self.posko())
        with as_guest(), self.assertRaises(frappe.ValidationError):
            api_stock_expiry.expiring(self.posko())
        q = frappe.get_all("RN Stock Observation", filters={"posko": self.posko()}, fields=["quantity"])
        self.assertEqual([x.quantity for x in q], [8])

    def test_expired_stock_does_not_close_the_public_need_gap(self):
        from rescue_net.tests.factories import make_posko

        pub = make_posko(self.w.event, public_detail="public", city_name="Kota Uji")
        _insert("RN Logistic Need", title="butuh beras", posko=pub.name, disaster_event=self.w.event.name,
                item_name=ITEM, quantity=10, unit=UNIT, urgency="critical")
        _insert("RN Stock Observation", title="s", posko=pub.name, disaster_event=self.w.event.name, item_name=ITEM,
                quantity=10, unit=UNIT, quantity_mode="exact", stock_state="available", observed_at=now_datetime())
        with as_guest():
            before = api_public_needs.board(event=self.w.event.name)
        self.assertEqual(before["needs"], [])                          # stok 10 menutup kebutuhan 10
        expiry.record_lot(pub.name, ITEM, UNIT, 10, add_days(nowdate(), -3), "BUSUK", self.w.event.name, "uji")
        with as_guest():
            after = api_public_needs.board(event=self.w.event.name)
        self.assertEqual([r["gap"] for r in after["needs"]], [10])      # stok kedaluwarsa tidak menutup kebutuhan


class TestAppendOnly(ExpiryBase):
    def test_lots_cannot_be_edited_or_deleted(self):
        name = self.lot(5, 10)
        doc = frappe.get_doc("RN Stock Batch", name)
        doc.quantity = 99
        with self.assertRaises(frappe.ValidationError):
            doc.save(ignore_permissions=True)
        with self.assertRaises(frappe.ValidationError):
            frappe.get_doc("RN Stock Batch", name).delete()

    def test_daily_notify_is_quiet_when_nothing_expires(self):
        self.snapshot(5)
        self.lot(5, 90)
        expiry.daily_expiry_notify()
        self.assertEqual(frappe.db.count("RN Notification Log", {"event_key": "stock_expiry"}), 0)

    def test_daily_notify_sends_once_per_posko_when_something_expires(self):
        frappe.db.set_value("RN Posko", self.posko(), {"notify_whatsapp_enabled": 1, "notify_whatsapp_numbers": "081200000009"})
        self.snapshot(5)
        self.lot(5, -2)
        expiry.daily_expiry_notify()
        logs = frappe.get_all("RN Notification Log", filters={"event_key": "stock_expiry"}, fields=["status", "body"])
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0].status, "simulated")             # tanpa gateway aktif: hanya dicatat
        self.assertIn("1 barang kedaluwarsa", logs[0].body)
