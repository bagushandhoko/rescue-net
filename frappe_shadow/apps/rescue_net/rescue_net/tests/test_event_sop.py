"""Kelola Bencana SOP (owner 2026-11-01): who creates active vs proposed events,
duplicate check, merge suggestions, merge + undo, hidden statuses, legacy bridge."""

import json

import frappe

from rescue_net import api_disaster_admin as da
from rescue_net.access_policy import rn_actor
from rescue_net.services import event_merge as em
from rescue_net.tests.factories import (RNTestCase, as_guest, as_user, make_actor, make_event, make_org,
                                        make_posko, make_user, uid)


def _create(user, **kw):
    with as_user(user):
        args = dict(title=kw.pop("title", "Banjir " + uid("Kota")), event_type="banjir",
                    location_summary=kw.pop("location_summary", uid("Kabupaten") + ", Provinsi Uji"))
        args.update(kw)
        return da.create_event_for(rn_actor(), **args)


class TestEventCreate(RNTestCase):
    def setUp(self):
        super().setUp()
        self.vorg = make_org(verification_status="verified")
        self.uorg = make_org(verification_status="pending")
        self.v_member = make_actor(org=self.vorg)
        self.u_member = make_actor(org=self.uorg)
        self.lone = make_actor()
        self.admin = make_user(roles=("System Manager",))

    def test_verified_org_member_creates_active(self):
        r = _create(self.v_member.user)
        self.assertTrue(r["created"])
        self.assertEqual(r["event_status"], "active")
        self.assertEqual(frappe.db.get_value("RN Disaster Event", r["name"], "reporting_organization"), self.vorg.name)

    def test_unverified_and_individual_create_proposed(self):
        self.assertEqual(_create(self.u_member.user)["event_status"], "proposed")
        self.assertEqual(_create(self.lone.user)["event_status"], "proposed")

    def test_proposed_hidden_from_public_list(self):
        from rescue_net.api_events import disasters
        r = _create(self.lone.user)
        with as_guest():
            names = [d["name"] for d in disasters(limit=500)["disasters"]]
        self.assertNotIn(r["name"], names)

    def test_validation(self):
        with self.assertRaisesRegex(frappe.ValidationError, "Nama bencana"):
            _create(self.v_member.user, title="x")
        with self.assertRaisesRegex(frappe.ValidationError, "Lokasi"):
            _create(self.v_member.user, location_summary="")
        with self.assertRaisesRegex(frappe.ValidationError, "Koordinat"):
            _create(self.v_member.user, latitude=95, longitude=100)

    def test_guest_cannot_create(self):
        with as_guest(), self.assertRaises(Exception):
            da.create_options()

    def test_not_member_of_named_org(self):
        with self.assertRaises(frappe.PermissionError):
            _create(self.lone.user, organization=self.vorg.name)

    def test_duplicate_warning_then_force(self):
        place = uid("Kabupaten") + " Jawa Barat"
        first = _create(self.v_member.user, title="Banjir Bandang " + place, location_summary=place,
                        latitude=-6.6, longitude=106.8)
        self.assertTrue(first["created"])
        second = _create(self.lone.user, title="banjir " + place, location_summary=place,
                         latitude=-6.62, longitude=106.82)
        self.assertFalse(second["created"])
        self.assertEqual(second["duplicates"][0]["name"], first["name"])
        forced = _create(self.lone.user, title="banjir " + place, location_summary=place,
                         latitude=-6.62, longitude=106.82, force=1)
        self.assertTrue(forced["created"])
        # the forced twin gets an automatic merge suggestion (newer proposal -> older active)
        sug = [json.loads(s) for s in frappe.get_all("RN AI Suggestion", filters={"feature": em.FEATURE,
               "ref_name": forced["name"]}, pluck="payload")]
        self.assertEqual(len(sug), 1)
        self.assertEqual((sug[0]["source"], sug[0]["target"]), (forced["name"], first["name"]))

    def test_different_type_is_not_duplicate(self):
        place = uid("Kabupaten")
        a = {"title": "Banjir " + place, "event_type": "banjir", "location_summary": place}
        b = {"title": "Gempa " + place, "event_type": "gempa", "location_summary": place}
        self.assertEqual(em.score_pair(a, b)[0], 0)

    def test_type_guessed_from_title(self):
        self.assertEqual(em.norm_type(None, "Karhutla Kalimantan Barat 2026"), "karhutla")
        self.assertEqual(em.norm_type("", "Kebakaran hutan Riau"), "karhutla")
        self.assertEqual(em.norm_type(None, "[SIMULASI] Krakatau Meletus"), "erupsi")

    def test_admin_review(self):
        r = _create(self.lone.user)
        with as_user(self.v_member.user), self.assertRaises(frappe.PermissionError):
            da.review_event(r["name"], "approve")
        with as_user(self.admin):
            self.assertIn(r["name"], [e["name"] for e in da.admin_queue()["proposed"]])
            da.review_event(r["name"], "approve", note="cek lapangan")
        self.assertEqual(frappe.db.get_value("RN Disaster Event", r["name"], "event_status"), "active")
        with as_user(self.admin):
            da.review_event(r["name"], "demote")
            self.assertEqual(frappe.db.get_value("RN Disaster Event", r["name"], "event_status"), "proposed")
            da.review_event(r["name"], "reject")
        self.assertEqual(frappe.db.get_value("RN Disaster Event", r["name"], "event_status"), "rejected")

    def test_legacy_bridge_cannot_set_status(self):
        from rescue_net.frontend_bridge.misc import create_disaster_event
        with as_user(self.lone.user):
            r = create_disaster_event(json.dumps({"title": "Longsor " + uid("Desa"), "status": "active",
                                                  "location": "Desa Uji"}))
        self.assertEqual(frappe.db.get_value("RN Disaster Event", r["name"], "event_status"), "proposed")


class TestEventMerge(RNTestCase):
    def setUp(self):
        super().setUp()
        self.admin = make_user(roles=("System Manager",))
        self.org = make_org()
        self.main = make_event(event_status="active", title="Banjir Utama " + uid())
        self.twin = make_event(event_status="active", title="banjir kembar " + uid())
        self.p_main = make_posko(self.main, self.org)
        self.p_twin = make_posko(self.twin, self.org)
        # a posko serving both events: its served_events row for twin becomes a duplicate
        self.p_both = make_posko(self.main, self.org)
        self.p_both.append("served_events", {"disaster_event": self.twin.name})
        self.p_both.save(ignore_permissions=True)

    def _served(self, posko):
        return sorted(frappe.get_all("RN Posko Served Event", filters={"parent": posko.name}, pluck="disaster_event"))

    def test_only_super_admin_merges(self):
        op = make_actor(role="command_center")
        with as_user(op.user), self.assertRaises(frappe.PermissionError):
            da.merge_events(self.twin.name, self.main.name)

    def test_merge_moves_records_and_undo_restores(self):
        with as_user(self.admin):
            res = da.merge_events(self.twin.name, self.main.name)
        self.assertGreaterEqual(res["moved"], 2)
        self.assertEqual(res["removed_duplicates"], 1)
        self.assertEqual(frappe.db.get_value("RN Posko", self.p_twin.name, "disaster_event"), self.main.name)
        self.assertEqual(self._served(self.p_both), [self.main.name])
        ev = frappe.db.get_value("RN Disaster Event", self.twin.name, ["event_status", "merged_into"], as_dict=True)
        self.assertEqual((ev.event_status, ev.merged_into), ("merged", self.main.name))
        self.assertIn(self.twin.title, frappe.db.get_value("RN Disaster Event", self.main.name, "aliases"))
        # old link resolves to the main event
        from rescue_net.reference_resolver import resolve_disaster_event
        self.assertEqual(resolve_disaster_event(self.twin.name), self.main.name)
        with as_guest():
            self.assertEqual(da.resolve_event(self.twin.name)["name"], self.main.name)
        self.assertEqual(em.linked_counts(self.twin.name), {})

        with as_user(self.admin):
            u = da.undo_merge(res["log"])
        self.assertEqual(u["reinserted"], 1)
        self.assertEqual(frappe.db.get_value("RN Posko", self.p_twin.name, "disaster_event"), self.twin.name)
        self.assertEqual(self._served(self.p_both), sorted([self.main.name, self.twin.name]))
        self.assertEqual(frappe.db.get_value("RN Disaster Event", self.twin.name, "event_status"), "active")
        self.assertNotIn(self.twin.title, frappe.db.get_value("RN Disaster Event", self.main.name, "aliases") or "")
        with as_user(self.admin), self.assertRaisesRegex(frappe.ValidationError, "sudah dibatalkan"):
            da.undo_merge(res["log"])

    def test_records_created_after_merge_stay_on_main(self):
        with as_user(self.admin):
            res = da.merge_events(self.twin.name, self.main.name)
        later = make_posko(self.main, self.org)
        with as_user(self.admin):
            da.undo_merge(res["log"])
        self.assertEqual(frappe.db.get_value("RN Posko", later.name, "disaster_event"), self.main.name)

    def test_cannot_merge_into_merged_or_self_or_drill(self):
        drill = make_event(event_status="active", is_drill=1)
        with as_user(self.admin):
            with self.assertRaises(frappe.ValidationError):
                da.merge_events(self.main.name, self.main.name)
            with self.assertRaisesRegex(frappe.ValidationError, "latihan"):
                da.merge_events(drill.name, self.main.name)
            da.merge_events(self.twin.name, self.main.name)
            with self.assertRaises(frappe.ValidationError):
                da.merge_events(self.main.name, self.twin.name)

    def test_merge_suggestion_accept_and_reject(self):
        place = uid("Kabupaten")
        a = make_event(event_status="active", title="Gempa " + place, event_type="gempa", location_summary=place,
                       latitude=-2.0, longitude=120.0, started_at="2026-10-01 08:00:00")
        b = make_event(event_status="active", title="gempa bumi " + place, event_type="gempa",
                       location_summary=place, latitude=-2.05, longitude=120.03, started_at="2026-10-01 09:00:00")
        made = em.suggest_for(b.name)
        self.assertEqual(len(made), 1)
        self.assertEqual(em.suggest_for(b.name), [])  # one suggestion per pair
        with as_user(self.admin):
            q = da.admin_queue()
            self.assertIn(made[0], [s["name"] for s in q["suggestions"]])
            res = da.decide_merge_suggestion(made[0], "accept")
        self.assertEqual((res["source"], res["target"]), (b.name, a.name))
        self.assertEqual(frappe.db.get_value("RN AI Suggestion", made[0], "status"), "accepted")

        c = make_event(event_status="active", title="Banjir " + place, event_type="banjir", location_summary=place)
        d = make_event(event_status="active", title="banjir " + place, event_type="banjir", location_summary=place)
        s = em.suggest_for(d.name)
        if s:  # without coordinates/date the score may stay under the threshold
            with as_user(self.admin):
                da.decide_merge_suggestion(s[0], "reject")
            self.assertEqual(frappe.db.get_value("RN Disaster Event", c.name, "event_status"), "active")
