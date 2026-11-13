"""Penyaring umum respons untuk tampilan Riil (owner 2026-11-13: pilih riil tapi data simulasi masih muncul)."""

import json

import frappe
from werkzeug.wrappers import Response

from rescue_net.services import drill, sim_scrub
from rescue_net.tests.test_operational_mode import LABEL_SENT, SENT, OperationalBase
from rescue_net.tests.test_tampilan_riil import _Cookie


def _resp(message):
    return Response(json.dumps({"message": message}), status=200, content_type="application/json")


class _Req:
    def __init__(self, method):
        self.path = "/api/method/" + method


class TestSimScrub(OperationalBase):
    def payload(self):
        return {
            "totals": {"alat_aktif": 3},
            "items": [
                {"title": "HT nyata", "sub": "Posko " + self.real.posko_a.title, "href": "posko-detail.html?id=" + self.real.posko_a.name},
                {"title": "HT sim", "sub": "Posko " + SENT, "href": "posko-detail.html?id=" + self.sim_posko.name + "&event="},
                {"title": "Laporan", "disaster_event": self.sim.name},
                {"title": "[SIMULASI] Org lain"},
                {"title": "Posko label", "posko": self.label_posko.name},
            ],
            "by_event": {self.sim.name: 1, self.real.event.name: 2},
        }

    def run_hook(self, cookie, method="rescue_net.api_comms.comms_board", payload=None):
        r = _resp(payload or self.payload())
        with _Cookie(cookie):
            sim_scrub.after_request(response=r, request=_Req(method))
        return json.loads(r.get_data(as_text=True))["message"]

    def test_riil_removes_simulation_rows(self):
        m = self.run_hook("riil")
        self.assertEqual([x["title"] for x in m["items"]], ["HT nyata"])
        self.assertEqual(list(m["by_event"]), [self.real.event.name])
        self.assertEqual(m["totals"], {"alat_aktif": 3})

    def test_simulasi_view_untouched(self):
        m = self.run_hook(None)
        self.assertEqual(len(m["items"]), 5)

    def test_admin_endpoints_skipped(self):
        m = self.run_hook("riil", method="rescue_net.api_operational_mode.admin_status")
        self.assertEqual(len(m["items"]), 5)

    def test_system_manager_in_operational_mode_sees_all(self):
        self._mode(True)
        frappe.set_user("Administrator")
        self.assertEqual(len(self.run_hook(None)["items"]), 5)
        self.assertEqual(len(self.run_hook("riil")["items"]), 1)  # memilih riil sendiri -> ikut disaring

    def test_real_endpoint_board_is_clean(self):
        from rescue_net import api_comms, api_volunteer
        for fn, name in ((api_comms.comms_board, "rescue_net.api_comms.comms_board"),
                         (api_volunteer.volunteer_board, "rescue_net.api_volunteer.volunteer_board")):
            with _Cookie("riil"):
                raw = fn()
            m = self.run_hook("riil", method=name, payload=json.loads(json.dumps(raw, default=str)))
            text = json.dumps(m)
            self.assertNotIn(SENT, text, name)
            self.assertNotIn(LABEL_SENT, text, name)

    def test_broken_json_is_ignored(self):
        r = Response("bukan json", status=200, content_type="application/json")
        with _Cookie("riil"):
            sim_scrub.after_request(response=r, request=_Req("rescue_net.api_comms.comms_board"))
        self.assertEqual(r.get_data(as_text=True), "bukan json")
