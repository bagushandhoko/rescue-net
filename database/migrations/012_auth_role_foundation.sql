-- Rescue-Net Migration 012
-- Auth and Role foundation for prototype

BEGIN;

CREATE TABLE IF NOT EXISTS user_accounts (
  id TEXT PRIMARY KEY,
  username TEXT UNIQUE NOT NULL,
  display_name TEXT NOT NULL,
  phone TEXT,
  email TEXT,
  role TEXT NOT NULL DEFAULT 'viewer',
  organization_id TEXT,
  posko_id TEXT,
  status TEXT DEFAULT 'active',
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
  deleted_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_sessions (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES user_accounts(id) ON DELETE CASCADE,
  session_token TEXT UNIQUE NOT NULL,
  status TEXT DEFAULT 'active',
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  expires_at TIMESTAMP,
  deleted_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_user_accounts_role ON user_accounts(role);
CREATE INDEX IF NOT EXISTS idx_user_accounts_org ON user_accounts(organization_id);
CREATE INDEX IF NOT EXISTS idx_user_accounts_posko ON user_accounts(posko_id);
CREATE INDEX IF NOT EXISTS idx_user_sessions_token ON user_sessions(session_token);

INSERT INTO user_accounts
(id, username, display_name, phone, email, role, organization_id, posko_id, status)
VALUES
('user-command-demo', 'command', 'Command Center Demo', '081200000100', 'command@rescue-net.local', 'command_center', 'org-bpbd-aceh', NULL, 'active'),
('user-posko-logistik-demo', 'posko-logistik', 'Operator Posko Logistik', '081200000101', 'posko-logistik@rescue-net.local', 'posko_operator', 'org-bpbd-aceh', 'posko-logistik-aceh', 'active'),
('user-medical-demo', 'medical', 'Operator Posko Medis', '081200000102', 'medical@rescue-net.local', 'medical_operator', 'org-pmi', 'posko-medis-aceh', 'active'),
('user-shelter-demo', 'shelter', 'Operator Shelter', '081200000103', 'shelter@rescue-net.local', 'shelter_operator', NULL, 'posko-shelter-melati', 'active'),
('user-donor-demo', 'donor', 'Donor Demo', '081200000104', 'donor@rescue-net.local', 'donor', NULL, NULL, 'active'),
('user-volunteer-demo', 'volunteer', 'Volunteer Demo', '081200000105', 'volunteer@rescue-net.local', 'volunteer', NULL, NULL, 'active')
ON CONFLICT (username) DO NOTHING;

COMMIT;
