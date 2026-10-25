"""Control Centre: nilai program donasi yang masuk per penyelenggara (owner 2026-10-25)."""

import frappe

from rescue_net.api_donor_program import donation_summary
from rescue_net.tests.factories import RNTestCase, _insert, as_guest, make_event, make_org, uid


class TestDonationSummary(RNTestCase):
    def test_public_programs_with_organiser_and_received(self):
        ev = make_event()
        org = make_org(title=uid("Org Donasi"))
        p1 = _insert("RN Donor Program", disaster_event=ev.name, program_name=uid("Program A"), owner_type="organization",
                     owner_id=org.name, status="active", public_visibility="summary_public",
                     budget_target=100000000, budget_received=40000000)
        _insert("RN Donor Program", disaster_event=ev.name, program_name=uid("Program B"), owner_type="organization",
                owner_id=org.name, status="active", public_visibility="summary_public",
                budget_target=50000000, budget_received=10000000)
        hidden = _insert("RN Donor Program", disaster_event=ev.name, program_name=uid("Internal"), owner_type="organization",
                         owner_id=org.name, status="active", public_visibility="internal",
                         budget_target=1, budget_received=999)
        cd = _insert("RN Cash Donation", donor_program=p1.name, donor_name="Donatur Uji", amount=250000, status="pending")
        frappe.db.set_value("RN Cash Donation", cd.name, "status", "received")
        with as_guest():
            s = donation_summary(ev.name)
        self.assertEqual(s["program_count"], 2)
        self.assertEqual(s["received_total"], 50000000)
        self.assertEqual(s["target_total"], 150000000)
        self.assertNotIn(hidden.name, [p["id"] for p in s["programs"]])
        a = [p for p in s["programs"] if p["id"] == p1.name][0]
        self.assertEqual((a["organiser"], a["percent"], a["donor_count"]), (org.title, 40.0, 1))
        self.assertEqual(s["organisers"][0]["organiser"], org.title)
        self.assertEqual(s["organisers"][0]["programs"], 2)
