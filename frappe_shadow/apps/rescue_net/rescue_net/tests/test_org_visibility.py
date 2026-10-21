"""One-click org visibility toggle (api_privacy.set_org_visibility /
set_posko_public_choice) and the 'closed org keeps a public posko' rule.

A closed org shows only a summary to outsiders on the Control Centre, yet its
own members keep full detail of their poskos and any posko it deliberately set
to 'public' (e.g. a shared TNI ship) stays fully public — visible AND open to
outside coordination."""

import frappe

from rescue_net.access_policy import public_posko_allowed
from rescue_net.visibility import effective_posko_share
from rescue_net.tests.factories import (
    RNTestCase, api_call, as_guest, as_user, make_actor, make_event, make_org, make_posko,
)


class TestOrgVisibilityToggle(RNTestCase):
    def _owned_org(self, **kw):
        org = make_org(
            privacy_mode="open",
            control_centre_share="full_authorized",
            allow_posko_public_choice=1,
            **kw,
        )
        owner = make_actor(org=org, org_role="owner")
        return org, owner

    def test_toggle_flips_both_fields_and_keeps_posko_choice(self):
        org, owner = self._owned_org()
        with as_user(owner.user):
            r = api_call("rescue_net.api_privacy.set_org_visibility",
                         organization=org.name, open_to_public=0)
        self.assertEqual(r["privacy_mode"], "closed")
        self.assertEqual(r["control_centre_share"], "aggregate")
        self.assertEqual(int(r["allow_posko_public_choice"]), 1)  # preserved across close

        with as_user(owner.user):
            r2 = api_call("rescue_net.api_privacy.set_org_visibility",
                          organization=org.name, open_to_public=1)
        self.assertEqual(r2["privacy_mode"], "open")
        self.assertEqual(r2["control_centre_share"], "full_authorized")

    def test_closed_org_keeps_a_public_posko_visible_and_coordinable(self):
        org, owner = self._owned_org()
        posko = make_posko(make_event(), org, public_detail="public")

        with as_user(owner.user):
            api_call("rescue_net.api_privacy.set_org_visibility",
                     organization=org.name, open_to_public=0)

        self.assertEqual(frappe.db.get_value("RN Organization", org.name, "privacy_mode"), "closed")
        self.assertEqual(frappe.db.get_value("RN Posko", posko.name, "public_detail"), "public")
        # Visible in the Control Centre to an anonymous viewer…
        with as_guest():
            self.assertEqual(effective_posko_share(posko.name)["mode"], "full")
        # …and still open to outside coordination (the owner chose full public).
        self.assertTrue(public_posko_allowed(posko.name))

    def test_set_posko_public_choice_off_cascades_public_posko_to_inherit(self):
        org, owner = self._owned_org()
        posko = make_posko(make_event(), org, public_detail="public")

        with as_user(owner.user):
            api_call("rescue_net.api_privacy.set_posko_public_choice",
                     organization=org.name, allow=0)

        self.assertEqual(frappe.db.get_value("RN Posko", posko.name, "public_detail"), "inherit")
        self.assertFalse(public_posko_allowed(posko.name))

    def test_guest_and_non_owner_cannot_toggle(self):
        org, _owner = self._owned_org()
        outsider = make_actor()  # logged in, no affiliation to this org

        with as_guest():
            with self.assertRaises(frappe.PermissionError):
                api_call("rescue_net.api_privacy.set_org_visibility",
                         organization=org.name, open_to_public=0)

        with as_user(outsider.user):
            with self.assertRaises(frappe.PermissionError):
                api_call("rescue_net.api_privacy.set_org_visibility",
                         organization=org.name, open_to_public=0)
            with self.assertRaises(frappe.PermissionError):
                api_call("rescue_net.api_privacy.set_posko_public_choice",
                         organization=org.name, allow=1)
