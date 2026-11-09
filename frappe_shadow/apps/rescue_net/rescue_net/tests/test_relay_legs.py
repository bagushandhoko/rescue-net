"""Estafet antar-posko distribusi (owner 2026-11-09): kapal → truk → motor, satu kiriman, satu resi."""

import frappe

from rescue_net.api_custody import custody_chain, record_scan
from rescue_net.control_centre.distribusi import flow_trace
from rescue_net.logistics.relay import book_relay_leg
from rescue_net.logistics.transport import confirm_transport_booking
from rescue_net.tests.factories import as_guest, as_user, make_actor, make_org, make_posko, make_transport_space
from rescue_net.tests.test_shipment_booking import _ShipmentWorld


class TestRelayLegs(_ShipmentWorld):
    def test_ship_truck_motorbike_relay(self):
        r = self.send(self.arm_a)                                   # main leg: same org armada, confirmed
        flow = r["flow"]
        self.assertEqual(r["booking_status"], "confirmed")
        ship_op = make_actor(posko=self.tp_a)
        truck_op = make_actor(posko=self.tp_b)
        org_c = make_org(title="Pelajar")
        tp_c = make_posko(self.w.event, org_c, posko_type="transport")
        motor = make_transport_space(tp_c, disaster_event=self.w.event.name, transport_type="darat")
        motor_op = make_actor(posko=tp_c)

        # outsider cannot add a leg
        with as_user(motor_op.user), self.assertRaises(frappe.PermissionError):
            book_relay_leg(flow, motor.name)
        # the ship's posko (carrier of the main leg) books the truck as relay 1; the truck's posko confirms
        with as_user(ship_op.user):
            l1 = book_relay_leg(flow, self.arm_b.name, pickup_location="Pelabuhan", dropoff_location="Simpang Kota")
        self.assertEqual((l1["leg_seq"], l1["status"]), (1, "requested"))
        with as_user(truck_op.user):
            confirm_transport_booking(l1["booking"], pin=l1.get("verification_pin"))
        self.assertEqual(frappe.db.get_value("RN Distribution Flow", flow, "transport_space"), self.arm_a.name)
        # the truck posko is now a carrier: it records the handover and books the motorbike as relay 2
        with as_user(truck_op.user):
            self.assertTrue(record_scan(flow=flow, scan_type="handover", note="terima dari kapal")["ok"])
            l2 = book_relay_leg(flow, motor.name, pickup_location="Simpang Kota", dropoff_location="Posko tujuan")
            self.assertEqual(l2["leg_seq"], 2)
            with self.assertRaises(frappe.PermissionError):
                record_scan(flow=flow, scan_type="receive")         # only the destination receives
            chain = custody_chain(flow=flow)
        with as_user(motor_op.user):
            confirm_transport_booking(l2["booking"], pin=l2.get("verification_pin"))
        with as_guest():
            t = flow_trace(flow=flow)
        self.assertEqual([l["leg"] for l in t["legs"]], ["main", "relay", "relay"])
        self.assertEqual([l["leg_label"] for l in t["legs"]][1:], ["Estafet 1", "Estafet 2"])
        self.assertEqual(t["handovers"][0]["jenis"], "Serah-terima")
        self.assertNotIn("PIN", frappe.as_json(t))
        self.assertEqual(len(chain["legs"]), 3)
        self.assertTrue(chain["scans"][0]["posko_title"])
