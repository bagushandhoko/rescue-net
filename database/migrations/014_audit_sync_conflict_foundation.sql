-- Rescue-Net Migration 014
-- Audit log foundation; sync_conflicts already exists in the live database.

BEGIN;

CREATE TABLE IF NOT EXISTS audit_events (
  id TEXT PRIMARY KEY,
  disaster_event_id TEXT,
  actor_user_id TEXT,
  actor_role TEXT,
  actor_display_name TEXT,
  action TEXT NOT NULL,
  object_table TEXT NOT NULL,
  object_id TEXT,
  before_data JSONB,
  after_data JSONB,
  ip_address TEXT,
  user_agent TEXT,
  source_device_id TEXT,
  source_server_id TEXT,
  created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_events_disaster
  ON audit_events(disaster_event_id);

CREATE INDEX IF NOT EXISTS idx_audit_events_object
  ON audit_events(object_table, object_id);

CREATE INDEX IF NOT EXISTS idx_audit_events_actor
  ON audit_events(actor_user_id, actor_role);

CREATE INDEX IF NOT EXISTS idx_audit_events_created
  ON audit_events(created_at DESC);

COMMIT;
