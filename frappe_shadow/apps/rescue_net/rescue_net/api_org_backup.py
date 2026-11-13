"""Backup & restore data lengkap satu organisasi oleh admin organisasinya sendiri (owner 2026-11-13).

Owner: "untuk organisasi tambahkan di pengaturan admin nya mereka bisa backup semua data lengkap organisasi dan
bisa restore, jadi jika data rusak mereka lakukan restore sendiri."

Aturan (diusulkan Suri, owner "lanjutkan"):
1. Backup = satu file .json.gz: organisasi, keanggotaan, semua posko organisasi, dan semua catatan yang
   menempel ke organisasi / posko-poskonya. Disimpan privat (File menempel ke RN Organization), bisa diunduh.
   Hanya admin organisasi (pemilik keanggotaan / komando) atau super admin.
2. Restore hanya menyentuh data MILIK organisasi itu. Setiap catatan di file diperiksa: kolom pemiliknya harus
   menunjuk organisasi ini atau posko milik organisasi ini, dan catatan yang kini milik organisasi lain tidak
   ditimpa. File yang diubah tangan tidak bisa dipakai menulis data organisasi lain.
3. Sebelum restore sistem otomatis membuat backup keadaan sekarang (bisa dipulihkan balik).
4. Catatan yang rusak/terhapus dikembalikan ke isi saat backup. Catatan baru setelah backup TIDAK dihapus, kecuali
   admin mencentang hapus_baru.
5. Setiap backup / restore dicatat (Comment di RN Organization: siapa, kapan, jumlah).
Berkas foto/dokumen fisik tidak ikut dihapus/ditimpa: catatan yang menunjuk berkas tetap memakai alamat yang sama.
"""

import base64
import datetime
import gzip
import json

import frappe
from frappe.rate_limiter import rate_limit

from rescue_net.access_policy import can_manage_organization, rn_actor

ORG = "RN Organization"
POSKO = "RN Posko"
PREFIX = "backup-org-"
FORMAT = "rescue-net-org-backup/1"
MAX_UPLOAD = 60 * 1024 * 1024
RN_MODULES = ("RN Search Found", "RN Core", "RN Command", "RN Community", "RN Logistics", "RN Shelter", "RN Medical",
              "RN Volunteer", "RN Resources", "RN Donor", "RN Verification", "RN Intelligence")
# milik bersama / tata kelola lintas organisasi: tidak ikut backup-restore organisasi
SKIP = {ORG, POSKO, "RN User Account", "RN Disaster Event", "RN Org Merge Request", "RN Command Change Request"}
META_SKIP = {"modified", "creation", "owner", "modified_by", "_user_tags", "_comments", "_assign", "_liked_by",
             "_seen", "docstatus"}


# ---- peta pemilik ----------------------------------------------------------------------------------------------
def _owner_field(dt):
    """(jenis, fieldname) kolom yang menentukan pemilik catatan dt: link ke organisasi, atau link ke posko."""
    meta = frappe.get_meta(dt)
    links = [f for f in meta.fields if f.fieldtype == "Link"]
    org = [f.fieldname for f in links if f.options == ORG]
    if org:
        return ("org", "organization" if "organization" in org else org[0])
    posko = [f.fieldname for f in links if f.options == POSKO]
    if posko:
        return ("posko", "posko" if "posko" in posko else posko[0])
    return None


def _doctypes():
    out = []
    for dt in frappe.get_all("DocType", filters={"module": ["in", list(RN_MODULES)], "istable": 0, "issingle": 0},
                             pluck="name", order_by="name asc"):
        if dt in SKIP:
            continue
        of = _owner_field(dt)
        if of:
            out.append((dt, of[0], of[1]))
    return out


def _org_poskos(org):
    return frappe.get_all(POSKO, filters={"organization": org}, pluck="name", limit_page_length=0)


def _require_admin(organization):
    actor = rn_actor()
    if not organization or not frappe.db.exists(ORG, organization):
        frappe.throw("Organisasi tidak ditemukan.", frappe.DoesNotExistError)
    if not can_manage_organization(actor, organization):
        frappe.throw("Hanya admin organisasi ini yang bisa membuat atau memulihkan backup.", frappe.PermissionError)
    return actor


def _plain(doc):
    d = doc.as_dict(no_default_fields=False, convert_dates_to_str=True)
    return json.loads(frappe.as_json(d))


# ---- backup ----------------------------------------------------------------------------------------------------
def _collect(org):
    poskos = _org_poskos(org)
    records = {ORG: [_plain(frappe.get_doc(ORG, org))],
               POSKO: [_plain(frappe.get_doc(POSKO, p)) for p in poskos]}
    for dt, kind, field in _doctypes():
        values = [org] if kind == "org" else poskos
        if not values:
            continue
        names = frappe.get_all(dt, filters={field: ["in", values]}, pluck="name", limit_page_length=0)
        if names:
            records[dt] = [_plain(frappe.get_doc(dt, n)) for n in names]
    return records


def _comment(org, text):
    try:
        frappe.get_doc({"doctype": "Comment", "comment_type": "Info", "reference_doctype": ORG,
                        "reference_name": org, "content": text}).insert(ignore_permissions=True)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "org backup comment")


def _make_backup(org, label="manual"):
    records = _collect(org)
    now = datetime.datetime.now()
    counts = {dt: len(rows) for dt, rows in records.items()}
    payload = {"format": FORMAT, "organization": org, "title": frappe.db.get_value(ORG, org, "title"),
               "label": label, "created_at": now.isoformat(timespec="seconds"), "created_by": frappe.session.user,
               "counts": counts, "records": records}
    raw = gzip.compress(json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8"))
    fname = "%s%s-%s-%s.json.gz" % (PREFIX, org.replace(":", "_").replace("/", "_")[:60], now.strftime("%Y%m%d-%H%M%S"), label)
    f = frappe.get_doc({"doctype": "File", "file_name": fname, "attached_to_doctype": ORG, "attached_to_name": org,
                        "is_private": 1, "content": raw})
    f.flags.ignore_permissions = True
    f.insert(ignore_permissions=True)
    total = sum(counts.values())
    _comment(org, "Backup data organisasi (%s) dibuat oleh %s: %d catatan." % (label, frappe.session.user, total))
    return {"file": f.name, "file_name": fname, "records": total, "counts": counts, "size": len(raw)}


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=10, seconds=600)
def backup_organisasi(organization):
    _require_admin(organization)
    return _make_backup(organization, "manual")


@frappe.whitelist()
def daftar_backup(organization):
    _require_admin(organization)
    rows = frappe.get_all("File", filters={"attached_to_doctype": ORG, "attached_to_name": organization,
                                           "file_name": ["like", PREFIX + "%"]},
                          fields=["name", "file_name", "file_size", "creation"], order_by="creation desc",
                          limit_page_length=50)
    log = frappe.get_all("Comment", filters={"reference_doctype": ORG, "reference_name": organization,
                                             "comment_type": "Info", "content": ["like", "%data organisasi%"]},
                         fields=["content", "creation"], order_by="creation desc", limit_page_length=20)
    return {"backups": [{"file": r.name, "file_name": r.file_name, "size": r.file_size, "created": str(r.creation)[:19]}
                        for r in rows],
            "log": [{"text": frappe.utils.strip_html(c.content), "at": str(c.creation)[:19]} for c in log]}


@frappe.whitelist()
def unduh_backup(organization, file):
    _require_admin(organization)
    f = frappe.get_doc("File", file)
    if f.attached_to_doctype != ORG or f.attached_to_name != organization or not (f.file_name or "").startswith(PREFIX):
        frappe.throw("Berkas backup tidak ditemukan.", frappe.DoesNotExistError)
    frappe.local.response.filename = f.file_name
    frappe.local.response.filecontent = f.get_content()
    frappe.local.response.type = "download"


# ---- restore ---------------------------------------------------------------------------------------------------
def _load(organization, file=None, content_base64=None):
    if file:
        f = frappe.get_doc("File", file)
        if f.attached_to_doctype != ORG or f.attached_to_name != organization or not (f.file_name or "").startswith(PREFIX):
            frappe.throw("Berkas backup tidak ditemukan.", frappe.DoesNotExistError)
        raw = f.get_content()
    elif content_base64:
        if len(content_base64) > MAX_UPLOAD * 4 // 3 + 16:
            frappe.throw("Berkas terlalu besar.")
        raw = base64.b64decode(content_base64.split(",", 1)[-1])
    else:
        frappe.throw("Pilih backup yang akan dipulihkan.")
    if isinstance(raw, str):
        raw = raw.encode("latin-1")
    try:
        data = json.loads(gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw)
    except Exception:
        frappe.throw("Berkas bukan backup organisasi Rescue-Net yang sah.")
    if not isinstance(data, dict) or data.get("format") != FORMAT or not isinstance(data.get("records"), dict):
        frappe.throw("Berkas bukan backup organisasi Rescue-Net yang sah.")
    if data.get("organization") != organization:
        frappe.throw("Backup ini milik organisasi lain; tidak bisa dipulihkan ke sini.")
    return data


def _clean(d):
    out = {k: v for k, v in d.items() if k not in META_SKIP}
    for k, v in list(out.items()):
        if isinstance(v, list):
            out[k] = [{ck: cv for ck, cv in (c or {}).items() if ck not in META_SKIP} if isinstance(c, dict) else c for c in v]
    return out


def _same(doc, d):
    cur = _plain(doc)
    return all(json.dumps(cur.get(k), default=str, sort_keys=True) == json.dumps(v, default=str, sort_keys=True)
               for k, v in d.items() if k not in ("name", "doctype"))


def _save(dt, d):
    """Kembalikan satu catatan: 'sama' | 'dipulihkan' | 'dibuat'."""
    name = d.get("name")
    clean = _clean(d)
    clean["doctype"] = dt
    if frappe.db.exists(dt, name):
        doc = frappe.get_doc(dt, name)
        if _same(doc, clean):
            return "sama"
        doc.update(clean)
        for flag in ("ignore_validate", "ignore_links", "ignore_mandatory", "ignore_permissions"):
            setattr(doc.flags, flag, True)
        doc.save(ignore_permissions=True)
        return "dipulihkan"
    doc = frappe.get_doc(clean)
    for flag in ("ignore_validate", "ignore_links", "ignore_mandatory", "ignore_permissions"):
        setattr(doc.flags, flag, True)
    doc.insert(ignore_permissions=True, ignore_links=True, ignore_mandatory=True, set_name=name)
    return "dibuat"


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=5, seconds=600)
def pulihkan_organisasi(organization, file=None, content_base64=None, hapus_baru=0):
    _require_admin(organization)
    data = _load(organization, file, content_base64)
    recs = data["records"]
    hapus_baru = str(hapus_baru).lower() in ("1", "true", "yes", "on")
    before = _make_backup(organization, "sebelum-pulihkan")  # aturan 3

    # posko yang sah = posko di backup yang memang milik organisasi ini, dan kini tidak dimiliki organisasi lain
    posko_ok = set()
    for p in recs.get(POSKO) or []:
        cur_org = frappe.db.get_value(POSKO, p.get("name"), "organization")
        if p.get("organization") == organization and cur_org in (None, organization):
            posko_ok.add(p.get("name"))
    posko_ok |= set(_org_poskos(organization))
    types = {dt: (kind, field) for dt, kind, field in _doctypes()}

    hasil = {"sama": 0, "dipulihkan": 0, "dibuat": 0, "dihapus": 0, "dilewati": 0, "gagal": 0}
    gagal = []
    frappe.flags.in_import = True
    try:
        order = [ORG, POSKO] + sorted(dt for dt in recs if dt not in (ORG, POSKO))
        for dt in order:
            rows = recs.get(dt) or []
            if dt == ORG:
                check = lambda d: d.get("name") == organization
            elif dt == POSKO:
                check = lambda d: d.get("name") in posko_ok
            elif dt in types:
                kind, field = types[dt]
                allowed = {organization} if kind == "org" else posko_ok

                def check(d, field=field, allowed=allowed, dt=dt):
                    if d.get(field) not in allowed:
                        return False
                    cur = frappe.db.get_value(dt, d.get("name"), field) if frappe.db.exists(dt, d.get("name")) else None
                    return cur in (None,) or cur in allowed
            else:
                hasil["dilewati"] += len(rows)
                continue
            for d in rows:
                if not isinstance(d, dict) or not d.get("name") or not check(d):
                    hasil["dilewati"] += 1
                    continue
                try:
                    hasil[_save(dt, d)] += 1
                except Exception as e:
                    hasil["gagal"] += 1
                    gagal.append("%s %s: %s" % (dt, d.get("name"), str(e)[:120]))
        if hapus_baru:  # aturan 4: hanya bila dicentang; catatan anak dulu, posko terakhir
            for dt, kind, field in _doctypes():
                keep = {d.get("name") for d in recs.get(dt) or [] if isinstance(d, dict)}
                values = [organization] if kind == "org" else list(posko_ok)
                if not values:
                    continue
                for n in frappe.get_all(dt, filters={field: ["in", values]}, pluck="name", limit_page_length=0):
                    if n in keep:
                        continue
                    try:
                        frappe.delete_doc(dt, n, ignore_permissions=True, force=True)
                        hasil["dihapus"] += 1
                    except Exception as e:
                        hasil["gagal"] += 1
                        gagal.append("hapus %s %s: %s" % (dt, n, str(e)[:120]))
    finally:
        frappe.flags.in_import = False
    _comment(organization, "Pulihkan data organisasi dari backup %s oleh %s: %s." % (
        data.get("created_at"), frappe.session.user, ", ".join("%s %d" % (k, v) for k, v in hasil.items())))
    return {"hasil": hasil, "gagal": gagal[:50], "backup_sebelumnya": before["file_name"],
            "dari_backup": data.get("created_at")}
