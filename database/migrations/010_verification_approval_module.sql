-- Rescue-Net Migration 010
-- Verification & Approval module

BEGIN;

CREATE TABLE IF NOT EXISTS verification_actions (
  id TEXT PRIMARY KEY,
  disaster_event_id TEXT NOT NULL REFERENCES disaster_events(id) ON DELETE CASCADE,

  object_type TEXT NOT NULL,
  object_id TEXT NOT NULL,

  action_type TEXT NOT NULL DEFAULT 'verify',
  verification_status TEXT NOT NULL DEFAULT 'verified',
  trust_level TEXT,
  reviewed_by TEXT,
  reviewer_role TEXT,
  review_notes TEXT,

  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
  deleted_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_verification_actions_disaster
  ON verification_actions(disaster_event_id);

CREATE INDEX IF NOT EXISTS idx_verification_actions_object
  ON verification_actions(object_type, object_id);

COMMIT;
