import os
import json
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import psycopg
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from routes.auth_routes import router as auth_router

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://rescuenet_user@localhost:5432/rescuenet_db",
)
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "/data/uploads"))

app = FastAPI(
    title="Rescue-Net API",
    description="Open Disaster Coordination & Relief Management System",
    version="0.1.0",
)
app.include_router(auth_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


RBAC_MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
RBAC_PUBLIC_PREFIXES = (
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/auth/",
    "/public/",
)
RBAC_ROLE_ACTIONS = {
    "command_center": {"*"},
    "posko_operator": {
        "stock", "distribution", "evidence", "sync", "resource_request",
        "resource_profile", "volunteer_assignment"
    },
    "medical_operator": {"medical", "evidence", "sync"},
    "shelter_operator": {"shelter", "evidence", "sync"},
    "donor": {"aid_offer", "donor_program", "evidence", "sync"},
    "volunteer": {"sync"},
    "viewer": set(),
}


def rbac_enabled():
    return os.getenv("RN_ENFORCE_RBAC", "false").lower() in {"1", "true", "yes", "on"}


def classify_path_action(path: str):
    if "evidence" in path:
        return "evidence"
    if "sync" in path:
        return "sync"
    if "stock" in path or "posko" in path or "logistic" in path or "kitchen" in path:
        return "stock"
    if "distribution" in path or "transport" in path:
        return "distribution"
    if "medical" in path:
        return "medical"
    if "shelter" in path:
        return "shelter"
    if "donor-program" in path or "special-program" in path or "recovery" in path:
        return "donor_program"
    if "aid-offer" in path:
        return "aid_offer"
    if "resource-profile" in path or "resource-profiles" in path:
        return "resource_profile"
    if "resource-request" in path:
        return "resource_request"
    if "volunteer-assignment" in path:
        return "volunteer_assignment"
    if "verification" in path:
        return "verify"
    return "general_mutation"


def role_allows_path(role: str, path: str):
    allowed = RBAC_ROLE_ACTIONS.get(role, set())
    if "*" in allowed:
        return True
    return classify_path_action(path) in allowed


@app.middleware("http")
async def optional_rbac_middleware(request: Request, call_next):
    if not rbac_enabled() or request.method not in RBAC_MUTATING_METHODS:
        return await call_next(request)

    path = request.url.path
    if path == "/" or any(path == p or path.startswith(p) for p in RBAC_PUBLIC_PREFIXES):
        return await call_next(request)

    session_token = request.headers.get("X-RN-Session-Token")
    role = request.headers.get("X-RN-Role") or "viewer"

    if not session_token:
        raise HTTPException(status_code=401, detail="Session token required")

    if not role_allows_path(role, path):
        raise HTTPException(status_code=403, detail=f"Role {role} is not allowed to mutate {path}")

    return await call_next(request)

def get_conn():
    return psycopg.connect(DATABASE_URL)

def rows_to_dicts(cur):
    cols = [d.name for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def make_edit_code():
    return str(secrets.randbelow(900000) + 100000)

def hash_edit_code(donor_contact: str, edit_code: str):
    raw = f"{donor_contact}|{edit_code}|rescue-net-v1"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

def normalize_public_aid_status(delivery_mode: str, status: str = "available"):
    if delivery_mode == "need_pickup":
        return "need_pickup"
    if delivery_mode == "self_deliver_to_posko":
        return "self_delivery_planned"
    if delivery_mode == "drop_to_collection_point":
        return "drop_to_collection_point"
    return status

def init_db():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
            CREATE TABLE IF NOT EXISTS disaster_events (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                disaster_type TEXT NOT NULL,
                location TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                severity TEXT NOT NULL DEFAULT 'normal',
                created_at TIMESTAMP NOT NULL DEFAULT NOW()
            );
            """)
            cur.execute("""
            CREATE TABLE IF NOT EXISTS organizations (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                organization_type TEXT NOT NULL,
                trust_level TEXT NOT NULL DEFAULT 'unverified',
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TIMESTAMP NOT NULL DEFAULT NOW()
            );
            """)
            cur.execute("""
            CREATE TABLE IF NOT EXISTS posko_nodes (
                id TEXT PRIMARY KEY,
                disaster_event_id TEXT NOT NULL REFERENCES disaster_events(id) ON DELETE CASCADE,
                organization_id TEXT REFERENCES organizations(id) ON DELETE SET NULL,
                name TEXT NOT NULL,
                node_type TEXT NOT NULL,
                location TEXT NOT NULL,
                verification_status TEXT NOT NULL DEFAULT 'self_reported',
                operational_status TEXT NOT NULL DEFAULT 'active',
                created_at TIMESTAMP NOT NULL DEFAULT NOW()
            );
            """)
            cur.execute("""
            CREATE TABLE IF NOT EXISTS volunteers (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                phone TEXT,
                email TEXT,
                main_skill TEXT NOT NULL,
                location TEXT NOT NULL,
                availability TEXT NOT NULL DEFAULT 'available',
                duration_available TEXT,
                verification_status TEXT NOT NULL DEFAULT 'self_reported',
                created_at TIMESTAMP NOT NULL DEFAULT NOW()
            );
            """)
            cur.execute("""
            CREATE TABLE IF NOT EXISTS logistic_needs (
                id TEXT PRIMARY KEY,
                disaster_event_id TEXT NOT NULL REFERENCES disaster_events(id) ON DELETE CASCADE,
                node_id TEXT REFERENCES posko_nodes(id) ON DELETE SET NULL,
                item_name TEXT NOT NULL,
                quantity_needed NUMERIC NOT NULL,
                unit TEXT NOT NULL,
                priority TEXT NOT NULL DEFAULT 'normal',
                needed_before TEXT,
                status TEXT NOT NULL DEFAULT 'open',
                created_at TIMESTAMP NOT NULL DEFAULT NOW()
            );
            """)
            cur.execute("""
            CREATE TABLE IF NOT EXISTS aid_offers (
                id TEXT PRIMARY KEY,
                disaster_event_id TEXT NOT NULL REFERENCES disaster_events(id) ON DELETE CASCADE,
                donor_name TEXT NOT NULL,
                item_name TEXT NOT NULL,
                quantity NUMERIC NOT NULL,
                unit TEXT NOT NULL,
                pickup_location TEXT NOT NULL,
                ready_at TEXT,
                status TEXT NOT NULL DEFAULT 'available',
                created_at TIMESTAMP NOT NULL DEFAULT NOW()
            );
            """)
            cur.execute("""
            CREATE TABLE IF NOT EXISTS transport_spaces (
                id TEXT PRIMARY KEY,
                disaster_event_id TEXT NOT NULL REFERENCES disaster_events(id) ON DELETE CASCADE,
                provider_name TEXT NOT NULL,
                transport_type TEXT NOT NULL,
                route_origin TEXT NOT NULL,
                route_destination TEXT NOT NULL,
                capacity_weight_kg NUMERIC DEFAULT 0,
                capacity_volume_m3 NUMERIC DEFAULT 0,
                departure_time TEXT,
                eta TEXT,
                status TEXT NOT NULL DEFAULT 'available',
                created_at TIMESTAMP NOT NULL DEFAULT NOW()
            );
            """)
            cur.execute("""
            CREATE TABLE IF NOT EXISTS distribution_flows (
                id TEXT PRIMARY KEY,
                disaster_event_id TEXT NOT NULL REFERENCES disaster_events(id) ON DELETE CASCADE,
                need_id TEXT REFERENCES logistic_needs(id) ON DELETE SET NULL,
                aid_offer_id TEXT REFERENCES aid_offers(id) ON DELETE SET NULL,
                transport_space_id TEXT REFERENCES transport_spaces(id) ON DELETE SET NULL,
                destination_node_id TEXT REFERENCES posko_nodes(id) ON DELETE SET NULL,
                eta_final TEXT,
                status TEXT NOT NULL DEFAULT 'planned',
                created_at TIMESTAMP NOT NULL DEFAULT NOW()
            );
            """)
            cur.execute("""
            CREATE TABLE IF NOT EXISTS evidence_files (
                id TEXT PRIMARY KEY,
                disaster_event_id TEXT,
                node_id TEXT,
                linked_object_type TEXT NOT NULL,
                linked_object_id TEXT,
                evidence_type TEXT NOT NULL,
                filename TEXT NOT NULL,
                file_path TEXT NOT NULL,
                mime_type TEXT,
                size_bytes BIGINT DEFAULT 0,
                uploaded_by TEXT,
                verification_status TEXT NOT NULL DEFAULT 'pending',
                created_at TIMESTAMP NOT NULL DEFAULT NOW()
            );
            """)
        conn.commit()

def seed_db():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM disaster_events;")
            if cur.fetchone()[0] == 0:
                cur.execute("""
                INSERT INTO disaster_events (id, name, disaster_type, location, status, severity)
                VALUES
                ('event-aceh-2025', 'Gempa Aceh Barat 2025', 'earthquake', 'Aceh Barat, Aceh', 'active', 'critical'),
                ('event-luwu-2025', 'Banjir Luwu 2025', 'flood', 'Luwu Utara', 'active', 'urgent');
                """)
                cur.execute("""
                INSERT INTO organizations (id, name, organization_type, trust_level, status)
                VALUES
                ('org-bpbd-aceh', 'BPBD Aceh Barat', 'government', 'official', 'verified'),
                ('org-landrover', 'Land Rover Rescue Community', 'community', 'trusted', 'verified');
                """)
                cur.execute("""
                INSERT INTO posko_nodes
                (id, disaster_event_id, organization_id, name, node_type, location, verification_status, operational_status)
                VALUES
                ('posko-logistik-aceh', 'event-aceh-2025', 'org-bpbd-aceh', 'Posko Logistik Aceh Barat Utama', 'logistics', 'Aceh Barat', 'official_verified', 'active'),
                ('posko-dapur-melati', 'event-aceh-2025', NULL, 'Dapur Ibu-Ibu Gang Melati', 'kitchen', 'Gang Melati', 'community_verified', 'active');
                """)
                cur.execute("""
                INSERT INTO volunteers
                (id, name, phone, email, main_skill, location, availability, duration_available, verification_status)
                VALUES
                ('vol-rudi', 'Rudi', '0800000001', 'rudi@example.local', 'Driver MPV / Pickup', 'Depok', 'available today 12:00-18:00', '6 jam', 'phone_verified'),
                ('vol-rina', 'dr. Rina', '0800000002', 'rina@example.local', 'Dokter umum', 'Jakarta', 'available 7 days', '7 hari', 'medical_verified');
                """)
                cur.execute("""
                INSERT INTO logistic_needs
                (id, disaster_event_id, node_id, item_name, quantity_needed, unit, priority, needed_before, status)
                VALUES
                ('need-water-aceh', 'event-aceh-2025', 'posko-logistik-aceh', 'Air Minum', 18240, 'liter', 'critical', 'Hari ini 18:00', 'open'),
                ('need-baby-food', 'event-aceh-2025', 'posko-logistik-aceh', 'Makanan Bayi', 442, 'kaleng', 'critical', 'Hari ini 16:00', 'open');
                """)
                cur.execute("""
                INSERT INTO aid_offers
                (id, disaster_event_id, donor_name, item_name, quantity, unit, pickup_location, ready_at, status)
                VALUES
                ('aid-water-andi', 'event-aceh-2025', 'Donasi Bpk. Andi', 'Air Mineral', 500, 'dus', 'Jakarta Selatan', 'Hari ini 13:00', 'need_pickup');
                """)
                cur.execute("""
                INSERT INTO transport_spaces
                (id, disaster_event_id, provider_name, transport_type, route_origin, route_destination, capacity_weight_kg, capacity_volume_m3, departure_time, eta, status)
                VALUES
                ('transport-landrover-01', 'event-aceh-2025', 'Land Rover Rescue', 'darat', 'Jakarta Selatan', 'Bandara Halim', 2000, 8, 'Hari ini 13:30', 'Hari ini 14:30', 'available');
                """)
        conn.commit()

@app.on_event("startup")
def startup():
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    init_db()
    seed_db()

class DisasterCreate(BaseModel):
    name: str
    disaster_type: str
    location: str
    status: str = "active"
    severity: str = "normal"

class OrganizationCreate(BaseModel):
    name: str
    organization_type: str
    trust_level: str = "unverified"
    status: str = "pending"

class PoskoCreate(BaseModel):
    disaster_event_id: str
    name: str
    node_type: str
    location: str
    organization_id: Optional[str] = None
    verification_status: str = "self_reported"
    operational_status: str = "active"

class DeviceRegistrationCreate(BaseModel):
    disaster_event_id: str = "event-sim-001"
    local_id: Optional[str] = None
    device_id: Optional[str] = None
    organization_name: str
    member_name: Optional[str] = None
    role: str = "posko_operator"
    posko_name: Optional[str] = None
    notes: Optional[str] = None
    location_text: Optional[str] = None
    area_level: Optional[str] = None
    province_name: Optional[str] = None
    city_name: Optional[str] = None
    district_name: Optional[str] = None
    village_name: Optional[str] = None
    admin_area_id: Optional[str] = None
    verifier_mode: Optional[str] = "none"
    requested_verifier_id: Optional[str] = None
    requested_verifier_name: Optional[str] = None
    requested_verifier_phone: Optional[str] = None
    requested_verifier_email: Optional[str] = None
    verifier_relationship: Optional[str] = None

class VolunteerCreate(BaseModel):
    name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    main_skill: str
    location: str
    availability: str = "available"
    duration_available: Optional[str] = None
    verification_status: str = "self_reported"


class TransportSpaceCreate(BaseModel):
    disaster_event_id: str
    provider_name: str
    transport_type: str
    route_origin: str
    route_destination: str
    capacity_weight_kg: float = 0
    capacity_volume_m3: float = 0
    departure_time: Optional[str] = None
    eta: Optional[str] = None
    status: str = "available"

class DistributionFlowCreate(BaseModel):
    disaster_event_id: str
    need_id: Optional[str] = None
    aid_offer_id: Optional[str] = None
    transport_space_id: Optional[str] = None
    destination_node_id: Optional[str] = None
    eta_final: Optional[str] = None
    status: str = "planned"


class PublicAidOfferCreate(BaseModel):
    disaster_event_id: str
    donor_name: str
    donor_contact: str
    item_name: str
    quantity: float
    unit: str
    pickup_location: str
    ready_at: Optional[str] = None
    delivery_mode: str = "need_pickup"
    target_node_id: Optional[str] = None
    target_node_name: Optional[str] = None
    expected_arrival_at: Optional[str] = None
    notes: Optional[str] = None

class PublicAidOfferVerifyEdit(BaseModel):
    aid_offer_id: str
    donor_contact: str
    edit_code: str

class PublicAidOfferUpdate(BaseModel):
    donor_contact: str
    edit_code: str
    donor_name: Optional[str] = None
    item_name: Optional[str] = None
    quantity: Optional[float] = None
    unit: Optional[str] = None
    pickup_location: Optional[str] = None
    ready_at: Optional[str] = None
    delivery_mode: Optional[str] = None
    target_node_id: Optional[str] = None
    target_node_name: Optional[str] = None
    expected_arrival_at: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[str] = None


class LogisticNeedCreate(BaseModel):
    disaster_event_id: str
    node_id: Optional[str] = None
    item_name: str
    quantity_needed: float
    unit: str
    priority: str = "normal"
    needed_before: Optional[str] = None
    status: str = "open"


class AidOfferCreate(BaseModel):
    disaster_event_id: str
    donor_name: str
    donor_contact: Optional[str] = None
    item_name: str
    quantity: float
    unit: str
    pickup_location: str
    ready_at: Optional[str] = None
    delivery_mode: str = "need_pickup"
    target_node_id: Optional[str] = None
    target_node_name: Optional[str] = None
    expected_arrival_at: Optional[str] = None
    notes: Optional[str] = None
    status: str = "available"


class UnitConversionCreate(BaseModel):
    item_name: Optional[str] = None
    from_unit: str
    to_unit: str
    multiplier: float
    confidence_level: Optional[str] = "operator_defined"
    source: Optional[str] = "operator"
    notes: Optional[str] = None


class UnitNormalizeRequest(BaseModel):
    item_name: str
    quantity: float
    unit: str


def clean_unit(value: Optional[str]):
    return (value or "").strip().lower().replace("_", " ")


def clean_item(value: Optional[str]):
    return (value or "").strip().lower()


def ensure_unit_normalization_tables():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
            CREATE TABLE IF NOT EXISTS stock_movements (
                id TEXT PRIMARY KEY,
                disaster_event_id TEXT NOT NULL REFERENCES disaster_events(id) ON DELETE CASCADE,
                posko_id TEXT NOT NULL,
                item_name TEXT NOT NULL,
                quantity NUMERIC NOT NULL,
                unit TEXT NOT NULL,
                movement_type TEXT NOT NULL DEFAULT 'stock_in',
                movement_direction TEXT NOT NULL DEFAULT 'in',
                source_type TEXT,
                source_id TEXT,
                destination_type TEXT,
                destination_id TEXT,
                related_aid_offer_id TEXT,
                related_distribution_flow_id TEXT,
                related_logistic_need_id TEXT,
                notes TEXT,
                evidence_file_id TEXT,
                owner_type TEXT DEFAULT 'posko',
                owner_id TEXT,
                visibility_scope TEXT DEFAULT 'disaster_ecosystem',
                access_policy TEXT DEFAULT 'request_required',
                verification_status TEXT DEFAULT 'self_reported',
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
                deleted_at TIMESTAMP
            );
            """)
            cur.execute("""
            CREATE TABLE IF NOT EXISTS item_catalog (
                id TEXT PRIMARY KEY,
                item_name TEXT NOT NULL UNIQUE,
                category TEXT,
                base_unit TEXT,
                aliases_json JSONB NOT NULL DEFAULT '[]',
                notes TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW()
            );
            """)
            cur.execute("""
            CREATE TABLE IF NOT EXISTS unit_conversions (
                id TEXT PRIMARY KEY,
                item_name TEXT,
                from_unit TEXT NOT NULL,
                to_unit TEXT NOT NULL,
                multiplier NUMERIC NOT NULL,
                confidence_level TEXT NOT NULL DEFAULT 'operator_defined',
                source TEXT NOT NULL DEFAULT 'operator',
                notes TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW()
            );
            """)
            cur.execute("ALTER TABLE item_catalog ADD COLUMN IF NOT EXISTS category TEXT;")
            cur.execute("ALTER TABLE item_catalog ADD COLUMN IF NOT EXISTS base_unit TEXT;")
            cur.execute("ALTER TABLE item_catalog ADD COLUMN IF NOT EXISTS aliases_json JSONB NOT NULL DEFAULT '[]';")
            cur.execute("ALTER TABLE item_catalog ADD COLUMN IF NOT EXISTS notes TEXT;")
            cur.execute("ALTER TABLE item_catalog ADD COLUMN IF NOT EXISTS created_at TIMESTAMP NOT NULL DEFAULT NOW();")
            cur.execute("ALTER TABLE item_catalog ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP NOT NULL DEFAULT NOW();")
            cur.execute("ALTER TABLE unit_conversions ADD COLUMN IF NOT EXISTS item_name TEXT;")
            cur.execute("ALTER TABLE unit_conversions ADD COLUMN IF NOT EXISTS confidence_level TEXT NOT NULL DEFAULT 'operator_defined';")
            cur.execute("ALTER TABLE unit_conversions ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT 'operator';")
            cur.execute("ALTER TABLE unit_conversions ADD COLUMN IF NOT EXISTS notes TEXT;")
            cur.execute("ALTER TABLE unit_conversions ADD COLUMN IF NOT EXISTS created_at TIMESTAMP NOT NULL DEFAULT NOW();")
            cur.execute("ALTER TABLE unit_conversions ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP NOT NULL DEFAULT NOW();")
            for table, qty_col in (("stock_movements", "quantity"), ("aid_offers", "quantity"), ("logistic_needs", "quantity_needed")):
                savepoint = f"unit_alter_{table}"
                cur.execute(f"SAVEPOINT {savepoint};")
                try:
                    cur.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS original_quantity NUMERIC;")
                    cur.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS original_unit TEXT;")
                    cur.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS normalized_quantity NUMERIC;")
                    cur.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS normalized_unit TEXT;")
                    cur.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS conversion_status TEXT NOT NULL DEFAULT 'not_normalized';")
                    cur.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS conversion_factor NUMERIC;")
                    cur.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS conversion_notes TEXT;")
                    cur.execute(f"RELEASE SAVEPOINT {savepoint};")
                except psycopg.errors.InsufficientPrivilege:
                    cur.execute(f"ROLLBACK TO SAVEPOINT {savepoint};")
                    cur.execute(f"RELEASE SAVEPOINT {savepoint};")
                    continue
            cur.execute("CREATE INDEX IF NOT EXISTS idx_unit_conversions_lookup ON unit_conversions(item_name, from_unit, to_unit);")
            seed_unit_normalization(cur)
            conn.commit()


def seed_unit_normalization(cur):
    catalog_rows = [
        ("cat-air-mineral", "air mineral", "water", "liter", ["air minum", "aqua", "air kemasan"]),
        ("cat-beras", "beras", "food", "kg", ["rice"]),
        ("cat-mie-instan", "mie instan", "food", "pcs", ["mi instan", "instant noodle"]),
        ("cat-nasi-bungkus", "nasi bungkus", "food", "porsi", ["makanan siap saji", "meal box"]),
        ("cat-selimut", "selimut", "shelter", "pcs", ["blanket"]),
    ]
    for item_id, item_name, category, base_unit, aliases in catalog_rows:
        cur.execute("""
        INSERT INTO item_catalog (id, item_name, category, base_unit, aliases_json)
        VALUES (%s,%s,%s,%s,%s)
        ON CONFLICT (id) DO NOTHING;
        """, (item_id, item_name, category, base_unit, json.dumps(aliases)))

    conversion_rows = [
        ("conv-air-dus-botol", "air mineral", "dus", "botol", 24, "common_packaging", "Common bottled water carton; verify brand/size if used for liters."),
        ("conv-air-dus-liter", "air mineral 600ml", "dus", "liter", 14.4, "brand_size_specific", "24 bottles x 600ml."),
        ("conv-beras-karung-kg", "beras", "karung", "kg", 25, "operator_default", "Default disaster logistics estimate; adjust when sack size differs."),
        ("conv-mie-dus-pcs", "mie instan", "dus", "pcs", 40, "common_packaging", "Common carton size; verify brand."),
        ("conv-nasi-kantong-porsi", "nasi bungkus", "kantong plastik", "porsi", 10, "operator_estimate", "Estimate only; operator should verify actual contents."),
    ]
    for conv_id, item_name, from_unit, to_unit, multiplier, confidence, notes in conversion_rows:
        cur.execute("""
        INSERT INTO unit_conversions
        (id, item_name, from_unit, to_unit, multiplier, confidence_level, source, notes)
        VALUES (%s,%s,%s,%s,%s,%s,'rn_seed',%s)
        ON CONFLICT (id) DO NOTHING;
        """, (conv_id, item_name, from_unit, to_unit, multiplier, confidence, notes))


def normalize_quantity(cur, item_name: str, quantity: float, unit: str):
    clean_from = clean_unit(unit)
    item_key = clean_item(item_name)
    canonical_units = {"kg", "liter", "l", "pcs", "unit", "paket", "porsi", "botol", "orang", "kk"}
    if clean_from == "l":
        clean_from = "liter"
    if clean_from in canonical_units:
        return {
            "original_quantity": quantity,
            "original_unit": unit,
            "normalized_quantity": quantity,
            "normalized_unit": clean_from,
            "conversion_status": "same_unit",
            "conversion_factor": 1,
            "conversion_notes": "Unit already treated as canonical."
        }

    cur.execute("""
    SELECT *
    FROM unit_conversions
    WHERE from_unit = %s
      AND (item_name IS NULL OR %s ILIKE ('%%' || item_name || '%%') OR item_name ILIKE ('%%' || %s || '%%'))
    ORDER BY CASE WHEN item_name IS NULL THEN 1 ELSE 0 END, updated_at DESC
    LIMIT 1;
    """, (clean_from, item_key, item_key))
    rows = rn_rows_to_dicts(cur)
    if rows:
        conv = rows[0]
        factor = float(conv["multiplier"])
        return {
            "original_quantity": quantity,
            "original_unit": unit,
            "normalized_quantity": quantity * factor,
            "normalized_unit": conv["to_unit"],
            "conversion_status": "converted",
            "conversion_factor": factor,
            "conversion_notes": f"{conv.get('confidence_level')}: {conv.get('notes') or ''}".strip()
        }
    return {
        "original_quantity": quantity,
        "original_unit": unit,
        "normalized_quantity": None,
        "normalized_unit": None,
        "conversion_status": "needs_unit_review",
        "conversion_factor": None,
        "conversion_notes": f"No trusted conversion for '{unit}' and item '{item_name}'. Keep original value; do not auto-sum."
    }


@app.get("/unit-catalog")
def list_unit_catalog():
    try:
        ensure_unit_normalization_tables()
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM item_catalog ORDER BY item_name;")
            items = rows_to_dicts(cur)
            cur.execute("SELECT * FROM unit_conversions ORDER BY COALESCE(item_name, ''), from_unit, to_unit;")
            conversions = rows_to_dicts(cur)
        return {"items": items, "conversions": conversions}
    except Exception as exc:
        return {
            "status": "error",
            "error_type": exc.__class__.__name__,
            "detail": str(exc)
        }


@app.post("/unit-conversions")
def create_unit_conversion(payload: UnitConversionCreate):
    ensure_unit_normalization_tables()
    conv_id = "conv-" + uuid.uuid4().hex[:12]
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
        INSERT INTO unit_conversions
        (id, item_name, from_unit, to_unit, multiplier, confidence_level, source, notes)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        RETURNING *;
        """, (
            conv_id, clean_item(payload.item_name) or None, clean_unit(payload.from_unit),
            clean_unit(payload.to_unit), payload.multiplier, payload.confidence_level,
            payload.source, payload.notes
        ))
        row = rows_to_dicts(cur)[0]
        conn.commit()
    return {"status": "created", "unit_conversion": row}


@app.post("/unit-normalize")
def unit_normalize(payload: UnitNormalizeRequest):
    try:
        ensure_unit_normalization_tables()
        with get_conn() as conn, conn.cursor() as cur:
            return normalize_quantity(cur, payload.item_name, payload.quantity, payload.unit)
    except Exception as exc:
        return {
            "status": "error",
            "error_type": exc.__class__.__name__,
            "detail": str(exc)
        }


@app.get("/unit-review")
def unit_review(disaster_event_id: str = "event-sim-001"):
    ensure_unit_normalization_tables()
    result = {"logistic_needs": [], "aid_offers": [], "stock_movements": []}
    with get_conn() as conn, conn.cursor() as cur:
        def has_columns(table, columns):
            cur.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = %s;
            """, (table,))
            existing = {row["column_name"] for row in rows_to_dicts(cur)}
            return all(col in existing for col in columns)

        if has_columns("logistic_needs", {"conversion_status", "conversion_notes"}):
            cur.execute("""
            SELECT id, item_name, quantity_needed AS quantity, unit, conversion_status, conversion_notes, created_at
            FROM logistic_needs
            WHERE disaster_event_id = %s AND conversion_status = 'needs_unit_review'
            ORDER BY created_at DESC
            LIMIT 100;
            """, (disaster_event_id,))
            result["logistic_needs"] = rows_to_dicts(cur)
        if has_columns("aid_offers", {"conversion_status", "conversion_notes"}):
            cur.execute("""
            SELECT id, item_name, quantity, unit, conversion_status, conversion_notes, created_at
            FROM aid_offers
            WHERE disaster_event_id = %s AND conversion_status = 'needs_unit_review'
            ORDER BY created_at DESC
            LIMIT 100;
            """, (disaster_event_id,))
            result["aid_offers"] = rows_to_dicts(cur)
        if has_columns("stock_movements", {"conversion_status", "conversion_notes", "deleted_at"}):
            cur.execute("""
            SELECT id, posko_id, item_name, quantity, unit, conversion_status, conversion_notes, created_at
            FROM stock_movements
            WHERE disaster_event_id = %s AND conversion_status = 'needs_unit_review' AND deleted_at IS NULL
            ORDER BY created_at DESC
            LIMIT 100;
            """, (disaster_event_id,))
            result["stock_movements"] = rows_to_dicts(cur)
    result["total"] = sum(len(v) for v in result.values() if isinstance(v, list))
    return result


@app.get("/central-data/status")
def central_data_status(disaster_event_id: str = "event-sim-001"):
    try:
        ensure_location_resolution_tables()
        ensure_community_report_tables()
        ensure_unit_normalization_tables()
        summary = data_consolidation_summary(disaster_event_id)
        unit = unit_review(disaster_event_id)
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM logistic_needs WHERE disaster_event_id = %s AND status = 'open';", (disaster_event_id,))
            open_needs = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM aid_offers WHERE disaster_event_id = %s;", (disaster_event_id,))
            aid_offers = cur.fetchone()[0]
            cur.execute("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'stock_movements');")
            stock_exists = cur.fetchone()[0]
            stock_movements = 0
            if stock_exists:
                cur.execute("SELECT COUNT(*) FROM stock_movements WHERE disaster_event_id = %s;", (disaster_event_id,))
                stock_movements = cur.fetchone()[0]
        return {
            "status": "ok",
            "disaster_event_id": disaster_event_id,
            "central_data_ready": unit["total"] == 0,
            "summary": summary,
            "counts": {
                "open_logistic_needs": open_needs,
                "aid_offers": aid_offers,
                "stock_movements": stock_movements
            },
            "unit_review_total": unit["total"],
            "unit_policy": "Preserve original units. Convert only when a trusted conversion exists. Unknown local packaging stays in review and must not be auto-summed."
        }
    except Exception as exc:
        return {"status": "error", "error_type": exc.__class__.__name__, "detail": str(exc)}


class SyncConflictResolve(BaseModel):
    resolution_status: str = "resolved"
    resolved_by: Optional[str] = None


@app.get("/")
def root():
    return {"system": "Rescue-Net", "version": "0.1.0", "status": "running"}

@app.get("/health")
def health():
    return {"status": "ok", "time": datetime.utcnow().isoformat()}


@app.get("/audit-events")
def list_audit_events(
    disaster_event_id: Optional[str] = None,
    object_table: Optional[str] = None,
    object_id: Optional[str] = None,
    actor_user_id: Optional[str] = None,
    limit: int = 100,
):
    limit = max(1, min(limit, 500))
    where = []
    params = []

    if disaster_event_id:
        where.append("disaster_event_id = %s")
        params.append(disaster_event_id)
    if object_table:
        where.append("object_table = %s")
        params.append(object_table)
    if object_id:
        where.append("object_id = %s")
        params.append(object_id)
    if actor_user_id:
        where.append("actor_user_id = %s")
        params.append(actor_user_id)

    sql = "SELECT * FROM audit_events"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY created_at DESC LIMIT %s"
    params.append(limit)

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        return rows_to_dicts(cur)


@app.get("/sync-conflicts")
def list_sync_conflicts(resolution_status: Optional[str] = None, limit: int = 100):
    limit = max(1, min(limit, 500))
    where = []
    params = []

    if resolution_status:
        where.append("resolution_status = %s")
        params.append(resolution_status)

    sql = "SELECT * FROM sync_conflicts"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY created_at DESC LIMIT %s"
    params.append(limit)

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        return rows_to_dicts(cur)


@app.post("/sync-conflicts/{conflict_id}/resolve")
def resolve_sync_conflict(conflict_id: str, payload: SyncConflictResolve):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
        UPDATE sync_conflicts
        SET resolution_status = %s,
            resolved_by = %s,
            resolved_at = NOW()
        WHERE id = %s
        RETURNING *;
        """, (payload.resolution_status, payload.resolved_by, conflict_id))
        rows = rows_to_dicts(cur)
        conn.commit()

    if not rows:
        raise HTTPException(status_code=404, detail="Sync conflict not found")

    return {"status": "updated", "sync_conflict": rows[0]}

@app.get("/disasters")
def get_disasters():
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM disaster_events ORDER BY created_at DESC;")
        return rows_to_dicts(cur)

@app.post("/disasters")
def create_disaster(payload: DisasterCreate):
    item_id = "event-" + uuid.uuid4().hex[:12]
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
        INSERT INTO disaster_events (id, name, disaster_type, location, status, severity)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING *;
        """, (item_id, payload.name, payload.disaster_type, payload.location, payload.status, payload.severity))
        row = rows_to_dicts(cur)[0]
        conn.commit()
        return row

@app.get("/organizations")
def get_organizations():
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM organizations ORDER BY created_at DESC;")
        return rows_to_dicts(cur)

@app.post("/organizations")
def create_organization(payload: OrganizationCreate):
    item_id = "org-" + uuid.uuid4().hex[:12]
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
        INSERT INTO organizations (id, name, organization_type, trust_level, status)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING *;
        """, (item_id, payload.name, payload.organization_type, payload.trust_level, payload.status))
        row = rows_to_dicts(cur)[0]
        conn.commit()
        return row

@app.get("/poskos")
def get_poskos():
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM posko_nodes ORDER BY created_at DESC;")
        return rows_to_dicts(cur)

@app.post("/poskos")
def create_posko(payload: PoskoCreate):
    item_id = "posko-" + uuid.uuid4().hex[:12]
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
        INSERT INTO posko_nodes
        (id, disaster_event_id, organization_id, name, node_type, location, verification_status, operational_status)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        RETURNING *;
        """, (
            item_id,
            payload.disaster_event_id,
            payload.organization_id,
            payload.name,
            payload.node_type,
            payload.location,
            payload.verification_status,
            payload.operational_status,
        ))
        row = rows_to_dicts(cur)[0]
        conn.commit()
        return row

@app.post("/device-registrations")
def register_device_posko(payload: DeviceRegistrationCreate):
    ensure_location_resolution_tables()
    ensure_trusted_verifier_tables()
    org_id = "org-" + hashlib.sha1((payload.device_id or payload.organization_name).encode("utf-8")).hexdigest()[:12]
    posko_id = "posko-" + hashlib.sha1(((payload.device_id or payload.local_id or payload.organization_name) + "|" + payload.disaster_event_id).encode("utf-8")).hexdigest()[:12]
    org_name = payload.organization_name.strip()
    posko_name = (payload.posko_name or payload.organization_name).strip()
    location_text = payload.location_text or "Lokasi belum dipilih"

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT id FROM disaster_events WHERE id = %s;", (payload.disaster_event_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Disaster event not found")

        cur.execute("""
        INSERT INTO organizations (id, name, organization_type, trust_level, status, device_id, contact_person, notes)
        VALUES (%s,%s,%s,'unverified','pending',%s,%s,%s)
        ON CONFLICT (id) DO UPDATE SET
          name = EXCLUDED.name,
          organization_type = EXCLUDED.organization_type,
          device_id = EXCLUDED.device_id,
          contact_person = EXCLUDED.contact_person,
          notes = EXCLUDED.notes
        RETURNING *;
        """, (org_id, org_name, payload.role, payload.device_id, payload.member_name, payload.notes))
        org = rows_to_dicts(cur)[0]

        cur.execute("""
        INSERT INTO posko_nodes (
          id, disaster_event_id, organization_id, name, node_type, location,
          verification_status, operational_status, device_id, area_level,
          admin_area_id, province_name, city_name, district_name, village_name, notes
        )
        VALUES (%s,%s,%s,%s,%s,%s,'self_reported','active',%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (id) DO UPDATE SET
          organization_id = EXCLUDED.organization_id,
          name = EXCLUDED.name,
          node_type = EXCLUDED.node_type,
          location = EXCLUDED.location,
          operational_status = 'active',
          device_id = EXCLUDED.device_id,
          area_level = EXCLUDED.area_level,
          admin_area_id = EXCLUDED.admin_area_id,
          province_name = EXCLUDED.province_name,
          city_name = EXCLUDED.city_name,
          district_name = EXCLUDED.district_name,
          village_name = EXCLUDED.village_name,
          notes = EXCLUDED.notes
        RETURNING *;
        """, (
            posko_id, payload.disaster_event_id, org_id, posko_name, payload.role, location_text,
            payload.device_id, payload.area_level, payload.admin_area_id, payload.province_name,
            payload.city_name, payload.district_name, payload.village_name, payload.notes
        ))
        posko = rows_to_dicts(cur)[0]

        cur.execute("""
        INSERT INTO sync_events
        (id, event_id, object_type, object_id, operation, payload_json, source_device_id, verification_status, apply_status)
        VALUES (%s,%s,'device_registration',%s,'upsert',%s,%s,'unverified','applied')
        ON CONFLICT (event_id) DO NOTHING;
        """, (
            "syncev-" + uuid.uuid4().hex[:12],
            payload.local_id or ("device-reg-" + uuid.uuid4().hex[:12]),
            posko_id,
            json.dumps(payload.model_dump(), default=str),
            payload.device_id
        ))
        if payload.area_level in {"province", "city", "district"}:
            area_id = "oparea-" + hashlib.sha1((posko_id + "|" + (payload.admin_area_id or payload.area_level or "aggregate")).encode("utf-8")).hexdigest()[:12]
            cur.execute("""
            INSERT INTO operational_areas (
                id, disaster_event_id, owner_type, owner_id, area_level,
                province_code, city_code, district_code, village_code,
                coverage_description, verification_status
            )
            VALUES (%s,%s,'posko',%s,%s,%s,%s,%s,%s,%s,'self_reported')
            ON CONFLICT (id) DO UPDATE SET
              area_level = EXCLUDED.area_level,
              province_code = EXCLUDED.province_code,
              city_code = EXCLUDED.city_code,
              district_code = EXCLUDED.district_code,
              village_code = EXCLUDED.village_code,
              coverage_description = EXCLUDED.coverage_description,
              updated_at = NOW();
            """, (
                area_id, payload.disaster_event_id, posko_id, payload.area_level,
                payload.admin_area_id if payload.area_level == "province" else None,
                payload.admin_area_id if payload.area_level == "city" else None,
                payload.admin_area_id if payload.area_level == "district" else None,
                payload.admin_area_id if payload.area_level == "village" else None,
                "Aggregate coverage registration. Must be broken down into child posko/village-level reports before final distribution."
            ))
        verification_request = None
        verification_token = None
        if payload.verifier_mode in {"registered", "invite"} and (
            payload.requested_verifier_id or payload.requested_verifier_name
        ):
            verification_token = secrets.token_urlsafe(32)
            verification_request_id = "verreq-" + uuid.uuid4().hex[:12]
            cur.execute("""
            INSERT INTO trusted_verification_requests (
                id, requester_type, requester_id, target_type, target_id,
                requested_verifier_id, requested_verifier_name, requested_verifier_phone,
                requested_verifier_email, relationship_description, verification_scope,
                message, status, token_hash, expires_at
            )
            VALUES (%s,'device_registration',%s,'posko',%s,%s,%s,%s,%s,%s,'posko_identity',%s,'pending',%s,%s)
            RETURNING id, target_type, target_id, requested_verifier_id, requested_verifier_name,
                      relationship_description, verification_scope, status, expires_at, created_at;
            """, (
                verification_request_id, payload.local_id, posko_id,
                payload.requested_verifier_id, payload.requested_verifier_name,
                payload.requested_verifier_phone, payload.requested_verifier_email,
                payload.verifier_relationship or "Mengenal pendaftar",
                f"Permintaan verifikasi identitas posko {posko_name}. Verifikasi ini tidak otomatis membenarkan lokasi, laporan, atau kebutuhan.",
                hashlib.sha256(verification_token.encode("utf-8")).hexdigest(),
                datetime.utcnow() + timedelta(days=7)
            ))
            verification_request = rows_to_dicts(cur)[0]
        conn.commit()

    return {
        "status": "registered",
        "organization": org,
        "posko": posko,
        "verification_request": verification_request,
        "verification_url": (
            f"/rescue-net/pages/verification-approval.html?token={verification_token}"
            if verification_token else None
        )
    }

@app.get("/volunteers")
def get_volunteers():
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM volunteers ORDER BY created_at DESC;")
        return rows_to_dicts(cur)

@app.post("/legacy-volunteers")
def create_legacy_volunteer(payload: VolunteerCreate):
    item_id = "vol-" + uuid.uuid4().hex[:12]
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
        INSERT INTO volunteers
        (id, name, phone, email, main_skill, location, availability, duration_available, verification_status)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        RETURNING *;
        """, (
            item_id,
            payload.name,
            payload.phone,
            payload.email,
            payload.main_skill,
            payload.location,
            payload.availability,
            payload.duration_available,
            payload.verification_status,
        ))
        row = rows_to_dicts(cur)[0]
        conn.commit()
        return row

@app.get("/logistic-needs")
def get_logistic_needs():
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM logistic_needs ORDER BY created_at DESC;")
        return rows_to_dicts(cur)


@app.post("/logistic-needs")
def create_logistic_need(payload: LogisticNeedCreate):
    ensure_unit_normalization_tables()
    item_id = "need-" + uuid.uuid4().hex[:12]
    with get_conn() as conn, conn.cursor() as cur:
        norm = normalize_quantity(cur, payload.item_name, payload.quantity_needed, payload.unit)
        cur.execute("""
        INSERT INTO logistic_needs
        (id, disaster_event_id, node_id, item_name, quantity_needed, unit, priority, needed_before, status,
         original_quantity, original_unit, normalized_quantity, normalized_unit,
         conversion_status, conversion_factor, conversion_notes)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        RETURNING *;
        """, (
            item_id,
            payload.disaster_event_id,
            payload.node_id,
            payload.item_name,
            payload.quantity_needed,
            payload.unit,
            payload.priority,
            payload.needed_before,
            payload.status,
            norm["original_quantity"],
            norm["original_unit"],
            norm["normalized_quantity"],
            norm["normalized_unit"],
            norm["conversion_status"],
            norm["conversion_factor"],
            norm["conversion_notes"],
        ))
        row = rows_to_dicts(cur)[0]
        conn.commit()
        return row

@app.get("/aid-offers")
def get_aid_offers():
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM aid_offers ORDER BY created_at DESC;")
        return rows_to_dicts(cur)


@app.post("/aid-offers")
def create_aid_offer(payload: AidOfferCreate):
    ensure_unit_normalization_tables()
    item_id = "aid-" + uuid.uuid4().hex[:12]
    with get_conn() as conn, conn.cursor() as cur:
        norm = normalize_quantity(cur, payload.item_name, payload.quantity, payload.unit)
        cur.execute("""
        INSERT INTO aid_offers
        (id, disaster_event_id, donor_name, item_name, quantity, unit, pickup_location, ready_at, status,
         original_quantity, original_unit, normalized_quantity, normalized_unit,
         conversion_status, conversion_factor, conversion_notes)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        RETURNING *;
        """, (
            item_id,
            payload.disaster_event_id,
            payload.donor_name,
            payload.item_name,
            payload.quantity,
            payload.unit,
            payload.pickup_location,
            payload.ready_at,
            payload.status,
            norm["original_quantity"],
            norm["original_unit"],
            norm["normalized_quantity"],
            norm["normalized_unit"],
            norm["conversion_status"],
            norm["conversion_factor"],
            norm["conversion_notes"],
        ))
        row = rows_to_dicts(cur)[0]
        conn.commit()
        return row

@app.get("/transport-spaces")
def get_transport_spaces():
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM transport_spaces ORDER BY created_at DESC;")
        return rows_to_dicts(cur)


@app.post("/transport-spaces")
def create_transport_space(payload: TransportSpaceCreate):
    item_id = "transport-" + uuid.uuid4().hex[:12]
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
        INSERT INTO transport_spaces
        (id, disaster_event_id, provider_name, transport_type, route_origin, route_destination,
         capacity_weight_kg, capacity_volume_m3, departure_time, eta, status)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        RETURNING *;
        """, (
            item_id,
            payload.disaster_event_id,
            payload.provider_name,
            payload.transport_type,
            payload.route_origin,
            payload.route_destination,
            payload.capacity_weight_kg,
            payload.capacity_volume_m3,
            payload.departure_time,
            payload.eta,
            payload.status,
        ))
        row = rows_to_dicts(cur)[0]
        conn.commit()
        return row

@app.get("/distribution-flows")
def get_distribution_flows():
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM distribution_flows ORDER BY created_at DESC;")
        return rows_to_dicts(cur)


@app.post("/distribution-flows")
def create_distribution_flow(payload: DistributionFlowCreate):
    item_id = "flow-" + uuid.uuid4().hex[:12]
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
        INSERT INTO distribution_flows
        (id, disaster_event_id, need_id, aid_offer_id, transport_space_id,
         destination_node_id, eta_final, status)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        RETURNING *;
        """, (
            item_id,
            payload.disaster_event_id,
            payload.need_id,
            payload.aid_offer_id,
            payload.transport_space_id,
            payload.destination_node_id,
            payload.eta_final,
            payload.status,
        ))
        row = rows_to_dicts(cur)[0]
        conn.commit()
        return row

@app.get("/evidence")
def get_evidence():
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM evidence_files ORDER BY created_at DESC;")
        return rows_to_dicts(cur)

@app.post("/evidence/upload")
async def upload_evidence(
    file: UploadFile = File(...),
    linked_object_type: str = Form(...),
    disaster_event_id: Optional[str] = Form(None),
    node_id: Optional[str] = Form(None),
    linked_object_id: Optional[str] = Form(None),
    evidence_type: str = Form("photo"),
    uploaded_by: Optional[str] = Form(None),
):
    max_size = 100 * 1024 * 1024
    content = await file.read()

    if len(content) > max_size:
        raise HTTPException(status_code=413, detail="File too large. Max 100MB.")

    evidence_id = "ev-" + uuid.uuid4().hex[:16]
    safe_name = file.filename.replace("/", "_").replace("\\", "_")
    stored_name = f"{evidence_id}-{safe_name}"
    target = UPLOAD_DIR / stored_name
    target.write_bytes(content)

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
        INSERT INTO evidence_files
        (id, disaster_event_id, node_id, linked_object_type, linked_object_id, evidence_type,
         filename, file_path, mime_type, size_bytes, uploaded_by, verification_status)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'pending')
        RETURNING *;
        """, (
            evidence_id,
            disaster_event_id,
            node_id,
            linked_object_type,
            linked_object_id,
            evidence_type,
            safe_name,
            str(target),
            file.content_type,
            len(content),
            uploaded_by,
        ))
        row = rows_to_dicts(cur)[0]
        conn.commit()
        return row


@app.post("/public/aid-offers")
def public_create_aid_offer(payload: PublicAidOfferCreate):
    item_id = "aid-" + uuid.uuid4().hex[:12]
    edit_code = make_edit_code()
    edit_code_hash = hash_edit_code(payload.donor_contact, edit_code)
    status = normalize_public_aid_status(payload.delivery_mode)

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
        INSERT INTO aid_offers
        (id, disaster_event_id, donor_name, donor_contact, donor_type, item_name, quantity, unit,
         pickup_location, ready_at, delivery_mode, target_node_id, target_node_name,
         expected_arrival_at, notes, edit_code_hash, edit_code_created_at, edit_count, status)
        VALUES (%s,%s,%s,%s,'personal_guest',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW(),0,%s)
        RETURNING *;
        """, (
            item_id,
            payload.disaster_event_id,
            payload.donor_name,
            payload.donor_contact,
            payload.item_name,
            payload.quantity,
            payload.unit,
            payload.pickup_location,
            payload.ready_at,
            payload.delivery_mode,
            payload.target_node_id,
            payload.target_node_name,
            payload.expected_arrival_at,
            payload.notes,
            edit_code_hash,
            status,
        ))
        row = rows_to_dicts(cur)[0]
        conn.commit()

    return {
        "id": row["id"],
        "donor_type": "personal_guest",
        "status": row["status"],
        "delivery_mode": row["delivery_mode"],
        "edit_code": edit_code,
        "message": "Simpan kode edit ini. Kode diperlukan untuk mengubah data bantuan."
    }


@app.post("/public/aid-offers/verify-edit")
def public_verify_aid_offer_edit(payload: PublicAidOfferVerifyEdit):
    expected_hash = hash_edit_code(payload.donor_contact, payload.edit_code)

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
        SELECT * FROM aid_offers
        WHERE id = %s
          AND donor_contact = %s
          AND edit_code_hash = %s
          AND donor_type = 'personal_guest';
        """, (payload.aid_offer_id, payload.donor_contact, expected_hash))
        rows = rows_to_dicts(cur)

    if not rows:
        raise HTTPException(status_code=403, detail="Kode edit atau nomor HP tidak cocok.")

    return {
        "verified": True,
        "aid_offer": rows[0]
    }


@app.put("/public/aid-offers/{aid_offer_id}")
def public_update_aid_offer(aid_offer_id: str, payload: PublicAidOfferUpdate):
    expected_hash = hash_edit_code(payload.donor_contact, payload.edit_code)

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
        SELECT * FROM aid_offers
        WHERE id = %s
          AND donor_contact = %s
          AND edit_code_hash = %s
          AND donor_type = 'personal_guest';
        """, (aid_offer_id, payload.donor_contact, expected_hash))
        rows = rows_to_dicts(cur)

        if not rows:
            raise HTTPException(status_code=403, detail="Kode edit atau nomor HP tidak cocok.")

        current = rows[0]

        donor_name = payload.donor_name if payload.donor_name is not None else current["donor_name"]
        item_name = payload.item_name if payload.item_name is not None else current["item_name"]
        quantity = payload.quantity if payload.quantity is not None else current["quantity"]
        unit = payload.unit if payload.unit is not None else current["unit"]
        pickup_location = payload.pickup_location if payload.pickup_location is not None else current["pickup_location"]
        ready_at = payload.ready_at if payload.ready_at is not None else current["ready_at"]
        delivery_mode = payload.delivery_mode if payload.delivery_mode is not None else current["delivery_mode"]
        target_node_id = payload.target_node_id if payload.target_node_id is not None else current["target_node_id"]
        target_node_name = payload.target_node_name if payload.target_node_name is not None else current["target_node_name"]
        expected_arrival_at = payload.expected_arrival_at if payload.expected_arrival_at is not None else current["expected_arrival_at"]
        notes = payload.notes if payload.notes is not None else current["notes"]

        status = payload.status if payload.status is not None else normalize_public_aid_status(delivery_mode, current["status"])

        cur.execute("""
        UPDATE aid_offers
        SET donor_name = %s,
            item_name = %s,
            quantity = %s,
            unit = %s,
            pickup_location = %s,
            ready_at = %s,
            delivery_mode = %s,
            target_node_id = %s,
            target_node_name = %s,
            expected_arrival_at = %s,
            notes = %s,
            status = %s,
            last_edited_at = NOW(),
            edit_count = COALESCE(edit_count, 0) + 1
        WHERE id = %s
        RETURNING *;
        """, (
            donor_name,
            item_name,
            quantity,
            unit,
            pickup_location,
            ready_at,
            delivery_mode,
            target_node_id,
            target_node_name,
            expected_arrival_at,
            notes,
            status,
            aid_offer_id,
        ))

        updated = rows_to_dicts(cur)[0]
        conn.commit()

    return updated




@app.get("/ai/context/{disaster_event_id}")
def get_ai_context(disaster_event_id: str):
    context = {
        "disaster_event_id": disaster_event_id,
        "generated_at": datetime.utcnow().isoformat(),
        "disaster": None,

        "poskos": [],
        "organizations": [],
        "volunteers": [],
        "logistic_needs": [],
        "aid_offers": [],
        "transport_spaces": [],
        "distribution_flows": [],
        "ecosystem_members": [],
        "resources": [],
        "resource_requests": [],
        "resource_assignments": [],

        "stock_summary": [],
        "stock_movements": [],
        "kitchen_meal_productions": [],
        "medical_cases": [],
        "medical_supply_uses": [],
        "shelter_occupancies": [],
        "shelter_needs": [],
        "missing_person_reports": [],
        "found_person_reports": [],
        "search_found_matches": [],
        "donor_programs": [],
        "donor_program_updates": [],

        "summary": {},
        "alerts": [],
        "recommendations": [],
        "sources": []
    }

    with get_conn() as conn, conn.cursor() as cur:
        def table_exists(table_name):
            cur.execute("""
            SELECT EXISTS (
              SELECT 1 FROM information_schema.tables
              WHERE table_schema = 'public'
                AND table_name = %s
            ) AS exists;
            """, (table_name,))
            return rows_to_dicts(cur)[0]["exists"]

        def table_columns(table_name):
            cur.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = %s;
            """, (table_name,))
            return {r["column_name"] for r in rows_to_dicts(cur)}

        def read_disaster_table(key, table_name, limit=300):
            if not table_exists(table_name):
                return
            cols = table_columns(table_name)
            if "disaster_event_id" not in cols:
                return

            deleted_filter = "AND deleted_at IS NULL" if "deleted_at" in cols else ""
            order_col = "created_at" if "created_at" in cols else "id"

            cur.execute(f"""
            SELECT *
            FROM {table_name}
            WHERE disaster_event_id = %s
            {deleted_filter}
            ORDER BY {order_col} DESC
            LIMIT %s;
            """, (disaster_event_id, limit))
            context[key] = rows_to_dicts(cur)

        cur.execute("SELECT * FROM disaster_events WHERE id = %s;", (disaster_event_id,))
        rows = rows_to_dicts(cur)
        context["disaster"] = rows[0] if rows else None

        for key, table in [
            ("poskos", "posko_nodes"),
            ("logistic_needs", "logistic_needs"),
            ("aid_offers", "aid_offers"),
            ("transport_spaces", "transport_spaces"),
            ("distribution_flows", "distribution_flows"),
            ("ecosystem_members", "disaster_ecosystem_members"),
            ("resources", "resources"),
            ("resource_requests", "resource_requests"),
            ("resource_assignments", "resource_assignments"),
            ("stock_movements", "stock_movements"),
            ("kitchen_meal_productions", "kitchen_meal_productions"),
            ("medical_cases", "medical_cases"),
            ("medical_supply_uses", "medical_supply_uses"),
            ("shelter_occupancies", "shelter_occupancies"),
            ("shelter_needs", "shelter_needs"),
            ("missing_person_reports", "missing_person_reports"),
            ("found_person_reports", "found_person_reports"),
            ("search_found_matches", "search_found_matches"),
            ("donor_programs", "donor_programs"),
            ("donor_program_updates", "donor_program_updates"),
        ]:
            read_disaster_table(key, table)

        # Organizations are currently global, but include active orgs for command context.
        if table_exists("organizations"):
            cols = table_columns("organizations")
            deleted_filter = "WHERE deleted_at IS NULL" if "deleted_at" in cols else ""
            cur.execute(f"""
            SELECT *
            FROM organizations
            {deleted_filter}
            ORDER BY name ASC
            LIMIT 200;
            """)
            context["organizations"] = rows_to_dicts(cur)

        # Volunteers are currently global in this prototype.
        if table_exists("volunteers"):
            cols = table_columns("volunteers")
            deleted_filter = "WHERE deleted_at IS NULL" if "deleted_at" in cols else ""
            order_col = "created_at" if "created_at" in cols else "id"
            cur.execute(f"""
            SELECT *
            FROM volunteers
            {deleted_filter}
            ORDER BY {order_col} DESC
            LIMIT 200;
            """)
            context["volunteers"] = rows_to_dicts(cur)

        if table_exists("stock_movements"):
            cols = table_columns("stock_movements")
            deleted_filter = "AND deleted_at IS NULL" if "deleted_at" in cols else ""
            cur.execute(f"""
            SELECT
              posko_id,
              item_name,
              unit,
              SUM(
                CASE
                  WHEN movement_direction = 'in' THEN quantity
                  WHEN movement_direction = 'out' THEN -quantity
                  ELSE 0
                END
              ) AS current_quantity
            FROM stock_movements
            WHERE disaster_event_id = %s
            {deleted_filter}
            GROUP BY posko_id, item_name, unit
            ORDER BY posko_id, item_name;
            """, (disaster_event_id,))
            context["stock_summary"] = rows_to_dicts(cur)

        context["summary"] = {
            "posko_count": len(context["poskos"]),
            "organization_count": len(context["organizations"]),
            "volunteer_count": len(context["volunteers"]),

            "open_logistic_need_count": len([x for x in context["logistic_needs"] if x.get("status") == "open"]),
            "urgent_logistic_need_count": len([x for x in context["logistic_needs"] if x.get("priority") == "urgent" and x.get("status") == "open"]),
            "critical_logistic_need_count": len([x for x in context["logistic_needs"] if x.get("priority") == "critical" and x.get("status") == "open"]),

            "aid_offer_count": len(context["aid_offers"]),
            "aid_need_pickup_count": len([x for x in context["aid_offers"] if x.get("delivery_mode") == "need_pickup" or x.get("status") == "need_pickup"]),

            "distribution_flow_count": len(context["distribution_flows"]),
            "resource_request_count": len(context["resource_requests"]),
            "resource_assignment_count": len(context["resource_assignments"]),

            "stock_item_count": len(context["stock_summary"]),
            "stock_movement_count": len(context["stock_movements"]),

            "meal_production_count": len(context["kitchen_meal_productions"]),
            "medical_case_count": len(context["medical_cases"]),
            "medical_supply_use_count": len(context["medical_supply_uses"]),

            "shelter_occupancy_count": len(context["shelter_occupancies"]),
            "shelter_need_count": len(context["shelter_needs"]),

            "missing_person_count": len([x for x in context["missing_person_reports"] if x.get("status") != "reunited"]),
            "found_person_count": len(context["found_person_reports"]),
            "search_found_match_count": len(context["search_found_matches"]),
            "reunited_count": len([x for x in context["search_found_matches"] if x.get("status") == "reunited"]),
            "donor_program_count": len(context["donor_programs"]),
            "donor_program_update_count": len(context["donor_program_updates"]),
        }

        for aid in context["aid_offers"]:
            if aid.get("delivery_mode") == "need_pickup" or aid.get("status") == "need_pickup":
                context["alerts"].append({
                    "level": "warning",
                    "type": "aid_need_pickup",
                    "message": f"Bantuan {aid.get('item_name')} dari {aid.get('donor_name')} perlu pickup di {aid.get('pickup_location')}.",
                    "source_table": "aid_offers",
                    "source_id": aid.get("id")
                })

        for need in context["logistic_needs"]:
            if need.get("status") == "open" and need.get("priority") in ["urgent", "critical"]:
                context["alerts"].append({
                    "level": need.get("priority"),
                    "type": "logistic_need",
                    "message": f"Kebutuhan {need.get('item_name')} masih open: {need.get('quantity_needed')} {need.get('unit')}.",
                    "source_table": "logistic_needs",
                    "source_id": need.get("id")
                })

        for need in context["shelter_needs"]:
            if need.get("status") == "open" and need.get("priority") in ["urgent", "critical"]:
                context["alerts"].append({
                    "level": need.get("priority"),
                    "type": "shelter_need",
                    "message": f"Kebutuhan shelter {need.get('item_name')} masih open: {need.get('quantity_needed')} {need.get('unit')}.",
                    "source_table": "shelter_needs",
                    "source_id": need.get("id")
                })

        for occ in context["shelter_occupancies"]:
            cap = occ.get("capacity_total") or 0
            cur_occ = occ.get("current_occupancy") or 0
            try:
                if cap and float(cur_occ) / float(cap) >= 0.9:
                    context["alerts"].append({
                        "level": "urgent",
                        "type": "shelter_capacity",
                        "message": f"Shelter hampir penuh: {occ.get('shelter_name')} {cur_occ}/{cap}.",
                        "source_table": "shelter_occupancies",
                        "source_id": occ.get("id")
                    })
            except Exception:
                pass

        for case in context["medical_cases"]:
            if case.get("severity") in ["severe", "critical"] or case.get("triage_status") == "red":
                context["alerts"].append({
                    "level": case.get("severity") or "urgent",
                    "type": "medical_case",
                    "message": f"Kasus medis prioritas: {case.get('patient_code')} - {case.get('complaint')}.",
                    "source_table": "medical_cases",
                    "source_id": case.get("id")
                })

        if context["summary"]["missing_person_count"] > 0:
            context["alerts"].append({
                "level": "urgent",
                "type": "search_found",
                "message": f"{context['summary']['missing_person_count']} laporan orang hilang masih terbuka.",
                "source_table": "missing_person_reports",
                "source_id": "missing_person_reports"
            })

        if context["summary"]["open_logistic_need_count"] > 0:
            context["recommendations"].append("Prioritaskan kebutuhan logistik urgent/critical dan cocokkan dengan stok atau bantuan masuk.")
        if context["summary"]["aid_need_pickup_count"] > 0:
            context["recommendations"].append("Assign relawan/transport untuk pickup bantuan yang masih perlu dijemput.")
        if context["summary"]["shelter_need_count"] > 0:
            context["recommendations"].append("Cek kebutuhan shelter dan arahkan distribusi stok menuju shelter.")
        if context["summary"]["medical_case_count"] > 0:
            context["recommendations"].append("Monitor pemakaian stok medis dan replenishment obat cepat habis.")
        if context["summary"]["missing_person_count"] > 0:
            context["recommendations"].append("Koordinasikan Search & Found dengan shelter, posko medis, dan relawan lapangan.")
        if context["summary"].get("donor_program_count", 0) > 0:
            context["recommendations"].append("Monitor progress program khusus, dana diterima, pengeluaran, bukti, dan target penerima manfaat.")

        for key, rows_ in context.items():
            if isinstance(rows_, list):
                for row in rows_[:80]:
                    if isinstance(row, dict) and row.get("id"):
                        context["sources"].append({
                            "source_table": key,
                            "source_id": row.get("id")
                        })

    return context



@app.get("/ecosystem-members/{disaster_event_id}")
def get_ecosystem_members(disaster_event_id: str):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
        SELECT * FROM disaster_ecosystem_members
        WHERE disaster_event_id = %s
        ORDER BY role_in_disaster, member_type, member_id;
        """, (disaster_event_id,))
        return rows_to_dicts(cur)


@app.get("/resources/{disaster_event_id}")
def get_resources(disaster_event_id: str):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
        SELECT * FROM resources
        WHERE disaster_event_id = %s
        ORDER BY resource_type, trust_level DESC, created_at DESC;
        """, (disaster_event_id,))
        return rows_to_dicts(cur)


@app.get("/resource-shares/{disaster_event_id}")
def get_resource_shares(disaster_event_id: str):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
        SELECT rs.*, r.name AS resource_name, r.resource_type, r.owner_type, r.owner_id
        FROM resource_shares rs
        LEFT JOIN resources r ON r.id = rs.resource_id
        WHERE rs.disaster_event_id = %s
        ORDER BY rs.created_at DESC;
        """, (disaster_event_id,))
        return rows_to_dicts(cur)


@app.get("/resource-requests")
def get_resource_requests():
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
        SELECT rr.*, r.disaster_event_id, r.name AS resource_name, r.resource_type, r.owner_id
        FROM resource_requests rr
        LEFT JOIN resources r ON r.id = rr.resource_id
        ORDER BY rr.created_at DESC;
        """)
        return rows_to_dicts(cur)



class ResourceRequestCreate(BaseModel):
    disaster_event_id: Optional[str] = None
    resource_id: str
    requested_by_type: str
    requested_by_id: str
    request_reason: str
    related_need_id: Optional[str] = None
    related_distribution_flow_id: Optional[str] = None
    requested_quantity: Optional[float] = 1
    requested_time: Optional[str] = None
    created_by_user_id: Optional[str] = "resource-operator"


class ResourceRequestApprove(BaseModel):
    approved_by: str
    assignment_notes: Optional[str] = None
    assigned_quantity: Optional[float] = 1
    created_by_user_id: Optional[str] = "resource-operator"


@app.post("/resource-requests")
def create_resource_request(payload: ResourceRequestCreate):
    request_id = "req-" + uuid.uuid4().hex[:12]

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
        INSERT INTO resource_requests
        (id, disaster_event_id, resource_id,
         requested_by_type, requested_by_id, request_reason,
         related_need_id, related_distribution_flow_id,
         requested_quantity, requested_time,
         status, created_at, updated_at)
        VALUES
        (%s,%s,%s,
         %s,%s,%s,
         %s,%s,
         %s,%s,
         'requested', NOW(), NOW())
        RETURNING *;
        """, (
            request_id,
            payload.disaster_event_id,
            payload.resource_id,
            payload.requested_by_type,
            payload.requested_by_id,
            payload.request_reason,
            payload.related_need_id,
            payload.related_distribution_flow_id,
            payload.requested_quantity,
            payload.requested_time,
        ))

        row = rows_to_dicts(cur)[0]
        conn.commit()
        return row


@app.post("/resource-requests/{request_id}/approve")
def approve_resource_request(request_id: str, payload: ResourceRequestApprove):
    assignment_id = "assign-" + uuid.uuid4().hex[:12]

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
        SELECT rr.*, r.disaster_event_id
        FROM resource_requests rr
        JOIN resources r ON r.id = rr.resource_id
        WHERE rr.id = %s;
        """, (request_id,))
        rows = rows_to_dicts(cur)

        if not rows:
            raise HTTPException(status_code=404, detail="Resource request not found")

        req = rows[0]

        if req.get("status") not in ("requested", "approved"):
            raise HTTPException(status_code=400, detail=f"Request status is {req.get('status')}")

        cur.execute("""
        UPDATE resource_requests
        SET status = 'approved',
            approved_by = %s,
            approved_at = NOW(),
            updated_at = NOW()
        WHERE id = %s
        RETURNING *;
        """, (payload.approved_by, request_id))
        updated_request = rows_to_dicts(cur)[0]

        cur.execute("""
        INSERT INTO resource_assignments
        (id, resource_id, assigned_to_type, assigned_to_id, assigned_by,
         related_need_id, related_distribution_flow_id, assigned_quantity,
         assignment_notes, status)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'assigned')
        RETURNING *;
        """, (
            assignment_id,
            req["resource_id"],
            req["requested_by_type"],
            req["requested_by_id"],
            payload.approved_by,
            req.get("related_need_id"),
            req.get("related_distribution_flow_id"),
            payload.assigned_quantity if payload.assigned_quantity is not None else req.get("requested_quantity"),
            payload.assignment_notes,
        ))
        assignment = rows_to_dicts(cur)[0]

        cur.execute("""
        INSERT INTO audit_logs
        (id, actor_type, actor_id, action, object_type, object_id,
         after_json, disaster_event_id)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s);
        """, (
            "audit-" + uuid.uuid4().hex[:12],
            "user_or_org",
            payload.approved_by,
            "approve_resource_request",
            "resource_request",
            request_id,
            json.dumps({"request": updated_request, "assignment": assignment}, default=str),
            req.get("disaster_event_id"),
        ))

        conn.commit()

        return {
            "request": updated_request,
            "assignment": assignment
        }


@app.get("/resource-assignments")
def get_resource_assignments():
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
        SELECT ra.*, r.disaster_event_id, r.name AS resource_name, r.resource_type, r.owner_id
        FROM resource_assignments ra
        LEFT JOIN resources r ON r.id = ra.resource_id
        ORDER BY ra.created_at DESC;
        """)
        return rows_to_dicts(cur)

class SyncEventIn(BaseModel):
    event_id: Optional[str] = None
    object_type: str
    object_id: str
    operation: str
    payload_json: dict = {}
    source_server_id: Optional[str] = None
    source_device_id: Optional[str] = None
    source_user_id: Optional[str] = None
    source_organization_id: Optional[str] = None

class SyncPushRequest(BaseModel):
    source_device_id: Optional[str] = None
    source_server_id: Optional[str] = None
    events: list[SyncEventIn]


def apply_sync_event(cur, ev, event_id: str):
    """
    Apply selected sync events into operational tables.
    Current prototype supports:
    - resource_request create
    """
    if ev.object_type == "resource_request" and ev.operation == "create":
        payload = ev.payload_json or {}

        resource_id = payload.get("resource_id")
        requested_by_type = payload.get("requested_by_type")
        requested_by_id = payload.get("requested_by_id")

        if not resource_id or not requested_by_type or not requested_by_id:
            return {
                "apply_status": "rejected",
                "reason": "resource_id, requested_by_type, and requested_by_id are required"
            }

        server_request_id = "req-" + uuid.uuid4().hex[:12]

        cur.execute("""
        INSERT INTO resource_requests
        (id, resource_id, requested_by_type, requested_by_id, request_reason,
         related_need_id, related_distribution_flow_id, requested_quantity,
         requested_time, status)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'requested')
        RETURNING *;
        """, (
            server_request_id,
            resource_id,
            requested_by_type,
            requested_by_id,
            payload.get("request_reason"),
            payload.get("related_need_id"),
            payload.get("related_distribution_flow_id"),
            payload.get("requested_quantity"),
            payload.get("requested_time"),
        ))

        row = rows_to_dicts(cur)[0]

        return {
            "apply_status": "applied",
            "object_type": "resource_request",
            "local_object_id": ev.object_id,
            "server_object_id": row["id"]
        }

    return {
        "apply_status": "stored_only",
        "reason": "No apply rule for this object_type/operation yet"
    }

@app.post("/sync/push")
def sync_push(payload: SyncPushRequest):
    accepted = []
    rejected = []

    with get_conn() as conn, conn.cursor() as cur:
        for ev in payload.events:
            event_id = ev.event_id or ("sync-" + uuid.uuid4().hex[:16])
            sync_row_id = "syncev-" + uuid.uuid4().hex[:12]

            try:
                cur.execute("""
                INSERT INTO sync_events
                (id, event_id, object_type, object_id, operation, payload_json,
                 source_server_id, source_device_id, source_user_id, source_organization_id,
                 verification_status, apply_status)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'unverified','accepted')
                ON CONFLICT (event_id) DO NOTHING
                RETURNING *;
                """, (
                    sync_row_id,
                    event_id,
                    ev.object_type,
                    ev.object_id,
                    ev.operation,
                    json.dumps(ev.payload_json, default=str),
                    ev.source_server_id or payload.source_server_id,
                    ev.source_device_id or payload.source_device_id,
                    ev.source_user_id,
                    ev.source_organization_id,
                ))

                rows = rows_to_dicts(cur)

                if rows:
                    apply_result = apply_sync_event(cur, ev, event_id)
                    cur.execute(
                        "UPDATE sync_events SET apply_status = %s WHERE event_id = %s;",
                        (apply_result.get("apply_status", "accepted"), event_id)
                    )

                    accepted.append({
                        "event_id": event_id,
                        "object_type": ev.object_type,
                        "object_id": ev.object_id,
                        "operation": ev.operation,
                        "apply_status": apply_result.get("apply_status", "accepted"),
                        "apply_result": apply_result
                    })
                else:
                    accepted.append({
                        "event_id": event_id,
                        "object_type": ev.object_type,
                        "object_id": ev.object_id,
                        "operation": ev.operation,
                        "apply_status": "duplicate_ignored"
                    })

            except Exception as ex:
                rejected.append({
                    "event_id": event_id,
                    "object_type": ev.object_type,
                    "object_id": ev.object_id,
                    "operation": ev.operation,
                    "error": str(ex)
                })

        conn.commit()

    return {
        "status": "ok",
        "accepted_count": len(accepted),
        "rejected_count": len(rejected),
        "accepted": accepted,
        "rejected": rejected
    }


@app.get("/sync/pull/{disaster_event_id}")
def sync_pull(disaster_event_id: str, since: Optional[str] = None):
    result = {
        "disaster_event_id": disaster_event_id,
        "generated_at": datetime.utcnow().isoformat(),
        "disasters": [],
        "ecosystem_members": [],
        "resources": [],
        "resource_shares": [],
        "resource_requests": [],
        "resource_assignments": [],
        "aid_offers": [],
        "transport_spaces": [],
        "distribution_flows": [],
        "sync_events": [],
    }

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM disaster_events WHERE id = %s;", (disaster_event_id,))
        result["disasters"] = rows_to_dicts(cur)

        cur.execute("SELECT * FROM disaster_ecosystem_members WHERE disaster_event_id = %s ORDER BY updated_at DESC;", (disaster_event_id,))
        result["ecosystem_members"] = rows_to_dicts(cur)

        cur.execute("SELECT * FROM resources WHERE disaster_event_id = %s ORDER BY updated_at DESC;", (disaster_event_id,))
        result["resources"] = rows_to_dicts(cur)

        cur.execute("SELECT * FROM resource_shares WHERE disaster_event_id = %s ORDER BY updated_at DESC;", (disaster_event_id,))
        result["resource_shares"] = rows_to_dicts(cur)

        cur.execute("""
        SELECT rr.*, r.disaster_event_id, r.name AS resource_name, r.resource_type, r.owner_id
        FROM resource_requests rr
        JOIN resources r ON r.id = rr.resource_id
        WHERE r.disaster_event_id = %s
        ORDER BY rr.updated_at DESC;
        """, (disaster_event_id,))
        result["resource_requests"] = rows_to_dicts(cur)

        cur.execute("""
        SELECT ra.*, r.disaster_event_id, r.name AS resource_name, r.resource_type, r.owner_id
        FROM resource_assignments ra
        JOIN resources r ON r.id = ra.resource_id
        WHERE r.disaster_event_id = %s
        ORDER BY ra.updated_at DESC;
        """, (disaster_event_id,))
        result["resource_assignments"] = rows_to_dicts(cur)

        cur.execute("SELECT * FROM aid_offers WHERE disaster_event_id = %s ORDER BY created_at DESC;", (disaster_event_id,))
        result["aid_offers"] = rows_to_dicts(cur)

        cur.execute("SELECT * FROM transport_spaces WHERE disaster_event_id = %s ORDER BY created_at DESC;", (disaster_event_id,))
        result["transport_spaces"] = rows_to_dicts(cur)

        cur.execute("SELECT * FROM distribution_flows WHERE disaster_event_id = %s ORDER BY created_at DESC;", (disaster_event_id,))
        result["distribution_flows"] = rows_to_dicts(cur)

        if since:
            cur.execute("""
            SELECT * FROM sync_events
            WHERE created_at >= %s
            ORDER BY created_at DESC
            LIMIT 200;
            """, (since,))
        else:
            cur.execute("""
            SELECT * FROM sync_events
            ORDER BY created_at DESC
            LIMIT 200;
            """)
        result["sync_events"] = rows_to_dicts(cur)

    return result


class StockMovementCreate(BaseModel):
    disaster_event_id: str
    posko_id: str
    item_name: str
    quantity: float
    unit: str
    movement_type: str = "stock_in"
    movement_direction: str = "in"
    source_type: Optional[str] = None
    source_id: Optional[str] = None
    destination_type: Optional[str] = None
    destination_id: Optional[str] = None
    related_aid_offer_id: Optional[str] = None
    related_distribution_flow_id: Optional[str] = None
    related_logistic_need_id: Optional[str] = None
    notes: Optional[str] = None
    evidence_file_id: Optional[str] = None
    owner_type: Optional[str] = "posko"
    owner_id: Optional[str] = None
    visibility_scope: Optional[str] = "disaster_ecosystem"
    access_policy: Optional[str] = "request_required"
    verification_status: Optional[str] = "self_reported"


@app.get("/stock-movements/{posko_id}")
def get_stock_movements(posko_id: str):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
        SELECT *
        FROM stock_movements
        WHERE posko_id = %s
          AND deleted_at IS NULL
        ORDER BY created_at DESC;
        """, (posko_id,))
        return rows_to_dicts(cur)


@app.post("/stock-movements")
def create_stock_movement(payload: StockMovementCreate):
    ensure_unit_normalization_tables()
    item_id = "stock-" + uuid.uuid4().hex[:12]

    with get_conn() as conn, conn.cursor() as cur:
        norm = normalize_quantity(cur, payload.item_name, payload.quantity, payload.unit)
        cur.execute("""
        INSERT INTO stock_movements
        (id, disaster_event_id, posko_id, item_name, quantity, unit,
         movement_type, movement_direction, source_type, source_id,
         destination_type, destination_id, related_aid_offer_id,
         related_distribution_flow_id, related_logistic_need_id,
         notes, evidence_file_id, owner_type, owner_id,
         visibility_scope, access_policy, verification_status,
         original_quantity, original_unit, normalized_quantity, normalized_unit,
         conversion_status, conversion_factor, conversion_notes)
        VALUES
        (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        RETURNING *;
        """, (
            item_id,
            payload.disaster_event_id,
            payload.posko_id,
            payload.item_name,
            payload.quantity,
            payload.unit,
            payload.movement_type,
            payload.movement_direction,
            payload.source_type,
            payload.source_id,
            payload.destination_type,
            payload.destination_id,
            payload.related_aid_offer_id,
            payload.related_distribution_flow_id,
            payload.related_logistic_need_id,
            payload.notes,
            payload.evidence_file_id,
            payload.owner_type,
            payload.owner_id or payload.posko_id,
            payload.visibility_scope,
            payload.access_policy,
            payload.verification_status,
            norm["original_quantity"],
            norm["original_unit"],
            norm["normalized_quantity"],
            norm["normalized_unit"],
            norm["conversion_status"],
            norm["conversion_factor"],
            norm["conversion_notes"],
        ))

        row = rows_to_dicts(cur)[0]
        conn.commit()
        return row


@app.get("/posko-context/{posko_id}")
def get_posko_context(posko_id: str):
    result = {
        "posko": None,
        "organization": None,
        "disaster": None,
        "logistic_needs": [],
        "incoming_aid": [],
        "stock_movements": [],
        "stock_summary": [],
        "distribution_flows": [],
        "volunteers": [],
        "generated_at": datetime.utcnow().isoformat(),
    }

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM posko_nodes WHERE id = %s;", (posko_id,))
        rows = rows_to_dicts(cur)
        if not rows:
            raise HTTPException(status_code=404, detail="Posko not found")

        result["posko"] = rows[0]
        disaster_event_id = result["posko"].get("disaster_event_id")
        organization_id = result["posko"].get("organization_id")
        posko_name = result["posko"].get("name") or posko_id

        if organization_id:
            cur.execute("SELECT * FROM organizations WHERE id = %s;", (organization_id,))
            org_rows = rows_to_dicts(cur)
            result["organization"] = org_rows[0] if org_rows else None

        if disaster_event_id:
            cur.execute("SELECT * FROM disaster_events WHERE id = %s;", (disaster_event_id,))
            dis_rows = rows_to_dicts(cur)
            result["disaster"] = dis_rows[0] if dis_rows else None

        # logistic_needs schema-safe
        cur.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'logistic_needs';
        """)
        need_cols = {r["column_name"] for r in rows_to_dicts(cur)}

        if "posko_id" in need_cols:
            cur.execute("SELECT * FROM logistic_needs WHERE posko_id = %s ORDER BY created_at DESC;", (posko_id,))
        elif "node_id" in need_cols:
            cur.execute("SELECT * FROM logistic_needs WHERE node_id = %s ORDER BY created_at DESC;", (posko_id,))
        elif "posko_node_id" in need_cols:
            cur.execute("SELECT * FROM logistic_needs WHERE posko_node_id = %s ORDER BY created_at DESC;", (posko_id,))
        elif "disaster_event_id" in need_cols:
            cur.execute("SELECT * FROM logistic_needs WHERE disaster_event_id = %s ORDER BY created_at DESC LIMIT 50;", (disaster_event_id,))
        else:
            cur.execute("SELECT * FROM logistic_needs ORDER BY created_at DESC LIMIT 50;")
        result["logistic_needs"] = rows_to_dicts(cur)

        # incoming aid to this posko
        cur.execute("""
        SELECT *
        FROM aid_offers
        WHERE target_node_id = %s
           OR target_node_name = %s
           OR target_node_name = %s
        ORDER BY created_at DESC;
        """, (posko_id, posko_id, posko_name))
        result["incoming_aid"] = rows_to_dicts(cur)

        # stock movements, only if table exists
        cur.execute("""
        SELECT EXISTS (
          SELECT 1 FROM information_schema.tables
          WHERE table_schema = 'public'
            AND table_name = 'stock_movements'
        ) AS exists;
        """)
        stock_exists = rows_to_dicts(cur)[0]["exists"]

        if stock_exists:
            cur.execute("""
            SELECT *
            FROM stock_movements
            WHERE posko_id = %s
              AND deleted_at IS NULL
            ORDER BY created_at DESC;
            """, (posko_id,))
            result["stock_movements"] = rows_to_dicts(cur)

            cur.execute("""
            SELECT
              item_name,
              unit,
              SUM(
                CASE
                  WHEN movement_direction = 'in' THEN quantity
                  WHEN movement_direction = 'out' THEN -quantity
                  ELSE 0
                END
              ) AS current_quantity
            FROM stock_movements
            WHERE posko_id = %s
              AND deleted_at IS NULL
            GROUP BY item_name, unit
            ORDER BY item_name;
            """, (posko_id,))
            result["stock_summary"] = rows_to_dicts(cur)

        cur.execute("""
        SELECT *
        FROM distribution_flows
        WHERE destination_node_id = %s
        ORDER BY created_at DESC;
        """, (posko_id,))
        result["distribution_flows"] = rows_to_dicts(cur)

        cur.execute("""
        SELECT *
        FROM volunteers
        WHERE location ILIKE %s
        ORDER BY created_at DESC
        LIMIT 50;
        """, (f"%{posko_name}%",))
        result["volunteers"] = rows_to_dicts(cur)

    return result


class AidReceiveVerify(BaseModel):
    posko_id: str
    disaster_event_id: str
    aid_offer_id: str
    item_name: str
    quantity_received: float
    unit: str
    received_by: Optional[str] = "posko-operator"
    notes: Optional[str] = None
    distribution_flow_id: Optional[str] = None


@app.post("/posko/verify-aid-received")
def verify_aid_received(payload: AidReceiveVerify):
    stock_id = "stock-" + uuid.uuid4().hex[:12]
    audit_id = "audit-" + uuid.uuid4().hex[:12]

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT status FROM aid_offers WHERE id = %s;", (payload.aid_offer_id,))
        aid_status_rows = rows_to_dicts(cur)
        if not aid_status_rows:
            raise HTTPException(status_code=404, detail="Aid offer not found")

        if aid_status_rows[0].get("status") == "received_verified":
            raise HTTPException(status_code=400, detail="Aid offer already received_verified. Duplicate stock movement blocked.")

        cur.execute("""
        INSERT INTO stock_movements
        (id, disaster_event_id, posko_id, item_name, quantity, unit,
         movement_type, movement_direction, source_type, source_id,
         related_aid_offer_id, related_distribution_flow_id,
         notes, owner_type, owner_id, verification_status)
        VALUES
        (%s,%s,%s,%s,%s,%s,
         'stock_in','in','aid_offer',%s,
         %s,%s,
         %s,'posko',%s,'received_verified')
        RETURNING *;
        """, (
            stock_id,
            payload.disaster_event_id,
            payload.posko_id,
            payload.item_name,
            payload.quantity_received,
            payload.unit,
            payload.aid_offer_id,
            payload.aid_offer_id,
            payload.distribution_flow_id,
            payload.notes,
            payload.posko_id,
        ))
        stock_row = rows_to_dicts(cur)[0]

        cur.execute("""
        UPDATE aid_offers
        SET status = 'received_verified',
            updated_by_user_id = %s,
            last_edited_at = NOW()
        WHERE id = %s
        RETURNING *;
        """, (payload.received_by, payload.aid_offer_id))
        aid_rows = rows_to_dicts(cur)

        flow_row = None
        if payload.distribution_flow_id:
            cur.execute("""
            UPDATE distribution_flows
            SET status = 'received_verified'
            WHERE id = %s
            RETURNING *;
            """, (payload.distribution_flow_id,))
            flow_rows = rows_to_dicts(cur)
            flow_row = flow_rows[0] if flow_rows else None

        cur.execute("""
        INSERT INTO audit_logs
        (id, actor_type, actor_id, action, object_type, object_id,
         after_json, disaster_event_id)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s);
        """, (
            audit_id,
            "posko_operator",
            payload.received_by,
            "verify_aid_received",
            "aid_offer",
            payload.aid_offer_id,
            json.dumps({
                "stock_movement": stock_row,
                "aid_offer": aid_rows[0] if aid_rows else None,
                "distribution_flow": flow_row
            }, default=str),
            payload.disaster_event_id,
        ))

        conn.commit()

        return {
            "status": "received_verified",
            "stock_movement": stock_row,
            "aid_offer": aid_rows[0] if aid_rows else None,
            "distribution_flow": flow_row
        }


class StockTransferCreate(BaseModel):
    disaster_event_id: str
    source_posko_id: str
    destination_posko_id: str
    item_name: str
    quantity: float
    unit: str
    notes: Optional[str] = None
    created_by_user_id: Optional[str] = "posko-operator"


@app.post("/stock-transfer")
def create_stock_transfer(payload: StockTransferCreate):
    out_id = "stock-" + uuid.uuid4().hex[:12]
    in_id = "stock-" + uuid.uuid4().hex[:12]
    flow_id = "flow-" + uuid.uuid4().hex[:12]

    if payload.quantity <= 0:
        raise HTTPException(status_code=400, detail="Quantity must be positive")

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
        SELECT COALESCE(SUM(
            CASE
              WHEN movement_direction = 'in' THEN quantity
              WHEN movement_direction = 'out' THEN -quantity
              ELSE 0
            END
        ), 0) AS current_quantity
        FROM stock_movements
        WHERE posko_id = %s
          AND item_name = %s
          AND unit = %s
          AND deleted_at IS NULL;
        """, (payload.source_posko_id, payload.item_name, payload.unit))
        current_qty = rows_to_dicts(cur)[0]["current_quantity"] or 0

        if float(current_qty) < payload.quantity:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient stock. Current stock is {current_qty} {payload.unit}"
            )

        cur.execute("""
        INSERT INTO stock_movements
        (id, disaster_event_id, posko_id, item_name, quantity, unit,
         movement_type, movement_direction, source_type, source_id,
         destination_type, destination_id, notes,
         owner_type, owner_id, verification_status, created_by_user_id)
        VALUES
        (%s,%s,%s,%s,%s,%s,
         'transfer_out','out','posko',%s,
         'posko',%s,%s,
         'posko',%s,'self_reported',%s)
        RETURNING *;
        """, (
            out_id, payload.disaster_event_id, payload.source_posko_id,
            payload.item_name, payload.quantity, payload.unit,
            payload.source_posko_id, payload.destination_posko_id,
            payload.notes, payload.source_posko_id, payload.created_by_user_id
        ))
        out_row = rows_to_dicts(cur)[0]

        cur.execute("""
        INSERT INTO stock_movements
        (id, disaster_event_id, posko_id, item_name, quantity, unit,
         movement_type, movement_direction, source_type, source_id,
         destination_type, destination_id, notes,
         owner_type, owner_id, verification_status, created_by_user_id)
        VALUES
        (%s,%s,%s,%s,%s,%s,
         'transfer_in','in','posko',%s,
         'posko',%s,%s,
         'posko',%s,'self_reported',%s)
        RETURNING *;
        """, (
            in_id, payload.disaster_event_id, payload.destination_posko_id,
            payload.item_name, payload.quantity, payload.unit,
            payload.source_posko_id, payload.destination_posko_id,
            payload.notes, payload.destination_posko_id, payload.created_by_user_id
        ))
        in_row = rows_to_dicts(cur)[0]

        cur.execute("""
        INSERT INTO distribution_flows
        (id, disaster_event_id, destination_node_id, eta_final, status)
        VALUES (%s,%s,%s,%s,'stock_transferred')
        RETURNING *;
        """, (
            flow_id, payload.disaster_event_id,
            payload.destination_posko_id, "internal transfer"
        ))
        flow_row = rows_to_dicts(cur)[0]

        conn.commit()

        return {
            "status": "stock_transferred",
            "source_stock_out": out_row,
            "destination_stock_in": in_row,
            "distribution_flow": flow_row
        }

class KitchenMealProductionCreate(BaseModel):
    disaster_event_id: str
    posko_id: str
    meal_name: str
    portions: int
    production_time: Optional[str] = None
    target_distribution_location: Optional[str] = None
    ingredients: list[dict] = []
    notes: Optional[str] = None
    created_by_user_id: Optional[str] = "kitchen-operator"

@app.get("/kitchen-context/{posko_id}")
def get_kitchen_context(posko_id: str):
    result = {
        "posko_context": None,
        "meal_productions": [],
        "generated_at": datetime.utcnow().isoformat(),
    }

    with get_conn() as conn, conn.cursor() as cur:
        # reuse posko context logic by reading same data directly
        cur.execute("SELECT * FROM posko_nodes WHERE id = %s;", (posko_id,))
        posko_rows = rows_to_dicts(cur)
        if not posko_rows:
            raise HTTPException(status_code=404, detail="Kitchen posko not found")

        posko = posko_rows[0]

        cur.execute("""
        SELECT
          item_name,
          unit,
          SUM(
            CASE
              WHEN movement_direction = 'in' THEN quantity
              WHEN movement_direction = 'out' THEN -quantity
              ELSE 0
            END
          ) AS current_quantity
        FROM stock_movements
        WHERE posko_id = %s
          AND deleted_at IS NULL
        GROUP BY item_name, unit
        ORDER BY item_name;
        """, (posko_id,))
        stock_summary = rows_to_dicts(cur)

        cur.execute("""
        SELECT *
        FROM stock_movements
        WHERE posko_id = %s
          AND deleted_at IS NULL
        ORDER BY created_at DESC
        LIMIT 100;
        """, (posko_id,))
        stock_movements = rows_to_dicts(cur)

        cur.execute("""
        SELECT *
        FROM kitchen_meal_productions
        WHERE posko_id = %s
          AND deleted_at IS NULL
        ORDER BY created_at DESC;
        """, (posko_id,))
        meals = rows_to_dicts(cur)

        result["posko_context"] = {
            "posko": posko,
            "stock_summary": stock_summary,
            "stock_movements": stock_movements,
        }
        result["meal_productions"] = meals

    return result

@app.post("/kitchen-meal-production")
def create_kitchen_meal_production(payload: KitchenMealProductionCreate):
    meal_id = "meal-" + uuid.uuid4().hex[:12]

    if payload.portions <= 0:
        raise HTTPException(status_code=400, detail="Portions must be positive")

    with get_conn() as conn, conn.cursor() as cur:
        # Check stock for each ingredient before deducting
        for ing in payload.ingredients:
            item_name = ing.get("item_name")
            quantity = float(ing.get("quantity", 0))
            unit = ing.get("unit")

            if not item_name or quantity <= 0 or not unit:
                raise HTTPException(status_code=400, detail="Each ingredient needs item_name, quantity, and unit")

            cur.execute("""
            SELECT COALESCE(SUM(
                CASE
                  WHEN movement_direction = 'in' THEN quantity
                  WHEN movement_direction = 'out' THEN -quantity
                  ELSE 0
                END
            ), 0) AS current_quantity
            FROM stock_movements
            WHERE posko_id = %s
              AND item_name = %s
              AND unit = %s
              AND deleted_at IS NULL;
            """, (payload.posko_id, item_name, unit))
            current_qty = rows_to_dicts(cur)[0]["current_quantity"] or 0

            if float(current_qty) < quantity:
                raise HTTPException(
                    status_code=400,
                    detail=f"Insufficient stock for {item_name}. Current stock is {current_qty} {unit}"
                )

        # Create meal production row
        cur.execute("""
        INSERT INTO kitchen_meal_productions
        (id, disaster_event_id, posko_id, meal_name, portions,
         production_time, target_distribution_location, status,
         ingredients_json, notes, owner_type, owner_id,
         verification_status, created_by_user_id)
        VALUES
        (%s,%s,%s,%s,%s,%s,%s,'prepared',%s,%s,'posko',%s,'self_reported',%s)
        RETURNING *;
        """, (
            meal_id,
            payload.disaster_event_id,
            payload.posko_id,
            payload.meal_name,
            payload.portions,
            payload.production_time,
            payload.target_distribution_location,
            json.dumps(payload.ingredients, default=str),
            payload.notes,
            payload.posko_id,
            payload.created_by_user_id,
        ))
        meal_row = rows_to_dicts(cur)[0]

        # Deduct ingredients as stock_out
        ingredient_movements = []
        for ing in payload.ingredients:
            stock_id = "stock-" + uuid.uuid4().hex[:12]
            cur.execute("""
            INSERT INTO stock_movements
            (id, disaster_event_id, posko_id, item_name, quantity, unit,
             movement_type, movement_direction, source_type, source_id,
             destination_type, destination_id, notes,
             owner_type, owner_id, verification_status, created_by_user_id)
            VALUES
            (%s,%s,%s,%s,%s,%s,
             'kitchen_use','out','stock',%s,
             'kitchen_meal',%s,%s,
             'posko',%s,'self_reported',%s)
            RETURNING *;
            """, (
                stock_id,
                payload.disaster_event_id,
                payload.posko_id,
                ing.get("item_name"),
                float(ing.get("quantity", 0)),
                ing.get("unit"),
                payload.posko_id,
                meal_id,
                f"Used for meal production: {payload.meal_name}",
                payload.posko_id,
                payload.created_by_user_id,
            ))
            ingredient_movements.append(rows_to_dicts(cur)[0])

        conn.commit()

        return {
            "status": "prepared",
            "meal_production": meal_row,
            "ingredient_stock_movements": ingredient_movements
        }

class MedicalCaseCreate(BaseModel):
    disaster_event_id: str
    posko_id: str
    patient_code: str
    age_group: Optional[str] = None
    gender: Optional[str] = None
    complaint: str
    severity: Optional[str] = "minor"
    triage_status: Optional[str] = "green"
    treatment_notes: Optional[str] = None
    referral_needed: Optional[bool] = False
    referral_destination: Optional[str] = None
    status: Optional[str] = "treated"
    created_by_user_id: Optional[str] = "medical-operator"

class MedicalSupplyUseCreate(BaseModel):
    disaster_event_id: str
    posko_id: str
    medical_case_id: Optional[str] = None
    item_name: str
    quantity: float
    unit: str
    notes: Optional[str] = None
    created_by_user_id: Optional[str] = "medical-operator"

@app.get("/medical-context/{posko_id}")
def get_medical_context(posko_id: str):
    result = {
        "posko": None,
        "stock_summary": [],
        "stock_movements": [],
        "medical_cases": [],
        "medical_supply_uses": [],
        "generated_at": datetime.utcnow().isoformat(),
    }

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM posko_nodes WHERE id = %s;", (posko_id,))
        posko_rows = rows_to_dicts(cur)
        if not posko_rows:
            raise HTTPException(status_code=404, detail="Medical posko not found")

        result["posko"] = posko_rows[0]

        cur.execute("""
        SELECT
          item_name,
          unit,
          SUM(
            CASE
              WHEN movement_direction = 'in' THEN quantity
              WHEN movement_direction = 'out' THEN -quantity
              ELSE 0
            END
          ) AS current_quantity
        FROM stock_movements
        WHERE posko_id = %s
          AND deleted_at IS NULL
        GROUP BY item_name, unit
        ORDER BY item_name;
        """, (posko_id,))
        result["stock_summary"] = rows_to_dicts(cur)

        cur.execute("""
        SELECT *
        FROM stock_movements
        WHERE posko_id = %s
          AND deleted_at IS NULL
        ORDER BY created_at DESC
        LIMIT 100;
        """, (posko_id,))
        result["stock_movements"] = rows_to_dicts(cur)

        cur.execute("""
        SELECT *
        FROM medical_cases
        WHERE posko_id = %s
          AND deleted_at IS NULL
        ORDER BY created_at DESC;
        """, (posko_id,))
        result["medical_cases"] = rows_to_dicts(cur)

        cur.execute("""
        SELECT *
        FROM medical_supply_uses
        WHERE posko_id = %s
          AND deleted_at IS NULL
        ORDER BY created_at DESC;
        """, (posko_id,))
        result["medical_supply_uses"] = rows_to_dicts(cur)

    return result

@app.post("/medical-cases")
def create_medical_case(payload: MedicalCaseCreate):
    case_id = "medcase-" + uuid.uuid4().hex[:12]

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
        INSERT INTO medical_cases
        (id, disaster_event_id, posko_id, patient_code, age_group, gender,
         complaint, severity, triage_status, treatment_notes,
         referral_needed, referral_destination, status,
         owner_type, owner_id, created_by_user_id)
        VALUES
        (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'posko',%s,%s)
        RETURNING *;
        """, (
            case_id,
            payload.disaster_event_id,
            payload.posko_id,
            payload.patient_code,
            payload.age_group,
            payload.gender,
            payload.complaint,
            payload.severity,
            payload.triage_status,
            payload.treatment_notes,
            payload.referral_needed,
            payload.referral_destination,
            payload.status,
            payload.posko_id,
            payload.created_by_user_id,
        ))

        row = rows_to_dicts(cur)[0]
        conn.commit()
        return row

@app.post("/medical-supply-use")
def create_medical_supply_use(payload: MedicalSupplyUseCreate):
    use_id = "meduse-" + uuid.uuid4().hex[:12]
    stock_id = "stock-" + uuid.uuid4().hex[:12]

    if payload.quantity <= 0:
        raise HTTPException(status_code=400, detail="Quantity must be positive")

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
        SELECT COALESCE(SUM(
            CASE
              WHEN movement_direction = 'in' THEN quantity
              WHEN movement_direction = 'out' THEN -quantity
              ELSE 0
            END
        ), 0) AS current_quantity
        FROM stock_movements
        WHERE posko_id = %s
          AND item_name = %s
          AND unit = %s
          AND deleted_at IS NULL;
        """, (payload.posko_id, payload.item_name, payload.unit))
        current_qty = rows_to_dicts(cur)[0]["current_quantity"] or 0

        if float(current_qty) < payload.quantity:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient medical stock for {payload.item_name}. Current stock is {current_qty} {payload.unit}"
            )

        cur.execute("""
        INSERT INTO medical_supply_uses
        (id, disaster_event_id, posko_id, medical_case_id,
         item_name, quantity, unit, notes,
         owner_type, owner_id, created_by_user_id)
        VALUES
        (%s,%s,%s,%s,%s,%s,%s,%s,'posko',%s,%s)
        RETURNING *;
        """, (
            use_id,
            payload.disaster_event_id,
            payload.posko_id,
            payload.medical_case_id,
            payload.item_name,
            payload.quantity,
            payload.unit,
            payload.notes,
            payload.posko_id,
            payload.created_by_user_id,
        ))
        use_row = rows_to_dicts(cur)[0]

        cur.execute("""
        INSERT INTO stock_movements
        (id, disaster_event_id, posko_id, item_name, quantity, unit,
         movement_type, movement_direction, source_type, source_id,
         destination_type, destination_id, notes,
         owner_type, owner_id, verification_status, created_by_user_id)
        VALUES
        (%s,%s,%s,%s,%s,%s,
         'medical_use','out','stock',%s,
         'medical_case',%s,%s,
         'posko',%s,'self_reported',%s)
        RETURNING *;
        """, (
            stock_id,
            payload.disaster_event_id,
            payload.posko_id,
            payload.item_name,
            payload.quantity,
            payload.unit,
            payload.posko_id,
            payload.medical_case_id,
            payload.notes or f"Medical supply used: {payload.item_name}",
            payload.posko_id,
            payload.created_by_user_id,
        ))
        stock_row = rows_to_dicts(cur)[0]

        conn.commit()

        return {
            "medical_supply_use": use_row,
            "stock_movement": stock_row
        }

class ShelterOccupancyCreate(BaseModel):
    disaster_event_id: str
    posko_id: str
    shelter_name: str
    capacity_total: int = 0
    current_occupancy: int = 0
    families_count: Optional[int] = 0
    children_count: Optional[int] = 0
    elderly_count: Optional[int] = 0
    disabled_count: Optional[int] = 0
    sanitation_status: Optional[str] = "unknown"
    water_status: Optional[str] = "unknown"
    electricity_status: Optional[str] = "unknown"
    safety_status: Optional[str] = "unknown"
    notes: Optional[str] = None
    status: Optional[str] = "active"
    created_by_user_id: Optional[str] = "shelter-operator"

class ShelterNeedCreate(BaseModel):
    disaster_event_id: str
    posko_id: str
    item_name: str
    quantity_needed: float
    unit: str
    priority: Optional[str] = "normal"
    needed_before: Optional[str] = None
    notes: Optional[str] = None
    created_by_user_id: Optional[str] = "shelter-operator"

@app.get("/shelter-context/{posko_id}")
def get_shelter_context(posko_id: str):
    result = {
        "posko": None,
        "stock_summary": [],
        "stock_movements": [],
        "shelter_occupancies": [],
        "shelter_needs": [],
        "distribution_flows": [],
        "generated_at": datetime.utcnow().isoformat(),
    }

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM posko_nodes WHERE id = %s;", (posko_id,))
        posko_rows = rows_to_dicts(cur)
        if not posko_rows:
            raise HTTPException(status_code=404, detail="Shelter posko not found")

        result["posko"] = posko_rows[0]

        cur.execute("""
        SELECT
          item_name,
          unit,
          SUM(
            CASE
              WHEN movement_direction = 'in' THEN quantity
              WHEN movement_direction = 'out' THEN -quantity
              ELSE 0
            END
          ) AS current_quantity
        FROM stock_movements
        WHERE posko_id = %s
          AND deleted_at IS NULL
        GROUP BY item_name, unit
        ORDER BY item_name;
        """, (posko_id,))
        result["stock_summary"] = rows_to_dicts(cur)

        cur.execute("""
        SELECT *
        FROM stock_movements
        WHERE posko_id = %s
          AND deleted_at IS NULL
        ORDER BY created_at DESC
        LIMIT 100;
        """, (posko_id,))
        result["stock_movements"] = rows_to_dicts(cur)

        cur.execute("""
        SELECT *
        FROM shelter_occupancies
        WHERE posko_id = %s
          AND deleted_at IS NULL
        ORDER BY created_at DESC;
        """, (posko_id,))
        result["shelter_occupancies"] = rows_to_dicts(cur)

        cur.execute("""
        SELECT *
        FROM shelter_needs
        WHERE posko_id = %s
          AND deleted_at IS NULL
        ORDER BY created_at DESC;
        """, (posko_id,))
        result["shelter_needs"] = rows_to_dicts(cur)

        cur.execute("""
        SELECT *
        FROM distribution_flows
        WHERE destination_node_id = %s
        ORDER BY created_at DESC;
        """, (posko_id,))
        result["distribution_flows"] = rows_to_dicts(cur)

    return result

@app.post("/shelter-occupancy")
def create_shelter_occupancy(payload: ShelterOccupancyCreate):
    occ_id = "shelterocc-" + uuid.uuid4().hex[:12]

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
        INSERT INTO shelter_occupancies
        (id, disaster_event_id, posko_id, shelter_name,
         capacity_total, current_occupancy, families_count,
         children_count, elderly_count, disabled_count,
         sanitation_status, water_status, electricity_status, safety_status,
         notes, status, owner_type, owner_id, created_by_user_id)
        VALUES
        (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'posko',%s,%s)
        RETURNING *;
        """, (
            occ_id,
            payload.disaster_event_id,
            payload.posko_id,
            payload.shelter_name,
            payload.capacity_total,
            payload.current_occupancy,
            payload.families_count,
            payload.children_count,
            payload.elderly_count,
            payload.disabled_count,
            payload.sanitation_status,
            payload.water_status,
            payload.electricity_status,
            payload.safety_status,
            payload.notes,
            payload.status,
            payload.posko_id,
            payload.created_by_user_id,
        ))
        row = rows_to_dicts(cur)[0]
        conn.commit()
        return row

@app.post("/shelter-needs")
def create_shelter_need(payload: ShelterNeedCreate):
    need_id = "shelterneeds-" + uuid.uuid4().hex[:12]

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
        INSERT INTO shelter_needs
        (id, disaster_event_id, posko_id, item_name, quantity_needed, unit,
         priority, needed_before, status, notes,
         owner_type, owner_id, created_by_user_id)
        VALUES
        (%s,%s,%s,%s,%s,%s,%s,%s,'open',%s,'posko',%s,%s)
        RETURNING *;
        """, (
            need_id,
            payload.disaster_event_id,
            payload.posko_id,
            payload.item_name,
            payload.quantity_needed,
            payload.unit,
            payload.priority,
            payload.needed_before,
            payload.notes,
            payload.posko_id,
            payload.created_by_user_id,
        ))
        row = rows_to_dicts(cur)[0]
        conn.commit()
        return row

class MissingPersonReportCreate(BaseModel):
    disaster_event_id: str
    reporter_name: Optional[str] = None
    reporter_contact: Optional[str] = None
    reporter_relation: Optional[str] = None
    person_code: str
    person_name: Optional[str] = None
    age_group: Optional[str] = None
    gender: Optional[str] = None
    last_seen_location: Optional[str] = None
    last_seen_time: Optional[str] = None
    description: Optional[str] = None
    clothing_description: Optional[str] = None
    special_notes: Optional[str] = None
    source_posko_id: Optional[str] = None
    source_organization_id: Optional[str] = None
    created_by_user_id: Optional[str] = "search-found-operator"

class FoundPersonReportCreate(BaseModel):
    disaster_event_id: str
    finder_name: Optional[str] = None
    finder_contact: Optional[str] = None
    person_code: str
    person_name: Optional[str] = None
    age_group: Optional[str] = None
    gender: Optional[str] = None
    found_location: Optional[str] = None
    found_time: Optional[str] = None
    current_location: Optional[str] = None
    condition_notes: Optional[str] = None
    description: Optional[str] = None
    clothing_description: Optional[str] = None
    special_notes: Optional[str] = None
    source_posko_id: Optional[str] = None
    source_organization_id: Optional[str] = None
    created_by_user_id: Optional[str] = "search-found-operator"

class SearchFoundMatchCreate(BaseModel):
    disaster_event_id: str
    missing_report_id: str
    found_report_id: str
    match_score: Optional[float] = 0
    match_reason: Optional[str] = None
    status: Optional[str] = "candidate"
    created_by_user_id: Optional[str] = "search-found-operator"

@app.get("/search-found-context/{disaster_event_id}")
def get_search_found_context(disaster_event_id: str):
    result = {
        "disaster_event_id": disaster_event_id,
        "missing_person_reports": [],
        "found_person_reports": [],
        "matches": [],
        "summary": {},
        "generated_at": datetime.utcnow().isoformat(),
    }

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
        SELECT *
        FROM missing_person_reports
        WHERE disaster_event_id = %s
          AND deleted_at IS NULL
        ORDER BY created_at DESC;
        """, (disaster_event_id,))
        result["missing_person_reports"] = rows_to_dicts(cur)

        cur.execute("""
        SELECT *
        FROM found_person_reports
        WHERE disaster_event_id = %s
          AND deleted_at IS NULL
        ORDER BY created_at DESC;
        """, (disaster_event_id,))
        result["found_person_reports"] = rows_to_dicts(cur)

        cur.execute("""
        SELECT
          m.*,
          mp.person_code AS missing_person_code,
          mp.person_name AS missing_person_name,
          fp.person_code AS found_person_code,
          fp.person_name AS found_person_name
        FROM search_found_matches m
        LEFT JOIN missing_person_reports mp ON mp.id = m.missing_report_id
        LEFT JOIN found_person_reports fp ON fp.id = m.found_report_id
        WHERE m.disaster_event_id = %s
          AND m.deleted_at IS NULL
        ORDER BY m.created_at DESC;
        """, (disaster_event_id,))
        result["matches"] = rows_to_dicts(cur)

        result["summary"] = {
            "missing_count": len(result["missing_person_reports"]),
            "found_count": len(result["found_person_reports"]),
            "match_count": len(result["matches"]),
            "reunited_count": len([x for x in result["matches"] if x.get("status") == "reunited"]),
        }

    return result

@app.post("/missing-person-reports")
def create_missing_person_report(payload: MissingPersonReportCreate):
    report_id = "missing-" + uuid.uuid4().hex[:12]

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
        INSERT INTO missing_person_reports
        (id, disaster_event_id, reporter_name, reporter_contact, reporter_relation,
         person_code, person_name, age_group, gender,
         last_seen_location, last_seen_time, description, clothing_description,
         special_notes, status, source_posko_id, source_organization_id,
         created_by_user_id)
        VALUES
        (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'missing',%s,%s,%s)
        RETURNING *;
        """, (
            report_id,
            payload.disaster_event_id,
            payload.reporter_name,
            payload.reporter_contact,
            payload.reporter_relation,
            payload.person_code,
            payload.person_name,
            payload.age_group,
            payload.gender,
            payload.last_seen_location,
            payload.last_seen_time,
            payload.description,
            payload.clothing_description,
            payload.special_notes,
            payload.source_posko_id,
            payload.source_organization_id,
            payload.created_by_user_id,
        ))
        row = rows_to_dicts(cur)[0]
        conn.commit()
        return row

@app.post("/found-person-reports")
def create_found_person_report(payload: FoundPersonReportCreate):
    report_id = "found-" + uuid.uuid4().hex[:12]

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
        INSERT INTO found_person_reports
        (id, disaster_event_id, finder_name, finder_contact,
         person_code, person_name, age_group, gender,
         found_location, found_time, current_location, condition_notes,
         description, clothing_description, special_notes, status,
         source_posko_id, source_organization_id, created_by_user_id)
        VALUES
        (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'found',%s,%s,%s)
        RETURNING *;
        """, (
            report_id,
            payload.disaster_event_id,
            payload.finder_name,
            payload.finder_contact,
            payload.person_code,
            payload.person_name,
            payload.age_group,
            payload.gender,
            payload.found_location,
            payload.found_time,
            payload.current_location,
            payload.condition_notes,
            payload.description,
            payload.clothing_description,
            payload.special_notes,
            payload.source_posko_id,
            payload.source_organization_id,
            payload.created_by_user_id,
        ))
        row = rows_to_dicts(cur)[0]
        conn.commit()
        return row

@app.post("/search-found-matches")
def create_search_found_match(payload: SearchFoundMatchCreate):
    match_id = "match-" + uuid.uuid4().hex[:12]

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
        INSERT INTO search_found_matches
        (id, disaster_event_id, missing_report_id, found_report_id,
         match_score, match_reason, status, created_by_user_id)
        VALUES
        (%s,%s,%s,%s,%s,%s,%s,%s)
        RETURNING *;
        """, (
            match_id,
            payload.disaster_event_id,
            payload.missing_report_id,
            payload.found_report_id,
            payload.match_score,
            payload.match_reason,
            payload.status,
            payload.created_by_user_id,
        ))
        row = rows_to_dicts(cur)[0]

        if payload.status == "reunited":
            cur.execute("UPDATE missing_person_reports SET status = 'reunited', updated_at = NOW() WHERE id = %s;", (payload.missing_report_id,))
            cur.execute("UPDATE found_person_reports SET status = 'reunited', updated_at = NOW() WHERE id = %s;", (payload.found_report_id,))

        conn.commit()
        return row

class SearchFoundMatchStatusUpdate(BaseModel):
    status: str
    reviewed_by: Optional[str] = "search-found-operator"
    reunion_notes: Optional[str] = None

@app.post("/search-found-matches/{match_id}/status")
def update_search_found_match_status(match_id: str, payload: SearchFoundMatchStatusUpdate):
    if payload.status not in ["candidate", "investigating", "reunited", "rejected"]:
        raise HTTPException(status_code=400, detail="Invalid status")

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
        UPDATE search_found_matches
        SET status = %s,
            reviewed_by = %s,
            reviewed_at = NOW(),
            reunion_notes = %s,
            updated_at = NOW()
        WHERE id = %s
          AND deleted_at IS NULL
        RETURNING *;
        """, (
            payload.status,
            payload.reviewed_by,
            payload.reunion_notes,
            match_id,
        ))
        rows = rows_to_dicts(cur)

        if not rows:
            raise HTTPException(status_code=404, detail="Match not found")

        match = rows[0]

        if payload.status == "reunited":
            cur.execute("""
            UPDATE missing_person_reports
            SET status = 'reunited',
                updated_at = NOW()
            WHERE id = %s;
            """, (match["missing_report_id"],))

            cur.execute("""
            UPDATE found_person_reports
            SET status = 'reunited',
                updated_at = NOW()
            WHERE id = %s;
            """, (match["found_report_id"],))

        if payload.status == "rejected":
            cur.execute("""
            UPDATE missing_person_reports
            SET status = 'missing',
                updated_at = NOW()
            WHERE id = %s
              AND status <> 'reunited';
            """, (match["missing_report_id"],))

            cur.execute("""
            UPDATE found_person_reports
            SET status = 'found',
                updated_at = NOW()
            WHERE id = %s
              AND status <> 'reunited';
            """, (match["found_report_id"],))

        conn.commit()
        return match


class AiUserKeySave(BaseModel):
    user_id: str
    organization_id: Optional[str] = None
    provider: Optional[str] = "openai"
    model_name: Optional[str] = "gpt-4o-mini"
    api_key: str
    api_key_label: Optional[str] = None

class AiUserModelUpdate(BaseModel):
    user_id: str
    provider: Optional[str] = "openai"
    model_name: str


def encrypt_ai_key(api_key: str) -> str:
    return get_ai_key_fernet().encrypt(api_key.encode()).decode()

def decrypt_ai_key(encrypted_api_key: str) -> str:
    return get_ai_key_fernet().decrypt(encrypted_api_key.encode()).decode()


@app.post("/ai/user-key")
def save_ai_user_key(payload: AiUserKeySave):
    setting_id = "aikey-" + uuid.uuid4().hex[:12]

    api_key = payload.api_key.strip()
    if len(api_key) < 20:
        raise HTTPException(status_code=400, detail="API key is too short")

    encrypted = encrypt_ai_key(api_key)
    last4 = api_key[-4:]

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
        INSERT INTO ai_user_settings
        (id, user_id, organization_id, provider, model_name,
         encrypted_api_key, api_key_last4, api_key_label,
         status, owner_type, owner_id, created_by_user_id, updated_by_user_id)
        VALUES
        (%s,%s,%s,%s,%s,%s,%s,%s,
         'active','user',%s,%s,%s)
        ON CONFLICT (user_id, provider)
        DO UPDATE SET
          organization_id = EXCLUDED.organization_id,
          model_name = EXCLUDED.model_name,
          encrypted_api_key = EXCLUDED.encrypted_api_key,
          api_key_last4 = EXCLUDED.api_key_last4,
          api_key_label = EXCLUDED.api_key_label,
          status = 'active',
          updated_by_user_id = EXCLUDED.updated_by_user_id,
          updated_at = NOW()
        RETURNING id, user_id, organization_id, provider, model_name,
                  api_key_last4, api_key_label, status, created_at, updated_at;
        """, (
            setting_id,
            payload.user_id,
            payload.organization_id,
            payload.provider,
            payload.model_name,
            encrypted,
            last4,
            payload.api_key_label,
            payload.user_id,
            payload.user_id,
            payload.user_id,
        ))

        row = rows_to_dicts(cur)[0]
        conn.commit()

        return {
            "status": "saved",
            "message": "AI key saved encrypted. Secret key is not returned.",
            "setting": row
        }

@app.get("/ai/user-key/{user_id}")
def get_ai_user_key_status(user_id: str, provider: str = "openai"):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
        SELECT id, user_id, organization_id, provider, model_name,
               api_key_last4, api_key_label, status, created_at, updated_at
        FROM ai_user_settings
        WHERE user_id = %s
          AND provider = %s
          AND status = 'active';
        """, (user_id, provider))

        rows = rows_to_dicts(cur)
        if not rows:
            return {
                "user_id": user_id,
                "provider": provider,
                "key_exists": False,
                "message": "No active AI key configured"
            }

        row = rows[0]
        return {
            "user_id": user_id,
            "provider": provider,
            "key_exists": True,
            "masked_key": "****" + (row.get("api_key_last4") or ""),
            "setting": row
        }

@app.post("/ai/user-model")
def update_ai_user_model(payload: AiUserModelUpdate):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
        UPDATE ai_user_settings
        SET model_name = %s,
            updated_by_user_id = %s,
            updated_at = NOW()
        WHERE user_id = %s
          AND provider = %s
          AND status = 'active'
        RETURNING id, user_id, provider, model_name, api_key_last4, status, updated_at;
        """, (
            payload.model_name,
            payload.user_id,
            payload.user_id,
            payload.provider,
        ))

        rows = rows_to_dicts(cur)
        if not rows:
            raise HTTPException(status_code=404, detail="AI user setting not found")

        conn.commit()
        return rows[0]

@app.delete("/ai/user-key/{user_id}")
def delete_ai_user_key(user_id: str, provider: str = "openai"):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
        UPDATE ai_user_settings
        SET status = 'deleted',
            updated_at = NOW()
        WHERE user_id = %s
          AND provider = %s
          AND status = 'active'
        RETURNING id, user_id, provider, status, updated_at;
        """, (user_id, provider))

        rows = rows_to_dicts(cur)
        conn.commit()

        if not rows:
            return {"status": "not_found", "user_id": user_id, "provider": provider}

        return {"status": "deleted", "setting": rows[0]}


from openai import OpenAI
from app_shared import encrypt_ai_key, decrypt_ai_key

class AiAskRequest(BaseModel):
    user_id: str
    disaster_event_id: str
    question: str
    provider: Optional[str] = "openai"

def get_user_ai_setting(user_id: str, provider: str = "openai"):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
        SELECT *
        FROM ai_user_settings
        WHERE user_id = %s
          AND provider = %s
          AND status = 'active'
        ORDER BY updated_at DESC
        LIMIT 1;
        """, (user_id, provider))
        rows = rows_to_dicts(cur)
        return rows[0] if rows else None

@app.post("/ai/ask")
def ai_ask(payload: AiAskRequest):
    if not payload.question.strip():
        raise HTTPException(status_code=400, detail="Question is required")

    setting = get_user_ai_setting(payload.user_id, payload.provider)
    if not setting:
        raise HTTPException(
            status_code=400,
            detail="No active AI key configured for this user. Please add key in AI Settings."
        )

    api_key = decrypt_ai_key(setting["encrypted_api_key"])
    model_name = setting.get("model_name") or "gpt-4o-mini"

    # Build context directly from database using existing AI context route function
    context = get_ai_context(payload.disaster_event_id)

    compact_context = {
        "disaster": context.get("disaster"),
        "summary": context.get("summary"),
        "alerts": context.get("alerts", [])[:30],
        "recommendations": context.get("recommendations", [])[:30],
        "stock_summary": context.get("stock_summary", [])[:80],
        "logistic_needs": context.get("logistic_needs", [])[:80],
        "aid_offers": context.get("aid_offers", [])[:80],
        "distribution_flows": context.get("distribution_flows", [])[:80],
        "kitchen_meal_productions": context.get("kitchen_meal_productions", [])[:50],
        "medical_cases": context.get("medical_cases", [])[:50],
        "shelter_occupancies": context.get("shelter_occupancies", [])[:50],
        "shelter_needs": context.get("shelter_needs", [])[:50],
        "missing_person_reports": context.get("missing_person_reports", [])[:50],
        "found_person_reports": context.get("found_person_reports", [])[:50],
        "search_found_matches": context.get("search_found_matches", [])[:50],
    }

    system_prompt = """
You are Rescue-Net AI Situation Analyst.
Analyze disaster response data and answer operationally.
Be concise, practical, and safety-focused.
Do not expose private API keys.
For medical/search-found data, avoid exposing unnecessary personal identity.
Prioritize urgent needs, logistics gaps, shelter capacity, medical risk, stock shortages, and search & found coordination.
"""

    client = OpenAI(api_key=api_key)

    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "Rescue-Net context JSON:\n" + json.dumps(compact_context, default=str)},
                {"role": "user", "content": payload.question},
            ],
            temperature=0.2,
        )
    except Exception as e:
        err = str(e)

        if "Incorrect API key" in err or "invalid_api_key" in err or "401" in err:
            raise HTTPException(
                status_code=401,
                detail="AI request failed: invalid API key. Please update your AI key in AI Settings."
            )

        raise HTTPException(
            status_code=500,
            detail="AI request failed. Please check AI provider, model, quota, and network settings."
        )

    answer = response.choices[0].message.content

    return {
        "user_id": payload.user_id,
        "provider": payload.provider,
        "model_name": model_name,
        "disaster_event_id": payload.disaster_event_id,
        "question": payload.question,
        "answer": answer,
        "context_summary": context.get("summary"),
        "alerts_count": len(context.get("alerts", [])),
        "recommendations_count": len(context.get("recommendations", [])),
        "key_used": "****" + (setting.get("api_key_last4") or "")
    }

class VolunteerProfileCreate(BaseModel):
    disaster_event_id: str
    volunteer_name: str
    contact: Optional[str] = None
    skill_tags: Optional[str] = None
    availability_status: Optional[str] = "available"
    current_location: Optional[str] = None
    assigned_posko_id: Optional[str] = None
    notes: Optional[str] = None

class VolunteerAssignmentCreate(BaseModel):
    disaster_event_id: str
    volunteer_id: str
    assigned_to_type: Optional[str] = "posko"
    assigned_to_id: Optional[str] = None
    task_name: str
    task_description: Optional[str] = None
    priority: Optional[str] = "normal"
    created_by_user_id: Optional[str] = "volunteer-operator"

class WorkToolRequestCreate(BaseModel):
    disaster_event_id: str
    requested_by_type: Optional[str] = "posko"
    requested_by_id: Optional[str] = None
    tool_name: str
    tool_type: Optional[str] = None
    quantity: Optional[float] = 1
    unit: Optional[str] = "unit"
    location: Optional[str] = None
    needed_for: Optional[str] = None
    priority: Optional[str] = "normal"
    required_operator_skill: Optional[str] = None
    notes: Optional[str] = None
    created_by_user_id: Optional[str] = "worktool-operator"

@app.get("/volunteer-context/{disaster_event_id}")
def get_volunteer_context(disaster_event_id: str):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
        SELECT * FROM volunteer_profiles
        WHERE disaster_event_id = %s AND deleted_at IS NULL
        ORDER BY created_at DESC;
        """, (disaster_event_id,))
        volunteers = rows_to_dicts(cur)

        cur.execute("""
        SELECT va.*, vp.volunteer_name
        FROM volunteer_assignments va
        LEFT JOIN volunteer_profiles vp ON vp.id = va.volunteer_id
        WHERE va.disaster_event_id = %s AND va.deleted_at IS NULL
        ORDER BY va.created_at DESC;
        """, (disaster_event_id,))
        assignments = rows_to_dicts(cur)

        return {
            "disaster_event_id": disaster_event_id,
            "volunteers": volunteers,
            "assignments": assignments,
            "summary": {
                "volunteer_count": len(volunteers),
                "available_count": len([v for v in volunteers if v.get("availability_status") == "available"]),
                "assignment_count": len(assignments),
            },
            "generated_at": datetime.utcnow().isoformat()
        }

@app.post("/volunteers")
def create_volunteer_profile(payload: VolunteerProfileCreate):
    volunteer_id = "vol-" + uuid.uuid4().hex[:12]

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
        INSERT INTO volunteer_profiles
        (id, disaster_event_id, volunteer_name, contact, skill_tags,
         availability_status, current_location, assigned_posko_id, notes)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        RETURNING *;
        """, (
            volunteer_id,
            payload.disaster_event_id,
            payload.volunteer_name,
            payload.contact,
            payload.skill_tags,
            payload.availability_status,
            payload.current_location,
            payload.assigned_posko_id,
            payload.notes,
        ))
        row = rows_to_dicts(cur)[0]
        conn.commit()
        return row

@app.post("/volunteer-assignments")
def create_volunteer_assignment(payload: VolunteerAssignmentCreate):
    assignment_id = "volassign-" + uuid.uuid4().hex[:12]

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
        INSERT INTO volunteer_assignments
        (id, disaster_event_id, volunteer_id, assigned_to_type, assigned_to_id,
         task_name, task_description, priority, status, created_by_user_id)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'assigned',%s)
        RETURNING *;
        """, (
            assignment_id,
            payload.disaster_event_id,
            payload.volunteer_id,
            payload.assigned_to_type,
            payload.assigned_to_id,
            payload.task_name,
            payload.task_description,
            payload.priority,
            payload.created_by_user_id,
        ))
        row = rows_to_dicts(cur)[0]

        cur.execute("""
        UPDATE volunteer_profiles
        SET availability_status = 'assigned',
            assigned_posko_id = %s,
            updated_at = NOW()
        WHERE id = %s;
        """, (payload.assigned_to_id, payload.volunteer_id))

        conn.commit()
        return row

@app.get("/work-tools-context/{disaster_event_id}")
def get_work_tools_context(disaster_event_id: str):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
        SELECT *
        FROM work_tool_requests
        WHERE disaster_event_id = %s AND deleted_at IS NULL
        ORDER BY created_at DESC;
        """, (disaster_event_id,))
        requests = rows_to_dicts(cur)

        return {
            "disaster_event_id": disaster_event_id,
            "work_tool_requests": requests,
            "summary": {
                "request_count": len(requests),
                "open_count": len([r for r in requests if r.get("status") == "requested"]),
                "urgent_count": len([r for r in requests if r.get("priority") in ["urgent", "critical"]]),
            },
            "generated_at": datetime.utcnow().isoformat()
        }

@app.post("/work-tool-requests")
def create_work_tool_request(payload: WorkToolRequestCreate):
    request_id = "toolreq-" + uuid.uuid4().hex[:12]

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
        INSERT INTO work_tool_requests
        (id, disaster_event_id, requested_by_type, requested_by_id,
         tool_name, tool_type, quantity, unit, location, needed_for,
         priority, required_operator_skill, status, notes, created_by_user_id)
        VALUES
        (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'requested',%s,%s)
        RETURNING *;
        """, (
            request_id,
            payload.disaster_event_id,
            payload.requested_by_type,
            payload.requested_by_id,
            payload.tool_name,
            payload.tool_type,
            payload.quantity,
            payload.unit,
            payload.location,
            payload.needed_for,
            payload.priority,
            payload.required_operator_skill,
            payload.notes,
            payload.created_by_user_id,
        ))
        row = rows_to_dicts(cur)[0]
        conn.commit()
        return row

class OfficerInChargeUpdate(BaseModel):
    officer_in_charge_name: Optional[str] = None
    officer_in_charge_phone: Optional[str] = None
    officer_in_charge_role: Optional[str] = None

def update_officer_in_charge(table_name: str, object_id: str, payload: OfficerInChargeUpdate):
    allowed_tables = {
        "transport_spaces": "transport space",
        "distribution_flows": "distribution flow",
        "aid_offers": "aid offer",
        "posko_nodes": "posko",
    }

    if table_name not in allowed_tables:
        raise HTTPException(status_code=400, detail="Invalid table")

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = %s;
        """, (table_name,))
        cols = {r["column_name"] for r in rows_to_dicts(cur)}

        required_cols = {
            "officer_in_charge_name",
            "officer_in_charge_phone",
            "officer_in_charge_role",
        }

        missing = required_cols - cols
        if missing:
            raise HTTPException(
                status_code=500,
                detail=f"Officer columns missing in {table_name}: {sorted(missing)}"
            )

        updated_at_sql = ", updated_at = NOW()" if "updated_at" in cols else ""

        cur.execute(f"""
        UPDATE {table_name}
        SET officer_in_charge_name = %s,
            officer_in_charge_phone = %s,
            officer_in_charge_role = %s
            {updated_at_sql}
        WHERE id = %s
        RETURNING *;
        """, (
            payload.officer_in_charge_name,
            payload.officer_in_charge_phone,
            payload.officer_in_charge_role,
            object_id,
        ))

        rows = rows_to_dicts(cur)
        if not rows:
            raise HTTPException(status_code=404, detail=f"{allowed_tables[table_name]} not found")

        conn.commit()
        return rows[0]


@app.post("/transport-spaces/{transport_id}/officer")
def update_transport_officer(transport_id: str, payload: OfficerInChargeUpdate):
    return update_officer_in_charge("transport_spaces", transport_id, payload)

@app.post("/distribution-flows/{flow_id}/officer")
def update_distribution_flow_officer(flow_id: str, payload: OfficerInChargeUpdate):
    return update_officer_in_charge("distribution_flows", flow_id, payload)

@app.post("/aid-offers/{aid_offer_id}/officer")
def update_aid_offer_officer(aid_offer_id: str, payload: OfficerInChargeUpdate):
    return update_officer_in_charge("aid_offers", aid_offer_id, payload)

@app.post("/poskos/{posko_id}/officer")
def update_posko_officer(posko_id: str, payload: OfficerInChargeUpdate):
    return update_officer_in_charge("posko_nodes", posko_id, payload)

class VerificationActionCreate(BaseModel):
    disaster_event_id: str
    object_type: str
    object_id: str
    action_type: Optional[str] = "verify"
    verification_status: Optional[str] = "verified"
    trust_level: Optional[str] = None
    reviewed_by: Optional[str] = "verification-officer"
    reviewer_role: Optional[str] = "command_center"
    review_notes: Optional[str] = None


class VerifierProfileCreate(BaseModel):
    user_id: Optional[str] = None
    display_name: str
    verifier_type: str = "community"
    organization_id: Optional[str] = None
    position_title: Optional[str] = None
    public_role_description: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    verifier_status: str = "candidate_verifier"
    trust_level: int = 1
    allowed_verification_scope: Optional[list[str]] = None


class VerificationRequestCreate(BaseModel):
    requester_type: str = "self_registration"
    requester_id: Optional[str] = None
    target_type: str
    target_id: str
    requested_verifier_id: Optional[str] = None
    requested_verifier_name: Optional[str] = None
    requested_verifier_phone: Optional[str] = None
    requested_verifier_email: Optional[str] = None
    relationship_description: str
    verification_scope: str = "identity"
    message: Optional[str] = None


class VerificationRequestDecision(BaseModel):
    decision: str
    verifier_id: Optional[str] = None
    verifier_display_name: Optional[str] = None
    verifier_role: Optional[str] = None
    statement: Optional[str] = None
    correction_note: Optional[str] = None


class VerifierStatusUpdate(BaseModel):
    verifier_status: str
    trust_level: Optional[int] = None
    allowed_verification_scope: Optional[list[str]] = None
    reviewed_by: Optional[str] = "rn-command-center"
    notes: Optional[str] = None


class EndorsementRevoke(BaseModel):
    revoked_by: Optional[str] = "rn-command-center"
    reason: str


def ensure_trusted_verifier_tables():
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
        CREATE TABLE IF NOT EXISTS verifier_profiles (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            display_name TEXT NOT NULL,
            verifier_type TEXT NOT NULL DEFAULT 'community',
            organization_id TEXT,
            position_title TEXT,
            public_role_description TEXT,
            phone TEXT,
            email TEXT,
            identity_verification_status TEXT NOT NULL DEFAULT 'pending',
            verifier_status TEXT NOT NULL DEFAULT 'candidate_verifier',
            trust_level INTEGER NOT NULL DEFAULT 1,
            allowed_verification_scope_json JSONB NOT NULL DEFAULT '["identity"]',
            suspicious_activity_count INTEGER NOT NULL DEFAULT 0,
            approved_by TEXT,
            approved_at TIMESTAMP,
            notes TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW()
        );
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS trusted_verification_requests (
            id TEXT PRIMARY KEY,
            requester_type TEXT NOT NULL,
            requester_id TEXT,
            target_type TEXT NOT NULL,
            target_id TEXT NOT NULL,
            requested_verifier_id TEXT,
            requested_verifier_name TEXT,
            requested_verifier_phone TEXT,
            requested_verifier_email TEXT,
            relationship_description TEXT NOT NULL,
            verification_scope TEXT NOT NULL,
            message TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            token_hash TEXT NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            decided_at TIMESTAMP,
            correction_note TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW()
        );
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS verification_endorsements (
            id TEXT PRIMARY KEY,
            request_id TEXT REFERENCES trusted_verification_requests(id) ON DELETE SET NULL,
            target_type TEXT NOT NULL,
            target_id TEXT NOT NULL,
            verifier_id TEXT,
            verifier_display_name TEXT NOT NULL,
            verifier_role TEXT,
            verification_scope TEXT NOT NULL,
            verification_level INTEGER NOT NULL DEFAULT 1,
            statement TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            visible_on_profile BOOLEAN NOT NULL DEFAULT TRUE,
            verified_at TIMESTAMP NOT NULL DEFAULT NOW(),
            expires_at TIMESTAMP,
            revoked_at TIMESTAMP,
            revoked_by TEXT,
            revoke_reason TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW()
        );
        """)
        for table in ("posko_nodes", "organizations"):
            cur.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS identity_verification_status TEXT NOT NULL DEFAULT 'unverified';")
            cur.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS identity_verified_by TEXT;")
            cur.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS identity_verified_at TIMESTAMP;")
            cur.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS trusted_verifier_count INTEGER NOT NULL DEFAULT 0;")
            cur.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS public_verified_badge BOOLEAN NOT NULL DEFAULT FALSE;")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_verifier_profiles_status ON verifier_profiles(verifier_status, trust_level);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_trusted_verification_requests_target ON trusted_verification_requests(target_type, target_id, status);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_verification_endorsements_target ON verification_endorsements(target_type, target_id, status);")
        conn.commit()


def verifier_target_table(target_type: str):
    return {
        "posko": "posko_nodes",
        "organization": "organizations",
        "volunteer": "volunteer_profiles",
        "resource_provider": "organizations",
        "reporter": None,
        "community_report": None,
    }.get(target_type)


def apply_identity_endorsement(cur, target_type: str, target_id: str, verifier_name: str):
    table = verifier_target_table(target_type)
    if not table:
        return
    cur.execute(f"""
    UPDATE {table}
    SET identity_verification_status = 'verified',
        identity_verified_by = %s,
        identity_verified_at = NOW(),
        trusted_verifier_count = trusted_verifier_count + 1,
        public_verified_badge = TRUE
    WHERE id = %s;
    """, (verifier_name, target_id))


@app.post("/public/verifier-profiles")
def register_verifier_profile(payload: VerifierProfileCreate):
    ensure_trusted_verifier_tables()
    allowed_types = {"community", "organization", "government", "public_figure", "rn_admin"}
    if payload.verifier_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Invalid verifier_type")
    verifier_id = "verifier-" + uuid.uuid4().hex[:12]
    scopes = payload.allowed_verification_scope or ["identity"]
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
        INSERT INTO verifier_profiles (
            id, user_id, display_name, verifier_type, organization_id,
            position_title, public_role_description, phone, email,
            verifier_status, trust_level, allowed_verification_scope_json
        )
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        RETURNING *;
        """, (
            verifier_id, payload.user_id, payload.display_name, payload.verifier_type,
            payload.organization_id, payload.position_title, payload.public_role_description,
            payload.phone, payload.email, payload.verifier_status, payload.trust_level,
            json.dumps(scopes)
        ))
        row = rows_to_dicts(cur)[0]
        conn.commit()
    return {"status": "registered", "verifier_profile": row}


@app.get("/verifier-profiles")
def list_verifier_profiles(status: Optional[str] = None, q: Optional[str] = None):
    ensure_trusted_verifier_tables()
    where = ["1=1"]
    params = []
    if status:
        where.append("verifier_status = %s")
        params.append(status)
    if q:
        where.append("(display_name ILIKE %s OR position_title ILIKE %s OR public_role_description ILIKE %s)")
        params.extend([f"%{q}%"] * 3)
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM verifier_profiles WHERE " + " AND ".join(where) + " ORDER BY trust_level DESC, updated_at DESC LIMIT 300;", params)
        return rows_to_dicts(cur)


@app.patch("/verifier-profiles/{verifier_id}/status")
def update_verifier_profile_status(verifier_id: str, payload: VerifierStatusUpdate):
    ensure_trusted_verifier_tables()
    allowed = {"candidate_verifier", "community_verifier", "organization_verifier", "government_verifier", "official_verifier", "trusted_public_verifier", "suspended", "rejected"}
    if payload.verifier_status not in allowed:
        raise HTTPException(status_code=400, detail="Invalid verifier_status")
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
        UPDATE verifier_profiles
        SET verifier_status = %s,
            trust_level = COALESCE(%s, trust_level),
            allowed_verification_scope_json = COALESCE(%s, allowed_verification_scope_json),
            approved_by = %s,
            approved_at = CASE WHEN %s NOT IN ('candidate_verifier','rejected','suspended') THEN NOW() ELSE approved_at END,
            notes = COALESCE(%s, notes),
            updated_at = NOW()
        WHERE id = %s
        RETURNING *;
        """, (
            payload.verifier_status, payload.trust_level,
            json.dumps(payload.allowed_verification_scope) if payload.allowed_verification_scope is not None else None,
            payload.reviewed_by, payload.verifier_status, payload.notes, verifier_id
        ))
        rows = rows_to_dicts(cur)
        conn.commit()
    if not rows:
        raise HTTPException(status_code=404, detail="Verifier not found")
    return {"status": "updated", "verifier_profile": rows[0]}


@app.post("/public/verification-requests")
def create_trusted_verification_request(payload: VerificationRequestCreate):
    ensure_trusted_verifier_tables()
    allowed_targets = {"reporter", "posko", "organization", "volunteer", "resource_provider", "community_report"}
    allowed_scopes = {"identity", "posko_identity", "organization_membership", "location", "report_source"}
    if payload.target_type not in allowed_targets or payload.verification_scope not in allowed_scopes:
        raise HTTPException(status_code=400, detail="Invalid target_type or verification_scope")
    raw_token = secrets.token_urlsafe(32)
    request_id = "verreq-" + uuid.uuid4().hex[:12]
    expires_at = datetime.utcnow() + timedelta(days=7)
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
        INSERT INTO trusted_verification_requests (
            id, requester_type, requester_id, target_type, target_id,
            requested_verifier_id, requested_verifier_name, requested_verifier_phone,
            requested_verifier_email, relationship_description, verification_scope,
            message, status, token_hash, expires_at
        )
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'pending',%s,%s)
        RETURNING *;
        """, (
            request_id, payload.requester_type, payload.requester_id,
            payload.target_type, payload.target_id, payload.requested_verifier_id,
            payload.requested_verifier_name, payload.requested_verifier_phone,
            payload.requested_verifier_email, payload.relationship_description,
            payload.verification_scope, payload.message,
            hashlib.sha256(raw_token.encode("utf-8")).hexdigest(), expires_at
        ))
        row = rows_to_dicts(cur)[0]
        conn.commit()
    row.pop("token_hash", None)
    return {
        "status": "pending",
        "verification_request": row,
        "verification_token": raw_token,
        "verification_url": f"/rescue-net/pages/verification-approval.html?token={raw_token}"
    }


@app.get("/verification-requests")
def list_trusted_verification_requests(status: Optional[str] = None, target_type: Optional[str] = None):
    ensure_trusted_verifier_tables()
    where = ["1=1"]
    params = []
    if status:
        where.append("status = %s")
        params.append(status)
    if target_type:
        where.append("target_type = %s")
        params.append(target_type)
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT id, requester_type, requester_id, target_type, target_id, requested_verifier_id, requested_verifier_name, requested_verifier_phone, requested_verifier_email, relationship_description, verification_scope, message, status, expires_at, decided_at, correction_note, created_at, updated_at FROM trusted_verification_requests WHERE " + " AND ".join(where) + " ORDER BY created_at DESC LIMIT 300;", params)
        return rows_to_dicts(cur)


@app.post("/public/verification-requests/respond")
def respond_trusted_verification_request(token: str, payload: VerificationRequestDecision):
    ensure_trusted_verifier_tables()
    allowed = {"approved", "needs_correction", "rejected", "not_known"}
    if payload.decision not in allowed:
        raise HTTPException(status_code=400, detail="Invalid decision")
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
        SELECT * FROM trusted_verification_requests
        WHERE token_hash = %s AND status = 'pending' AND expires_at > NOW()
        LIMIT 1;
        """, (token_hash,))
        rows = rows_to_dicts(cur)
        if not rows:
            raise HTTPException(status_code=404, detail="Request not found, expired, or already decided")
        req = rows[0]
        verifier = None
        if payload.verifier_id:
            cur.execute("SELECT * FROM verifier_profiles WHERE id = %s LIMIT 1;", (payload.verifier_id,))
            vr = rows_to_dicts(cur)
            verifier = vr[0] if vr else None
            if not verifier or verifier.get("verifier_status") in {"candidate_verifier", "suspended", "rejected"}:
                raise HTTPException(status_code=403, detail="Verifier is not approved to endorse")
            scopes = verifier.get("allowed_verification_scope_json") or []
            if isinstance(scopes, str):
                scopes = json.loads(scopes)
            if req["verification_scope"] not in scopes:
                raise HTTPException(status_code=403, detail="Verifier scope does not allow this verification")
        cur.execute("""
        UPDATE trusted_verification_requests
        SET status = %s, correction_note = %s, decided_at = NOW(), updated_at = NOW()
        WHERE id = %s;
        """, (payload.decision, payload.correction_note, req["id"]))
        endorsement = None
        if payload.decision == "approved":
            verifier_name = payload.verifier_display_name or (verifier or {}).get("display_name") or req.get("requested_verifier_name") or "Trusted verifier"
            verifier_role = payload.verifier_role or (verifier or {}).get("position_title") or (verifier or {}).get("public_role_description")
            level = int((verifier or {}).get("trust_level") or 1)
            endorsement_id = "endorse-" + uuid.uuid4().hex[:12]
            cur.execute("""
            INSERT INTO verification_endorsements (
                id, request_id, target_type, target_id, verifier_id,
                verifier_display_name, verifier_role, verification_scope,
                verification_level, statement, status, visible_on_profile
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'active',TRUE)
            RETURNING *;
            """, (
                endorsement_id, req["id"], req["target_type"], req["target_id"],
                payload.verifier_id, verifier_name, verifier_role,
                req["verification_scope"], level, payload.statement
            ))
            endorsement = rows_to_dicts(cur)[0]
            if req["verification_scope"] in {"identity", "posko_identity", "organization_membership"}:
                apply_identity_endorsement(cur, req["target_type"], req["target_id"], verifier_name)
        conn.commit()
    return {"status": payload.decision, "endorsement": endorsement}


@app.get("/verification-endorsements")
def list_verification_endorsements(target_type: Optional[str] = None, target_id: Optional[str] = None, status: Optional[str] = "active"):
    ensure_trusted_verifier_tables()
    where = ["1=1"]
    params = []
    for key, value in (("target_type", target_type), ("target_id", target_id), ("status", status)):
        if value:
            where.append(f"{key} = %s")
            params.append(value)
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM verification_endorsements WHERE " + " AND ".join(where) + " ORDER BY verified_at DESC LIMIT 300;", params)
        return rows_to_dicts(cur)


@app.post("/verification-endorsements/{endorsement_id}/revoke")
def revoke_verification_endorsement(endorsement_id: str, payload: EndorsementRevoke):
    ensure_trusted_verifier_tables()
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
        UPDATE verification_endorsements
        SET status = 'revoked', revoked_at = NOW(), revoked_by = %s,
            revoke_reason = %s, updated_at = NOW()
        WHERE id = %s AND status = 'active'
        RETURNING *;
        """, (payload.revoked_by, payload.reason, endorsement_id))
        rows = rows_to_dicts(cur)
        if not rows:
            raise HTTPException(status_code=404, detail="Active endorsement not found")
        row = rows[0]
        table = verifier_target_table(row["target_type"])
        if table:
            cur.execute("SELECT COUNT(*) FROM verification_endorsements WHERE target_type = %s AND target_id = %s AND status = 'active';", (row["target_type"], row["target_id"]))
            active_count = cur.fetchone()[0]
            cur.execute(f"""
            UPDATE {table}
            SET trusted_verifier_count = %s,
                public_verified_badge = %s,
                identity_verification_status = CASE WHEN %s = 0 THEN 'unverified' ELSE identity_verification_status END
            WHERE id = %s;
            """, (active_count, active_count > 0, active_count, row["target_id"]))
        conn.commit()
    return {"status": "revoked", "endorsement": row}

@app.get("/verification-context/{disaster_event_id}")
def get_verification_context(disaster_event_id: str):
    ensure_trusted_verifier_tables()
    context = {
        "disaster_event_id": disaster_event_id,
        "organizations": [],
        "poskos": [],
        "volunteers": [],
        "aid_offers": [],
        "resources": [],
        "work_tool_requests": [],
        "missing_person_reports": [],
        "found_person_reports": [],
        "verification_actions": [],
        "verifier_profiles": [],
        "verification_requests": [],
        "verification_endorsements": [],
        "summary": {},
        "generated_at": datetime.utcnow().isoformat()
    }

    with get_conn() as conn, conn.cursor() as cur:
        def table_exists(table_name):
            cur.execute("""
            SELECT EXISTS (
              SELECT 1 FROM information_schema.tables
              WHERE table_schema = 'public'
                AND table_name = %s
            ) AS exists;
            """, (table_name,))
            return rows_to_dicts(cur)[0]["exists"]

        def cols_for(table_name):
            cur.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = %s;
            """, (table_name,))
            return {r["column_name"] for r in rows_to_dicts(cur)}

        def read_by_disaster(key, table_name, limit=120):
            if not table_exists(table_name):
                context[key] = []
                return

            cols = cols_for(table_name)
            if "disaster_event_id" not in cols:
                context[key] = []
                return

            deleted_filter = "AND deleted_at IS NULL" if "deleted_at" in cols else ""
            order_col = "created_at" if "created_at" in cols else "id"

            cur.execute(f"""
            SELECT *
            FROM {table_name}
            WHERE disaster_event_id = %s
            {deleted_filter}
            ORDER BY {order_col} DESC
            LIMIT %s;
            """, (disaster_event_id, limit))
            context[key] = rows_to_dicts(cur)

        # organizations may not have disaster_event_id, include verified/pending org list globally
        if table_exists("organizations"):
            cols = cols_for("organizations")
            deleted_filter = "WHERE deleted_at IS NULL" if "deleted_at" in cols else ""
            order_col = "created_at" if "created_at" in cols else "id"
            cur.execute(f"""
            SELECT *
            FROM organizations
            {deleted_filter}
            ORDER BY {order_col} DESC
            LIMIT 120;
            """)
            context["organizations"] = rows_to_dicts(cur)

        read_by_disaster("poskos", "posko_nodes")
        read_by_disaster("volunteers", "volunteer_profiles")
        read_by_disaster("aid_offers", "aid_offers")
        read_by_disaster("resources", "resources")
        read_by_disaster("work_tool_requests", "work_tool_requests")
        read_by_disaster("missing_person_reports", "missing_person_reports")
        read_by_disaster("found_person_reports", "found_person_reports")
        read_by_disaster("verification_actions", "verification_actions", limit=200)
        cur.execute("SELECT * FROM verifier_profiles ORDER BY trust_level DESC, updated_at DESC LIMIT 200;")
        context["verifier_profiles"] = rows_to_dicts(cur)
        cur.execute("SELECT id, requester_type, requester_id, target_type, target_id, requested_verifier_id, requested_verifier_name, requested_verifier_phone, requested_verifier_email, relationship_description, verification_scope, message, status, expires_at, decided_at, correction_note, created_at, updated_at FROM trusted_verification_requests ORDER BY created_at DESC LIMIT 200;")
        context["verification_requests"] = rows_to_dicts(cur)
        cur.execute("SELECT * FROM verification_endorsements ORDER BY verified_at DESC LIMIT 200;")
        context["verification_endorsements"] = rows_to_dicts(cur)

        def count_pending(items):
            n = 0
            for x in items:
                status = (
                    x.get("verification_status")
                    or x.get("status")
                    or x.get("trust_level")
                    or ""
                )
                if status in ["pending", "unverified", "self_reported", "community_verified"]:
                    n += 1
            return n

        context["summary"] = {
            "organization_count": len(context["organizations"]),
            "posko_count": len(context["poskos"]),
            "volunteer_count": len(context["volunteers"]),
            "aid_offer_count": len(context["aid_offers"]),
            "resource_count": len(context["resources"]),
            "work_tool_request_count": len(context["work_tool_requests"]),
            "search_found_report_count": len(context["missing_person_reports"]) + len(context["found_person_reports"]),
            "verification_action_count": len(context["verification_actions"]),
            "pending_organization_count": count_pending(context["organizations"]),
            "pending_posko_count": count_pending(context["poskos"]),
            "pending_volunteer_count": count_pending(context["volunteers"]),
            "pending_aid_offer_count": count_pending(context["aid_offers"]),
            "pending_work_tool_count": count_pending(context["work_tool_requests"]),
            "verifier_profile_count": len(context["verifier_profiles"]),
            "candidate_verifier_count": len([x for x in context["verifier_profiles"] if x.get("verifier_status") == "candidate_verifier"]),
            "pending_verifier_request_count": len([x for x in context["verification_requests"] if x.get("status") == "pending"]),
            "active_endorsement_count": len([x for x in context["verification_endorsements"] if x.get("status") == "active"]),
            "revoked_endorsement_count": len([x for x in context["verification_endorsements"] if x.get("status") == "revoked"]),
        }

    return context

@app.post("/verification-actions")
def create_verification_action(payload: VerificationActionCreate):
    action_id = "verify-" + uuid.uuid4().hex[:12]

    allowed_object_tables = {
        "organization": "organizations",
        "posko": "posko_nodes",
        "volunteer": "volunteer_profiles",
        "aid_offer": "aid_offers",
        "resource": "resources",
        "work_tool_request": "work_tool_requests",
        "missing_person_report": "missing_person_reports",
        "found_person_report": "found_person_reports",
    }

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
        INSERT INTO verification_actions
        (id, disaster_event_id, object_type, object_id,
         action_type, verification_status, trust_level,
         reviewed_by, reviewer_role, review_notes)
        VALUES
        (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        RETURNING *;
        """, (
            action_id,
            payload.disaster_event_id,
            payload.object_type,
            payload.object_id,
            payload.action_type,
            payload.verification_status,
            payload.trust_level,
            payload.reviewed_by,
            payload.reviewer_role,
            payload.review_notes,
        ))

        action = rows_to_dicts(cur)[0]

        table = allowed_object_tables.get(payload.object_type)
        if table:
            cur.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema='public'
              AND table_name=%s;
            """, (table,))
            cols = {r["column_name"] for r in rows_to_dicts(cur)}

            updates = []
            values = []

            if "verification_status" in cols:
                updates.append("verification_status = %s")
                values.append(payload.verification_status)

            if "trust_level" in cols and payload.trust_level is not None:
                updates.append("trust_level = %s")
                values.append(payload.trust_level)

            if "status" in cols and payload.verification_status in ["verified", "official_verified"]:
                # organization uses status=verified, other tables may ignore this
                updates.append("status = %s")
                values.append("verified")

            if "updated_at" in cols:
                updates.append("updated_at = NOW()")

            if updates:
                values.append(payload.object_id)
                cur.execute(f"""
                UPDATE {table}
                SET {", ".join(updates)}
                WHERE id = %s;
                """, tuple(values))

        conn.commit()
        return action

class DonorProgramCreate(BaseModel):
    disaster_event_id: str
    program_name: str
    program_type: Optional[str] = "general_relief"
    owner_type: Optional[str] = "organization"
    owner_id: Optional[str] = None
    target_description: Optional[str] = None
    target_amount: Optional[float] = 0
    target_unit: Optional[str] = "IDR"
    location: Optional[str] = None
    contact_person: Optional[str] = None
    contact_phone: Optional[str] = None
    notes: Optional[str] = None
    created_by_user_id: Optional[str] = "donor-program-operator"


class DonorProgramUpdateCreate(BaseModel):
    program_id: str
    disaster_event_id: str
    update_type: Optional[str] = "progress"
    progress_percent: Optional[float] = 0
    amount_spent: Optional[float] = 0
    update_title: str
    update_notes: Optional[str] = None
    evidence_file_id: Optional[str] = None
    officer_in_charge_name: Optional[str] = None
    officer_in_charge_phone: Optional[str] = None
    public_visibility: Optional[str] = "summary_public"
    created_by_user_id: Optional[str] = "program-operator"


@app.get("/donor-program-context/{disaster_event_id}")
def get_donor_program_context(disaster_event_id: str):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
        SELECT *
        FROM donor_programs
        WHERE disaster_event_id = %s
          AND deleted_at IS NULL
        ORDER BY created_at DESC;
        """, (disaster_event_id,))
        programs = rows_to_dicts(cur)

        cur.execute("""
        SELECT *
        FROM donor_program_updates
        WHERE disaster_event_id = %s
          AND deleted_at IS NULL
        ORDER BY created_at DESC;
        """, (disaster_event_id,))
        updates = rows_to_dicts(cur)

        updates_by_program = {}
        for u in updates:
            updates_by_program.setdefault(u.get("program_id"), []).append(u)

        enriched = []
        for p in programs:
            p = dict(p)
            p["updates"] = updates_by_program.get(p.get("id"), [])
            p["update_count"] = len(p["updates"])
            p["spent_amount"] = sum(float(u.get("amount_used") or 0) for u in p["updates"])
            enriched.append(p)

        return {
            "disaster_event_id": disaster_event_id,
            "programs": enriched,
            "updates": updates,
            "summary": {
                "program_count": len(programs),
                "active_count": len([p for p in programs if p.get("status") == "active"]),
                "update_count": len(updates),
                "target_total": sum(float(p.get("target_amount") or 0) for p in programs),
                "current_total": sum(float(p.get("current_amount") or 0) for p in programs),
                "spent_total": sum(float(u.get("amount_used") or 0) for u in updates),
            },
            "generated_at": datetime.utcnow().isoformat()
        }

@app.post("/donor-programs")
def create_donor_program(payload: DonorProgramCreate):
    program_id = "donorprog-" + uuid.uuid4().hex[:12]

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
        INSERT INTO donor_programs
        (id, disaster_event_id, program_name, program_type,
         owner_type, owner_id, target_description,
         target_amount, target_unit, current_amount,
         status, location, contact_person, contact_phone,
         notes, created_by_user_id)
        VALUES
        (%s,%s,%s,%s,%s,%s,%s,%s,%s,0,'active',%s,%s,%s,%s,%s)
        RETURNING *;
        """, (
            program_id,
            payload.disaster_event_id,
            payload.program_name,
            payload.program_type,
            payload.owner_type,
            payload.owner_id,
            payload.target_description,
            payload.target_amount,
            payload.target_unit,
            payload.location,
            payload.contact_person,
            payload.contact_phone,
            payload.notes,
            payload.created_by_user_id,
        ))

        row = rows_to_dicts(cur)[0]
        conn.commit()
        return row


@app.post("/donor-program-updates")
def create_donor_program_update(payload: DonorProgramUpdateCreate):
    update_id = "programupd-" + uuid.uuid4().hex[:12]

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
        SELECT id
        FROM donor_programs
        WHERE id = %s
          AND deleted_at IS NULL;
        """, (payload.program_id,))
        rows = rows_to_dicts(cur)

        if not rows:
            raise HTTPException(status_code=404, detail="Program not found")

        cur.execute("""
        INSERT INTO donor_program_updates
        (id, program_id, disaster_event_id,
         update_type, progress_percent, amount_spent,
         update_title, update_notes, evidence_file_id,
         officer_in_charge_name, officer_in_charge_phone,
         public_visibility, created_by_user_id)
        VALUES
        (%s,%s,%s,
         %s,%s,%s,
         %s,%s,%s,
         %s,%s,
         %s,%s)
        RETURNING *;
        """, (
            update_id, payload.program_id, payload.disaster_event_id,
            payload.update_type, payload.progress_percent, payload.amount_spent,
            payload.update_title, payload.update_notes, payload.evidence_file_id,
            payload.officer_in_charge_name, payload.officer_in_charge_phone,
            payload.public_visibility, payload.created_by_user_id
        ))

        update_row = rows_to_dicts(cur)[0]

        # Compatible with current donor_programs schema:
        # current_amount = total dana/progress berjalan.
        cur.execute("""
        UPDATE donor_programs
        SET current_amount = COALESCE(current_amount, 0) + %s,
            updated_at = NOW()
        WHERE id = %s;
        """, (
            payload.amount_spent or 0,
            payload.program_id
        ))

        conn.commit()
        return update_row



@app.get("/map-context/{disaster_event_id}")
def get_map_context(disaster_event_id: str):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
        SELECT *
        FROM map_points
        WHERE disaster_event_id = %s
          AND deleted_at IS NULL
        ORDER BY priority DESC, created_at DESC;
        """, (disaster_event_id,))
        custom_points = rows_to_dicts(cur)

        # Pull posko nodes as map candidates even if they do not have lat/lng yet.
        cur.execute("""
        SELECT
          id,
          disaster_event_id,
          node_type AS object_type,
          id AS object_id,
          name AS label,
          location AS location_text,
          operational_status AS point_status,
          verification_status,
          officer_in_charge_name,
          officer_in_charge_phone,
          created_at
        FROM posko_nodes
        WHERE disaster_event_id = %s
          AND deleted_at IS NULL
        ORDER BY created_at DESC;
        """, (disaster_event_id,))
        posko_points = rows_to_dicts(cur)

        # Work tools can represent blocked road / heavy equipment need location.
        cur.execute("""
        SELECT
          id,
          disaster_event_id,
          'work_tool_request' AS object_type,
          id AS object_id,
          tool_name AS label,
          needed_for AS description,
          location AS location_text,
          status AS point_status,
          priority,
          created_at
        FROM work_tool_requests
        WHERE disaster_event_id = %s
          AND deleted_at IS NULL
        ORDER BY created_at DESC;
        """, (disaster_event_id,))
        work_tool_points = rows_to_dicts(cur)

        # Missing/found reports as location candidates.
        cur.execute("""
        SELECT
          id,
          disaster_event_id,
          'missing_person_report' AS object_type,
          id AS object_id,
          COALESCE(person_name, person_code) AS label,
          description,
          last_seen_location AS location_text,
          status AS point_status,
          'urgent' AS priority,
          created_at
        FROM missing_person_reports
        WHERE disaster_event_id = %s
          AND deleted_at IS NULL
        ORDER BY created_at DESC;
        """, (disaster_event_id,))
        missing_points = rows_to_dicts(cur)

        cur.execute("""
        SELECT
          id,
          disaster_event_id,
          'found_person_report' AS object_type,
          id AS object_id,
          COALESCE(person_name, person_code) AS label,
          description,
          found_location AS location_text,
          status AS point_status,
          'urgent' AS priority,
          created_at
        FROM found_person_reports
        WHERE disaster_event_id = %s
          AND deleted_at IS NULL
        ORDER BY created_at DESC;
        """, (disaster_event_id,))
        found_points = rows_to_dicts(cur)

        points = []
        points.extend(custom_points)
        points.extend(posko_points)
        points.extend(work_tool_points)
        points.extend(missing_points)
        points.extend(found_points)

        return {
            "disaster_event_id": disaster_event_id,
            "points": points,
            "custom_points": custom_points,
            "posko_points": posko_points,
            "work_tool_points": work_tool_points,
            "missing_points": missing_points,
            "found_points": found_points,
            "summary": {
                "point_count": len(points),
                "custom_count": len(custom_points),
                "posko_count": len(posko_points),
                "work_tool_count": len(work_tool_points),
                "missing_count": len(missing_points),
                "found_count": len(found_points),
                "with_coordinates_count": len([p for p in points if p.get("latitude") is not None and p.get("longitude") is not None]),
            },
            "generated_at": datetime.utcnow().isoformat()
        }


class MapPointCreate(BaseModel):
    disaster_event_id: str
    point_type: Optional[str] = "posko"
    title: str
    description: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    location_text: Optional[str] = None
    related_object_type: Optional[str] = None
    related_object_id: Optional[str] = None
    status: Optional[str] = "active"
    priority: Optional[str] = "normal"
    visibility_scope: Optional[str] = "disaster_ecosystem"
    access_policy: Optional[str] = "request_required"
    created_by_user_id: Optional[str] = "map-operator"

@app.post("/map-points")
def create_map_point(payload: MapPointCreate):
    point_id = "map-" + uuid.uuid4().hex[:12]

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
        INSERT INTO map_points
        (id, disaster_event_id, object_type, object_id, label, description,
         latitude, longitude, location_text, point_status, priority, created_by_user_id)
        VALUES
        (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        RETURNING *;
        """, (
            point_id,
            payload.disaster_event_id,
            payload.object_type,
            payload.object_id,
            payload.label,
            payload.description,
            payload.latitude,
            payload.longitude,
            payload.location_text,
            payload.point_status,
            payload.priority,
            payload.created_by_user_id,
        ))

        row = rows_to_dicts(cur)[0]
        conn.commit()
        return row


class SpecialProgramCreate(BaseModel):
    disaster_event_id: str
    owner_type: Optional[str] = "organization"
    owner_id: Optional[str] = None
    program_name: str
    program_type: Optional[str] = "special_program"
    target_location: Optional[str] = None
    target_node_id: Optional[str] = None
    target_beneficiaries: Optional[str] = None
    budget_target: Optional[float] = 0
    budget_received: Optional[float] = 0
    budget_spent: Optional[float] = 0
    status: Optional[str] = "planned"
    priority: Optional[str] = "normal"
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    description: Optional[str] = None
    public_visibility: Optional[str] = "summary_public"
    officer_in_charge_name: Optional[str] = None
    officer_in_charge_phone: Optional[str] = None
    evidence_file_id: Optional[str] = None
    created_by_user_id: Optional[str] = "program-operator"


class SpecialProgramUpdateCreate(BaseModel):
    program_id: str
    disaster_event_id: str
    update_type: Optional[str] = "progress"
    progress_percent: Optional[float] = 0
    amount_spent: Optional[float] = 0
    update_title: str
    update_notes: Optional[str] = None
    evidence_file_id: Optional[str] = None
    officer_in_charge_name: Optional[str] = None
    officer_in_charge_phone: Optional[str] = None
    public_visibility: Optional[str] = "summary_public"
    created_by_user_id: Optional[str] = "program-operator"


@app.get("/donor-programs")
def list_donor_programs(disaster_event_id: Optional[str] = None):
    with get_conn() as conn, conn.cursor() as cur:
        if disaster_event_id:
            cur.execute("""
            SELECT *
            FROM donor_programs
            WHERE disaster_event_id = %s
              AND deleted_at IS NULL
            ORDER BY created_at DESC;
            """, (disaster_event_id,))
        else:
            cur.execute("""
            SELECT *
            FROM donor_programs
            WHERE deleted_at IS NULL
            ORDER BY created_at DESC
            LIMIT 200;
            """)
        return rows_to_dicts(cur)


@app.post("/special-programs")
def create_special_program(payload: SpecialProgramCreate):
    program_id = "program-" + uuid.uuid4().hex[:12]

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
        INSERT INTO donor_programs
        (id, disaster_event_id, owner_type, owner_id,
         program_name, program_type, target_location, target_node_id,
         target_beneficiaries, budget_target, budget_received, budget_spent,
         status, priority, start_date, end_date, description,
         public_visibility, officer_in_charge_name, officer_in_charge_phone,
         evidence_file_id, created_by_user_id)
        VALUES
        (%s,%s,%s,%s,
         %s,%s,%s,%s,
         %s,%s,%s,%s,
         %s,%s,%s,%s,%s,
         %s,%s,%s,
         %s,%s)
        RETURNING *;
        """, (
            program_id, payload.disaster_event_id, payload.owner_type, payload.owner_id,
            payload.program_name, payload.program_type, payload.target_location, payload.target_node_id,
            payload.target_beneficiaries, payload.budget_target, payload.budget_received, payload.budget_spent,
            payload.status, payload.priority, payload.start_date, payload.end_date, payload.description,
            payload.public_visibility, payload.officer_in_charge_name, payload.officer_in_charge_phone,
            payload.evidence_file_id, payload.created_by_user_id
        ))

        row = rows_to_dicts(cur)[0]
        conn.commit()
        return row


@app.get("/donor-programs/{program_id}")
def get_donor_program(program_id: str):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
        SELECT *
        FROM donor_programs
        WHERE id = %s
          AND deleted_at IS NULL;
        """, (program_id,))
        rows = rows_to_dicts(cur)

        if not rows:
            raise HTTPException(status_code=404, detail="Program not found")

        program = rows[0]

        cur.execute("""
        SELECT *
        FROM donor_program_updates
        WHERE program_id = %s
          AND deleted_at IS NULL
        ORDER BY created_at DESC;
        """, (program_id,))

        updates = rows_to_dicts(cur)

        return {
            "program": program,
            "updates": updates
        }


@app.post("/special-program-updates")
def create_special_program_update(payload: SpecialProgramUpdateCreate):
    update_id = "programupd-" + uuid.uuid4().hex[:12]

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
        INSERT INTO donor_program_updates
        (id, program_id, disaster_event_id,
         update_type, progress_percent, amount_spent,
         update_title, update_notes, evidence_file_id,
         officer_in_charge_name, officer_in_charge_phone,
         public_visibility, created_by_user_id)
        VALUES
        (%s,%s,%s,
         %s,%s,%s,
         %s,%s,%s,
         %s,%s,
         %s,%s)
        RETURNING *;
        """, (
            update_id, payload.program_id, payload.disaster_event_id,
            payload.update_type, payload.progress_percent, payload.amount_spent,
            payload.update_title, payload.update_notes, payload.evidence_file_id,
            payload.officer_in_charge_name, payload.officer_in_charge_phone,
            payload.public_visibility, payload.created_by_user_id
        ))

        update_row = rows_to_dicts(cur)[0]

        cur.execute("""
        UPDATE donor_programs
        SET budget_spent = COALESCE(budget_spent, 0) + %s,
            updated_at = NOW(),
            updated_by_user_id = %s
        WHERE id = %s;
        """, (
            payload.amount_spent or 0,
            payload.created_by_user_id,
            payload.program_id
        ))

        conn.commit()
        return update_row


# ============================================================
# RESOURCE PROFILE + RECOVERY ENDPOINTS ONLY
# Do not patch /ai/context here.
# ============================================================

def rn_rows_to_dicts(cur):
    cols = [d.name for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def rn_dict_row(cur):
    row = cur.fetchone()
    if not row:
        return None
    cols = [d.name for d in cur.description]
    return dict(zip(cols, row))


def ensure_resource_recovery_tables():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
            CREATE TABLE IF NOT EXISTS resource_profiles (
                id TEXT PRIMARY KEY,
                disaster_event_id TEXT NOT NULL,
                owner_type TEXT NOT NULL,
                owner_id TEXT NOT NULL,
                resource_name TEXT NOT NULL,
                resource_type TEXT NOT NULL,
                category TEXT,
                quantity NUMERIC DEFAULT 1,
                unit TEXT DEFAULT 'unit',
                capacity_description TEXT,
                availability_status TEXT DEFAULT 'available',
                current_location TEXT,
                coverage_area TEXT,
                pic_name TEXT,
                pic_phone TEXT,
                verification_status TEXT DEFAULT 'self_reported',
                notes TEXT,
                created_by_user_id TEXT,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW(),
                deleted_at TIMESTAMP NULL,
                sync_status TEXT DEFAULT 'synced',
                version INTEGER DEFAULT 1
            );
            """)

            cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_resource_profiles_disaster
            ON resource_profiles(disaster_event_id);
            """)

            cur.execute("""
            CREATE TABLE IF NOT EXISTS recovery_projects (
                id TEXT PRIMARY KEY,
                disaster_event_id TEXT NOT NULL,
                project_name TEXT NOT NULL,
                project_type TEXT DEFAULT 'recovery_reconstruction',
                owner_type TEXT DEFAULT 'organization',
                owner_id TEXT,
                target_description TEXT,
                location TEXT,
                priority TEXT DEFAULT 'normal',
                target_amount NUMERIC DEFAULT 0,
                current_amount NUMERIC DEFAULT 0,
                progress_percent NUMERIC DEFAULT 0,
                status TEXT DEFAULT 'planned',
                start_date TEXT,
                target_finish_date TEXT,
                pic_name TEXT,
                pic_phone TEXT,
                notes TEXT,
                created_by_user_id TEXT,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW(),
                deleted_at TIMESTAMP NULL,
                sync_status TEXT DEFAULT 'synced',
                version INTEGER DEFAULT 1
            );
            """)

            cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_recovery_projects_disaster
            ON recovery_projects(disaster_event_id);
            """)

            cur.execute("""
            CREATE TABLE IF NOT EXISTS recovery_project_updates (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                disaster_event_id TEXT NOT NULL,
                update_type TEXT DEFAULT 'progress',
                progress_percent NUMERIC DEFAULT 0,
                amount_spent NUMERIC DEFAULT 0,
                update_title TEXT NOT NULL,
                update_notes TEXT,
                evidence_file_id TEXT,
                verification_status TEXT DEFAULT 'self_reported',
                created_by_user_id TEXT,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW(),
                deleted_at TIMESTAMP NULL,
                sync_status TEXT DEFAULT 'synced',
                version INTEGER DEFAULT 1
            );
            """)

            conn.commit()


class ResourceProfileCreate(BaseModel):
    disaster_event_id: str
    owner_type: str = "organization"
    owner_id: str
    resource_name: str
    resource_type: str
    category: Optional[str] = None
    quantity: Optional[float] = 1
    unit: Optional[str] = "unit"
    capacity_description: Optional[str] = None
    availability_status: Optional[str] = "available"
    current_location: Optional[str] = None
    coverage_area: Optional[str] = None
    pic_name: Optional[str] = None
    pic_phone: Optional[str] = None
    verification_status: Optional[str] = "self_reported"
    notes: Optional[str] = None
    created_by_user_id: Optional[str] = "resource-profile-operator"


class ResourceProfilePatch(BaseModel):
    resource_name: Optional[str] = None
    resource_type: Optional[str] = None
    category: Optional[str] = None
    quantity: Optional[float] = None
    unit: Optional[str] = None
    capacity_description: Optional[str] = None
    availability_status: Optional[str] = None
    current_location: Optional[str] = None
    coverage_area: Optional[str] = None
    pic_name: Optional[str] = None
    pic_phone: Optional[str] = None
    verification_status: Optional[str] = None
    notes: Optional[str] = None


class RecoveryProjectCreate(BaseModel):
    disaster_event_id: str
    project_name: str
    project_type: Optional[str] = "recovery_reconstruction"
    owner_type: Optional[str] = "organization"
    owner_id: Optional[str] = None
    target_description: Optional[str] = None
    location: Optional[str] = None
    priority: Optional[str] = "normal"
    target_amount: Optional[float] = 0
    current_amount: Optional[float] = 0
    progress_percent: Optional[float] = 0
    status: Optional[str] = "planned"
    start_date: Optional[str] = None
    target_finish_date: Optional[str] = None
    pic_name: Optional[str] = None
    pic_phone: Optional[str] = None
    notes: Optional[str] = None
    created_by_user_id: Optional[str] = "recovery-operator"


class RecoveryProjectPatch(BaseModel):
    project_name: Optional[str] = None
    project_type: Optional[str] = None
    owner_type: Optional[str] = None
    owner_id: Optional[str] = None
    target_description: Optional[str] = None
    location: Optional[str] = None
    priority: Optional[str] = None
    target_amount: Optional[float] = None
    current_amount: Optional[float] = None
    progress_percent: Optional[float] = None
    status: Optional[str] = None
    start_date: Optional[str] = None
    target_finish_date: Optional[str] = None
    pic_name: Optional[str] = None
    pic_phone: Optional[str] = None
    notes: Optional[str] = None


class RecoveryProjectUpdateCreate(BaseModel):
    project_id: str
    disaster_event_id: str
    update_type: Optional[str] = "progress"
    progress_percent: Optional[float] = 0
    amount_spent: Optional[float] = 0
    update_title: str
    update_notes: Optional[str] = None
    evidence_file_id: Optional[str] = None
    verification_status: Optional[str] = "self_reported"
    created_by_user_id: Optional[str] = "recovery-operator"


class CommunityReportCreate(BaseModel):
    disaster_event_id: str = "event-sim-001"
    reporter_name: str
    reporter_phone: Optional[str] = None
    reporter_role: str = "warga_terdampak"
    reporter_verification_level: str = "anonymous"
    report_type: str
    title: str
    description: str
    location_text: str
    lat: Optional[float] = None
    lng: Optional[float] = None
    location_accuracy_meters: Optional[float] = None
    location_input_method: Optional[str] = "no_location"
    location_source: Optional[str] = None
    location_status: Optional[str] = None
    admin_area_id: Optional[str] = None
    admin_level: Optional[str] = None
    area_level: Optional[str] = None
    province_name: Optional[str] = None
    city_name: Optional[str] = None
    district_name: Optional[str] = None
    village_name: Optional[str] = None
    is_aggregate: Optional[bool] = False
    consolidation_status: Optional[str] = None
    affected_people_count: Optional[int] = 0
    priority: str = "normal"
    urgent_needs: Optional[str] = None
    evidence_url: Optional[str] = None
    evidence_caption: Optional[str] = None
    consent_to_contact: bool = True


class CommunityReportStatusUpdate(BaseModel):
    status: str
    verifier_id: Optional[str] = None
    verifier_role: Optional[str] = None
    notes: Optional[str] = None
    assigned_verifier_type: Optional[str] = None
    assigned_verifier_id: Optional[str] = None


class CommunityReportConvert(BaseModel):
    target_type: str
    item_name: Optional[str] = None
    quantity_needed: Optional[float] = 1
    unit: Optional[str] = "paket"
    node_id: Optional[str] = None
    notes: Optional[str] = None


class GeoLocationCreate(BaseModel):
    country_code: Optional[str] = "ID"
    province_code: Optional[str] = None
    province_name: Optional[str] = None
    city_code: Optional[str] = None
    city_name: Optional[str] = None
    district_code: Optional[str] = None
    district_name: Optional[str] = None
    village_code: Optional[str] = None
    village_name: Optional[str] = None
    location_name: str
    lat: Optional[float] = None
    lng: Optional[float] = None
    accuracy_meters: Optional[float] = None
    admin_level: str = "point"
    source: Optional[str] = "manual"


class OperationalAreaCreate(BaseModel):
    disaster_event_id: str = "event-sim-001"
    owner_type: str
    owner_id: str
    area_level: str = "point"
    country_code: Optional[str] = "ID"
    province_code: Optional[str] = None
    city_code: Optional[str] = None
    district_code: Optional[str] = None
    village_code: Optional[str] = None
    center_lat: Optional[float] = None
    center_lng: Optional[float] = None
    radius_meters: Optional[float] = None
    boundary_geojson: Optional[dict] = None
    coverage_description: Optional[str] = None
    verification_status: Optional[str] = "self_reported"


class BeneficiaryGroupCreate(BaseModel):
    disaster_event_id: str = "event-sim-001"
    geo_location_id: Optional[str] = None
    group_name: str
    group_type: Optional[str] = "community"
    estimated_people_count: Optional[int] = 0
    household_count: Optional[int] = 0
    description: Optional[str] = None
    verified_status: Optional[str] = "self_reported"


class DuplicateCheckRequest(BaseModel):
    disaster_event_id: str = "event-sim-001"
    object_type: str = "need"


class DuplicateResolveRequest(BaseModel):
    status: str
    reviewed_by: Optional[str] = "operator-web"
    review_notes: Optional[str] = None


class CommunityReportConsolidationUpdate(BaseModel):
    consolidation_status: str
    location_status: Optional[str] = None
    is_aggregate: Optional[bool] = None
    reviewer_id: Optional[str] = "operator-web"
    notes: Optional[str] = None


class ConsolidatedNeedCreate(BaseModel):
    disaster_event_id: str = "event-sim-001"
    canonical_area_id: Optional[str] = None
    canonical_posko_id: Optional[str] = None
    need_type: str = "logistic"
    item_name: str
    quantity_final: float
    quantity_unit: str = "paket"
    quantity_min: Optional[float] = None
    quantity_max: Optional[float] = None
    confidence_level: Optional[str] = "medium"
    source_ids: Optional[list[str]] = None
    merge_method: Optional[str] = "manual_review"
    status: Optional[str] = "draft"


class CommandCorrectionCreate(BaseModel):
    disaster_event_id: str = "event-sim-001"
    target_type: str = "consolidated_need"
    target_id: str
    corrected_quantity: float
    corrected_by: Optional[str] = "command-center"
    correction_reason: Optional[str] = None
    correction_note: Optional[str] = None


class FederationNodeCreate(BaseModel):
    node_name: str
    node_type: str = "partner"
    base_url: Optional[str] = None
    organization_id: Optional[str] = None
    trust_level: Optional[str] = "unverified"
    sync_scope: Optional[str] = "event"
    disaster_event_id: Optional[str] = "event-sim-001"
    status: Optional[str] = "active"
    notes: Optional[str] = None


class FederationRepositoryCreate(BaseModel):
    node_id: str
    repository_name: str
    repository_type: str = "sync_events"
    endpoint_path: Optional[str] = "/sync/pull"
    direction: Optional[str] = "bidirectional"
    conflict_policy: Optional[str] = "manual_review"
    status: Optional[str] = "active"
    notes: Optional[str] = None


class FederationSyncLogCreate(BaseModel):
    node_id: Optional[str] = None
    repository_id: Optional[str] = None
    direction: str = "export"
    status: str = "created"
    manifest_json: Optional[dict] = None
    notes: Optional[str] = None


@app.post("/resource-profiles")
def create_resource_profile(payload: ResourceProfileCreate):
    ensure_resource_recovery_tables()
    item_id = "resprof-" + uuid.uuid4().hex[:12]

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
            INSERT INTO resource_profiles (
                id, disaster_event_id, owner_type, owner_id, resource_name, resource_type,
                category, quantity, unit, capacity_description, availability_status,
                current_location, coverage_area, pic_name, pic_phone, verification_status,
                notes, created_by_user_id
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING *;
            """, (
                item_id, payload.disaster_event_id, payload.owner_type, payload.owner_id,
                payload.resource_name, payload.resource_type, payload.category,
                payload.quantity, payload.unit, payload.capacity_description,
                payload.availability_status, payload.current_location, payload.coverage_area,
                payload.pic_name, payload.pic_phone, payload.verification_status,
                payload.notes, payload.created_by_user_id
            ))
            row = rn_dict_row(cur)
            conn.commit()

    return {"status": "created", "resource_profile": row}


@app.get("/resource-profiles")
def list_resource_profiles(disaster_event_id: Optional[str] = None, owner_id: Optional[str] = None):
    ensure_resource_recovery_tables()

    where = ["deleted_at IS NULL"]
    params = []

    if disaster_event_id:
        where.append("disaster_event_id = %s")
        params.append(disaster_event_id)

    if owner_id:
        where.append("owner_id = %s")
        params.append(owner_id)

    sql = "SELECT * FROM resource_profiles WHERE " + " AND ".join(where) + " ORDER BY updated_at DESC, created_at DESC"

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = rn_rows_to_dicts(cur)

    return rows


@app.patch("/resource-profiles/{resource_id}")
def patch_resource_profile(resource_id: str, payload: ResourceProfilePatch):
    ensure_resource_recovery_tables()
    data = payload.model_dump(exclude_unset=True)

    if not data:
        raise HTTPException(status_code=400, detail="No fields to update")

    sets = []
    params = []

    for k, v in data.items():
        sets.append(f"{k} = %s")
        params.append(v)

    sets.append("updated_at = NOW()")
    sets.append("version = version + 1")
    params.append(resource_id)

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(f"""
            UPDATE resource_profiles
            SET {", ".join(sets)}
            WHERE id = %s AND deleted_at IS NULL
            RETURNING *;
            """, params)
            row = rn_dict_row(cur)
            conn.commit()

    if not row:
        raise HTTPException(status_code=404, detail="Resource profile not found")

    return {"status": "updated", "resource_profile": row}


@app.delete("/resource-profiles/{resource_id}")
def delete_resource_profile(resource_id: str):
    ensure_resource_recovery_tables()

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
            UPDATE resource_profiles
            SET deleted_at = NOW(), updated_at = NOW(), version = version + 1
            WHERE id = %s AND deleted_at IS NULL
            RETURNING id;
            """, (resource_id,))
            row = cur.fetchone()
            conn.commit()

    if not row:
        raise HTTPException(status_code=404, detail="Resource profile not found")

    return {"status": "deleted", "id": resource_id}


@app.post("/recovery-projects")
def create_recovery_project(payload: RecoveryProjectCreate):
    ensure_resource_recovery_tables()
    project_id = "recovery-" + uuid.uuid4().hex[:12]

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
            INSERT INTO recovery_projects (
                id, disaster_event_id, project_name, project_type, owner_type, owner_id,
                target_description, location, priority, target_amount, current_amount,
                progress_percent, status, start_date, target_finish_date, pic_name, pic_phone,
                notes, created_by_user_id
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING *;
            """, (
                project_id, payload.disaster_event_id, payload.project_name, payload.project_type,
                payload.owner_type, payload.owner_id, payload.target_description,
                payload.location, payload.priority, payload.target_amount, payload.current_amount,
                payload.progress_percent, payload.status, payload.start_date,
                payload.target_finish_date, payload.pic_name, payload.pic_phone,
                payload.notes, payload.created_by_user_id
            ))
            row = rn_dict_row(cur)
            conn.commit()

    return {"status": "created", "recovery_project": row}


@app.get("/recovery-projects")
def list_recovery_projects(disaster_event_id: Optional[str] = None, status: Optional[str] = None):
    ensure_resource_recovery_tables()

    where = ["deleted_at IS NULL"]
    params = []

    if disaster_event_id:
        where.append("disaster_event_id = %s")
        params.append(disaster_event_id)

    if status:
        where.append("status = %s")
        params.append(status)

    sql = "SELECT * FROM recovery_projects WHERE " + " AND ".join(where) + " ORDER BY updated_at DESC, created_at DESC"

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = rn_rows_to_dicts(cur)

    return rows


@app.patch("/recovery-projects/{project_id}")
def patch_recovery_project(project_id: str, payload: RecoveryProjectPatch):
    ensure_resource_recovery_tables()
    data = payload.model_dump(exclude_unset=True)

    if not data:
        raise HTTPException(status_code=400, detail="No fields to update")

    sets = []
    params = []

    for k, v in data.items():
        sets.append(f"{k} = %s")
        params.append(v)

    sets.append("updated_at = NOW()")
    sets.append("version = version + 1")
    params.append(project_id)

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(f"""
            UPDATE recovery_projects
            SET {", ".join(sets)}
            WHERE id = %s AND deleted_at IS NULL
            RETURNING *;
            """, params)
            row = rn_dict_row(cur)
            conn.commit()

    if not row:
        raise HTTPException(status_code=404, detail="Recovery project not found")

    return {"status": "updated", "recovery_project": row}


@app.delete("/recovery-projects/{project_id}")
def delete_recovery_project(project_id: str):
    ensure_resource_recovery_tables()

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
            UPDATE recovery_projects
            SET deleted_at = NOW(), updated_at = NOW(), version = version + 1
            WHERE id = %s AND deleted_at IS NULL
            RETURNING id;
            """, (project_id,))
            row = cur.fetchone()
            conn.commit()

    if not row:
        raise HTTPException(status_code=404, detail="Recovery project not found")

    return {"status": "deleted", "id": project_id}


@app.post("/recovery-project-updates")
def create_recovery_project_update(payload: RecoveryProjectUpdateCreate):
    ensure_resource_recovery_tables()
    update_id = "recoveryupd-" + uuid.uuid4().hex[:12]

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
            INSERT INTO recovery_project_updates (
                id, project_id, disaster_event_id, update_type, progress_percent,
                amount_spent, update_title, update_notes, evidence_file_id,
                verification_status, created_by_user_id
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING *;
            """, (
                update_id, payload.project_id, payload.disaster_event_id,
                payload.update_type, payload.progress_percent, payload.amount_spent,
                payload.update_title, payload.update_notes, payload.evidence_file_id,
                payload.verification_status, payload.created_by_user_id
            ))
            row = rn_dict_row(cur)

            cur.execute("""
            UPDATE recovery_projects
            SET progress_percent = GREATEST(progress_percent, %s),
                current_amount = COALESCE(current_amount, 0) + COALESCE(%s, 0),
                updated_at = NOW(),
                version = version + 1
            WHERE id = %s AND deleted_at IS NULL;
            """, (payload.progress_percent or 0, payload.amount_spent or 0, payload.project_id))

            conn.commit()

    return {"status": "created", "recovery_project_update": row}


@app.get("/recovery-project-updates")
def list_recovery_project_updates(project_id: Optional[str] = None, disaster_event_id: Optional[str] = None):
    ensure_resource_recovery_tables()

    where = ["deleted_at IS NULL"]
    params = []

    if project_id:
        where.append("project_id = %s")
        params.append(project_id)

    if disaster_event_id:
        where.append("disaster_event_id = %s")
        params.append(disaster_event_id)

    sql = "SELECT * FROM recovery_project_updates WHERE " + " AND ".join(where) + " ORDER BY created_at DESC"

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = rn_rows_to_dicts(cur)

    return rows


def ensure_community_report_tables():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
            CREATE TABLE IF NOT EXISTS community_reports (
                id TEXT PRIMARY KEY,
                disaster_event_id TEXT NOT NULL REFERENCES disaster_events(id) ON DELETE CASCADE,
                reporter_name TEXT NOT NULL,
                reporter_phone TEXT,
                reporter_role TEXT NOT NULL DEFAULT 'warga_terdampak',
                reporter_verification_level TEXT NOT NULL DEFAULT 'anonymous',
                report_type TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                location_text TEXT NOT NULL,
                lat DOUBLE PRECISION,
                lng DOUBLE PRECISION,
                affected_people_count INTEGER DEFAULT 0,
                priority TEXT NOT NULL DEFAULT 'normal',
                urgent_needs TEXT,
                status TEXT NOT NULL DEFAULT 'submitted',
                trust_score INTEGER NOT NULL DEFAULT 0,
                assigned_verifier_type TEXT,
                assigned_verifier_id TEXT,
                verified_by TEXT,
                verified_at TIMESTAMP,
                converted_object_type TEXT,
                converted_object_id TEXT,
                consent_to_contact BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
                deleted_at TIMESTAMP
            );
            """)
            cur.execute("""
            CREATE TABLE IF NOT EXISTS community_report_evidence (
                id TEXT PRIMARY KEY,
                report_id TEXT NOT NULL REFERENCES community_reports(id) ON DELETE CASCADE,
                file_url TEXT NOT NULL,
                file_type TEXT DEFAULT 'url',
                caption TEXT,
                verification_status TEXT NOT NULL DEFAULT 'pending',
                uploaded_at TIMESTAMP NOT NULL DEFAULT NOW()
            );
            """)
            cur.execute("""
            CREATE TABLE IF NOT EXISTS community_report_verifications (
                id TEXT PRIMARY KEY,
                report_id TEXT NOT NULL REFERENCES community_reports(id) ON DELETE CASCADE,
                verifier_id TEXT,
                verifier_role TEXT,
                action TEXT NOT NULL,
                notes TEXT,
                before_status TEXT,
                after_status TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT NOW()
            );
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_community_reports_event_status ON community_reports(disaster_event_id, status);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_community_reports_type ON community_reports(report_type);")
            extra_columns = {
                "location_accuracy_meters": "DOUBLE PRECISION",
                "location_input_method": "TEXT",
                "location_source": "TEXT",
                "location_status": "TEXT",
                "admin_area_id": "TEXT",
                "admin_level": "TEXT",
                "area_level": "TEXT",
                "province_name": "TEXT",
                "city_name": "TEXT",
                "district_name": "TEXT",
                "village_name": "TEXT",
                "is_aggregate": "BOOLEAN NOT NULL DEFAULT FALSE",
                "consolidation_status": "TEXT"
            }
            for col, coltype in extra_columns.items():
                cur.execute(f"ALTER TABLE community_reports ADD COLUMN IF NOT EXISTS {col} {coltype};")
            conn.commit()


def calculate_community_trust(payload: CommunityReportCreate, status: str = "submitted"):
    score = 0
    if payload.reporter_phone:
        score += 10
    if payload.location_text and len(payload.location_text.strip()) >= 8:
        score += 20
    if payload.evidence_url:
        score += 20
    if payload.reporter_role in {"rt_rw", "relawan", "posko", "organisasi", "tenaga_medis", "pemerintah"}:
        score += 20
    if payload.reporter_verification_level in {"phone_verified", "community_verifiable"}:
        score += 10
    if payload.reporter_verification_level == "trusted_reporter":
        score += 20
    if status == "verified":
        score += 20
    if status == "rejected":
        score -= 50
    return max(0, min(100, score))


def derive_community_location_state(payload: CommunityReportCreate):
    method = payload.location_input_method or "no_location"
    has_coordinate = payload.lat is not None and payload.lng is not None
    area_level = payload.area_level or payload.admin_level
    is_aggregate = bool(payload.is_aggregate)

    if method == "government_area_select":
        if area_level in {"province", "city", "district"}:
            return {
                "location_status": payload.location_status or "admin_area_only",
                "consolidation_status": payload.consolidation_status or "not_ready_admin_only",
                "is_aggregate": True,
                "area_level": area_level or "admin_area"
            }
        return {
            "location_status": payload.location_status or "admin_area_only",
            "consolidation_status": payload.consolidation_status or "ready_for_review",
            "is_aggregate": is_aggregate,
            "area_level": area_level or "village"
        }

    if has_coordinate:
        if payload.location_accuracy_meters and payload.location_accuracy_meters > 500:
            return {
                "location_status": payload.location_status or "low_accuracy",
                "consolidation_status": payload.consolidation_status or "needs_location_review",
                "is_aggregate": is_aggregate,
                "area_level": area_level or "point"
            }
        if payload.village_name or payload.admin_area_id:
            return {
                "location_status": payload.location_status or "admin_area_detected",
                "consolidation_status": payload.consolidation_status or "ready_for_review",
                "is_aggregate": is_aggregate,
                "area_level": area_level or "point"
            }
        return {
            "location_status": payload.location_status or "coordinate_only",
            "consolidation_status": payload.consolidation_status or "needs_location_review",
            "is_aggregate": is_aggregate,
            "area_level": area_level or "point"
        }

    return {
        "location_status": payload.location_status or "no_coordinate",
        "consolidation_status": payload.consolidation_status or "not_ready_no_location",
        "is_aggregate": is_aggregate,
        "area_level": area_level or "unknown"
    }


def community_report_with_evidence(cur, report_id: str):
    cur.execute("SELECT * FROM community_reports WHERE id = %s AND deleted_at IS NULL;", (report_id,))
    report = rn_dict_row(cur)
    if not report:
        return None
    cur.execute("SELECT * FROM community_report_evidence WHERE report_id = %s ORDER BY uploaded_at DESC;", (report_id,))
    report["evidence"] = rn_rows_to_dicts(cur)
    return report


@app.post("/public/community-reports")
def submit_community_report(payload: CommunityReportCreate):
    ensure_community_report_tables()
    report_id = "cr-" + uuid.uuid4().hex[:12]
    trust_score = calculate_community_trust(payload)
    location_state = derive_community_location_state(payload)

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
            INSERT INTO community_reports (
                id, disaster_event_id, reporter_name, reporter_phone, reporter_role,
                reporter_verification_level, report_type, title, description,
                location_text, lat, lng, location_accuracy_meters, location_input_method,
                location_source, location_status, admin_area_id, admin_level, area_level,
                province_name, city_name, district_name, village_name, is_aggregate,
                consolidation_status, affected_people_count, priority, urgent_needs,
                status, trust_score, consent_to_contact
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                    %s,%s,%s,%s,%s,%s,%s,%s,'submitted',%s,%s)
            RETURNING *;
            """, (
                report_id, payload.disaster_event_id, payload.reporter_name,
                payload.reporter_phone, payload.reporter_role,
                payload.reporter_verification_level, payload.report_type,
                payload.title, payload.description, payload.location_text,
                payload.lat, payload.lng, payload.location_accuracy_meters,
                payload.location_input_method, payload.location_source,
                location_state["location_status"], payload.admin_area_id,
                payload.admin_level, location_state["area_level"], payload.province_name,
                payload.city_name, payload.district_name, payload.village_name,
                location_state["is_aggregate"], location_state["consolidation_status"],
                payload.affected_people_count, payload.priority, payload.urgent_needs, trust_score,
                payload.consent_to_contact
            ))
            report = rn_dict_row(cur)

            if payload.evidence_url:
                cur.execute("""
                INSERT INTO community_report_evidence
                (id, report_id, file_url, file_type, caption, verification_status)
                VALUES (%s,%s,%s,%s,%s,'pending');
                """, (
                    "crev-" + uuid.uuid4().hex[:12], report_id, payload.evidence_url,
                    "url", payload.evidence_caption
                ))

            cur.execute("""
            INSERT INTO community_report_verifications
            (id, report_id, action, notes, before_status, after_status)
            VALUES (%s,%s,'submit','Community report submitted','none','submitted');
            """, ("crlog-" + uuid.uuid4().hex[:12], report_id))
            conn.commit()

    return {"status": "submitted", "community_report": report}


@app.get("/community-reports")
def list_community_reports(disaster_event_id: Optional[str] = None, status: Optional[str] = None, report_type: Optional[str] = None):
    ensure_community_report_tables()
    where = ["deleted_at IS NULL"]
    params = []

    if disaster_event_id:
        where.append("disaster_event_id = %s")
        params.append(disaster_event_id)
    if status:
        where.append("status = %s")
        params.append(status)
    if report_type:
        where.append("report_type = %s")
        params.append(report_type)

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM community_reports WHERE " + " AND ".join(where) + " ORDER BY created_at DESC LIMIT 200;",
                params
            )
            rows = rn_rows_to_dicts(cur)

    return rows


@app.get("/community-reports/{report_id}")
def get_community_report(report_id: str):
    ensure_community_report_tables()
    with get_conn() as conn:
        with conn.cursor() as cur:
            report = community_report_with_evidence(cur, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Community report not found")
    return report


@app.patch("/community-reports/{report_id}/status")
def update_community_report_status(report_id: str, payload: CommunityReportStatusUpdate):
    ensure_community_report_tables()
    allowed = {"submitted", "triage", "needs_verification", "verified", "rejected", "duplicate", "escalated", "converted_to_action", "closed"}
    if payload.status not in allowed:
        raise HTTPException(status_code=400, detail="Invalid community report status")

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT status, trust_score FROM community_reports WHERE id = %s AND deleted_at IS NULL;", (report_id,))
            before = cur.fetchone()
            if not before:
                raise HTTPException(status_code=404, detail="Community report not found")

            before_status = before[0]
            trust_delta = 20 if payload.status == "verified" else -50 if payload.status == "rejected" else 0
            verified_by = payload.verifier_id if payload.status == "verified" else None
            verified_at_sql = "NOW()" if payload.status == "verified" else "verified_at"

            cur.execute(f"""
            UPDATE community_reports
            SET status = %s,
                trust_score = GREATEST(0, LEAST(100, trust_score + %s)),
                assigned_verifier_type = COALESCE(%s, assigned_verifier_type),
                assigned_verifier_id = COALESCE(%s, assigned_verifier_id),
                verified_by = COALESCE(%s, verified_by),
                verified_at = {verified_at_sql},
                updated_at = NOW()
            WHERE id = %s AND deleted_at IS NULL
            RETURNING *;
            """, (
                payload.status, trust_delta, payload.assigned_verifier_type,
                payload.assigned_verifier_id, verified_by, report_id
            ))
            row = rn_dict_row(cur)

            cur.execute("""
            INSERT INTO community_report_verifications
            (id, report_id, verifier_id, verifier_role, action, notes, before_status, after_status)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s);
            """, (
                "crlog-" + uuid.uuid4().hex[:12], report_id, payload.verifier_id,
                payload.verifier_role, payload.status, payload.notes,
                before_status, payload.status
            ))
            conn.commit()

    return {"status": "updated", "community_report": row}


@app.post("/community-reports/{report_id}/convert")
def convert_community_report(report_id: str, payload: CommunityReportConvert):
    ensure_community_report_tables()
    if payload.target_type != "logistic_need":
        raise HTTPException(status_code=400, detail="Only logistic_need conversion is available in this first implementation")

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM community_reports WHERE id = %s AND deleted_at IS NULL;", (report_id,))
            report = rn_dict_row(cur)
            if not report:
                raise HTTPException(status_code=404, detail="Community report not found")

            need_id = "need-cr-" + uuid.uuid4().hex[:10]
            cur.execute("""
            INSERT INTO logistic_needs
            (id, disaster_event_id, node_id, item_name, quantity_needed, unit, priority, needed_before, status)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'open')
            RETURNING *;
            """, (
                need_id, report["disaster_event_id"], payload.node_id,
                payload.item_name or report.get("urgent_needs") or report["title"],
                payload.quantity_needed or 1, payload.unit or "paket",
                report["priority"], payload.notes or "Converted from community report"
            ))
            need = rn_dict_row(cur)

            cur.execute("""
            UPDATE community_reports
            SET status = 'converted_to_action',
                converted_object_type = 'logistic_need',
                converted_object_id = %s,
                updated_at = NOW()
            WHERE id = %s
            RETURNING *;
            """, (need_id, report_id))
            updated = rn_dict_row(cur)

            cur.execute("""
            INSERT INTO community_report_verifications
            (id, report_id, action, notes, before_status, after_status)
            VALUES (%s,%s,'convert_to_logistic_need',%s,%s,'converted_to_action');
            """, (
                "crlog-" + uuid.uuid4().hex[:12], report_id,
                payload.notes, report["status"]
            ))
            conn.commit()

    return {"status": "converted", "community_report": updated, "logistic_need": need}


@app.patch("/community-reports/{report_id}/consolidation")
def update_community_report_consolidation(report_id: str, payload: CommunityReportConsolidationUpdate):
    ensure_community_report_tables()
    allowed_consolidation = {
        "not_ready_no_location", "not_ready_admin_only", "ready_for_review",
        "needs_location_review", "suspected_duplicate", "verified_unique",
        "merged_to_canonical", "excluded_aggregate"
    }
    allowed_location = {
        "no_coordinate", "coordinate_only", "admin_area_detected", "admin_area_only",
        "verified_location", "location_conflict", "low_accuracy"
    }
    if payload.consolidation_status not in allowed_consolidation:
        raise HTTPException(status_code=400, detail="Invalid consolidation status")
    if payload.location_status and payload.location_status not in allowed_location:
        raise HTTPException(status_code=400, detail="Invalid location status")

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
            SELECT consolidation_status, location_status, is_aggregate
            FROM community_reports
            WHERE id = %s AND deleted_at IS NULL;
            """, (report_id,))
            before = rn_dict_row(cur)
            if not before:
                raise HTTPException(status_code=404, detail="Community report not found")

            cur.execute("""
            UPDATE community_reports
            SET consolidation_status = %s,
                location_status = COALESCE(%s, location_status),
                is_aggregate = COALESCE(%s, is_aggregate),
                updated_at = NOW()
            WHERE id = %s
            RETURNING *;
            """, (
                payload.consolidation_status, payload.location_status,
                payload.is_aggregate, report_id
            ))
            report = rn_dict_row(cur)
            cur.execute("""
            INSERT INTO community_report_verifications
            (id, report_id, verifier_id, verifier_role, action, notes, before_status, after_status)
            VALUES (%s,%s,%s,'data_consolidation','consolidation_update',%s,%s,%s);
            """, (
                "crlog-" + uuid.uuid4().hex[:12], report_id, payload.reviewer_id,
                payload.notes or "Consolidation status updated from Data Konsolidasi",
                before.get("consolidation_status"), payload.consolidation_status
            ))
            conn.commit()

    return {"status": "updated", "community_report": report}


def ensure_location_resolution_tables():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
            CREATE TABLE IF NOT EXISTS geo_locations (
                id TEXT PRIMARY KEY,
                country_code TEXT DEFAULT 'ID',
                province_code TEXT,
                province_name TEXT,
                city_code TEXT,
                city_name TEXT,
                district_code TEXT,
                district_name TEXT,
                village_code TEXT,
                village_name TEXT,
                location_name TEXT NOT NULL,
                lat DOUBLE PRECISION,
                lng DOUBLE PRECISION,
                accuracy_meters DOUBLE PRECISION,
                admin_level TEXT NOT NULL DEFAULT 'point',
                source TEXT DEFAULT 'manual',
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW()
            );
            """)
            cur.execute("""
            CREATE TABLE IF NOT EXISTS official_admin_areas (
                code TEXT PRIMARY KEY,
                parent_code TEXT,
                name TEXT NOT NULL,
                level TEXT NOT NULL,
                source_name TEXT NOT NULL DEFAULT 'manual_seed',
                source_url TEXT,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                updated_at TIMESTAMP NOT NULL DEFAULT NOW()
            );
            """)
            cur.execute("""
            CREATE TABLE IF NOT EXISTS operational_areas (
                id TEXT PRIMARY KEY,
                disaster_event_id TEXT NOT NULL REFERENCES disaster_events(id) ON DELETE CASCADE,
                owner_type TEXT NOT NULL,
                owner_id TEXT NOT NULL,
                area_level TEXT NOT NULL DEFAULT 'point',
                country_code TEXT DEFAULT 'ID',
                province_code TEXT,
                city_code TEXT,
                district_code TEXT,
                village_code TEXT,
                center_lat DOUBLE PRECISION,
                center_lng DOUBLE PRECISION,
                radius_meters DOUBLE PRECISION,
                boundary_geojson JSONB,
                coverage_description TEXT,
                verification_status TEXT NOT NULL DEFAULT 'self_reported',
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW()
            );
            """)
            cur.execute("""
            CREATE TABLE IF NOT EXISTS beneficiary_groups (
                id TEXT PRIMARY KEY,
                disaster_event_id TEXT NOT NULL REFERENCES disaster_events(id) ON DELETE CASCADE,
                geo_location_id TEXT REFERENCES geo_locations(id) ON DELETE SET NULL,
                group_name TEXT NOT NULL,
                group_type TEXT DEFAULT 'community',
                estimated_people_count INTEGER DEFAULT 0,
                household_count INTEGER DEFAULT 0,
                description TEXT,
                verified_status TEXT NOT NULL DEFAULT 'self_reported',
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW()
            );
            """)
            cur.execute("""
            CREATE TABLE IF NOT EXISTS duplicate_candidates (
                id TEXT PRIMARY KEY,
                disaster_event_id TEXT NOT NULL REFERENCES disaster_events(id) ON DELETE CASCADE,
                object_type TEXT NOT NULL,
                object_id_a TEXT NOT NULL,
                object_id_b TEXT NOT NULL,
                match_score INTEGER NOT NULL DEFAULT 0,
                match_reason TEXT,
                location_distance_meters DOUBLE PRECISION,
                same_admin_area BOOLEAN DEFAULT FALSE,
                same_name_score INTEGER DEFAULT 0,
                same_contact_score INTEGER DEFAULT 0,
                same_owner_score INTEGER DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'candidate',
                reviewed_by TEXT,
                review_notes TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW()
            );
            """)
            cur.execute("""
            CREATE TABLE IF NOT EXISTS canonical_entities (
                id TEXT PRIMARY KEY,
                disaster_event_id TEXT NOT NULL REFERENCES disaster_events(id) ON DELETE CASCADE,
                entity_type TEXT NOT NULL,
                canonical_object_id TEXT NOT NULL,
                merged_object_ids_json JSONB NOT NULL DEFAULT '[]',
                merge_strategy TEXT NOT NULL DEFAULT 'manual_review',
                merge_notes TEXT,
                created_by TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW()
            );
            """)
            cur.execute("""
            CREATE TABLE IF NOT EXISTS consolidated_needs (
                id TEXT PRIMARY KEY,
                disaster_event_id TEXT NOT NULL REFERENCES disaster_events(id) ON DELETE CASCADE,
                canonical_area_id TEXT,
                canonical_posko_id TEXT,
                need_type TEXT NOT NULL DEFAULT 'logistic',
                item_name TEXT NOT NULL,
                quantity_final NUMERIC NOT NULL DEFAULT 0,
                quantity_unit TEXT NOT NULL DEFAULT 'paket',
                quantity_min NUMERIC,
                quantity_max NUMERIC,
                confidence_level TEXT NOT NULL DEFAULT 'medium',
                source_count INTEGER NOT NULL DEFAULT 0,
                source_ids_json JSONB NOT NULL DEFAULT '[]',
                merge_method TEXT NOT NULL DEFAULT 'manual_review',
                status TEXT NOT NULL DEFAULT 'draft',
                verified_by TEXT,
                verified_at TIMESTAMP,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW()
            );
            """)
            cur.execute("""
            CREATE TABLE IF NOT EXISTS command_corrections (
                id TEXT PRIMARY KEY,
                disaster_event_id TEXT NOT NULL REFERENCES disaster_events(id) ON DELETE CASCADE,
                target_type TEXT NOT NULL DEFAULT 'consolidated_need',
                target_id TEXT NOT NULL,
                original_quantity NUMERIC NOT NULL DEFAULT 0,
                corrected_quantity NUMERIC NOT NULL DEFAULT 0,
                correction_delta NUMERIC NOT NULL DEFAULT 0,
                corrected_by TEXT,
                correction_reason TEXT,
                correction_note TEXT,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW()
            );
            """)

            for table in ("posko_nodes", "logistic_needs"):
                cur.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS geo_location_id TEXT;")
                cur.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS operational_area_id TEXT;")
                cur.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS lat DOUBLE PRECISION;")
                cur.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS lng DOUBLE PRECISION;")
                cur.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS location_accuracy_meters DOUBLE PRECISION;")
                cur.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS admin_level TEXT;")
                cur.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS duplicate_group_id TEXT;")

            cur.execute("ALTER TABLE posko_nodes ADD COLUMN IF NOT EXISTS coverage_radius_meters DOUBLE PRECISION;")
            cur.execute("ALTER TABLE posko_nodes ADD COLUMN IF NOT EXISTS parent_posko_id TEXT;")
            cur.execute("ALTER TABLE posko_nodes ADD COLUMN IF NOT EXISTS canonical_posko_id TEXT;")
            cur.execute("ALTER TABLE posko_nodes ADD COLUMN IF NOT EXISTS device_id TEXT;")
            cur.execute("ALTER TABLE posko_nodes ADD COLUMN IF NOT EXISTS area_level TEXT;")
            cur.execute("ALTER TABLE posko_nodes ADD COLUMN IF NOT EXISTS admin_area_id TEXT;")
            cur.execute("ALTER TABLE posko_nodes ADD COLUMN IF NOT EXISTS province_name TEXT;")
            cur.execute("ALTER TABLE posko_nodes ADD COLUMN IF NOT EXISTS city_name TEXT;")
            cur.execute("ALTER TABLE posko_nodes ADD COLUMN IF NOT EXISTS district_name TEXT;")
            cur.execute("ALTER TABLE posko_nodes ADD COLUMN IF NOT EXISTS village_name TEXT;")
            cur.execute("ALTER TABLE posko_nodes ADD COLUMN IF NOT EXISTS notes TEXT;")

            cur.execute("ALTER TABLE organizations ADD COLUMN IF NOT EXISTS device_id TEXT;")
            cur.execute("ALTER TABLE organizations ADD COLUMN IF NOT EXISTS contact_person TEXT;")
            cur.execute("ALTER TABLE organizations ADD COLUMN IF NOT EXISTS notes TEXT;")

            cur.execute("ALTER TABLE logistic_needs ADD COLUMN IF NOT EXISTS source_type TEXT;")
            cur.execute("ALTER TABLE logistic_needs ADD COLUMN IF NOT EXISTS source_id TEXT;")
            cur.execute("ALTER TABLE logistic_needs ADD COLUMN IF NOT EXISTS reporting_org_id TEXT;")
            cur.execute("ALTER TABLE logistic_needs ADD COLUMN IF NOT EXISTS reporting_posko_id TEXT;")
            cur.execute("ALTER TABLE logistic_needs ADD COLUMN IF NOT EXISTS affected_group_id TEXT;")
            cur.execute("ALTER TABLE logistic_needs ADD COLUMN IF NOT EXISTS beneficiary_group_description TEXT;")
            cur.execute("ALTER TABLE logistic_needs ADD COLUMN IF NOT EXISTS is_aggregate BOOLEAN NOT NULL DEFAULT FALSE;")
            cur.execute("ALTER TABLE logistic_needs ADD COLUMN IF NOT EXISTS aggregation_level TEXT;")
            cur.execute("ALTER TABLE logistic_needs ADD COLUMN IF NOT EXISTS parent_aggregate_id TEXT;")
            cur.execute("ALTER TABLE logistic_needs ADD COLUMN IF NOT EXISTS canonical_need_id TEXT;")
            cur.execute("ALTER TABLE logistic_needs ADD COLUMN IF NOT EXISTS verification_status TEXT NOT NULL DEFAULT 'self_reported';")
            cur.execute("ALTER TABLE logistic_needs ADD COLUMN IF NOT EXISTS confidence_score INTEGER NOT NULL DEFAULT 50;")

            cur.execute("CREATE INDEX IF NOT EXISTS idx_duplicate_candidates_event_status ON duplicate_candidates(disaster_event_id, status);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_consolidated_needs_event_status ON consolidated_needs(disaster_event_id, status);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_command_corrections_event_target ON command_corrections(disaster_event_id, target_type, target_id, status);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_operational_areas_event_owner ON operational_areas(disaster_event_id, owner_type, owner_id);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_official_admin_areas_parent ON official_admin_areas(parent_code, level);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_posko_nodes_device ON posko_nodes(device_id);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_posko_nodes_admin_area ON posko_nodes(admin_area_id);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_organizations_device ON organizations(device_id);")
            conn.commit()


def insert_location_resolution_seed(cur, disaster_event_id: str):
    cur.execute("SELECT id FROM operational_areas WHERE disaster_event_id = %s LIMIT 1;", (disaster_event_id,))
    if cur.fetchone():
        return
    cur.execute("""
    INSERT INTO operational_areas
    (id, disaster_event_id, owner_type, owner_id, area_level, province_code, coverage_description, verification_status)
    VALUES (%s,%s,'organization','org-bpbd-demo','province','DEMO-PROV','Demo aggregate province-level operation. Needs child city/district/village breakdown before field distribution.', 'self_reported');
    """, ("oparea-demo-province", disaster_event_id))


def seed_official_admin_areas(cur):
    cur.execute("SELECT code FROM official_admin_areas LIMIT 1;")
    if cur.fetchone():
        return
    seed_rows = [
        ("11", None, "Aceh", "province"),
        ("11.06", "11", "Aceh Besar", "city"),
        ("11.06.10", "11.06", "Lhoong", "district"),
        ("11.06.10.2001", "11.06.10", "Desa A", "village"),
        ("11.06.10.2002", "11.06.10", "Desa B", "village"),
        ("11.06.10.2003", "11.06.10", "Desa C", "village"),
        ("11.71", "11", "Kota Banda Aceh", "city"),
        ("11.71.02", "11.71", "Baiturrahman", "district"),
        ("11.71.02.1001", "11.71.02", "Kampung Baru", "village"),
        ("11.71.02.1002", "11.71.02", "Peuniti", "village"),
        ("31", None, "DKI Jakarta", "province"),
        ("31.71", "31", "Kota Jakarta Pusat", "city"),
        ("31.71.01", "31.71", "Gambir", "district"),
        ("31.71.01.1001", "31.71.01", "Gambir", "village")
    ]
    for code, parent_code, name, level in seed_rows:
        cur.execute("""
        INSERT INTO official_admin_areas
        (code, parent_code, name, level, source_name, source_url)
        VALUES (%s,%s,%s,%s,'Rescue-Net demo cache / official admin area reference','https://data.go.id')
        ON CONFLICT (code) DO NOTHING;
        """, (code, parent_code, name, level))


@app.post("/geo/locations")
def create_geo_location(payload: GeoLocationCreate):
    ensure_location_resolution_tables()
    location_id = "geo-" + uuid.uuid4().hex[:12]
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
            INSERT INTO geo_locations (
                id, country_code, province_code, province_name, city_code, city_name,
                district_code, district_name, village_code, village_name, location_name,
                lat, lng, accuracy_meters, admin_level, source
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING *;
            """, (
                location_id, payload.country_code, payload.province_code, payload.province_name,
                payload.city_code, payload.city_name, payload.district_code, payload.district_name,
                payload.village_code, payload.village_name, payload.location_name,
                payload.lat, payload.lng, payload.accuracy_meters, payload.admin_level, payload.source
            ))
            row = rn_dict_row(cur)
            conn.commit()
    return {"status": "created", "geo_location": row}


@app.get("/geo/locations")
def list_geo_locations(admin_level: Optional[str] = None, q: Optional[str] = None):
    ensure_location_resolution_tables()
    where = ["1=1"]
    params = []
    if admin_level:
        where.append("admin_level = %s")
        params.append(admin_level)
    if q:
        where.append("(location_name ILIKE %s OR village_name ILIKE %s OR district_name ILIKE %s OR city_name ILIKE %s)")
        params.extend([f"%{q}%"] * 4)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM geo_locations WHERE " + " AND ".join(where) + " ORDER BY updated_at DESC LIMIT 200;", params)
            rows = rn_rows_to_dicts(cur)
    return rows


@app.get("/admin-areas/sources")
def official_admin_area_sources():
    return {
        "status": "ok",
        "mode": "local_cache_first",
        "sources": [
            {
                "name": "Portal Satu Data Indonesia",
                "url": "https://data.go.id",
                "usage": "reference/import source when an official wilayah dataset is available"
            },
            {
                "name": "Kode wilayah pemerintah/BPS/Kemendagri",
                "url": "https://www.bps.go.id",
                "usage": "reference for administrative code hierarchy"
            }
        ],
        "tree_levels": ["province", "city", "district", "village"],
        "note": "Rescue-Net stores the hierarchy locally so field reporting remains fast and usable during disasters."
    }


@app.get("/admin-areas/children")
def list_admin_area_children(parent_code: Optional[str] = None, level: Optional[str] = None, q: Optional[str] = None):
    ensure_location_resolution_tables()
    with get_conn() as conn:
        with conn.cursor() as cur:
            seed_official_admin_areas(cur)
            where = ["is_active = TRUE"]
            params = []
            if parent_code:
                where.append("parent_code = %s")
                params.append(parent_code)
            else:
                where.append("parent_code IS NULL")
            if level:
                where.append("level = %s")
                params.append(level)
            if q:
                where.append("name ILIKE %s")
                params.append(f"%{q}%")
            cur.execute("""
            SELECT code, parent_code, name, level, source_name, source_url
            FROM official_admin_areas
            WHERE """ + " AND ".join(where) + """
            ORDER BY name
            LIMIT 500;
            """, params)
            rows = rn_rows_to_dicts(cur)
            conn.commit()
    return rows


@app.get("/admin-areas/tree")
def list_admin_area_tree():
    ensure_location_resolution_tables()
    with get_conn() as conn:
        with conn.cursor() as cur:
            seed_official_admin_areas(cur)
            cur.execute("""
            SELECT code, parent_code, name, level, source_name, source_url
            FROM official_admin_areas
            WHERE is_active = TRUE
            ORDER BY code;
            """)
            rows = rn_rows_to_dicts(cur)
            conn.commit()
    return {
        "status": "ok",
        "source_reference": "https://data.go.id",
        "tree_levels": ["province", "city", "district", "village"],
        "areas": rows
    }


@app.post("/operational-areas")
def create_operational_area(payload: OperationalAreaCreate):
    ensure_location_resolution_tables()
    area_id = "oparea-" + uuid.uuid4().hex[:12]
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
            INSERT INTO operational_areas (
                id, disaster_event_id, owner_type, owner_id, area_level, country_code,
                province_code, city_code, district_code, village_code, center_lat,
                center_lng, radius_meters, boundary_geojson, coverage_description, verification_status
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING *;
            """, (
                area_id, payload.disaster_event_id, payload.owner_type, payload.owner_id,
                payload.area_level, payload.country_code, payload.province_code,
                payload.city_code, payload.district_code, payload.village_code,
                payload.center_lat, payload.center_lng, payload.radius_meters,
                json.dumps(payload.boundary_geojson) if payload.boundary_geojson else None,
                payload.coverage_description, payload.verification_status
            ))
            row = rn_dict_row(cur)
            conn.commit()
    return {"status": "created", "operational_area": row}


@app.get("/operational-areas")
def list_operational_areas(disaster_event_id: Optional[str] = None, owner_type: Optional[str] = None):
    ensure_location_resolution_tables()
    where = ["1=1"]
    params = []
    if disaster_event_id:
        where.append("disaster_event_id = %s")
        params.append(disaster_event_id)
    if owner_type:
        where.append("owner_type = %s")
        params.append(owner_type)
    with get_conn() as conn:
        with conn.cursor() as cur:
            if disaster_event_id:
                insert_location_resolution_seed(cur, disaster_event_id)
                conn.commit()
            cur.execute("SELECT * FROM operational_areas WHERE " + " AND ".join(where) + " ORDER BY updated_at DESC LIMIT 200;", params)
            rows = rn_rows_to_dicts(cur)
    return rows


@app.post("/beneficiary-groups")
def create_beneficiary_group(payload: BeneficiaryGroupCreate):
    ensure_location_resolution_tables()
    group_id = "bengrp-" + uuid.uuid4().hex[:12]
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
            INSERT INTO beneficiary_groups (
                id, disaster_event_id, geo_location_id, group_name, group_type,
                estimated_people_count, household_count, description, verified_status
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING *;
            """, (
                group_id, payload.disaster_event_id, payload.geo_location_id,
                payload.group_name, payload.group_type, payload.estimated_people_count,
                payload.household_count, payload.description, payload.verified_status
            ))
            row = rn_dict_row(cur)
            conn.commit()
    return {"status": "created", "beneficiary_group": row}


@app.get("/beneficiary-groups")
def list_beneficiary_groups(disaster_event_id: Optional[str] = None):
    ensure_location_resolution_tables()
    params = []
    where = ["1=1"]
    if disaster_event_id:
        where.append("disaster_event_id = %s")
        params.append(disaster_event_id)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM beneficiary_groups WHERE " + " AND ".join(where) + " ORDER BY updated_at DESC LIMIT 200;", params)
            rows = rn_rows_to_dicts(cur)
    return rows


@app.post("/duplicates/check")
def check_duplicate_candidates(payload: DuplicateCheckRequest):
    ensure_location_resolution_tables()
    ensure_community_report_tables()
    created = 0
    candidates = []

    with get_conn() as conn:
        with conn.cursor() as cur:
            if payload.object_type in {"need", "all"}:
                cur.execute("""
                SELECT id, disaster_event_id, node_id, item_name, unit, priority, status,
                       COALESCE(beneficiary_group_description, '') AS beneficiary_group_description,
                       COALESCE(admin_level, '') AS admin_level,
                       COALESCE(is_aggregate, FALSE) AS is_aggregate
                FROM logistic_needs
                WHERE disaster_event_id = %s AND status <> 'closed'
                ORDER BY created_at DESC
                LIMIT 300;
                """, (payload.disaster_event_id,))
                needs = rn_rows_to_dicts(cur)
                for i, a in enumerate(needs):
                    for b in needs[i + 1:]:
                        if a["id"] == b["id"]:
                            continue
                        same_item = (a["item_name"] or "").strip().lower() == (b["item_name"] or "").strip().lower()
                        same_node = a.get("node_id") and a.get("node_id") == b.get("node_id")
                        same_group = a.get("beneficiary_group_description") and a.get("beneficiary_group_description") == b.get("beneficiary_group_description")
                        aggregate_overlap = bool(a.get("is_aggregate") or b.get("is_aggregate"))
                        if not same_item or not (same_node or same_group or aggregate_overlap):
                            continue
                        score = 50 + (25 if same_node else 0) + (15 if same_group else 0) + (10 if aggregate_overlap else 0)
                        reason = "same item"
                        if same_node:
                            reason += " + same posko"
                        if same_group:
                            reason += " + same beneficiary group"
                        if aggregate_overlap:
                            reason += " + aggregation overlap unknown"
                        cur.execute("""
                        SELECT id FROM duplicate_candidates
                        WHERE disaster_event_id = %s AND object_type = 'need'
                          AND ((object_id_a = %s AND object_id_b = %s) OR (object_id_a = %s AND object_id_b = %s))
                        LIMIT 1;
                        """, (payload.disaster_event_id, a["id"], b["id"], b["id"], a["id"]))
                        if cur.fetchone():
                            continue
                        cand_id = "dupcand-" + uuid.uuid4().hex[:12]
                        cur.execute("""
                        INSERT INTO duplicate_candidates
                        (id, disaster_event_id, object_type, object_id_a, object_id_b, match_score, match_reason, same_admin_area, status)
                        VALUES (%s,%s,'need',%s,%s,%s,%s,%s,'candidate')
                        RETURNING *;
                        """, (cand_id, payload.disaster_event_id, a["id"], b["id"], min(100, score), reason, same_node or same_group))
                        candidates.append(rn_dict_row(cur))
                        created += 1
            if payload.object_type in {"community_report", "report", "all"}:
                cur.execute("""
                SELECT id, disaster_event_id, report_type, title, urgent_needs, affected_people_count,
                       location_text, reporter_phone, area_level, province_name, city_name,
                       district_name, village_name, COALESCE(is_aggregate, FALSE) AS is_aggregate,
                       COALESCE(consolidation_status, '') AS consolidation_status
                FROM community_reports
                WHERE disaster_event_id = %s
                  AND deleted_at IS NULL
                  AND status NOT IN ('rejected', 'closed')
                ORDER BY created_at DESC
                LIMIT 300;
                """, (payload.disaster_event_id,))
                reports = rn_rows_to_dicts(cur)
                for i, a in enumerate(reports):
                    for b in reports[i + 1:]:
                        if a["id"] == b["id"]:
                            continue
                        same_type = (a.get("report_type") or "").strip().lower() == (b.get("report_type") or "").strip().lower()
                        same_village = a.get("village_name") and a.get("village_name") == b.get("village_name")
                        same_district = a.get("district_name") and a.get("district_name") == b.get("district_name")
                        same_city = a.get("city_name") and a.get("city_name") == b.get("city_name")
                        same_reporter = a.get("reporter_phone") and a.get("reporter_phone") == b.get("reporter_phone")
                        aggregate_overlap = bool(a.get("is_aggregate") or b.get("is_aggregate") or a.get("area_level") in {"province", "city", "district"} or b.get("area_level") in {"province", "city", "district"})
                        need_a = (a.get("urgent_needs") or a.get("title") or "").strip().lower()
                        need_b = (b.get("urgent_needs") or b.get("title") or "").strip().lower()
                        same_need_text = need_a and need_b and (need_a in need_b or need_b in need_a)
                        if not same_type or not (same_village or same_district or same_city or same_reporter or aggregate_overlap or same_need_text):
                            continue
                        score = 45
                        score += 25 if same_village else 0
                        score += 15 if same_district and not same_village else 0
                        score += 10 if same_city and not same_district else 0
                        score += 10 if same_reporter else 0
                        score += 10 if same_need_text else 0
                        score += 10 if aggregate_overlap else 0
                        reason = "same report type"
                        if same_village:
                            reason += " + same village"
                        elif same_district:
                            reason += " + same district"
                        elif same_city:
                            reason += " + same city"
                        if same_reporter:
                            reason += " + same reporter contact"
                        if same_need_text:
                            reason += " + similar need text"
                        if aggregate_overlap:
                            reason += " + aggregate/child area overlap"
                        cur.execute("""
                        SELECT id FROM duplicate_candidates
                        WHERE disaster_event_id = %s AND object_type = 'community_report'
                          AND ((object_id_a = %s AND object_id_b = %s) OR (object_id_a = %s AND object_id_b = %s))
                        LIMIT 1;
                        """, (payload.disaster_event_id, a["id"], b["id"], b["id"], a["id"]))
                        if cur.fetchone():
                            continue
                        cand_id = "dupcand-" + uuid.uuid4().hex[:12]
                        cur.execute("""
                        INSERT INTO duplicate_candidates
                        (id, disaster_event_id, object_type, object_id_a, object_id_b, match_score, match_reason, same_admin_area, status)
                        VALUES (%s,%s,'community_report',%s,%s,%s,%s,%s,'candidate')
                        RETURNING *;
                        """, (cand_id, payload.disaster_event_id, a["id"], b["id"], min(100, score), reason, bool(same_village or same_district or same_city)))
                        candidates.append(rn_dict_row(cur))
                        created += 1
            if payload.object_type in {"posko", "posko_node", "all"}:
                cur.execute("""
                SELECT id, disaster_event_id, organization_id, name, node_type, location,
                       COALESCE(admin_area_id, '') AS admin_area_id,
                       COALESCE(area_level, '') AS area_level,
                       COALESCE(province_name, '') AS province_name,
                       COALESCE(city_name, '') AS city_name,
                       COALESCE(district_name, '') AS district_name,
                       COALESCE(village_name, '') AS village_name,
                       lat, lng,
                       COALESCE(parent_posko_id, '') AS parent_posko_id,
                       COALESCE(canonical_posko_id, '') AS canonical_posko_id
                FROM posko_nodes
                WHERE disaster_event_id = %s
                  AND operational_status <> 'closed'
                ORDER BY created_at DESC
                LIMIT 400;
                """, (payload.disaster_event_id,))
                poskos = rn_rows_to_dicts(cur)
                for i, a in enumerate(poskos):
                    for b in poskos[i + 1:]:
                        if a["id"] == b["id"]:
                            continue
                        same_admin = a.get("admin_area_id") and a.get("admin_area_id") == b.get("admin_area_id")
                        same_village = a.get("village_name") and a.get("village_name") == b.get("village_name") and a.get("district_name") == b.get("district_name")
                        same_location_text = (a.get("location") or "").strip().lower() and (a.get("location") or "").strip().lower() == (b.get("location") or "").strip().lower()
                        same_org = a.get("organization_id") and a.get("organization_id") == b.get("organization_id")
                        aggregate_overlap = bool(a.get("area_level") in {"province", "city", "district"} or b.get("area_level") in {"province", "city", "district"})
                        close_gps = False
                        if a.get("lat") is not None and a.get("lng") is not None and b.get("lat") is not None and b.get("lng") is not None:
                            close_gps = abs(float(a["lat"]) - float(b["lat"])) < 0.001 and abs(float(a["lng"]) - float(b["lng"])) < 0.001
                        if not (same_admin or same_village or same_location_text or close_gps or (same_org and aggregate_overlap)):
                            continue
                        score = 45
                        score += 25 if same_admin else 0
                        score += 20 if close_gps else 0
                        score += 15 if same_location_text else 0
                        score += 10 if same_org else 0
                        score += 10 if aggregate_overlap else 0
                        reason = "posko location overlap"
                        if same_admin:
                            reason += " + same admin area"
                        if close_gps:
                            reason += " + close GPS"
                        if same_location_text:
                            reason += " + same location text"
                        if same_org:
                            reason += " + same organization"
                        if aggregate_overlap:
                            reason += " + aggregate/child coverage overlap"
                        cur.execute("""
                        SELECT id FROM duplicate_candidates
                        WHERE disaster_event_id = %s AND object_type = 'posko'
                          AND ((object_id_a = %s AND object_id_b = %s) OR (object_id_a = %s AND object_id_b = %s))
                        LIMIT 1;
                        """, (payload.disaster_event_id, a["id"], b["id"], b["id"], a["id"]))
                        if cur.fetchone():
                            continue
                        cand_id = "dupcand-" + uuid.uuid4().hex[:12]
                        cur.execute("""
                        INSERT INTO duplicate_candidates
                        (id, disaster_event_id, object_type, object_id_a, object_id_b, match_score, match_reason, same_admin_area, status)
                        VALUES (%s,%s,'posko',%s,%s,%s,%s,%s,'candidate')
                        RETURNING *;
                        """, (cand_id, payload.disaster_event_id, a["id"], b["id"], min(100, score), reason, bool(same_admin or same_village)))
                        candidates.append(rn_dict_row(cur))
                        created += 1
            conn.commit()

    return {"status": "checked", "created": created, "candidates": candidates}


@app.get("/duplicates/candidates")
def list_duplicate_candidates(disaster_event_id: Optional[str] = None, status: Optional[str] = None, object_type: Optional[str] = None):
    ensure_location_resolution_tables()
    where = ["1=1"]
    params = []
    if disaster_event_id:
        where.append("disaster_event_id = %s")
        params.append(disaster_event_id)
    if status:
        where.append("status = %s")
        params.append(status)
    if object_type:
        where.append("object_type = %s")
        params.append(object_type)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM duplicate_candidates WHERE " + " AND ".join(where) + " ORDER BY match_score DESC, created_at DESC LIMIT 300;", params)
            rows = rn_rows_to_dicts(cur)
    return rows


@app.get("/data-consolidation/posko-coverage-review")
def posko_coverage_review(disaster_event_id: str = "event-sim-001"):
    ensure_location_resolution_tables()
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
            SELECT p.*, o.name AS organization_name
            FROM posko_nodes p
            LEFT JOIN organizations o ON o.id = p.organization_id
            WHERE p.disaster_event_id = %s
              AND COALESCE(p.area_level, '') IN ('province', 'city', 'district')
              AND p.operational_status <> 'closed'
            ORDER BY p.created_at DESC
            LIMIT 200;
            """, (disaster_event_id,))
            aggregate_poskos = rn_rows_to_dicts(cur)
            review = []
            for row in aggregate_poskos:
                level = row.get("area_level")
                admin_id = row.get("admin_area_id")
                child_where = ["disaster_event_id = %s", "operational_status <> 'closed'", "id <> %s", "organization_id = %s"]
                params = [disaster_event_id, row["id"], row["organization_id"]]
                if level == "province":
                    child_where.append("province_name = %s")
                    params.append(row.get("province_name"))
                elif level == "city":
                    child_where.append("city_name = %s")
                    params.append(row.get("city_name"))
                elif level == "district":
                    child_where.append("district_name = %s")
                    params.append(row.get("district_name"))
                child_where.append("COALESCE(area_level, '') IN ('village', 'point')")
                cur.execute("SELECT COUNT(*) FROM posko_nodes WHERE " + " AND ".join(child_where) + ";", params)
                child_count = cur.fetchone()[0]
                review.append({
                    **row,
                    "child_posko_count": child_count,
                    "coverage_status": "needs_child_posko_breakdown" if child_count == 0 else "has_child_posko",
                    "sop_rule": "Aggregate posko/organization is command coverage only. Do not use it as final distribution target until village/point posko or verified beneficiary group exists.",
                    "admin_area_id": admin_id
                })
    return {
        "status": "ok",
        "disaster_event_id": disaster_event_id,
        "aggregate_posko_total": len(review),
        "needs_child_breakdown": len([x for x in review if x["coverage_status"] == "needs_child_posko_breakdown"]),
        "items": review
    }


@app.get("/data-consolidation/raw-reports")
def list_data_consolidation_raw_reports(disaster_event_id: str = "event-sim-001"):
    ensure_location_resolution_tables()
    ensure_community_report_tables()
    rows = []
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
            SELECT id, 'community_report' AS source_type, report_type AS data_type,
                   title, description, location_text, lat, lng,
                   location_status, consolidation_status, area_level,
                   province_name, city_name, district_name, village_name,
                   COALESCE(is_aggregate, FALSE) AS is_aggregate,
                   affected_people_count AS quantity_value,
                   'orang terdampak' AS quantity_unit,
                   urgent_needs AS need_text,
                   status, trust_score, created_at
            FROM community_reports
            WHERE disaster_event_id = %s AND deleted_at IS NULL
            ORDER BY created_at DESC
            LIMIT 150;
            """, (disaster_event_id,))
            rows.extend(rn_rows_to_dicts(cur))
            cur.execute("""
            SELECT id, 'logistic_need' AS source_type, 'logistic' AS data_type,
                   item_name AS title, beneficiary_group_description AS description,
                   COALESCE(node_id, '') AS location_text, lat, lng,
                   CASE
                     WHEN lat IS NOT NULL AND lng IS NOT NULL THEN 'verified_location'
                     WHEN admin_level IN ('village', 'point') THEN 'admin_area_detected'
                     WHEN admin_level IN ('province', 'city', 'district') THEN 'admin_area_only'
                     ELSE 'no_coordinate'
                   END AS location_status,
                   CASE
                     WHEN COALESCE(is_aggregate, FALSE) THEN 'excluded_aggregate'
                     WHEN lat IS NOT NULL AND lng IS NOT NULL THEN 'ready_for_review'
                     WHEN admin_level IN ('village', 'point') THEN 'ready_for_review'
                     WHEN admin_level IN ('province', 'city', 'district') THEN 'not_ready_admin_only'
                     ELSE 'not_ready_no_location'
                   END AS consolidation_status,
                   admin_level AS area_level,
                   NULL AS province_name, NULL AS city_name, NULL AS district_name, NULL AS village_name,
                   COALESCE(is_aggregate, FALSE) AS is_aggregate,
                   quantity_needed AS quantity_value, unit AS quantity_unit,
                   item_name AS need_text, status, confidence_score AS trust_score, created_at
            FROM logistic_needs
            WHERE disaster_event_id = %s
            ORDER BY created_at DESC
            LIMIT 150;
            """, (disaster_event_id,))
            rows.extend(rn_rows_to_dicts(cur))
    return sorted(rows, key=lambda row: str(row.get("created_at") or ""), reverse=True)[:250]


@app.post("/duplicates/{candidate_id}/resolve")
def resolve_duplicate_candidate(candidate_id: str, payload: DuplicateResolveRequest):
    ensure_location_resolution_tables()
    allowed = {"candidate", "confirmed_duplicate", "not_duplicate", "needs_review", "merged"}
    if payload.status not in allowed:
        raise HTTPException(status_code=400, detail="Invalid duplicate candidate status")
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
            UPDATE duplicate_candidates
            SET status = %s, reviewed_by = %s, review_notes = %s, updated_at = NOW()
            WHERE id = %s
            RETURNING *;
            """, (payload.status, payload.reviewed_by, payload.review_notes, candidate_id))
            row = rn_dict_row(cur)
            conn.commit()
    if not row:
        raise HTTPException(status_code=404, detail="Duplicate candidate not found")
    return {"status": "resolved", "duplicate_candidate": row}


@app.post("/consolidated-needs")
def create_consolidated_need(payload: ConsolidatedNeedCreate):
    ensure_location_resolution_tables()
    need_id = "conneed-" + uuid.uuid4().hex[:12]
    source_ids = payload.source_ids or []
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
            INSERT INTO consolidated_needs (
                id, disaster_event_id, canonical_area_id, canonical_posko_id, need_type,
                item_name, quantity_final, quantity_unit, quantity_min, quantity_max,
                confidence_level, source_count, source_ids_json, merge_method, status
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING *;
            """, (
                need_id, payload.disaster_event_id, payload.canonical_area_id,
                payload.canonical_posko_id, payload.need_type, payload.item_name,
                payload.quantity_final, payload.quantity_unit, payload.quantity_min,
                payload.quantity_max, payload.confidence_level, len(source_ids),
                json.dumps(source_ids), payload.merge_method, payload.status
            ))
            row = rn_dict_row(cur)
            conn.commit()
    return {"status": "created", "consolidated_need": row}


@app.get("/consolidated-needs")
def list_consolidated_needs(disaster_event_id: Optional[str] = None, status: Optional[str] = None):
    ensure_location_resolution_tables()
    where = ["1=1"]
    params = []
    if disaster_event_id:
        where.append("disaster_event_id = %s")
        params.append(disaster_event_id)
    if status:
        where.append("status = %s")
        params.append(status)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM consolidated_needs WHERE " + " AND ".join(where) + " ORDER BY updated_at DESC LIMIT 300;", params)
            rows = rn_rows_to_dicts(cur)
    return rows


@app.get("/command-corrections")
def list_command_corrections(disaster_event_id: str = "event-sim-001", status: Optional[str] = "active"):
    ensure_location_resolution_tables()
    params = [disaster_event_id]
    where = ["disaster_event_id = %s"]
    if status:
        where.append("status = %s")
        params.append(status)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM command_corrections WHERE " + " AND ".join(where) + " ORDER BY updated_at DESC LIMIT 300;", params)
            rows = rn_rows_to_dicts(cur)
    return rows


@app.post("/command-corrections")
def create_command_correction(payload: CommandCorrectionCreate):
    ensure_location_resolution_tables()
    if payload.target_type != "consolidated_need":
        raise HTTPException(status_code=400, detail="Only consolidated_need command correction is available")
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
            SELECT id, disaster_event_id, quantity_final
            FROM consolidated_needs
            WHERE id = %s AND disaster_event_id = %s
            LIMIT 1;
            """, (payload.target_id, payload.disaster_event_id))
            need = rn_dict_row(cur)
            if not need:
                raise HTTPException(status_code=404, detail="Consolidated need not found")
            original_quantity = float(need.get("quantity_final") or 0)
            corrected_quantity = float(payload.corrected_quantity or 0)
            correction_delta = corrected_quantity - original_quantity
            cur.execute("""
            UPDATE command_corrections
            SET status = 'superseded', updated_at = NOW()
            WHERE disaster_event_id = %s AND target_type = %s AND target_id = %s AND status = 'active';
            """, (payload.disaster_event_id, payload.target_type, payload.target_id))
            correction_id = "cmdcorr-" + uuid.uuid4().hex[:12]
            cur.execute("""
            INSERT INTO command_corrections (
                id, disaster_event_id, target_type, target_id,
                original_quantity, corrected_quantity, correction_delta,
                corrected_by, correction_reason, correction_note, status
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'active')
            RETURNING *;
            """, (
                correction_id, payload.disaster_event_id, payload.target_type, payload.target_id,
                original_quantity, corrected_quantity, correction_delta,
                payload.corrected_by, payload.correction_reason, payload.correction_note
            ))
            row = rn_dict_row(cur)
            conn.commit()
    return {"status": "corrected", "command_correction": row}


@app.get("/data-consolidation/national-rollup")
def data_consolidation_national_rollup(disaster_event_id: str = "event-sim-001", include_aggregate: bool = False, scenario: str = "optimal"):
    ensure_location_resolution_tables()
    ensure_community_report_tables()
    scenario = (scenario or "optimal").strip().lower()
    if scenario not in {"minimum", "optimal", "maximum"}:
        raise HTTPException(status_code=400, detail="scenario must be minimum, optimal, or maximum")
    if scenario == "maximum":
        include_aggregate = True
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
            SELECT cn.*,
                   p.name AS posko_name,
                   p.organization_id,
                   COALESCE(p.area_level, '') AS posko_area_level,
                   COALESCE(p.admin_area_id, '') AS posko_admin_area_id,
                   COALESCE(p.province_name, '') AS province_name,
                   COALESCE(p.city_name, '') AS city_name,
                   COALESCE(p.district_name, '') AS district_name,
                   COALESCE(p.village_name, '') AS village_name,
                   COALESCE(p.location, '') AS posko_location
            FROM consolidated_needs cn
            LEFT JOIN posko_nodes p ON p.id = cn.canonical_posko_id
            WHERE cn.disaster_event_id = %s
              AND COALESCE(cn.status, '') NOT IN ('rejected', 'closed')
            ORDER BY cn.need_type, cn.item_name, cn.quantity_unit, cn.updated_at DESC;
            """, (disaster_event_id,))
            needs = rn_rows_to_dicts(cur)
            cur.execute("""
            SELECT *
            FROM duplicate_candidates
            WHERE disaster_event_id = %s
              AND status IN ('candidate', 'needs_review', 'confirmed_duplicate')
            ORDER BY match_score DESC, created_at DESC
            LIMIT 500;
            """, (disaster_event_id,))
            duplicate_rows = rn_rows_to_dicts(cur)
            cur.execute("""
            SELECT *
            FROM command_corrections
            WHERE disaster_event_id = %s
              AND target_type = 'consolidated_need'
              AND status = 'active';
            """, (disaster_event_id,))
            correction_rows = rn_rows_to_dicts(cur)
            cur.execute("""
            SELECT owner_id, owner_type, area_level, coverage_description, verification_status
            FROM operational_areas
            WHERE disaster_event_id = %s
              AND area_level IN ('province', 'city', 'district')
            ORDER BY updated_at DESC
            LIMIT 200;
            """, (disaster_event_id,))
            aggregate_areas = rn_rows_to_dicts(cur)

    duplicate_by_id = {}
    for cand in duplicate_rows:
        for key in (cand.get("object_id_a"), cand.get("object_id_b")):
            if key:
                duplicate_by_id.setdefault(str(key), []).append(cand)
    correction_by_need_id = {str(row["target_id"]): row for row in correction_rows if row.get("target_id")}

    aggregate_levels = {"province", "city", "district"}
    detail_rows = []
    aggregate_context = []
    grouped = {}
    for row in needs:
        source_ids = row.get("source_ids_json") or []
        if isinstance(source_ids, str):
            try:
                source_ids = json.loads(source_ids)
            except Exception:
                source_ids = [source_ids]
        source_ids = [str(x) for x in source_ids if x]
        posko_id = row.get("canonical_posko_id")
        correction = correction_by_need_id.get(str(row.get("id")))
        original_quantity_final = float(row.get("quantity_final") or 0)
        effective_quantity_final = float(correction.get("corrected_quantity") if correction else original_quantity_final)
        manual_delta = float(correction.get("correction_delta") or 0) if correction else 0
        area_level = row.get("posko_area_level") or ("area" if row.get("canonical_area_id") else "")
        duplicate_hits = []
        for source_id in source_ids + ([str(posko_id)] if posko_id else []):
            duplicate_hits.extend(duplicate_by_id.get(source_id, []))
        duplicate_hits = {hit["id"]: hit for hit in duplicate_hits}.values()
        is_aggregate_context = area_level in aggregate_levels or (
            row.get("canonical_area_id") and str(row.get("canonical_area_id")).lower() not in {"", "unknown-area"}
            and not row.get("canonical_posko_id")
        )
        trace = {
            "province": row.get("province_name") or "",
            "city": row.get("city_name") or "",
            "district": row.get("district_name") or "",
            "village": row.get("village_name") or "",
            "posko_id": posko_id,
            "posko_name": row.get("posko_name") or row.get("canonical_area_id") or "area report",
            "area_level": area_level or "unknown",
            "source_ids": source_ids
        }
        enriched = {
            **row,
            "trace": trace,
            "original_quantity_final": original_quantity_final,
            "effective_quantity_final": effective_quantity_final,
            "has_command_correction": bool(correction),
            "manual_correction_delta": manual_delta,
            "manual_correction_delta_abs": abs(manual_delta),
            "manual_correction": correction,
            "is_aggregate_context": bool(is_aggregate_context),
            "duplicate_warning_count": len(list(duplicate_hits)),
            "duplicate_warnings": [
                {
                    "id": hit.get("id"),
                    "object_type": hit.get("object_type"),
                    "match_score": hit.get("match_score"),
                    "match_reason": hit.get("match_reason"),
                    "status": hit.get("status")
                }
                for hit in duplicate_hits
            ],
            "sop_note": (
                "Aggregate command context only; trace to child posko/village before distribution."
                if is_aggregate_context
                else "Detail candidate; may enter national baseline, with warning if overlaps remain."
            )
        }
        if is_aggregate_context and not include_aggregate:
            aggregate_context.append(enriched)
            continue
        detail_rows.append(enriched)
        area_key = "|".join([
            str(row.get("posko_admin_area_id") or ""),
            str(row.get("canonical_posko_id") or ""),
            str(row.get("canonical_area_id") or ""),
            str(row.get("village_name") or ""),
            str(row.get("district_name") or ""),
            str(row.get("city_name") or ""),
            str(row.get("province_name") or "")
        ])
        group_key = (
            row.get("need_type") or "need",
            (row.get("item_name") or "unknown").strip().lower(),
            row.get("quantity_unit") or ""
        )
        if scenario == "minimum":
            group_key = group_key + (area_key,)
        bucket = grouped.setdefault(group_key, {
            "need_type": row.get("need_type") or "need",
            "item_name": row.get("item_name") or "unknown",
            "quantity_unit": row.get("quantity_unit") or "",
            "scenario_area_key": area_key if scenario == "minimum" else "",
            "baseline_quantity": 0,
            "range_min": 0,
            "range_max": 0,
            "detail_count": 0,
            "source_count": 0,
            "duplicate_warning_count": 0,
            "manual_correction_total": 0,
            "manual_correction_abs_total": 0,
            "corrected_detail_count": 0,
            "has_warning": False,
            "trace_rows": []
        })
        row_min = effective_quantity_final if correction else float(row.get("quantity_min") or row.get("quantity_final") or 0)
        row_final = effective_quantity_final
        row_max = max(effective_quantity_final, float(row.get("quantity_max") or row.get("quantity_final") or 0))
        if scenario == "minimum":
            if bucket["detail_count"] == 0:
                bucket["baseline_quantity"] = row_min
                bucket["range_min"] = row_min
                bucket["range_max"] = row_max
            else:
                bucket["baseline_quantity"] = min(float(bucket["baseline_quantity"] or 0), row_min)
                bucket["range_min"] = min(float(bucket["range_min"] or 0), row_min)
                bucket["range_max"] = min(float(bucket["range_max"] or 0), row_max)
        else:
            bucket["baseline_quantity"] += row_final
            bucket["range_min"] += row_min
            bucket["range_max"] += row_max
        bucket["detail_count"] += 1
        bucket["source_count"] += int(row.get("source_count") or len(source_ids) or 0)
        bucket["duplicate_warning_count"] += enriched["duplicate_warning_count"]
        bucket["manual_correction_total"] += manual_delta
        bucket["manual_correction_abs_total"] += abs(manual_delta)
        bucket["corrected_detail_count"] += 1 if correction else 0
        bucket["has_warning"] = bucket["has_warning"] or enriched["duplicate_warning_count"] > 0
        bucket["trace_rows"].append(enriched)

    if scenario == "minimum":
        min_grouped = {}
        for row in grouped.values():
            key = (row["need_type"], row["item_name"].strip().lower(), row["quantity_unit"])
            bucket = min_grouped.setdefault(key, {
                "need_type": row["need_type"],
                "item_name": row["item_name"],
                "quantity_unit": row["quantity_unit"],
                "baseline_quantity": 0,
                "range_min": 0,
                "range_max": 0,
                "detail_count": 0,
                "source_count": 0,
                "duplicate_warning_count": 0,
                "manual_correction_total": 0,
                "manual_correction_abs_total": 0,
                "corrected_detail_count": 0,
                "has_warning": False,
                "trace_rows": []
            })
            bucket["baseline_quantity"] += float(row["baseline_quantity"] or 0)
            bucket["range_min"] += float(row["range_min"] or 0)
            bucket["range_max"] += float(row["range_max"] or 0)
            bucket["detail_count"] += int(row["detail_count"] or 0)
            bucket["source_count"] += int(row["source_count"] or 0)
            bucket["duplicate_warning_count"] += int(row["duplicate_warning_count"] or 0)
            bucket["manual_correction_total"] += float(row["manual_correction_total"] or 0)
            bucket["manual_correction_abs_total"] += float(row["manual_correction_abs_total"] or 0)
            bucket["corrected_detail_count"] += int(row["corrected_detail_count"] or 0)
            bucket["has_warning"] = bucket["has_warning"] or bool(row["has_warning"])
            bucket["trace_rows"].extend(row["trace_rows"])
        national_rollup = sorted(min_grouped.values(), key=lambda item: (item["need_type"], item["item_name"]))
    else:
        national_rollup = sorted(grouped.values(), key=lambda item: (item["need_type"], item["item_name"]))
    for item in national_rollup:
        item["scenario"] = scenario
        if scenario == "minimum":
            item["view_mode"] = "minimum_same_area_dedup"
            item["operator_note"] = "Minimum memakai angka terkecil untuk posko/wilayah yang relatif sama dan tidak menghitung agregat."
        elif scenario == "maximum":
            item["view_mode"] = "maximum_with_aggregate_context"
            item["operator_note"] = "Maximum menghitung detail plus konteks agregat. Pakai untuk estimasi kapasitas terburuk, bukan angka distribusi final."
        else:
            item["view_mode"] = "optimal_baseline_sum_of_max_per_posko"
            item["operator_note"] = (
                "Optimal memakai penjumlahan angka terbesar per posko/detail. "
                "Range memperlihatkan min-max dari sumber konsolidasi. Warning berarti ada sumber/posko lain yang perlu review sebelum final."
            )
        baseline = float(item.get("baseline_quantity") or 0)
        item["manual_correction_share"] = (
            float(item.get("manual_correction_abs_total") or 0) / baseline
            if baseline else 0
        )
    return {
        "status": "ok",
        "disaster_event_id": disaster_event_id,
        "scenario": scenario,
        "include_aggregate": include_aggregate,
        "rule": "minimum=min per same area without aggregate; optimal=sum of consolidated detail rows using MAX per posko; maximum=optimal plus aggregate context.",
        "national_rollup": national_rollup,
        "detail_rows": detail_rows,
        "aggregate_context": aggregate_context,
        "aggregate_areas": aggregate_areas,
        "command_correction_count": len(correction_rows),
        "duplicate_candidate_count": len(duplicate_rows)
    }


@app.get("/data-consolidation/evidence-requirements")
def data_consolidation_evidence_requirements():
    return {
        "status": "ok",
        "source": "Rescue-Net anti-misinformation rules",
        "official_area_reference": {
            "label": "Portal Satu Data Indonesia / data.go.id",
            "url": "https://data.go.id",
            "usage": "optional_reference",
            "notes": "Use as a reference for official administrative area datasets when available. GPS, map point, or verified village/admin code remain valid alternatives."
        },
        "rules": [
            {
                "data_type": "community_report",
                "camera_required": "recommended",
                "evidence_required_for_status": ["verified", "converted_to_action", "verified_unique"],
                "accepted_evidence": ["photo", "video", "GPS/map point", "official village/admin area", "verifier note"],
                "notes": "Public report may be stored without media, but cannot become final operational fact without location and verification."
            },
            {
                "data_type": "logistic_need",
                "camera_required": "recommended",
                "evidence_required_for_status": ["verified", "consolidated", "ready_for_distribution"],
                "accepted_evidence": ["photo of affected site/posko list", "posko confirmation", "beneficiary group note", "GPS/map point"],
                "notes": "Use MAX first when duplicate/overlap is possible."
            },
            {
                "data_type": "posko_node",
                "camera_required": "recommended",
                "evidence_required_for_status": ["verified_posko", "official_node"],
                "accepted_evidence": ["photo of posko signage/site", "PIC contact", "organization letter", "GPS/map point"],
                "notes": "Province/city organization coverage must be broken down into child area/posko before village-level distribution."
            },
            {
                "data_type": "aid_offer",
                "camera_required": "recommended_for_goods",
                "evidence_required_for_status": ["ready_for_pickup", "received_verified"],
                "accepted_evidence": ["photo of goods", "donor contact", "packing list", "pickup/delivery proof"],
                "notes": "Photo helps avoid fake/duplicate aid offers."
            },
            {
                "data_type": "distribution_flow",
                "camera_required": "required_at_handover",
                "evidence_required_for_status": ["pickup_confirmed", "received_verified", "closed"],
                "accepted_evidence": ["pickup photo", "delivery photo", "recipient signature", "vehicle/driver note", "timestamp/location"],
                "notes": "Proof of delivery is required before closing a distribution flow."
            },
            {
                "data_type": "medical_case_or_shelter",
                "camera_required": "restricted_optional",
                "evidence_required_for_status": ["verified"],
                "accepted_evidence": ["authorized medical/shelter confirmation", "redacted document", "restricted photo if consented"],
                "notes": "Privacy first. Do not expose sensitive victim/medical photos publicly."
            },
            {
                "data_type": "search_found",
                "camera_required": "restricted_optional",
                "evidence_required_for_status": ["verified_match", "closed"],
                "accepted_evidence": ["restricted photo", "identity verifier note", "family/official confirmation"],
                "notes": "Highly sensitive. Evidence must be restricted to authorized verifiers."
            }
        ]
    }


@app.post("/consolidated-needs/rebuild")
def rebuild_consolidated_needs(disaster_event_id: str = "event-sim-001"):
    ensure_location_resolution_tables()
    ensure_community_report_tables()
    ensure_unit_normalization_tables()
    # Safe first-pass strategy:
    # group raw needs by event + posko + item + unit; use max/latest-like quantity,
    # not sum, because duplicate/overlap has not been reviewed yet.
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM consolidated_needs WHERE disaster_event_id = %s AND merge_method = 'auto_max_by_posko_item';", (disaster_event_id,))
            cur.execute("DELETE FROM consolidated_needs WHERE disaster_event_id = %s AND merge_method = 'auto_max_by_community_area';", (disaster_event_id,))
            cur.execute("""
            SELECT disaster_event_id, node_id, item_name,
                   COALESCE(normalized_unit, unit) AS unit,
                   MAX(COALESCE(normalized_quantity, quantity_needed)) AS quantity_final,
                   MIN(COALESCE(normalized_quantity, quantity_needed)) AS quantity_min,
                   MAX(COALESCE(normalized_quantity, quantity_needed)) AS quantity_max,
                   COUNT(*) AS source_count,
                   jsonb_agg(id ORDER BY created_at DESC) AS source_ids_json,
                   bool_or(COALESCE(conversion_status, 'not_normalized') = 'needs_unit_review') AS needs_unit_review
            FROM logistic_needs
            WHERE disaster_event_id = %s AND status <> 'closed'
            GROUP BY disaster_event_id, node_id, item_name, COALESCE(normalized_unit, unit)
            ORDER BY item_name;
            """, (disaster_event_id,))
            groups = rn_rows_to_dicts(cur)
            inserted = []
            for g in groups:
                need_id = "conneed-" + uuid.uuid4().hex[:12]
                confidence = "low" if g.get("needs_unit_review") or int(g["source_count"] or 0) > 1 else "medium"
                cur.execute("""
                INSERT INTO consolidated_needs (
                    id, disaster_event_id, canonical_posko_id, need_type, item_name,
                    quantity_final, quantity_unit, quantity_min, quantity_max,
                    confidence_level, source_count, source_ids_json, merge_method, status
                )
                VALUES (%s,%s,%s,'logistic',%s,%s,%s,%s,%s,%s,%s,%s,'auto_max_by_posko_item','needs_review')
                RETURNING *;
                """, (
                    need_id, g["disaster_event_id"], g["node_id"], g["item_name"],
                    g["quantity_final"], g["unit"], g["quantity_min"], g["quantity_max"],
                    confidence, g["source_count"], json.dumps(g["source_ids_json"])
                ))
                inserted.append(rn_dict_row(cur))
            cur.execute("""
            SELECT disaster_event_id,
                   COALESCE(NULLIF(village_name, ''), NULLIF(district_name, ''), NULLIF(city_name, ''), NULLIF(province_name, ''), 'unknown-area') AS area_key,
                   COALESCE(NULLIF(urgent_needs, ''), title, report_type) AS item_name,
                   MAX(COALESCE(affected_people_count, 0)) AS quantity_final,
                   MIN(COALESCE(affected_people_count, 0)) AS quantity_min,
                   MAX(COALESCE(affected_people_count, 0)) AS quantity_max,
                   COUNT(*) AS source_count,
                   jsonb_agg(id ORDER BY created_at DESC) AS source_ids_json
            FROM community_reports
            WHERE disaster_event_id = %s
              AND deleted_at IS NULL
              AND status NOT IN ('rejected', 'closed')
              AND COALESCE(is_aggregate, FALSE) = FALSE
              AND COALESCE(consolidation_status, '') IN ('ready_for_review', 'verified_unique')
              AND COALESCE(area_level, '') IN ('village', 'point')
            GROUP BY 1, 2, 3
            ORDER BY item_name;
            """, (disaster_event_id,))
            community_groups = rn_rows_to_dicts(cur)
            for g in community_groups:
                need_id = "conneed-" + uuid.uuid4().hex[:12]
                confidence = "low" if int(g["source_count"] or 0) > 1 else "medium"
                cur.execute("""
                INSERT INTO consolidated_needs (
                    id, disaster_event_id, canonical_area_id, need_type, item_name,
                    quantity_final, quantity_unit, quantity_min, quantity_max,
                    confidence_level, source_count, source_ids_json, merge_method, status
                )
                VALUES (%s,%s,%s,'community_signal',%s,%s,'orang terdampak',%s,%s,%s,%s,%s,'auto_max_by_community_area','needs_review')
                RETURNING *;
                """, (
                    need_id, g["disaster_event_id"], g["area_key"], g["item_name"],
                    g["quantity_final"], g["quantity_min"], g["quantity_max"],
                    confidence, g["source_count"], json.dumps(g["source_ids_json"])
                ))
                inserted.append(rn_dict_row(cur))
            conn.commit()

    return {"status": "rebuilt", "inserted": len(inserted), "consolidated_needs": inserted}


@app.get("/data-consolidation/summary")
def data_consolidation_summary(disaster_event_id: str = "event-sim-001"):
    ensure_location_resolution_tables()
    ensure_community_report_tables()
    with get_conn() as conn:
        with conn.cursor() as cur:
            insert_location_resolution_seed(cur, disaster_event_id)
            cur.execute("SELECT COUNT(*) FROM logistic_needs WHERE disaster_event_id = %s;", (disaster_event_id,))
            raw_needs = cur.fetchone()[0]
            cur.execute("""
            SELECT COUNT(*) FROM community_reports
            WHERE disaster_event_id = %s AND deleted_at IS NULL;
            """, (disaster_event_id,))
            raw_community_reports = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM consolidated_needs WHERE disaster_event_id = %s;", (disaster_event_id,))
            consolidated = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM duplicate_candidates WHERE disaster_event_id = %s AND status = 'candidate';", (disaster_event_id,))
            duplicate_candidates = cur.fetchone()[0]
            cur.execute("""
            SELECT COUNT(*) FROM logistic_needs
            WHERE disaster_event_id = %s AND (lat IS NULL OR lng IS NULL OR location_accuracy_meters IS NULL);
            """, (disaster_event_id,))
            logistic_location_review_needed = cur.fetchone()[0]
            cur.execute("""
            SELECT COUNT(*) FROM community_reports
            WHERE disaster_event_id = %s
              AND deleted_at IS NULL
              AND COALESCE(consolidation_status, '') IN ('not_ready_no_location', 'not_ready_admin_only', 'needs_location_review');
            """, (disaster_event_id,))
            community_location_review_needed = cur.fetchone()[0]
            cur.execute("""
            SELECT COUNT(*) FROM logistic_needs
            WHERE disaster_event_id = %s AND is_aggregate = TRUE;
            """, (disaster_event_id,))
            logistic_aggregate_reports = cur.fetchone()[0]
            cur.execute("""
            SELECT COUNT(*) FROM community_reports
            WHERE disaster_event_id = %s
              AND deleted_at IS NULL
              AND (COALESCE(is_aggregate, FALSE) = TRUE OR COALESCE(consolidation_status, '') IN ('not_ready_admin_only', 'excluded_aggregate'));
            """, (disaster_event_id,))
            community_aggregate_reports = cur.fetchone()[0]
            conn.commit()
    return {
        "raw_logistic_reports": raw_needs,
        "raw_community_reports": raw_community_reports,
        "raw_reports_total": raw_needs + raw_community_reports,
        "consolidated_needs": consolidated,
        "duplicate_candidates": duplicate_candidates,
        "location_review_needed": logistic_location_review_needed + community_location_review_needed,
        "logistic_location_review_needed": logistic_location_review_needed,
        "community_location_review_needed": community_location_review_needed,
        "aggregate_reports": logistic_aggregate_reports + community_aggregate_reports,
        "logistic_aggregate_reports": logistic_aggregate_reports,
        "community_aggregate_reports": community_aggregate_reports
    }


def ensure_federation_tables():
    ensure_location_resolution_tables()
    ensure_community_report_tables()
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
            CREATE TABLE IF NOT EXISTS federation_nodes (
                id TEXT PRIMARY KEY,
                node_name TEXT NOT NULL,
                node_type TEXT NOT NULL DEFAULT 'partner',
                base_url TEXT,
                organization_id TEXT,
                trust_level TEXT NOT NULL DEFAULT 'unverified',
                sync_scope TEXT NOT NULL DEFAULT 'event',
                disaster_event_id TEXT,
                status TEXT NOT NULL DEFAULT 'active',
                notes TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW()
            );
            """)
            cur.execute("""
            CREATE TABLE IF NOT EXISTS federation_repositories (
                id TEXT PRIMARY KEY,
                node_id TEXT NOT NULL REFERENCES federation_nodes(id) ON DELETE CASCADE,
                repository_name TEXT NOT NULL,
                repository_type TEXT NOT NULL DEFAULT 'sync_events',
                endpoint_path TEXT DEFAULT '/sync/pull',
                direction TEXT NOT NULL DEFAULT 'bidirectional',
                conflict_policy TEXT NOT NULL DEFAULT 'manual_review',
                status TEXT NOT NULL DEFAULT 'active',
                notes TEXT,
                last_sync_at TIMESTAMP,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW()
            );
            """)
            cur.execute("""
            CREATE TABLE IF NOT EXISTS federation_sync_logs (
                id TEXT PRIMARY KEY,
                node_id TEXT REFERENCES federation_nodes(id) ON DELETE SET NULL,
                repository_id TEXT REFERENCES federation_repositories(id) ON DELETE SET NULL,
                direction TEXT NOT NULL,
                status TEXT NOT NULL,
                manifest_json JSONB,
                notes TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT NOW()
            );
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_federation_nodes_event ON federation_nodes(disaster_event_id, status);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_federation_repos_node ON federation_repositories(node_id, status);")
            conn.commit()


@app.post("/federation/nodes")
def create_federation_node(payload: FederationNodeCreate):
    ensure_federation_tables()
    node_id = "fednode-" + uuid.uuid4().hex[:12]
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
            INSERT INTO federation_nodes (
                id, node_name, node_type, base_url, organization_id, trust_level,
                sync_scope, disaster_event_id, status, notes
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING *;
            """, (
                node_id, payload.node_name, payload.node_type, payload.base_url,
                payload.organization_id, payload.trust_level, payload.sync_scope,
                payload.disaster_event_id, payload.status, payload.notes
            ))
            row = rn_dict_row(cur)
            conn.commit()
    return {"status": "created", "federation_node": row}


@app.get("/federation/nodes")
def list_federation_nodes(disaster_event_id: Optional[str] = None, status: Optional[str] = None):
    ensure_federation_tables()
    where = ["1=1"]
    params = []
    if disaster_event_id:
        where.append("(disaster_event_id = %s OR disaster_event_id IS NULL)")
        params.append(disaster_event_id)
    if status:
        where.append("status = %s")
        params.append(status)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM federation_nodes WHERE " + " AND ".join(where) + " ORDER BY updated_at DESC LIMIT 200;", params)
            rows = rn_rows_to_dicts(cur)
    return rows


@app.post("/federation/repositories")
def create_federation_repository(payload: FederationRepositoryCreate):
    ensure_federation_tables()
    repo_id = "fedrepo-" + uuid.uuid4().hex[:12]
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
            INSERT INTO federation_repositories (
                id, node_id, repository_name, repository_type, endpoint_path,
                direction, conflict_policy, status, notes
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING *;
            """, (
                repo_id, payload.node_id, payload.repository_name, payload.repository_type,
                payload.endpoint_path, payload.direction, payload.conflict_policy,
                payload.status, payload.notes
            ))
            row = rn_dict_row(cur)
            conn.commit()
    return {"status": "created", "federation_repository": row}


@app.get("/federation/repositories")
def list_federation_repositories(node_id: Optional[str] = None, status: Optional[str] = None):
    ensure_federation_tables()
    where = ["1=1"]
    params = []
    if node_id:
        where.append("node_id = %s")
        params.append(node_id)
    if status:
        where.append("status = %s")
        params.append(status)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
            SELECT r.*, n.node_name, n.base_url, n.trust_level
            FROM federation_repositories r
            LEFT JOIN federation_nodes n ON n.id = r.node_id
            WHERE """ + " AND ".join(where) + " ORDER BY r.updated_at DESC LIMIT 200;", params)
            rows = rn_rows_to_dicts(cur)
    return rows


@app.get("/federation/manifest/{disaster_event_id}")
def federation_manifest(disaster_event_id: str):
    ensure_federation_tables()
    manifest = {
        "schema": "rescue-net-federation-manifest-v1",
        "disaster_event_id": disaster_event_id,
        "generated_at": datetime.utcnow().isoformat(),
        "policy": {
            "raw_reports_are_not_final": True,
            "use_consolidated_needs_for_operations": True,
            "duplicate_candidates_require_review": True,
            "aggregate_overlap_requires_warning": True
        }
    }
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM sync_events WHERE payload_json::text ILIKE %s ORDER BY created_at DESC LIMIT 100;", (f"%{disaster_event_id}%",))
            manifest["sync_events"] = rn_rows_to_dicts(cur)
            cur.execute("SELECT * FROM community_reports WHERE disaster_event_id = %s AND deleted_at IS NULL ORDER BY created_at DESC LIMIT 100;", (disaster_event_id,))
            manifest["community_reports"] = rn_rows_to_dicts(cur)
            cur.execute("SELECT * FROM consolidated_needs WHERE disaster_event_id = %s ORDER BY updated_at DESC LIMIT 100;", (disaster_event_id,))
            manifest["consolidated_needs"] = rn_rows_to_dicts(cur)
            cur.execute("SELECT * FROM duplicate_candidates WHERE disaster_event_id = %s ORDER BY created_at DESC LIMIT 100;", (disaster_event_id,))
            manifest["duplicate_candidates"] = rn_rows_to_dicts(cur)
            cur.execute("SELECT * FROM operational_areas WHERE disaster_event_id = %s ORDER BY updated_at DESC LIMIT 100;", (disaster_event_id,))
            manifest["operational_areas"] = rn_rows_to_dicts(cur)
    return manifest


@app.post("/federation/sync-logs")
def create_federation_sync_log(payload: FederationSyncLogCreate):
    ensure_federation_tables()
    log_id = "fedlog-" + uuid.uuid4().hex[:12]
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
            INSERT INTO federation_sync_logs
            (id, node_id, repository_id, direction, status, manifest_json, notes)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
            RETURNING *;
            """, (
                log_id, payload.node_id, payload.repository_id, payload.direction,
                payload.status, json.dumps(payload.manifest_json or {}), payload.notes
            ))
            row = rn_dict_row(cur)
            conn.commit()
    return {"status": "created", "federation_sync_log": row}


@app.get("/federation/sync-logs")
def list_federation_sync_logs(node_id: Optional[str] = None, repository_id: Optional[str] = None):
    ensure_federation_tables()
    where = ["1=1"]
    params = []
    if node_id:
        where.append("node_id = %s")
        params.append(node_id)
    if repository_id:
        where.append("repository_id = %s")
        params.append(repository_id)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM federation_sync_logs WHERE " + " AND ".join(where) + " ORDER BY created_at DESC LIMIT 100;", params)
            rows = rn_rows_to_dicts(cur)
    return rows

