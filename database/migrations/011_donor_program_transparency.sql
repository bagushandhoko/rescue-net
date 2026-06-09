-- Rescue-Net Migration 011
-- Donor Program / Transparency module

BEGIN;

CREATE TABLE IF NOT EXISTS donor_programs (
  id TEXT PRIMARY KEY,
  disaster_event_id TEXT NOT NULL REFERENCES disaster_events(id) ON DELETE CASCADE,

  program_name TEXT NOT NULL,
  program_type TEXT DEFAULT 'general_relief',
  owner_type TEXT DEFAULT 'organization',
  owner_id TEXT,
  target_description TEXT,
  target_amount NUMERIC DEFAULT 0,
  target_unit TEXT DEFAULT 'IDR',
  current_amount NUMERIC DEFAULT 0,
  status TEXT DEFAULT 'active',
  location TEXT,
  contact_person TEXT,
  contact_phone TEXT,
  notes TEXT,

  created_by_user_id TEXT,
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
  deleted_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS donor_program_updates (
  id TEXT PRIMARY KEY,
  program_id TEXT NOT NULL REFERENCES donor_programs(id) ON DELETE CASCADE,
  disaster_event_id TEXT NOT NULL REFERENCES disaster_events(id) ON DELETE CASCADE,

  update_title TEXT NOT NULL,
  update_type TEXT DEFAULT 'progress',
  amount_used NUMERIC DEFAULT 0,
  amount_unit TEXT DEFAULT 'IDR',
  description TEXT,
  evidence_file_id TEXT,
  created_by_user_id TEXT,

  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
  deleted_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_donor_programs_disaster ON donor_programs(disaster_event_id);
CREATE INDEX IF NOT EXISTS idx_donor_program_updates_program ON donor_program_updates(program_id);
CREATE INDEX IF NOT EXISTS idx_donor_program_updates_disaster ON donor_program_updates(disaster_event_id);

COMMIT;
