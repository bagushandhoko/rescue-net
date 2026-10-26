"""CAP & HXL exports (2026-10-26)."""

import datetime
import json

import frappe

from rescue_net import api_export
from rescue_net.services import early_warning as ew
from rescue_net.tests.factories import RNTestCase, _insert, as_guest, make_world
from rescue_net.tests.test_early_warning import payload


class TestExports(RNTestCase):
    def test_cap_alert_is_valid_cap_xml(self):
        ew.process([payload()])
        name = frappe.get_all("RN Early Warning", filters={"meets_threshold": 1}, pluck="name")[0]
        with as_guest():
            r = api_export.cap_alert(name)
            feed = api_export.cap_alerts()
        xml = r.get_data(as_text=True)
        self.assertIn('urn:oasis:names:tc:emergency:cap:1.2', xml)
        self.assertIn("<event>Gempa bumi</event>", xml)
        self.assertIn("<circle>", xml)
        self.assertEqual(r.mimetype, "application/cap+xml")
        self.assertIn(name, feed.get_data(as_text=True))

    def test_hxl_csv_has_hashtag_row(self):
        w = make_world()
        with as_guest():
            r = api_export.hxl_needs(w.event.name)
        lines = r.get_data(as_text=True).splitlines()
        self.assertTrue(lines[1].startswith("#loc+name"))
        self.assertEqual(r.mimetype, "text/csv")
