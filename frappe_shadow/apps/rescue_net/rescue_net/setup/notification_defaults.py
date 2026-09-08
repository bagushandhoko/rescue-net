import frappe

# Seeds the app-wide `RN Notification Setting` row (scope "global") the first
# time it is missing. Provider defaults to `simulasi` + disabled: every send is
# logged in `RN Notification Log` but nothing leaves the server until a real
# gateway (fonnte / wablas / twilio / meta_cloud) + token is saved from the
# Notifikasi WhatsApp settings page. Idempotent — never overwrites an existing
# row (so a gateway configured in Desk / the settings page survives migrate).

_NOTE = (
    "Default simulasi — setiap kiriman WhatsApp dicatat di RN Notification "
    "Log (status 'simulated') tanpa benar-benar keluar. Ganti provider + token "
    "lewat halaman Notifikasi WhatsApp untuk mengaktifkan pengiriman nyata."
)


def install_defaults():
    if not frappe.db.exists("DocType", "RN Notification Setting"):
        return {"status": "doctype_not_ready"}
    if frappe.db.get_value("RN Notification Setting", {"scope": "global"}, "name"):
        return {"status": "exists"}
    doc = frappe.new_doc("RN Notification Setting")
    doc.scope = "global"
    doc.channel = "whatsapp"
    doc.provider = "simulasi"
    doc.enabled = 0
    doc.note = _NOTE
    doc.status = "active"
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return {"status": "created", "name": doc.name}
