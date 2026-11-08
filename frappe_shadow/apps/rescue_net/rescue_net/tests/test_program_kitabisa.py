"""Owner 2026-11-08: program donasi "dikelola sendiri" atau "melalui Kitabisa". Kitabisa page parsing is tested on
a saved sample (no network in tests); fetch_campaign is patched."""

from unittest.mock import patch

import frappe

from rescue_net import api_donor_program as api
from rescue_net.donor_program import kitabisa as kb
from rescue_net.tests.factories import RNTestCase, as_guest, as_user, make_actor, make_event, make_org, make_posko

SAMPLE = """<html><head><meta property="og:title" content="Kitabisa-in Yuk! - Bantu Korban Asap Riau"/>
<script type="application/ld+json">{"@context":"https://schema.org","@type":"Product","name":"Bantu Korban Asap Riau ",
"image":["https://gudang-prod.kitabisa.com/images/x.jpg"],"mpn":"123","brand":{"@type":"Brand","name":"Kitabisa.com"},
"manufacturer":{"@type":"Organization","name":"LAZISMU Riau","logo":{"@type":"ImageObject","url":"https://x/logo.png"}},
"offers":[{"@type":"Offer","price":150000000,"priceCurrency":"IDR","availability":"https://schema.org/InStock",
"seller":{"@type":"Organization","name":"LAZISMU Riau"}}]}</script></head><body></body></html>"""


class TestKitabisaParse(RNTestCase):
    def test_parse_sample(self):
        d = kb.parse_campaign_html(SAMPLE, "https://kitabisa.com/campaign/bantuasapriau")
        self.assertEqual(d["title"], "Bantu Korban Asap Riau")
        self.assertEqual(d["organizer"], "LAZISMU Riau")
        self.assertEqual(d["target"], 150_000_000)
        self.assertTrue(d["open"])
        closed = kb.parse_campaign_html(SAMPLE.replace("InStock", "SoldOut"), "u")
        self.assertFalse(closed["open"])

    def test_url_validation(self):
        self.assertEqual(kb.normalize_url("https://kitabisa.com/bantuasapriau"), "https://kitabisa.com/campaign/bantuasapriau")
        for bad in ("http://evil.com/campaign/x", "https://kitabisa.com.evil.io/campaign/x", "javascript:alert(1)"):
            with self.assertRaises(frappe.ValidationError):
                kb.normalize_url(bad)


class TestKitabisaChannel(RNTestCase):
    def setUp(self):
        super().setUp()
        self.event = make_event(event_status="active")
        self.org = make_org(verification_status="verified")
        posko = make_posko(self.event, self.org)
        self.owner = make_actor(org=self.org, org_role="owner", posko=posko)
        self.other = make_actor(org=self.org, org_role="member")
        with as_user(self.owner.user):
            self.program = api.create_special_program(self.event.name, "Asap Riau", owner_type="organization",
                                                      owner_id=self.org.name, status="active")["program"]

    def test_switch_to_kitabisa_shows_block_and_blocks_internal_donation(self):
        parsed = kb.parse_campaign_html(SAMPLE, "https://kitabisa.com/campaign/bantuasapriau")
        with as_user(self.owner.user), patch.object(kb, "fetch_campaign", return_value=parsed):
            api.set_donation_channel(self.program, "kitabisa", kitabisa_url="https://kitabisa.com/campaign/bantuasapriau")
            api.set_kitabisa_figures(self.program, collected=45_500_000, donor_count=812, as_of="2026-11-08")
        with as_guest():
            d = api.program_detail(self.program)
            row = [p for p in api.program_board(self.event.name)["programs"] if p["name"] == self.program][0]
        self.assertEqual(d["donation_channel"], "kitabisa")
        self.assertEqual(d["kitabisa"]["title"], "Bantu Korban Asap Riau")
        self.assertEqual(d["kitabisa"]["collected"], 45_500_000)
        self.assertEqual(d["kitabisa"]["donor_count"], 812)
        self.assertEqual(row["kitabisa"]["url"], "https://kitabisa.com/campaign/bantuasapriau")
        donor = make_actor()
        with as_user(donor.user):
            with self.assertRaisesRegex(frappe.ValidationError, "Kitabisa"):
                api.create_cash_donation(self.program, 10_000)

    def test_only_manager_can_change_channel(self):
        with as_user(self.other.user):
            with self.assertRaises(frappe.PermissionError):
                api.set_donation_channel(self.program, "kitabisa", kitabisa_url="https://kitabisa.com/campaign/x1")
            with self.assertRaises(frappe.PermissionError):
                api.set_kitabisa_figures(self.program, collected=1)

    def test_fetch_failure_keeps_link_with_warning(self):
        with as_user(self.owner.user), patch.object(kb, "fetch_campaign", side_effect=ValueError("HTTP 403")):
            r = api.set_donation_channel(self.program, "kitabisa", kitabisa_url="https://kitabisa.com/campaign/abc123")
        self.assertIn("HTTP 403", r["warning"])
        self.assertEqual(frappe.db.get_value("RN Donor Program", self.program, "kitabisa_url"),
                         "https://kitabisa.com/campaign/abc123")
