"""Relawan multi-bencana + booking armada & shelter (owner 2026-10-26)."""

import frappe

from rescue_net import api_volunteer_booking as vb
from rescue_net.tests.factories import (RNTestCase, _insert, as_guest, as_user, make_actor, make_event, make_posko,
                                        make_transport_space, make_world)


class TestVolunteerBooking(RNTestCase):
    def setUp(self):
        super().setUp()
        self.w = make_world()
        frappe.db.set_value("RN Disaster Event", self.w.event.name, "event_status", "active")
        self.ev2 = make_event(event_status="active")
        self.tp = make_posko(self.w.event, self.w.org_a, posko_type="transport")
        self.sh = make_posko(self.w.event, self.w.org_b, posko_type="shelter")
        self.arm = make_transport_space(self.tp, disaster_event=self.w.event.name, volunteer_capacity_seats=1)
        self.bed = _insert("RN Volunteer Accommodation", disaster_event=self.w.event.name, posko=self.sh.name,
                           location_name="Mess Relawan", accommodation_type="mess", capacity_beds=2, occupants_count=0)
        self.rel = make_actor(role="relawan")
        self.rel2 = make_actor(role="relawan")

    def offer(self, actor, events, **kw):
        with as_user(actor.user):
            return vb.offer_events(events, contact="0812000011", main_skill="logistik", **kw)

    def test_offer_many_disasters_and_withdraw(self):
        r = self.offer(self.rel, [self.w.event.name, self.ev2.name])
        self.assertEqual(set(r["offered"]), {self.w.event.name, self.ev2.name})
        self.assertEqual(frappe.db.count("RN Volunteer Profile", {"user_account": self.rel.account}), 2)
        r = self.offer(self.rel, [self.w.event.name])
        self.assertEqual(r["offered"], [self.w.event.name])

    def test_book_seat_capacity_and_posko_decision(self):
        self.offer(self.rel, [self.w.event.name]); self.offer(self.rel2, [self.w.event.name])
        with as_user(self.rel.user):
            opts = vb.booking_options(self.w.event.name)
            self.assertEqual([a["seats_left"] for a in opts["armada"] if a["id"] == self.arm.name], [1])
            b1 = vb.book("transport", self.arm.name, self.w.event.name)["booking"]
            with self.assertRaisesRegex(frappe.ValidationError, "sudah punya"):
                vb.book("transport", self.arm.name, self.w.event.name)
        with as_user(self.rel2.user):
            b2 = vb.book("transport", self.arm.name, self.w.event.name)["booking"]
            with self.assertRaises(frappe.PermissionError):
                vb.decide_booking(b1, "confirm")
        with as_user(make_actor(posko=self.tp).user):
            self.assertEqual(vb.decide_booking(b1, "confirm")["status"], "confirmed")
            with self.assertRaisesRegex(frappe.ValidationError, "Penuh"):
                vb.decide_booking(b2, "confirm")
        with as_user(make_actor(role="relawan").user), self.assertRaises(frappe.ValidationError):
            vb.book("transport", self.arm.name, self.w.event.name)     # not offered for this disaster

    def test_book_bed_and_cancel(self):
        self.offer(self.rel, [self.w.event.name])
        with as_user(self.rel.user):
            b = vb.book("akomodasi", self.bed.name, self.w.event.name, date_from="2026-11-01", date_to="2026-11-05")
            self.assertEqual(b["posko"], self.sh.name)
            self.assertEqual(vb.cancel_booking(b["booking"])["status"], "cancelled")
            self.assertEqual(vb.my_volunteer()["bookings"][0]["status"], "cancelled")

    def test_finished_armada_cannot_be_booked(self):
        self.offer(self.rel, [self.w.event.name])
        frappe.db.set_value("RN Transport Space", self.arm.name, "transport_status", "completed")
        with as_user(self.rel.user), self.assertRaisesRegex(frappe.ValidationError, "selesai"):
            vb.book("transport", self.arm.name, self.w.event.name)

    def test_guest_refused(self):
        with as_guest(), self.assertRaises(frappe.PermissionError):
            vb.my_volunteer()


class TestArmadaVolunteerSeats(RNTestCase):
    def test_posko_sets_volunteer_seats_on_create_and_update(self):
        from rescue_net.logistics.transport import create_transport_space, update_transport_space
        w = make_world()
        tp = make_posko(w.event, w.org_a, posko_type="transport")
        with as_user(make_actor(posko=tp).user):
            r = create_transport_space(coordination_posko=tp.name, provider_name="Truk Relawan", transport_type="darat",
                                       capacity_weight_kg=1000, disaster_event=w.event.name, volunteer_capacity_seats=4,
                                       volunteer_pickup_location="Halaman posko")
            name = r["transport"]
            self.assertEqual(frappe.db.get_value("RN Transport Space", name, "volunteer_capacity_seats"), 4)
            update_transport_space(name, volunteer_capacity_seats=6)
        self.assertEqual(frappe.db.get_value("RN Transport Space", name, "volunteer_capacity_seats"), 6)


class TestVolunteerTripAndShelter(RNTestCase):
    """Owner 2026-11-12: kursi pulang terpisah dari berangkat; menginap di posko shelter."""
    def setUp(self):
        super().setUp()
        self.w = make_world()
        frappe.db.set_value("RN Disaster Event", self.w.event.name, "event_status", "active")
        self.tp = make_posko(self.w.event, self.w.org_a, posko_type="transport")
        self.sh = make_posko(self.w.event, self.w.org_b, posko_type="shelter")
        self.pp = make_transport_space(self.tp, disaster_event=self.w.event.name, volunteer_capacity_seats=1,
                                       people_trip="pergi_pulang", route_origin="Banda Aceh", route_destination="Meulaboh")
        self.go = make_transport_space(self.tp, disaster_event=self.w.event.name, volunteer_capacity_seats=2)
        self.rel = make_actor(role="relawan")
        with as_user(self.rel.user):
            vb.offer_events([self.w.event.name], contact="0812000011", main_skill="logistik")

    def test_return_leg_has_own_seats(self):
        with as_user(self.rel.user):
            opts = vb.booking_options(self.w.event.name)
            self.assertIn(self.pp.name, [a["id"] for a in opts["armada"]])
            back = [a for a in opts["armada_pulang"] if a["id"] == self.pp.name]
            self.assertEqual(back[0]["route"], "Meulaboh → Banda Aceh")
            self.assertNotIn(self.go.name, [a["id"] for a in opts["armada_pulang"]])   # data lama: berangkat saja
            b1 = vb.book("transport", self.pp.name, self.w.event.name)["booking"]
            b2 = vb.book("transport", self.pp.name, self.w.event.name, trip_leg="pulang")["booking"]
            with self.assertRaisesRegex(frappe.ValidationError, "tidak melayani"):
                vb.book("transport", self.go.name, self.w.event.name, trip_leg="pulang")
        with as_user(make_actor(posko=self.tp).user):
            self.assertEqual(vb.decide_booking(b1, "confirm")["status"], "confirmed")
            self.assertEqual(vb.decide_booking(b2, "confirm")["status"], "confirmed")   # 1 kursi per arah
        self.assertEqual(frappe.db.get_value("RN Volunteer Booking", b2, "trip_leg"), "pulang")

    def test_stay_at_shelter_posko(self):
        with as_user(self.rel.user):
            opts = vb.booking_options(self.w.event.name)
            self.assertIn(self.sh.name, [p["id"] for p in opts["shelter"]])
            b = vb.book("shelter", self.sh.name, self.w.event.name, date_from="2026-11-13")["booking"]
            with self.assertRaisesRegex(frappe.ValidationError, "sudah"):
                vb.book("shelter", self.sh.name, self.w.event.name)
            with self.assertRaisesRegex(frappe.ValidationError, "bukan posko shelter"):
                vb.book("shelter", self.tp.name, self.w.event.name)
        with as_user(make_actor(posko=self.sh).user):
            self.assertEqual(vb.decide_booking(b, "confirm")["status"], "confirmed")
