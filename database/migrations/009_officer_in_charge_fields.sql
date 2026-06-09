-- Rescue-Net Migration 009
-- Officer in Charge contact fields for operational coordination

BEGIN;

ALTER TABLE transport_spaces
  ADD COLUMN IF NOT EXISTS officer_in_charge_name TEXT,
  ADD COLUMN IF NOT EXISTS officer_in_charge_phone TEXT,
  ADD COLUMN IF NOT EXISTS officer_in_charge_role TEXT;

ALTER TABLE distribution_flows
  ADD COLUMN IF NOT EXISTS officer_in_charge_name TEXT,
  ADD COLUMN IF NOT EXISTS officer_in_charge_phone TEXT,
  ADD COLUMN IF NOT EXISTS officer_in_charge_role TEXT;

ALTER TABLE aid_offers
  ADD COLUMN IF NOT EXISTS officer_in_charge_name TEXT,
  ADD COLUMN IF NOT EXISTS officer_in_charge_phone TEXT,
  ADD COLUMN IF NOT EXISTS officer_in_charge_role TEXT;

ALTER TABLE posko_nodes
  ADD COLUMN IF NOT EXISTS officer_in_charge_name TEXT,
  ADD COLUMN IF NOT EXISTS officer_in_charge_phone TEXT,
  ADD COLUMN IF NOT EXISTS officer_in_charge_role TEXT;

COMMIT;
