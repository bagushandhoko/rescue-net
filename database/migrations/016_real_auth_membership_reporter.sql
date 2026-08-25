-- Rescue-Net Migration 016
-- P0: Real authentication, Kelompok (organization) membership, Posko assignment,
-- reporter profile/linkage.
--
-- Additive only. No DROP TABLE / DROP COLUMN / TRUNCATE.
-- Must be run as the `postgres` superuser (user_accounts/user_sessions are
-- owned by `postgres`; the app role `rescuenet_user` only has granted DML,
-- not ALTER/CREATE INDEX/REFERENCES rights on those tables).

BEGIN;

-- ---------------------------------------------------------------------
-- A. Real auth: password + refresh token support on existing tables
-- ---------------------------------------------------------------------

ALTER TABLE user_accounts ADD COLUMN IF NOT EXISTS password_hash TEXT;
ALTER TABLE user_accounts ADD COLUMN IF NOT EXISTS failed_login_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE user_accounts ADD COLUMN IF NOT EXISTS locked_until TIMESTAMP;
ALTER TABLE user_accounts ADD COLUMN IF NOT EXISTS last_login_at TIMESTAMP;

-- Email must be unique among active (non-deleted) accounts that have one,
-- without breaking existing rows that share/lack an email.
CREATE UNIQUE INDEX IF NOT EXISTS idx_user_accounts_email_unique
  ON user_accounts (lower(email))
  WHERE email IS NOT NULL AND deleted_at IS NULL;

ALTER TABLE user_sessions ADD COLUMN IF NOT EXISTS refresh_token_hash TEXT;
ALTER TABLE user_sessions ADD COLUMN IF NOT EXISTS refresh_expires_at TIMESTAMP;

CREATE INDEX IF NOT EXISTS idx_user_sessions_refresh
  ON user_sessions(refresh_token_hash);

-- ---------------------------------------------------------------------
-- B. Kelompok (organization) membership - additive relational model.
--    Does NOT replace user_accounts.organization_id (kept for compat).
-- ---------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS organization_memberships (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES user_accounts(id) ON DELETE CASCADE,
  organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  membership_role TEXT NOT NULL DEFAULT 'member',
  status TEXT NOT NULL DEFAULT 'pending',
  requested_at TIMESTAMP NOT NULL DEFAULT NOW(),
  approved_at TIMESTAMP,
  approved_by TEXT,
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
  UNIQUE(user_id, organization_id)
);

CREATE INDEX IF NOT EXISTS idx_org_memberships_user
  ON organization_memberships(user_id);
CREATE INDEX IF NOT EXISTS idx_org_memberships_org
  ON organization_memberships(organization_id, status);

-- ---------------------------------------------------------------------
-- C. Posko assignment - additive, separate from user_accounts.posko_id.
-- ---------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS posko_assignments (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES user_accounts(id) ON DELETE CASCADE,
  posko_id TEXT NOT NULL REFERENCES posko_nodes(id) ON DELETE CASCADE,
  role TEXT NOT NULL DEFAULT 'member',
  status TEXT NOT NULL DEFAULT 'pending',
  approved_by TEXT,
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
  UNIQUE(user_id, posko_id)
);

CREATE INDEX IF NOT EXISTS idx_posko_assignments_user
  ON posko_assignments(user_id);
CREATE INDEX IF NOT EXISTS idx_posko_assignments_posko
  ON posko_assignments(posko_id, status);

-- ---------------------------------------------------------------------
-- D. Reporter profile - relational reporter identity/contact, linkable
--    to community_reports. Legacy reporter_name/reporter_phone columns
--    on community_reports are kept untouched for dedupe compatibility.
-- ---------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS reporter_profiles (
  id TEXT PRIMARY KEY,
  user_id TEXT REFERENCES user_accounts(id) ON DELETE SET NULL,
  display_name TEXT NOT NULL,
  phone TEXT,
  email TEXT,
  preferred_contact_method TEXT NOT NULL DEFAULT 'whatsapp',
  organization_id TEXT REFERENCES organizations(id) ON DELETE SET NULL,
  consent_to_contact BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_reporter_profiles_user
  ON reporter_profiles(user_id);

ALTER TABLE community_reports ADD COLUMN IF NOT EXISTS reporter_profile_id TEXT;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'community_reports_reporter_profile_id_fkey'
  ) THEN
    ALTER TABLE community_reports
      ADD CONSTRAINT community_reports_reporter_profile_id_fkey
      FOREIGN KEY (reporter_profile_id) REFERENCES reporter_profiles(id) ON DELETE SET NULL;
  END IF;
END $$;

-- ---------------------------------------------------------------------
-- E. Grants: the running app connects as rescuenet_user. New tables are
--    created by the migration runner (postgres) and must be explicitly
--    opened for DML. Table-level grants on user_accounts/user_sessions
--    already cover the new columns added above (no action needed there).
-- ---------------------------------------------------------------------

GRANT SELECT, INSERT, UPDATE, DELETE ON organization_memberships TO rescuenet_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON posko_assignments TO rescuenet_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON reporter_profiles TO rescuenet_user;

COMMIT;
