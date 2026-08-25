-- Rescue-Net Migration 017
-- Registration role-request hardening.
-- Additive only. No DROP / TRUNCATE.

BEGIN;

ALTER TABLE user_accounts
  ADD COLUMN IF NOT EXISTS requested_role TEXT;

ALTER TABLE user_accounts
  ADD COLUMN IF NOT EXISTS role_request_status TEXT NOT NULL DEFAULT 'none';

CREATE INDEX IF NOT EXISTS idx_user_accounts_requested_role
  ON user_accounts(requested_role, role_request_status);

COMMIT;
