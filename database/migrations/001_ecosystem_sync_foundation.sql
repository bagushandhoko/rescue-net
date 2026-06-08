
-- Rescue-Net Migration 001
-- Disaster Ecosystem Consolidation + Offline Sync Foundation

BEGIN;

-- =========================================================
-- 1. Standard ownership / visibility / sync columns
-- =========================================================

ALTER TABLE organizations
  ADD COLUMN IF NOT EXISTS owner_type TEXT DEFAULT 'organization',
  ADD COLUMN IF NOT EXISTS owner_id TEXT,
  ADD COLUMN IF NOT EXISTS visibility_scope TEXT DEFAULT 'disaster_ecosystem',
  ADD COLUMN IF NOT EXISTS access_policy TEXT DEFAULT 'request_required',
  ADD COLUMN IF NOT EXISTS source_server_id TEXT,
  ADD COLUMN IF NOT EXISTS source_device_id TEXT,
  ADD COLUMN IF NOT EXISTS source_organization_id TEXT,
  ADD COLUMN IF NOT EXISTS source_posko_id TEXT,
  ADD COLUMN IF NOT EXISTS created_by_user_id TEXT,
  ADD COLUMN IF NOT EXISTS updated_by_user_id TEXT,
  ADD COLUMN IF NOT EXISTS version INTEGER DEFAULT 1,
  ADD COLUMN IF NOT EXISTS sync_status TEXT DEFAULT 'synced',
  ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP;

ALTER TABLE posko_nodes
  ADD COLUMN IF NOT EXISTS owner_type TEXT DEFAULT 'organization',
  ADD COLUMN IF NOT EXISTS owner_id TEXT,
  ADD COLUMN IF NOT EXISTS visibility_scope TEXT DEFAULT 'disaster_ecosystem',
  ADD COLUMN IF NOT EXISTS access_policy TEXT DEFAULT 'request_required',
  ADD COLUMN IF NOT EXISTS source_server_id TEXT,
  ADD COLUMN IF NOT EXISTS source_device_id TEXT,
  ADD COLUMN IF NOT EXISTS source_organization_id TEXT,
  ADD COLUMN IF NOT EXISTS source_posko_id TEXT,
  ADD COLUMN IF NOT EXISTS created_by_user_id TEXT,
  ADD COLUMN IF NOT EXISTS updated_by_user_id TEXT,
  ADD COLUMN IF NOT EXISTS version INTEGER DEFAULT 1,
  ADD COLUMN IF NOT EXISTS sync_status TEXT DEFAULT 'synced',
  ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP;

ALTER TABLE volunteers
  ADD COLUMN IF NOT EXISTS owner_type TEXT DEFAULT 'registered_user',
  ADD COLUMN IF NOT EXISTS owner_id TEXT,
  ADD COLUMN IF NOT EXISTS visibility_scope TEXT DEFAULT 'disaster_ecosystem',
  ADD COLUMN IF NOT EXISTS access_policy TEXT DEFAULT 'request_required',
  ADD COLUMN IF NOT EXISTS source_server_id TEXT,
  ADD COLUMN IF NOT EXISTS source_device_id TEXT,
  ADD COLUMN IF NOT EXISTS source_organization_id TEXT,
  ADD COLUMN IF NOT EXISTS source_posko_id TEXT,
  ADD COLUMN IF NOT EXISTS created_by_user_id TEXT,
  ADD COLUMN IF NOT EXISTS updated_by_user_id TEXT,
  ADD COLUMN IF NOT EXISTS version INTEGER DEFAULT 1,
  ADD COLUMN IF NOT EXISTS sync_status TEXT DEFAULT 'synced',
  ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP;

ALTER TABLE logistic_needs
  ADD COLUMN IF NOT EXISTS owner_type TEXT DEFAULT 'posko',
  ADD COLUMN IF NOT EXISTS owner_id TEXT,
  ADD COLUMN IF NOT EXISTS visibility_scope TEXT DEFAULT 'disaster_ecosystem',
  ADD COLUMN IF NOT EXISTS access_policy TEXT DEFAULT 'request_required',
  ADD COLUMN IF NOT EXISTS source_server_id TEXT,
  ADD COLUMN IF NOT EXISTS source_device_id TEXT,
  ADD COLUMN IF NOT EXISTS source_organization_id TEXT,
  ADD COLUMN IF NOT EXISTS source_posko_id TEXT,
  ADD COLUMN IF NOT EXISTS created_by_user_id TEXT,
  ADD COLUMN IF NOT EXISTS updated_by_user_id TEXT,
  ADD COLUMN IF NOT EXISTS version INTEGER DEFAULT 1,
  ADD COLUMN IF NOT EXISTS sync_status TEXT DEFAULT 'synced',
  ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP;

ALTER TABLE aid_offers
  ADD COLUMN IF NOT EXISTS owner_type TEXT DEFAULT 'personal_guest',
  ADD COLUMN IF NOT EXISTS owner_id TEXT,
  ADD COLUMN IF NOT EXISTS visibility_scope TEXT DEFAULT 'disaster_ecosystem',
  ADD COLUMN IF NOT EXISTS access_policy TEXT DEFAULT 'request_required',
  ADD COLUMN IF NOT EXISTS source_server_id TEXT,
  ADD COLUMN IF NOT EXISTS source_device_id TEXT,
  ADD COLUMN IF NOT EXISTS source_organization_id TEXT,
  ADD COLUMN IF NOT EXISTS source_posko_id TEXT,
  ADD COLUMN IF NOT EXISTS created_by_user_id TEXT,
  ADD COLUMN IF NOT EXISTS updated_by_user_id TEXT,
  ADD COLUMN IF NOT EXISTS version INTEGER DEFAULT 1,
  ADD COLUMN IF NOT EXISTS sync_status TEXT DEFAULT 'synced',
  ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP;

ALTER TABLE transport_spaces
  ADD COLUMN IF NOT EXISTS owner_type TEXT DEFAULT 'organization',
  ADD COLUMN IF NOT EXISTS owner_id TEXT,
  ADD COLUMN IF NOT EXISTS visibility_scope TEXT DEFAULT 'disaster_ecosystem',
  ADD COLUMN IF NOT EXISTS access_policy TEXT DEFAULT 'owner_approval_required',
  ADD COLUMN IF NOT EXISTS source_server_id TEXT,
  ADD COLUMN IF NOT EXISTS source_device_id TEXT,
  ADD COLUMN IF NOT EXISTS source_organization_id TEXT,
  ADD COLUMN IF NOT EXISTS source_posko_id TEXT,
  ADD COLUMN IF NOT EXISTS created_by_user_id TEXT,
  ADD COLUMN IF NOT EXISTS updated_by_user_id TEXT,
  ADD COLUMN IF NOT EXISTS version INTEGER DEFAULT 1,
  ADD COLUMN IF NOT EXISTS sync_status TEXT DEFAULT 'synced',
  ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP;

ALTER TABLE distribution_flows
  ADD COLUMN IF NOT EXISTS owner_type TEXT DEFAULT 'system',
  ADD COLUMN IF NOT EXISTS owner_id TEXT,
  ADD COLUMN IF NOT EXISTS visibility_scope TEXT DEFAULT 'disaster_ecosystem',
  ADD COLUMN IF NOT EXISTS access_policy TEXT DEFAULT 'command_center_assign',
  ADD COLUMN IF NOT EXISTS source_server_id TEXT,
  ADD COLUMN IF NOT EXISTS source_device_id TEXT,
  ADD COLUMN IF NOT EXISTS source_organization_id TEXT,
  ADD COLUMN IF NOT EXISTS source_posko_id TEXT,
  ADD COLUMN IF NOT EXISTS created_by_user_id TEXT,
  ADD COLUMN IF NOT EXISTS updated_by_user_id TEXT,
  ADD COLUMN IF NOT EXISTS version INTEGER DEFAULT 1,
  ADD COLUMN IF NOT EXISTS sync_status TEXT DEFAULT 'synced',
  ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP;

ALTER TABLE evidence_files
  ADD COLUMN IF NOT EXISTS owner_type TEXT DEFAULT 'registered_user',
  ADD COLUMN IF NOT EXISTS owner_id TEXT,
  ADD COLUMN IF NOT EXISTS visibility_scope TEXT DEFAULT 'restricted',
  ADD COLUMN IF NOT EXISTS access_policy TEXT DEFAULT 'request_required',
  ADD COLUMN IF NOT EXISTS source_server_id TEXT,
  ADD COLUMN IF NOT EXISTS source_device_id TEXT,
  ADD COLUMN IF NOT EXISTS source_organization_id TEXT,
  ADD COLUMN IF NOT EXISTS source_posko_id TEXT,
  ADD COLUMN IF NOT EXISTS created_by_user_id TEXT,
  ADD COLUMN IF NOT EXISTS updated_by_user_id TEXT,
  ADD COLUMN IF NOT EXISTS version INTEGER DEFAULT 1,
  ADD COLUMN IF NOT EXISTS sync_status TEXT DEFAULT 'synced',
  ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP;

-- =========================================================
-- 2. Server and device registry
-- =========================================================

CREATE TABLE IF NOT EXISTS servers (
  id TEXT PRIMARY KEY,
  server_name TEXT NOT NULL,
  server_type TEXT NOT NULL,
  owner_organization_id TEXT,
  region TEXT,
  base_url TEXT,
  public_key TEXT,
  trust_level TEXT DEFAULT 'self_reported',
  status TEXT DEFAULT 'active',
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS devices (
  id TEXT PRIMARY KEY,
  device_name TEXT NOT NULL,
  device_type TEXT NOT NULL,
  owner_user_id TEXT,
  owner_organization_id TEXT,
  last_seen_at TIMESTAMP,
  public_key TEXT,
  status TEXT DEFAULT 'active',
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- =========================================================
-- 3. Disaster ecosystem membership
-- =========================================================

CREATE TABLE IF NOT EXISTS disaster_ecosystem_members (
  id TEXT PRIMARY KEY,
  disaster_event_id TEXT NOT NULL REFERENCES disaster_events(id) ON DELETE CASCADE,
  member_type TEXT NOT NULL,
  member_id TEXT NOT NULL,
  role_in_disaster TEXT NOT NULL,
  joined_at TIMESTAMP NOT NULL DEFAULT NOW(),
  verification_status TEXT DEFAULT 'self_reported',
  trust_level TEXT DEFAULT 'self_reported',
  permissions_json JSONB DEFAULT '{}'::jsonb,
  status TEXT DEFAULT 'active',
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ecosystem_members_event
  ON disaster_ecosystem_members(disaster_event_id);

CREATE INDEX IF NOT EXISTS idx_ecosystem_members_member
  ON disaster_ecosystem_members(member_type, member_id);

-- =========================================================
-- 4. Shared resource model
-- =========================================================

CREATE TABLE IF NOT EXISTS resources (
  id TEXT PRIMARY KEY,
  disaster_event_id TEXT NOT NULL REFERENCES disaster_events(id) ON DELETE CASCADE,
  resource_type TEXT NOT NULL,
  owner_type TEXT NOT NULL,
  owner_id TEXT NOT NULL,
  name TEXT NOT NULL,
  description TEXT,
  capacity_json JSONB DEFAULT '{}'::jsonb,
  location TEXT,
  status TEXT DEFAULT 'available',
  visibility_scope TEXT DEFAULT 'disaster_ecosystem',
  access_policy TEXT DEFAULT 'request_required',
  verification_status TEXT DEFAULT 'self_reported',
  trust_level TEXT DEFAULT 'self_reported',
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_resources_event
  ON resources(disaster_event_id);

CREATE INDEX IF NOT EXISTS idx_resources_type
  ON resources(resource_type);

CREATE TABLE IF NOT EXISTS resource_shares (
  id TEXT PRIMARY KEY,
  resource_id TEXT NOT NULL REFERENCES resources(id) ON DELETE CASCADE,
  shared_by_owner_id TEXT,
  shared_to_scope TEXT DEFAULT 'disaster_ecosystem',
  shared_to_organization_id TEXT,
  disaster_event_id TEXT NOT NULL REFERENCES disaster_events(id) ON DELETE CASCADE,
  access_policy TEXT DEFAULT 'request_required',
  valid_from TIMESTAMP,
  valid_until TIMESTAMP,
  status TEXT DEFAULT 'active',
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS resource_requests (
  id TEXT PRIMARY KEY,
  resource_id TEXT NOT NULL REFERENCES resources(id) ON DELETE CASCADE,
  requested_by_type TEXT NOT NULL,
  requested_by_id TEXT NOT NULL,
  request_reason TEXT,
  related_need_id TEXT,
  related_distribution_flow_id TEXT,
  requested_quantity NUMERIC,
  requested_time TEXT,
  status TEXT DEFAULT 'requested',
  approved_by TEXT,
  approved_at TIMESTAMP,
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS resource_assignments (
  id TEXT PRIMARY KEY,
  resource_id TEXT NOT NULL REFERENCES resources(id) ON DELETE CASCADE,
  assigned_to_type TEXT NOT NULL,
  assigned_to_id TEXT NOT NULL,
  assigned_by TEXT,
  related_need_id TEXT,
  related_distribution_flow_id TEXT,
  assigned_quantity NUMERIC,
  assignment_notes TEXT,
  status TEXT DEFAULT 'assigned',
  assigned_at TIMESTAMP NOT NULL DEFAULT NOW(),
  completed_at TIMESTAMP,
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- =========================================================
-- 5. Coordination channels
-- =========================================================

CREATE TABLE IF NOT EXISTS coordination_channels (
  id TEXT PRIMARY KEY,
  disaster_event_id TEXT NOT NULL REFERENCES disaster_events(id) ON DELETE CASCADE,
  channel_name TEXT NOT NULL,
  channel_type TEXT NOT NULL,
  visibility_scope TEXT DEFAULT 'disaster_ecosystem',
  access_policy TEXT DEFAULT 'request_required',
  created_by TEXT,
  status TEXT DEFAULT 'active',
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS coordination_messages (
  id TEXT PRIMARY KEY,
  channel_id TEXT NOT NULL REFERENCES coordination_channels(id) ON DELETE CASCADE,
  sender_type TEXT NOT NULL,
  sender_id TEXT NOT NULL,
  message_text TEXT NOT NULL,
  related_object_type TEXT,
  related_object_id TEXT,
  visibility_scope TEXT DEFAULT 'disaster_ecosystem',
  created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- =========================================================
-- 6. Offline sync and audit
-- =========================================================

CREATE TABLE IF NOT EXISTS sync_events (
  id TEXT PRIMARY KEY,
  event_id TEXT UNIQUE NOT NULL,
  object_type TEXT NOT NULL,
  object_id TEXT NOT NULL,
  operation TEXT NOT NULL,
  payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  source_server_id TEXT,
  source_device_id TEXT,
  source_user_id TEXT,
  source_organization_id TEXT,
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  received_at TIMESTAMP NOT NULL DEFAULT NOW(),
  event_hash TEXT,
  previous_event_hash TEXT,
  sync_batch_id TEXT,
  verification_status TEXT DEFAULT 'unverified',
  apply_status TEXT DEFAULT 'pending'
);

CREATE INDEX IF NOT EXISTS idx_sync_events_object
  ON sync_events(object_type, object_id);

CREATE INDEX IF NOT EXISTS idx_sync_events_source
  ON sync_events(source_server_id, source_device_id);

CREATE TABLE IF NOT EXISTS sync_batches (
  id TEXT PRIMARY KEY,
  source_server_id TEXT,
  target_server_id TEXT,
  started_at TIMESTAMP NOT NULL DEFAULT NOW(),
  completed_at TIMESTAMP,
  event_count INTEGER DEFAULT 0,
  status TEXT DEFAULT 'started',
  checksum TEXT
);

CREATE TABLE IF NOT EXISTS sync_conflicts (
  id TEXT PRIMARY KEY,
  object_type TEXT NOT NULL,
  object_id TEXT NOT NULL,
  local_version INTEGER,
  incoming_version INTEGER,
  local_payload JSONB,
  incoming_payload JSONB,
  conflict_type TEXT NOT NULL,
  resolution_status TEXT DEFAULT 'open',
  resolved_by TEXT,
  resolved_at TIMESTAMP,
  created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS audit_logs (
  id TEXT PRIMARY KEY,
  actor_type TEXT,
  actor_id TEXT,
  action TEXT NOT NULL,
  object_type TEXT NOT NULL,
  object_id TEXT NOT NULL,
  before_json JSONB,
  after_json JSONB,
  source_server_id TEXT,
  source_device_id TEXT,
  disaster_event_id TEXT,
  created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

COMMIT;
