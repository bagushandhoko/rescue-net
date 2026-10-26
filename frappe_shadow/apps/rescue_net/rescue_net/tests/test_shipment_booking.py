"""Kirim stok via armada = booking (owner 2026-10-19): same organisation is
approved at once, another organisation's posko distribusi confirms; armada
choices follow the disaster, the posko logistik and the send window."""

import frappe

from rescue_net.api_control_centre import logistik_dispatch_options
from rescue_net.logistics.flows import create_flow
from rescue_net.logistics.transport import confirm_transport_booking, update_transport_space
from rescue_net.tests.factories import (RNTestCase, _insert, as_guest, as_user, make_actor, make_event,
                                        make_posko, make_transport_space, make_world)


class _ShipmentWorld(RNTestCase):
    def setUp(self):
        super().setUp()
        self.w = make_world()
        self.src = make_posko(self.w.event, self.w.org_a, posko_type="logistics")
        self.dst = make_posko(self.w.event, self.w.org_b, posko_type="logistics")
        self.tp_a = make_posko(self.w.event, self.w.org_a, posko_type="transport")
        self.tp_b = make_posko(self.w.event, self.w.org_b, posko_type="transport")
        self.arm_a = make_transport_space(self.tp_a, disaster_event=self.w.event.name,
                                          departure_at="2026-11-02 08:00:00")
        self.arm_b = make_transport_space(self.tp_b, disaster_event=self.w.event.name,
                                          departure_at="2026-11-05 08:00:00")
        self.op = make_actor(posko=self.src)
        _insert("RN Stock Observation", title="Stok Beras", posko=self.src.name, item_name="Beras", quantity=1000, unit="karung",
                observed_at="2026-10-01 08:00:00")

    def send(self, armada, **kw):
        with as_user(self.op.user):
            return create_flow(destination_posko=self.dst.name, item_text="Beras", quantity=10, unit="karung",
                               quantity_mode="exact", source_posko=self.src.name,
                               transport_space=armada.name, weight_kg=kw.pop("weight_kg", 500), **kw)


class TestShipmentBooking(_ShipmentWorld):
    def test_same_org_armada_is_a_confirmed_booking(self):
        r = self.send(self.arm_a, window_from="2026-11-01 00:00:00", window_to="2026-11-03 23:59:59")
        self.assertEqual(r["booking_status"], "confirmed")
        b = frappe.get_doc("RN Transport Booking", r["booking"])
        self.assertEqual(b.distribution_flow, r["flow"])
        self.assertEqual(str(b.window_from)[:10], "2026-11-01")
        self.assertEqual(frappe.db.get_value("RN Distribution Flow", r["flow"], "transport_space"), self.arm_a.name)

    def test_other_org_armada_waits_for_its_posko(self):
        r = self.send(self.arm_b)
        self.assertEqual(r["booking_status"], "requested")
        self.assertFalse(r["verification_pin"])
        self.assertFalse(frappe.db.get_value("RN Distribution Flow", r["flow"], "transport_space"))
        # the sender cannot confirm it; the armada's posko can, without a PIN
        with as_user(self.op.user), self.assertRaises(frappe.PermissionError):
            confirm_transport_booking(r["booking"])
        coord = make_actor(posko=self.tp_b)
        with as_user(coord.user):
            confirm_transport_booking(r["booking"])
        self.assertEqual(frappe.db.get_value("RN Distribution Flow", r["flow"], "transport_space"), self.arm_b.name)

    def test_flow_takes_the_chosen_disaster_only_if_served(self):
        e2 = make_event()
        with self.assertRaisesRegex(frappe.ValidationError, "tidak menangani"):
            self.send(self.arm_a, disaster_event=e2.name)
        doc = frappe.get_doc("RN Posko", self.src.name)
        doc.append("served_events", {"disaster_event": e2.name})
        doc.save(ignore_permissions=True)
        r = self.send(self.arm_a, disaster_event=e2.name)
        self.assertEqual(frappe.db.get_value("RN Distribution Flow", r["flow"], "disaster_event"), e2.name)

    def test_options_follow_disaster_posko_and_window(self):
        with as_guest():
            ids = lambda **kw: [a["id"] for a in logistik_dispatch_options(
                self.w.event.name, source_posko=self.src.name, **kw)["armada"]]
            both = ids()
            nov1to3 = ids(window_from="2026-11-01", window_to="2026-11-03")
        self.assertTrue({self.arm_a.name, self.arm_b.name} <= set(both))
        self.assertIn(self.arm_a.name, nov1to3)
        self.assertNotIn(self.arm_b.name, nov1to3)
        # armada B now serves only another posko logistik -> not offered to src
        coord = make_actor(posko=self.tp_b)
        with as_user(coord.user):
            update_transport_space(self.arm_b.name, served_poskos=[self.dst.name])
        with as_guest():
            self.assertNotIn(self.arm_b.name, ids())
        # armada A moved to another disaster only -> gone from this one
        e2 = make_event()
        coord_a = make_actor(posko=self.tp_a)
        with as_user(coord_a.user):
            update_transport_space(self.arm_a.name, served_events=[e2.name])
        with as_guest():
            self.assertNotIn(self.arm_a.name, ids())
            opt = logistik_dispatch_options(e2.name)
        self.assertIn(self.arm_a.name, [a["id"] for a in opt["armada"]])

    def test_armada_that_cannot_take_cargo_is_not_offered(self):
        frappe.db.set_value("RN Transport Space", self.arm_b.name, "transport_status", "in_transit")
        with as_guest():
            ids = [a["id"] for a in logistik_dispatch_options(self.w.event.name, source_posko=self.src.name)["armada"]]
        self.assertNotIn(self.arm_b.name, ids)
        self.assertIn(self.arm_a.name, ids)


class TestFirstMile(_ShipmentWorld):
    """Langkah 3 (owner 2026-10-20): how the cargo reaches the main armada's
    handover point — antar sendiri / antrean / transporter."""

    def test_transporter_books_a_second_leg(self):
        courier = make_transport_space(self.tp_a, disaster_event=self.w.event.name)
        r = self.send(self.arm_b, first_mile="transporter", first_mile_space=courier.name)
        self.assertEqual(r["booking_status"], "requested")             # main armada, other org
        self.assertEqual(r["first_mile_status"], "confirmed")          # courier, same org
        fb = frappe.get_doc("RN Transport Booking", r["first_mile_booking"])
        self.assertEqual(fb.booking_leg, "first_mile")
        self.assertEqual(frappe.db.get_value("RN Distribution Flow", r["flow"], "first_mile_space"), courier.name)
        self.assertEqual(frappe.db.get_value("RN Transport Booking", r["booking"], "delivery_method"), "self_deliver")
        # confirming the main booking sets the main armada, not the courier
        coord = make_actor(posko=self.tp_b)
        with as_user(coord.user):
            confirm_transport_booking(r["booking"])
        flow = frappe.get_doc("RN Distribution Flow", r["flow"])
        self.assertEqual((flow.transport_space, flow.first_mile_space), (self.arm_b.name, courier.name))

    def test_transporter_without_main_armada_is_the_main_leg(self):
        r = self.send_direct(first_mile="transporter", first_mile_space=self.arm_b.name)
        self.assertEqual(frappe.db.get_value("RN Transport Booking", r["booking"], "booking_leg"), "main")
        self.assertIsNone(r["first_mile_booking"])

    def test_queue_waits_for_a_posko_distribusi_then_claim_sets_first_leg(self):
        from rescue_net.api_control_centre import posko_distribusi_board
        from rescue_net.logistics.transport import claim_distribution_flow
        r = self.send(self.arm_a, first_mile="queue")                   # main: same org, confirmed
        self.assertEqual(frappe.db.get_value("RN Distribution Flow", r["flow"], "transport_space"), self.arm_a.name)
        with as_guest():
            q = posko_distribusi_board(disaster_event=self.w.event.name)["pickup_queue"]
        row = [x for x in q if x.get("flow") == r["flow"]]
        self.assertTrue(row and row[0]["first_leg"])
        courier = make_transport_space(self.tp_b, disaster_event=self.w.event.name)
        coord = make_actor(posko=self.tp_b)
        with as_user(coord.user):
            claim_distribution_flow(r["flow"], transport_space=courier.name)
        self.assertEqual(frappe.db.get_value("RN Distribution Flow", r["flow"], "first_mile_space"), courier.name)
        with as_guest():
            q = posko_distribusi_board(disaster_event=self.w.event.name)["pickup_queue"]
        self.assertNotIn(r["flow"], [x.get("flow") for x in q])

    def test_self_delivery_and_pending_booking_stay_out_of_the_queue(self):
        from rescue_net.api_control_centre import posko_distribusi_board
        own = self.send_direct(first_mile="self_deliver")
        booked = self.send(self.arm_b)                                  # requested, no armada yet
        with as_guest():
            q = [x.get("flow") for x in posko_distribusi_board(disaster_event=self.w.event.name)["pickup_queue"]]
        self.assertNotIn(own["flow"], q)
        self.assertNotIn(booked["flow"], q)

    def send_direct(self, **kw):
        with as_user(self.op.user):
            return create_flow(destination_posko=self.dst.name, item_text="Beras", quantity=10, unit="karung",
                               quantity_mode="exact", source_posko=self.src.name, weight_kg=500, **kw)


class TestSendWithinStock(_ShipmentWorld):
    """Owner 2026-10-20: a posko never sends beyond its stock."""

    def direct(self, qty, unit="karung"):
        with as_user(self.op.user):
            return create_flow(destination_posko=self.dst.name, item_text="Beras", quantity=qty, unit=unit,
                               quantity_mode="exact", source_posko=self.src.name)

    def test_cannot_send_more_than_available(self):
        with self.assertRaisesRegex(frappe.ValidationError, "Stok tidak cukup"):
            self.direct(1001)
        self.direct(600)
        with self.assertRaisesRegex(frappe.ValidationError, "tersedia 400"):
            self.direct(500)                       # 1000 - 600 already sent
        self.direct(400)

    def test_cancelled_flow_returns_to_available(self):
        from rescue_net.logistics.flows import update_flow_status
        flow = self.direct(1000)["flow"]
        with as_user(self.op.user):
            update_flow_status(flow, "cancelled")
        self.direct(1000)

    def test_unit_and_unknown_item(self):
        with self.assertRaisesRegex(frappe.ValidationError, "Satuan"):
            self.direct(1, unit="ikat")   # no conversion row (kg now converts via the table)
        with as_user(self.op.user), self.assertRaisesRegex(frappe.ValidationError, "Belum ada stok"):
            create_flow(destination_posko=self.dst.name, item_text="Tenda", quantity=1, unit="unit",
                        quantity_mode="exact", source_posko=self.src.name)

    def test_send_form_shows_available_to_the_posko_only(self):
        self.direct(250)
        with as_user(self.op.user):
            st = logistik_dispatch_options(self.w.event.name, source_posko=self.src.name, item="Beras")["stock"]
        self.assertEqual((st["observed"], st["sent_since"], st["available"]), (1000, 250, 750))
        with as_guest():
            self.assertIsNone(logistik_dispatch_options(self.w.event.name, source_posko=self.src.name,
                                                        item="Beras")["stock"])


class TestCargoTerms(_ShipmentWorld):
    """Owner 2026-10-23: an armada owner records syarat barang (packing, per-koli cap,
    prohibited items, documents, cut-off); senders see them in the send form."""

    def test_create_with_terms_and_they_reach_the_send_form(self):
        from rescue_net.logistics.transport import create_transport_space
        owner = make_actor(posko=self.tp_a)
        with as_user(owner.user):
            out = create_transport_space(
                self.tp_a.name, "Garuda Cargo GA-1204", transport_type="udara", disaster_event=self.w.event.name,
                capacity_weight_kg=5000, departure_at="2026-11-02 08:00:00",
                packing_required="wajib", packing_spec="Dus tertutup, label isi + tujuan", max_piece_weight_kg=25,
                prohibited_items="BBM, baterai lepas", documents_required="Surat jalan, packing list",
                cargo_requirements="Maks 1 palet per pengirim", cargo_cutoff_at="2026-11-02 04:00:00")
        d = frappe.get_doc("RN Transport Space", out["transport"])
        self.assertEqual((d.packing_required, d.max_piece_weight_kg), ("wajib", 25))
        with as_user(self.op.user):
            opt = logistik_dispatch_options(self.w.event.name, source_posko=self.src.name, item="Beras",
                                            window_from="2026-11-01", window_to="2026-11-03")
        row = next(a for a in opt["armada"] if a["id"] == d.name)
        t = row["syarat"]
        self.assertTrue(t["ada"])
        self.assertEqual((t["packing_label"], t["maks_koli_kg"], t["terlarang"], t["batas_serah"]),
                         ("Packing wajib", 25.0, "BBM, baterai lepas", "2026-11-02 04:00"))
        plain = next(a for a in opt["armada"] if a["id"] == self.arm_a.name)
        self.assertFalse(plain["syarat"]["ada"])

    def test_update_changes_only_given_terms_and_validates(self):
        owner = make_actor(posko=self.tp_a)
        with as_user(owner.user):
            update_transport_space(self.arm_a.name, packing_required="dianjurkan", prohibited_items="Aerosol")
            update_transport_space(self.arm_a.name, max_piece_weight_kg=20)
        d = frappe.get_doc("RN Transport Space", self.arm_a.name)
        self.assertEqual((d.packing_required, d.prohibited_items, d.max_piece_weight_kg), ("dianjurkan", "Aerosol", 20))
        with as_user(owner.user), self.assertRaises(frappe.ValidationError):
            update_transport_space(self.arm_a.name, packing_required="mungkin")
        with as_user(owner.user), self.assertRaisesRegex(frappe.ValidationError, "sebelum waktu berangkat"):
            update_transport_space(self.arm_a.name, cargo_cutoff_at="2026-11-09 00:00:00")

    def test_only_the_posko_team_may_set_terms(self):
        stranger = make_actor()
        with as_user(stranger.user), self.assertRaises(frappe.PermissionError):
            update_transport_space(self.arm_a.name, packing_required="wajib")


class TestTermsAck(_ShipmentWorld):
    """A sender must confirm the armada's syarat barang before booking (owner 2026-10-23)."""

    def setUp(self):
        super().setUp()
        with as_user(make_actor(posko=self.tp_b).user):
            update_transport_space(self.arm_b.name, packing_required="wajib", prohibited_items="BBM")

    def test_booking_without_ack_is_refused_and_with_ack_is_recorded(self):
        from rescue_net.logistics.transport import book_transport_space
        with as_user(self.op.user), self.assertRaisesRegex(frappe.ValidationError, "memenuhi syarat"):
            book_transport_space(self.arm_b.name, cargo_desc="Beras", qty_weight_kg=10, delivery_method="self_deliver")
        with as_user(self.op.user):
            r = book_transport_space(self.arm_b.name, cargo_desc="Beras", qty_weight_kg=10,
                                     delivery_method="self_deliver", terms_ack=1)
        self.assertEqual(frappe.db.get_value("RN Transport Booking", r["booking"], "terms_ack"), 1)

    def test_armada_without_terms_needs_no_ack(self):
        from rescue_net.logistics.transport import book_transport_space
        with as_user(self.op.user):
            r = book_transport_space(self.arm_a.name, cargo_desc="Beras", qty_weight_kg=10, delivery_method="self_deliver")
        self.assertEqual(frappe.db.get_value("RN Transport Booking", r["booking"], "terms_ack"), 0)

    def test_send_stock_wizard_requires_ack_on_the_main_armada(self):
        with self.assertRaisesRegex(frappe.ValidationError, "memenuhi syarat"):
            self.send(self.arm_b, window_from="2026-11-04 00:00:00", window_to="2026-11-06 23:59:59")
        r = self.send(self.arm_b, window_from="2026-11-04 00:00:00", window_to="2026-11-06 23:59:59", terms_ack=1)
        self.assertEqual(frappe.db.get_value("RN Transport Booking", r["booking"], "terms_ack"), 1)


class TestSameOrgMemberBooks(_ShipmentWorld):
    """A plain member of the armada's organisation books (auto-confirmed) instead
    of taking the armada directly (E2E 2026-10-25)."""

    def test_member_gets_confirmed_booking(self):
        member = make_actor(posko=self.src, org=self.w.org_a)          # member of org_a, operator of src only
        with as_user(member.user):
            r = create_flow(destination_posko=self.dst.name, item_text="Beras", quantity=10, unit="karung",
                            quantity_mode="exact", source_posko=self.src.name, transport_space=self.arm_a.name, weight_kg=100)
        self.assertEqual(r["booking_status"], "confirmed")
        self.assertEqual(frappe.db.get_value("RN Distribution Flow", r["flow"], "transport_space"), self.arm_a.name)


class TestMovementsReadable(_ShipmentWorld):
    def test_outgoing_rows_show_posko_title_and_status_name(self):
        from rescue_net.api_control_centre import logistik_board
        r = self.send(self.arm_a)
        with as_user(self.op.user):
            b = logistik_board(posko=self.src.name, disaster_event=self.w.event.name)
        row = next(m for m in b["movements_out"] if m["flow"] == r["flow"])
        self.assertEqual(row["tujuan"], self.dst.title)
        self.assertEqual(row["tujuan_posko"], self.dst.name)
        self.assertTrue(row["status_label"])
        self.assertNotIn("_", row["status_label"])
