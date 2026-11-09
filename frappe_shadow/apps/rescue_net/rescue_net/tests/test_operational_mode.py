"""Mode Operasional Riil (owner 2026-11-09): satu tombol super admin menyembunyikan SEMUA data simulasi dari
halaman Rescue-Net — tanpa menghapus apa pun, dan bisa dikembalikan.

- mode mati  -> bencana simulasi tampil seperti biasa;
- mode aktif -> bencana simulasi, posko, armada & data turunannya tidak tampil di endpoint publik utama, id
  eksplisit ditolak untuk tamu & pengguna biasa (System Manager tetap bisa membuka);
- hanya System Manager yang bisa mengubah saklar; perubahan tercatat (siapa & kapan);
- pembersihan latihan (hapus) tidak pernah menyentuh bencana simulasi.
"""

import json

import frappe

from rescue_net import api_armada, api_events, api_gis
from rescue_net import api_operational_mode as opm
from rescue_net.ai.public import public_active_disasters
from rescue_net.control_centre import bencana_aktif
from rescue_net.control_centre.org import org_posko_board, posko_registry_board
from rescue_net.services import drill
from rescue_net.tests.factories import (
    RNTestCase,
    _insert,
    as_guest,
    as_user,
    make_actor,
    make_event,
    make_org,
    make_posko,
    make_user,
    make_world,
    uid,
)

SENT = "SIMOPS-SENTINEL-5521"
LABEL_SENT = "SIMLABEL-SENTINEL-6632"


class OperationalBase(RNTestCase):
    def setUp(self):
        super().setUp()
        self._mode(False)
        self.real = make_world()
        frappe.db.set_value("RN Disaster Event", self.real.event.name, "event_status", "active")
        # bencana simulasi BUKAN is_drill: hanya ditandai lewat judul (pola data demo produksi)
        self.sim = make_event(title="[SIMULASI] Gempa " + SENT, event_status="active")
        self.sim_org = make_org(title="[SIMULASI] Org " + SENT)
        self.sim_posko = make_posko(self.sim, self.sim_org, title="Posko " + SENT, latitude=-6.2, longitude=106.8)
        self.sim_armada = _insert("RN Transport Space", title="Truk " + SENT, provider_name="Truk " + SENT,
                                  disaster_event=self.sim.name, coordination_posko=self.sim_posko.name,
                                  transport_type="darat", transport_status="available", capacity_weight_kg=1000)
        _insert("RN Logistic Need", title=SENT + " butuh", posko=self.sim_posko.name, disaster_event=self.sim.name,
                item_name=SENT + " beras", quantity=10, unit="kg", urgency="critical")
        _insert("RN Donor Program", disaster_event=self.sim.name, program_name="Program " + SENT,
                owner_type="organization", owner_id=self.sim_org.name, status="active",
                public_visibility="summary_public", budget_target=1000000, budget_received=250000)
        # posko berlabel [SIMULASI] di bencana NYATA: ikut tersembunyi saat mode aktif
        self.label_posko = make_posko(self.real.event, self.real.org_a, title="[SIMULASI] Posko " + LABEL_SENT)

    def _mode(self, on):
        frappe.db.set_default(drill.MODE_KEY, "1" if on else "0")

    def blob(self, value):
        return json.dumps(value, default=str)

    def public_blobs(self):
        with as_guest():
            return {
                "disasters": self.blob(api_events.disasters()),
                "public_active_disasters": self.blob(public_active_disasters()),
                "active_disasters_board": self.blob(bencana_aktif.active_disasters_board()),
                "national_situation": self.blob(api_gis.national_situation(active_only=0)),
                "armada_finder": self.blob(api_armada.armada_finder()),
                "posko_registry_board": self.blob(posko_registry_board()),
                "org_posko_board": self.blob(org_posko_board()),
            }


class TestOperationalModeVisibility(OperationalBase):
    def test_mode_off_simulation_is_visible(self):
        self.assertFalse(drill.operational_mode())
        self.assertIn(self.sim.name, drill.simulation_event_names())  # terdeteksi, tapi belum disembunyikan
        self.assertNotIn(self.sim.name, drill.drill_event_names())
        blobs = self.public_blobs()
        for key in ("disasters", "public_active_disasters", "active_disasters_board", "armada_finder"):
            self.assertIn(SENT, blobs[key], key)
        self.assertIn(LABEL_SENT, blobs["posko_registry_board"])
        with as_guest():
            drill.guard_guest_refs(frappe._dict({"disaster_event": self.sim.name}))  # tidak ditolak

    def test_mode_on_hides_simulation_event_and_its_data(self):
        self._mode(True)
        self.assertIn(self.sim.name, drill.drill_event_names())
        blobs = self.public_blobs()
        for key, text in blobs.items():
            self.assertNotIn(SENT, text, key)
            self.assertNotIn(LABEL_SENT, text, key)
        # bencana nyata tetap tampil (penyaring tidak membuang semuanya)
        self.assertIn(self.real.event.title, blobs["disasters"])
        self.assertIn(self.real.posko_a.title, blobs["posko_registry_board"])
        from rescue_net.donor_program.board import program_board
        with as_guest():
            self.assertNotIn(SENT, self.blob(program_board()))

    def test_mode_on_explicit_ids_refused_except_system_manager(self):
        self._mode(True)
        user = make_actor().user
        refs = ({"disaster_event": self.sim.name}, {"event": "disaster_events:" + self.sim.legacy_id},
                {"posko": self.sim_posko.name}, {"posko": self.label_posko.name},
                {"organization": self.sim_org.name})
        for params in refs:
            for who in ("Guest", user):
                with as_user(who):
                    with self.assertRaises(frappe.DoesNotExistError, msg=f"{who} {params}"):
                        drill.guard_guest_refs(frappe._dict(params))
            drill.guard_guest_refs(frappe._dict(params))  # Administrator (System Manager) lolos
        with as_user(user):
            drill.guard_guest_refs(frappe._dict({"disaster_event": self.real.event.name, "posko": self.real.posko_a.name}))

    def test_switching_back_shows_everything_again_nothing_deleted(self):
        self._mode(True)
        self.assertNotIn(SENT, self.public_blobs()["disasters"])
        self._mode(False)
        self.assertIn(SENT, self.public_blobs()["disasters"])
        self.assertTrue(frappe.db.exists("RN Posko", self.sim_posko.name))
        self.assertTrue(frappe.db.exists("RN Transport Space", self.sim_armada.name))

    def test_drill_cleanup_never_targets_simulation(self):
        from rescue_net.services import drill_tools
        self._mode(True)
        with self.assertRaises(frappe.ValidationError):
            drill_tools.preview_cleanup(self.sim.name)


class TestOperationalModeSwitch(OperationalBase):
    def test_only_system_manager_can_change(self):
        user = make_actor(role="command_center").user
        for who in ("Guest", user):
            with as_user(who):
                with self.assertRaises(frappe.PermissionError):
                    opm.set_operational_mode(1, confirm=opm.CONFIRM_WORD)
                with self.assertRaises(frappe.PermissionError):
                    opm.set_event_simulation(self.real.event.name, "1")
                with self.assertRaises(frappe.PermissionError):
                    opm.admin_status()
                self.assertEqual(opm.status(), {"operational": False})  # status publik boleh dibaca
        self.assertFalse(drill.operational_mode())

    def test_system_manager_switch_needs_confirmation_and_is_logged(self):
        with self.assertRaises(frappe.ValidationError):
            opm.set_operational_mode(1)  # tanpa kata konfirmasi
        self.assertFalse(drill.operational_mode())
        r = opm.set_operational_mode(1, confirm=opm.CONFIRM_WORD)
        self.assertTrue(r["operational"])
        self.assertEqual(r["log"][0]["by"], "Administrator")
        self.assertEqual(r["log"][0]["action"], "aktif")
        self.assertTrue(r["changed_at"])
        self.assertIn(self.sim.name, {e["name"] for e in r["events"] if e["simulation"]})
        with as_guest():
            self.assertEqual(opm.status(), {"operational": True})
        r = opm.set_operational_mode(0)
        self.assertFalse(r["operational"])
        self.assertEqual(r["log"][0]["action"], "nonaktif")

    def test_manual_mark_real_and_simulation(self):
        self._mode(True)
        opm.set_event_simulation(self.sim.name, "0")          # ternyata bencana nyata
        self.assertNotIn(self.sim.name, drill.drill_event_names())
        opm.set_event_simulation(self.real.event.name, "1")   # tidak terdeteksi otomatis, ditandai manual
        self.assertIn(self.real.event.name, drill.drill_event_names())
        with as_guest():
            self.assertNotIn(self.real.event.title, self.blob(api_events.disasters()))
        opm.set_event_simulation(self.sim.name, "auto")
        opm.set_event_simulation(self.real.event.name, "auto")
        self.assertIn(self.sim.name, drill.drill_event_names())
        self.assertNotIn(self.real.event.name, drill.drill_event_names())


class TestDemoAccountsBlocked(RNTestCase):
    """Owner 2026-11-09 malam: satu tombol super admin juga mematikan akun demo (@rescue-net.local / @example.org)."""

    def tearDown(self):
        frappe.db.set_default(drill.MODE_KEY, "0")
        super().tearDown()

    def _login_manager(self, user):
        return frappe._dict(user=user)

    def test_demo_detection(self):
        self.assertTrue(drill.is_demo_user("ld1.demo@rescue-net.local"))
        self.assertTrue(drill.is_demo_user("sim-mu-mdmc@example.org"))
        self.assertFalse(drill.is_demo_user("pemilik@gmail.com"))
        self.assertFalse(drill.is_demo_user("Administrator"))

    def test_demo_login_blocked_only_in_operational_mode(self):
        demo = make_user(email=uid("demo") + "@example.org")
        real = make_user(email=uid("nyata") + "@gmail.com")
        frappe.db.set_default(drill.MODE_KEY, "0")
        drill.block_demo_login(self._login_manager(demo))  # mode mati: boleh
        frappe.db.set_default(drill.MODE_KEY, "1")
        with self.assertRaises(frappe.AuthenticationError):
            drill.block_demo_login(self._login_manager(demo))
        drill.block_demo_login(self._login_manager(real))  # akun nyata tetap boleh

    def test_hook_registered(self):
        hooks = frappe.get_hooks("on_login")
        self.assertIn("rescue_net.services.drill.block_demo_login", hooks)
