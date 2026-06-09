-- Rescue-Net Migration 007
-- AI BYOK / Per User AI Key Settings

BEGIN;

CREATE TABLE IF NOT EXISTS ai_user_settings (
  id TEXT PRIMARY KEY,

  user_id TEXT NOT NULL,
  organization_id TEXT,
  provider TEXT NOT NULL DEFAULT 'openai',
  model_name TEXT DEFAULT 'gpt-4o-mini',

  encrypted_api_key TEXT NOT NULL,
  api_key_last4 TEXT,
  api_key_label TEXT,

  status TEXT DEFAULT 'active',

  owner_type TEXT DEFAULT 'user',
  owner_id TEXT,
  visibility_scope TEXT DEFAULT 'private',
  access_policy TEXT DEFAULT 'owner_only',

  created_by_user_id TEXT,
  updated_by_user_id TEXT,

  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP NOT NULL DEFAULT NOW(),

  UNIQUE(user_id, provider)
);

CREATE INDEX IF NOT EXISTS idx_ai_user_settings_user
  ON ai_user_settings(user_id);

CREATE INDEX IF NOT EXISTS idx_ai_user_settings_org
  ON ai_user_settings(organization_id);

COMMIT;
