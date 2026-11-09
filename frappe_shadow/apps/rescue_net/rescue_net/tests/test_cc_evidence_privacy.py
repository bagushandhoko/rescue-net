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
