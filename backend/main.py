import os
import json
import hashlib
import secrets
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import psycopg
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://rescuenet_user:rescuenet_dev_password@192.168.100.32:5433/rescuenet_db",
)
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "/data/uploads"))

app = FastAPI(
    title="Rescue-Net API",
    description="Open Disaster Coordination & Relief Management System",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

@app.get("/")
def root():
    return {"system": "Rescue-Net", "version": "0.1.0", "status": "running"}

@app.get("/health")
def health():
    return {"status": "ok", "time": datetime.utcnow().isoformat()}

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

@app.get("/volunteers")
def get_volunteers():
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM volunteers ORDER BY created_at DESC;")
        return rows_to_dicts(cur)

@app.post("/volunteers")
def create_volunteer(payload: VolunteerCreate):
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
    item_id = "need-" + uuid.uuid4().hex[:12]
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
        INSERT INTO logistic_needs
        (id, disaster_event_id, node_id, item_name, quantity_needed, unit, priority, needed_before, status)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
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
    item_id = "aid-" + uuid.uuid4().hex[:12]
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
        INSERT INTO aid_offers
        (id, disaster_event_id, donor_name, item_name, quantity, unit, pickup_location, ready_at, status)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
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
        "logistic_needs": [],
        "aid_offers": [],
        "transport_spaces": [],
        "distribution_flows": [],
        "volunteers": [],
        "ecosystem_members": [],
        "resources": [],
        "resource_shares": [],
        "resource_requests": [],
        "summary": {},
        "alerts": [],
        "recommendations": [],
        "sources": [],
    }

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM disaster_events WHERE id = %s;", (disaster_event_id,))
        rows = rows_to_dicts(cur)
        context["disaster"] = rows[0] if rows else None

        cur.execute("SELECT * FROM posko_nodes WHERE disaster_event_id = %s ORDER BY created_at DESC;", (disaster_event_id,))
        context["poskos"] = rows_to_dicts(cur)

        cur.execute("SELECT * FROM logistic_needs WHERE disaster_event_id = %s ORDER BY created_at DESC;", (disaster_event_id,))
        context["logistic_needs"] = rows_to_dicts(cur)

        cur.execute("SELECT * FROM aid_offers WHERE disaster_event_id = %s ORDER BY created_at DESC;", (disaster_event_id,))
        context["aid_offers"] = rows_to_dicts(cur)

        cur.execute("SELECT * FROM transport_spaces WHERE disaster_event_id = %s ORDER BY created_at DESC;", (disaster_event_id,))
        context["transport_spaces"] = rows_to_dicts(cur)

        cur.execute("SELECT * FROM distribution_flows WHERE disaster_event_id = %s ORDER BY created_at DESC;", (disaster_event_id,))
        context["distribution_flows"] = rows_to_dicts(cur)

        cur.execute("SELECT * FROM volunteers ORDER BY created_at DESC LIMIT 50;")
        context["volunteers"] = rows_to_dicts(cur)

        cur.execute("SELECT * FROM disaster_ecosystem_members WHERE disaster_event_id = %s ORDER BY role_in_disaster, member_type;", (disaster_event_id,))
        context["ecosystem_members"] = rows_to_dicts(cur)

        cur.execute("SELECT * FROM resources WHERE disaster_event_id = %s ORDER BY resource_type, trust_level DESC, created_at DESC;", (disaster_event_id,))
        context["resources"] = rows_to_dicts(cur)

        cur.execute("SELECT * FROM resource_shares WHERE disaster_event_id = %s ORDER BY created_at DESC;", (disaster_event_id,))
        context["resource_shares"] = rows_to_dicts(cur)

        cur.execute("""
        SELECT rr.*
        FROM resource_requests rr
        JOIN resources r ON r.id = rr.resource_id
        WHERE r.disaster_event_id = %s
        ORDER BY rr.created_at DESC;
        """, (disaster_event_id,))
        context["resource_requests"] = rows_to_dicts(cur)

    needs = context["logistic_needs"]
    offers = context["aid_offers"]
    transports = context["transport_spaces"]
    flows = context["distribution_flows"]

    critical_needs = [n for n in needs if n.get("priority") == "critical" and n.get("status") == "open"]
    urgent_needs = [n for n in needs if n.get("priority") == "urgent" and n.get("status") == "open"]
    need_pickup = [a for a in offers if a.get("status") == "need_pickup" or a.get("delivery_mode") == "need_pickup"]
    self_delivery = [a for a in offers if a.get("status") == "self_delivery_planned" or a.get("delivery_mode") == "self_deliver_to_posko"]
    available_transports = [t for t in transports if t.get("status") == "available"]
    planned_flows = [f for f in flows if f.get("status") == "planned"]

    context["summary"] = {
        "total_poskos": len(context["poskos"]),
        "total_logistic_needs": len(needs),
        "critical_needs": len(critical_needs),
        "urgent_needs": len(urgent_needs),
        "total_aid_offers": len(offers),
        "aid_need_pickup": len(need_pickup),
        "aid_self_delivery_planned": len(self_delivery),
        "available_transport_spaces": len(available_transports),
        "distribution_flows": len(flows),
        "planned_distribution_flows": len(planned_flows),
        "volunteers_listed": len(context["volunteers"]),
        "ecosystem_members": len(context.get("ecosystem_members", [])),
        "shared_resources": len(context.get("resources", [])),
        "resource_requests": len(context.get("resource_requests", [])),
    }

    for n in critical_needs:
        context["alerts"].append({
            "level": "critical",
            "type": "logistic_need",
            "message": f"{n.get('item_name')} masih critical: {n.get('quantity_needed')} {n.get('unit')}, dibutuhkan sebelum {n.get('needed_before') or 'belum ditentukan'}.",
            "source_table": "logistic_needs",
            "source_id": n.get("id"),
        })

    for a in need_pickup:
        context["alerts"].append({
            "level": "warning",
            "type": "aid_need_pickup",
            "message": f"Bantuan {a.get('item_name')} dari {a.get('donor_name')} perlu pickup di {a.get('pickup_location')}.",
            "source_table": "aid_offers",
            "source_id": a.get("id"),
        })

    if critical_needs and need_pickup and available_transports:
        context["recommendations"].append({
            "priority": "high",
            "message": "Ada kebutuhan critical, bantuan perlu pickup, dan transport tersedia. Prioritaskan matching bantuan dengan transport.",
            "related_sources": {
                "critical_needs": [n.get("id") for n in critical_needs[:5]],
                "aid_offers": [a.get("id") for a in need_pickup[:5]],
                "transport_spaces": [t.get("id") for t in available_transports[:5]],
            }
        })

    if self_delivery:
        context["recommendations"].append({
            "priority": "medium",
            "message": "Ada bantuan yang akan diantar sendiri ke posko. Posko tujuan perlu menyiapkan penerimaan dan verifikasi barang.",
            "related_sources": {
                "aid_offers": [a.get("id") for a in self_delivery[:5]]
            }
        })

    for collection_name, table_name in [
        ("poskos", "posko_nodes"),
        ("logistic_needs", "logistic_needs"),
        ("aid_offers", "aid_offers"),
        ("transport_spaces", "transport_spaces"),
        ("distribution_flows", "distribution_flows"),
        ("volunteers", "volunteers"),
        ("ecosystem_members", "disaster_ecosystem_members"),
        ("resources", "resources"),
        ("resource_shares", "resource_shares"),
        ("resource_requests", "resource_requests"),
    ]:
        for item in context[collection_name]:
            context["sources"].append({
                "source_table": table_name,
                "source_id": item.get("id"),
            })

    return context

class ResourceRequestCreate(BaseModel):
    resource_id: str
    requested_by_type: str
    requested_by_id: str
    request_reason: Optional[str] = None
    related_need_id: Optional[str] = None
    related_distribution_flow_id: Optional[str] = None
    requested_quantity: Optional[float] = None
    requested_time: Optional[str] = None


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


@app.post("/resource-requests")
def create_resource_request(payload: ResourceRequestCreate):
    item_id = "req-" + uuid.uuid4().hex[:12]
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
        INSERT INTO resource_requests
        (id, resource_id, requested_by_type, requested_by_id, request_reason,
         related_need_id, related_distribution_flow_id, requested_quantity,
         requested_time, status)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'requested')
        RETURNING *;
        """, (
            item_id,
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

class ResourceRequestApprove(BaseModel):
    approved_by: str = "command-center"
    assignment_notes: Optional[str] = None
    assigned_quantity: Optional[float] = None


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
    item_id = "stock-" + uuid.uuid4().hex[:12]

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
        INSERT INTO stock_movements
        (id, disaster_event_id, posko_id, item_name, quantity, unit,
         movement_type, movement_direction, source_type, source_id,
         destination_type, destination_id, related_aid_offer_id,
         related_distribution_flow_id, related_logistic_need_id,
         notes, evidence_file_id, owner_type, owner_id,
         visibility_scope, access_policy, verification_status)
        VALUES
        (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
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

@app.get("/verification-context/{disaster_event_id}")
def get_verification_context(disaster_event_id: str):
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
