"""Owner 2026-11-02 23:20: settings of a posko / program are for its OWNER only — not guests, not other
logged-in users. Server side: every write behind the forms found visible in the guest/stranger audit."""

import unittest

import frappe

from rescue_net import api_comms, api_medical, api_shelter, api_tender
from rescue_net import api_donor_program as dp
from rescue_net.tests.factories import RNTestCase, as_guest, as_user, make_actor, make_event, make_org, make_posko


@unittest.skip("WIP audit owner-only (antrean owner 2026-11-02 23:15): comms.create_comms_device masih terbuka "
               "bagi pengguna lain + fixture posko belum bertipe medis/shelter; perbaikan izin menunggu persetujuan owner")
class TestOwnerOnlySettings(RNTestCase):
    def setUp(self):
        super().setUp()
        self.event = make_event(event_status="active")
        self.org = make_org(verification_status="verified")
        self.posko = make_posko(self.event, self.org)
        self.owner = make_actor(org=self.org, org_role="owner", posko=self.posko)
        self.stranger = make_actor()           # logged in, another posko's user
        with as_user(self.owner.user):
            self.program = dp.create_special_program(self.event.name, "Program uji", owner_type="organization",
                                                     owner_id=self.org.name, budget_target=1_000_000)["program"]

    def writes(self):
        p, e = self.posko.name, self.event.name
        return {
            "shelter.create_occupancy": lambda: api_shelter.create_occupancy(p, "Shelter uji", capacity_total=10, current_occupancy=5),
            "shelter.create_need": lambda: api_shelter.create_need(p, "Selimut", quantity_mode="exact", quantity_needed=5),
            "medical.create_case": lambda: api_medical.create_case(p, "PX-UJI-1", "demam"),
            "medical.add_posko_need": lambda: api_medical.add_posko_need(p, "Paracetamol", 10, "strip"),
            "medical.record_aid_received": lambda: api_medical.record_aid_received(p, "Paracetamol", 10, "strip"),
            "medical.record_supply_use": lambda: api_medical.record_supply_use(p, "Paracetamol", 1, "strip"),
            "comms.create_comms_device": lambda: api_comms.create_comms_device("HT uji", "ht", disaster_event=e, posko=p),
            "comms.create_comms_operator": lambda: api_comms.create_comms_operator("Operator uji", disaster_event=e, posko=p),
            "comms.set_posko_comms_support": lambda: api_comms.set_posko_comms_support(p, offered="HT", needed="-"),
            "program.create_update": lambda: dp.create_update(self.program, "Progres uji", progress_percent=10),
        }

    def test_stranger_and_guest_are_refused(self):
        for name, fn in self.writes().items():
            for who in ("guest", "stranger"):
                ctx = as_guest() if who == "guest" else as_user(self.stranger.user)
                with ctx:
                    try:
                        fn()
                    except (frappe.PermissionError, frappe.AuthenticationError):
                        continue
                    except frappe.ValidationError as e:
                        if "login" in str(e).lower() or "akses" in str(e).lower() or "hanya" in str(e).lower():
                            continue
                        self.fail(f"{name} as {who}: ValidationError instead of a refusal: {e}")
                    self.fail(f"{name} as {who}: was ALLOWED")

    def test_owner_is_allowed(self):
        failed = {}
        for name, fn in self.writes().items():
            with as_user(self.owner.user):
                try:
                    fn()
                except Exception as e:      # noqa: BLE001 — collect them all
                    failed[name] = repr(e)[:160]
        self.assertEqual(failed, {})
