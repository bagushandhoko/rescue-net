import frappe
import os, sys
SITE = os.environ.get("RN_SITE", "rescuenet-test.localhost")
if SITE == "osiun.localhost":
    sys.exit("DITOLAK: komando-tests tidak boleh dijalankan terhadap produksi (osiun.localhost). Pakai scripts/rn-test-stack.sh e2e-ai.")
frappe.init(site=SITE, sites_path="/home/frappe/frappe-bench/sites"); frappe.connect()
PW = "CmdTest123"


def make(doctype, **f):
    d = frappe.get_doc({"doctype": doctype, **f}); d.insert(ignore_permissions=True); return d


org = make("RN Organization", title="[UJI-AI] Organisasi")
out_org = make("RN Organization", title="[UJI-AI] Organisasi Lain")
event = make("RN Disaster Event", legacy_id="event-uji-ai", title="[UJI-AI] Bencana")
for key, o, role in (("owner", org, "owner"), ("member", org, "member"), ("outsider", out_org, "member"),
                     ("personal", None, None)):
    email = f"{key}@aitest.local"
    u = make("User", email=email, first_name=key.title(), send_welcome_email=0, user_type="Website User", new_password=PW)
    a = make("RN User Account", frappe_user=u.name, title=f"Uji AI {key}", username=f"ai_{key}", email=email,
             role="posko_operator", status="active")
    if o:
        make("RN Organization Membership", user_account=a.name, organization=o.name, membership_role=role, status="approved")
frappe.db.commit()
print("AI_ORG=" + org.name, "AI_EVENT=" + event.name)
