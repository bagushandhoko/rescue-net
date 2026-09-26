import math

import frappe
from frappe.rate_limiter import rate_limit
from frappe.utils import cint, flt


# ============================================================
# Perkiraan Kebutuhan Alat/Logistik dari Laporan Masyarakat — owner ask:
# "jalan rusak 200 m butuh buldoser/excavator", "100 kehilangan rumah
# butuh makanan/pakaian/shelter", optional fields, feeds a heuristic
# estimate so posko can adjust prep. Deliberately the SAME kind of
# simple, honestly-labeled divisor heuristic as
# services/tool_needs.py (Kebutuhan Alat Kerja) (Alat
# Kerja's "Prediksi Kebutuhan Alat") — a real math estimate, not a
# fabricated "AI" black box, and not a real LLM call for something
# this deterministic.
# ============================================================

# report_type -> [(item, label, divisor, basis)]; qty = ceil(scale/divisor).
_ACCESS_DAMAGE_TYPES = {"blocked_access", "new_hazard"}
_ACCESS_EQUIPMENT_RULES = [
    ("excavator", "Ekskavator", 150, "1 ekskavator per ~150 m jalan/akses rusak atau tertutup"),
    ("buldoser", "Buldoser", 200, "1 buldoser per ~200 m jalan/akses rusak atau tertutup"),
]

# report_type -> per-affected-person logistics; "per_day": consumable
# (rate, not a total — duration is unknown), else one-time durable item.
_DISPLACEMENT_TYPES = {"shelter_need", "affected_need_help", "location_needs_help"}
_DISPLACEMENT_LOGISTICS_RULES = [
    ("beras", "Beras", 0.4, "kg", True, "~0.4 kg beras per orang per hari (standar bantuan pangan darurat)"),
    ("air_bersih", "Air Bersih", 3.0, "liter", True, "~3 liter air bersih per orang per hari"),
    ("selimut", "Selimut", 1.0, "pcs", False, "1 selimut per orang terdampak"),
    ("pakaian_layak", "Pakaian Layak Pakai", 1.0, "set", False, "1 set pakaian per orang terdampak"),
    ("tenda_keluarga", "Tenda Keluarga", 0.2, "unit", False, "1 tenda keluarga per ~5 orang terdampak"),
]


# Drought / water crisis: Sphere minimum 15 L per person per day for all
# household use; delivered by 5,000-litre water tanker trips.
_WATER_SHORTAGE_TYPES = {"water_shortage"}
_WATER_LITRES_PER_PERSON_DAY = 15.0
_TANKER_LITRES = 5000.0


def predict_report_needs(report_type, damage_scale_value=None, affected_people_count=0):
    """Heuristic equipment/logistics estimate from a citizen report — same
    honest-heuristic spirit as services/tool_needs.estimate.
    Returns [] when there's nothing to predict from (no scale/people given,
    or a report_type this doesn't apply to) — never fabricates a number."""
    report_type = (report_type or "").strip()
    scale = flt(damage_scale_value)
    people = cint(affected_people_count)

    out = []

    if report_type in _ACCESS_DAMAGE_TYPES and scale > 0:
        for key, label, divisor, basis in _ACCESS_EQUIPMENT_RULES:
            qty = max(1, math.ceil(scale / divisor))
            out.append({
                "category": key, "label": label, "predicted_qty": qty,
                "unit": "unit", "basis": basis,
            })

    if report_type in _DISPLACEMENT_TYPES and people > 0:
        for key, label, rate, unit, per_day, basis in _DISPLACEMENT_LOGISTICS_RULES:
            qty = math.ceil(rate * people)
            if qty <= 0:
                continue
            out.append({
                "category": key, "label": label, "predicted_qty": qty,
                "unit": unit, "basis": basis, "per_day": bool(per_day),
            })

    if report_type in _WATER_SHORTAGE_TYPES and people > 0:
        litres = math.ceil(_WATER_LITRES_PER_PERSON_DAY * people)
        out.append({
            "category": "air_bersih", "label": "Air Bersih", "predicted_qty": litres,
            "unit": "liter", "per_day": True,
            "basis": "15 liter air per orang per hari (standar minimum Sphere)",
        })
        out.append({
            "category": "truk_tangki_air", "label": "Rit Truk Tangki Air 5.000 L",
            "predicted_qty": max(1, math.ceil(litres / _TANKER_LITRES)), "unit": "rit", "per_day": True,
            "basis": "1 rit truk tangki = 5.000 liter",
        })
        out.append({
            "category": "jerigen", "label": "Jerigen 20 L", "predicted_qty": math.ceil(people / 5 * 2),
            "unit": "pcs", "per_day": False,
            "basis": "2 jerigen 20 L per keluarga (~5 orang) untuk menampung air",
        })

    return out


def _area(code):
    if not code:
        return None
    return frappe.db.get_value(
        "RN Admin Area",
        {"code": code, "enabled": 1},
        ["code", "area_name", "level", "parent_code"],
        as_dict=True,
    )


@frappe.whitelist()
def submit_community_report(
    title=None,
    description=None,
    report_type=None,
    priority=None,
    affected_people_count=0,
    urgent_needs=None,
    location_text=None,
    latitude=None,
    longitude=None,
    province_code=None,
    city_code=None,
    district_code=None,
    village_code=None,
    consent_to_contact=0,
    location_input_method=None,
    create_need=0,
    damage_scale_value=None,
    damage_scale_unit=None,
    disaster_event=None,
    intake_mode="form",
    intake_parser=None,
):
    if frappe.session.user == "Guest":
        frappe.throw("Login diperlukan untuk mengirim laporan", frappe.PermissionError)

    intake_mode = "narrative" if intake_mode == "narrative" else "form"
    if not (description or "").strip():
        frappe.throw("Uraian / deskripsi laporan wajib diisi")
    parser = None
    if intake_mode == "narrative":
        from rescue_net.services.llm import PROVIDERS

        # label from the reviewed draft (draft_community_report); only known values
        if intake_parser == "rules" or str(intake_parser or "").split(":", 1)[-1] in PROVIDERS:
            parser = intake_parser
        if not (title and report_type):
            # sent without a reviewed draft: fill whatever the form left empty
            from rescue_net.services.report_intake import extract

            fields, parser = extract(description)
            title = title or fields["title"]
            report_type = report_type or fields["report_type"]
            priority = priority or fields["priority"]
            affected_people_count = cint(affected_people_count) or fields["affected_people_count"]
            urgent_needs = urgent_needs or fields["urgent_needs"]
            location_text = location_text or fields["location_text"]
            if damage_scale_value in (None, "") and fields["damage_scale_value"] is not None:
                damage_scale_value, damage_scale_unit = fields["damage_scale_value"], fields["damage_scale_unit"]
    if not (title or "").strip():
        frappe.throw("Judul laporan wajib diisi")

    province = _area(province_code)
    city = _area(city_code)
    district = _area(district_code)
    village = _area(village_code)

    deepest = village or district or city or province

    lat = None if latitude in (None, "") else flt(latitude)
    lng = None if longitude in (None, "") else flt(longitude)
    has_coordinates = lat is not None and lng is not None

    from rescue_net.reference_resolver import resolve_disaster_event

    doc = frappe.new_doc("RN Community Report")
    doc.title = title
    doc.description = description
    doc.disaster_event = resolve_disaster_event(disaster_event) if disaster_event else None
    doc.report_type = report_type
    doc.priority = priority
    doc.affected_people_count = cint(affected_people_count or 0)
    doc.urgent_needs = urgent_needs
    doc.location_text = location_text
    doc.damage_scale_value = flt(damage_scale_value) if damage_scale_value not in (None, "") else None
    doc.damage_scale_unit = damage_scale_unit or None

    doc.has_coordinates = 1 if has_coordinates else 0
    doc.latitude = lat
    doc.longitude = lng
    doc.location_input_method = location_input_method
    doc.location_source = "frappe-web"
    doc.location_status = "provided" if has_coordinates else "not_provided"

    if deepest:
        doc.admin_area_id = deepest.code
        doc.admin_level = deepest.level
        doc.area_level = deepest.level

    doc.province_name = province.area_name if province else None
    doc.city_name = city.area_name if city else None
    doc.district_name = district.area_name if district else None
    doc.village_name = village.area_name if village else None

    doc.consent_to_contact = cint(consent_to_contact or 0)
    doc.status = "submitted"
    doc.intake_mode = intake_mode
    doc.intake_parser = parser

    _route(doc)
    doc.insert(ignore_permissions=True)

    community_need = None

    if cint(create_need):
        need_text = (urgent_needs or "").strip()

        if not need_text:
            frappe.throw(
                "Kebutuhan Mendesak wajib diisi bila dijadikan kebutuhan penanganan"
            )

        need = frappe.new_doc("RN Community Need")
        need.title = f"Kebutuhan - {doc.title}"
        need.source_report = doc.name
        need.requester_user = doc.reporter_user
        need.disaster_event = doc.disaster_event

        if doc.reporter_user:
            need.community_owner = frappe.db.get_value(
                "RN User Account",
                doc.reporter_user,
                "organization",
            )

            if not need.community_owner:
                memberships = frappe.get_all(
                    "RN Organization Membership",
                    filters={
                        "user_account": doc.reporter_user,
                        "status": "approved",
                    },
                    fields=["organization"],
                    order_by="approved_at desc, creation asc",
                    limit_page_length=1,
                )
                if memberships:
                    need.community_owner = memberships[0].organization

            if not need.community_owner:
                memberships = frappe.get_all(
                    "RN Organization Membership",
                    filters={
                        "user_account": doc.reporter_user,
                        "status": "approved",
                    },
                    fields=["organization"],
                    order_by="approved_at desc, creation asc",
                    limit_page_length=1,
                )
                if memberships:
                    need.community_owner = memberships[0].organization

        need.need_type = doc.report_type
        need.description = need_text

        if priority in ("low", "medium", "high", "critical"):
            need.urgency = priority

        need.handling_mode = "community"
        need.takeover_status = "none"
        need.status = "open"

        need.verification_status = "unverified"
        need.verification_status = "unverified"
        need.insert(ignore_permissions=True)
        community_need = need.name

        frappe.db.set_value(
            "RN Community Report",
            doc.name,
            {
                "converted_object_type": "RN Community Need",
                "converted_object_id": need.name,
            },
            update_modified=False,
        )

        frappe.db.set_value(
            "RN Community Report",
            doc.name,
            {
                "converted_object_type": "RN Community Need",
                "converted_object_id": need.name,
            },
            update_modified=False,
        )

    predicted_needs = predict_report_needs(
        doc.report_type, doc.damage_scale_value, doc.affected_people_count,
    )

    return {
        "name": doc.name,
        "status": doc.status,
        "reporter_user": doc.reporter_user,
        "admin_area_id": doc.admin_area_id,
        "has_coordinates": doc.has_coordinates,
        "community_need": community_need,
        "posko": doc.posko,
        "posko_title": frappe.db.get_value("RN Posko", doc.posko, "title") if doc.posko else None,
        "routing_reason": doc.routing_reason,
        "intake_parser": doc.intake_parser,
        "predicted_needs": predicted_needs,
        "predicted_needs_note": (
            "Perkiraan heuristik dari skala kerusakan/jumlah terdampak yang dilaporkan — "
            "bukan perhitungan teknis, untuk membantu posko menyesuaikan persiapan awal."
        ) if predicted_needs else None,
    }


# ============================================================
# Laporan Masyarakat: uraian -> form (AI / aturan), posko tujuan otomatis,
# tindak lanjut oleh pelapor. The reporter must be logged in (RN account or
# Google) so the report stays theirs and they can add to it later.
# ============================================================

def _route(doc):
    from frappe.utils import now_datetime

    from rescue_net.services.report_routing import best_posko

    posko, score, reason = best_posko(doc.as_dict())
    doc.posko = posko
    doc.routing_score = score
    doc.routing_reason = reason
    doc.routing_mode = "auto" if posko else None
    doc.routed_at = now_datetime() if posko else None


def _require_reporter():
    from rescue_net.access_policy import rn_actor

    if frappe.session.user == "Guest":
        frappe.throw("Masuk dulu (akun Rescue-Net atau Google) untuk melapor.", frappe.PermissionError)
    actor = rn_actor(required=True)
    return actor


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=30, seconds=60 * 60)
def draft_community_report(
    narrative,
    disaster_event=None,
    latitude=None,
    longitude=None,
    province_code=None,
    city_code=None,
    district_code=None,
    village_code=None,
):
    """Uraian warga -> isian form + posko tujuan yang diusulkan. Nothing is
    saved: the reporter reviews the suggestion and sends it with
    submit_community_report(intake_mode="narrative")."""
    _require_reporter()
    narrative = (narrative or "").strip()
    if len(narrative) < 15:
        frappe.throw("Uraian terlalu pendek — ceritakan apa yang terjadi, di mana, dan apa yang dibutuhkan.")
    if len(narrative) > 5000:
        frappe.throw("Uraian terlalu panjang (maks. 5.000 karakter).")

    from rescue_net.reference_resolver import resolve_disaster_event
    from rescue_net.services.report_intake import REPORT_TYPES, extract
    from rescue_net.services.report_routing import best_posko

    fields, parser = extract(narrative)
    areas = {lvl: _area(code) for lvl, code in (("province", province_code), ("city", city_code),
                                                 ("district", district_code), ("village", village_code))}
    probe = {
        "disaster_event": resolve_disaster_event(disaster_event) if disaster_event else None,
        "report_type": fields["report_type"],
        "latitude": None if latitude in (None, "") else flt(latitude),
        "longitude": None if longitude in (None, "") else flt(longitude),
        "admin_area_id": next((a.code for a in (areas["village"], areas["district"], areas["city"],
                                                  areas["province"]) if a), None),
    }
    for lvl in ("province", "city", "district", "village"):
        probe[f"{lvl}_name"] = areas[lvl].area_name if areas[lvl] else None
    posko, score, reason = best_posko(probe)

    return {
        "fields": fields,
        "parser": parser,
        "parser_label": "AI (" + parser.split(":", 1)[1] + ")" if parser.startswith("ai:") else "aturan kata kunci",
        "report_type_label": REPORT_TYPES.get(fields["report_type"]),
        "suggested_posko": posko,
        "suggested_posko_title": frappe.db.get_value("RN Posko", posko, "title") if posko else None,
        "routing_score": score,
        "routing_reason": reason,
        "predicted_needs": predict_report_needs(fields["report_type"], fields["damage_scale_value"],
                                                fields["affected_people_count"]),
    }


def _report_or_404(report):
    name = report if frappe.db.exists("RN Community Report", report) else frappe.db.get_value(
        "RN Community Report", {"legacy_id": report}, "name")
    if not name:
        frappe.throw("Laporan tidak ditemukan", frappe.DoesNotExistError)
    return frappe.get_doc("RN Community Report", name)


def _update_role(actor, doc):
    """'reporter' for the report's own reporter, 'posko' for a manager of the
    routed posko (or System Manager), else None."""
    from rescue_net.access_policy import can_manage_posko, is_system_manager

    if actor and doc.reporter_user and actor.name == doc.reporter_user:
        return "reporter"
    if is_system_manager() or (doc.posko and actor and can_manage_posko(actor, doc.posko)):
        return "posko"
    return None


def _updates(report):
    return frappe.get_all(
        "RN Community Report Update", filters={"report": report},
        fields=["name", "update_type", "body", "urgent_needs", "affected_people_count", "author_role",
                "posted_at"],
        order_by="posted_at asc, creation asc",
    )


@frappe.whitelist()
def my_community_reports():
    """The logged-in reporter's own reports, newest first, with follow-ups."""
    actor = _require_reporter()
    rows = frappe.get_all(
        "RN Community Report", filters={"reporter_user": actor.name},
        fields=["name", "title", "report_type", "priority", "status", "location_text", "affected_people_count",
                "urgent_needs", "posko", "routing_reason", "intake_mode", "intake_parser", "creation"],
        order_by="creation desc", limit_page_length=100,
    )
    for r in rows:
        r["posko_title"] = frappe.db.get_value("RN Posko", r.posko, "title") if r.posko else None
        r["updates"] = _updates(r.name)
    return rows


@frappe.whitelist()
def community_report_updates(report):
    actor = _require_reporter()
    doc = _report_or_404(report)
    if not _update_role(actor, doc):
        frappe.throw("Hanya pelapor dan posko tujuan yang dapat melihat tindak lanjut.", frappe.PermissionError)
    return _updates(doc.name)


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=60, seconds=60 * 60)
def add_community_report_update(report, body, update_type="info", urgent_needs=None, affected_people_count=None):
    """The reporter adds what changed / what else is needed ("bantuan
    berikutnya"); the routed posko answers on the same thread."""
    actor = _require_reporter()
    doc = _report_or_404(report)
    role = _update_role(actor, doc)
    if not role:
        frappe.throw("Hanya pelapor dan posko tujuan yang dapat menambah tindak lanjut.", frappe.PermissionError)
    if doc.status == "rejected":
        frappe.throw("Laporan ini sudah ditolak — kirim laporan baru.")

    row = frappe.get_doc({
        "doctype": "RN Community Report Update",
        "report": doc.name,
        "update_type": update_type or "info",
        "body": (body or "").strip()[:2000],
        "urgent_needs": (urgent_needs or "").strip()[:500] or None,
        "affected_people_count": cint(affected_people_count) if affected_people_count not in (None, "") else None,
        "author_user": actor.name,
        "author_role": role,
    })
    row.insert(ignore_permissions=True)
    return {"update": row.name, "report": doc.name, "author_role": role, "updates": _updates(doc.name)}


@frappe.whitelist(methods=["POST"])
def reroute_community_report(report, posko):
    """Hand a report to another posko of the same event: a manager of the
    current posko, Control Centre or System Manager (unrouted reports: any
    manager of the target posko may take them)."""
    from frappe.utils import now_datetime

    from rescue_net.access_policy import can_manage_posko, is_system_manager, rn_actor
    from rescue_net.reference_resolver import resolve_posko

    actor = rn_actor(required=True)
    doc = _report_or_404(report)
    posko = resolve_posko(posko)
    target = frappe.db.get_value("RN Posko", posko, ["name", "title", "disaster_event"], as_dict=True)
    if not target:
        frappe.throw("Posko tujuan tidak ditemukan")
    if doc.disaster_event and target.disaster_event != doc.disaster_event:
        frappe.throw("Posko tujuan harus pada kejadian bencana yang sama.")
    allowed = is_system_manager() or (actor and actor.get("role") == "command_center") or (
        doc.posko and can_manage_posko(actor, doc.posko)) or (not doc.posko and can_manage_posko(actor, posko))
    if not allowed:
        frappe.throw("Hanya posko tujuan saat ini atau Control Centre yang dapat mengalihkan laporan.",
                     frappe.PermissionError)
    old = doc.posko
    frappe.db.set_value("RN Community Report", doc.name, {
        "posko": target.name, "routing_mode": "manual", "routed_at": now_datetime(),
        "routing_reason": f"Dialihkan manual ke {target.title}" + (f" dari {old}" if old else ""),
    })
    return {"report": doc.name, "posko": target.name, "posko_title": target.title, "previous_posko": old}
