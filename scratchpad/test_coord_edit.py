import frappe
from rescue_net.access_policy import rn_actor, can_manage_posko

frappe.set_user("ld1.demo@rescue-net.local")
actor = rn_actor(required=False)
print("LD1 actor:", dict(actor) if actor else None)

siblings = frappe.get_all("RN Posko", filters={"organization": "SIM-LR-ORG"},
                          fields=["name", "title", "organization"], limit_page_length=50)
for p in siblings:
    print("  can_manage", p["name"], "->", can_manage_posko(actor, p["name"]))

# a posko from another org must stay False
other = frappe.get_all("RN Posko", filters={"organization": ["!=", "SIM-LR-ORG"]},
                       fields=["name", "organization"], limit_page_length=3)
for p in other:
    print("  OTHER-ORG can_manage", p["name"], "(", p["organization"], ") ->",
          can_manage_posko(actor, p["name"]))

print("--- my_org_coordination as LD1 ---")
from rescue_net.api_control_centre import my_org_coordination
d = my_org_coordination(disaster_event="event-sim-001")
print("my_posko:", d["my_posko"])
print("totals:", d["totals"])
for c in d["my_org_poskos"]:
    print("  org posko", c["name"], "can_edit=", c["can_edit"])

print("--- posko_edit_scope as LD1 vs a sibling ---")
from rescue_net.api_control_centre import posko_edit_scope
sib = siblings[0]["name"] if siblings else None
s = posko_edit_scope(posko=sib, disaster_event="event-sim-001")
print("sibling", sib, "can_edit_current=", s["can_edit_current"],
      "primary_posko=", s["primary_posko"], "my_poskos=", len(s["my_poskos"]))

# LD2 (operator, own posko) must be unchanged: can edit own, not siblings
frappe.set_user("ld2.demo@rescue-net.local")
a2 = rn_actor(required=False)
print("--- LD2 regression ---")
for p in siblings:
    print("  LD2 can_manage", p["name"], "->", can_manage_posko(a2, p["name"]))
