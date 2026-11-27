"""Protokol Burst VPS (docs/PROTOKOL-BURST-VPS.md) — tombol "Burst ke VPS" di Setting > Cadangan & Pindah Server.

Owner 2026-11-27: "jika bencana besar terjadi saya cukup klik satu button, beri alamat ip vps, login code, semua
otomatis di create di vps itu dan burst siap jalan". RN hanya MENYIMPAN permintaan (kode login terenkripsi).
Pekerjaan dilakukan agen di luar aplikasi (CT102 rn-burst-agent.sh) yang mengambil permintaan dengan token
rahasia (site_config `burst_agent_token`); kode login dihapus dari database begitu diambil agen."""

import hmac
import ipaddress

import frappe
from frappe.utils import now_datetime

DT = "RN Burst Request"
MODES = {"gladi": "Gladi (uji, tanpa alih lalu lintas)", "siaga": "Siaga (VPS siap, belum dipakai)",
         "pindah": "Pindah penuh (burst)", "darurat": "Darurat (Flex mati)"}


def _sm():
    if frappe.session.user in (None, "", "Guest") or "System Manager" not in frappe.get_roles():
        frappe.throw("Hanya super admin (System Manager).", frappe.PermissionError)


def _agent(token):
    exp = str(frappe.conf.get("burst_agent_token") or "")
    if len(exp) < 24 or not hmac.compare_digest(str(token or ""), exp):
        frappe.throw("Tidak diizinkan.", frappe.PermissionError)


def _row(d):
    return {"name": d.name, "mode": d.mode, "mode_label": MODES.get(d.mode, d.mode), "ip": d.ip, "ssh_user": d.ssh_user,
            "status": d.status, "requested_by": d.requested_by, "created": str(d.creation)[:19],
            "started_at": str(d.started_at or "")[:19], "finished_at": str(d.finished_at or "")[:19],
            "log": (d.log or "")[-6000:]}


@frappe.whitelist(methods=["POST"])
def request_burst(ip, login_code, mode="siaga", ssh_user="root"):
    _sm()
    if mode not in MODES:
        frappe.throw("Mode tidak dikenal.")
    try:
        ip = str(ipaddress.ip_address(str(ip or "").strip()))
    except ValueError:
        frappe.throw("Alamat IP VPS tidak valid.")
    ssh_user = str(ssh_user or "root").strip()
    if not ssh_user.replace("_", "").replace("-", "").isalnum() or len(ssh_user) > 32:
        frappe.throw("User SSH tidak valid.")
    if not str(login_code or "").strip() or len(str(login_code)) > 200:
        frappe.throw("Isi kode login VPS (kata sandi root dari penyedia VPS).")
    if frappe.db.exists(DT, {"status": ["in", ["Menunggu", "Berjalan"]]}):
        frappe.throw("Masih ada permintaan burst yang berjalan. Tunggu sampai selesai.")
    d = frappe.get_doc({"doctype": DT, "mode": mode, "ip": ip, "ssh_user": ssh_user, "login_code": str(login_code),
                        "status": "Menunggu", "requested_by": frappe.session.user,
                        "log": "%s permintaan dibuat oleh %s\n" % (str(now_datetime())[:19], frappe.session.user)})
    d.insert(ignore_permissions=True)   # track_changes -> tampil di Jejak Audit
    return _row(d)


@frappe.whitelist()
def list_requests():
    _sm()
    return {"requests": [_row(frappe.get_doc(DT, n)) for n in frappe.get_all(DT, order_by="creation desc", limit=10, pluck="name")],
            "modes": MODES}


@frappe.whitelist(methods=["POST"])
def cancel_request(name):
    _sm()
    d = frappe.get_doc(DT, name)
    if d.status != "Menunggu":
        frappe.throw("Hanya permintaan yang belum berjalan yang bisa dibatalkan.")
    d.status, d.login_code = "Dibatalkan", None
    d.log = (d.log or "") + "%s dibatalkan oleh %s\n" % (str(now_datetime())[:19], frappe.session.user)
    d.save(ignore_permissions=True)
    return _row(d)


@frappe.whitelist(allow_guest=True, methods=["POST"])
def agent_next(token=None):
    """Agen mengambil permintaan tertua. Kode login dikembalikan SEKALI lalu dihapus dari database."""
    _agent(token)
    n = frappe.db.get_value(DT, {"status": "Menunggu"}, "name", order_by="creation asc")
    if not n:
        return {"job": None}
    d = frappe.get_doc(DT, n)
    code = d.get_password("login_code", raise_exception=False) or ""
    d.status, d.started_at, d.login_code = "Berjalan", now_datetime(), None
    d.log = (d.log or "") + "%s diambil agen\n" % str(now_datetime())[:19]
    d.save(ignore_permissions=True)
    frappe.db.delete("__Auth", {"doctype": DT, "name": n, "fieldname": "login_code"})
    return {"job": {"name": n, "mode": d.mode, "ip": d.ip, "ssh_user": d.ssh_user, "login_code": code}}


@frappe.whitelist(allow_guest=True, methods=["POST"])
def agent_update(token=None, name=None, status=None, log=None):
    _agent(token)
    d = frappe.get_doc(DT, name)
    if log:
        d.log = ((d.log or "") + str(log)[-20000:])[-60000:]
    if status in ("Berjalan", "Selesai", "Gagal"):
        d.status = status
        if status != "Berjalan":
            d.finished_at = now_datetime()
    d.save(ignore_permissions=True)
    return {"ok": True}
