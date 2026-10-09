"""Seeds a throwaway world for flows_e2e.py (real-login checks). Everything is tagged [UJI-FLOW] /
@flowtest.local so clean_flows_data.py can remove it. Writes ids to /tmp/flows_ids.json."""
import json
import os
import sys

import frappe

SITE = os.environ.get("RN_SITE", "rescuenet-test.localhost")
if SITE == "osiun.localhost":
    sys.exit("DITOLAK: komando-tests tidak boleh dijalankan terhadap produksi (osiun.localhost).")
frappe.init(site=SITE, sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
PW = "CmdTest123"
DOM = "@flowtest.local"
S = {"missing_name": "NAMA-HILANG-SENTINEL", "found_name": "NAMA-DITEMUKAN-SENTINEL",
     "claimant": "NAMA-PENGKLAIM-SENTINEL", "claimant_contact": "081377700011",
     "rep_phone": "081355500022", "rep_email": "pelapor.sentinel@flowtest.local", "rep_name": "NAMA-PELAPOR-SENTINEL"}


def make(doctype, **f):
    d = frappe.get_doc({"doctype": doctype, **f})
    d.insert(ignore_permissions=True)
    return d


ids = {"sentinels": S}
org_a = make("RN Organization", title="[UJI-FLOW] Org A")
org_b = make("RN Organization", title="[UJI-FLOW] Org B")
event = make("RN Disaster Event", legacy_id="event-uji-flow", title="[UJI-FLOW] Bencana")
pa = make("RN Posko", title="[UJI-FLOW] Posko A", disaster_event=event.name, organization=org_a.name)
pb = make("RN Posko", title="[UJI-FLOW] Posko B", disaster_event=event.name, organization=org_b.name)
ids.update(org_a=org_a.name, org_b=org_b.name, event=event.name, posko_a=pa.name, posko_b=pb.name)

# key -> (rn role, extra frappe roles)
USERS = {"sm": ("posko_operator", ["System Manager"]), "opa": ("posko_operator", []), "opb": ("posko_operator", []),
         "ver": ("citizen", []), "ver2": ("citizen", []), "vsus": ("citizen", []), "plain": ("citizen", []),
         "reporter": ("citizen", []), "cc": ("command_center", [])}
acc = {}
for key, (role, extra) in USERS.items():
    email = key + DOM
    u = frappe.get_doc({"doctype": "User", "email": email, "first_name": key.title(), "send_welcome_email": 0,
                        "user_type": "System User" if extra else "Website User", "new_password": PW})
    for r in extra:
        u.append("roles", {"role": r})
    u.insert(ignore_permissions=True)
    acc[key] = make("RN User Account", frappe_user=u.name, title=f"Uji Flow {key}", username=f"fl_{key}",
                    email=email, role=role, status="active", phone=S["rep_phone"] if key == "reporter" else None).name
ids["acc"] = acc
make("RN Posko Assignment", user_account=acc["opa"], posko=pa.name, assignment_role="operator", status="approved")
make("RN Posko Assignment", user_account=acc["opb"], posko=pb.name, assignment_role="operator", status="approved")
for key, st in (("ver", "active"), ("ver2", "active"), ("vsus", "suspended")):
    make("RN Verifier Profile", title=f"Verifikator {key}", user=acc[key], verifier_type="community_leader",
         verifier_status=st, trust_level=1)

# Search & Found (posko A) with sentinel names
miss = make("RN Missing Person Report", person_code="UJI-M-1", person_name=S["missing_name"], disaster_event=event.name,
            posko=pa.name, report_status="missing", description="anak hilang baju merah", clothing_description="baju merah",
            reporter_name=S["rep_name"], reporter_contact=S["rep_phone"], created_by_user=acc["opa"])
found = make("RN Found Person Report", person_code="UJI-F-1", person_name=S["found_name"], disaster_event=event.name,
             posko=pa.name, report_status="found", description="anak ditemukan baju merah", clothing_description="baju merah",
             reporter_name=S["rep_name"], reporter_contact=S["rep_phone"], created_by_user=acc["opa"],
             identification_status="belum_teridentifikasi")
claim = make("RN Search Found Claim", claim_code="CLM-UJI-1", item_description="Tas biru", kind="barang",
             disaster_event=event.name, posko=pa.name, claimant_name=S["claimant"], claimant_contact=S["claimant_contact"],
             claim_status="menunggu_verifikasi", created_by_user=acc["opa"])
ids.update(missing=miss.name, found=found.name, claim=claim.name)

# Program Khusus owned by posko A
prog = make("RN Donor Program", program_name="[UJI-FLOW] Program", disaster_event=event.name, owner_type="posko",
            owner_id=pa.name, status="active", public_visibility="restricted", output_target=12, output_verified=0)
ms = make("RN Program Milestone", program=prog.name, title="[UJI-FLOW] Tahap 1", milestone_status="berjalan", progress_percent=10)
ids.update(program=prog.name, milestone=ms.name)

# Community reports + AI suggestions
def report(title, posko, consent, phone):
    return make("RN Community Report", title=f"[UJI-FLOW] {title}", description="Banjir setinggi dada, butuh perahu karet dan makanan.",
                disaster_event=event.name, report_type="shelter_need", priority="medium", affected_people_count=10,
                posko=posko, status="submitted", ai_status="ai_suggested", reporter_user=acc["reporter"],
                reporter_name=S["rep_name"], reporter_phone=phone, reporter_email=S["rep_email"] if consent else None,
                consent_to_contact=consent).name


ids["rep_consent"] = report("A consent", pa.name, 1, S["rep_phone"])
ids["rep_noconsent"] = report("A tanpa consent", pa.name, 0, S["rep_phone"])
ids["rep_noposko"] = report("tanpa posko", None, 1, S["rep_phone"])
ids["rep_b"] = report("B", pb.name, 1, S["rep_phone"])


def sug(ref):
    return make("RN AI Suggestion", feature="report_intake", ref_doctype="RN Community Report", ref_name=ref, provider="openai",
                payload='{"current": {}, "proposed": {"affected_people_count": 55}}', status="draft").name


ids.update(sug_accept=sug(ids["rep_consent"]), sug_reject=sug(ids["rep_noconsent"]), sug_b=sug(ids["rep_b"]),
           sug_b2=sug(ids["rep_b"]))
frappe.db.commit()
json.dump(ids, open("/tmp/flows_ids.json", "w"))
print("FLOWS_SETUP ok", len(ids))
