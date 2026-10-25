"""volunteer_board returns Relawan Tersedia / Ditempatkan with readiness
details (2026-10-25: the lists were built but missing from the return in the
repo, and the readiness fields were never fetched)."""

import frappe

from rescue_net.api_volunteer import volunteer_board
from rescue_net.tests.factories import RNTestCase, _insert, as_guest, make_event, make_posko, uid


class TestVolunteerBoardReady(RNTestCase):
    def test_available_and_placed_lists(self):
        ev = make_event()
        posko = make_posko(ev, title=uid("Posko Relawan"))
        free = _insert("RN Volunteer Profile", disaster_event=ev.name, volunteer_name=uid("Siap"),
                       main_skill="logistik", availability_status="available", needs_pickup=1,
                       transport_vehicle="motor", availability_schedule="Sabtu-Minggu",
                       service_areas="Meulaboh")
        busy = _insert("RN Volunteer Profile", disaster_event=ev.name, volunteer_name=uid("Tugas"),
                       main_skill="medis", availability_status="assigned", assigned_posko=posko.name)
        _insert("RN Volunteer Assignment", volunteer=busy.name, posko=posko.name, task_title="Triase",
                disaster_event=ev.name, assignment_status="planned")
        with as_guest():
            b = volunteer_board(ev.name)
        r = [x for x in b["relawan_tersedia"] if x["name"] == free.name][0]
        self.assertEqual((r["jadwal_tersedia"], r["kendaraan_bawaan"], r["area_layanan"], r["butuh_jemput"]),
                         ("Sabtu-Minggu", "motor", "Meulaboh", True))
        d = [x for x in b["relawan_ditempatkan"] if x["name"] == busy.name][0]
        self.assertEqual(d["posko_ditempatkan"], posko.title)
        self.assertEqual([t["task_title"] for t in d["penugasan"]], ["Triase"])
        self.assertNotIn(busy.name, [x["name"] for x in b["relawan_tersedia"]])
        # no contact number on the public board
        self.assertNotIn("contact", r)
