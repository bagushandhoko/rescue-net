-- Rescue-Net Migration 015
-- Database-level audit triggers for core operational tables.

BEGIN;

CREATE OR REPLACE FUNCTION rn_audit_row_change()
RETURNS TRIGGER AS $$
DECLARE
  row_before JSONB;
  row_after JSONB;
  audit_object_id TEXT;
  audit_disaster_event_id TEXT;
  audit_actor_user_id TEXT;
BEGIN
  IF TG_OP = 'INSERT' THEN
    row_before := NULL;
    row_after := to_jsonb(NEW);
  ELSIF TG_OP = 'UPDATE' THEN
    row_before := to_jsonb(OLD);
    row_after := to_jsonb(NEW);
  ELSE
    row_before := to_jsonb(OLD);
    row_after := NULL;
  END IF;

  audit_object_id := COALESCE(row_after ->> 'id', row_before ->> 'id');
  audit_disaster_event_id := COALESCE(row_after ->> 'disaster_event_id', row_before ->> 'disaster_event_id');
  audit_actor_user_id := COALESCE(
    row_after ->> 'updated_by_user_id',
    row_after ->> 'created_by_user_id',
    row_after ->> 'uploaded_by',
    row_before ->> 'updated_by_user_id',
    row_before ->> 'created_by_user_id',
    row_before ->> 'uploaded_by'
  );

  INSERT INTO audit_events
  (id, disaster_event_id, actor_user_id, action, object_table, object_id, before_data, after_data)
  VALUES
  (
    'audit-' || md5(clock_timestamp()::text || random()::text),
    audit_disaster_event_id,
    audit_actor_user_id,
    lower(TG_OP),
    TG_TABLE_NAME,
    audit_object_id,
    row_before,
    row_after
  );

  IF TG_OP = 'DELETE' THEN
    RETURN OLD;
  END IF;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_audit_disaster_events ON disaster_events;
CREATE TRIGGER trg_audit_disaster_events
AFTER INSERT OR UPDATE OR DELETE ON disaster_events
FOR EACH ROW EXECUTE FUNCTION rn_audit_row_change();

DROP TRIGGER IF EXISTS trg_audit_logistic_needs ON logistic_needs;
CREATE TRIGGER trg_audit_logistic_needs
AFTER INSERT OR UPDATE OR DELETE ON logistic_needs
FOR EACH ROW EXECUTE FUNCTION rn_audit_row_change();

DROP TRIGGER IF EXISTS trg_audit_aid_offers ON aid_offers;
CREATE TRIGGER trg_audit_aid_offers
AFTER INSERT OR UPDATE OR DELETE ON aid_offers
FOR EACH ROW EXECUTE FUNCTION rn_audit_row_change();

DROP TRIGGER IF EXISTS trg_audit_distribution_flows ON distribution_flows;
CREATE TRIGGER trg_audit_distribution_flows
AFTER INSERT OR UPDATE OR DELETE ON distribution_flows
FOR EACH ROW EXECUTE FUNCTION rn_audit_row_change();

DROP TRIGGER IF EXISTS trg_audit_evidence_files ON evidence_files;
CREATE TRIGGER trg_audit_evidence_files
AFTER INSERT OR UPDATE OR DELETE ON evidence_files
FOR EACH ROW EXECUTE FUNCTION rn_audit_row_change();

DROP TRIGGER IF EXISTS trg_audit_resource_profiles ON resource_profiles;
CREATE TRIGGER trg_audit_resource_profiles
AFTER INSERT OR UPDATE OR DELETE ON resource_profiles
FOR EACH ROW EXECUTE FUNCTION rn_audit_row_change();

DROP TRIGGER IF EXISTS trg_audit_recovery_projects ON recovery_projects;
CREATE TRIGGER trg_audit_recovery_projects
AFTER INSERT OR UPDATE OR DELETE ON recovery_projects
FOR EACH ROW EXECUTE FUNCTION rn_audit_row_change();

DROP TRIGGER IF EXISTS trg_audit_recovery_project_updates ON recovery_project_updates;
CREATE TRIGGER trg_audit_recovery_project_updates
AFTER INSERT OR UPDATE OR DELETE ON recovery_project_updates
FOR EACH ROW EXECUTE FUNCTION rn_audit_row_change();

COMMIT;
