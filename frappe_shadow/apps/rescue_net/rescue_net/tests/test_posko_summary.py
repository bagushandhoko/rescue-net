"""Ringkasan semua posko satu jenis (control_centre.posko_summary.posko_summary), owner 2026-11-09 malam.

Satu baris per posko; angka diambil dari papan posko yang sama dengan halaman detail, tamu boleh
membaca, data pribadi (kontak petugas, data pasien) tidak ikut."""

import frappe

from rescue_net.tests.factories import (
    RNTestCase,
    _insert,
    api_call,
    as_guest,
    as_user,
    contains_value,
    make_actor,
    make_event,
    make_medical_case,
    make_org,
    make_posko,
    make_transport_space,
    uid,
)

METHOD = "rescue_net.api_control_centre.posko_summary"
PHONE = "+62811-7777-4242"


class TestPoskoSummary(RNTestCase):
    def setUp(self):
        super().setUp()
        self.event = make_event()
        self.org = make_org(title=uid("Org Terbuka"))
        geo = dict(latitude=-6.2, longitude=106.8, officer_in_charge_phone=PHONE, operational_status="active")
        self.log = make_posko(self.event, self.org, posko_type="logistics", title=uid("Gudang"), **geo)
        self.trans = make_posko(self.event, self.org, posko_type="transport", title=uid("Armada"), **geo)
        self.med = make_posko(self.event, self.org, posko_type="medical", title=uid("Klinik"), **geo)
        self.shel = make_posko(self.event, self.org, posko_type="shelter", title=uid("Shelter"), **geo)
        self.kit = make_posko(self.event, self.org, posko_type="kitchen", title=uid("Dapur"), **geo)
        self.other_event_log = make_posko(make_event(), self.org, posko_type="logistics", **geo)

        _insert("RN Logistic Need", title=uid("Butuh"), disaster_event=self.event.name, posko=self.log.name,
                item_name="Beras", quantity=100, unit="kg", need_status="open", urgency="critical")
        make_transport_space(self.trans, disaster_event=self.event.name, capacity_weight_kg=1000)
        make_transport_space(self.trans, disaster_event=self.event.name, capacity_weight_kg=500,
                             transport_status="completed")
        make_medical_case(self.med, disaster_event=self.event.name, patient_name="Pasien Rahasia Uji",
                          triage_status="red")
        _insert("RN Shelter Occupancy", disaster_event=self.event.name, posko=self.shel.name,
                shelter_name="Aula", capacity_total=100, current_occupancy=80, children_count=10)

    def summary(self, kind):
        with as_guest():
            return api_call(METHOD, disaster_event=self.event.name, kind=kind)

    def row(self, res, posko):
        rows = [r for r in res["rows"] if r["posko"] == posko.name]
        self.assertEqual(len(rows), 1, res["rows"])
        return rows[0]

    def test_each_kind_lists_only_its_poskos_of_this_event(self):
        expect = {"logistik": self.log, "distribusi": self.trans, "medis": self.med,
                  "shelter": self.shel, "dapur": self.kit}
        for kind, posko in expect.items():
            res = self.summary(kind)
            names = {r["posko"] for r in res["rows"]}
            self.assertEqual(names, {posko.name}, kind)
            self.assertNotIn(self.other_event_log.name, names)

    def test_metrics_match_posko_boards(self):
        m = self.row(self.summary("logistik"), self.log)["metrics"]
        self.assertEqual(m["kebutuhan_terbuka"], 1)
        self.assertEqual(m["kebutuhan_kritis"], 1)

        m = self.row(self.summary("distribusi"), self.trans)["metrics"]
        self.assertEqual(m["armada"], 2)
        self.assertEqual(m["armada_aktif"], 1)

        m = self.row(self.summary("shelter"), self.shel)["metrics"]
        self.assertEqual(m["penghuni"], 80)
        self.assertEqual(m["okupansi_pct"], 80)

    def test_guest_gets_no_contact_or_patient_data(self):
        for kind in ("logistik", "distribusi", "medis", "shelter", "dapur"):
            res = self.summary(kind)
            self.assertFalse(contains_value(res, PHONE), kind)
            self.assertFalse(contains_value(res, "Pasien Rahasia Uji"), kind)
        m = self.row(self.summary("medis"), self.med)["metrics"]
        self.assertIsNone(m["pasien_aktif"])

    def test_member_sees_own_posko_marked_first(self):
        mine = make_posko(self.event, self.org, posko_type="logistics", title="AAA " + uid("Milik"),
                          latitude=-6.1, longitude=106.7)
        actor = make_actor(org=self.org, posko=mine)
        with as_user(actor.user):
            res = api_call(METHOD, disaster_event=self.event.name, kind="logistik")
        self.assertEqual(res["rows"][0]["posko"], mine.name)
        self.assertTrue(res["rows"][0]["mine"])

    def test_unknown_kind_refused(self):
        with as_guest():
            with self.assertRaises(frappe.ValidationError):
                api_call(METHOD, disaster_event=self.event.name, kind="hapus")
