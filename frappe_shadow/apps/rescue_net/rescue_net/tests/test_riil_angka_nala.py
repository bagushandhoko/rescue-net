from frappe.utils import now_datetime

from rescue_net import api_volunteer, api_search_found, api_tender
from rescue_net.tests.factories import _insert, as_guest
from rescue_net.tests.test_operational_mode import OperationalBase
from rescue_net.tests.test_tampilan_riil import _Cookie
from rescue_net.tests.test_search_found_board import missing, found


class TestRiilAngkaNala(OperationalBase):
    def test_volunteer_totals_and_safety(self):
        p = _insert('RN Volunteer Profile', disaster_event=self.sim.name,
                    volunteer_name='Relawan simulasi', main_skill='logistik', availability_status='available')
        _insert('RN Volunteer Assignment', disaster_event=self.sim.name, volunteer=p.name,
                posko=self.sim_posko.name, task_title='Tugas simulasi', assignment_status='planned')
        _insert('RN Volunteer Accommodation', disaster_event=self.sim.name,
                location_name='Penginapan', posko=self.sim_posko.name, capacity_beds=5, occupants_count=2)
        with as_guest(), _Cookie(None):
            before = api_volunteer.volunteer_board()
        with as_guest(), _Cookie('riil'):
            after = api_volunteer.volunteer_board()
        self.assertEqual(before['totals']['terdaftar'] - after['totals']['terdaftar'], 1)
        self.assertEqual(before['totals']['available_hari_ini'] - after['totals']['available_hari_ini'], 1)
        self.assertEqual(before['totals']['butuh_penugasan'] - after['totals']['butuh_penugasan'], 1)
        self.assertEqual(before['akomodasi_keselamatan']['tempat_tidur_tersedia'] - after['akomodasi_keselamatan']['tempat_tidur_tersedia'], 5)

    def test_search_found_counts(self):
        missing(self.sim)
        found(self.sim)
        with as_guest(), _Cookie(None):
            before = api_search_found.dashboard()
        with as_guest(), _Cookie('riil'):
            after = api_search_found.dashboard()
        for key in ('orang_hilang', 'korban_ditemukan', 'belum_teridentifikasi'):
            self.assertEqual(before['kpis'][key]['n'] - after['kpis'][key]['n'], 1, key)

    def test_tender_counts_and_bids(self):
        t = _insert('RN Procurement Tender', title='Tender simulasi', disaster_event=self.sim.name,
                    rab_total=1234, status='open')
        _insert('RN Tender Bid', tender=t.name, bidder_name='Penyedia', bid_amount=1000, status='submitted')
        with as_guest(), _Cookie(None):
            before = api_tender.tender_board()['totals']
        with as_guest(), _Cookie('riil'):
            after = api_tender.tender_board()['totals']
        for key, delta in (('total', 1), ('rab_value_total', 1234), ('bids_total', 1)):
            self.assertGreaterEqual(before[key] - after[key], delta, key)
