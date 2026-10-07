"""Search & Found board: likeness score, suggestions, claims, guest privacy."""

import frappe
from frappe.utils import now_datetime

from rescue_net import api_search_found
from rescue_net.services.search_found import match_score
from rescue_net.tests.factories import (
    RNTestCase, _insert, api_call, as_guest, as_user, contains_value, make_actor, make_world, uid,
)


def missing(event, **kw):
    return _insert("RN Missing Person Report", disaster_event=event.name, person_code=uid("MP"),
                   report_status="missing", observed_at=now_datetime(), **kw)


def found(event, **kw):
    return _insert("RN Found Person Report", disaster_event=event.name, person_code=uid("FP"),
                   report_status="found", observed_at=now_datetime(), **kw)


class TestScore(RNTestCase):
    def test_same_child_scores_high_and_other_kind_zero(self):
        w = make_world()
        m = missing(w.event, age_years=12, gender="laki-laki", clothing_description="kaos merah celana biru",
                    last_seen_location="Kampung Melayu")
        f = found(w.event, age_years=12, gender="laki-laki", clothing_description="kaos merah celana biru",
                  found_location="Kampung Melayu")
        self.assertGreaterEqual(match_score(m, f), 85)
        pet = found(w.event, subject_type="hewan", age_years=12, gender="laki-laki",
                    clothing_description="kaos merah celana biru")
        self.assertEqual(match_score(m, pet), 0)

    def test_gender_or_age_clash_drops_the_score(self):
        w = make_world()
        m = missing(w.event, age_years=12, gender="laki-laki", clothing_description="kaos merah")
        same = found(w.event, age_years=12, gender="laki-laki", clothing_description="kaos merah")
        other = found(w.event, age_years=45, gender="perempuan", clothing_description="kaos merah")
        self.assertLess(match_score(m, other), 40)
        self.assertGreater(match_score(m, same), match_score(m, other) + 40)


class TestBoard(RNTestCase):
    def setUp(self):
        super().setUp()
        self.w = make_world()
        self.op = make_actor(posko=self.w.posko_a)
        self.m = missing(self.w.event, person_name="Rahasia Satu", age_years=12, gender="perempuan",
                         clothing_description="jaket kuning")
        self.f = found(self.w.event, person_name="Rahasia Dua", age_years=11, gender="perempuan",
                       clothing_description="jaket kuning")

    def board(self):
        return api_call("rescue_net.api_search_found.dashboard", disaster_event=self.w.event.name)

    def test_guest_sees_suggestion_without_names_or_photos(self):
        with as_guest():
            data = self.board()
        pairs = data["board"]["orang"]["possible"]
        self.assertEqual(len(pairs), 1)
        self.assertGreaterEqual(pairs[0]["score"], 70)
        self.assertFalse(contains_value(data, "Rahasia"))
        self.assertEqual(data["photos"]["items"], [])
        self.assertEqual(data["kpis"]["orang_hilang"]["n"], 1)
        self.assertEqual(data["kpis"]["belum_teridentifikasi"]["n"], 1)

    def test_propose_stores_the_score_and_confirmed_goes_active(self):
        with as_user(self.op.user):
            res = api_search_found.propose_match(self.m.name, self.f.name)
            self.assertGreaterEqual(frappe.db.get_value("RN Search Found Match", res["match"], "match_score"), 70)
            api_search_found.update_match_status(res["match"], "confirmed", "ok")
            data = self.board()
        self.assertEqual(data["board"]["orang"]["possible"], [])
        self.assertEqual(len(data["board"]["orang"]["active"]), 1)

    def test_identification_counts_follow_status_and_reunion(self):
        with as_user(self.op.user):
            api_search_found.set_identification_status(self.f.name, "proses_identifikasi")
            self.assertEqual(self.board()["identification"]["proses_identifikasi"], 1)
            with self.assertRaises(frappe.ValidationError):
                api_search_found.set_identification_status(self.f.name, "ngawur")
        with as_guest():
            with self.assertRaises((frappe.PermissionError, frappe.ValidationError)):
                api_search_found.set_identification_status(self.f.name, "teridentifikasi")


class TestClaims(RNTestCase):
    def setUp(self):
        super().setUp()
        self.w = make_world()
        self.op = make_actor(posko=self.w.posko_a)

    def test_claim_flow_and_graph(self):
        with as_user(self.op.user):
            res = api_search_found.create_claim("Tas ransel hitam", disaster_event=self.w.event.name,
                                                posko=self.w.posko_a.name, claimant_name="Andi",
                                                claimant_contact="0812")
            self.assertTrue(res["claim_code"].startswith("CLM-"))
            with self.assertRaises(frappe.ValidationError):   # cannot skip verification
                api_search_found.update_claim_status(res["claim"], "selesai")
            for s in ("terverifikasi", "siap_diserahkan", "selesai"):
                api_search_found.update_claim_status(res["claim"], s)

    def test_guest_lists_claims_without_claimant(self):
        with as_user(self.op.user):
            api_search_found.create_claim("Dompet kulit", disaster_event=self.w.event.name,
                                          posko=self.w.posko_a.name, claimant_name="Budi Rahasia",
                                          claimant_contact="0899")
        with as_guest():
            data = api_call("rescue_net.api_search_found.dashboard", disaster_event=self.w.event.name)
        self.assertEqual(len(data["claims"]), 1)
        self.assertFalse(contains_value(data, "Budi Rahasia"))
        self.assertFalse(contains_value(data, "0899"))

    def test_guest_cannot_file_a_claim(self):
        with as_guest():
            with self.assertRaises((frappe.PermissionError, frappe.ValidationError)):
                api_search_found.create_claim("Tas", disaster_event=self.w.event.name)
