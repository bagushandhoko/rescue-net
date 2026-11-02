"""Privacy check 2026-11-02: the armada handover phone no longer reaches guests on the public distribution boards."""

import frappe

from rescue_net.control_centre.distribusi import distribusi_board, posko_distribusi_board
from rescue_net.tests.factories import RNTestCase, _insert, as_guest, as_user, make_actor, make_world


class TestHandoverPhonePrivacy(RNTestCase):
    def test_guest_never_sees_handover_phone(self):
        w = make_world()
        frappe.db.set_value("RN Posko", w.posko_a.name, {"public_detail": "public", "public_participation": 1})
        _insert("RN Transport Space", title="Truk Privasi", provider_name="Truk Privasi", disaster_event=w.event.name,
                coordination_posko=w.posko_a.name, transport_type="darat", capacity_weight_kg=500,
                transport_status="available", handover_contact_person="Pak Sopir", handover_contact_phone="0813-7777-4242")
        sp = frappe.get_all("RN Transport Space", filters={"title": "Truk Privasi"}, pluck="name")[0]
        _insert("RN Transport Booking", transport_space=sp, disaster_event=w.event.name, status="requested",
                cargo_desc="Beras", qty_weight_kg=50, booked_by_type="individu", contact_person="Bu Pemesan",
                contact_phone="0857-1111-3030")
        with as_guest():
            blob = frappe.as_json(distribusi_board(w.event.name)) + frappe.as_json(posko_distribusi_board(w.posko_a.name, w.event.name))
        self.assertNotIn("0813-7777-4242", blob)
        self.assertNotIn("0857-1111-3030", blob)       # booker phone
        self.assertNotIn("Bu Pemesan", blob)
        with as_user(make_actor(posko=w.posko_a).user):
            mine = frappe.as_json(posko_distribusi_board(w.posko_a.name, w.event.name))
        self.assertIn("0813-7777-4242", mine)
