"""Asisten AI di setiap halaman (owner 2026-11-02): login / no key / quota / rejected key → friendly status;
answers get public disaster data + search + ONLY the poskos the user manages; the AI never writes."""

import json
from unittest.mock import patch

import frappe

from rescue_net import api_assistant as aa
from rescue_net.ai import budget
from rescue_net.services import llm
from rescue_net.tests.factories import RNTestCase, as_guest, as_user, make_actor, make_world

KEY = {"api_key": "sk-test", "model": "m", "key_source": "user", "owner_type": "user", "owner_id": None,
       "provider": "openai", "base_url": None}


class TestAssistant(RNTestCase):
    def setUp(self):
        super().setUp()
        self.w = make_world()
        frappe.db.set_value("RN Disaster Event", self.w.event.name, "event_status", "active")
        self.mgr = make_actor(posko=self.w.posko_a)
        self.other = make_actor()

    def test_guest_must_login(self):
        with as_guest():
            self.assertEqual(aa.status()["status"], "login")
            self.assertEqual(aa.chat("halo")["status"], "login")

    def test_no_key(self):
        with as_user(self.other.user), patch("rescue_net.ai.keys.resolve_ai", return_value=None):
            s = aa.status()
            self.assertEqual(s["status"], "no_key")
            self.assertIn("AI Settings", s["message"])
            self.assertEqual(aa.chat("halo")["status"], "no_key")

    def test_quota_spent(self):
        def spent(*a, **k):
            raise budget.AIUnavailable("budget", "Anggaran AI bersama (harian) habis. Pasang kunci AI Anda sendiri di Setting")
        with as_user(self.other.user), patch("rescue_net.ai.keys.resolve_ai", return_value=dict(KEY, owner_id=self.other.user)), \
                patch.object(budget, "check_allowed", side_effect=spent):
            self.assertEqual(aa.status()["status"], "quota")
            r = aa.chat("halo")
        self.assertEqual(r["status"], "quota")
        self.assertIn("habis", r["message"])

    def test_key_rejected(self):
        with as_user(self.other.user), patch("rescue_net.ai.keys.resolve_ai", return_value=dict(KEY, owner_id=self.other.user)), \
                patch.object(llm, "chat", side_effect=llm.LLMError("auth", "401")):
            r = aa.chat("halo")
        self.assertEqual(r["status"], "key_rejected")

    def test_manager_gets_own_posko_context_and_search(self):
        seen = {}

        def fake_chat(provider, key, model, system, content, **kw):
            seen["ctx"] = content[0]
            return "Jawaban uji", {"total_tokens": 10}
        title_a = frappe.db.get_value("RN Posko", self.w.posko_a.name, "title")
        title_b = frappe.db.get_value("RN Posko", self.w.posko_b.name, "title")
        with as_user(self.mgr.user), patch("rescue_net.ai.keys.resolve_ai", return_value=dict(KEY, owner_id=self.mgr.user)), \
                patch.object(llm, "chat", side_effect=fake_chat):
            r = aa.chat("apa yang perlu saya tindak di " + title_b.split()[-1], disaster_event=self.w.event.name,
                        posko=self.w.posko_b.name)
        self.assertEqual((r["status"], r["answer"]), ("ok", "Jawaban uji"))
        ctx = json.loads(seen["ctx"].split("\n", 1)[1])
        self.assertIn(title_a, [p["title"] for p in ctx["posko_yang_anda_kelola"]])
        self.assertNotIn("posko_aktif", ctx)          # asked about posko B, which this user does not manage
        self.assertIn("PAGE_MAP", ctx)
        self.assertIn(self.w.event.name, [e["name"] for e in ctx["bencana_aktif"]])   # always listed, any question
        self.assertIn(self.w.posko_b.name, [p["name"] for p in ctx.get("hasil_pencarian", {}).get("posko", [])])
        with as_user(self.mgr.user), patch("rescue_net.ai.keys.resolve_ai", return_value=dict(KEY, owner_id=self.mgr.user)), \
                patch.object(llm, "chat", side_effect=fake_chat):
            aa.chat("stok posko saya", disaster_event=self.w.event.name, posko=self.w.posko_a.name)
        ctx = json.loads(seen["ctx"].split("\n", 1)[1])
        self.assertEqual(ctx["posko_aktif"]["title"], title_a)


class TestAssistantActions(RNTestCase):
    """Owner 2026-11-02: the AI may PROPOSE changes for the user's own posko; the user presses 'Jalankan'."""

    def setUp(self):
        super().setUp()
        from rescue_net.tests.factories import _insert
        self.w = make_world()
        self.mgr = make_actor(posko=self.w.posko_a)
        self.space = _insert("RN Transport Space", title="Truk AI", provider_name="Truk AI", disaster_event=self.w.event.name,
                             coordination_posko=self.w.posko_a.name, transport_type="darat", capacity_weight_kg=500,
                             transport_status="available")

    def _ask(self, user, reply):
        with as_user(user), patch("rescue_net.ai.keys.resolve_ai", return_value=dict(KEY, owner_id=user)), \
                patch.object(llm, "chat", return_value=(reply, {"total_tokens": 5})):
            return aa.chat("tolong", disaster_event=self.w.event.name, posko=self.w.posko_a.name)

    def test_proposals_filtered_by_rights(self):
        reply = ("Silakan.\n"
                 '[[AKSI {"action": "armada_status", "params": {"transport_space": "%s", "transport_status": "in_transit"}, "label": "Truk AI berangkat"}]]\n'
                 '[[AKSI {"action": "posko_status", "params": {"posko": "%s", "operational_status": "standby"}, "label": "Posko B siaga"}]]\n'
                 '[[AKSI {"action": "hapus_semua", "params": {}, "label": "x"}]]') % (self.space.name, self.w.posko_b.name)
        r = self._ask(self.mgr.user, reply)
        self.assertNotIn("[[AKSI", r["answer"])
        self.assertEqual([a["action"] for a in r["actions"]], ["armada_status"])   # posko B not managed, unknown dropped
        r2 = self._ask(make_actor().user, reply)
        self.assertEqual(r2["actions"], [])

    def test_run_action_as_the_user(self):
        with as_user(make_actor().user), self.assertRaises(frappe.PermissionError):
            aa.run_action("armada_status", json.dumps({"transport_space": self.space.name, "transport_status": "in_transit"}))
        with as_user(self.mgr.user):
            aa.run_action("armada_status", json.dumps({"transport_space": self.space.name, "transport_status": "in_transit"}))
            r = aa.run_action("armada_position", json.dumps({"transport_space": self.space.name}), latitude=4.14, longitude=96.13)
            aa.run_action("comms_support", json.dumps({"posko": self.w.posko_a.name, "needed": "HT 2 unit"}))
            with self.assertRaisesRegex(frappe.ValidationError, "tidak valid"):
                aa.run_action("armada_status", json.dumps({"transport_space": self.space.name, "transport_status": "meledak"}))
        self.assertTrue(r["ok"])
        self.assertEqual(frappe.db.get_value("RN Transport Space", self.space.name, ["transport_status", "position_lat"]),
                         ("in_transit", 4.14))
        self.assertEqual(frappe.db.get_value("RN Posko", self.w.posko_a.name, "comms_support_needed"), "HT 2 unit")
