import frappe
frappe.init(site="osiun.localhost", sites_path="/home/frappe/frappe-bench/sites"); frappe.connect()
# GUARD: never build a delete filter from an empty list (see feedback-destructive-empty-filter).
def gone(doctype, field, values):
    values = [v for v in values if v]
    if not values:
        return 0
    n = frappe.db.count(doctype, {field: ["in", values]})
    frappe.db.delete(doctype, {field: ["in", values]})
    return n
orgs = frappe.get_all("RN Organization", filters={"title": ["like", "[UJI-KOMANDO]%"]}, pluck="name")
accts = frappe.get_all("RN User Account", filters={"email": ["like", "%@cmdtest.local"]}, pluck="name")
poskos = frappe.get_all("RN Posko", filters={"organization": ["in", orgs]}, pluck="name") if orgs else []
assert all(frappe.db.get_value("RN Posko", p, "organization") in orgs for p in poskos)
print("PLAN: orgs", len(orgs), "| poskos", len(poskos), "| accounts", len(accts))
n = {}
n["req"] = gone("RN Command Change Request", "command_organization", orgs) + gone("RN Command Change Request", "requested_by", accts)
n["assign"] = gone("RN Posko Assignment", "posko", poskos) + gone("RN Posko Assignment", "user_account", accts)
n["member"] = gone("RN Organization Membership", "organization", orgs) + gone("RN Organization Membership", "user_account", accts)
n["merge"] = gone("RN Org Merge Request", "requester_organization", orgs) + gone("RN Org Merge Request", "target_organization", orgs)
n["posko"] = gone("RN Posko", "name", poskos)
n["acct"] = gone("RN User Account", "name", accts)
n["org"] = gone("RN Organization", "name", orgs)
# WhatsApp log rows the tests generated (simulated sends to the fixed test numbers 0812345000xx)
logs = frappe.get_all("RN Notification Log", filters={"to_number": ["like", "%812345000%"], "context_type": "command_request"}, pluck="name")
n["wa_log"] = gone("RN Notification Log", "name", logs)
for u in frappe.get_all("User", filters={"name": ["like", "%@cmdtest.local"]}, pluck="name"):
    frappe.delete_doc("User", u, force=True, ignore_permissions=True)
frappe.db.commit()
print("deleted:", n, "| poskos now", frappe.db.count("RN Posko"))
