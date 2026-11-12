"""Ekspor format standar (2026-10-26, rencana pembenahan tahap 3) so other
systems (BNPB, PBB/OCHA, Palang Merah, aplikasi peringatan) can read RN:

- CAP 1.2 (OASIS Common Alerting Protocol): earthquake warnings RN received
  from BMKG — `cap_alerts` (Atom feed) and `cap_alert` (one CAP document).
- HXL (Humanitarian Exchange Language): the public needs board as CSV with a
  hashtag row — `hxl_needs`.

Guest-safe: only what the public pages already show."""

import csv
import io
from xml.sax.saxutils import escape

import frappe
from frappe.rate_limiter import rate_limit
from werkzeug.wrappers import Response

SENDER = "rescue-net.online"
_BASE = "https://rescue-net.online/rescue-net-frappe/api/method/rescue_net.api_export."


def _utc(dt):
    # RN Early Warning times are stored in UTC (BMKG DateTime)
    return str(dt).replace(" ", "T")[:19] + "+00:00" if dt else ""


def _active_warnings(limit=20):
    from rescue_net.api_early_warning import _now_utc
    return frappe.get_all(
        "RN Early Warning",
        filters={"status": ["!=", "dismissed"], "meets_threshold": 1, "expires_at": [">", _now_utc()]},
        fields=["name", "identifier", "title", "area_desc", "potential", "latitude", "longitude",
                "magnitude", "depth_km", "issued_at", "expires_at", "severity", "source"],
        order_by="issued_at desc", limit_page_length=limit, ignore_permissions=True)


def _cap_xml(w):
    from rescue_net.services.early_warning import radius_km
    mag = float(w.magnitude or 0)
    severity = "Extreme" if mag >= 7 else "Severe" if mag >= 6 else "Moderate"
    desc = " ".join(x for x in [w.area_desc or "", ("Kedalaman %g km." % w.depth_km) if w.depth_km else "",
                                w.potential or ""] if x).strip()
    circle = ""
    if w.latitude is not None and w.longitude is not None:
        circle = "<circle>%s,%s %s</circle>" % (w.latitude, w.longitude, radius_km(mag))
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">'
        "<identifier>RN-EW-%s</identifier><sender>%s</sender><sent>%s</sent>"
        "<status>Actual</status><msgType>Alert</msgType><scope>Public</scope>"
        "<note>Diteruskan Rescue-Net dari BMKG; belum diverifikasi Rescue-Net.</note>"
        "<info><language>id-ID</language><category>Geo</category><event>Gempa bumi</event>"
        "<urgency>Immediate</urgency><severity>%s</severity><certainty>Observed</certainty>"
        "<senderName>Rescue-Net (sumber: BMKG data.bmkg.go.id)</senderName>"
        "<headline>%s</headline><description>%s</description>"
        "<web>https://rescue-net.online/rescue-net/pages/bencana-aktif.html</web>"
        "<parameter><valueName>magnitude</valueName><value>%s</value></parameter>"
        "<expires>%s</expires>"
        "<area><areaDesc>%s</areaDesc>%s</area></info></alert>"
    ) % (escape(w.name), SENDER, _utc(w.issued_at), severity, escape(w.title or "Gempa"), escape(desc),
         mag, _utc(w.expires_at), escape(w.area_desc or "Indonesia"), circle)


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=120, seconds=60)
def cap_alert(name):
    rows = [w for w in _active_warnings(100) if w.name == name]
    if not rows:
        frappe.throw("Peringatan tidak ditemukan atau sudah kedaluwarsa.", frappe.DoesNotExistError)
    return Response(_cap_xml(rows[0]), mimetype="application/cap+xml")


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=120, seconds=60)
def cap_alerts():
    """Atom feed of the active earthquake warnings, each entry linking its CAP document."""
    from rescue_net.api_early_warning import _now_utc
    entries = "".join(
        "<entry><id>RN-EW-%s</id><title>%s</title><updated>%s</updated>"
        '<link rel="alternate" type="application/cap+xml" href="%scap_alert?name=%s"/></entry>'
        % (escape(w.name), escape(w.title or "Gempa"), _utc(w.issued_at), _BASE, escape(w.name))
        for w in _active_warnings())
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n<feed xmlns="http://www.w3.org/2005/Atom">'
           "<id>%scap_alerts</id><title>Rescue-Net: peringatan gempa (CAP)</title><updated>%s</updated>%s</feed>"
           % (_BASE, _utc(_now_utc()), entries))
    return Response(xml, mimetype="application/atom+xml")


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=60, seconds=60)
def hxl_needs(disaster_event):
    """Public needs board as HXL CSV (header row + hashtag row)."""
    from rescue_net.api_public_needs import board
    b = board(event=disaster_event) or {}
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["Posko", "Kode posko", "Wilayah", "Barang", "Satuan", "Kekurangan", "Kritis", "Diperbarui"])
    w.writerow(["#loc+name", "#loc+code", "#adm2+name", "#item+name", "#item+unit", "#need+num", "#status+critical", "#date+updated"])
    for n in b.get("needs") or []:
        w.writerow([n.get("posko_title") or "", n.get("posko") or "", n.get("region") or "", n.get("item") or "",
                    n.get("unit") or "", n.get("gap") if n.get("gap") is not None else "",
                    "ya" if n.get("critical") else "tidak", str(n.get("updated_at") or "")[:19]])
    resp = Response(out.getvalue(), mimetype="text/csv")
    resp.headers["Content-Disposition"] = 'inline; filename="rescue-net-kebutuhan-hxl.csv"'
    return resp


# ---------------------------------------------------------------------------------------------------------
# SITREP untuk sistem lain (owner 2026-11-12: "lengkapi dengan API protokol untuk pelaporan ini" + "berikan button
# berikan api key untuk sitrep itu"). Autentikasi = kunci API bawaan Frappe:
#   Authorization: token <api_key>:<api_secret>
# Kunci dibuat lewat tombol "Buat API key" di halaman SITREP (super admin / admin organisasi).
# Format: JSON (lengkap), EDXL-SitRep 1.0 (OASIS, struktur dasar), HXL CSV (angka kunci). Isi = SITREP publik.
# ---------------------------------------------------------------------------------------------------------

def _need_login():
    if frappe.session.user in (None, "", "Guest"):
        frappe.throw("Perlu kunci API (Authorization: token <api_key>:<api_secret>) atau login.", frappe.AuthenticationError)


def _sitrep_data(disaster_event, hours):
    from rescue_net.api_sitrep import sitrep
    return sitrep(disaster_event, hours)


@frappe.whitelist()
@rate_limit(limit=60, seconds=60)
def sitrep_json(disaster_event, hours=24):
    """SITREP lengkap (JSON) untuk sistem lain."""
    _need_login()
    d = _sitrep_data(disaster_event, hours)
    d["format"] = "rescue-net-sitrep/1"
    d["sumber"] = "https://rescue-net.online/rescue-net/pages/sitrep.html?event=%s" % d["bencana"]["id"]
    return d


def _iso_local(s):
    s = str(s or "")[:16]
    return (s.replace(" ", "T") + ":00+07:00") if s else ""


@frappe.whitelist()
@rate_limit(limit=60, seconds=60)
def sitrep_edxl(disaster_event, hours=24):
    """SITREP sebagai XML berstruktur OASIS EDXL-SitRep 1.0 (laporan SituationInformation + ringkasan korban).
    Catatan: struktur dasar mengikuti EDXL-SitRep 1.0; belum divalidasi terhadap skema XSD resmi OASIS."""
    _need_login()
    d = _sitrep_data(disaster_event, hours)
    s = d.get("situasi") or {}
    b = d.get("bencana") or {}
    sev = {"critical": "Extreme", "high": "Severe", "medium": "Moderate", "low": "Minor"}.get(str(b.get("severity") or "").lower(), "Unknown")
    highlights = "".join("<KeyMessage>%s</KeyMessage>" % escape(h) for h in d.get("highlights") or [])
    sektor = "".join(
        "<SectorReport><Sector>%s</Sector><NeedsCount>%s</NeedsCount><CriticalCount>%s</CriticalCount>"
        "<Response>%s</Response><Gaps>%s</Gaps></SectorReport>"
        % (escape(x.get("nama") or ""), x.get("kebutuhan") or 0, x.get("kritis") or 0, escape(x.get("respons") or ""),
           escape("; ".join(x.get("kesenjangan") or [])))
        for x in d.get("sektor") or [])
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<SitRep xmlns="urn:oasis:names:tc:emergency:edxl:sitrep:1.0">'
        "<MessageID>RN-SITREP-%s-%s</MessageID>"
        "<PreparedBy><OrganizationName>Rescue-Net (rescue-net.online)</OrganizationName></PreparedBy>"
        "<ReportPurpose>Laporan situasi otomatis dari data posko Rescue-Net</ReportPurpose>"
        "<ReportNumber>%s</ReportNumber><ReportVersion>Update</ReportVersion>"
        "<ForTimePeriod><FromDateTime>%s</FromDateTime><ToDateTime>%s</ToDateTime></ForTimePeriod>"
        "<IncidentID>%s</IncidentID><IncidentName>%s</IncidentName><IncidentLifecyclePhase>%s</IncidentLifecyclePhase>"
        "<Severity>%s</Severity><ReportConfidence>Unsure</ReportConfidence>"
        "<SituationInformation>%s"
        "<CasualtyAndIllnessSummary><AffectedPersons>%s</AffectedPersons><MissingPersons>%s</MissingPersons>"
        "<DisplacedPersons>%s</DisplacedPersons></CasualtyAndIllnessSummary>"
        "<ResourceSummary><ActiveFacilities>%s</ActiveFacilities><CriticalFacilities>%s</CriticalFacilities>"
        "<OpenNeeds>%s</OpenNeeds><Volunteers>%s</Volunteers></ResourceSummary>%s"
        "<NextReport>%s</NextReport></SituationInformation></SitRep>"
    ) % (escape(b.get("id") or ""), escape(str(d.get("nomor") or 1)), d.get("nomor") or 1,
         _iso_local(d["periode"]["dari"]), _iso_local(d["periode"]["sampai"]), escape(b.get("id") or ""),
         escape(b.get("title") or ""), escape(b.get("status") or "active"), sev, highlights,
         s.get("jiwa_terdampak") or 0, s.get("orang_hilang") or 0, s.get("pengungsi_shelter") or 0,
         s.get("posko_aktif") or 0, s.get("posko_kritis") or 0, s.get("kebutuhan_terbuka") or 0, s.get("relawan") or 0,
         sektor, _iso_local(d.get("laporan_berikutnya")))
    return Response(xml, mimetype="application/xml")


@frappe.whitelist()
@rate_limit(limit=60, seconds=60)
def sitrep_hxl(disaster_event, hours=24):
    """Angka kunci SITREP sebagai HXL CSV (satu baris per angka)."""
    _need_login()
    d = _sitrep_data(disaster_event, hours)
    s = d.get("situasi") or {}
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["Bencana", "Indikator", "Nilai", "Periode sampai"])
    w.writerow(["#crisis+code", "#indicator+name", "#indicator+value+num", "#date+reported"])
    for label, val in (("affected", s.get("jiwa_terdampak")), ("missing", s.get("orang_hilang")),
                       ("displaced_in_shelter", s.get("pengungsi_shelter")), ("facilities_active", s.get("posko_aktif")),
                       ("facilities_critical", s.get("posko_kritis")), ("needs_open", s.get("kebutuhan_terbuka")),
                       ("volunteers", s.get("relawan"))):
        w.writerow([d["bencana"]["id"], label, val if val is not None else "", d["periode"]["sampai"]])
    resp = Response(out.getvalue(), mimetype="text/csv")
    resp.headers["Content-Disposition"] = 'inline; filename="rescue-net-sitrep-hxl.csv"'
    return resp


# Owner 2026-11-12: "api key aproval super admin bagushandhoko@gmail.com" -> admin organisasi hanya MEMINTA kunci;
# super admin pemberi persetujuan menyetujui (atau membuat langsung) dan menerima rahasia untuk diteruskan.
KUNCI_APPROVER = "bagushandhoko@gmail.com"
_TODO_TAG = "[API-SITREP]"


def _is_approver():
    u = frappe.session.user
    if frappe.db.exists("User", KUNCI_APPROVER):
        return u == KUNCI_APPROVER
    from rescue_net.access_policy import is_system_manager
    return bool(is_system_manager())  # cadangan bila akun pemberi persetujuan tidak ada


def _org_admin():
    """(org, allowed) untuk admin organisasi yang login."""
    from rescue_net.access_policy import rn_actor
    actor = rn_actor(required=False) or {}
    org = actor.get("organization")
    if not org:
        return None, False
    try:
        from rescue_net.access_policy import can_manage_organization
        return org, bool(can_manage_organization(actor, org))
    except Exception:
        return org, False


def _issue_key(owner, by):
    import re as _re
    slug = _re.sub(r"[^a-z0-9]+", "-", str(owner).lower()).strip("-")[:40] or "umum"
    email = "api-sitrep-%s@rescue-net.local" % slug
    if not frappe.db.exists("User", email):
        u = frappe.get_doc({"doctype": "User", "email": email, "first_name": ("API SITREP " + str(owner))[:60],
                            "user_type": "Website User", "send_welcome_email": 0, "enabled": 1})
        u.flags.ignore_permissions = True
        u.flags.no_welcome_mail = True
        u.insert(ignore_permissions=True)
    u = frappe.get_doc("User", email)
    key, secret = frappe.generate_hash(length=15), frappe.generate_hash(length=15)
    u.api_key = key
    u.api_secret = secret
    u.enabled = 1
    u.flags.ignore_permissions = True
    u.save(ignore_permissions=True)
    try:
        u.add_comment("Info", "Kunci API SITREP diterbitkan/disetujui oleh %s" % by)
    except Exception:
        pass
    base = "https://rescue-net.online/rescue-net-frappe/api/method/rescue_net.api_export."
    return {"api_key": key, "api_secret": secret, "pengguna_api": email, "untuk": owner,
            "header": "Authorization: token %s:%s" % (key, secret),
            "endpoint": {"json": base + "sitrep_json?disaster_event=<id>&hours=24",
                         "edxl_sitrep": base + "sitrep_edxl?disaster_event=<id>&hours=24",
                         "hxl": base + "sitrep_hxl?disaster_event=<id>&hours=24"},
            "catatan": "Simpan rahasia ini sekarang; tidak bisa ditampilkan lagi. Kunci baru membatalkan kunci lama organisasi itu."}


@frappe.whitelist()
def status_kunci_api_sitrep():
    """Untuk tombol di halaman SITREP: peran penanya + permintaan yang menunggu (hanya untuk pemberi persetujuan)."""
    if frappe.session.user in (None, "", "Guest"):
        return {"login": False}
    appr = _is_approver()
    org, admin = _org_admin()
    out = {"login": True, "pemberi_persetujuan": appr, "admin_organisasi": admin, "organisasi": org,
           "approver": KUNCI_APPROVER, "permintaan": [], "menunggu_saya": False}
    if appr:
        out["permintaan"] = frappe.get_all("ToDo", filters={"status": "Open", "description": ["like", _TODO_TAG + "%"]},
                                           fields=["name", "description", "owner", "creation", "reference_name"],
                                           order_by="creation desc", limit_page_length=50, ignore_permissions=True)
    if org:
        out["menunggu_saya"] = bool(frappe.db.exists("ToDo", {"status": "Open", "reference_type": "RN Organization",
                                                             "reference_name": org, "description": ["like", _TODO_TAG + "%"]}))
    return out


@frappe.whitelist(methods=["POST"])
def minta_kunci_api_sitrep(alasan=None):
    """Admin organisasi meminta kunci API SITREP -> tugas (ToDo) untuk super admin pemberi persetujuan."""
    if frappe.session.user in (None, "", "Guest"):
        frappe.throw("Login dulu.", frappe.AuthenticationError)
    org, admin = _org_admin()
    if not admin:
        frappe.throw("Permintaan kunci API hanya untuk admin organisasi.", frappe.PermissionError)
    if frappe.db.exists("ToDo", {"status": "Open", "reference_type": "RN Organization", "reference_name": org,
                                 "description": ["like", _TODO_TAG + "%"]}):
        return {"ok": True, "pesan": "Permintaan organisasi Anda sudah ada dan menunggu persetujuan super admin."}
    title = frappe.db.get_value("RN Organization", org, "title") or org
    t = frappe.get_doc({"doctype": "ToDo", "allocated_to": KUNCI_APPROVER, "status": "Open", "priority": "Medium",
                        "reference_type": "RN Organization", "reference_name": org,
                        "description": "%s Permintaan kunci API SITREP untuk organisasi %s oleh %s. Alasan: %s"
                                       % (_TODO_TAG, title, frappe.session.user, str(alasan or "-")[:300])})
    t.insert(ignore_permissions=True)
    return {"ok": True, "pesan": "Permintaan terkirim ke super admin (%s). Kunci akan diberikan setelah disetujui." % KUNCI_APPROVER}


@frappe.whitelist(methods=["POST"])
def setujui_kunci_api_sitrep(todo):
    """Super admin menyetujui permintaan -> kunci untuk organisasi peminta (rahasia tampil sekali, diteruskan manual)."""
    if not _is_approver():
        frappe.throw("Hanya super admin %s yang bisa menyetujui kunci API." % KUNCI_APPROVER, frappe.PermissionError)
    t = frappe.get_doc("ToDo", todo)
    if not str(t.description or "").startswith(_TODO_TAG) or t.status != "Open":
        frappe.throw("Permintaan tidak ditemukan atau sudah diproses.")
    out = _issue_key(t.reference_name or t.owner, frappe.session.user)
    out["peminta"] = t.owner
    t.status = "Closed"
    t.flags.ignore_permissions = True
    t.save(ignore_permissions=True)
    return out


@frappe.whitelist(methods=["POST"])
def buat_kunci_api_sitrep():
    """Super admin pemberi persetujuan membuat kunci langsung (untuk dirinya / mitra). Admin organisasi: pakai minta_."""
    if frappe.session.user in (None, "", "Guest"):
        frappe.throw("Login dulu.", frappe.AuthenticationError)
    if not _is_approver():
        frappe.throw("Kunci API SITREP dibuat/disetujui oleh super admin %s. Admin organisasi: tekan \"Minta API key\"."
                     % KUNCI_APPROVER, frappe.PermissionError)
    return _issue_key("super-admin", frappe.session.user)
