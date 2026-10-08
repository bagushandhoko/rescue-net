import frappe
import os, sys
SITE = os.environ.get("RN_SITE", "rescuenet-test.localhost")
if SITE == "osiun.localhost":
    sys.exit("DITOLAK: komando-tests tidak boleh dijalankan terhadap produksi (osiun.localhost).")
frappe.init(site=SITE, sites_path="/home/frappe/frappe-bench/sites"); frappe.connect()
# GUARD: never build a delete filter from an empty list.
def gone(doctype, field, values):
    values = [v for v in values if v]
    if not values:
        return 0
    n = frappe.db.count(doctype, {field: ["in", values]})
    frappe.db.delete(doctype, {field: ["in", values]})
    return n
users = frappe.get_all("User", filters={"email": ["like", "%@aitest.local"]}, pluck="name")
accts = frappe.get_all("RN User Account", filters={"email": ["like", "%@aitest.local"]}, pluck="name")
orgs = frappe.get_all("RN Organization", filters={"title": ["like", "[UJI-AI]%"]}, pluck="name")
print("PLAN: users", len(users), "| accounts", len(accts), "| orgs", len(orgs))
gone("RN Organization Membership", "user_account", accts)
gone("RN AI User Setting", "organization_id", orgs); gone("RN AI User Setting", "user_id", users)
gone("RN AI Profile", "owner_id", orgs + users)
gone("RN AI Usage Log", "owner_id", orgs + users); gone("RN AI Usage Log", "user_id", users)
gone("RN AI Usage Daily", "owner_id", orgs + users)
gone("Notification Log", "for_user", users)
reports = frappe.get_all("RN Community Report", filters={"title": ["like", "[UJI-AI]%"]}, pluck="name") + \
    frappe.get_all("RN Community Report", filters={"reporter_user": ["in", accts or [""]]}, pluck="name")
gone("RN AI Job", "ref_name", reports); gone("RN AI Suggestion", "ref_name", reports)
poskos = frappe.get_all("RN Posko", filters={"title": ["like", "[UJI-AI]%"]}, pluck="name")
gone("RN Posko Assignment", "posko", poskos)
gone("RN Community Report", "name", reports)
gone("RN Posko", "name", poskos)
gone("RN User Account", "name", accts)
for u in users:
    frappe.delete_doc("User", u, force=True, ignore_permissions=True)
gone("RN Organization", "name", orgs)
gone("RN Disaster Event", "legacy_id", ["event-uji-ai"])
frappe.db.commit(); print("clean done")
