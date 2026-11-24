"""Temuan seed data simulasi 24 Nov 2026 (owner: "lengkapi data simulasi supaya kelihatan kurang-kurangnya"):
(1) posko serba-fungsi bercentang shelter ditolak "Posko ini bukan Shelter"; (2) Simulasi Terbuka belum mencakup
proyek pemulihan; (3) rencana pengungsian bisa ditulis siapa pun yang login, juga di bencana riil."""

import frappe

from rescue_net import api_aid_card, api_displacement, api_recovery_support, api_shelter
from rescue_net.tests.factories import RNTestCase, _insert, as_user, make_actor, make_event, make_posko


def _sim(ev):
    from rescue_net.services import drill
    names = set(drill._json_list(drill.EXTRA_KEY)) | {ev.name}
    frappe.db.set_default(drill.EXTRA_KEY, frappe.as_json(sorted(names)))
    return ev


class TestSeedTemuan(RNTestCase):
    def test_multi_function_posko_with_shelter_flag_can_run_shelter(self):
        ev = make_event()
        posko = make_posko(ev, posko_type="logistics", rn_fn_shelter=1)
        op = make_actor(posko=posko)
        with as_user(op.user):
            api_shelter.check_in_household(posko.name, "KK-UJI-1", 4)
            r = api_aid_card.create_round(posko.name, "Putaran uji")
        self.assertTrue(r)
        self.assertIn(posko.name, api_shelter._all_shelters())
        plain = make_posko(ev, posko_type="logistics")
        op2 = make_actor(posko=plain)
        with as_user(op2.user), self.assertRaises(frappe.ValidationError):
            api_shelter.check_in_household(plain.name, "KK-UJI-2", 3)

    def test_sim_open_covers_recovery_project_but_not_real(self):
        sim, real = _sim(make_event()), make_event()
        mk = lambda ev: _insert("RN Recovery Project", disaster_event=ev.name, project_name="Rehab uji",
                                owner_type="organization", owner_id="ORG-TIDAK-ADA")
        ps, pr = mk(sim), mk(real)
        a = make_actor()
        with as_user(a.user):
            api_recovery_support.create_volunteer_need(ps.name, "Tukang", 2)
            with self.assertRaises(frappe.PermissionError):
                api_recovery_support.create_volunteer_need(pr.name, "Tukang", 2)

    def test_displacement_write_needs_posko_manager_on_real_event(self):
        real = make_event()
        posko = make_posko(real)
        outsider, op = make_actor(), make_actor(posko=posko)
        with as_user(outsider.user), self.assertRaises(frappe.PermissionError):
            api_displacement.create_displacement_plan(real.name, "Desa A", 4)
        with as_user(op.user):
            r = api_displacement.create_displacement_plan(real.name, "Desa A", 4, posko=posko.name)
        with as_user(outsider.user), self.assertRaises(frappe.PermissionError):
            api_displacement.update_displacement_plan(r["plan"], status="approved")
        sim = _sim(make_event())
        with as_user(outsider.user):
            self.assertTrue(api_displacement.create_displacement_plan(sim.name, "Desa B", 3)["plan"])

    def test_displacement_board_real_detail_only_for_managers(self):
        from rescue_net.tests.factories import as_guest
        real = make_event()
        posko = make_posko(real)
        op, outsider = make_actor(posko=posko), make_actor()
        with as_user(op.user):
            api_displacement.create_displacement_plan(real.name, "Desa A", 4, household_code="KK-RAHASIA", posko=posko.name)
        with as_guest():
            g = api_displacement.displacement_board(real.name)
        self.assertEqual(g["plans"], [])
        self.assertEqual(g["detail_hidden"], 1)
        self.assertEqual(g["totals"]["people_total"], 4)
        self.assertNotIn("KK-RAHASIA", frappe.as_json(g))
        with as_user(outsider.user):
            self.assertEqual(api_displacement.displacement_board(real.name)["plans"], [])
        with as_user(op.user):
            self.assertEqual([p["household_code"] for p in api_displacement.displacement_board(real.name)["plans"]], ["KK-RAHASIA"])
        sim = _sim(make_event())
        with as_user(op.user):
            api_displacement.create_displacement_plan(sim.name, "Desa B", 3, household_code="KK-SIM")
        with as_guest():
            self.assertEqual([p["household_code"] for p in api_displacement.displacement_board(sim.name)["plans"]], ["KK-SIM"])

    def test_session_runs_posko_is_real_role_not_sim_open(self):
        from rescue_net import api_auth
        sim = _sim(make_event())
        posko = make_posko(sim)
        op, citizen = make_actor(posko=posko), make_actor(role="citizen")
        with as_user(op.user):
            self.assertTrue(api_auth.session_info()["runs_posko"])
        with as_user(citizen.user):
            self.assertFalse(api_auth.session_info()["runs_posko"])   # Simulasi Terbuka tidak menjadikannya pengelola
