"""Program donasi "melalui Kitabisa" (owner 2026-11-08: "pilihan itu ada saat setting program khusus, mau dikelola
sendiri atau melalui Kitabisa, dan ada data pendukung yang ditampilkan yang nggak ada di Kitabisa").

What we can read from a public Kitabisa campaign page (schema.org JSON-LD in the HTML): title, image, organiser +
logo, target, open/closed. The collected amount and donor count are loaded by Kitabisa's own API, which is behind a
Cloudflare challenge — we do NOT try to get around that. The initiator copies those two figures from their Kitabisa
dashboard (stored with a date and shown as "per tanggal …, sumber Kitabisa").
"""

import json
import re

import frappe
from frappe.utils import cint, flt, getdate, now_datetime, nowdate

from rescue_net.api_kitchen import rn_actor, _is_control
from rescue_net.donor_program.common import _program, _program_manager

URL_RE = re.compile(r"^https://(www\.)?kitabisa\.com/(campaign/)?([A-Za-z0-9_-]{3,80})/?(\?.*)?$")
CHANNELS = ("sendiri", "kitabisa")
STALE_HOURS = 6


def normalize_url(url):
    url = (url or "").strip()
    m = URL_RE.match(url)
    if not m:
        frappe.throw("Link Kitabisa tidak valid. Contoh: https://kitabisa.com/campaign/namacampaign")
    return "https://kitabisa.com/campaign/" + m.group(3)


def parse_campaign_html(html, url):
    """Pull the public campaign facts out of the page's JSON-LD. Returns a dict (never raises on odd pages)."""
    out = {"url": url, "title": None, "image": None, "organizer": None, "organizer_logo": None,
           "target": None, "open": None, "campaign_id": None}
    for block in re.findall(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', html or "", re.S):
        try:
            data = json.loads(block)
        except ValueError:
            continue
        items = data if isinstance(data, list) else [data]
        for it in items:
            if not isinstance(it, dict) or it.get("@type") not in ("Product", "DonateAction", "Event", "CreativeWork"):
                continue
            out["title"] = (it.get("name") or "").strip() or out["title"]
            img = it.get("image")
            out["image"] = (img[0] if isinstance(img, list) and img else img) or out["image"]
            org = it.get("manufacturer") or it.get("brand") or {}
            if isinstance(org, dict) and org.get("name") and org.get("name") != "Kitabisa.com":
                out["organizer"] = org.get("name")
                logo = org.get("logo")
                out["organizer_logo"] = logo.get("url") if isinstance(logo, dict) else logo
            offers = it.get("offers") or []
            offer = offers[0] if isinstance(offers, list) and offers else (offers if isinstance(offers, dict) else {})
            if offer:
                out["target"] = flt(offer.get("price")) or None
                avail = str(offer.get("availability") or "")
                out["open"] = None if not avail else not avail.endswith(("SoldOut", "Discontinued", "OutOfStock"))
                seller = offer.get("seller") or {}
                if not out["organizer"] and isinstance(seller, dict):
                    out["organizer"] = seller.get("name")
            out["campaign_id"] = it.get("mpn") or out["campaign_id"]
    if not out["title"]:
        m = re.search(r'property="og:title" content="([^"]+)"', html or "")
        if m:
            out["title"] = re.sub(r"^Kitabisa-in Yuk!\s*-\s*", "", m.group(1)).strip()
    if not out["image"]:
        m = re.search(r'property="og:image" content="([^"]+)"', html or "")
        if m:
            out["image"] = m.group(1)
    return out


def fetch_campaign(url):
    import requests
    resp = requests.get(url, timeout=15, headers={
        "User-Agent": "Mozilla/5.0 (compatible; RescueNet/1.0; +https://rescue-net.online)",
        "Accept": "text/html"})
    if resp.status_code != 200:
        raise ValueError("Kitabisa menjawab HTTP %s" % resp.status_code)
    data = parse_campaign_html(resp.text, url)
    if not data.get("title"):
        raise ValueError("Halaman Kitabisa tidak berisi data campaign (mungkin link salah atau sedang dibatasi).")
    return data


def _store(program, data=None, error=None):
    vals = {"kitabisa_synced_at": now_datetime()}
    if data is not None:
        vals["kitabisa_data"] = json.dumps(data, ensure_ascii=False)
    elif error:
        old = {}
        try:
            old = json.loads(frappe.db.get_value("RN Donor Program", program, "kitabisa_data") or "{}")
        except ValueError:
            pass
        old["last_error"] = str(error)[:200]
        vals["kitabisa_data"] = json.dumps(old, ensure_ascii=False)
    frappe.db.set_value("RN Donor Program", program, vals, update_modified=False)


def _assert_manage(actor, row):
    if not (_is_control(actor) or _program_manager(actor, row)):
        frappe.throw("Hanya pemrakarsa program yang boleh mengubah ini.", frappe.PermissionError)


@frappe.whitelist(methods=["POST"])
def set_donation_channel(donor_program, channel, kitabisa_url=None):
    """Pemrakarsa memilih: dikelola sendiri (rekening/QRIS sendiri) atau melalui Kitabisa (link campaign)."""
    actor = rn_actor()
    row = _program(donor_program)
    _assert_manage(actor, row)
    channel = (channel or "").strip().lower()
    if channel not in CHANNELS:
        frappe.throw("Pilihan tidak dikenal (sendiri / kitabisa).")
    if channel == "sendiri":
        frappe.db.set_value("RN Donor Program", donor_program, "donation_channel", "sendiri")
        return {"donation_channel": "sendiri"}
    url = normalize_url(kitabisa_url)
    frappe.db.set_value("RN Donor Program", donor_program, {"donation_channel": "kitabisa", "kitabisa_url": url})
    try:
        data = fetch_campaign(url)
        _store(donor_program, data)
        return {"donation_channel": "kitabisa", "kitabisa": data}
    except Exception as exc:
        _store(donor_program, error=exc)
        return {"donation_channel": "kitabisa", "kitabisa": None,
                "warning": "Link disimpan, tetapi data Kitabisa belum bisa dibaca sekarang: %s. Coba 'Perbarui dari Kitabisa' nanti." % exc}


@frappe.whitelist(methods=["POST"])
def refresh_kitabisa(donor_program):
    actor = rn_actor()
    row = _program(donor_program)
    _assert_manage(actor, row)
    url = frappe.db.get_value("RN Donor Program", donor_program, "kitabisa_url")
    if not url:
        frappe.throw("Program ini belum punya link Kitabisa.")
    try:
        data = fetch_campaign(url)
    except Exception as exc:
        _store(donor_program, error=exc)
        frappe.throw("Data Kitabisa belum bisa dibaca: %s" % exc)
    _store(donor_program, data)
    return {"kitabisa": data}


@frappe.whitelist(methods=["POST"])
def set_kitabisa_figures(donor_program, collected=None, donor_count=None, as_of=None):
    """Angka dari dashboard Kitabisa pemrakarsa (tidak bisa dibaca otomatis)."""
    actor = rn_actor()
    row = _program(donor_program)
    _assert_manage(actor, row)
    collected, donor_count = flt(collected), cint(donor_count)
    if collected < 0 or donor_count < 0:
        frappe.throw("Angka tidak boleh negatif.")
    day = getdate(as_of) if as_of else getdate(nowdate())
    if day > getdate(nowdate()):
        frappe.throw("Tanggal tidak boleh di masa depan.")
    frappe.db.set_value("RN Donor Program", donor_program, {
        "kitabisa_collected": collected, "kitabisa_donor_count": donor_count, "kitabisa_figures_at": day})
    return {"collected": collected, "donor_count": donor_count, "as_of": str(day)}


def public_block(row):
    """What program_detail / program_board show for a Kitabisa-channel program."""
    if (row.get("donation_channel") or "sendiri") != "kitabisa":
        return None
    try:
        data = json.loads(row.get("kitabisa_data") or "{}")
    except ValueError:
        data = {}
    data.pop("last_error", None)
    return {
        "url": row.get("kitabisa_url"),
        "title": data.get("title"), "image": data.get("image"),
        "organizer": data.get("organizer"), "organizer_logo": data.get("organizer_logo"),
        "target": data.get("target"), "open": data.get("open"),
        "synced_at": str(row.get("kitabisa_synced_at") or "")[:16] or None,
        "collected": flt(row.get("kitabisa_collected")) if row.get("kitabisa_figures_at") else None,
        "donor_count": cint(row.get("kitabisa_donor_count")) if row.get("kitabisa_figures_at") else None,
        "figures_at": str(row.get("kitabisa_figures_at") or "") or None,
    }


def refresh_stale():
    """Hourly: re-read Kitabisa campaigns older than STALE_HOURS (title/target/open)."""
    from frappe.utils import add_to_date
    cutoff = add_to_date(now_datetime(), hours=-STALE_HOURS)
    rows = frappe.get_all("RN Donor Program",
                          filters={"donation_channel": "kitabisa", "kitabisa_url": ["is", "set"],
                                   "status": ["not in", ["cancelled", "completed"]]},
                          fields=["name", "kitabisa_url", "kitabisa_synced_at"], limit_page_length=200)
    for r in rows:
        if r.kitabisa_synced_at and r.kitabisa_synced_at > cutoff:
            continue
        try:
            _store(r.name, fetch_campaign(r.kitabisa_url))
        except Exception as exc:
            _store(r.name, error=exc)
        frappe.db.commit()
