import hashlib
import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime

def _actor():
    user = frappe.session.user
    if user in ("Guest", "Administrator"):
        return None

    return frappe.db.get_value(
        "RN User Account",
        {"frappe_user":user, "status":"active"},
        "name",
    )


def _classify(doc, raw):
    from rescue_net.intelligence.normalization_registry import classify_text

    suggestion = classify_text(raw)

    if not doc.canonical_category:
        doc.canonical_category = suggestion["canonical_category"]

    if not doc.canonical_group:
        doc.canonical_group = suggestion["canonical_group"]

    if not doc.canonical_item:
        doc.canonical_item = suggestion["canonical_item"]

    if not doc.normalization_source:
        doc.normalization_source = "rule"

    if not doc.normalization_confidence:
        doc.normalization_confidence = suggestion[
            "normalization_confidence"
        ]

    if not doc.normalization_status:
        doc.normalization_status = "suggested"

    if (
        (not doc.quantity_mode or doc.quantity_mode == "unknown")
        and suggestion["quantity_mode"] != "unknown"
    ):
        doc.quantity_mode = suggestion["quantity_mode"]

    if not doc.estimate_text and suggestion["estimate_text"]:
        doc.estimate_text = suggestion["estimate_text"]


# L-10 / GAP-P2: every save follows this graph (was only in update_flow_status)
TRANSITIONS = {
    "planned": {"assigned_pickup", "cancelled"},
    # a transporter posko claimed the pickup of an aid offer
    "pickup_claimed": {"assigned_pickup", "dispatched", "in_transit", "cancelled"},
    "assigned_pickup": {"dispatched", "in_transit", "cancelled"},
    "dispatched": {"in_transit", "arrived_at_posko", "cancelled"},
    "in_transit": {"arrived_at_posko", "cancelled"},
    "arrived_at_posko": {"partially_received", "received", "cancelled"},
    "partially_received": {"partially_received", "received"},
    "received": set(),
    "cancelled": set(),
}

VALID_STATES = set(TRANSITIONS)

# L-11: what the armada and the aid offer show while a flow is at a status
TRANSPORT_STATUS_FOR = {
    "assigned_pickup": "assigned",
    "dispatched": "assigned",
    "in_transit": "in_transit",
    "arrived_at_posko": "arrived",
    "partially_received": "arrived",
    "received": "completed",
    "cancelled": "available",
}
OFFER_STATUS_FOR = {
    "pickup_claimed": "pickup_claimed",
    "assigned_pickup": "reserved",
    "dispatched": "in_transit",
    "in_transit": "in_transit",
    "arrived_at_posko": "in_transit",
    "partially_received": "in_transit",
    "received": "delivered",
    "cancelled": "available",
}


class RNDistributionFlow(Document):
    def autoname(self):
        if self.legacy_id:
            self.name = self.legacy_id
            return

        seed = f"{self.destination_posko or ''}:{self.item_name or ''}:{frappe.generate_hash(length=12)}"
        self.name = "rn-flow-" + hashlib.sha256(
            seed.encode()
        ).hexdigest()[:20]

    def before_insert(self):
        if self.legacy_id:
            return

        self.legacy_source = None
        self.migration_status = None

        actor = _actor()

        if not self.created_by_user:
            self.created_by_user = actor

        if not self.last_updated_by_user:
            self.last_updated_by_user = actor

        if not self.raw_item_text:
            self.raw_item_text = self.item_name or self.title or ""

        _classify(self, self.raw_item_text)

        if self.quantity_mode == "unknown" and self.quantity:
            self.quantity_mode = "exact"

        if not self.flow_status:
            self.flow_status = "planned"

        if not self.observed_at:
            self.observed_at = now_datetime()

        if not self.source_updated_at:
            self.source_updated_at = self.observed_at

    def validate(self):
        from rescue_net.services.guards import assert_quantities
        assert_quantities(self, allow_zero=False, label="Jumlah distribusi")
        self.assert_received_within_sent()
        if (
            not self.legacy_id
            and self.flow_status
            and self.flow_status not in VALID_STATES
        ):
            frappe.throw("Status distribusi tidak valid")

        from rescue_net.services.guards import assert_transition
        assert_transition(self, "flow_status", TRANSITIONS, "Status distribusi",
                          initial={"planned", "pickup_claimed"})

    def on_update(self):
        """The armada and the aid offer follow the flow on every status change."""
        from rescue_net.services.guards import bypass

        before = self.get_doc_before_save()
        if bypass(self) or not before or before.flow_status == self.flow_status:
            return
        now = now_datetime()
        if self.transport_space:
            from rescue_net.services.transport import armada_status_after_flow
            status = TRANSPORT_STATUS_FOR.get(self.flow_status)
            status = status and armada_status_after_flow(self.transport_space, self.name, status)
            if status:
                frappe.db.set_value("RN Transport Space", self.transport_space,
                                    {"transport_status": status, "source_updated_at": now},
                                    update_modified=False)
        if self.aid_offer and self.flow_status in OFFER_STATUS_FOR:
            frappe.db.set_value("RN Aid Offer", self.aid_offer,
                                {"offer_status": OFFER_STATUS_FOR[self.flow_status], "source_updated_at": now},
                                update_modified=False)

    def assert_received_within_sent(self):
        """L-2: what is received is never negative and never more than what
        was sent, when both are counted in the same unit (a receipt in
        another unit — karung vs kg — cannot be compared here)."""
        from rescue_net.services.guards import bypass, changed

        rq = self.received_quantity
        if bypass(self) or rq in (None, "") or not (self.is_new() or changed(self, "received_quantity")):
            return
        rq = float(rq)
        if rq < 0:
            frappe.throw("Jumlah diterima tidak boleh negatif.")
        sent = self.quantity
        same_unit = not self.received_unit or not self.unit or \
            str(self.received_unit).strip().lower() == str(self.unit).strip().lower()
        if sent not in (None, "") and float(sent) > 0 and same_unit and rq > float(sent):
            frappe.throw(f"Jumlah diterima ({rq:g}) melebihi jumlah yang dikirim ({float(sent):g} {self.unit or ''}).")
