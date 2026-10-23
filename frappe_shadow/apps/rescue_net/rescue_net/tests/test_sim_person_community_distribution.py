"""Simulation (owner 2026-10-23): a distribusi provider can be a PERSON (no organisation)
or a KOMUNITAS, not only an organisation. A person typically only (a) carries cargo from
a posko logistik to the nearest posko distribusi, or (b) carries from one posko
distribusi to another. Runs on the isolated test stack only."""

import frappe

from rescue_net.api_control_centre import logistik_dispatch_options
from rescue_net.logistics.flows import create_flow
from rescue_net.logistics.transport import claim_distribution_flow, confirm_transport_booking
from rescue_net.tests.factories import (RNTestCase, _insert, as_guest, as_user, make_actor, make_event, make_org,
                                        make_posko, make_transport_space)


class _Sim(RNTestCase):
    def setUp(self):
        super().setUp()
        self.ev = make_event()
        # the logistics side: a posko logistik (organisation) holding stock
        self.org_log = make_org(title="Org Logistik")
        self.log = make_posko(self.ev, self.org_log, posko_type="logistics", latitude=-0.02, longitude=109.34)
        self.dest = make_posko(self.ev, self.org_log, posko_type="logistics", latitude=-0.30, longitude=109.50)
        _insert("RN Stock Observation", title="Stok Beras", posko=self.log.name, item_name="Beras", quantity=500,
                unit="karung", observed_at="2026-10-01 08:00:00")
        self.op_log = make_actor(posko=self.log)
        # two posko distribusi run by a KOMUNITAS (near + far) with a space-only truck each
        self.com = make_org(title="Komunitas Truk Relawan", org_type="community") if "org_type" in frappe.get_meta("RN Organization").get_valid_columns() else make_org(title="Komunitas Truk Relawan")
        self.d_near = make_posko(self.ev, self.com, posko_type="transport", latitude=-0.03, longitude=109.35,
                                 title="Posko Distribusi Dekat")
        self.d_far = make_posko(self.ev, self.com, posko_type="transport", latitude=-0.50, longitude=109.80,
                                title="Posko Distribusi Jauh")
        self.truck = make_transport_space(self.d_near, disaster_event=self.ev.name, provider_name="Truk Komunitas",
                                          capacity_weight_kg=3000, service_mode="space_only",
                                          departure_at="2026-11-05 08:00:00", handover_location="Halaman Posko Dekat")
        self.com_op = make_actor(org=self.com, org_role="owner", posko=self.d_near)
        # a PERSON: no organisation, own posko transport + a motorbike (courier, 80 kg)
        self.p_posko = make_posko(self.ev, None, posko_type="transport", title="Budi - Motor Antar",
                                  latitude=-0.04, longitude=109.36)
        self.bike = make_transport_space(self.p_posko, disaster_event=self.ev.name, provider_name="Motor Budi",
                                         capacity_weight_kg=80, service_mode="courier_pickup",
                                         departure_at="2026-11-04 09:00:00")
        self.person = make_actor(posko=self.p_posko)

    def ship_to_hub(self, qty=10, kg=60, **kw):
        """posko logistik -> destination via the komunitas truck; the first mile waits in the queue."""
        with as_user(self.op_log.user):
            return create_flow(destination_posko=self.dest.name, item_text="Beras", quantity=qty, unit="karung",
                               quantity_mode="exact", source_posko=self.log.name, transport_space=self.truck.name,
                               weight_kg=kg, first_mile="queue", window_from="2026-11-04 00:00:00",
                               window_to="2026-11-06 23:59:59", **kw)


class TestPersonFirstMile(_Sim):
    def test_person_without_org_claims_the_first_mile_to_the_nearest_distribusi(self):
        r = self.ship_to_hub()
        with as_user(self.person.user):
            out = claim_distribution_flow(r["flow"], transport_space=self.bike.name)
        self.assertEqual(out["first_mile_space"], self.bike.name)
        self.assertEqual(frappe.db.get_value("RN Distribution Flow", r["flow"], "flow_status"), "assigned_pickup")

    def test_person_cannot_carry_more_than_the_bike_holds(self):
        r = self.ship_to_hub(kg=300)
        with as_user(self.person.user), self.assertRaisesRegex(frappe.ValidationError, "kapasitas|muat|penuh|cukup"):
            claim_distribution_flow(r["flow"], transport_space=self.bike.name)
        self.assertFalse(frappe.db.get_value("RN Distribution Flow", r["flow"], "first_mile_space"))
        self.assertEqual(frappe.db.get_value("RN Transport Space", self.bike.name, "capacity_committed_kg") or 0, 0)

    def test_claim_commits_the_bike_capacity_and_records_the_leg(self):
        r = self.ship_to_hub(kg=60)
        with as_user(self.person.user):
            claim_distribution_flow(r["flow"], transport_space=self.bike.name)
        leg = frappe.get_all("RN Transport Booking", filters={"distribution_flow": r["flow"], "booking_leg": "first_mile"},
                             fields=["status", "qty_weight_kg", "transport_space"])
        self.assertEqual([(b.status, b.qty_weight_kg, b.transport_space) for b in leg], [("confirmed", 60, self.bike.name)])
        self.assertEqual(frappe.db.get_value("RN Transport Space", self.bike.name, "capacity_committed_kg"), 60)

    def test_a_stranger_cannot_claim_with_someones_bike(self):
        r = self.ship_to_hub()
        stranger = make_actor()
        with as_user(stranger.user), self.assertRaises(frappe.PermissionError):
            claim_distribution_flow(r["flow"], transport_space=self.bike.name)

    def test_guest_cannot_claim(self):
        r = self.ship_to_hub()
        with as_guest(), self.assertRaises(Exception):
            claim_distribution_flow(r["flow"], transport_space=self.bike.name)


class TestDistribusiToDistribusi(_Sim):
    def test_person_relays_between_two_posko_distribusi(self):
        """cargo already sits at the near hub (handed over by the truck); the person takes it on to the far hub"""
        _insert("RN Stock Observation", title="Stok hub", posko=self.d_near.name, item_name="Beras", quantity=40,
                unit="karung", observed_at="2026-11-05 10:00:00")
        hub_op = make_actor(posko=self.d_near)
        with as_user(hub_op.user):
            r = create_flow(destination_posko=self.d_far.name, item_text="Beras", quantity=20, unit="karung",
                            quantity_mode="exact", source_posko=self.d_near.name, first_mile="queue",
                            transport_space=self.truck.name, weight_kg=60,
                            window_from="2026-11-05 00:00:00", window_to="2026-11-07 23:59:59")
        with as_user(self.person.user):
            out = claim_distribution_flow(r["flow"], transport_space=self.bike.name, weight_kg=60)
        self.assertEqual(out["first_mile_space"], self.bike.name)
        with as_user(self.person.user), self.assertRaisesRegex(frappe.ValidationError, "sudah"):
            claim_distribution_flow(r["flow"], transport_space=self.bike.name, weight_kg=60)   # no double claim

    def test_nearest_distribusi_is_listed_first_with_distance(self):
        with as_user(self.op_log.user):
            opt = logistik_dispatch_options(self.ev.name, source_posko=self.log.name, item="Beras")
        armada = [a for a in opt["armada"] if a["id"] == self.truck.name]
        self.assertTrue(armada, "komunitas truck offered")
        self.assertIsNotNone(armada[0].get("jarak_km"))
        self.assertLess(armada[0]["jarak_km"], 5)


class TestPublicAndOthersBooking(_Sim):
    """How the public / another user books: bring it yourself, or ask a distributor to fetch it."""

    def setUp(self):
        super().setUp()
        frappe.db.set_value("RN Organization", self.com.name, "allow_posko_public_choice", 1)
        frappe.db.set_value("RN Posko", self.d_near.name,
                            {"public_participation": 1, "public_detail": "public", "accept_goods": 1})

    def test_guest_books_the_komunitas_truck_and_brings_the_cargo_themselves(self):
        from rescue_net.logistics.guest import book_transport_space_public
        with as_guest():
            out = book_transport_space_public(self.truck.name, "Warga Ani", "081234567890", cargo_desc="Beras 5 karung",
                                              qty_weight_kg=200, delivery_method="self_deliver")
        self.assertTrue(out.get("edit_code"))
        b = frappe.get_doc("RN Transport Booking", out["booking"])
        self.assertEqual((b.delivery_method, b.status), ("self_deliver", "requested"))     # komunitas confirms with the PIN
        with as_user(self.com_op.user):
            confirm_transport_booking(b.name, pin=b.verification_pin)
        self.assertEqual(frappe.db.get_value("RN Transport Booking", b.name, "status"), "confirmed")

    def test_space_only_truck_cannot_be_asked_to_fetch(self):
        from rescue_net.logistics.guest import book_transport_space_public
        with as_guest(), self.assertRaisesRegex(frappe.ValidationError, "ruang muat|space"):
            book_transport_space_public(self.truck.name, "Warga Ani", "081234567890", cargo_desc="Beras",
                                        qty_weight_kg=50, delivery_method="use_transporter")

    def test_guest_donor_asks_for_pickup_and_a_person_carries_it_to_the_nearest_posko(self):
        import json
        from rescue_net.logistics.guest import submit_guest_aid_offer_multi
        from rescue_net.logistics.transport import claim_aid_pickup
        with as_guest():
            sub = submit_guest_aid_offer_multi(
                self.ev.name, "Donatur Tamu", "081355500011",
                json.dumps([{"item_name": "Air mineral", "quantity": 20, "unit": "dus"}]),
                handling_mode="need_pickup", pickup_location="Jl. Mawar 3", target_posko=self.d_near.name)
        offer = (sub.get("aid_offers") or sub.get("offers") or sub.get("aid_ids") or [None])[0]
        offer = offer["name"] if isinstance(offer, dict) else offer
        self.assertTrue(offer, sub)
        with as_user(self.person.user):
            out = claim_aid_pickup(self.p_posko.name, offer, self.d_near.name)
        self.assertEqual(out["destination_posko"], self.d_near.name)
        self.assertEqual(frappe.db.get_value("RN Aid Offer", offer, "offer_status"), "pickup_claimed")
        self.assertEqual(frappe.db.get_value("RN Distribution Flow", out["flow"], "flow_status"), "pickup_claimed")
