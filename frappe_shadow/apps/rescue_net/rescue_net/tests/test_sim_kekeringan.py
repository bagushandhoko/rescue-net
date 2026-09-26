"""E2E simulation — Kekeringan Kabupaten Kupang, NTT (kemarau panjang 2026).

Runs only on the isolated test stack (never production): every row is made
here and rolled back. One story, through the same whitelisted API the pages
call:

  1. Three villagers report by narrative (no form): wells dry in Oebelo,
     children with diarrhoea, failed harvest in Tesabela. The keyword parser
     fills the form; each report lands at the relevant posko with a reason.
  2. The drought report predicts water per Sphere (15 L/person/day) and
     tanker trips.
  3. The reporter adds a follow-up (more people, jerrycans); the posko answers.
  4. The village posko turns it into a logistic need; PMI offers water; the
     district posko sends a tanker flow; the village posko receives it into
     stock.
  5. The health posko records the diarrhoea cases.
  6. Bencana Aktif / Control Centre show the event with its poskos.
"""

import json

import frappe

from rescue_net import api_control_centre as cc
from rescue_net import api_logistics as logistics
from rescue_net import api_medical as medical
from rescue_net import api_reports as reports
from rescue_net.tests.factories import (
    RNTestCase, as_guest, as_user, make_actor, make_event, make_org, make_posko, make_transport_space,
)


class TestSimKekeringanKupang(RNTestCase):
    def setUp(self):
        super().setUp()
        self.event = make_event(title="Kekeringan Kabupaten Kupang 2026", event_status="active")
        bpbd = make_org(title="BPBD Kabupaten Kupang")
        pmi = make_org(title="PMI Kabupaten Kupang")
        area = dict(province_name="Nusa Tenggara Timur", city_name="Kupang")
        self.p_oebelo = make_posko(self.event, bpbd, title="Posko Air Bersih Oebelo", posko_type="logistics",
                                   village_name="Oebelo", district_name="Kupang Tengah",
                                   latitude=-10.103, longitude=123.717, coverage_radius_meters=5000, **area)
        self.p_sehat = make_posko(self.event, bpbd, title="Posko Kesehatan Kupang Tengah", posko_type="medical",
                                  district_name="Kupang Tengah", latitude=-10.115, longitude=123.725, **area)
        self.p_kab = make_posko(self.event, bpbd, title="Posko Logistik Kabupaten", posko_type="logistics",
                                district_name="Kupang Timur", latitude=-10.18, longitude=123.84, **area)
        self.op_oebelo = make_actor(posko=self.p_oebelo)
        self.op_sehat = make_actor(posko=self.p_sehat)
        self.op_kab = make_actor(posko=self.p_kab)
        self.pmi_member = make_actor(org=pmi, org_role="member")
        self.bpbd_member = make_actor(org=bpbd, org_role="member")
        self.warga = [make_actor(role="viewer") for _ in range(3)]

    def lapor(self, who, text, **kw):
        with as_user(who.user):
            return reports.submit_community_report(description=text, intake_mode="narrative",
                                                   disaster_event=self.event.name, **kw)

    def test_kekeringan_end_to_end(self):
        # 1. narrative reports, routed
        wells = self.lapor(self.warga[0],
                           "Sumur di Desa Oebelo kering sejak 2 bulan. 50 KK kekurangan air bersih, "
                           "anak-anak harus jalan 3 km ambil air. Mohon segera kirim tangki air.",
                           latitude=-10.104, longitude=123.718)
        sick = self.lapor(self.warga[1],
                          "12 anak di Desa Oebelo diare dan demam karena minum air kotor, butuh obat dan dokter.",
                          latitude=-10.105, longitude=123.719)
        harvest = self.lapor(self.warga[2],
                             "Gagal panen di Kecamatan Kupang Timur, sungai kering, 80 orang kekurangan air minum.")

        w = frappe.get_doc("RN Community Report", wells["name"])
        self.assertEqual((w.report_type, w.priority, w.affected_people_count), ("water_shortage", "urgent", 200))
        self.assertEqual(w.posko, self.p_oebelo.name)
        self.assertIn("radius layanan", w.routing_reason)
        self.assertEqual(frappe.db.get_value("RN Community Report", sick["name"], "report_type"), "medical_case")
        self.assertEqual(sick["posko"], self.p_sehat.name)
        self.assertEqual(harvest["posko"], self.p_kab.name)  # the only posko of Kupang Timur

        # 2. drought predictions: 200 people x 15 L = 3,000 L/day = 1 tanker trip
        by = {n["category"]: n["predicted_qty"] for n in wells["predicted_needs"]}
        self.assertEqual((by["air_bersih"], by["truk_tangki_air"], by["jerigen"]), (3000, 1, 80))

        # 3. follow-up thread: reporter adds, posko answers, others cannot
        with as_user(self.warga[0].user):
            reports.add_community_report_update(wells["name"], "Sekarang 70 KK, sumur desa sebelah juga kering.",
                                                update_type="additional_need", urgent_needs="jerigen 100 pcs",
                                                affected_people_count=280)
        with as_user(self.op_oebelo.user):
            reports.add_community_report_update(wells["name"], "Truk tangki dijadwalkan besok pagi.")
        with as_user(self.warga[1].user), self.assertRaises(frappe.PermissionError):
            reports.add_community_report_update(wells["name"], "bukan laporan saya")
        with as_user(self.warga[0].user):
            mine = reports.my_community_reports()
        self.assertEqual([u.author_role for u in mine[0]["updates"]], ["reporter", "posko"])

        # 4. need -> offer -> tanker flow -> receipt into stock
        with as_user(self.op_oebelo.user):
            need = logistics.create_need(self.p_oebelo.name, "Air bersih", quantity=5000, unit="liter",
                                         urgency="critical", jiwa_terdampak=280)["need"]
        with as_user(self.pmi_member.user):
            # PMI is not the posko's org: the posko must open public participation
            with self.assertRaises(frappe.PermissionError):
                logistics.create_aid_offer(self.p_oebelo.name, "PMI Kupang", "Air bersih", quantity=5000, unit="liter")
        with as_user(self.bpbd_member.user):
            offer = logistics.create_aid_offer(self.p_oebelo.name, "BPBD Kupang (gudang)", "Air bersih",
                                               quantity=5000, unit="liter")["aid_offer"]
        tanker = make_transport_space(self.p_kab, title="Truk Tangki 5.000 L")
        # the tanker belongs to the district posko: its operator sends it
        with as_user(self.op_oebelo.user), self.assertRaises(frappe.PermissionError):
            logistics.create_flow(self.p_oebelo.name, "Air bersih", quantity=5000, unit="liter",
                                  transport_space=tanker.name)
        with as_user(self.op_kab.user):
            flow = logistics.create_flow(self.p_oebelo.name, "Air bersih", quantity=5000, unit="liter",
                                         source_posko=self.p_kab.name, logistic_need=need, aid_offer=offer,
                                         transport_space=tanker.name)["flow"]
            for status in ("assigned_pickup", "dispatched"):
                logistics.update_flow_status(flow, status)
        with as_user(self.op_oebelo.user):
            logistics.update_flow_status(flow, "arrived_at_posko")
            logistics.receive_flow_and_update_stock(flow, 5000, "liter", "Diterima di bak penampungan desa")
        self.assertEqual(frappe.db.get_value("RN Distribution Flow", flow, "flow_status"), "received")
        self.assertEqual(frappe.db.get_value("RN Aid Offer", offer, "offer_status"), "delivered")
        stock = frappe.get_all("RN Stock Observation", filters={"posko": self.p_oebelo.name},
                               fields=["item_name", "quantity", "unit"])
        self.assertTrue(any(s.quantity == 5000 for s in stock), stock)

        # 5. health posko records the diarrhoea cases
        with as_user(self.op_sehat.user):
            for i in range(3):
                medical.create_case(self.p_sehat.name, f"KPG-DIARE-{i}", "Diare akut, dehidrasi ringan",
                                    age_group="child", severity="moderate", triage_status="yellow")
        self.assertEqual(frappe.db.count("RN Medical Case", {"posko": self.p_sehat.name}), 3)

        # 6. the public Bencana Aktif board shows the event and its poskos (no report text leaks)
        with as_guest():
            board = cc.active_disasters_board()
        blob = json.dumps(board, default=str)
        self.assertIn("Kekeringan Kabupaten Kupang 2026", blob)
        self.assertIn("Posko Air Bersih Oebelo", blob)
        self.assertNotIn("KPG-DIARE", blob)
