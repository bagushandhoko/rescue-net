import frappe

from rescue_net.logistics.transport import create_transport_space, update_transport_space
from rescue_net.control_centre.distribusi import posko_distribusi_board, distribusi_board
from rescue_net.tests.factories import RNTestCase, as_guest, as_user, make_actor, make_posko, make_world


class TestAngkutAlatBeratNala(RNTestCase):
    def setUp(self):
        super().setUp()
        self.w = make_world()
        self.tp = make_posko(self.w.event, self.w.org_a, posko_type='transport')
        self.op = make_actor(posko=self.tp)

    def create(self, **kw):
        with as_user(self.op.user):
            return create_transport_space(coordination_posko=self.tp.name, provider_name='Lowbed uji',
                                           transport_type='darat', disaster_event=self.w.event.name, **kw)['transport']

    def test_create_update_and_public_boards(self):
        name = self.create(carries_heavy_equipment=1, heavy_max_ton=25, heavy_deck_type='lowbed',
                           heavy_trip='mob_demob', heavy_demob_at='2026-12-01 10:00:00')
        doc = frappe.get_doc('RN Transport Space', name)
        self.assertEqual((doc.carries_heavy_equipment, doc.heavy_max_ton, doc.heavy_trip), (1, 25, 'mob_demob'))
        with as_user(self.op.user):
            update_transport_space(name, heavy_max_ton=30, heavy_deck_type='selfloader', heavy_trip='demob')
            update_transport_space(name, current_location='Posko')  # partial update keeps heavy fields
        with as_guest():
            boards = [(posko_distribusi_board(self.tp.name), 'armada'),
                      (distribusi_board(self.w.event.name), 'armada_posko')]
        for b, key in boards:
            row = next(r for r in b[key] if r['id'] == name)
            self.assertTrue(row['angkut_alat_berat'])
            self.assertEqual(row['alat_berat_maks_ton'], 30)
            self.assertEqual(row['alat_berat_dek'], 'selfloader')
            self.assertEqual(row['alat_berat_arah'], 'demob')
            self.assertEqual(row['jadwal_demob'], '2026-12-01 10:00')

    def test_tons_required_on_create_and_update(self):
        for tons in (None, '', 0, -1):
            with self.assertRaises(frappe.ValidationError):
                self.create(carries_heavy_equipment=1, heavy_max_ton=tons)
        name = self.create()
        with as_user(self.op.user), self.assertRaises(frappe.ValidationError):
            update_transport_space(name, carries_heavy_equipment=1)

    def test_disable_and_clear_fields(self):
        name = self.create(carries_heavy_equipment=1, heavy_max_ton=10, heavy_trip='mob')
        with as_user(self.op.user):
            update_transport_space(name, carries_heavy_equipment=0, heavy_max_ton=0,
                                   heavy_trip='', heavy_deck_type='', heavy_demob_at='')
        doc = frappe.get_doc('RN Transport Space', name)
        self.assertFalse(doc.carries_heavy_equipment)
        self.assertEqual(doc.heavy_max_ton, 0)
        self.assertFalse(doc.heavy_trip)

    def test_invalid_choices_rejected(self):
        for kw in ({'heavy_deck_type':'pesawat'}, {'heavy_trip':'ngawur'}):
            with self.assertRaises(frappe.ValidationError):
                self.create(carries_heavy_equipment=1, heavy_max_ton=10, **kw)
