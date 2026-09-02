import json
from collections import defaultdict

import frappe
from rescue_net.reference_resolver import resolve_disaster_event, resolve_posko

from frappe.utils import (
    cint,
    flt,
    get_datetime,
    getdate,
    now_datetime,
)

from rescue_net.access_policy import (
    can_manage_posko,
    is_system_manager,
    rn_actor,
)


CONTROL_ROLE = "command_center"

TRANSITIONS = {
    "prepared": {
        "dispatched",
    },
    "dispatched": {
        "distributed",
    },
    "distributed": set(),
}


def _role(actor):
    return getattr(actor, "role", None)


def _actor_name(actor):
    return getattr(actor, "name", None)


def _is_control(actor):
    return bool(
        is_system_manager()
        or _role(actor) == CONTROL_ROLE
    )


def _can_operate(actor, posko):
    return bool(
        _is_control(actor)
        or (
            posko
            and can_manage_posko(
                actor,
                posko,
            )
        )
    )


def _assert_operate(actor, posko):
    if not frappe.db.exists(
        "RN Posko",
        posko,
    ):
        frappe.throw(
            "Posko tidak ditemukan"
        )

    if not _can_operate(actor, posko):
        frappe.throw(
            "Akses Dapur Umum ditolak",
            frappe.PermissionError,
        )


def _allowed_poskos(actor):
    names = frappe.get_all(
        "RN Posko",
        pluck="name",
        limit_page_length=5000,
    )

    if _is_control(actor):
        return names

    return [
        name
        for name in names
        if can_manage_posko(
            actor,
            name,
        )
    ]


def _parse_ingredients(value):
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except Exception:
            frappe.throw(
                "Ingredients harus berupa JSON/list valid"
            )

    if not isinstance(value, list):
        frappe.throw(
            "Ingredients harus berupa list"
        )

    if not value:
        frappe.throw(
            "Minimal satu ingredient diperlukan"
        )

    grouped = defaultdict(float)

    for row in value:
        if not isinstance(row, dict):
            frappe.throw(
                "Format ingredient tidak valid"
            )

        item = (
            str(
                row.get("item_name")
                or ""
            ).strip()
        )

        unit = (
            str(
                row.get("unit")
                or ""
            ).strip()
        )

        qty = flt(
            row.get("quantity")
        )

        if not item or not unit or qty <= 0:
            frappe.throw(
                "Setiap ingredient perlu item_name, quantity, dan unit"
            )

        grouped[
            (item, unit)
        ] += qty

    return [
        {
            "item_name": item,
            "unit": unit,
            "quantity": qty,
        }
        for (
            item,
            unit,
        ), qty
        in sorted(grouped.items())
    ]


def _basis_quantity(row):
    mode = (
        row.quantity_mode
        or "unknown"
    )

    if mode in {
        "exact",
        "estimated",
    }:
        if row.quantity is None:
            return None

        return flt(row.quantity)

    if mode == "range":
        if row.quantity_min is None:
            return None

        return flt(
            row.quantity_min
        )

    return None


def _latest_stock(
    posko,
    item_name,
    unit,
):
    rows = frappe.get_all(
        "RN Stock Observation",
        filters={
            "posko": posko,
            "item_name": item_name,
            "unit": unit,
            "stock_state": "available",
        },
        fields=[
            "name",
            "quantity",
            "quantity_mode",
            "quantity_min",
            "quantity_max",
            "unit",
            "observed_at",
            "source_updated_at",
            "creation",
        ],
        order_by=(
            "observed_at desc, "
            "creation desc"
        ),
        limit_page_length=1,
    )

    return (
        rows[0]
        if rows
        else None
    )


def _stock_state(
    posko,
    item_name,
    unit,
    lock=False,
    strict=True,
):
    row = _latest_stock(
        posko,
        item_name,
        unit,
    )

    if not row:
        if strict:
            frappe.throw(
                f"Belum ada Stock Observation untuk "
                f"{item_name} ({unit})"
            )

        return None

    if lock:
        frappe.db.sql(
            """
            SELECT name
            FROM `tabRN Stock Observation`
            WHERE name = %s
            FOR UPDATE
            """,
            (row.name,),
        )

        row = frappe.db.get_value(
            "RN Stock Observation",
            row.name,
            [
                "name",
                "quantity",
                "quantity_mode",
                "quantity_min",
                "quantity_max",
                "unit",
                "observed_at",
                "source_updated_at",
                "creation",
            ],
            as_dict=True,
        )

    basis = _basis_quantity(
        row
    )

    if basis is None:
        if strict:
            frappe.throw(
                f"Stock {item_name} belum memiliki "
                f"quantity yang dapat dipakai sebagai basis"
            )

        return {
            "stock_observation":
                row.name,
            "quantity_mode":
                row.quantity_mode,
            "basis_quantity":
                None,
            "used_after_snapshot":
                None,
            "available_quantity":
                None,
            "observed_at":
                row.observed_at,
        }

    baseline = (
        row.observed_at
        or row.source_updated_at
        or row.creation
    )

    filters = {
        "posko": posko,
        "item_name": item_name,
        "unit": unit,
        "usage_status": "consumed",
    }

    if baseline:
        filters[
            "consumed_at"
        ] = [
            ">",
            baseline,
        ]

    rows = frappe.get_all(
        "RN Kitchen Ingredient Usage",
        filters=filters,
        fields=[
            "quantity",
        ],
        limit_page_length=5000,
    )

    used = sum(
        flt(x.quantity)
        for x in rows
    )

    available = max(
        basis - used,
        0,
    )

    return {
        "stock_observation":
            row.name,
        "quantity_mode":
            row.quantity_mode,
        "basis_quantity":
            basis,
        "used_after_snapshot":
            used,
        "available_quantity":
            available,
        "observed_at":
            row.observed_at,
    }


@frappe.whitelist()
def create_production(
    posko,
    meal_name,
    portions,
    ingredients,
    disaster_event=None,
    production_time=None,
    target_distribution_location=None,
    notes=None,
):
    # RN_CANONICAL_REF posko = resolve_posko(posko)
    posko = resolve_posko(posko)
    # RN_CANONICAL_REF disaster_event = resolve_disaster_event(disaster_event)
    disaster_event = resolve_disaster_event(disaster_event)
    actor = rn_actor()

    _assert_operate(
        actor,
        posko,
    )

    portions = cint(portions)

    if portions <= 0:
        frappe.throw(
            "Jumlah porsi harus lebih dari 0"
        )

    ingredients = (
        _parse_ingredients(
            ingredients
        )
    )

    when = (
        get_datetime(
            production_time
        )
        if production_time
        else now_datetime()
    )

    stock_states = {}

    # Deterministic order reduces concurrent lock risk.
    for ing in ingredients:
        key = (
            ing["item_name"],
            ing["unit"],
        )

        state = _stock_state(
            posko,
            ing["item_name"],
            ing["unit"],
            lock=True,
            strict=True,
        )

        if (
            ing["quantity"]
            > state[
                "available_quantity"
            ]
        ):
            frappe.throw(
                f"Stok tidak cukup untuk "
                f"{ing['item_name']}. "
                f"Tersedia "
                f"{state['available_quantity']} "
                f"{ing['unit']}"
            )

        stock_states[
            key
        ] = state

    production = frappe.new_doc(
        "RN Kitchen Production"
    )

    production.disaster_event = (
        disaster_event
    )
    production.posko = posko
    production.meal_name = meal_name
    production.portions = portions
    production.production_time = when
    production.target_distribution_location = (
        target_distribution_location
    )
    production.production_status = (
        "prepared"
    )
    production.notes = notes
    production.created_by_user = (
        _actor_name(actor)
    )
    production.verification_status = (
        "self_reported"
    )
    production.observed_at = when

    production.insert(
        ignore_permissions=True
    )

    usages = []

    for ing in ingredients:
        key = (
            ing["item_name"],
            ing["unit"],
        )

        state = stock_states[key]

        use = frappe.new_doc(
            "RN Kitchen Ingredient Usage"
        )

        use.production = production.name
        use.disaster_event = (
            disaster_event
        )
        use.posko = posko
        use.item_name = (
            ing["item_name"]
        )
        use.quantity = (
            ing["quantity"]
        )
        use.unit = ing["unit"]
        use.stock_observation = (
            state[
                "stock_observation"
            ]
        )
        use.stock_quantity_mode = (
            state[
                "quantity_mode"
            ]
        )
        use.stock_basis_quantity = (
            state[
                "basis_quantity"
            ]
        )
        use.available_before = (
            state[
                "available_quantity"
            ]
        )
        use.available_after = max(
            state[
                "available_quantity"
            ]
            - ing["quantity"],
            0,
        )
        use.consumed_at = when
        use.usage_status = "consumed"
        use.verification_status = (
            "self_reported"
        )
        use.notes = (
            f"Used for meal production: "
            f"{meal_name}"
        )

        use.insert(
            ignore_permissions=True
        )

        usages.append({
            "usage": use.name,
            "item_name": use.item_name,
            "quantity": flt(
                use.quantity
            ),
            "unit": use.unit,
            "available_before":
                flt(
                    use.available_before
                ),
            "available_after":
                flt(
                    use.available_after
                ),
            "stock_observation":
                use.stock_observation,
        })

    return {
        "production":
            production.name,
        "status":
            production.production_status,
        "portions":
            production.portions,
        "ingredient_usages":
            usages,
        "stock_observation_updated":
            False,
    }


@frappe.whitelist()
def update_production_status(
    production,
    new_status,
):
    actor = rn_actor()

    doc = frappe.get_doc(
        "RN Kitchen Production",
        production,
    )

    _assert_operate(
        actor,
        doc.posko,
    )

    current = (
        doc.production_status
    )

    if new_status not in (
        TRANSITIONS.get(
            current,
            set(),
        )
    ):
        frappe.throw(
            f"Transisi produksi tidak valid: "
            f"{current} -> {new_status}"
        )

    doc.production_status = (
        new_status
    )

    now = now_datetime()

    if new_status == "dispatched":
        doc.dispatched_at = now

    elif new_status == "distributed":
        doc.distributed_at = now
        doc.verification_status = (
            "distributed"
        )

    doc.save(
        ignore_permissions=True
    )

    return {
        "production": doc.name,
        "previous_status":
            current,
        "status":
            doc.production_status,
    }


@frappe.whitelist()
def effective_stock(
    posko,
    item_name,
    unit,
):
    # RN_CANONICAL_REF posko = resolve_posko(posko)
    posko = resolve_posko(posko)
    actor = rn_actor()

    _assert_operate(
        actor,
        posko,
    )

    state = _stock_state(
        posko,
        item_name,
        unit,
        strict=False,
    )

    return {
        "posko": posko,
        "item_name": item_name,
        "unit": unit,
        "stock": state,
    }


@frappe.whitelist()
def add_evidence(
    linked_doctype,
    linked_name,
    file_url,
    evidence_type="verification",
    caption=None,
):
    supported = {
        "RN Kitchen Production",
        "RN Kitchen Ingredient Usage",
    }

    if linked_doctype not in supported:
        frappe.throw(
            "Objek Dapur Umum tidak didukung"
        )

    if not (file_url or "").startswith(
        "/private/files/"
    ):
        frappe.throw(
            "Evidence Dapur Umum wajib private"
        )

    if not frappe.db.exists(
        linked_doctype,
        linked_name,
    ):
        frappe.throw(
            "Objek tidak ditemukan"
        )

    posko = frappe.db.get_value(
        linked_doctype,
        linked_name,
        "posko",
    )

    actor = rn_actor()

    _assert_operate(
        actor,
        posko,
    )

    now = now_datetime()

    ev = frappe.new_doc(
        "RN Operational Evidence"
    )

    ev.linked_doctype = linked_doctype
    ev.linked_name = linked_name
    ev.posko = posko
    ev.file_url = file_url
    ev.evidence_type = evidence_type
    ev.caption = caption
    ev.observed_at = now
    ev.uploaded_at = now
    ev.uploader_user = _actor_name(actor)
    ev.verification_status = "pending"

    ev.insert(
        ignore_permissions=True
    )

    return {
        "evidence": ev.name,
        "private": True,
    }


@frappe.whitelist(allow_guest=True)
def dashboard(posko=None):
    # RN_CANONICAL_REF posko = resolve_posko(posko)
    posko = resolve_posko(posko)
    actor = rn_actor(required=False)

    allowed = _allowed_poskos(actor)

    if posko:
        # Guests reading a specific posko get a public read-only view of
        # that one posko (same guest-read model as kitchen_board); the
        # manager allow-list only gates authenticated actors.
        if actor and posko not in allowed:
            frappe.throw(
                "Akses Dapur Umum ditolak",
                frappe.PermissionError,
            )

        allowed = [posko]

    if not allowed:
        return {
            "mode": "viewer",
            "productions": [],
            "ingredient_usages": [],
            "stock_summary": [],
        }

    productions = frappe.get_all(
        "RN Kitchen Production",
        filters={
            "posko": ["in", allowed],
        },
        fields=[
            "name",
            "disaster_event",
            "posko",
            "meal_name",
            "portions",
            "production_time",
            "target_distribution_location",
            "production_status",
            "dispatched_at",
            "distributed_at",
            "verification_status",
            "observed_at",
        ],
        order_by="production_time desc, creation desc",
        limit_page_length=2000,
    )

    usages = frappe.get_all(
        "RN Kitchen Ingredient Usage",
        filters={
            "posko": ["in", allowed],
        },
        fields=[
            "name",
            "production",
            "posko",
            "item_name",
            "quantity",
            "unit",
            "stock_observation",
            "stock_quantity_mode",
            "stock_basis_quantity",
            "available_before",
            "available_after",
            "consumed_at",
            "usage_status",
        ],
        order_by="consumed_at desc",
        limit_page_length=5000,
    )

    observations = frappe.get_all(
        "RN Stock Observation",
        filters={
            "posko": ["in", allowed],
            "stock_state": "available",
        },
        fields=[
            "name",
            "posko",
            "item_name",
            "quantity",
            "quantity_mode",
            "quantity_min",
            "quantity_max",
            "unit",
            "observed_at",
            "creation",
        ],
        order_by="observed_at desc, creation desc",
        limit_page_length=5000,
    )

    seen = set()
    stock_summary = []

    for row in observations:
        key = (
            row.posko,
            row.item_name,
            row.unit or "",
        )

        if key in seen:
            continue

        seen.add(key)

        state = _stock_state(
            row.posko,
            row.item_name,
            row.unit,
            strict=False,
        )

        stock_summary.append({
            "posko": row.posko,
            "item_name": row.item_name,
            "unit": row.unit,
            "stock_observation": row.name,
            "quantity_mode": row.quantity_mode,
            "snapshot_quantity": (
                state["basis_quantity"]
                if state else None
            ),
            "kitchen_used_after_snapshot": (
                state["used_after_snapshot"]
                if state else None
            ),
            "effective_available": (
                state["available_quantity"]
                if state else None
            ),
            "observed_at": row.observed_at,
        })

    return {
        "mode": (
            "control"
            if _is_control(actor)
            else "manager"
        ),
        "productions": productions,
        "ingredient_usages": usages,
        "stock_summary": stock_summary,
    }


@frappe.whitelist()
def control_centre_kitchen():
    actor = rn_actor()

    if not _is_control(actor):
        frappe.throw(
            "Akses Control Centre ditolak",
            frappe.PermissionError,
        )

    productions = frappe.get_all(
        "RN Kitchen Production",
        fields=[
            "production_status",
            "portions",
            "posko",
        ],
        limit_page_length=5000,
    )

    usages = frappe.get_all(
        "RN Kitchen Ingredient Usage",
        fields=[
            "item_name",
            "quantity",
            "unit",
        ],
        limit_page_length=10000,
    )

    status = defaultdict(int)
    ingredient_totals = defaultdict(float)

    for row in productions:
        status[
            row.production_status
        ] += 1

    for row in usages:
        ingredient_totals[
            (
                row.item_name,
                row.unit or "",
            )
        ] += flt(
            row.quantity
        )

    return {
        "production_count":
            len(productions),

        "posko_count":
            len({
                row.posko
                for row in productions
                if row.posko
            }),

        "total_portions":
            sum(
                cint(row.portions)
                for row in productions
            ),

        "status":
            dict(status),

        "ingredient_consumption": [
            {
                "item_name": key[0],
                "unit": key[1],
                "quantity": qty,
            }
            for key, qty
            in ingredient_totals.items()
        ],

        "stock_semantics": (
            "RN Stock Observation tetap snapshot. "
            "Kitchen usage adalah consumption event terpisah."
        ),
    }


_GAS_BBM_KEYWORDS = ("gas", "lpg", "solar", "bensin", "bbm", "genset", "elpiji")


def _stock_status(available, basis):
    if available is None:
        return "tidak diketahui"
    if available <= 0:
        return "kritis"
    if basis:
        ratio = available / basis
        if ratio < 0.34:
            return "kritis"
        if ratio < 0.6:
            return "waspada"
    return "aman"


def _drill(title, sub, href):
    return {"title": title, "sub": sub, "href": href}


@frappe.whitelist(allow_guest=True)
def kitchen_board(posko=None, disaster_event=None):
    """Dapur Umum dashboard (matches the DMS mock-up), guest read-only.

    One payload: KPI totals + `<kpi>_items` drill lists, Target Layanan,
    the production donut, the ingredient stock table, today's cook
    schedule + distribution derived from real RN Kitchen Production rows,
    Relawan Dapur (RN Volunteer Profile.assigned_posko), Gas/BBM stock
    filtered by item-name keyword, and the shared evidence strip.
    """
    from rescue_net.api_control_centre import (
        _num,
        _posko_beneficiary,
        event_evidence,
    )

    posko = resolve_posko(posko)
    if not posko or not frappe.db.exists("RN Posko", posko):
        frappe.throw("Posko dapur tidak ditemukan")

    posko_row = frappe.db.get_value(
        "RN Posko",
        posko,
        [
            "name", "title", "posko_type", "operational_status",
            "address", "disaster_event",
        ],
        as_dict=True,
    ) or {}

    event = resolve_disaster_event(
        disaster_event or posko_row.get("disaster_event")
    )

    bene = _posko_beneficiary(posko)
    jiwa = bene["count"]

    productions = frappe.get_all(
        "RN Kitchen Production",
        filters={"posko": posko},
        fields=[
            "name", "meal_name", "portions", "production_time",
            "target_distribution_location", "production_status",
            "dispatched_at", "distributed_at", "notes", "creation",
        ],
        order_by="production_time desc",
        limit_page_length=1000,
    )

    today = getdate()
    for p in productions:
        p.effective_time = p.production_time or p.get("creation")
    daily_totals = defaultdict(int)
    for p in productions:
        if p.effective_time:
            daily_totals[getdate(p.effective_time)] += cint(p.portions)

    today_rows = [
        p for p in productions
        if p.effective_time and getdate(p.effective_time) == today
    ]
    produksi_hari_ini = sum(cint(p.portions) for p in today_rows)
    kapasitas_porsi_hari = max(daily_totals.values()) if daily_totals else produksi_hari_ini
    gap_porsi = max(0, kapasitas_porsi_hari - produksi_hari_ini)

    distribusi_rows = [
        p for p in today_rows
        if p.production_status in ("dispatched", "distributed")
    ]
    distribusi_hari_ini = sum(cint(p.portions) for p in distribusi_rows)

    status_label = {
        "prepared": "Siap Kirim",
        "dispatched": "Dalam Perjalanan",
        "distributed": "Terkirim",
    }

    jadwal_masak = [
        {
            "time": str(p.effective_time)[11:16] if p.effective_time else "-",
            "meal_name": p.meal_name,
            "portions": cint(p.portions),
            "status": p.production_status,
            "status_label": (
                "Selesai" if p.production_status == "distributed"
                else "Proses" if p.production_status == "dispatched"
                else "Menunggu"
            ),
            "href": "evidence.html?event=" + (event or "") +
                    "&object_type=meal_production&object_id=" + p.name,
        }
        for p in sorted(today_rows, key=lambda r: str(r.effective_time or ""))
    ]

    distribusi_list = [
        {
            "tujuan": p.target_distribution_location or "-",
            "waktu": str(p.dispatched_at or p.distributed_at or p.effective_time or "")[11:16],
            "porsi": cint(p.portions),
            "status": p.production_status,
            "status_label": status_label.get(p.production_status, p.production_status),
            "href": "evidence.html?event=" + (event or "") +
                    "&object_type=meal_production&object_id=" + p.name,
        }
        for p in sorted(today_rows, key=lambda r: str(r.effective_time or ""))
    ]

    # Produksi donut: capacity split by today's production status.
    prepared_qty = sum(cint(p.portions) for p in today_rows if p.production_status == "prepared")
    dispatched_qty = sum(cint(p.portions) for p in today_rows if p.production_status == "dispatched")
    distributed_qty = sum(cint(p.portions) for p in today_rows if p.production_status == "distributed")
    sisa_kapasitas = max(0, kapasitas_porsi_hari - produksi_hari_ini)
    donut_total = max(kapasitas_porsi_hari, produksi_hari_ini, 1)

    def _pct(v):
        return round(100.0 * v / donut_total, 1)

    produksi_donut = {
        "total": produksi_hari_ini,
        "kapasitas": kapasitas_porsi_hari,
        "segments": [
            {"key": "distributed", "label": "Terkirim", "value": distributed_qty, "pct": _pct(distributed_qty)},
            {"key": "dispatched", "label": "Dalam Perjalanan", "value": dispatched_qty, "pct": _pct(dispatched_qty)},
            {"key": "prepared", "label": "Siap Kirim", "value": prepared_qty, "pct": _pct(prepared_qty)},
            {"key": "remaining", "label": "Sisa Kapasitas", "value": sisa_kapasitas, "pct": _pct(sisa_kapasitas)},
        ],
    }

    # Stock summary (dedup latest observation per item), reusing effective
    # available quantity via _stock_state (strict=False -> honest "-" when
    # basis unknown instead of throwing).
    observations = frappe.get_all(
        "RN Stock Observation",
        filters={"posko": posko, "stock_state": "available"},
        fields=["name", "item_name", "unit", "observed_at", "creation"],
        order_by="observed_at desc, creation desc",
        limit_page_length=500,
    )
    seen = set()
    stok_bahan = []
    for row in observations:
        key = (row.item_name, row.unit or "")
        if key in seen:
            continue
        seen.add(key)
        state = _stock_state(posko, row.item_name, row.unit, strict=False)
        available = state["available_quantity"] if state else None
        basis = state["basis_quantity"] if state else None
        stok_bahan.append({
            "item_name": row.item_name,
            "unit": row.unit,
            "stok": available,
            "status": _stock_status(available, basis),
            "observed_at": row.observed_at,
        })

    kebutuhan_kritis = [s for s in stok_bahan if s["status"] in ("kritis", "waspada")]
    gas_bbm = [
        s for s in stok_bahan
        if any(k in (s["item_name"] or "").lower() for k in _GAS_BBM_KEYWORDS)
    ]

    # Relawan dapur: volunteers assigned straight to this posko.
    volunteers = frappe.get_all(
        "RN Volunteer Profile",
        filters={"assigned_posko": posko},
        fields=["name", "volunteer_name", "main_skill", "availability_status"],
        limit_page_length=200,
    )
    vol_status_label = {
        "available": "Aktif", "assigned": "Aktif",
        "limited": "Istirahat", "unavailable": "Tidak Aktif",
    }
    relawan_list = [
        {
            "name": v.volunteer_name or v.name,
            "role": v.main_skill or "-",
            "status": v.availability_status,
            "status_label": vol_status_label.get(v.availability_status, "-"),
        }
        for v in volunteers
    ]
    relawan_dapur = {
        "total": len(relawan_list),
        "aktif": sum(1 for v in relawan_list if v["status_label"] == "Aktif"),
        "istirahat": sum(1 for v in relawan_list if v["status_label"] == "Istirahat"),
        "tidak_aktif": sum(1 for v in relawan_list if v["status_label"] == "Tidak Aktif"),
        "list": relawan_list,
    }

    # Evidence strip — same unified feed as Control Centre / Posko Logistik,
    # narrowed to this posko.
    bukti = []
    bukti_last_at = None
    try:
        title_l = str(posko_row.get("title") or "").lower().strip()
        for row in event_evidence(event, limit=80):
            loc = str(row.get("location_text") or "").lower()
            hit = (
                row.get("posko") == posko
                or row.get("linked_object_id") == posko
                or (title_l and len(title_l) > 4 and title_l in loc)
            )
            if hit:
                bukti.append(row)
        bukti.sort(
            key=lambda r: str(r.get("created_at") or r.get("creation") or ""),
            reverse=True,
        )
        bukti = bukti[:8]
        if bukti:
            bukti_last_at = bukti[0].get("created_at") or bukti[0].get("creation")
    except Exception:
        bukti = []

    return {
        "posko": posko_row,
        "disaster_event": event,
        "generated_at": now_datetime(),
        "totals": {
            "jiwa_dilayani": jiwa,
            "kapasitas_porsi_hari": kapasitas_porsi_hari,
            "produksi_hari_ini": produksi_hari_ini,
            "gap_porsi": gap_porsi,
            "bahan_kritis": len(kebutuhan_kritis),
            "distribusi_hari_ini": distribusi_hari_ini,
        },
        "kpi_items": {
            "jiwa_dilayani_items": [
                _drill(posko_row.get("title") or posko, f"{jiwa} jiwa dilayani",
                       "posko-detail.html?id=" + posko + "&event=" + (event or "")),
            ],
            "produksi_hari_ini_items": [
                _drill(p.meal_name, f"{cint(p.portions)} porsi · {status_label.get(p.production_status, p.production_status)}",
                       "evidence.html?event=" + (event or "") + "&object_type=meal_production&object_id=" + p.name)
                for p in today_rows
            ],
            "bahan_kritis_items": [
                _drill(s["item_name"], f"Stok {s['stok']} {s['unit']} · {s['status']}",
                       "posko-logistik.html?id=" + posko + "&event=" + (event or ""))
                for s in kebutuhan_kritis
            ],
            "distribusi_hari_ini_items": [
                _drill(d["tujuan"], f"{d['porsi']} porsi · {d['status_label']}", d["href"])
                for d in distribusi_list
            ],
        },
        "target_layanan": {
            "total_target": kapasitas_porsi_hari,
            "target_jiwa": jiwa,
            "rasio_label": (
                f"1 porsi : {round(jiwa / kapasitas_porsi_hari, 2)} jiwa"
                if kapasitas_porsi_hari and jiwa else "-"
            ),
        },
        "produksi_donut": produksi_donut,
        "stok_bahan": stok_bahan,
        "kebutuhan_kritis": kebutuhan_kritis,
        "jadwal_masak": jadwal_masak,
        "distribusi_hari_ini_list": distribusi_list,
        "relawan_dapur": relawan_dapur,
        "gas_bbm": gas_bbm,
        "bukti": bukti,
        "bukti_total": len(bukti),
        "bukti_last_at": bukti_last_at,
    }
