-- Rescue-Net Migration 004
-- Medical Post Foundation

BEGIN;

CREATE TABLE IF NOT EXISTS medical_cases (
  id TEXT PRIMARY KEY,
  disaster_event_id TEXT NOT NULL REFERENCES disaster_events(id) ON DELETE CASCADE,
  posko_id TEXT NOT NULL REFERENCES posko_nodes(id) ON DELETE CASCADE,

  patient_code TEXT NOT NULL,
  age_group TEXT,
  gender TEXT,
  complaint TEXT NOT NULL,
  severity TEXT DEFAULT 'minor',
  triage_status TEXT DEFAULT 'green',
  treatment_notes TEXT,
  referral_needed BOOLEAN DEFAULT FALSE,
  referral_destination TEXT,

  status TEXT DEFAULT 'treated',

  owner_type TEXT DEFAULT 'posko',
  owner_id TEXT,
  visibility_scope TEXT DEFAULT 'restricted_medical',
  access_policy TEXT DEFAULT 'medical_role_required',

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

CREATE TABLE IF NOT EXISTS medical_supply_uses (
  id TEXT PRIMARY KEY,
  disaster_event_id TEXT NOT NULL REFERENCES disaster_events(id) ON DELETE CASCADE,
  posko_id TEXT NOT NULL REFERENCES posko_nodes(id) ON DELETE CASCADE,
  medical_case_id TEXT REFERENCES medical_cases(id) ON DELETE SET NULL,

  item_name TEXT NOT NULL,
  quantity NUMERIC NOT NULL,
  unit TEXT NOT NULL,

  notes TEXT,

  owner_type TEXT DEFAULT 'posko',
  owner_id TEXT,
  visibility_scope TEXT DEFAULT 'restricted_medical',
  access_policy TEXT DEFAULT 'medical_role_required',

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

CREATE INDEX IF NOT EXISTS idx_medical_cases_posko ON medical_cases(posko_id);
CREATE INDEX IF NOT EXISTS idx_medical_cases_disaster ON medical_cases(disaster_event_id);
CREATE INDEX IF NOT EXISTS idx_medical_supply_uses_posko ON medical_supply_uses(posko_id);
CREATE INDEX IF NOT EXISTS idx_medical_supply_uses_case ON medical_supply_uses(medical_case_id);

COMMIT;
