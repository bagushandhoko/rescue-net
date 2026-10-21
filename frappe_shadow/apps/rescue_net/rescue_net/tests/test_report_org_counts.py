"""Community report counts (C-2, C-4) and the posko-choice cascade (O-1) hold on a direct save."""

import frappe

from rescue_net.access_policy import public_posko_allowed
from rescue_net.tests.factories import RNTestCase, _insert, make_event, make_posko


class TestReportCounts(RNTestCase):
    def report(self, **kw):
        return _insert("RN Community Report", title="Uji", description="uji", status="submitted", **kw)

    def test_trust_score_and_counts(self):
        for bad in ({"trust_score": 101}, {"trust_score": -1}, {"affected_people_count": -3},
                    {"damage_scale_value": -10}):
            with self.assertRaises(frappe.ValidationError):
                self.report(**bad)
        self.assertTrue(self.report(trust_score=100, affected_people_count=0).name)


class TestOrgClosesCascade(RNTestCase):
    def test_public_posko_stays_public_when_the_org_closes(self):
        # A closed org keeps its activity private by default, but a posko it
        # deliberately set to "public" (e.g. a shared TNI ship) stays public as
        # long as the org still allows posko choice. Closing no longer strips it.
        org = _insert("RN Organization", title="Org Terbuka Uji", privacy_mode="open", allow_posko_public_choice=1)
        posko = make_posko(make_event(), org, public_detail="public")
        self.assertTrue(public_posko_allowed(posko.name))
        org.privacy_mode = "closed"
        org.control_centre_share = "aggregate"
        org.save(ignore_permissions=True)
        self.assertEqual(frappe.db.get_value("RN Posko", posko.name, "public_detail"), "public")
        self.assertTrue(public_posko_allowed(posko.name))

    def test_switching_off_the_choice_cascades(self):
        org = _insert("RN Organization", title="Org Pilihan Uji", privacy_mode="open", allow_posko_public_choice=1)
        posko = make_posko(make_event(), org, public_detail="public")
        org.allow_posko_public_choice = 0
        org.save(ignore_permissions=True)
        self.assertEqual(frappe.db.get_value("RN Posko", posko.name, "public_detail"), "inherit")
