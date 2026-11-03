"""Recovery dan Alat Kerja — support offers (owner 2026-11-03):

"alat tersedia bisa diklik ke halaman penyedia, kontak person ... halaman untuk pemilik alat yang ingin
sumbangkan alat, data alatnya, bisa dipakai dalam range waktu, kebutuhan pendukung untuk mobilisasi alatnya,
termasuk operator atau tidak ... untuk recovery ini juga selain alat juga kebutuhan relawan".

Tools (RN Resource Profile):
- tool_detail (guest): one tool + who provides it (link to the organisation / posko page) + contact person.
  The PIC's name / phone / email go to logged-in accounts only, unless the owner ticked contact_public.
  A private person's name is never shown as the provider (same rule as the tools board).
- my_tools / offer_tool / update_tool_offer / withdraw_tool (login): an owner offers a tool as hibah /
  pinjam / sewa, as themselves or for an organisation they manage, with usable date range, operator
  included or not, and what mobilisation needs (transport, BBM, akomodasi operator, other, cost).

Volunteers (RN Recovery Volunteer Need / Signup):
- volunteer_needs (guest): open needs per recovery project, counts only (no volunteer names / phones).
- create / update need: the recovery project's owner (same rule as patch_project) or Control Centre.
- signup / cancel (any logged-in account); the project owner sees signups with contact and confirms /
  rejects. A need becomes 'filled' when the confirmed count reaches the number needed (and reopens).
"""

import frappe
from frappe.rate_limiter import rate_limit
from frappe.utils import cint, flt, getdate, now_datetime

from rescue_net.access_policy import can_manage_organization, rn_actor
from rescue_net.reference_resolver import resolve_disaster_event
from rescue_net.resource_tools.common import _CATEGORY_LABELS, _can_manage_reference, _resource_access

OFFER_TYPES = {"hibah": "Dihibahkan (disumbangkan)", "pinjam": "Dipinjamkan gratis", "sewa": "Disewakan"}
TOOL_STATUS = {"available": "Siap dipakai", "limited": "Terbatas", "unavailable": "Tidak tersedia",
               "maintenance": "Perawatan"}
from rescue_net.services import equipment_specs  # noqa: E402

TOOL_CATEGORIES = equipment_specs.labels()        # spec catalog (owner 2026-11-03), a superset of tool_needs
_TEXT_MAX = 2000

# fields an owner may set through offer_tool / update_tool_offer
TOOL_FIELDS = ("resource_name", "category", "quantity", "unit", "capacity_description", "availability_status",
               "current_location", "coverage_area", "available_from", "available_until", "offer_type",
               "operator_included", "operator_count", "support_operator", "support_transport", "support_fuel",
               "support_accommodation", "mobilization_needs", "mobilization_cost", "daily_operating_cost",
               "support_notes", "pic_name", "pic_phone", "pic_email", "contact_public", "notes",
               "brand", "model", "manufacture_year", "serial_number", "tool_condition", "specs")
_CHECKS = {"operator_included", "support_operator", "support_transport", "support_fuel", "support_accommodation",
           "contact_public"}

# public part of a tool (no PIC, no notes)
_PUBLIC_TOOL = ["name", "disaster_event", "resource_name", "category", "quantity", "unit", "capacity_description",
                "availability_status", "current_location", "coverage_area", "available_from", "available_until",
                "offer_type", "operator_included", "operator_count", "support_operator", "support_transport",
                "support_fuel", "support_accommodation", "mobilization_needs", "mobilization_cost",
                "daily_operating_cost", "support_notes", "verification_status", "owner_type", "owner_id",
                "contact_public", "brand", "model", "manufacture_year", "tool_condition", "specs", "photo_url", "photos",
                "modified"]


# ----------------------------------------------------------------------------------------------- helpers
def _account(actor):
    return actor.get("name") if actor else None


def _clean_text(v):
    v = (str(v).strip() if v is not None else "")
    return v[:_TEXT_MAX] or None


def _tool_values(fields, partial):
    out = {}
    for k in TOOL_FIELDS:
        if k not in fields:
            continue
        v = fields[k]
        if k in _CHECKS:
            out[k] = 1 if str(v or "").lower() in ("1", "true", "yes", "on") else 0
        elif k in ("quantity",):
            q = flt(v)
            if q <= 0:
                frappe.throw("Jumlah alat harus lebih dari 0.")
            out[k] = q
        elif k in ("operator_count",):
            n = cint(v)
            if n < 0 or n > 500:
                frappe.throw("Jumlah operator harus 0–500.")
            out[k] = n or None
        elif k in ("mobilization_cost", "daily_operating_cost"):
            if v in (None, ""):
                out[k] = None
            else:
                if flt(v) < 0:
                    frappe.throw("Biaya tidak boleh negatif.")
                out[k] = flt(v)
        elif k in ("available_from", "available_until"):
            out[k] = str(getdate(v)) if v else None
        elif k == "offer_type":
            if v and v not in OFFER_TYPES:
                frappe.throw("Skema penyediaan tidak dikenal (hibah / pinjam / sewa).")
            out[k] = v or None
        elif k == "availability_status":
            if v not in TOOL_STATUS:
                frappe.throw("Status alat tidak dikenal.")
            out[k] = v
        elif k == "category":
            if v not in TOOL_CATEGORIES:
                frappe.throw("Kategori alat tidak dikenal.")
            out[k] = v
        elif k == "manufacture_year":
            n = cint(v)
            if v not in (None, "") and not (1950 <= n <= 2100):
                frappe.throw("Tahun pembuatan tidak masuk akal.")
            out[k] = n or None
        elif k == "tool_condition":
            if v and v not in equipment_specs.CONDITIONS:
                frappe.throw("Kondisi alat tidak dikenal.")
            out[k] = v or None
        elif k == "specs":
            out[k] = v              # cleaned below, needs the category
        elif k == "pic_email":
            v = (v or "").strip().lower()
            if v:
                from frappe.utils import validate_email_address
                if not validate_email_address(v):
                    frappe.throw("Email PIC tidak valid.")
            out[k] = v or None
        else:
            out[k] = _clean_text(v)
    if "specs" in out:
        out["specs"] = equipment_specs.clean_specs(out.get("category") or fields.get("_category") or "lainnya", out["specs"])
    if not partial or "resource_name" in out:
        if not out.get("resource_name"):
            frappe.throw("Nama alat wajib diisi.")
    if out.get("operator_included"):
        out["support_operator"] = 0          # comes with its operator → does not need one
    start = out.get("available_from")
    end = out.get("available_until")
    if start and end and getdate(end) < getdate(start):
        frappe.throw("Tanggal 'bisa dipakai sampai' tidak boleh sebelum 'mulai'.")
    return out


def _managed_orgs(actor):
    acc = _account(actor)
    if not acc:
        return []
    ids = set(frappe.get_all("RN Organization Membership", filters={"user_account": acc, "status": "approved"},
                             pluck="organization"))
    if actor.get("organization"):
        ids.add(actor.get("organization"))
    out = []
    for org in ids:
        if org and can_manage_organization(actor, org):
            out.append({"name": org, "title": frappe.db.get_value("RN Organization", org, "title") or org})
    return out


def _provider(row):
    """Who provides the tool, public: label + link to its page (organisation / posko)."""
    if row.owner_type == "organization" and row.owner_id:
        t = frappe.db.get_value("RN Organization", row.owner_id, "title")
        return {"type": "organization", "label": t or "Organisasi", "href": f"organisasi-posko.html?org={row.owner_id}"}
    if row.owner_type == "posko" and row.owner_id:
        t = frappe.db.get_value("RN Posko", row.owner_id, "title")
        ev = row.disaster_event or ""
        return {"type": "posko", "label": t or "Posko", "href": f"posko-detail.html?id={row.owner_id}&event={ev}"}
    return {"type": row.owner_type or "individual", "label": "Perorangan", "href": ""}


def _tool_public(row):
    d = {k: row.get(k) for k in _PUBLIC_TOOL if k not in ("owner_id",)}
    d["category_label"] = TOOL_CATEGORIES.get(row.category, row.category or "")
    d["status_label"] = TOOL_STATUS.get(row.availability_status, row.availability_status or "")
    d["offer_label"] = OFFER_TYPES.get(row.offer_type or "", "")
    d["provider"] = _provider(row)
    d["photos"] = _photos(row.get("photos"), row.get("photo_url"))
    d["condition_label"] = equipment_specs.CONDITIONS.get(row.get("tool_condition") or "", "")
    d["spec_rows"] = equipment_specs.spec_rows(row.category, row.get("specs"))
    return d


MAX_PHOTOS = 10


def _photos(raw, legacy=None):
    import json
    try:
        val = json.loads(raw or "[]")
        out = [p for p in val if isinstance(p, dict) and p.get("url")]
    except (ValueError, TypeError):
        out = []
    if legacy and legacy not in [p["url"] for p in out]:
        out.insert(0, {"url": legacy, "name": legacy.rsplit("/", 1)[-1]})
    return out


def _wa(number):
    from rescue_net.resource_tools.boards import _wa_url
    return _wa_url(number)


# ----------------------------------------------------------------------------------------------- tools
@frappe.whitelist(allow_guest=True)
@rate_limit(limit=120, seconds=60)
def tool_detail(resource_profile):
    row = frappe.db.get_value("RN Resource Profile", resource_profile,
                              _PUBLIC_TOOL + ["pic_name", "pic_phone", "pic_email"], as_dict=True)
    if not row:
        return {"found": False}
    actor = rn_actor(required=False)
    if row.disaster_event:
        from rescue_net.services.drill import real_rows
        if not real_rows([frappe._dict(disaster_event=row.disaster_event)]):
            return {"found": False}          # drill tools never reach a guest / non-admin
    out = _tool_public(row)
    out["found"] = True
    can_manage = bool(actor) and _can_manage_reference(actor, row.owner_type, row.owner_id)
    out["can_manage"] = can_manage
    show = bool(row.contact_public) or bool(_account(actor)) or can_manage
    has = bool(row.pic_name or row.pic_phone or row.pic_email)
    out["contact"] = {
        "available": has,
        "shown": show and has,
        "name": row.pic_name if show else None,
        "phone": row.pic_phone if show else None,
        "email": row.pic_email if show else None,
        "whatsapp_url": _wa(row.pic_phone) if show and row.pic_phone else None,
    }
    if not has and row.owner_type == "organization" and row.owner_id:
        org = frappe.db.get_value("RN Organization", row.owner_id, ["contact_person", "contact_summary"], as_dict=True)
        if org and (org.contact_person or org.contact_summary):
            out["contact"]["org_contact"] = {"name": org.contact_person, "note": org.contact_summary}
    # other tools of the same provider (organisation / posko only; a private person stays unlinked)
    others = []
    if row.owner_type in ("organization", "posko") and row.owner_id:
        others = frappe.get_all("RN Resource Profile",
                                filters={"owner_type": row.owner_type, "owner_id": row.owner_id,
                                         "name": ["!=", row.name]},
                                fields=["name", "resource_name", "quantity", "unit", "availability_status"],
                                order_by="resource_name asc", limit_page_length=30)
        for o in others:
            o["status_label"] = TOOL_STATUS.get(o.availability_status, o.availability_status or "")
    out["other_tools"] = others
    return out


@frappe.whitelist()
def tool_form_options():
    actor = rn_actor()
    return {
        "categories": [{"value": k, "label": v} for k, v in TOOL_CATEGORIES.items()],
        "offer_types": [{"value": k, "label": v} for k, v in OFFER_TYPES.items()],
        "statuses": [{"value": k, "label": v} for k, v in TOOL_STATUS.items()],
        "catalog": equipment_specs.catalog(),
        "conditions": [{"value": k, "label": v} for k, v in equipment_specs.CONDITIONS.items()],
        "organizations": _managed_orgs(actor),
        "account": _account(actor),
    }


@frappe.whitelist()
def my_tools():
    actor = rn_actor()
    acc = _account(actor)
    rows = []
    if acc:
        rows += frappe.get_all("RN Resource Profile", filters={"owner_type": "individual", "owner_id": acc},
                               fields=_PUBLIC_TOOL + ["pic_name", "pic_phone", "pic_email", "notes", "serial_number"],
                               limit_page_length=500)
    for org in _managed_orgs(actor):
        rows += frappe.get_all("RN Resource Profile", filters={"owner_type": "organization", "owner_id": org["name"]},
                               fields=_PUBLIC_TOOL + ["pic_name", "pic_phone", "pic_email", "notes", "serial_number"],
                               limit_page_length=500)
    out = []
    for r in sorted(rows, key=lambda r: str(r.modified), reverse=True):
        d = _tool_public(r)
        d.update(pic_name=r.pic_name, pic_phone=r.pic_phone, pic_email=r.pic_email, notes=r.notes,
                 serial_number=r.serial_number)
        out.append(d)
    return {"tools": out}


@frappe.whitelist(methods=["POST"])
def offer_tool(disaster_event, resource_name, owner_type="individual", organization=None, **fields):
    actor = rn_actor()
    acc = _account(actor)
    event = resolve_disaster_event(disaster_event)
    if not event or not frappe.db.exists("RN Disaster Event", event):
        frappe.throw("Pilih bencana yang ditawari alat.")
    if owner_type == "organization":
        if not (organization and can_manage_organization(actor, organization)):
            frappe.throw("Anda bukan pengelola organisasi ini.", frappe.PermissionError)
        owner_id = organization
    elif owner_type == "individual":
        if not acc:
            frappe.throw("Akun Rescue-Net aktif tidak ditemukan.", frappe.PermissionError)
        owner_id = acc
    else:
        frappe.throw("Pemilik alat harus perorangan atau organisasi.")
    fields = dict(fields, resource_name=resource_name)
    fields.setdefault("category", "lainnya")
    fields.setdefault("availability_status", "available")
    values = _tool_values(fields, partial=False)
    doc = frappe.new_doc("RN Resource Profile")
    doc.update(values)
    doc.disaster_event = event
    doc.owner_type = owner_type
    doc.owner_id = owner_id
    doc.resource_type = values.get("category")
    doc.unit = values.get("unit") or "unit"
    doc.quantity = values.get("quantity") or 1
    doc.offered_by_user = acc
    doc.verification_status = "self_reported"
    doc.insert(ignore_permissions=True)
    return {"resource_profile": doc.name}


@frappe.whitelist(methods=["POST"])
def update_tool_offer(resource_profile, **fields):
    actor = rn_actor()
    if not _resource_access(actor, resource_profile):
        frappe.throw("Hanya pemilik / pengelola alat yang boleh mengubah.", frappe.PermissionError)
    doc = frappe.get_doc("RN Resource Profile", resource_profile)
    values = _tool_values(dict(fields, _category=doc.category), partial=True)
    doc.update(values)
    if doc.available_from and doc.available_until and getdate(doc.available_until) < getdate(doc.available_from):
        frappe.throw("Tanggal 'bisa dipakai sampai' tidak boleh sebelum 'mulai'.")
    if doc.operator_included:
        doc.support_operator = 0
    doc.save(ignore_permissions=True)
    return tool_detail(resource_profile)


@frappe.whitelist(methods=["POST"])
def upload_tool_photo(resource_profile, filename, content_base64):
    """Add one photo to a tool (up to MAX_PHOTOS; PNG / JPG / WEBP, 10 MB, public), owner / manager only.
    Owner 2026-11-03: "pemilik alat untuk upload foto2 alatnya"."""
    import base64
    import re
    from frappe.utils.file_manager import save_file
    from rescue_net.donor_program.documents import _check_file

    actor = rn_actor()
    if not _resource_access(actor, resource_profile):
        frappe.throw("Hanya pemilik / pengelola alat yang boleh mengunggah foto.", frappe.PermissionError)
    filename = re.sub(r"[^\w.\- ]", "_", str(filename or "").strip())[:120]
    if not filename or filename.lower().endswith(".pdf"):
        frappe.throw("Foto alat harus berupa gambar (PNG / JPG / WEBP).")
    try:
        content = base64.b64decode(content_base64 or "", validate=False)
    except Exception:
        frappe.throw("Isi file tidak valid.")
    if not content:
        frappe.throw("File kosong.")
    _check_file("gambar", filename, content)
    row = frappe.db.get_value("RN Resource Profile", resource_profile, ["photos", "photo_url"], as_dict=True)
    photos = _photos(row.photos, row.photo_url)
    if len(photos) >= MAX_PHOTOS:
        frappe.throw(f"Maksimal {MAX_PHOTOS} foto per alat. Hapus foto lama dulu.")
    f = save_file(filename, content, "RN Resource Profile", resource_profile, is_private=0)
    photos.append({"url": f.file_url, "name": filename})
    return _save_photos(resource_profile, photos)


def _save_photos(resource_profile, photos):
    import json
    frappe.db.set_value("RN Resource Profile", resource_profile, {
        "photos": json.dumps(photos, ensure_ascii=False) if photos else None,
        "photo_url": photos[0]["url"] if photos else None})
    return {"resource_profile": resource_profile, "photos": photos, "photo_url": photos[0]["url"] if photos else None}


@frappe.whitelist(methods=["POST"])
def remove_tool_photo(resource_profile, file_url):
    actor = rn_actor()
    if not _resource_access(actor, resource_profile):
        frappe.throw("Hanya pemilik / pengelola alat yang boleh menghapus foto.", frappe.PermissionError)
    row = frappe.db.get_value("RN Resource Profile", resource_profile, ["photos", "photo_url"], as_dict=True)
    photos = _photos(row.photos, row.photo_url)
    keep = [p for p in photos if p["url"] != file_url]
    if len(keep) == len(photos):
        frappe.throw("Foto tidak ditemukan pada alat ini.")
    return _save_photos(resource_profile, keep)


@frappe.whitelist(methods=["POST"])
def withdraw_tool(resource_profile):
    """Owner takes the offer back: the tool stays on record (deployments keep their history) but is
    'Tidak tersedia'."""
    actor = rn_actor()
    if not _resource_access(actor, resource_profile):
        frappe.throw("Hanya pemilik / pengelola alat yang boleh menarik alat.", frappe.PermissionError)
    frappe.db.set_value("RN Resource Profile", resource_profile, "availability_status", "unavailable")
    return {"resource_profile": resource_profile, "availability_status": "unavailable"}


# ----------------------------------------------------------------------------------------------- volunteers
def _project(project_id):
    p = frappe.db.get_value("RN Recovery Project", project_id,
                            ["name", "project_name", "owner_type", "owner_id", "disaster_event", "location",
                             "is_deleted"], as_dict=True)
    if not p or p.is_deleted:
        frappe.throw("Proyek recovery tidak ditemukan.")
    return p


def _can_manage_project(actor, p):
    from rescue_net.api_donor_program import _allowed_owner
    return bool(actor) and _allowed_owner(actor, p.owner_type, p.owner_id)


def _assert_project(actor, p):
    if not _can_manage_project(actor, p):
        frappe.throw("Hanya pengelola proyek recovery ini yang boleh mengatur kebutuhan relawan.",
                     frappe.PermissionError)


_NEED_FIELDS = ("role_needed", "people_needed", "date_from", "date_to", "location", "task_description",
                "requirements", "provisions")


def _need_values(fields):
    out = {}
    for k in _NEED_FIELDS:
        if k not in fields:
            continue
        v = fields[k]
        if k == "people_needed":
            out[k] = cint(v)
        elif k in ("date_from", "date_to"):
            out[k] = str(getdate(v)) if v else None
        else:
            out[k] = _clean_text(v)
    return out


def _counts(names):
    c = {}
    if names:
        for s in frappe.get_all("RN Recovery Volunteer Signup",
                                filters={"need": ["in", names], "status": ["in", ["requested", "confirmed"]]},
                                fields=["need", "status"], limit_page_length=20000):
            d = c.setdefault(s.need, {"requested": 0, "confirmed": 0})
            d[s.status] += 1
    return c


def _sync_need_status(need):
    n = frappe.get_doc("RN Recovery Volunteer Need", need)
    if n.need_status == "closed":
        return
    confirmed = frappe.db.count("RN Recovery Volunteer Signup", {"need": need, "status": "confirmed"})
    want = "filled" if confirmed >= cint(n.people_needed) else "open"
    if n.need_status != want:
        n.need_status = want
        n.save(ignore_permissions=True)


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=120, seconds=60)
def volunteer_needs(disaster_event=None, recovery_project=None):
    actor = rn_actor(required=False)
    acc = _account(actor)
    filters = {}
    event = resolve_disaster_event(disaster_event) if disaster_event else None
    if event:
        filters["disaster_event"] = event
    if recovery_project:
        filters["recovery_project"] = recovery_project
    rows = frappe.get_all("RN Recovery Volunteer Need", filters=filters,
                          fields=["name", "disaster_event", "recovery_project", "role_needed", "people_needed",
                                  "date_from", "date_to", "location", "task_description", "requirements",
                                  "provisions", "need_status", "modified"],
                          order_by="need_status asc, date_from asc, modified desc", limit_page_length=500)
    from rescue_net.services.drill import real_rows
    rows = real_rows(rows)
    projects = {}
    for r in rows:
        if r.recovery_project not in projects:
            projects[r.recovery_project] = frappe.db.get_value(
                "RN Recovery Project", r.recovery_project,
                ["name", "project_name", "owner_type", "owner_id", "is_deleted", "disaster_event"], as_dict=True)
    rows = [r for r in rows if projects.get(r.recovery_project) and not projects[r.recovery_project].is_deleted]
    counts = _counts([r.name for r in rows])
    mine = {}
    if acc and rows:
        for s in frappe.get_all("RN Recovery Volunteer Signup",
                                filters={"need": ["in", [r.name for r in rows]], "user_account": acc,
                                         "status": ["in", ["requested", "confirmed"]]},
                                fields=["name", "need", "status"]):
            mine[s.need] = {"signup": s.name, "status": s.status}
    from rescue_net.resource_tools.boards import _provider_labels
    owner_of = _provider_labels(list(projects.values()))
    out = []
    for r in rows:
        p = projects[r.recovery_project]
        c = counts.get(r.name, {"requested": 0, "confirmed": 0})
        d = dict(r)
        d.update(project_title=p.project_name, project_owner=owner_of(p), confirmed=c["confirmed"],
                 requested=c["requested"], remaining=max(0, cint(r.people_needed) - c["confirmed"]),
                 can_manage=_can_manage_project(actor, p), my_signup=mine.get(r.name))
        out.append(d)
    managed = []
    if actor:
        pf = {"is_deleted": 0}
        if event:
            pf["disaster_event"] = event
        for p in frappe.get_all("RN Recovery Project", filters=pf,
                                fields=["name", "project_name", "owner_type", "owner_id"], limit_page_length=500):
            if _can_manage_project(actor, p):
                managed.append({"name": p.name, "title": p.project_name})
    return {
        "needs": out,
        "managed_projects": managed,
        "logged_in": bool(actor),
        "totals": {
            "needs": len(out),
            "open": sum(1 for n in out if n["need_status"] == "open"),
            "people_needed": sum(cint(n["people_needed"]) for n in out if n["need_status"] != "closed"),
            "confirmed": sum(n["confirmed"] for n in out),
        },
    }


@frappe.whitelist(methods=["POST"])
def create_volunteer_need(recovery_project, role_needed, people_needed=1, **fields):
    actor = rn_actor()
    p = _project(recovery_project)
    _assert_project(actor, p)
    values = _need_values(dict(fields, role_needed=role_needed, people_needed=people_needed))
    doc = frappe.new_doc("RN Recovery Volunteer Need")
    doc.update(values)
    doc.recovery_project = p.name
    doc.disaster_event = p.disaster_event
    doc.location = doc.location or p.location
    doc.need_status = "open"
    doc.created_by_user = _account(actor)
    doc.insert(ignore_permissions=True)
    return {"need": doc.name}


@frappe.whitelist(methods=["POST"])
def update_volunteer_need(need, need_status=None, **fields):
    actor = rn_actor()
    n = frappe.get_doc("RN Recovery Volunteer Need", need)
    _assert_project(actor, _project(n.recovery_project))
    n.update(_need_values(fields))
    if need_status:
        if need_status not in ("open", "closed"):
            frappe.throw("Status hanya bisa 'open' (buka) atau 'closed' (tutup).")
        n.need_status = need_status
    n.save(ignore_permissions=True)
    if n.need_status != "closed":
        _sync_need_status(need)
    return {"need": need, "need_status": frappe.db.get_value("RN Recovery Volunteer Need", need, "need_status")}


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=30, seconds=3600)
def signup_volunteer_need(need, phone=None, skill=None, note=None, date_from=None, date_to=None):
    actor = rn_actor()
    acc = _account(actor)
    if not acc:
        frappe.throw("Akun Rescue-Net aktif diperlukan untuk mendaftar.", frappe.PermissionError)
    n = frappe.db.get_value("RN Recovery Volunteer Need", need, ["name", "need_status"], as_dict=True)
    if not n:
        frappe.throw("Kebutuhan relawan tidak ditemukan.")
    if n.need_status != "open":
        frappe.throw("Kebutuhan relawan ini sudah terpenuhi / ditutup.")
    if frappe.db.exists("RN Recovery Volunteer Signup",
                        {"need": need, "user_account": acc, "status": ["in", ["requested", "confirmed"]]}):
        frappe.throw("Anda sudah terdaftar untuk kebutuhan ini.")
    a = frappe.db.get_value("RN User Account", acc, ["title", "phone"], as_dict=True) or {}
    phone = (phone or a.get("phone") or "").strip()
    if not phone:
        frappe.throw("Isi nomor HP / WhatsApp agar pengelola proyek bisa menghubungi Anda.")
    doc = frappe.new_doc("RN Recovery Volunteer Signup")
    doc.need = need
    doc.user_account = acc
    doc.volunteer_name = a.get("title") or acc
    doc.phone = phone[:40]
    doc.skill = _clean_text(skill)
    doc.note = _clean_text(note)
    doc.date_from = str(getdate(date_from)) if date_from else None
    doc.date_to = str(getdate(date_to)) if date_to else None
    doc.status = "requested"
    doc.insert(ignore_permissions=True)
    return {"signup": doc.name, "status": doc.status}


@frappe.whitelist(methods=["POST"])
def cancel_my_signup(signup):
    actor = rn_actor()
    s = frappe.get_doc("RN Recovery Volunteer Signup", signup)
    if s.user_account != _account(actor):
        frappe.throw("Ini bukan pendaftaran Anda.", frappe.PermissionError)
    s.status = "cancelled"
    s.save(ignore_permissions=True)
    _sync_need_status(s.need)
    return {"signup": signup, "status": "cancelled"}


@frappe.whitelist()
def need_signups(need):
    actor = rn_actor()
    n = frappe.db.get_value("RN Recovery Volunteer Need", need, ["name", "recovery_project"], as_dict=True)
    if not n:
        frappe.throw("Kebutuhan relawan tidak ditemukan.")
    _assert_project(actor, _project(n.recovery_project))
    rows = frappe.get_all("RN Recovery Volunteer Signup", filters={"need": need},
                          fields=["name", "volunteer_name", "phone", "skill", "date_from", "date_to", "note", "status",
                                  "creation"], order_by="creation asc", limit_page_length=1000)
    for r in rows:
        r["whatsapp_url"] = _wa(r.phone)
        r["creation"] = str(r.creation)[:16]
    return {"need": need, "signups": rows}


@frappe.whitelist(methods=["POST"])
def decide_signup(signup, status):
    actor = rn_actor()
    if status not in ("confirmed", "rejected"):
        frappe.throw("Keputusan harus 'confirmed' atau 'rejected'.")
    s = frappe.get_doc("RN Recovery Volunteer Signup", signup)
    n = frappe.db.get_value("RN Recovery Volunteer Need", s.need, ["name", "recovery_project"], as_dict=True)
    _assert_project(actor, _project(n.recovery_project))
    s.status = status
    s.decided_by = _account(actor)
    s.decided_at = now_datetime()
    s.save(ignore_permissions=True)
    _sync_need_status(s.need)
    return {"signup": signup, "status": status}
