"""Organisasi & Posko: per-posko members, org detail counts, resource summary, completeness score."""

from rescue_net import api_control_centre as cc
from rescue_net.tests.factories import RNTestCase, _insert, make_actor, make_world


class TestOrgBoard(RNTestCase):
    def setUp(self):
        super().setUp()
        self.w = make_world()
        self.op = make_actor(posko=self.w.posko_a, org=self.w.org_a)

    def test_board_counts_approved_members_per_posko(self):
        data = cc.org_posko_board(self.w.event.name)
        org = next(o for o in data["orgs"] if o["name"] == self.w.org_a.name)
        self.assertEqual(org["poskos"][0]["member_count"], 1)

    def test_detail_counts_resources_and_score(self):
        _insert("RN Resource Profile", owner_type="organization", owner_id=self.w.org_a.name,
                resource_name="Pickup", resource_type="vehicle", category="kendaraan", quantity=2)
        _insert("RN Resource Profile", owner_type="organization", owner_id=self.w.org_a.name,
                resource_name="Motor", resource_type="vehicle", category="kendaraan", quantity=3)
        d = cc.org_detail(self.w.org_a.name)
        self.assertEqual(d["counts"]["poskos"], 1)
        veh = next(r for r in d["resources"] if r["category"] == "kendaraan")
        self.assertEqual((veh["items"], veh["quantity"]), (2, 5))
        t = d["trust"]
        self.assertEqual(t["score"], 25 * sum(1 for c in t["checks"] if c["done"]))
        self.assertIn(t["grade"], "ABCD")
        self.assertTrue(next(c for c in t["checks"] if c["key"] == "anggota")["done"])
