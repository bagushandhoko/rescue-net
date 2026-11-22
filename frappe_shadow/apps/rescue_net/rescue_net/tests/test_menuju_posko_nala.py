"""Public incoming: privacy, destinations, completed states and Riil."""
import json
import frappe
from rescue_net.api_public_needs import incoming_for_posko
from rescue_net.tests.factories import RNTestCase, _insert, as_guest, make_event, make_posko, make_transport_space
from rescue_net.tests.test_tampilan_riil import _Cookie


class TestMenujuPosko(RNTestCase):
    def setUp(self):
        super().setUp()
        self.ev = make_event()
        self.p = make_posko(self.ev, public_detail='public')
        self.src = make_posko(self.ev, public_detail='public')
        self.sp = make_transport_space(self.src, disaster_event=self.ev.name, route_destination=self.p.name,
                                       provider_name='Truk publik', capacity_weight_kg=1000)

    def flow(self, status='planned', **kw):
        f = _insert('RN Distribution Flow', title='Kiriman', destination_posko=self.p.name,
                    source_posko=self.src.name, disaster_event=self.ev.name, item_name='Beras',
                    quantity=12, unit='kg', transport_space=self.sp.name, **kw)
        frappe.db.set_value('RN Distribution Flow', f.name, 'flow_status', status)
        return f

    def feed(self, **kw):
        with as_guest():
            return incoming_for_posko(self.p.name, **kw)

    def test_guest_allowlist_and_tracking(self):
        f = self.flow()
        frappe.db.set_value('RN Posko', self.src.name, 'title', 'Pengirim 081234567899')
        _insert('RN Aid Offer', title='Donatur', disaster_event=self.ev.name, target_posko=self.p.name,
                donor_name='Donatur 081234567899', donor_contact='081234567899', item_name='Air', quantity=2,
                unit='dus', offer_status='reserved')
        data = self.feed(); blob = json.dumps(data)
        self.assertNotIn('081234567899', blob)
        self.assertNotIn('donor_contact', blob)
        self.assertEqual(data['in_transit'][0]['quantity'], 12)
        self.assertIn('lacak-logistik.html?flow=', data['in_transit'][0]['href'])
        self.assertEqual(data['in_transit'][0]['id'], f.name)
        self.assertEqual(len(data['booked']), 1)

    def test_done_flows_and_linked_offers_do_not_resurface(self):
        a = _insert('RN Aid Offer', title='Air', disaster_event=self.ev.name, target_posko=self.p.name,
                    item_name='Air', offer_status='reserved')
        self.flow('received', aid_offer=a.name)
        self.flow('cancelled')
        d = self.feed()
        self.assertEqual(d['in_transit'], [])
        self.assertEqual(d['booked'], [])

    def test_private_and_event_scope(self):
        private = make_posko(self.ev, public_detail='private')
        with as_guest(), self.assertRaises(frappe.PermissionError):
            incoming_for_posko(private.name)
        self.flow()
        self.assertEqual(self.feed(event=make_event().name)['in_transit'], [])

    def test_simulation_hidden_in_riil(self):
        frappe.db.set_value('RN Disaster Event', self.ev.name, 'title', '[SIMULASI] Bencana uji')
        self.flow()
        with _Cookie("simulasi"):
            self.assertEqual(len(self.feed()['in_transit']), 1)
        with _Cookie('riil'):
            d = self.feed()
            self.assertEqual(d['in_transit'] + d['booked'] + d['arrivals'], [])

    def test_volunteer_transport_uses_destination_not_operator_posko(self):
        v = _insert('RN Volunteer Profile', main_skill='Logistik', volunteer_name='Relawan publik', contact='081234567899',
                    disaster_event=self.ev.name)
        for status in ('requested', 'confirmed', 'rejected', 'cancelled'):
            _insert('RN Volunteer Booking', volunteer=v.name, disaster_event=self.ev.name,
                    booking_kind='transport', transport_space=self.sp.name, posko=self.src.name,
                    status=status, trip_leg='berangkat')
        d = self.feed()
        self.assertEqual(len([r for r in d['arrivals'] if r['kind'] == 'volunteer']), 2)
        self.assertNotIn('081234567899', json.dumps(d))
        with as_guest():
            src = incoming_for_posko(self.src.name)
        self.assertEqual(src['arrivals'], [])

    def test_cargo_bookings_follow_flow_destination_and_hide_secrets(self):
        f = self.flow()
        other = make_posko(self.ev, public_detail='public')
        foreign = _insert('RN Distribution Flow', title='Tujuan lain', source_posko=self.src.name,
                          destination_posko=other.name, disaster_event=self.ev.name, item_name='Air', quantity=1)
        for flow, status in ((f, 'requested'), (f, 'confirmed'), (f, 'completed'), (foreign, 'requested')):
            _insert('RN Transport Booking', transport_space=self.sp.name, disaster_event=self.ev.name,
                    distribution_flow=flow.name, dropoff_location=self.p.name, status=status,
                    qty_weight_kg=1, contact_phone='081234567899', verification_pin='PIN-RAHASIA',
                    cargo_desc='Catatan 081234567899')
        data = self.feed()
        self.assertEqual(len(data['booked']), 2)
        blob = json.dumps(data)
        self.assertNotIn('081234567899', blob)
        self.assertNotIn('PIN-RAHASIA', blob)
        self.assertTrue(all('lacak-logistik.html' in b['href'] for b in data['booked']))

    def test_unlinked_cargo_exact_destination_and_expired_volunteer(self):
        _insert('RN Transport Booking', transport_space=self.sp.name, disaster_event=self.ev.name,
                dropoff_location=self.p.title, status='confirmed', qty_weight_kg=1)
        v = _insert('RN Volunteer Profile', main_skill='Logistik', volunteer_name='Sudah lewat', disaster_event=self.ev.name)
        _insert('RN Volunteer Booking', volunteer=v.name, disaster_event=self.ev.name,
                booking_kind='posko', posko=self.p.name, status='confirmed', date_to='2000-01-01')
        d = self.feed()
        self.assertEqual(len(d['booked']), 1)
        self.assertEqual([r for r in d['arrivals'] if r['kind'] == 'volunteer'], [])
