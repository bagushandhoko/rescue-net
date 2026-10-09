import os
import sys

import frappe

SITE = os.environ.get("RN_SITE", "rescuenet-test.localhost")
if SITE == "osiun.localhost":
    sys.exit("DITOLAK: komando-tests tidak boleh dijalankan terhadap produksi (osiun.localhost).")
frappe.init(site=SITE, sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()


def gone(doctype, field, values):
    """GUARD: never build a delete filter from an empty list."""
    values = [v for v in values if v]
    if not values:
        return 0
    n = frappe.db.count(doctype, {field: ["in", values]})
    frappe.db.delete(doctype, {field: ["in", values]})
    return n


users = frappe.get_all("User", filters={"email": ["like", "%@flowtest.local"]}, pluck="name")
accts = frappe.get_all("RN User Account", filters={"email": ["like", "%@flowtest.local"]}, pluck="name")
orgs = frappe.get_all("RN Organization", filters={"title": ["like", "[UJI-FLOW]%"]}, pluck="name")
poskos = frappe.get_all("RN Posko", filters={"title": ["like", "[UJI-FLOW]%"]}, pluck="name")
progs = frappe.get_all("RN Donor Program", filters={"program_name": ["like", "[UJI-FLOW]%"]}, pluck="name")
reports = frappe.get_all("RN Community Report", filters={"title": ["like", "[UJI-FLOW]%"]}, pluck="name")
verifs = frappe.get_all("RN Verifier Profile", filters={"user": ["in", accts or [""]]}, pluck="name") if accts else []
print("PLAN: users", len(users), "| accounts", len(accts), "| orgs", len(orgs), "| poskos", len(poskos),
      "| programs", len(progs), "| reports", len(reports), "| verifiers", len(verifs))
for dt in ("RN Program Milestone", "RN Program Location", "RN Program Need"):
    gone(dt, "program", progs)
gone("RN Donor Program", "name", progs)
gone("RN AI Suggestion", "ref_name", reports)
gone("RN AI Job", "ref_name", reports)
gone("RN Community Need", "source_report", reports)
gone("RN Community Report", "name", reports)
for dt in ("RN Missing Person Report", "RN Found Person Report", "RN Search Found Claim"):
    gone(dt, "posko", poskos)
gone("RN Missing Person Report", "created_by_user", accts)
gone("RN Found Person Report", "created_by_user", accts)
gone("RN Search Found Claim", "created_by_user", accts)
gone("RN Verification Endorsement", "verifier", verifs)
gone("RN Verification Endorsement", "target_id", accts)
gone("RN Verification Action", "object_id", reports + accts + verifs)
gone("RN Verification Action", "reviewed_by", accts + users)
gone("RN Verifier Profile", "name", verifs)
gone("RN Posko Assignment", "posko", poskos)
gone("RN Organization Membership", "user_account", accts)
gone("Notification Log", "for_user", users)
gone("RN Posko", "name", poskos)
gone("RN User Account", "name", accts)
for u in users:
    frappe.delete_doc("User", u, force=True, ignore_permissions=True)
gone("RN Organization", "name", orgs)
gone("RN Disaster Event", "legacy_id", ["event-uji-flow"])
frappe.db.commit()
print("clean done")
