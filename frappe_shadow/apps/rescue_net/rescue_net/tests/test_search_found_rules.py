"""Search & Found match rules hold on every save path (phase 2: SF-2, SF-3, SF-4)."""

import frappe
from frappe.utils import now_datetime

from rescue_net.tests.factories import RNTestCase, _insert, make_event, make_world, uid


def missing(event, **kw):
    return _insert("RN Missing Person Report", disaster_event=event.name, person_code=uid("MP"),
                   report_status=kw.pop("report_status", "missing"), observed_at=now_datetime(), **kw)


def found(event, **kw):
    return _insert("RN Found Person Report", disaster_event=event.name, person_code=uid("FP"),
                   report_status=kw.pop("report_status", "found"), observed_at=now_datetime(), **kw)


def match(m, f, status="proposed"):
    return _insert("RN Search Found Match", missing_report=m.name, found_report=f.name, match_status=status)


def status(doctype, name):
    return frappe.db.get_value(doctype, name, "report_status")


class TestMatchRules(RNTestCase):
    def setUp(self):
        super().setUp()
        self.w = make_world()
        self.m = missing(self.w.event)
        self.f = found(self.w.event)

    def test_match_starts_proposed(self):
        with self.assertRaises(frappe.ValidationError):
            match(self.m, self.f, status="reunited")

    def test_transition_graph_on_direct_save(self):
        doc = match(self.m, self.f)
        doc.match_status = "reunited"          # skips confirmed
        with self.assertRaises(frappe.ValidationError):
            doc.save(ignore_permissions=True)

    def test_reports_of_different_events_do_not_match(self):
        with self.assertRaises(frappe.ValidationError):
            match(self.m, found(make_event()))

    def test_closed_report_does_not_match(self):
        with self.assertRaises(frappe.ValidationError):
            match(self.m, found(self.w.event, report_status="closed"))

    def test_reunite_marks_both_reports(self):
        doc = match(self.m, self.f)
        for s in ("confirmed", "reunited"):
            doc.match_status = s
            doc.save(ignore_permissions=True)
        self.assertEqual(status("RN Missing Person Report", self.m.name), "reunited")
        self.assertEqual(status("RN Found Person Report", self.f.name), "reunited")

    def test_rejecting_a_proposal_does_not_un_reunite_a_person(self):
        other = found(self.w.event)
        stale = match(self.m, other)                     # proposed before the reunion
        good = match(self.m, self.f)
        for s in ("confirmed", "reunited"):
            good.match_status = s
            good.save(ignore_permissions=True)
        stale.reload()
        stale.match_status = "rejected"
        stale.save(ignore_permissions=True)
        self.assertEqual(status("RN Missing Person Report", self.m.name), "reunited")

    def test_one_confirmed_match_per_report(self):
        a = match(self.m, self.f)
        b = match(self.m, found(self.w.event))
        a.match_status = "confirmed"
        a.save(ignore_permissions=True)
        b.match_status = "confirmed"
        with self.assertRaises(frappe.ValidationError):
            b.save(ignore_permissions=True)
