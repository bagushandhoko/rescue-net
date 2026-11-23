from unittest.mock import patch

import frappe
from werkzeug.test import EnvironBuilder
from werkzeug.wrappers import Request

from rescue_net.dms_sim.seed import _insert
from rescue_net.services import drill
from rescue_net.tests.factories import RNTestCase, as_guest, make_event, make_posko, uid


KEY = "x" * 48


def request(host="rescue-net.online", key="", mode="simulasi"):
    env = EnvironBuilder(
        base_url="https://rescue-net.online",
        path="/api/method/rescue_net.api_events.disasters",
        query_string={"rn_tampilan": mode},
        headers={"X-Forwarded-Host": host, "X-RN-DMS-Proxy-Key": key},
    ).get_environ()
    return patch.object(frappe.local, "request", Request(env), create=True)


class TestDMSDrillScope(RNTestCase):
    def setUp(self):
        super().setUp()
        self.rn = make_event(title="[SIMULASI] RN demo", event_status="active").name
        self.real = make_event(event_status="active").name
        self.dms = make_event(title="[SIMULASI] DMS demo", event_status="active", is_drill=1, drill_scope="dms")
        self.posko = make_posko(event=self.dms).name
        self.rows = [{"name": name} for name in (self.real, self.rn, self.dms.name)]
        config = patch.dict(frappe.conf, {"rn_dms_proxy_key": KEY})
        config.start()
        self.addCleanup(config.stop)

    def test_rn_excludes_dms_even_for_manager_and_with_forged_host(self):
        for headers in (("rescue-net.online", ""), ("disastermanagement.online", "incorrect")):
            with request(*headers):
                self.assertEqual(drill.real_rows(self.rows, key="name"), self.rows[:2])
                self.assertEqual(drill.real_rows(self.rows, key="name", include_drill=1), self.rows[:2])
                with self.assertRaises(frappe.DoesNotExistError):
                    drill.guard_guest_refs({"posko": self.posko})

    def test_dms_simulation_and_real_modes(self):
        with request("disastermanagement.online", KEY), as_guest():
            self.assertEqual(drill.real_rows(self.rows, key="name"), self.rows[2:])
            self.assertEqual(drill.drop_hidden_rows([{"posko": self.posko}]), [{"posko": self.posko}])
            self.assertTrue(drill.is_drill_posko(self.posko))  # Notification safety.
            drill.guard_guest_refs({"event": self.dms.name})
            with self.assertRaises(frappe.DoesNotExistError):
                drill.guard_guest_refs({"event": self.rn})
        with request("disastermanagement.online", KEY, "riil"), as_guest():
            self.assertEqual(drill.real_rows(self.rows, key="name"), self.rows[:1])
            with self.assertRaises(frappe.DoesNotExistError):
                drill.guard_guest_refs({"event": self.dms.name})

    def test_seed_id_is_reused(self):
        name = uid("seed-access")
        fields = dict(disaster_event=self.dms.name, kind="road", place_name="Jalur latihan",
                      status="closed", observed_at="2026-11-23 06:00:00", valid_until="2026-11-25 06:00:00")
        self.assertEqual(_insert("RN Access Status", name, **fields), name)
        before = frappe.db.get_value("RN Access Status", name, "modified")
        self.assertEqual(_insert("RN Access Status", name, **fields), name)
        self.assertEqual(frappe.db.get_value("RN Access Status", name, "modified"), before)
