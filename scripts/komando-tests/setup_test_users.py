import frappe
frappe.init(site="osiun.localhost", sites_path="/home/frappe/frappe-bench/sites"); frappe.connect()
PW = "CmdTest123"
for key in ("pusat", "sub", "out", "man"):
    email = f"{key}@cmdtest.local"
    if frappe.db.exists("User", email): continue
    u = frappe.get_doc({"doctype": "User", "email": email, "first_name": key.title(), "send_welcome_email": 0,
                        "user_type": "Website User", "new_password": PW})
    u.flags.ignore_permissions = True; u.insert(ignore_permissions=True)
    a = frappe.get_doc({"doctype": "RN User Account", "frappe_user": u.name, "title": f"Uji {key}", "username": f"cmd_{key}",
                        "email": email, "role": "viewer", "status": "active"})
    a.flags.ignore_permissions = True; a.insert(ignore_permissions=True)
# System Manager test account (scheme admin tests); removed by clean_test_data.py with the other @cmdtest.local users
if not frappe.db.exists("User", "sm@cmdtest.local"):
    u = frappe.get_doc({"doctype": "User", "email": "sm@cmdtest.local", "first_name": "Sm", "send_welcome_email": 0,
                        "user_type": "System User", "new_password": PW, "roles": [{"role": "System Manager"}]})
    u.insert(ignore_permissions=True)
frappe.db.commit(); print("users ready")
