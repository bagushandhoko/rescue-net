"""Load the fictional DMS exercise into an explicitly selected RN site."""
import hashlib
import json
from pathlib import Path

import frappe
from frappe.utils.password import update_password

from rescue_net.api_dms import DOCTYPE, _allowed, _catalog, _clean
from rescue_net.services.drill import DMS_DEMO_USERS, DMS_SOURCE as SOURCE
CUTOFF = "2026-11-23 06:00:00"
AGENCIES = {"bnpb": "BNPB", "tni": "TNI/POLRI", "pmi": "PMI", "kementerian": "Kementerian"}
STARTS = {
    "SIM-DMS-01": ("2026-11-18 05:42:00", "earthquake"),
    "SIM-DMS-02": ("2026-11-21 00:00:00", "flood"),
    "SIM-DMS-03": ("2026-11-20 00:00:00", "volcano"),
}
ITEMS = (
    "Beras", "Air minum", "Makanan siap saji", "Terpal", "Selimut", "Popok bayi",
    "Sabun", "Oralit", "Masker", "Jeriken", "Lampu darurat", "Paket kebersihan",
)


def _read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _insert(doctype, name, **fields):
    existing = frappe.db.get_value(doctype, name, "name")
    if existing:
        if fields.get("disaster_event") and frappe.db.get_value(
            doctype, name, "disaster_event"
        ) != fields["disaster_event"]:
            frappe.throw(f"ID seed bertabrakan pada {doctype}.")
        return existing
    doc = frappe.get_doc({"doctype": doctype, **fields})
    doc.flags.rn_data_load = True
    doc.insert(ignore_permissions=True, set_name=name)
    return doc.name


def _organization(template):
    candidates = frappe.get_all(
        "RN Organization",
        filters={"title": ["like", "%[SIMULASI]%"], "privacy_mode": "closed",
                 "operation_template": template},
        fields=["name", "title"],
        order_by="name asc",
    )
    eligible = [row.name for row in candidates if "aceh barat" not in row.title.casefold()]
    if eligible:
        return eligible[0]
    return _insert(
        "RN Organization", f"dms-demo-org-{template}", title=f"[SIMULASI] {AGENCIES[template]}",
        organization_type="institution", status="active", operation_template=template,
        privacy_mode="closed", legacy_source=SOURCE,
    )


def _account(template, organization, passwords):
    email = f"demo-{template}@disastermanagement.online"
    account = f"dms-demo-account-{template}"
    if frappe.db.exists("User", email):
        if frappe.db.get_value("RN User Account", account, "frappe_user") != email:
            frappe.throw(f"Akun demo {template} sudah dipakai di luar seed DMS.")
    else:
        frappe.get_doc(doctype="User", email=email, first_name=f"Demo {AGENCIES[template]}",
                       user_type="Website User", send_welcome_email=0).insert(ignore_permissions=True)
        update_password(email, passwords[email])
    _insert("RN User Account", account, title=f"[SIMULASI] Demo {AGENCIES[template]}",
            email=email, frappe_user=email, organization=organization, role="member",
            status="active", legacy_source=SOURCE)
    if not frappe.db.exists("RN Organization Membership", {"organization": organization, "user_account": account}):
        _insert("RN Organization Membership", f"dms-demo-member-{template}", organization=organization,
                user_account=account, membership_role="deputy", status="approved", approved_at=CUTOFF)
    return account


def _support(event, points):
    name = event["id"]
    shelters = [point for point in points if point["posko_type"] == "shelter"] or points[:1]
    share, remainder = divmod(event["pengungsi"], len(shelters))
    for index, point in enumerate(shelters):
        population = share + (index < remainder)
        _insert("RN Shelter Occupancy", f"{name}-shelter-{index + 1}", disaster_event=name,
                posko=point["name"], shelter_name=point["title"], capacity_total=population,
                current_occupancy=population, observed_at=CUTOFF, verification_status="verified")

    for index, point in enumerate(shelters):
        _insert("RN Displacement Plan", f"{name}-displacement-{index + 1}", disaster_event=name,
                posko=point["name"], title=f"[SIMULASI] Rencana pengungsian {name}",
                origin_area=event["location"], current_location=point["title"],
                people_count=share + (index < remainder), plan_type="undecided", in_camp=1, status="approved")

    for index in range(event["kebutuhan_kritis"]):
        point = points[index % len(points)]
        item = ITEMS[index % len(ITEMS)]
        _insert("RN Logistic Need", f"{name}-need-{index + 1}", disaster_event=name,
                posko=point["name"], title=f"[SIMULASI] {item}", item_name=item, need_status="open",
                urgency="critical", quantity=100 + 25 * (index % 8), unit="unit", observed_at=CUTOFF)

    for index, point in enumerate(points, 1):
        key = point["name"]
        common = {"disaster_event": name, "posko": key, "observed_at": CUTOFF}
        _insert("RN Stock Observation", f"{key}-stock", **common, title="[SIMULASI] Air minum",
                item_name="Air minum", quantity=200 + 20 * index, quantity_mode="exact",
                unit="liter", stock_state="available")
        _insert("RN Volunteer Profile", f"{key}-volunteer", disaster_event=name, assigned_posko=key,
                observed_at=CUTOFF, volunteer_name=f"[SIMULASI] Relawan {name[-2:]}-{index:02d}",
                main_skill="Evakuasi", skill_category="Evakuasi", availability_status="assigned")
        if point["posko_type"] == "medical":
            _insert("RN Medical Case", f"{key}-medical", **common, patient_code=f"{key}-P1",
                    complaint="Cedera ringan dalam skenario latihan", severity="mild", triage_status="green",
                    case_status="stabilized")

    primary = points[0]
    common = {"disaster_event": name, "posko": primary["name"], "observed_at": CUTOFF}
    _insert("RN Community Report", f"{name}-report", **common, title=f"[SIMULASI] Laporan lapangan {name}",
            description=event["ringkas"], status="verified", location_text=event["location"],
            has_coordinates=1, latitude=primary["lat"], longitude=primary["lng"])
    if event.get("hilang"):
        _insert("RN Missing Person Report", f"{name}-missing", **common, person_code=f"{name}-SAR-01",
                description="Contoh satu kasus dari rekap orang hilang", report_status="missing",
                last_seen_location=event["location"], verification_status="verified")
        _insert("RN Found Person Report", f"{name}-found", **common, person_code=f"{name}-SAR-02",
                description="Contoh temuan tim SAR", report_status="found",
                found_location=event["location"], verification_status="verified")

    _insert("RN Resource Profile", f"{name}-tool", disaster_event=name, owner_type="posko",
            owner_id=primary["name"], resource_name="[SIMULASI] Genset lapangan", resource_type="equipment",
            quantity=2, unit="unit", availability_status="available", current_location=event["location"])
    _insert("RN Comms Frequency", f"{name}-comms", disaster_event=name, observed_at=CUTOFF,
            band_label="[SIMULASI] Jaringan koordinasi lapangan", network_type="vhf", status="baik",
            notes="Kanal latihan. Tidak ada frekuensi siaran operasional.")
    if name == "SIM-DMS-01":
        kitchen = next(p for p in points if p["title"].startswith("Lumbung Sosial"))
        _insert("RN Kitchen Production", f"{name}-kitchen", disaster_event=name, posko=kitchen["name"],
                meal_name="[SIMULASI] Makanan siap saji", portions=12500, production_time=CUTOFF,
                production_status="prepared", observed_at=CUTOFF)

    routes = {
        "SIM-DMS-01": ("Trans Sulawesi km 18", "Jembatan Ponulele"),
        "SIM-DMS-02": ("Akses Radda", "Jalur Baloli–Pombakka"),
        "SIM-DMS-03": (),
    }
    for index, route in enumerate(routes[name], 1):
        _insert("RN Access Status", f"{name}-access-{index}", **common,
                kind="bridge" if route == "Jembatan Ponulele" else "road", place_name=route,
                status="closed", verification_status="verified", valid_until="2026-11-25 23:59:59")
        key = f"{name}-flow-{index}"
        _insert("RN Distribution Flow", key, legacy_id=key, legacy_source=SOURCE, disaster_event=name,
                source_posko=primary["name"], destination_posko=points[index]["name"],
                title=f"[SIMULASI] Distribusi via {route}", item_name="Air minum", quantity=600,
                quantity_mode="exact", unit="liter", flow_status="blocked", observed_at=CUTOFF,
                route_origin=primary["title"], route_destination=route)


def _menus(package, organizations, accounts):
    count = 0
    catalog = _catalog()
    for menu_id, group in package.items():
        if menu_id not in catalog:
            frappe.throw(f"Menu tidak dikenal dalam paket DMS: {menu_id}")
        menu = catalog[menu_id]
        for record in group["records"]:
            event = record.get("disaster_event") or next((code for code in STARTS if any(
                code in value.upper() for value in record.values() if isinstance(value, str)
            )), "SIM-DMS-01")
            if event not in STARTS:
                frappe.throw(f"Kejadian tidak dikenal dalam paket menu {menu_id}.")
            clean = _clean(menu, {key: value for key, value in record.items() if key != "disaster_event"})
            data = json.dumps(clean, ensure_ascii=False, sort_keys=True)
            for template, org in organizations.items():
                if not _allowed(menu, template):
                    continue
                digest = hashlib.sha256(f"{menu_id}|{template}|{event}|{data}".encode()).hexdigest()[:24]
                _insert(DOCTYPE, f"dms-demo-record-{digest}", menu_id=menu_id, organization=org,
                        disaster_event=event, classification=menu["klasifikasi"], status="aktif", data=data,
                        created_by_account=accounts.get(template), updated_by_account=accounts.get(template))
                count += 1
    return count


def run(map_path, menu_path=None, credentials_path=None):
    """Pass CT102 source copies readable by bench. Repeated loads preserve existing seeded rows."""
    source = _read(map_path)
    events = source["events"]
    if {e["id"] for e in events} != set(STARTS) or len(events) != len(STARTS):
        frappe.throw("Paket harus berisi tiga kejadian latihan DMS.")
    if (sum(e["pengungsi"] for e in events), sum(e["kebutuhan_kritis"] for e in events),
        sum(len(e["posko_points"]) for e in events)) != (48250, 37, 24):
        frappe.throw("Total data peta DMS tidak cocok dengan skenario.")
    passwords = _read(credentials_path) if credentials_path else None
    if passwords is not None and (
        set(passwords) != DMS_DEMO_USERS or any(not isinstance(p, str) or len(p) < 32 for p in passwords.values())
    ):
        frappe.throw("Berkas akun demo tidak lengkap atau sandi terlalu lemah.")
    package = _read(menu_path) if menu_path else {}
    organizations = {template: _organization(template) for template in AGENCIES}
    accounts = {template: _account(template, org, passwords) for template, org in organizations.items()} if passwords else {}
    for event in events:
        name = event["id"]
        started, kind = STARTS[name]
        if frappe.db.exists("RN Disaster Event", name) and frappe.db.get_value(
            "RN Disaster Event", name, "drill_scope"
        ) != "dms":
            frappe.throw("ID kejadian latihan sudah dipakai di luar DMS.")
        _insert("RN Disaster Event", name, legacy_id=name, legacy_source=SOURCE, title=event["name"],
                started_at=started, event_type=kind, location_summary=event["location"],
                latitude=event["center"]["lat"], longitude=event["center"]["lng"],
                severity=event["severity"], event_status="active", is_drill=1, drill_scope="dms",
                drill_label="Latihan Gabungan DMS 2026", legacy_payload=json.dumps(event, ensure_ascii=False))
        points = []
        for index, p in enumerate(event["posko_points"], 1):
            key = f"{name}-posko-{index:02d}"
            kind = {"command_center": "command", "distribution": "transport"}.get(p["posko_type"], p["posko_type"])
            _insert("RN Posko", key, legacy_id=key, legacy_source=SOURCE, disaster_event=name,
                    organization=organizations[p["instansi"]], title=f"[SIMULASI] {p['title']}",
                    posko_type=kind, latitude=p["lat"], longitude=p["lng"], notes=p["keterangan"],
                    address=event["location"], operational_status="critical" if p["status"] == "kritis" else "active",
                    rn_fn_logistics=int(kind == "logistics"), rn_fn_shelter=int(kind == "shelter"),
                    rn_fn_kitchen=int(p["title"].startswith("Lumbung Sosial")), public_detail="private",
                    rn_comms_status="connected")
            points.append(dict(p, name=key))
        _support(event, points)
    return {"events": len(events), "poskos": 24, "menus": len(package),
            "records": _menus(package, organizations, accounts), "accounts": len(accounts)}
