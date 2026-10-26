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
