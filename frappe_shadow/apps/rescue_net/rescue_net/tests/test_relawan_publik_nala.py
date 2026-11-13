import frappe
from rescue_net.api_volunteer import volunteer_board
from rescue_net.tests.factories import _insert, as_guest, make_event
from rescue_net.tests.test_operational_mode import OperationalBase
from rescue_net.tests.test_tampilan_riil import _Cookie


class TestRelawanPublikNala(OperationalBase):
    def setUp(self):
        super().setUp()
        self.p = _insert('RN Volunteer Profile', disaster_event=self.real.event.name,
                         volunteer_name='Relawan Publik', contact='081234567890',
                         main_skill='Medis', availability_status='available')
        self.stay = _insert('RN Volunteer Accommodation', disaster_event=self.real.event.name,
                            location_name='Rumah Relawan', capacity_beds=5)
        self.project = _insert('RN Recovery Project', disaster_event=self.real.event.name, project_name='Pemulihan')
        self.need = _insert('RN Recovery Volunteer Need', disaster_event=self.real.event.name,
                            recovery_project=self.project.name, role_needed='mEDIs', people_needed=4, need_status='open')

    def booking(self, kind, status='confirmed', **kw):
        return _insert('RN Volunteer Booking', volunteer=self.p.name, disaster_event=self.real.event.name,
                        booking_kind=kind, status=status, date_from='2026-11-14', date_to='2026-11-15', **kw)

    def board(self):
        with as_guest():
            return volunteer_board(self.real.event.name)

    def row(self, b, key='daftar_relawan'):
        return next(r for r in b[key] if r['name'] == self.p.name)

    def test_guest_positions_and_needs_without_phone(self):
        self.booking('akomodasi', accommodation=self.stay.name)
        self.booking('transport', transport_space=self.sim_armada.name, trip_leg='pulang')
        self.booking('posko', posko=self.real.posko_a.name)
        b = self.board()
        for key in ('daftar_relawan', 'relawan_tersedia'):
            r = self.row(b, key)
            self.assertEqual(r['volunteer_name'], 'Relawan Publik')
            self.assertIsNone(r['kontak'])
            self.assertEqual(r['menginap_di']['nama'], 'Rumah Relawan')
            self.assertEqual(r['kendaraan'][0]['arah'], 'pulang')
            self.assertEqual(r['bertugas_di'], self.real.posko_a.title)
        n = next(n for n in b['kebutuhan_relawan'] if n['bidang'] == 'mEDIs')
        self.assertEqual((n['dibutuhkan'], n['tersedia']), (4, 1))
        self.assertNotIn('081234567890', str(b))

    def test_requested_rejected_cancelled_not_public(self):
        for status in ('requested', 'rejected', 'cancelled'):
            self.booking('akomodasi', status=status, accommodation=self.stay.name)
            self.booking('transport', status=status, transport_space=self.sim_armada.name)
            self.booking('posko', status=status, posko=self.real.posko_a.name)
        r = self.row(self.board())
        self.assertIsNone(r['menginap_di'])
        self.assertEqual(r['kendaraan'], [])
        self.assertIsNone(r['bertugas_di'])

    def test_shelter_and_assigned_volunteer(self):
        self.booking('shelter', posko=self.real.posko_b.name)
        frappe.db.set_value('RN Volunteer Profile', self.p.name,
                            {'availability_status':'assigned', 'assigned_posko':self.real.posko_a.name})
        r = self.row(self.board(), 'relawan_ditempatkan')
        self.assertEqual(r['menginap_di']['nama'], self.real.posko_b.title)
        self.assertEqual(r['bertugas_di'], self.real.posko_a.title)

    def test_riil_hides_simulation_targets_and_needs(self):
        self.booking('transport', transport_space=self.sim_armada.name)
        _insert('RN Recovery Volunteer Need', disaster_event=self.sim.name, recovery_project=self.project.name,
                role_needed='Simulasi medis', people_needed=2, need_status='open')
        with as_guest(), _Cookie('riil'):
            b = volunteer_board()
        self.assertEqual(self.row(b)['kendaraan'], [])
        self.assertNotIn('Simulasi medis', str(b['kebutuhan_relawan']))

    def test_other_event_booking_and_closed_need_excluded(self):
        booking = self.booking('akomodasi', accommodation=self.stay.name)
        frappe.db.set_value('RN Volunteer Booking', booking.name, 'disaster_event', make_event().name)
        frappe.db.set_value('RN Recovery Volunteer Need', self.need.name, 'need_status', 'closed')
        b = self.board()
        self.assertIsNone(self.row(b)['menginap_di'])
        self.assertEqual(b['kebutuhan_relawan'], [])
