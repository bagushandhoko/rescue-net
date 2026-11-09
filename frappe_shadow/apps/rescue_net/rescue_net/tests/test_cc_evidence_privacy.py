"""owner 2026-11-09: bukti dari organisasi tertutup tidak tampil di Control Centre; organisasi terbuka & masyarakat tampil."""

import frappe

from rescue_net.control_centre.map_evidence import _drop_closed_org_evidence, event_evidence
from rescue_net.tests.factories import RNTestCase, _insert, make_world


class TestCCEvidencePrivacy(RNTestCase):
    def test_closed_org_evidence_hidden(self):
        w = make_world()
        frappe.db.set_value("RN Organization", w.org_a.name, "privacy_mode", "open")
        frappe.db.set_value("RN Organization", w.org_b.name, "privacy_mode", "closed")
        for p, fn in ((w.posko_a, "terbuka.jpg"), (w.posko_b, "tertutup.jpg")):
            _insert("RN Evidence File", legacy_id=frappe.generate_hash(length=12), title="Bukti " + fn, disaster_event=w.event.name, posko=p.name,
                    file_path="/files/" + fn, evidence_type="photo")
        rows = event_evidence(w.event.name)
        self.assertEqual({r.get("posko") for r in rows} & {w.posko_a.name, w.posko_b.name}, {w.posko_a.name, w.posko_b.name})
        _drop_closed_org_evidence(rows)
        poskos = {r.get("posko") for r in rows}
        self.assertIn(w.posko_a.name, poskos)
        self.assertNotIn(w.posko_b.name, poskos)

    def test_closed_member_chooses_internal_or_public(self):
        from rescue_net.frontend_bridge.map_evidence import upload_evidence
        from rescue_net.tests.factories import as_user, make_actor
        import base64
        w = make_world()
        frappe.db.set_value("RN Organization", w.org_b.name, "privacy_mode", "closed")
        frappe.db.set_value("RN Organization", w.org_a.name, "privacy_mode", "open")
        member = make_actor(posko=w.posko_b)
        outsider = make_actor(posko=w.posko_a)
        import io
        from PIL import Image
        def jpg(c):
            buf = io.BytesIO(); Image.new("RGB", (8, 8), c).save(buf, "JPEG")
            return base64.b64encode(buf.getvalue()).decode()
        with as_user(member.user):
            upload_evidence("internal.jpg", jpg((200, 0, 0)), w.event.name, node_id=w.posko_b.name, caption="internal")
            upload_evidence("publik.jpg", jpg((0, 200, 0)), w.event.name, node_id=w.posko_b.name, caption="publik", public=1)
        with as_user(outsider.user):
            upload_evidence("warga.jpg", jpg((0, 0, 200)), w.event.name, caption="warga")            # masyarakat, tanpa posko
            with self.assertRaises(frappe.PermissionError):
                upload_evidence("x.jpg", jpg((90, 90, 90)), w.event.name, node_id=w.posko_b.name)   # bukan anggota org tertutup
        rows = event_evidence(w.event.name)
        _drop_closed_org_evidence(rows)
        caps = {r.get("caption") or r.get("title") for r in rows}
        self.assertIn("publik", caps)
        self.assertIn("warga", caps)
        self.assertNotIn("internal", caps)
