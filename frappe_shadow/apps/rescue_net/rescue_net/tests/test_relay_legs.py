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

    def test_scan_moves_planned_flow_along_the_relay(self):
        """Simulasi DIST-MU-3: kiriman 'Direncanakan' macet karena pindai Dikirim ditolak."""
        org_c = make_org(title="Rotary")
        tp_c = make_posko(self.w.event, org_c, posko_type="transport")
        truck = make_transport_space(tp_c, disaster_event=self.w.event.name, capacity_weight_kg=8000)
        r = self.send(self.arm_b)                                    # main leg: other org -> requested
        coord_b = make_actor(posko=self.tp_b)
        with as_user(coord_b.user):
            confirm_transport_booking(r["booking"], pin=r.get("verification_pin"))
            leg = book_relay_leg(r["flow"], truck.name, pickup_location="Pelabuhan", dropoff_location="Posko tujuan")
        truck_op = make_actor(posko=tp_c)
        with as_user(truck_op.user):
            confirm_transport_booking(leg["booking"], pin=leg.get("verification_pin"))
        flow = r["flow"]
        with as_user(self.op.user):
            self.assertEqual(record_scan(flow=flow, scan_type="dispatch")["scan"]["status_after"], "dispatched")
        with as_user(coord_b.user):
            self.assertEqual(record_scan(flow=flow, scan_type="transit")["scan"]["status_after"], "in_transit")
        with as_user(truck_op.user):
            record_scan(flow=flow, scan_type="handover")
            self.assertEqual(record_scan(flow=flow, scan_type="arrive")["scan"]["status_after"], "arrived_at_posko")
            with self.assertRaisesRegex(frappe.PermissionError, "posko tujuan"):
                record_scan(flow=flow, scan_type="receive")
        dst_op = make_actor(posko=self.dst)
        with as_user(dst_op.user):
            record_scan(flow=flow, scan_type="receive", received_quantity=10, received_unit="karung")
        self.assertEqual(frappe.db.get_value("RN Distribution Flow", flow, "flow_status"), "received")
