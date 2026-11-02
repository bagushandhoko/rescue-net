"""Owner 2026-11-02 sore: "pastikan AI benar-benar berfungsi untuk semua user atau organisasi ... bisa jalankan
pengaturan posko dan setting lainnya, atau menjelaskan bagaimana penggunaan rescue-net"."""

import json
from unittest.mock import patch

import frappe

from rescue_net import api_ai
from rescue_net import api_assistant as aa
from rescue_net.services import llm
from rescue_net.tests.factories import RNTestCase, _insert, as_user, make_actor, make_org, make_world
from rescue_net.tests.test_ai_budget import ORG_KEY
from rescue_net.tests.test_assistant import KEY

PLATFORM_KEY = "fake-byok-PLATFORM-0123456789abcdefWXYZ"


class TestAssistantForEveryone(RNTestCase):
    """The assistant really uses the same key chain as the rest of the AI: own key → shared org key → platform key."""

    def setUp(self):
        super().setUp()
        self.org = make_org()
        self.owner = make_actor(org=self.org, org_role="owner")
        self.member = make_actor(org=self.org, org_role="member")
        self.lone = make_actor(role="relawan")

    def status(self, who, **kw):
        with as_user(who.user):
            return aa.status(**kw)

    def test_no_key_anywhere_tells_how_to_fix(self):
        s = self.status(self.lone)
        self.assertEqual(s["status"], "no_key")
        self.assertEqual(s["settings"], "pages/ai-settings.html")

    def test_shared_org_key_then_platform_key(self):
        with as_user(self.owner.user):
            api_ai.save_org_key(self.org.name, ORG_KEY)
            api_ai.save_ai_profile("organization", self.org.name, provider="openai", share_with_members=1)
        self.assertEqual((self.status(self.member)["status"], self.status(self.member)["source"]), ("ok", "kunci AI organisasi"))
        self.assertEqual(self.status(self.lone)["status"], "no_key")       # not a member
        api_ai.save_platform_key(PLATFORM_KEY, provider="openai")
        s = self.status(self.lone)
        self.assertEqual((s["status"], s["source"]), ("ok", "kunci AI bersama Rescue-Net"))
        # chosen organisation context: members only
        self.assertEqual(self.status(self.member, organization_id=self.org.name)["status"], "ok")
        self.assertEqual(self.status(self.lone, organization_id=self.org.name)["status"], "forbidden")

    def test_chat_reaches_the_model_with_the_platform_key(self):
        api_ai.save_platform_key(PLATFORM_KEY, provider="openai")
        with as_user(self.lone.user), patch.object(llm, "chat", return_value=("Halo", {"total_tokens": 3})) as m:
            r = aa.chat("bagaimana cara mendaftar jadi relawan?")
        self.assertEqual((r["status"], r["answer"]), ("ok", "Halo"))
        self.assertEqual(m.call_args[0][1], PLATFORM_KEY)


class TestAssistantSettingsActions(RNTestCase):
    def setUp(self):
        super().setUp()
        self.w = make_world()
        frappe.db.set_value("RN Disaster Event", self.w.event.name, "event_status", "active")
        self.mgr = make_actor(posko=self.w.posko_a)
        self.other = make_actor()
        self.rel = make_actor(role="relawan")
        self.prof = _insert("RN Volunteer Profile", user_account=self.rel.account, disaster_event=self.w.event.name,
                            volunteer_name="Relawan Uji", contact="0812", main_skill="medis")
        self.bk = _insert("RN Volunteer Booking", booking_kind="posko", status="requested", volunteer=self.prof.name,
                          user_account=self.rel.account, disaster_event=self.w.event.name, posko=self.w.posko_a.name)

    def ctx(self, user, q, **kw):
        seen = {}

        def fake_chat(provider, key, model, system, content, **k):
            seen["ctx"] = content[0]
            return "ok", {"total_tokens": 1}
        with as_user(user), patch("rescue_net.ai.keys.resolve_ai", return_value=dict(KEY, owner_id=user)), \
                patch.object(llm, "chat", side_effect=fake_chat):
            aa.chat(q, **kw)
        return json.loads(seen["ctx"].split("\n", 1)[1])

    def act(self, user, action, params):
        with as_user(user):
            return aa.run_action(action, json.dumps(params))

    def test_manual_only_for_how_to_questions(self):
        c = self.ctx(self.other.user, "bagaimana cara mendaftarkan posko?")
        self.assertIn("Manual Rescue-Net", c["MANUAL_PENGGUNA"])
        self.assertIn("Registrasi akun / login / peran", c["PAGE_MAP"])
        self.assertNotIn("MANUAL_PENGGUNA", self.ctx(self.other.user, "stok beras posko A"))

    def test_manager_context_has_contact_needs_and_volunteer_requests(self):
        c = self.ctx(self.mgr.user, "apa yang perlu saya tindak", posko=self.w.posko_a.name)
        self.assertIn(self.bk.name, [v["name"] for v in c["posko_aktif"]["permintaan_relawan"]])
        self.assertIn("kontak", c["posko_aktif"])
        c2 = self.ctx(self.other.user, "apa yang perlu saya tindak", posko=self.w.posko_a.name)
        self.assertNotIn("posko_aktif", c2)

    def test_volunteer_sees_only_own_profile(self):
        c = self.ctx(self.rel.user, "ubah keahlian saya")
        self.assertEqual(c["profil_relawan_anda"]["profil"]["main_skill"], "medis")
        self.assertNotIn("profil_relawan_anda", self.ctx(self.mgr.user, "ubah keahlian saya"))

    def test_posko_settings_by_the_manager_only(self):
        pa = self.w.posko_a.name
        for action, params in (("posko_contact", {"posko": pa, "officer_in_charge_phone": "0812-1111-2222"}),
                               ("need_create", {"posko": pa, "item_text": "Beras", "quantity": 50, "unit": "kg"}),
                               ("stock_record", {"posko": pa, "item_text": "Air mineral", "quantity": 20, "unit": "dus"}),
                               ("volunteer_decide", {"booking": self.bk.name, "decision": "reject"})):
            with self.assertRaises(frappe.PermissionError, msg=action):
                self.act(self.other.user, action, params)
            self.assertTrue(self.act(self.mgr.user, action, params)["ok"], action)
        self.assertEqual(frappe.db.get_value("RN Posko", pa, "officer_in_charge_phone"), "0812-1111-2222")
        self.assertTrue(frappe.db.exists("RN Logistic Need", {"posko": pa, "item_name": ["like", "%Beras%"]}))
        self.assertTrue(frappe.db.exists("RN Stock Observation", {"posko": pa, "item_name": ["like", "%Air mineral%"]}))
        self.assertEqual(frappe.db.get_value("RN Volunteer Booking", self.bk.name, "status"), "rejected")
        with self.assertRaisesRegex(frappe.ValidationError, "jiwa"):
            self.act(self.mgr.user, "need_create", {"posko": pa, "item_text": "Obat", "urgency": "critical"})

    def test_own_volunteer_profile(self):
        with self.assertRaises(frappe.PermissionError):
            self.act(self.other.user, "volunteer_profile", {"main_skill": "masak"})      # no volunteer profile
        self.act(self.rel.user, "volunteer_profile", {"main_skill": "evakuasi air", "available_from": "2026-11-05"})
        self.assertEqual(frappe.db.get_value("RN Volunteer Profile", self.prof.name, "main_skill"), "evakuasi air")

    def test_proposals_kept_only_when_allowed(self):
        reply = ('Baik.\n[[AKSI {"action": "volunteer_decide", "params": {"booking": "%s", "decision": "confirm"}, "label": "Terima"}]]\n'
                 '[[AKSI {"action": "volunteer_profile", "params": {"main_skill": "dapur"}, "label": "Ubah"}]]') % self.bk.name
        with as_user(self.mgr.user), patch("rescue_net.ai.keys.resolve_ai", return_value=dict(KEY, owner_id=self.mgr.user)), \
                patch.object(llm, "chat", return_value=(reply, {"total_tokens": 1})):
            r = aa.chat("tolong", posko=self.w.posko_a.name)
        self.assertEqual([a["action"] for a in r["actions"]], ["volunteer_decide"])   # manager has no volunteer profile



class TestAssistantNoLimit(RNTestCase):
    """Owner 2026-11-02: "kenapa harus dibatasi? bebaskan saja" — no request limit; only the key's AI budget applies."""

    def test_many_questions_in_a_row(self):
        a = make_actor()
        with patch("rescue_net.ai.keys.resolve_ai", return_value=dict(KEY)), \
                patch.object(llm, "chat", return_value=("ok", {"total_tokens": 1})), as_user(a.user):
            got = {aa.chat("halo %d" % i)["status"] for i in range(40)}
        self.assertEqual(got, {"ok"})
