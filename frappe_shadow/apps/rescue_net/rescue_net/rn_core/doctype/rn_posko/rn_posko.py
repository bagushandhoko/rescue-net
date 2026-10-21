import frappe
from frappe.model.document import Document


class RNPosko(Document):
    def autoname(self):
        legacy_id = (self.legacy_id or "").strip()
        if legacy_id:
            self.name = legacy_id
            return

        self.name = "rn-posko-" + frappe.generate_hash(length=20)

    def before_insert(self):
        if self.legacy_id:
            return

        self.legacy_source = None
        self.migration_status = None
        if not self.verification_status:
            self.verification_status = "self_reported"
        if not self.operational_status:
            self.operational_status = "active"
        if not self.identity_verification_status:
            self.identity_verification_status = "self_reported"


    def _validate_links(self):
        # Link wilayah divalidasi Frappe SEBELUM before_insert; normalkan dulu agar id tak dikenal ditandai,
        # bukan menolak simpan (laporan warga/posko selalu diterima — ADR-0005 A.5).
        from rescue_net.services.admin_areas import normalize_doc_area

        normalize_doc_area(self)
        super()._validate_links()

    def _sync_served_events(self):
        """served_events = every disaster this posko handles; the main
        disaster_event is always one of them (owner 2026-10-19)."""
        from frappe.utils import now_datetime

        if not self.meta.has_field("served_events"):    # before migrate
            return
        seen, rows = set(), []
        for row in self.get("served_events") or []:
            if row.disaster_event and row.disaster_event not in seen:
                seen.add(row.disaster_event)
                rows.append(row)
        self.set("served_events", rows)
        if not self.disaster_event and rows:
            self.disaster_event = rows[0].disaster_event
        if self.disaster_event and self.disaster_event not in seen:
            self.append("served_events", {"disaster_event": self.disaster_event})
        for row in self.served_events:
            if not row.added_on:
                row.added_on = now_datetime()

    # RN_PRIVACY_GUARD_V1
    def validate(self):
        self._sync_served_events()
        if not self.public_detail:
            self.public_detail = "inherit"

        if not self.organization:
            return

        org = frappe.db.get_value(
            "RN Organization",
            self.organization,
            [
                "privacy_mode",
                "allow_posko_public_choice",
            ],
            as_dict=True,
        )

        if (
            self.public_detail == "public"
            and org
            and (
                org.privacy_mode != "open"
                or not org.allow_posko_public_choice
            )
        ):
            frappe.throw(
                "Posko tidak dapat dibuka ke publik karena "
                "kebijakan Kelompok tidak mengizinkannya"
            )
