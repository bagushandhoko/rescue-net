"""Owner 2026-11-02 23:20: settings of a posko / program are for its OWNER only — not guests, not other
logged-in users. Server side: every write behind the forms found visible in the guest/stranger audit."""

import frappe

from rescue_net import api_comms, api_medical, api_shelter, api_tender
from rescue_net import api_donor_program as dp
from rescue_net.tests.factories import RNTestCase, _insert, as_guest, as_user, make_actor, make_event, make_org, make_posko


class TestOwnerOnlySettings(RNTestCase):
    def setUp(self):
        super().setUp()
        self.event = make_event(event_status="active")
        self.org = make_org(verification_status="verified")
        self.posko = make_posko(self.event, self.org)
        self.shelter = make_posko(self.event, self.org, posko_type="shelter")
        self.medical = make_posko(self.event, self.org, posko_type="medical")
        self.owner = make_actor(org=self.org, org_role="owner", posko=self.posko)
        for pk in (self.shelter, self.medical):
            _insert("RN Posko Assignment", user_account=self.owner.account, posko=pk.name,
                    assignment_role="operator", status="approved")
        self.stranger = make_actor()           # logged in, another posko's user
        with as_user(self.owner.user):
            self.program = dp.create_special_program(self.event.name, "Program uji", owner_type="organization",
                                                     owner_id=self.org.name, budget_target=1_000_000)["program"]

    def writes(self):
        p, e, sh, md = self.posko.name, self.event.name, self.shelter.name, self.medical.name
        return {
            "shelter.create_occupancy": lambda: api_shelter.create_occupancy(sh, "Shelter uji", capacity_total=10, current_occupancy=5),
            "shelter.create_need": lambda: api_shelter.create_need(sh, "Selimut", quantity_mode="exact", quantity_needed=5),
            "medical.create_case": lambda: api_medical.create_case(md, "PX-UJI-1", "demam"),
            "medical.add_posko_need": lambda: api_medical.add_posko_need(md, "Paracetamol", 10, "strip"),
            "medical.record_aid_received": lambda: api_medical.record_aid_received(md, "Paracetamol", 10, "strip"),
            "medical.record_supply_use": lambda: api_medical.record_supply_use(md, "Paracetamol", 1, "strip"),
            "comms.create_comms_device": lambda: api_comms.create_comms_device("HT uji", "ht", disaster_event=e, posko=p),
            "comms.create_comms_device(org)": lambda: api_comms.create_comms_device("HT org uji", "ht", disaster_event=e, owner_type="organization", owner_id=self.org.name),
            "tender.create_tender(org)": lambda: api_tender.create_tender(e, "Tender uji", rab_total=1000, organization=self.org.name),
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
