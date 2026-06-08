-- Rescue-Net Migration 003
-- Kitchen / Dapur Umum Foundation

BEGIN;

CREATE TABLE IF NOT EXISTS kitchen_meal_productions (
  id TEXT PRIMARY KEY,
  disaster_event_id TEXT NOT NULL REFERENCES disaster_events(id) ON DELETE CASCADE,
  posko_id TEXT NOT NULL REFERENCES posko_nodes(id) ON DELETE CASCADE,

  meal_name TEXT NOT NULL,
  portions INTEGER NOT NULL,
  production_time TEXT,
  target_distribution_location TEXT,
  status TEXT DEFAULT 'prepared',

  ingredients_json JSONB DEFAULT '[]'::jsonb,
  notes TEXT,

  owner_type TEXT DEFAULT 'posko',
  owner_id TEXT,
  visibility_scope TEXT DEFAULT 'disaster_ecosystem',
  access_policy TEXT DEFAULT 'request_required',

  source_server_id TEXT,
  source_device_id TEXT,
  source_organization_id TEXT,
  source_posko_id TEXT,

  created_by_user_id TEXT,
  updated_by_user_id TEXT,

  verification_status TEXT DEFAULT 'self_reported',
  sync_status TEXT DEFAULT 'synced',
  version INTEGER DEFAULT 1,
  deleted_at TIMESTAMP,

  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_kitchen_meal_posko
  ON kitchen_meal_productions(posko_id);

CREATE INDEX IF NOT EXISTS idx_kitchen_meal_disaster
  ON kitchen_meal_productions(disaster_event_id);

COMMIT;
