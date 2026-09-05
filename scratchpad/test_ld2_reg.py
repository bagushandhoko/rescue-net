import frappe
from rescue_net.access_policy import rn_actor, can_manage_posko
frappe.set_user("ld2.demo@rescue-net.local")
a2 = rn_actor(required=False)
print("LD2 role:", a2.get("role"), "posko:", a2.get("posko"))
for n in ["SIM-LR-POSKO-LD2","SIM-LR-POSKO-LD3","SIM-LR-POSKO-LD4","SIM-LR-POSKO-LD5"]:
    print("  LD2 can_manage", n, "->", can_manage_posko(a2, n))
frappe.set_user("ld6.demo@rescue-net.local")
a6 = rn_actor(required=False)
print("LD6 role:", a6.get("role"), "posko:", a6.get("posko"))
for n in ["SIM-LR-POSKO-LD6","SIM-LR-POSKO-LD2"]:
    print("  LD6 can_manage", n, "->", can_manage_posko(a6, n))
