"""Mode latihan (Fase 10g): event/posko/kebutuhan/laporan latihan tidak pernah tampil ke publik atau agregat
nasional, notifikasi latihan hanya simulasi, dan laporan nyata tidak diarahkan ke event latihan."""

import json
from unittest import mock

import frappe

from rescue_net import api_events, api_gis, api_notify
from rescue_net.control_centre import bencana_aktif
from rescue_net.services import drill
from rescue_net.tests import test_public_endpoints as sweep
from rescue_net.tests.factories import (
    RNTestCase,
    _insert,
    as_guest,
    make_event,
    make_org,
    make_posko,
    make_world,
)

SENT = "LATIHAN-SENTINEL-4471"


class DrillBase(RNTestCase):
    def setUp(self):
        super().setUp()
        self.real = make_world()
        self.drill = make_event(title=SENT + " Gempa Latihan", is_drill=1, drill_label="Latihan", event_status="active")
        self.org = make_org(title="Org Latihan")
        self.dposko = make_posko(self.drill, self.org, title=SENT + " Posko", latitude=-6.2, longitude=106.8,
                                 notify_whatsapp_enabled=1, notify_whatsapp_numbers="081200000001")
        _insert("RN Logistic Need", title=SENT + " butuh", posko=self.dposko.name, disaster_event=self.drill.name,
                item_name=SENT + " beras", quantity=10, unit="kg", urgency="critical")
        _insert("RN Community Report", title=SENT + " laporan", description=SENT, disaster_event=self.drill.name,
                posko=self.dposko.name, report_type="water_shortage", status="submitted")

    def blob(self, value):
        return json.dumps(value, default=str)


class TestDrillPublicLists(DrillBase):
    def test_public_event_lists_hide_drill(self):
        with as_guest():
            for result in (api_events.disasters(), api_gis.national_situation(active_only=0),
                           bencana_aktif.active_disasters_board()):
                self.assertNotIn(SENT, self.blob(result))
        # event nyata tetap tampil (filter tidak membuang semuanya)
        with as_guest():
            self.assertIn(self.real.event.title, self.blob(api_events.disasters()))

    def test_include_drill_is_system_manager_only(self):
        with as_guest():
            self.assertNotIn(SENT, self.blob(api_events.disasters(include_drill=1)))
        self.assertIn(SENT, self.blob(api_events.disasters(include_drill=1)))  # Administrator
        self.assertNotIn(SENT, self.blob(api_events.disasters()))  # default tetap tanpa latihan

    def test_national_numbers_exclude_drill_poskos(self):
        with as_guest():
            n = api_gis.national_situation(active_only=0)
        self.assertNotIn(self.dposko.name, self.blob(n))
        self.assertTrue(all(pt.get("name") != self.dposko.name for pt in n.get("points", [])))
        with as_guest():
            with_drill = api_gis.national_situation(active_only=0, include_drill=1)
        self.assertEqual(n["totals"]["posko_total"], with_drill["totals"]["posko_total"])  # tamu: include_drill diabaikan
        internal = api_gis.national_situation(active_only=0, include_drill=1)  # Administrator = System Manager
        self.assertEqual(internal["totals"]["posko_total"], n["totals"]["posko_total"] + 1)


class TestDrillNotifications(DrillBase):
    def _live_setting(self):
        row = frappe.db.get_value("RN Notification Setting", {"scope": "global"}, "name")
        if row:
            doc = frappe.get_doc("RN Notification Setting", row)
            doc.update({"provider": "fonnte", "enabled": 1, "api_token": "x", "status": "active"})
            doc.save(ignore_permissions=True)
        else:
            _insert("RN Notification Setting", scope="global", provider="fonnte", enabled=1, api_token="x", status="active")

    def test_drill_posko_never_hits_real_gateway(self):
        self._live_setting()
        called = mock.Mock(return_value=(True, "id", ""))
        with mock.patch.dict(api_notify._ADAPTERS, {"fonnte": called}):
            r = api_notify.send_whatsapp("081200000001", "uji", posko=self.dposko.name)
            self.assertEqual(r["status"], "simulated")
            via_ctx = api_notify.send_whatsapp("081200000001", "uji", context_type="posko", context_id=self.dposko.name)
            self.assertEqual(via_ctx["status"], "simulated")
            called.assert_not_called()
            # kontrol: posko nyata tetap lewat gateway
            r2 = api_notify.send_whatsapp("081200000001", "uji", posko=self.real.posko_a.name)
            self.assertEqual(r2["status"], "sent")
            called.assert_called_once()


class TestDrillRouting(DrillBase):
    def test_unscoped_report_is_not_routed_to_drill_poskos(self):
        from rescue_net.services import report_routing

        frappe.db.set_value("RN Disaster Event", self.real.event.name, "event_status", "active")
        names = {p.name for p in report_routing._candidates({})}
        self.assertNotIn(self.dposko.name, names)
        self.assertIn(self.real.posko_a.name, names)


class TestDrillGuestSweep(DrillBase):
    """Setiap endpoint tamu dipanggil dengan id event/posko latihan: sentinel latihan tak boleh muncul."""

    def test_no_drill_sentinel_in_any_guest_endpoint(self):
        import inspect

        leaks = set()
        for path, fn in sorted(sweep.guest_methods().items()):
            if path in sweep.NOT_SWEPT:
                continue
            sig = inspect.signature(inspect.unwrap(fn))
            fixed = {"disaster_event": self.drill.name, "disaster_event_id": self.drill.name,
                     "event": self.drill.name, "organization": self.org.name, "item": SENT + " beras"}
            kwargs, ok = {}, True
            for name, p in sig.parameters.items():
                if name in fixed:
                    kwargs[name] = fixed[name]
                elif name in ("posko", "source_posko"):
                    kwargs[name] = self.dposko.name
                elif name == "dimension":
                    from rescue_net.api_control_centre import _DRILL_BUILDERS
                    kwargs[name] = next(iter(_DRILL_BUILDERS))
                elif p.default is inspect.Parameter.empty:
                    ok = False
            if not ok:
                continue
            frappe.db.savepoint("drill_sweep")
            with as_guest():
                try:
                    frappe.local.form_dict = frappe._dict(kwargs)
                    drill.guard_guest_refs(frappe.local.form_dict)  # = hook before_request (lihat test hook di bawah)
                    result = frappe.call(fn, **kwargs)
                except Exception:
                    frappe.db.rollback(save_point="drill_sweep")
                    frappe.local.message_log = []
                    continue
            if SENT in self.blob(result):
                leaks.add(path)
        self.assertEqual(sorted(leaks), [], "endpoint tamu membocorkan data event latihan")


class TestDrillRequestGuard(DrillBase):
    def test_guard_refuses_guest_but_not_system_manager(self):
        for params in ({"disaster_event": self.drill.name}, {"event": "disaster_events:" + self.drill.legacy_id},
                       {"posko": self.dposko.name}):
            with as_guest():
                with self.assertRaises(frappe.DoesNotExistError):
                    drill.guard_guest_refs(frappe._dict(params))
            drill.guard_guest_refs(frappe._dict(params))  # Administrator lolos
        with as_guest():
            drill.guard_guest_refs(frappe._dict({"disaster_event": self.real.event.name, "posko": self.real.posko_a.name}))

    def test_hook_is_registered_and_ignores_non_api_requests(self):
        self.assertIn("rescue_net.services.drill.before_request", frappe.get_hooks("before_request"))
        drill.before_request()  # tanpa request nyata: tidak melempar


class TestDrillTools(RNTestCase):
    def test_create_hides_from_public_and_cleanup_requires_matching_total(self):
        from rescue_net.services import drill_tools

        real = make_world()
        ev = drill_tools.create_drill("banjir")
        self.assertTrue(frappe.db.get_value("RN Disaster Event", ev, "is_drill"))
        with as_guest():
            self.assertNotIn("[LATIHAN]", json.dumps(api_events.disasters(), default=str))
        p = drill_tools.preview_cleanup(ev)
        self.assertEqual(len(p["items"]["RN Posko"]), 2)
        self.assertEqual(len(p["items"]["RN Logistic Need"]), 3)
        self.assertEqual(p["total"], 2 + 3 + 1)
        with self.assertRaises(frappe.ValidationError):
            drill_tools.cleanup(ev, p["total"] + 1)           # konfirmasi salah -> tidak ada yang dihapus
        self.assertTrue(frappe.db.exists("RN Disaster Event", ev))
        r = drill_tools.cleanup(ev, p["total"])
        self.assertEqual(r["deleted"]["RN Posko"], 2)
        self.assertFalse(frappe.db.exists("RN Disaster Event", ev))
        self.assertTrue(frappe.db.exists("RN Disaster Event", real.event.name))   # data nyata utuh
        self.assertTrue(frappe.db.exists("RN Posko", real.posko_a.name))

    def test_non_drill_event_can_never_be_cleaned(self):
        from rescue_net.services import drill_tools

        real = make_world()
        for fn in (lambda: drill_tools.preview_cleanup(real.event.name), lambda: drill_tools.cleanup(real.event.name, 1),
                   lambda: drill_tools.preview_cleanup(""), lambda: drill_tools.cleanup(None, 0)):
            with self.assertRaises(frappe.ValidationError):
                fn()
        self.assertTrue(frappe.db.exists("RN Posko", real.posko_a.name))

    def test_financial_records_block_cleanup(self):
        from rescue_net.services import drill_tools

        ev = drill_tools.create_drill("gempa")
        frappe.db.sql("insert into `tabRN Cash Donation` (name, disaster_event, creation, modified, owner, modified_by, docstatus) "
                      "values ('DRILLCASH1', %s, now(), now(), 'Administrator', 'Administrator', 0)", ev)
        p = drill_tools.preview_cleanup(ev)
        self.assertEqual(p["blocked"], {"RN Cash Donation": 1})
        with self.assertRaises(frappe.ValidationError):
            drill_tools.cleanup(ev, p["total"])
        self.assertTrue(frappe.db.exists("RN Disaster Event", ev))

    def test_drill_api_is_system_manager_only(self):
        from rescue_net import api_drill
        from rescue_net.tests.factories import make_actor, as_user

        actor = make_actor(role="citizen")
        with as_user(actor.user):
            with self.assertRaises(frappe.PermissionError):
                api_drill.create_drill("banjir")
        with as_guest():
            with self.assertRaises(frappe.PermissionError):
                api_drill.drill_cleanup_preview("x")

    def test_drill_status_reports_flag(self):
        real = make_world()
        d = make_event(is_drill=1, drill_label="Latihan banjir")
        self.assertEqual(api_events.drill_status(d.name), {"is_drill": 1, "label": "Latihan banjir"})
        self.assertEqual(api_events.drill_status(real.event.name), {"is_drill": 0})
