"""Public (allow_guest) endpoints must not leak sensitive data.

1. Inventory: the set of guest-callable rescue_net methods is pinned. Adding
   a new public endpoint fails this test on purpose — review what it returns
   to Guest, then add it to GUEST_ENDPOINTS.
2. Sweep: seed one world full of sentinel secrets (phones, emails, patient
   data, missing-person names, household notes, handover PINs, AI key) and
   call every read-only guest endpoint as Guest with that world's ids. No
   sentinel may appear in any response, except the confirmed, owner-reported
   leaks in KNOWN_LEAKS (which must still reproduce, so the list stays honest).
"""

import importlib
import inspect
import json
import pkgutil

import frappe
import rescue_net
from frappe.utils import now_datetime

from rescue_net import api_ai
from rescue_net.tests.factories import (
    RNTestCase,
    _insert,
    as_guest,
    as_user,
    make_actor,
    make_medical_case,
    make_posko,
    make_transport_space,
    make_world,
)

GUEST_ENDPOINTS = {
    "api_admin_areas.get_children", "api_admin_areas.get_provinces",
    "api_ai.ai_providers", "api_ai.public_active_disasters", "api_ai.public_context", "api_ai.public_map_context",
    "api_auth.register", "api_auth.session_info", "api_auth.social_login_url",
    "api_comms.comms_board",
    "api_community_cluster.get_posko_settings",
    "api_control_centre.active_disasters_board", "api_control_centre.distribusi_board",
    "api_control_centre.event_poskos", "api_control_centre.evidence_board",
    "api_control_centre.flow_trace", "api_control_centre.fulfill_need",
    "api_control_centre.kpi_drilldown", "api_control_centre.logistik_board",
    "api_control_centre.logistik_dispatch_options", "api_control_centre.logistik_incoming",
    "api_control_centre.logistik_open_needs", "api_control_centre.logistik_stock_cards",
    "api_control_centre.logistik_stock_sources", "api_control_centre.my_org_coordination",
    "api_control_centre.org_detail", "api_control_centre.org_posko_board",
    "api_control_centre.posko_detail", "api_control_centre.posko_distribusi_board",
    "api_control_centre.posko_edit_scope", "api_control_centre.posko_functions",
    "api_control_centre.posko_registry_board", "api_control_centre.posko_verification_checklist",
    "api_control_centre.public_dashboard",
    "api_displacement.displacement_board",
    "api_donor_program.program_board", "api_donor_program.program_detail",
    "api_donor_program.program_donations", "api_donor_program.public_context",
    "api_forum.feedback_threads", "api_forum.post_feedback", "api_forum.upvote_feedback",
    "api_frontend_bridge.community_reports", "api_frontend_bridge.consolidated_needs",
    "api_frontend_bridge.consolidation_auxiliary", "api_frontend_bridge.consolidation_edit_scope",
    "api_frontend_bridge.consolidation_raw_reports", "api_frontend_bridge.consolidation_summary",
    "api_frontend_bridge.duplicate_candidates",
    "api_gis.national_situation",
    "api_intelligence.consolidated_need_snapshot_detail", "api_intelligence.consolidated_need_snapshots",
    "api_intelligence.control_centre_summary",
    "api_kitchen.dashboard", "api_kitchen.kitchen_board",
    "api_logistics.book_transport_space_public", "api_logistics.dashboard",
    "api_logistics.edit_guest_aid_offer", "api_logistics.get_guest_aid_offer",
    "api_logistics.get_public_transport_booking", "api_logistics.item_group_members",
    "api_logistics.item_groups", "api_logistics.public_dashboard",
    "api_logistics.submit_guest_aid_offer_multi", "api_logistics.update_public_transport_booking",
    "api_privacy.public_posko",
    "api_resource_tools.dashboard", "api_resource_tools.resource_profile_board",
    "api_resource_tools.tools_board", "api_resource_tools.work_objects_board",
    "api_search_found.dashboard",
    "api_shelter.dashboard", "api_shelter.shelter_board",
    "api_tender.submit_bid", "api_tender.tender_board", "api_tender.tender_detail",
    "api_verification.approval_item_detail", "api_verification.approval_queue",
    "api_verifier.posko_verification_public", "api_verifier.verifier_directory",
    "api_volunteer.dashboard", "api_volunteer.register_volunteer", "api_volunteer.volunteer_board",
}

# Guest endpoints that write, or need a secret the caller must already hold
# (edit codes); they are covered by their own tests, not the read sweep.
NOT_SWEPT = {
    "api_auth.register", "api_auth.social_login_url", "api_forum.post_feedback",
    "api_forum.upvote_feedback", "api_tender.submit_bid", "api_control_centre.fulfill_need",
    "api_logistics.submit_guest_aid_offer_multi", "api_logistics.edit_guest_aid_offer",
    "api_logistics.get_guest_aid_offer", "api_logistics.book_transport_space_public",
    "api_logistics.get_public_transport_booking", "api_logistics.update_public_transport_booking",
    "api_volunteer.register_volunteer",
}

SECRETS = {
    "officer_phone": "+62811-1111-0001",
    "officer_email": "pic.sentinel@test.rescue-net.local",
    "account_phone": "+62811-1111-0002",
    "donor_phone": "+62811-1111-0003",
    "booking_phone": "+62811-1111-0004",
    "volunteer_phone": "+62811-1111-0005",
    "booking_pin": "PIN-SENTINEL-93",
    "patient_code": "PX-SENTINEL-77",
    "complaint": "KELUHAN-SENTINEL",
    "treatment": "TERAPI-SENTINEL",
    "person_name": "Nama Sentinel Hilang",
    "reporter_contact": "+62811-1111-0006",
    "household_note": "CATATAN-KK-SENTINEL",
    "ai_key": "fake-byok-SENTINEL-0123456789abcdef",
}

# Confirmed leaks reported to the owner but not fixed yet:
# {(endpoint, secret key): "BUG-n"}. Empty since BUG-1..6 were fixed 2026-09-26.
KNOWN_LEAKS = {}


def guest_methods():
    for m in pkgutil.iter_modules(rescue_net.__path__):
        if m.name.startswith("api_"):
            importlib.import_module("rescue_net." + m.name)
    return {
        _public_path(fn): fn
        for fn in frappe.guest_methods
        if getattr(fn, "__module__", "").startswith("rescue_net.")
    }


def _public_path(fn):
    """The dotted path the frontend calls: code split into a package
    (rescue_net/<package>/*) is still served as api_<package>.*."""
    module = fn.__module__.replace("rescue_net.", "", 1)
    package = module.split(".")[0]
    if package in SPLIT_PACKAGES:
        module = "api_" + package
    return module + "." + fn.__name__


# API files split into a package per sub-domain (phase 2); the old module
# re-exports everything, so the public path stays api_<package>.<name>
SPLIT_PACKAGES = {"control_centre", "logistics", "ai", "resource_tools", "donor_program", "frontend_bridge"}


class TestGuestInventory(RNTestCase):
    def test_guest_endpoint_list_is_reviewed(self):
        current = set(guest_methods())
        self.assertEqual(sorted(current - GUEST_ENDPOINTS), [],
                         "new guest endpoint(s): review what they return to Guest, then list them")
        self.assertEqual(sorted(GUEST_ENDPOINTS - current), [],
                         "guest endpoint(s) removed: drop them from GUEST_ENDPOINTS")


class TestGuestSweep(RNTestCase):
    def setUp(self):
        super().setUp()
        s = SECRETS
        self.w = w = make_world()
        officer = {"officer_in_charge_phone": s["officer_phone"], "officer_in_charge_email": s["officer_email"]}
        for posko in (w.posko_a, w.posko_b):
            frappe.db.set_value("RN Posko", posko.name, officer)
        self.medical = make_posko(w.event, w.org_a, posko_type="medical", **officer)
        self.shelter = make_posko(w.event, w.org_a, posko_type="shelter", **officer)
        self.transport = make_posko(w.event, w.org_a, posko_type="transport", public_participation=1, **officer)
        # an org that opens posko detail to the public, so public_posko /
        # public_dashboard are exercised too (no sentinel on the posko itself:
        # a public posko may legitimately publish its PIC)
        open_org = _insert("RN Organization", title="Org Terbuka", privacy_mode="open",
                           allow_posko_public_choice=1)
        self.public = make_posko(w.event, open_org, public_detail="public", public_participation=1)
        _insert("RN Shelter Household", posko=self.public.name, household_code="KK-SENTINEL-2",
                members_count=2, household_status="checked_in", notes=s["household_note"],
                check_in_at=now_datetime())
        self.poskos = [w.posko_a, self.medical, self.shelter, self.transport, self.public]

        make_medical_case(self.medical, patient_code=s["patient_code"], complaint=s["complaint"],
                          treatment_notes=s["treatment"], disaster_event=w.event.name)
        _insert("RN Missing Person Report", disaster_event=w.event.name, posko=w.posko_a.name,
                person_code="MP-SENTINEL", person_name=s["person_name"], report_status="missing",
                reporter_name="Pelapor Sentinel", reporter_contact=s["reporter_contact"],
                observed_at=now_datetime())
        _insert("RN Shelter Household", posko=self.shelter.name, household_code="KK-SENTINEL",
                members_count=3, household_status="checked_in", notes=s["household_note"],
                check_in_at=now_datetime())
        self.offer = _insert("RN Aid Offer", title="Donasi sentinel", disaster_event=w.event.name,
                             target_posko=w.posko_a.name, donor_name="Donatur Sentinel",
                             donor_contact=s["donor_phone"], item_name="Beras", quantity=5, unit="karung",
                             offer_status="need_pickup", handling_mode="need_pickup")
        space = make_transport_space(self.transport)
        _insert("RN Transport Booking", transport_space=space.name, status="requested",
                booker_name="Pemesan Sentinel", contact_person="Pak Sentinel",
                contact_phone=s["booking_phone"], verification_pin=s["booking_pin"],
                cargo_desc="Beras", qty_weight_kg=20)
        _insert("RN Volunteer Profile", volunteer_name="Relawan Sentinel", main_skill="logistik",
                contact=s["volunteer_phone"], disaster_event=w.event.name, assigned_posko=w.posko_a.name)
        self.flow = _insert("RN Distribution Flow", title="Beras", destination_posko=w.posko_a.name,
                            disaster_event=w.event.name, item_name="Beras", quantity=5, unit="karung",
                            flow_status="planned")
        self.actor = make_actor(posko=w.posko_a, phone=s["account_phone"])
        with as_user(self.actor.user):
            api_ai.save_user_key(self.actor.user, s["ai_key"])

    def arg_sets(self, fn):
        """Plausible guest calls for `fn`: one per posko when it takes a posko."""
        sig = inspect.signature(inspect.unwrap(fn))
        fixed = {
            "disaster_event": self.w.event.name, "disaster_event_id": self.w.event.name,
            "organization": self.w.org_a.name, "flow": self.flow.name,
            "user_account": self.actor.account, "source_posko": self.w.posko_a.name,
            "item": "Beras",
        }
        base, needs_posko = {}, False
        for name, p in sig.parameters.items():
            if name in fixed:
                base[name] = fixed[name]
            elif name == "posko":
                needs_posko = True
            elif name == "dimension":
                pass
            elif p.default is inspect.Parameter.empty:
                return []                                   # required arg we cannot supply
        if "dimension" in sig.parameters:
            from rescue_net.api_control_centre import _DRILL_BUILDERS
            return [dict(base, dimension=d) for d in _DRILL_BUILDERS]
        if needs_posko:
            return [dict(base, posko=p.name) for p in self.poskos]
        return [base]

    def test_no_sentinel_leaks_to_guest(self):
        found, exercised, errors = set(), set(), {}
        for path, fn in sorted(guest_methods().items()):
            if path in NOT_SWEPT:
                continue
            for kwargs in self.arg_sets(fn):
                frappe.db.savepoint("guest_sweep")
                with as_guest():
                    try:
                        frappe.local.form_dict = frappe._dict(kwargs)
                        result = frappe.call(fn, **kwargs)
                    except Exception as e:                  # refused / not found is fine
                        frappe.db.rollback(save_point="guest_sweep")
                        errors[path] = f"{type(e).__name__}: {str(e)[:80]}"
                        frappe.local.message_log = []
                        continue
                exercised.add(path)
                blob = json.dumps(result, default=str)
                for key, secret in SECRETS.items():
                    if secret in blob:
                        found.add((path, key))

        print("\nSWEEP exercised=%d errors=%d" % (len(exercised), len(errors)))
        for p, e in sorted(errors.items()):
            if p not in exercised:
                print("  not exercised:", p, e)
        unknown = sorted(f"{p} → {k}" for p, k in found - set(KNOWN_LEAKS))
        self.assertEqual(unknown, [], "NEW leak(s) to Guest")
        stale = sorted(f"{p} → {k} ({b})" for (p, k), b in KNOWN_LEAKS.items() if (p, k) not in found)
        self.assertEqual(stale, [], "known leak no longer reproduces — fixed? remove it from KNOWN_LEAKS")
        # the sweep must actually reach the big boards, or it proves nothing
        for must in ("api_control_centre.posko_detail", "api_control_centre.distribusi_board",
                     "api_ai.public_context", "api_search_found.dashboard", "api_shelter.shelter_board",
                     "api_volunteer.volunteer_board", "api_control_centre.kpi_drilldown"):
            self.assertIn(must, exercised, errors.get(must))
