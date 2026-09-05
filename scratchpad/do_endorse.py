import frappe
frappe.set_user("admin.osiun@gmail.com")
from rescue_net.api_verifier import verifier_inbox, endorse_posko, posko_verification_public
inb = verifier_inbox()
dreq = [r for r in inb.get("direct_requests", []) if r["object_id"] == "SIM-NS-POSKO-WARGA"]
if dreq:
    r = endorse_posko(request=dreq[0]["name"], statement="Dikunjungi 4 Sep 2026; posko warga aktif melayani ~120 KK di Gedung Serbaguna.")
    print("ENDORSE:", r)
else:
    print("no pending WARGA request; existing endorsement?")
frappe.db.commit()
print("AFTER:", posko_verification_public("SIM-NS-POSKO-WARGA"))
