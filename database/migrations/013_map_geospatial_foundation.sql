-- Rescue-Net Migration 013
-- Map / Geospatial foundation

BEGIN;

CREATE TABLE IF NOT EXISTS map_points (
  id TEXT PRIMARY KEY,
  disaster_event_id TEXT NOT NULL REFERENCES disaster_events(id) ON DELETE CASCADE,

  object_type TEXT NOT NULL,
  object_id TEXT,
  label TEXT NOT NULL,
  description TEXT,

  latitude NUMERIC,
  longitude NUMERIC,
  location_text TEXT,

  point_status TEXT DEFAULT 'active',
  priority TEXT DEFAULT 'normal',

  created_by_user_id TEXT,
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
  deleted_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_map_points_disaster ON map_points(disaster_event_id);
CREATE INDEX IF NOT EXISTS idx_map_points_object ON map_points(object_type, object_id);
CREATE INDEX IF NOT EXISTS idx_map_points_status ON map_points(point_status);

COMMIT;
