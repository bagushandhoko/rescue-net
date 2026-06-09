-- Rescue-Net Migration 008
-- Volunteer Assignment and Work Tools Foundation

BEGIN;

CREATE TABLE IF NOT EXISTS volunteer_profiles (
  id TEXT PRIMARY KEY,
  disaster_event_id TEXT NOT NULL REFERENCES disaster_events(id) ON DELETE CASCADE,
  volunteer_name TEXT NOT NULL,
  contact TEXT,
  skill_tags TEXT,
  availability_status TEXT DEFAULT 'available',
  current_location TEXT,
  assigned_posko_id TEXT REFERENCES posko_nodes(id) ON DELETE SET NULL,
  verification_status TEXT DEFAULT 'self_reported',
  notes TEXT,
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
  deleted_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS volunteer_assignments (
  id TEXT PRIMARY KEY,
  disaster_event_id TEXT NOT NULL REFERENCES disaster_events(id) ON DELETE CASCADE,
  volunteer_id TEXT REFERENCES volunteer_profiles(id) ON DELETE CASCADE,
  assigned_to_type TEXT DEFAULT 'posko',
  assigned_to_id TEXT,
  task_name TEXT NOT NULL,
  task_description TEXT,
  priority TEXT DEFAULT 'normal',
  status TEXT DEFAULT 'assigned',
  created_by_user_id TEXT,
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
  deleted_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS work_tool_requests (
  id TEXT PRIMARY KEY,
  disaster_event_id TEXT NOT NULL REFERENCES disaster_events(id) ON DELETE CASCADE,
  requested_by_type TEXT DEFAULT 'posko',
  requested_by_id TEXT,
  tool_name TEXT NOT NULL,
  tool_type TEXT,
  quantity NUMERIC DEFAULT 1,
  unit TEXT DEFAULT 'unit',
  location TEXT,
  needed_for TEXT,
  priority TEXT DEFAULT 'normal',
  required_operator_skill TEXT,
  status TEXT DEFAULT 'requested',
  approved_by TEXT,
  assigned_resource_id TEXT,
  notes TEXT,
  created_by_user_id TEXT,
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
  deleted_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_volunteer_profiles_disaster ON volunteer_profiles(disaster_event_id);
CREATE INDEX IF NOT EXISTS idx_volunteer_assignments_disaster ON volunteer_assignments(disaster_event_id);
CREATE INDEX IF NOT EXISTS idx_work_tool_requests_disaster ON work_tool_requests(disaster_event_id);

COMMIT;
