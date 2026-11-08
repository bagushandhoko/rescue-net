"""Uploaded files through the API (2026-11-02: nginx only proxies the API, /files and /private/files were 404)."""

import frappe
from frappe.utils.file_manager import save_file

from rescue_net import api_files
from rescue_net.tests.factories import RNTestCase, as_guest, as_user, make_actor, make_event, make_org, make_posko

PNG = b"\x89PNG\r\n\x1a\n" + b"\x02" * 64


class TestApiFiles(RNTestCase):
    def setUp(self):
        super().setUp()
        self.event = make_event(event_status="active")
        org = make_org(verification_status="verified")
        self.posko = make_posko(self.event, org)
        self.mgr = make_actor(org=org, org_role="owner", posko=self.posko)
        self.stranger = make_actor()

    def _get(self, url):
        frappe.local.response = frappe._dict()
        api_files.file(url)
        return frappe.local.response

    def test_public_file_for_everyone(self):
        f = save_file("rab-uji.png", PNG + b"pub", None, None, is_private=0)
        with as_guest():
            r = self._get(f.file_url)
        self.assertEqual((r.type, r.filecontent), ("download", PNG + b"pub"))

    def test_private_evidence_only_for_allowed(self):
        from rescue_net.frontend_bridge.map_evidence import upload_evidence
        import base64
        with as_user(self.mgr.user):
            out = upload_evidence("bukti.png", base64.b64encode(PNG + b"priv").decode(), self.event.name,
                                  node_id=self.posko.name, caption="uji")
        url = out["file_url"]
        with as_guest(), self.assertRaises(frappe.PermissionError):
            self._get(url)
        with as_user(self.stranger.user), self.assertRaises(frappe.PermissionError):
            self._get(url)
        with as_user(self.mgr.user):
            self.assertEqual(self._get(url).filecontent, PNG + b"priv")

    def test_no_path_tricks(self):
        for bad in ("/files/../site_config.json", "/etc/passwd", "/private/files/a/b.png", "files/x.png"):
            with as_guest(), self.assertRaises(frappe.PermissionError):
                self._get(bad)

    def test_org_manager_sees_member_evidence(self):
        """Owner 2026-11-08: the organisation's manager (no posko assignment) sees photos its members upload."""
        from rescue_net.frontend_bridge.map_evidence import upload_evidence
        import base64
        org = frappe.db.get_value("RN Posko", self.posko.name, "organization")
        member = make_actor(org=frappe._dict(name=org), org_role="member", posko=self.posko)
        head = make_actor(org=frappe._dict(name=org), org_role="owner")
        other_org_head = make_actor(org=make_org(), org_role="owner")
        with as_user(member.user):
            url = upload_evidence("b2.png", base64.b64encode(PNG + b"m").decode(), self.event.name,
                                  node_id=self.posko.name, caption="uji")["file_url"]
        with as_user(head.user):
            self.assertEqual(self._get(url).filecontent, PNG + b"m")
        with as_user(other_org_head.user), self.assertRaises(frappe.PermissionError):
            self._get(url)
