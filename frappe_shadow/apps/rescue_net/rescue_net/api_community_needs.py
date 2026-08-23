import frappe
from frappe.utils import now_datetime


def _actor():
    user = frappe.session.user

    if user in ("Guest", "Administrator"):
        frappe.throw("Login sebagai operator Posko diperlukan")

    actor = frappe.db.get_value(
        "RN User Account",
        {"frappe_user": user, "status": "active"},
        ["name","role","requested_role","role_request_status","posko"],
        as_dict=True,
    )

    if not actor:
        frappe.throw("Akun Rescue-Net aktif tidak ditemukan")

    if actor.role != "posko_operator":
        frappe.throw(
            "Hanya operator Posko dengan role efektif "
            "yang dapat mengambil penanganan"
        )

    return actor


def _allowed_poskos(actor):
    result = set()

    if actor.posko:
        result.add(actor.posko)

    rows = frappe.get_all(
        "RN Posko Assignment",
        filters={
            "user_account": actor.name,
            "status": "approved",
        },
        pluck="posko",
        limit_page_length=100,
    )

    result.update(rows)
    return result


def _resolve_posko(actor, posko=None):
    allowed = _allowed_poskos(actor)

    if not allowed:
        frappe.throw("Operator belum mempunyai Posko yang disetujui")

    if posko:
        if posko not in allowed:
            frappe.throw("Operator tidak ditugaskan pada Posko tersebut")
        return posko

    if len(allowed) == 1:
        return next(iter(allowed))

    frappe.throw("Pilih Posko yang akan menangani kebutuhan")


def _lock_need(name):
    found = frappe.db.sql(
        """
        SELECT name
        FROM `tabRN Community Need`
        WHERE name=%s
        FOR UPDATE
        """,
        (name,),
    )

    if not found:
        frappe.throw("Kebutuhan tidak ditemukan")

    return frappe.get_doc("RN Community Need", name)


@frappe.whitelist()
def take_over(community_need, posko=None):
    actor = _actor()
    selected_posko = _resolve_posko(actor, posko)
    need = _lock_need(community_need)

    if need.status in ("fulfilled","closed","cancelled"):
        frappe.throw("Kebutuhan sudah selesai/ditutup")

    if (
        need.handling_mode == "posko"
        and need.handling_posko == selected_posko
        and need.takeover_status == "accepted"
    ):
        return {
            "community_need": need.name,
            "result": "already_handled_by_this_posko"
        }

    if (
        need.handling_mode == "posko"
        and need.handling_posko
        and need.handling_posko != selected_posko
    ):
        frappe.throw("Kebutuhan sudah ditangani Posko lain")

    # source_report dan community_owner TIDAK diubah.
    need.handling_mode = "posko"
    need.handling_posko = selected_posko
    need.takeover_status = "accepted"
    need.takeover_at = now_datetime()
    need.takeover_by = actor.name

    if need.status == "open":
        need.status = "in_progress"

    need.save(ignore_permissions=True)

    return {
        "community_need": need.name,
        "result": "taken_over",
        "handling_posko": selected_posko,
        "community_owner": need.community_owner,
        "source_report": need.source_report,
        "verification_status": need.verification_status,
        "status": need.status,
    }


@frappe.whitelist()
def release_to_community(community_need, posko=None):
    actor = _actor()
    selected_posko = _resolve_posko(actor, posko)
    need = _lock_need(community_need)

    if (
        need.handling_mode != "posko"
        or need.handling_posko != selected_posko
    ):
        frappe.throw("Kebutuhan tidak sedang ditangani Posko ini")

    need.handling_mode = "community"
    need.handling_posko = None
    need.takeover_status = "released"

    if need.status == "in_progress":
        need.status = "open"

    need.save(ignore_permissions=True)

    return {
        "community_need": need.name,
        "result": "released_to_community",
        "community_owner": need.community_owner,
        "source_report": need.source_report,
        "status": need.status,
    }
