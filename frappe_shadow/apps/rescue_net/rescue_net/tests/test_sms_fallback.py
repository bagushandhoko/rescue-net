"""SMS cadangan (Fase 10c): templat tetap, jenis terbatas, batas harian, latihan tak mengirim, cadangan dari WA gagal."""

from unittest import mock

import frappe

from rescue_net import api_notify
from rescue_net.services import sms
from rescue_net.tests.factories import RNTestCase, _insert, make_event, make_posko, make_world


def _setting(scope, provider, **kw):
    row = frappe.db.get_value("RN Notification Setting", {"scope": scope}, "name")
    values = dict(provider=provider, enabled=1, api_token="AC1:tok", sender_id="+15005550006", status="active", **kw)
    if row:
        doc = frappe.get_doc("RN Notification Setting", row)
        doc.update(values)
        doc.save(ignore_permissions=True)
    else:
        _insert("RN Notification Setting", scope=scope, channel="sms" if scope.startswith("sms:") else "whatsapp", **values)


class TestSmsText(RNTestCase):
    def test_template_is_fixed_ascii_and_short(self):
        t = sms.sms_text("peringatan", "AB-12 <script>")
        self.assertLessEqual(len(t), 160)
        self.assertTrue(t.isascii())
        self.assertIn("kode AB-12script", t)                   # kode disaring: hanya huruf/angka/strip
        self.assertNotIn("<", t)
        with self.assertRaises(frappe.ValidationError):
            sms.sms_text("promosi")

    def test_free_text_cannot_be_injected(self):
        r = sms.send_sms("081200000001", "peringatan", "K1")
        self.assertEqual(frappe.db.get_value("RN Notification Log", r["log"], "body"), sms.sms_text("peringatan", "K1"))

    def test_only_allowed_kinds_are_sent(self):
        self.assertEqual(sms.send_sms("081200000001", "ringkasan")["status"], "skipped")
        self.assertEqual(frappe.db.count("RN Notification Log", {"channel": "sms"}), 0)


class TestSmsSending(RNTestCase):
    def test_default_is_simulation_and_logged(self):
        r = sms.send_sms("0812-0000-0001", "penugasan", "T9")
        self.assertEqual(r["status"], "simulated")
        lg = frappe.get_doc("RN Notification Log", r["log"])
        self.assertEqual((lg.channel, lg.to_number, lg.event_key, lg.scope), ("sms", "6281200000001", "penugasan", "sms:global"))

    def test_live_provider_is_called_only_when_enabled_and_configured(self):
        sender = mock.Mock(return_value=(True, "SM1", ""))
        with mock.patch.dict(sms.SMS_ADAPTERS, {"twilio_sms": sender}):
            _setting("sms:global", "twilio_sms")
            r = sms.send_sms("081200000001", "peringatan")
        self.assertEqual(r["status"], "sent")
        sender.assert_called_once()
        self.assertEqual(sender.call_args.args[1], "6281200000001")

    def test_provider_failure_is_logged_not_raised(self):
        with mock.patch.dict(sms.SMS_ADAPTERS, {"twilio_sms": mock.Mock(return_value=(False, "", "gateway down"))}):
            _setting("sms:global", "twilio_sms")
            r = sms.send_sms("081200000001", "peringatan")
        self.assertEqual((r["status"], r["error"]), ("failed", "gateway down"))

    def test_daily_limit_blocks_further_sms(self):
        _setting("sms:global", "simulasi", daily_limit=2)
        results = [sms.send_sms("08120000000%d" % i, "peringatan")["status"] for i in range(1, 5)]
        self.assertEqual(results, ["simulated", "simulated", "failed", "failed"])
        self.assertEqual(frappe.db.get_value("RN Notification Log", {"channel": "sms", "status": "failed"}, "error"),
                         "batas harian SMS tercapai")

    def test_invalid_number_is_failed(self):
        self.assertEqual(sms.send_sms("abc", "peringatan")["status"], "failed")

    def test_drill_posko_never_sends_sms_for_real(self):
        d = make_event(is_drill=1)
        p = make_posko(d)
        sender = mock.Mock(return_value=(True, "X", ""))
        with mock.patch.dict(sms.SMS_ADAPTERS, {"twilio_sms": sender}):
            _setting("sms:global", "twilio_sms")
            r = sms.send_sms("081200000001", "peringatan", posko=p.name)
        self.assertEqual(r["status"], "simulated")
        sender.assert_not_called()


class TestFallback(RNTestCase):
    def test_failed_whatsapp_falls_back_to_sms_once(self):
        _setting("global", "fonnte")
        wa = mock.Mock(return_value=(False, "", "no internet"))
        with mock.patch.dict(api_notify._ADAPTERS, {"fonnte": wa}):
            out = sms.send_with_fallback("081200000001", "Peringatan banjir", "peringatan", "B1")
            self.assertEqual(out["whatsapp"]["status"], "failed")
            self.assertEqual(out["sms"]["status"], "simulated")
            sms.sweep_failed_whatsapp()                           # sudah ada SMS cadangan -> tidak dobel
        self.assertEqual(frappe.db.count("RN Notification Log", {"channel": "sms"}), 1)
        self.assertEqual(frappe.db.get_value("RN Notification Log", out["sms"]["log"], "fallback_of"), out["whatsapp"]["log"])

    def test_successful_whatsapp_sends_no_sms(self):
        _setting("global", "fonnte")
        with mock.patch.dict(api_notify._ADAPTERS, {"fonnte": mock.Mock(return_value=(True, "ok", ""))}):
            out = sms.send_with_fallback("081200000001", "Peringatan", "peringatan")
        self.assertIsNone(out["sms"])
        self.assertEqual(frappe.db.count("RN Notification Log", {"channel": "sms"}), 0)

    def test_sweep_covers_failed_whatsapp_from_other_paths_but_only_allowed_kinds(self):
        _setting("global", "fonnte")
        with mock.patch.dict(api_notify._ADAPTERS, {"fonnte": mock.Mock(return_value=(False, "", "x"))}):
            api_notify.send_whatsapp("081200000001", "a", event_key="peringatan")
            api_notify.send_whatsapp("081200000002", "b", event_key="ringkasan")
        sms.sweep_failed_whatsapp()
        sent = frappe.get_all("RN Notification Log", filters={"channel": "sms"}, pluck="to_number")
        self.assertEqual(sent, ["6281200000001"])

    def test_sms_scope_only_accepts_sms_providers(self):
        with self.assertRaises(frappe.ValidationError):
            api_notify.save_notification_setting(scope="sms:global", provider="fonnte")
        with self.assertRaises(frappe.ValidationError):
            api_notify.save_notification_setting(scope="global", provider="twilio_sms")
        api_notify.save_notification_setting(scope="sms:global", provider="twilio_sms", enabled=0)
        self.assertEqual(frappe.db.get_value("RN Notification Setting", {"scope": "sms:global"}, "channel"), "sms")
