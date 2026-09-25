# Run inside the container AFTER api_e2e.py: the WhatsApp notifications must be in RN Notification Log.
# args via env: none — numbers are the fixed test numbers used by api_e2e.py (section 11/13).
import frappe
frappe.init(site="osiun.localhost", sites_path="/home/frappe/frappe-bench/sites"); frappe.connect()
def logs(num, key):
    return frappe.get_all("RN Notification Log", filters={"to_number": ["like", "%" + num[-9:]], "event_key": key},
                          fields=["name", "status", "body", "context_type"], limit_page_length=50)
ok = fail = 0
def check(name, cond, extra=""):
    global ok, fail
    ok, fail = (ok + 1, fail) if cond else (ok, fail + 1)
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else "  -> " + str(extra)[:300]))
new = logs("081234500002", "command_request_new")
# the numbered deputy is deputy for exactly ONE new request (phase 11); after being revoked they must not be told again
check("N1. wakil (bernomor HP) dikabari WA saat ada permintaan baru — dan tidak lagi setelah dicabut", len(new) == 1 and all(l.context_type == "command_request" for l in new), new)
check("N2. isi WA memuat ringkasan permintaan", all("Permintaan baru" in (l.body or "") for l in new), new)
dec = logs("081234500001", "command_request_decided")
check("N3. pemohon dikabari WA saat permintaannya diputuskan", any("DITERAPKAN" in (l.body or "") for l in dec), dec)
check("N4. status log = simulated/sent (bukan failed)", all(l.status in ("simulated", "sent") for l in new + dec), [l.status for l in new + dec])
print(f"notify ok={ok} fail={fail}")
