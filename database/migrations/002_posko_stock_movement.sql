-- Rescue-Net Migration 002
-- Posko Detail + Stock Movement Foundation

BEGIN;

CREATE TABLE IF NOT EXISTS stock_movements (
  id TEXT PRIMARY KEY,
  disaster_event_id TEXT NOT NULL REFERENCES disaster_events(id) ON DELETE CASCADE,
  posko_id TEXT NOT NULL REFERENCES posko_nodes(id) ON DELETE CASCADE,

  item_name TEXT NOT NULL,
  quantity NUMERIC NOT NULL,
  unit TEXT NOT NULL,

  movement_type TEXT NOT NULL,
  movement_direction TEXT NOT NULL,

  source_type TEXT,
  source_id TEXT,
  destination_type TEXT,
  destination_id TEXT,

  related_aid_offer_id TEXT REFERENCES aid_offers(id) ON DELETE SET NULL,
  related_distribution_flow_id TEXT REFERENCES distribution_flows(id) ON DELETE SET NULL,
  related_logistic_need_id TEXT REFERENCES logistic_needs(id) ON DELETE SET NULL,

  notes TEXT,
  evidence_file_id TEXT,

  owner_type TEXT DEFAULT 'posko',
  owner_id TEXT,
  visibility_scope TEXT DEFAULT 'disaster_ecosystem',
  access_policy TEXT DEFAULT 'request_required',

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

CREATE INDEX IF NOT EXISTS idx_stock_movements_posko
  ON stock_movements(posko_id);

CREATE INDEX IF NOT EXISTS idx_stock_movements_disaster
  ON stock_movements(disaster_event_id);

CREATE INDEX IF NOT EXISTS idx_stock_movements_item
  ON stock_movements(item_name);

CREATE INDEX IF NOT EXISTS idx_stock_movements_type
  ON stock_movements(movement_type);

COMMIT;
