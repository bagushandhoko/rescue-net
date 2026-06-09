-- Rescue-Net Migration 006
-- Search & Found / Missing Person Foundation

BEGIN;

CREATE TABLE IF NOT EXISTS missing_person_reports (
  id TEXT PRIMARY KEY,
  disaster_event_id TEXT NOT NULL REFERENCES disaster_events(id) ON DELETE CASCADE,

  reporter_name TEXT,
  reporter_contact TEXT,
  reporter_relation TEXT,

  person_code TEXT NOT NULL,
  person_name TEXT,
  age_group TEXT,
  gender TEXT,
  last_seen_location TEXT,
  last_seen_time TEXT,
  description TEXT,
  clothing_description TEXT,
  special_notes TEXT,

  status TEXT DEFAULT 'missing',

  privacy_level TEXT DEFAULT 'restricted',
  visibility_scope TEXT DEFAULT 'disaster_ecosystem',
  access_policy TEXT DEFAULT 'search_found_role_required',

  source_posko_id TEXT,
  source_organization_id TEXT,
  source_device_id TEXT,
  source_server_id TEXT,

  created_by_user_id TEXT,
  updated_by_user_id TEXT,

  verification_status TEXT DEFAULT 'self_reported',
  sync_status TEXT DEFAULT 'synced',
  version INTEGER DEFAULT 1,
  deleted_at TIMESTAMP,

  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS found_person_reports (
  id TEXT PRIMARY KEY,
  disaster_event_id TEXT NOT NULL REFERENCES disaster_events(id) ON DELETE CASCADE,

  finder_name TEXT,
  finder_contact TEXT,

  person_code TEXT NOT NULL,
  person_name TEXT,
  age_group TEXT,
  gender TEXT,
  found_location TEXT,
  found_time TEXT,
  current_location TEXT,
  condition_notes TEXT,
  description TEXT,
  clothing_description TEXT,
  special_notes TEXT,

  status TEXT DEFAULT 'found',

  privacy_level TEXT DEFAULT 'restricted',
  visibility_scope TEXT DEFAULT 'disaster_ecosystem',
  access_policy TEXT DEFAULT 'search_found_role_required',

  source_posko_id TEXT,
  source_organization_id TEXT,
  source_device_id TEXT,
  source_server_id TEXT,

  created_by_user_id TEXT,
  updated_by_user_id TEXT,

  verification_status TEXT DEFAULT 'self_reported',
  sync_status TEXT DEFAULT 'synced',
  version INTEGER DEFAULT 1,
  deleted_at TIMESTAMP,

  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS search_found_matches (
  id TEXT PRIMARY KEY,
  disaster_event_id TEXT NOT NULL REFERENCES disaster_events(id) ON DELETE CASCADE,

  missing_report_id TEXT REFERENCES missing_person_reports(id) ON DELETE CASCADE,
  found_report_id TEXT REFERENCES found_person_reports(id) ON DELETE CASCADE,

  match_score NUMERIC DEFAULT 0,
  match_reason TEXT,
  status TEXT DEFAULT 'candidate',

  reviewed_by TEXT,
  reviewed_at TIMESTAMP,
  reunion_notes TEXT,

  privacy_level TEXT DEFAULT 'restricted',
  visibility_scope TEXT DEFAULT 'disaster_ecosystem',
  access_policy TEXT DEFAULT 'search_found_role_required',

  created_by_user_id TEXT,
  updated_by_user_id TEXT,

  verification_status TEXT DEFAULT 'self_reported',
  sync_status TEXT DEFAULT 'synced',
  version INTEGER DEFAULT 1,
  deleted_at TIMESTAMP,

  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_missing_person_disaster ON missing_person_reports(disaster_event_id);
CREATE INDEX IF NOT EXISTS idx_missing_person_status ON missing_person_reports(status);
CREATE INDEX IF NOT EXISTS idx_found_person_disaster ON found_person_reports(disaster_event_id);
CREATE INDEX IF NOT EXISTS idx_found_person_status ON found_person_reports(status);
CREATE INDEX IF NOT EXISTS idx_search_found_matches_disaster ON search_found_matches(disaster_event_id);
CREATE INDEX IF NOT EXISTS idx_search_found_matches_status ON search_found_matches(status);

COMMIT;
