"""Alat Komunikasi — inventory, connectivity, operators, power/battery and
frequency status for a disaster event.

Matches `assets/img/mockup/alat komunikasi.png` and the DMS blueprint's
Management Posko "sarana posko (komunikasi …)". Built on three real doctypes
(`RN Comms Device`, `RN Comms Operator`, `RN Comms Frequency`) plus two
optional `RN Posko` custom fields (`rn_comms_status`, `rn_comms_last_contact`);
when the posko fields are absent connectivity is derived from device rows so
the board still works.

`comms_board` is guest read-only. Writes require login and are gated the same
way as every other create_* endpoint in the app (any authenticated RN actor).
"""

import re

import frappe
from frappe.rate_limiter import rate_limit
from frappe.utils import now_datetime

from rescue_net.reference_resolver import resolve_disaster_event, resolve_posko
from rescue_net.access_policy import rn_actor


# --- category / status labels --------------------------------------------------

_CATEGORY_ORDER = [
    "ht", "repeater", "telepon_satelit", "starlink",
    "vsat", "router_4g5g", "antena_mast",
]
_CATEGORY_LABELS = {
    "ht": "Handy Talky (HT)",
    "repeater": "Repeater Radio",
    "telepon_satelit": "Telepon Satelit",
    "starlink": "Starlink Terminal",
    "vsat": "VSAT Terminal",
    "router_4g5g": "Router 4G/5G",
    "antena_mast": "Antena / Mast",
}
_DEVICE_STATUS_LABEL = {
    "active": "Aktif",
    "spare": "Cadangan",
    "inactive": "Tidak Aktif",
    "needs_attention": "Perlu Perhatian",
}
_OPERATOR_ROLE_LABEL = {
    "koordinator_radio": "Koordinator Radio",
    "operator": "Operator",
    "teknisi": "Teknisi",
}
_OPERATOR_STATUS_LABEL = {
    "online": "Online", "siaga": "Siaga",
    "istirahat": "Istirahat", "offline": "Offline",
}
_NETWORK_LABEL = {
    "vhf": "VHF", "uhf": "UHF", "hf": "HF", "seluler": "Seluler",
    "starlink": "Starlink", "vsat": "VSAT", "lainnya": "Lainnya",
}
_FREQ_STATUS_LABEL = {
    "baik": "Baik", "sibuk": "Sibuk", "lemah": "Lemah", "down": "Terputus",
}
_CONN_LABEL = {
    "connected": "Terhubung", "weak": "Koneksi Lemah",
    "disconnected": "Tidak Terhubung", "unknown": "Belum Terdata",
}

# categories that do not run on an internal battery
_NON_BATTERY_CATEGORIES = {"antena_mast", "vsat"}

# internet-in-a-box categories used for the "Internet Darurat" KPI
_INTERNET_CATEGORIES = {"starlink", "vsat", "router_4g5g"}

_BATTERY_CRITICAL = 20  # percent


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


_CONTACT_FIELDS = (
    "officer_in_charge_name", "officer_in_charge_role", "officer_in_charge_phone",
    "officer_in_charge_whatsapp", "officer_in_charge_email", "emergency_contact",
)


def _posko_contact(p, actor):
    """Posko phone / WhatsApp / email for this public board — same rule as posko_detail:
    only when the viewer may see the posko in "full" share mode, otherwise None."""
    from rescue_net.visibility import posko_contacts_visible

    if not posko_contacts_visible(p.name, actor):
        return None
    out = {
        "name": p.get("officer_in_charge_name") or "",
        "role": p.get("officer_in_charge_role") or "",
        "phone": p.get("officer_in_charge_phone") or "",
        "whatsapp": p.get("officer_in_charge_whatsapp") or "",
        "email": p.get("officer_in_charge_email") or "",
        "emergency": p.get("emergency_contact") or "",
    }
    # a name with no way to reach it is not a contact
    return out if any(out[k] for k in ("phone", "whatsapp", "email", "emergency")) else None


_FREQ_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(khz|mhz|ghz)", re.I)
_CHAN_RE = re.compile(r"\b(?:ch|chan(?:nel)?|kanal)\s*[-.:]?\s*(\w+)", re.I)


def _split_radio(value):
    """'146.020 MHz / CH 01' -> ('146.020 MHz', 'CH 01'); 'CH 03' -> ('', 'CH 03'); '-' -> ('', '')."""
    text = (value or "").strip()
    m, c = _FREQ_RE.search(text), _CHAN_RE.search(text)
    freq = (m.group(1).replace(",", ".") + " " + {"khz": "kHz", "mhz": "MHz", "ghz": "GHz"}[m.group(2).lower()]) if m else ""
    chan = ("CH " + c.group(1)) if c else ""
    return freq, chan


def _fmt_mhz(value):
    """'146.020', '146,02 MHz' -> '146.020 MHz'; anything that is not a plausible 0.1-3000 MHz value -> ''."""
    m = re.search(r"\d+(?:[.,]\d+)?", str(value or ""))
    if not m:
        return ""
    n = float(m.group(0).replace(",", "."))
    return ("%.3f MHz" % n) if 0.1 <= n <= 3000 else ""


def _radio_kind(mhz):
    n = float((mhz or "0").split()[0] or 0)
    return "HF" if n < 30 else ("VHF" if n < 300 else "UHF")


_INTERNET_HOW = "Internet tersedia — bisa lewat WhatsApp / email / video call"


def _posko_methods(p, actor, devices, contact):
    """Every way to reach a posko, one list: PIC phone / WhatsApp / email / emergency (only when the viewer
    may see the posko in full share mode), radio with frequency + channel + call sign, satellite phone,
    internet terminals. Inactive gear is not listed."""
    out = []
    if contact:
        if contact["phone"]:
            out.append({"type": "telepon", "label": "Telepon" + (" " + contact["name"] if contact["name"] else ""),
                        "value": contact["phone"], "href": "tel:" + re.sub(r"[^\d+]", "", contact["phone"])})
        if contact["whatsapp"]:
            num = re.sub(r"\D", "", contact["whatsapp"])
            num = "62" + num[1:] if num.startswith("0") else num
            out.append({"type": "wa", "label": "WhatsApp", "value": contact["whatsapp"], "href": "https://wa.me/" + num})
        if contact["email"]:
            out.append({"type": "email", "label": "Email", "value": contact["email"], "href": "mailto:" + contact["email"]})
        if contact["emergency"]:
            out.append({"type": "darurat", "label": "Kontak darurat", "value": contact["emergency"]})
    seen = set()
    for d in devices:
        if d.posko != p.name or d.status not in ("active", "spare"):
            continue
        freq, chan = _split_radio(d.frequency_channel)
        if d.get("frequency_mhz"):
            freq = _fmt_mhz(d.frequency_mhz) or freq
        cid = (d.get("contact_id") or "").strip()
        if d.category in ("ht", "repeater"):
            kind = _radio_kind(freq) + " " if freq else ""
            label = (("Repeater " if d.category == "repeater" else "Radio HT ") + kind.strip()).strip()
            value = " · ".join(x for x in (freq or "frekuensi belum diisi", chan, ("call sign " + cid) if cid else "") if x)
            key = ("radio", freq, chan, cid)
        elif d.category == "telepon_satelit":
            if not contact:  # a satellite number is a phone number: same visibility rule as the PIC's
                cid = ""
            label, value, key = "Telepon satelit", cid or "nomor belum diisi / tidak dibagikan", ("sat", cid)
        elif d.category in ("starlink", "vsat", "router_4g5g"):
            label, value, key = _CATEGORY_LABELS.get(d.category, d.category), _INTERNET_HOW, ("net", d.category)
        else:
            continue
        if key in seen:
            continue
        seen.add(key)
        out.append({"type": key[0], "label": label, "value": value, "device": d.device_name})
    return out


def _posko_location(p):
    lat, lng = p.get("latitude"), p.get("longitude")
    has = lat not in (None, "") and lng not in (None, "") and (float(lat) or float(lng))
    admin = ", ".join(x for x in (p.get("village_name"), p.get("district_name"),
                                  p.get("city_name"), p.get("province_name")) if x)
    return {
        "address": p.get("address") or "",
        "area": admin,
        "lat": float(lat) if has else None,
        "lng": float(lng) if has else None,
    }


def _posko_has_comms_fields():
    meta = frappe.get_meta("RN Posko")
    return meta.has_field("rn_comms_status")


def _drill(title, sub=None, href=None):
    return {"title": title, "sub": sub, "href": href}


# --- board -------------------------------------------------------------------

@frappe.whitelist(allow_guest=True)
@rate_limit(limit=120, seconds=60)
def comms_board(disaster_event=None):
    event = resolve_disaster_event(disaster_event)
    ev_q = (event or "")
    dfilt = {"disaster_event": event} if event else {}

    devices = frappe.get_all(
        "RN Comms Device",
        filters=dfilt,
        fields=[
            "name", "device_name", "category", "status", "battery_pct",
            "frequency_channel", "frequency_mhz", "contact_id", "current_location", "posko", "owner_type",
            "owner_id", "notes", "observed_at",
        ],
        order_by="category asc, device_name asc",
        limit_page_length=3000,
    )

    operators = frappe.get_all(
        "RN Comms Operator",
        filters=dfilt,
        fields=[
            "name", "operator_name", "role", "channel", "status",
            "contact_phone", "skills", "posko", "shift_note", "observed_at",
        ],
        order_by="modified desc",
        limit_page_length=1000,
    )

    frequencies = frappe.get_all(
        "RN Comms Frequency",
        filters=dfilt,
        fields=[
            "name", "band_label", "network_type", "frequency_value",
            "provider", "status", "load_pct", "notes", "observed_at",
        ],
        order_by="network_type asc, band_label asc",
        limit_page_length=500,
    )

    # ---- poskos for this event (connectivity) ----
    posko_fields = ["name", "title", "latitude", "longitude", "address", "province_name",
                    "city_name", "district_name", "village_name",
                    "disaster_event", "disaster_event_legacy_id"]
    posko_fields += [f for f in _CONTACT_FIELDS if frappe.get_meta("RN Posko").has_field(f)]
    if _posko_has_comms_fields():
        posko_fields += ["rn_comms_status", "rn_comms_last_contact"]
    if event:
        poskos = frappe.get_all(
            "RN Posko",
            or_filters={"disaster_event": event, "disaster_event_legacy_id": event},
            fields=posko_fields, limit_page_length=2000,
        )
    else:
        poskos = frappe.get_all(
            "RN Posko", fields=posko_fields, limit_page_length=2000,
        )

    posko_title = {p.name: (p.get("title") or p.name) for p in poskos}

    # device rollups per posko (fallback connectivity signal)
    dev_by_posko = {}
    for d in devices:
        if not d.posko:
            continue
        b = dev_by_posko.setdefault(d.posko, {"active": 0, "attention": 0, "total": 0})
        b["total"] += 1
        if d.status == "active":
            b["active"] += 1
        if d.status in ("needs_attention", "inactive"):
            b["attention"] += 1

    def _conn_for(p):
        explicit = (p.get("rn_comms_status") or "").strip().lower()
        if explicit in _CONN_LABEL:
            return explicit
        roll = dev_by_posko.get(p.name)
        if not roll or roll["total"] == 0:
            # no explicit flag and no comms device on record -> not yet tracked,
            # NOT a confirmed outage (don't inflate the alarming KPIs)
            return "unknown"
        if roll["active"] == 0:
            return "disconnected"
        if roll["attention"] > 0:
            return "weak"
        return "connected"

    # radio per posko, straight from the devices it holds (no personal data). A real frequency
    # ("146.020 MHz") and a channel ("CH 01") are different things: split what the device row holds.
    radio_by_posko = {}
    for d in devices:
        freq, chan = _split_radio(d.frequency_channel)
        if d.get("frequency_mhz"):
            freq = _fmt_mhz(d.frequency_mhz) or freq
        if d.posko and (freq or chan):
            radio_by_posko.setdefault(d.posko, {}).setdefault((freq, chan), []).append(d.device_name)

    actor = rn_actor(required=False)

    konektivitas_poskos = []
    conn_count = {"connected": 0, "weak": 0, "disconnected": 0, "unknown": 0}
    for p in poskos:
        contact = _posko_contact(p, actor)
        c = _conn_for(p)
        conn_count[c] += 1
        konektivitas_poskos.append({
            "posko": p.name,
            "title": posko_title.get(p.name, p.name),
            "status": c,
            "status_label": _CONN_LABEL[c],
            "last_contact": p.get("rn_comms_last_contact") or "",
            "frequencies": [
                {"frequency": f, "channel": c, "devices": names}
                for (f, c), names in sorted(radio_by_posko.get(p.name, {}).items())
            ],
            "location": _posko_location(p),
            "contact": contact,
            "methods": _posko_methods(p, actor, devices, contact) or [{
                "type": "kosong",
                "label": ("Alat komunikasi ada tapi tidak aktif" if p.name in dev_by_posko
                          else "Belum ada alat komunikasi terdata"),
                "value": "Hubungi lewat Control Centre / koordinator posko"}],
            "lat": p.get("latitude"),
            "lng": p.get("longitude"),
            "href": "posko-detail.html?id=" + p.name + "&event=" + ev_q,
        })
    konektivitas_poskos.sort(
        key=lambda r: {"disconnected": 0, "weak": 1, "unknown": 2, "connected": 3}[r["status"]]
    )

    # ---- inventory per category ----
    cat_map = {}
    for d in devices:
        cat = d.category or "lainnya"
        row = cat_map.setdefault(cat, {
            "category": cat,
            "label": _CATEGORY_LABELS.get(cat, cat.replace("_", " ").title()),
            "total": 0, "aktif": 0, "cadangan": 0,
            "tidak_aktif": 0, "perlu_perhatian": 0,
        })
        row["total"] += 1
        if d.status == "active":
            row["aktif"] += 1
        elif d.status == "spare":
            row["cadangan"] += 1
        elif d.status == "inactive":
            row["tidak_aktif"] += 1
        elif d.status == "needs_attention":
            row["perlu_perhatian"] += 1
    inventory = sorted(
        cat_map.values(),
        key=lambda c: _CATEGORY_ORDER.index(c["category"])
        if c["category"] in _CATEGORY_ORDER else 99,
    )
    inventory_total = {
        "total": sum(c["total"] for c in inventory),
        "aktif": sum(c["aktif"] for c in inventory),
        "cadangan": sum(c["cadangan"] for c in inventory),
        "tidak_aktif": sum(c["tidak_aktif"] for c in inventory),
        "perlu_perhatian": sum(c["perlu_perhatian"] for c in inventory),
    }

    # ---- operators ----
    op_rows = []
    for o in operators:
        op_rows.append({
            "name": o.operator_name,
            "role": o.role,
            "role_label": _OPERATOR_ROLE_LABEL.get(o.role, o.role or "Operator"),
            "channel": o.channel or "-",
            "status": o.status or "siaga",
            "status_label": _OPERATOR_STATUS_LABEL.get(o.status, o.status or "Siaga"),
            "posko": posko_title.get(o.posko, o.posko or "-"),
            "contact": o.contact_phone or "",
            "skills": o.skills or "",
        })
    operator_active = sum(1 for o in operators if o.status in ("online", "siaga"))

    # ---- power / battery ----
    batt_rows = []
    for d in devices:
        # skip mains-powered gear and rows with no real reading (Int NULL -> 0)
        if d.category in _NON_BATTERY_CATEGORIES or not d.battery_pct:
            continue
        pct = int(_num(d.battery_pct))
        state = "kritis" if pct < _BATTERY_CRITICAL else ("waspada" if pct < 40 else "aman")
        batt_rows.append({
            "label": d.device_name,
            "category_label": _CATEGORY_LABELS.get(d.category, d.category or "-"),
            "posko": posko_title.get(d.posko, d.posko or "-"),
            "battery_pct": pct,
            "state": state,
            "href": "posko-detail.html?id=" + (d.posko or "") + "&event=" + ev_q,
        })
    batt_rows.sort(key=lambda r: r["battery_pct"])
    baterai_kritis = [b for b in batt_rows if b["state"] == "kritis"]

    # ---- frequencies ----
    freq_rows = []
    for f in frequencies:
        freq_rows.append({
            "band_label": f.band_label,
            "network_type": f.network_type,
            "network_label": _NETWORK_LABEL.get(f.network_type, f.network_type or "-"),
            "frequency_value": f.frequency_value or "",
            "provider": f.provider or "",
            "status": f.status or "baik",
            "status_label": _FREQ_STATUS_LABEL.get(f.status, f.status or "Baik"),
            "load_pct": int(_num(f.load_pct)) if f.load_pct is not None else None,
        })

    # ---- KPI counts ----
    alat_aktif = [d for d in devices if d.status == "active"]
    repeater_aktif = [d for d in devices if d.category == "repeater" and d.status == "active"]
    internet_poskos = sorted({
        d.posko for d in devices
        if d.category in _INTERNET_CATEGORIES and d.status == "active" and d.posko
    })
    internet_darurat_poskos = [
        p for p in konektivitas_poskos
        if p["status"] in ("disconnected", "weak") and p["posko"] not in internet_poskos
    ]
    operator_dibutuhkan = max(
        0,
        conn_count["disconnected"] + conn_count["weak"] - operator_active,
    )

    totals = {
        "alat_aktif": len(alat_aktif),
        "posko_tidak_terhubung": conn_count["disconnected"],
        "repeater_aktif": len(repeater_aktif),
        "internet_darurat_posko": len(internet_darurat_poskos),
        "operator_dibutuhkan": operator_dibutuhkan,
        "baterai_kritis": len(baterai_kritis),
        "konektivitas": conn_count,
        "operator_aktif": operator_active,
    }

    kpi_items = {
        "alat_aktif_items": [
            _drill(d.device_name,
                   _CATEGORY_LABELS.get(d.category, d.category) + " · "
                   + (posko_title.get(d.posko, d.posko or "-")),
                   "posko-detail.html?id=" + (d.posko or "") + "&event=" + ev_q)
            for d in alat_aktif[:40]
        ],
        "posko_tidak_terhubung_items": [
            _drill(p["title"], "Terakhir kontak: " + (str(p["last_contact"]) or "-"), p["href"])
            for p in konektivitas_poskos if p["status"] == "disconnected"
        ],
        "repeater_aktif_items": [
            _drill(d.device_name,
                   (d.frequency_channel or "-") + " · " + (posko_title.get(d.posko, d.posko or "-")),
                   "posko-detail.html?id=" + (d.posko or "") + "&event=" + ev_q)
            for d in repeater_aktif
        ],
        "internet_darurat_items": [
            _drill(p["title"], p["status_label"], p["href"])
            for p in internet_darurat_poskos
        ],
        "operator_dibutuhkan_items": [
            _drill(p["title"], p["status_label"] + " — belum ada operator siaga", p["href"])
            for p in konektivitas_poskos
            if p["status"] in ("disconnected", "weak")
        ],
        "baterai_kritis_items": [
            _drill(b["label"], b["category_label"] + " · " + str(b["battery_pct"]) + "% · " + b["posko"],
                   b["href"])
            for b in baterai_kritis
        ],
    }

    # ---- connectivity alerts ----
    peringatan = []
    for p in konektivitas_poskos:
        if p["status"] == "disconnected":
            peringatan.append({
                "title": p["title"],
                "tag": "Tidak Terhubung",
                "sub": "Tidak ada sinyal / laporan terakhir " + (str(p["last_contact"]) or "tidak diketahui"),
                "level": "critical",
                "time": str(p["last_contact"] or ""),
                "href": p["href"],
            })
    for p in konektivitas_poskos:
        if p["status"] == "weak":
            peringatan.append({
                "title": p["title"],
                "tag": "Koneksi Lemah",
                "sub": "Sinyal tidak stabil / kecepatan rendah",
                "level": "warning",
                "time": str(p["last_contact"] or ""),
                "href": p["href"],
            })
    for b in baterai_kritis:
        peringatan.append({
            "title": b["label"],
            "tag": "Baterai Kritis (" + str(b["battery_pct"]) + "%)",
            "sub": "Segera lakukan pengisian daya — " + b["posko"],
            "level": "critical",
            "time": "",
            "href": b["href"],
        })
    for f in freq_rows:
        if f["status"] in ("lemah", "down"):
            peringatan.append({
                "title": f["band_label"],
                "tag": f["status_label"],
                "sub": (f["provider"] or f["network_label"]) + " — periksa jaringan",
                "level": "warning" if f["status"] == "lemah" else "critical",
                "time": "",
                "href": None,
            })

    return {
        "disaster_event": event,
        "generated_at": now_datetime(),
        "totals": totals,
        "kpi_items": kpi_items,
        "inventory": inventory,
        "inventory_total": inventory_total,
        "konektivitas": {
            "terhubung": conn_count["connected"],
            "lemah": conn_count["weak"],
            "tidak_terhubung": conn_count["disconnected"],
            "belum_terdata": conn_count["unknown"],
            "poskos": konektivitas_poskos,
        },
        "operators": op_rows,
        "daya_baterai": batt_rows,
        "frekuensi": freq_rows,
        "peringatan": peringatan,
        "posko_field_backed": _posko_has_comms_fields(),
    }


# --- writes (login required) -------------------------------------------------

_DEVICE_CATEGORIES = set(_CATEGORY_ORDER)
_DEVICE_STATUS = {"active", "spare", "inactive", "needs_attention"}


def _clean_mhz(value):
    if value in (None, ""):
        return None
    out = _fmt_mhz(value)
    if not out:
        frappe.throw("Frekuensi harus berupa angka MHz antara 0,1 dan 3000 (mis. 146.020).")
    return out.replace(" MHz", "")


@frappe.whitelist()
def create_comms_device(
    device_name,
    category,
    disaster_event=None,
    posko=None,
    status="active",
    battery_pct=None,
    frequency_channel=None,
    current_location=None,
    frequency_mhz=None,
    contact_id=None,
    owner_type="posko",
    owner_id=None,
    notes=None,
):
    rn_actor()  # 403 for Guest
    event = resolve_disaster_event(disaster_event)
    if not event:
        frappe.throw("Disaster event wajib diisi")
    if category not in _DEVICE_CATEGORIES:
        frappe.throw("Kategori alat komunikasi tidak valid")
    if status not in _DEVICE_STATUS:
        frappe.throw("Status alat tidak valid")

    doc = frappe.new_doc("RN Comms Device")
    doc.disaster_event = event
    doc.device_name = device_name
    doc.category = category
    doc.status = status
    if posko:
        doc.posko = resolve_posko(posko)
    if battery_pct not in (None, ""):
        doc.battery_pct = int(battery_pct)
    doc.frequency_channel = frequency_channel
    doc.frequency_mhz = _clean_mhz(frequency_mhz)
    doc.contact_id = (contact_id or "").strip() or None
    doc.current_location = current_location
    doc.owner_type = owner_type
    doc.owner_id = owner_id
    doc.notes = notes
    doc.insert(ignore_permissions=True)
    return {"comms_device": doc.name, "status": doc.status}


@frappe.whitelist()
def update_comms_device(
    comms_device,
    status=None,
    battery_pct=None,
    current_location=None,
    frequency_channel=None,
    notes=None,
    frequency_mhz=None,
    contact_id=None,
):
    rn_actor()
    doc = frappe.get_doc("RN Comms Device", comms_device)
    if status is not None:
        if status not in _DEVICE_STATUS:
            frappe.throw("Status alat tidak valid")
        doc.status = status
    if battery_pct not in (None, ""):
        doc.battery_pct = int(battery_pct)
    for field, value in (
        ("current_location", current_location),
        ("frequency_channel", frequency_channel),
        ("frequency_mhz", None if frequency_mhz is None else _clean_mhz(frequency_mhz)),
        ("contact_id", None if contact_id is None else ((contact_id or "").strip() or None)),
        ("notes", notes),
    ):
        if value is not None:
            doc.set(field, value)
    doc.observed_at = now_datetime()
    doc.save(ignore_permissions=True)
    return {"comms_device": doc.name, "status": doc.status}


@frappe.whitelist()
def create_comms_operator(
    operator_name,
    disaster_event=None,
    posko=None,
    role="operator",
    channel=None,
    status="siaga",
    contact_phone=None,
    skills=None,
    shift_note=None,
):
    rn_actor()
    event = resolve_disaster_event(disaster_event)
    if not event:
        frappe.throw("Disaster event wajib diisi")
    if role not in {"koordinator_radio", "operator", "teknisi"}:
        frappe.throw("Peran operator tidak valid")
    if status not in {"online", "siaga", "istirahat", "offline"}:
        frappe.throw("Status operator tidak valid")

    doc = frappe.new_doc("RN Comms Operator")
    doc.disaster_event = event
    doc.operator_name = operator_name
    doc.role = role
    doc.channel = channel
    doc.status = status
    doc.contact_phone = contact_phone
    doc.skills = skills
    doc.shift_note = shift_note
    if posko:
        doc.posko = resolve_posko(posko)
    doc.insert(ignore_permissions=True)
    return {"comms_operator": doc.name, "status": doc.status}


@frappe.whitelist()
def create_comms_frequency(
    band_label,
    network_type,
    disaster_event=None,
    frequency_value=None,
    provider=None,
    status="baik",
    load_pct=None,
    notes=None,
):
    rn_actor()
    event = resolve_disaster_event(disaster_event)
    if not event:
        frappe.throw("Disaster event wajib diisi")
    if network_type not in {"vhf", "uhf", "hf", "seluler", "starlink", "vsat", "lainnya"}:
        frappe.throw("Jenis jaringan tidak valid")
    if status not in {"baik", "sibuk", "lemah", "down"}:
        frappe.throw("Status frekuensi tidak valid")

    doc = frappe.new_doc("RN Comms Frequency")
    doc.disaster_event = event
    doc.band_label = band_label
    doc.network_type = network_type
    doc.frequency_value = frequency_value
    doc.provider = provider
    doc.status = status
    if load_pct not in (None, ""):
        doc.load_pct = int(load_pct)
    doc.notes = notes
    doc.insert(ignore_permissions=True)
    return {"comms_frequency": doc.name, "status": doc.status}


@frappe.whitelist()
def set_posko_comms_status(posko, status, last_contact=None):
    """Update a posko's connectivity flag (needs the RN Posko custom fields —
    added by the seed/setup script)."""
    rn_actor()
    if status not in _CONN_LABEL:
        frappe.throw("Status konektivitas tidak valid")
    posko = resolve_posko(posko)
    if not _posko_has_comms_fields():
        frappe.throw("Field konektivitas posko belum aktif di instance ini")
    values = {"rn_comms_status": status}
    values["rn_comms_last_contact"] = last_contact or frappe.utils.now_datetime()
    frappe.db.set_value("RN Posko", posko, values, update_modified=False)
    return {"posko": posko, "status": status}
