from datetime import datetime
from typing import Optional
import uuid

from fastapi import APIRouter
from pydantic import BaseModel

from app_shared import get_conn, rows_to_dicts

router = APIRouter(tags=["map"])

class MapPointCreate(BaseModel):
    disaster_event_id: str
    object_type: str
    object_id: Optional[str] = None
    label: str
    description: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    location_text: Optional[str] = None
    point_status: Optional[str] = "active"
    priority: Optional[str] = "normal"
    created_by_user_id: Optional[str] = "map-operator"

@router.get("/map-context/{disaster_event_id}")
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
                "with_coordinates_count": len([
                    p for p in points
                    if p.get("latitude") is not None and p.get("longitude") is not None
                ]),
            },
            "generated_at": datetime.utcnow().isoformat()
        }

@router.post("/map-points")
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
