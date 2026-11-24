"""Email ke donatur (owner 24 Nov 2026: "kalau orang kirim donasi, ada email dari RN ke emailnya").

Dua email: (1) saat donasi dikirim -> terima kasih + nominal + rekening tujuan + status menunggu konfirmasi;
(2) saat pengelola memutuskan -> diterima / tidak dikonfirmasi. Alamat: email akun RN donatur, atau kontak yang
diisi bila berbentuk email. Akun demo/uji (@rescue-net.local) tidak dikirimi. Email masuk antrean HANYA bila akun
email keluar sudah dipasang (tanpa itu antrean akan menumpuk lalu terkirim serentak, terlambat). Kegagalan email
tidak pernah menggagalkan donasi."""

import re

import frappe
from frappe.utils import escape_html

SITE = "https://rescue-net.online/rescue-net/pages/program-khusus.html?program="
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")
_SKIP_DOMAINS = ("rescue-net.local", "example.com", "test.rescue-net.local")


def outgoing_ready():
    return bool(frappe.db.exists("Email Account", {"enable_outgoing": 1}))


def donor_email(doc):
    cand = []
    if doc.get("donor_user"):
        cand.append(frappe.db.get_value("RN User Account", doc.donor_user, "email"))
    cand.append(doc.get("donor_contact"))
    for c in cand:
        c = (c or "").strip().lower()
        if _EMAIL.match(c) and not c.endswith(_SKIP_DOMAINS):
            return c
    return None


def _rp(v):
    return "Rp " + "{:,.0f}".format(v or 0).replace(",", ".")


def _sim_tag(event):
    from rescue_net.services.drill import is_simulation_event
    return "[SIMULASI] " if event and is_simulation_event(event) else ""


def _send(to, subject, rows, intro, outro):
    table = "".join('<tr><td style="padding:4px 12px 4px 0;color:#666">%s</td><td style="padding:4px 0"><b>%s</b></td></tr>'
                    % (escape_html(k), escape_html(v)) for k, v in rows if v)
    html = ('<div style="font-family:Arial,sans-serif;font-size:14px;color:#222;max-width:560px">'
            '<p>%s</p><table>%s</table><p>%s</p>'
            '<p style="color:#888;font-size:12px">Email otomatis dari Rescue-Net. Rescue-Net tidak pernah meminta '
            'transfer ke rekening selain yang tertera di halaman program. Jangan balas email ini.</p></div>'
            % (intro, table, outro))
    frappe.sendmail(recipients=[to], subject=subject, message=html, delayed=True, reference_doctype="RN Cash Donation")


def _program(name):
    return frappe.db.get_value("RN Donor Program", name, ["program_name", "disaster_event", "bank_name",
                                                         "bank_account_number", "bank_account_holder", "work_drawings"], as_dict=True) or frappe._dict()


def on_created(doc):
    """Dipanggil sesudah donasi tersimpan. Mengembalikan alamat yang dikirimi, atau None."""
    try:
        to = donor_email(doc)
        if not to or not outgoing_ready():
            return None
        p = _program(doc.donor_program)
        bank = " · ".join(x for x in (p.bank_name, p.bank_account_number, p.bank_account_holder and "a.n. " + p.bank_account_holder) if x)
        _send(to, "%sTerima kasih, donasi %s untuk %s sudah tercatat" % (_sim_tag(doc.disaster_event), _rp(doc.amount), p.program_name),
              [("Program", p.program_name), ("Nominal", _rp(doc.amount)), ("Nomor donasi", doc.name),
               ("Rekening tujuan", bank or "lihat halaman program"),
               ("QRIS", "tersedia di halaman program" if '"qris"' in (p.work_drawings or "") else ""),
               ("Status", "Menunggu konfirmasi pengelola program")],
              "Halo %s, terima kasih atas niat baik Anda." % escape_html(doc.donor_name or "Donatur"),
              'Bila belum, silakan transfer sesuai nominal ke rekening di atas. Pengelola program akan mengonfirmasi '
              'setelah dana masuk, dan Anda akan menerima email lagi. <a href="%s%s">Lihat program</a>.'
              % (SITE, escape_html(doc.donor_program)))
        return to
    except Exception:
        frappe.log_error(title="rn donation email (created) failed")
        return None


def on_decided(doc, action, note=None):
    try:
        to = donor_email(doc)
        if not to or not outgoing_ready():
            return None
        p = _program(doc.donor_program)
        ok = action == "confirm"
        _send(to, "%sDonasi %s untuk %s %s" % (_sim_tag(doc.disaster_event), _rp(doc.amount), p.program_name,
                                                "sudah diterima" if ok else "tidak dikonfirmasi"),
              [("Program", p.program_name), ("Nominal", _rp(doc.amount)), ("Nomor donasi", doc.name),
               ("Status", "Diterima & dikonfirmasi pengelola" if ok else "Tidak dikonfirmasi"),
               ("Catatan pengelola", (note or "").strip()[:300])],
              "Halo %s," % escape_html(doc.donor_name or "Donatur"),
              ("Dana Anda sudah tercatat masuk ke program dan tampil di daftar penyumbang. Terima kasih."
               if ok else "Pengelola belum menemukan dana ini. Bila Anda sudah transfer, hubungi pengelola lewat halaman program.")
              + ' <a href="%s%s">Lihat program</a>.' % (SITE, escape_html(doc.donor_program)))
        return to
    except Exception:
        frappe.log_error(title="rn donation email (decided) failed")
        return None
