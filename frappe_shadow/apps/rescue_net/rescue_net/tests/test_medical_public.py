"""Unit 4: the guest family-finding roster (api_medical.public_patients).

A PUBLIC medical posko exposes patient identity + outcome to guests so that
relatives can look for a victim — name, code, triage, case status, latest
evacuation. It must NEVER expose the complaint, treatment notes or supply use
(those stay behind the actor-gated dashboard). A non-public posko exposes
nothing."""

import frappe

from rescue_net import api_medical
from rescue_net.tests.factories import (
    RNTestCase,
    _insert,
    as_guest,
    contains_value,
    make_event,
    make_medical_case,
    make_posko,
)


class TestPublicPatients(RNTestCase):
    def setUp(self):
        super().setUp()
        self.event = make_event()

    def _public_med_posko(self):
        org = _insert(
            "RN Organization",
            title="Org Publik Medis",
            privacy_mode="open",
            allow_posko_public_choice=1,
        )
        return make_posko(
            self.event, org, posko_type="medical", public_detail="public"
        )

    def _private_med_posko(self):
        org = _insert(
            "RN Organization",
            title="Org Tertutup Medis",
            privacy_mode="closed",
            allow_posko_public_choice=0,
        )
        return make_posko(
            self.event, org, posko_type="medical", public_detail="inherit"
        )

    def test_guest_sees_name_and_outcome_but_not_complaint(self):
        posko = self._public_med_posko()
        make_medical_case(
            posko,
            patient_code="KRK-MC-01",
            patient_name="Siti Aminah",
            complaint="RAHASIA-KELUHAN",
            treatment_notes="RAHASIA-CATATAN",
            triage_status="red",
            case_status="referred",
        )
        with as_guest():
            res = api_medical.public_patients(posko=posko.name)

        self.assertTrue(res["allowed"])
        self.assertEqual(len(res["patients"]), 1)
        p = res["patients"][0]
        self.assertEqual(p["patient_name"], "Siti Aminah")
        self.assertEqual(p["patient_code"], "KRK-MC-01")
        self.assertEqual(p["triage_status"], "red")
        self.assertEqual(p["case_status"], "referred")
        # Sensitive medical detail must not leak anywhere in the payload.
        self.assertFalse(contains_value(res, "RAHASIA-KELUHAN"))
        self.assertFalse(contains_value(res, "RAHASIA-CATATAN"))

    def test_non_public_posko_exposes_nothing_to_guest(self):
        posko = self._private_med_posko()
        make_medical_case(
            posko, patient_code="KRK-MC-02", patient_name="Budi Santoso"
        )
        with as_guest():
            res = api_medical.public_patients(posko=posko.name)

        self.assertFalse(res["allowed"])
        self.assertEqual(res["patients"], [])
        self.assertFalse(contains_value(res, "Budi Santoso"))

    def test_guest_is_allowed_to_call_it(self):
        # Unlike dashboard(), this endpoint is allow_guest — no PermissionError.
        posko = self._public_med_posko()
        with as_guest():
            res = api_medical.public_patients(posko=posko.name)
        self.assertIn("patients", res)
