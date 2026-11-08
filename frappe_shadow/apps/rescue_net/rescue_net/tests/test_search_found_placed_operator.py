"""Owner 2026-11-08 (Muhammadiyah simulation finding): a SAR coordinator placed on a posko by their organisation
(approved posko assignment, no global operator role) may match a missing report filed at ANOTHER posko with a
found report at their own posko. Someone with no posko still may not."""

import frappe

from rescue_net import api_search_found as sf
from rescue_net.tests.factories import RNTestCase, as_user, make_actor, make_event, make_org, make_posko


class TestPlacedOperatorMatch(RNTestCase):
    def setUp(self):
        super().setUp()
        self.event = make_event(event_status="active")
        org_a, org_b = make_org(), make_org()
        self.posko_a, self.posko_b = make_posko(self.event, org_a), make_posko(self.event, org_b)
        self.sar = make_actor(role="", org=org_a, posko=self.posko_a)         # placed by its org, viewer role
        self.op_b = make_actor(posko=self.posko_b)
        self.nobody = make_actor(role="")
        with as_user(self.op_b.user):
            self.missing = sf.create_missing_report("MP-X1", disaster_event=self.event.name, posko=self.posko_b.name,
                                                    reporter_name="Ibu A", reporter_contact="0811000001")["missing_report"]
        with as_user(self.sar.user):
            self.found = sf.create_found_report("FP-X1", disaster_event=self.event.name, posko=self.posko_a.name,
                                                reporter_name="Tim SAR", reporter_contact="0811000002")["found_report"]

    def test_placed_sar_coordinator_can_match_across_poskos(self):
        with as_user(self.sar.user):
            r = sf.propose_match(self.missing, self.found, match_basis="ciri pakaian sama")
        self.assertTrue(r)

    def test_person_without_posko_cannot_match(self):
        with as_user(self.nobody.user):
            with self.assertRaises(frappe.PermissionError):
                sf.propose_match(self.missing, self.found)
