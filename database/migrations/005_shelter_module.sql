-- Rescue-Net Migration 005
-- Shelter / Temporary Accommodation Foundation

BEGIN;

CREATE TABLE IF NOT EXISTS shelter_occupancies (
  id TEXT PRIMARY KEY,
  disaster_event_id TEXT NOT NULL REFERENCES disaster_events(id) ON DELETE CASCADE,
  posko_id TEXT NOT NULL REFERENCES posko_nodes(id) ON DELETE CASCADE,

  shelter_name TEXT NOT NULL,
  capacity_total INTEGER NOT NULL DEFAULT 0,
  current_occupancy INTEGER NOT NULL DEFAULT 0,

  families_count INTEGER DEFAULT 0,
  children_count INTEGER DEFAULT 0,
  elderly_count INTEGER DEFAULT 0,
  disabled_count INTEGER DEFAULT 0,

  sanitation_status TEXT DEFAULT 'unknown',
  water_status TEXT DEFAULT 'unknown',
  electricity_status TEXT DEFAULT 'unknown',
  safety_status TEXT DEFAULT 'unknown',

  notes TEXT,
  status TEXT DEFAULT 'active',

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

CREATE TABLE IF NOT EXISTS shelter_needs (
  id TEXT PRIMARY KEY,
  disaster_event_id TEXT NOT NULL REFERENCES disaster_events(id) ON DELETE CASCADE,
  posko_id TEXT NOT NULL REFERENCES posko_nodes(id) ON DELETE CASCADE,

  item_name TEXT NOT NULL,
  quantity_needed NUMERIC NOT NULL,
  unit TEXT NOT NULL,
  priority TEXT DEFAULT 'normal',
  needed_before TEXT,
  status TEXT DEFAULT 'open',
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

CREATE INDEX IF NOT EXISTS idx_shelter_occupancies_posko ON shelter_occupancies(posko_id);
CREATE INDEX IF NOT EXISTS idx_shelter_occupancies_disaster ON shelter_occupancies(disaster_event_id);
CREATE INDEX IF NOT EXISTS idx_shelter_needs_posko ON shelter_needs(posko_id);
CREATE INDEX IF NOT EXISTS idx_shelter_needs_disaster ON shelter_needs(disaster_event_id);

COMMIT;
