#!/bin/sh
set -u

API="${RN_API:-http://127.0.0.1:8092}"
EVENT_ID="${EVENT_ID:-event-sim-001}"

echo "===================================================="
echo " Rescue-Net Full Simulation FIXED"
echo " API      : $API"
echo " EVENT_ID : $EVENT_ID"
echo "===================================================="

call() {
  METHOD="$1"
  API_PATH="$2"
  DATA="${3:-}"

  echo ""
  echo "---- $METHOD $API_PATH ----"

  if [ "$METHOD" = "GET" ]; then
    curl -sS "$API$API_PATH"
  else
    curl -sS -X "$METHOD" "$API$API_PATH" \
      -H "Content-Type: application/json" \
      -d "$DATA"
  fi

  echo ""
}

echo ""
echo "== 0. Health =="
call GET "/health"

echo ""
echo "== 1. Seed base data by SQL =="
sudo docker exec -i postgres-main psql -U postgres -d rescuenet_db <<SQL
INSERT INTO disaster_events
(id, name, disaster_type, location, status, severity)
VALUES
('$EVENT_ID', 'Simulasi Gempa Rescue-Net 001', 'earthquake', 'Aceh Barat Simulation Zone', 'active', 'critical')
ON CONFLICT (id) DO UPDATE SET
  name = EXCLUDED.name,
  disaster_type = EXCLUDED.disaster_type,
  location = EXCLUDED.location,
  status = EXCLUDED.status,
  severity = EXCLUDED.severity;

INSERT INTO organizations
(id, name, organization_type, trust_level, status,
 owner_type, owner_id, visibility_scope, access_policy, sync_status, version)
VALUES
('org-sim-bpbd', 'BPBD Simulation', 'government', 'official', 'verified',
 'organization', 'org-sim-bpbd', 'disaster_ecosystem', 'request_required', 'synced', 1),
('org-sim-pmi', 'PMI Simulation', 'ngo', 'trusted', 'verified',
 'organization', 'org-sim-pmi', 'disaster_ecosystem', 'request_required', 'synced', 1),
('org-sim-tni', 'TNI Simulation', 'government', 'official', 'verified',
 'organization', 'org-sim-tni', 'disaster_ecosystem', 'request_required', 'synced', 1)
ON CONFLICT (id) DO UPDATE SET
  name = EXCLUDED.name,
  organization_type = EXCLUDED.organization_type,
  trust_level = EXCLUDED.trust_level,
  status = EXCLUDED.status,
  owner_type = EXCLUDED.owner_type,
  owner_id = EXCLUDED.owner_id,
  visibility_scope = EXCLUDED.visibility_scope,
  access_policy = EXCLUDED.access_policy,
  sync_status = EXCLUDED.sync_status,
  version = EXCLUDED.version;

INSERT INTO posko_nodes
(id, disaster_event_id, organization_id, name, node_type, location,
 verification_status, operational_status,
 owner_type, owner_id, visibility_scope, access_policy, sync_status, version)
VALUES
('posko-sim-logistik', '$EVENT_ID', 'org-sim-bpbd',
 'Posko Logistik Simulasi', 'logistics', 'Gudang Utama Simulasi',
 'official_verified', 'active',
 'organization', 'org-sim-bpbd', 'disaster_ecosystem', 'request_required', 'synced', 1),

('posko-sim-dapur', '$EVENT_ID', NULL,
 'Dapur Umum Simulasi', 'kitchen', 'Gang Simulasi',
 'community_verified', 'active',
 'posko', 'posko-sim-dapur', 'disaster_ecosystem', 'request_required', 'synced', 1),

('posko-sim-medis', '$EVENT_ID', 'org-sim-pmi',
 'Posko Medis Simulasi', 'medical', 'Klinik Simulasi',
 'official_verified', 'active',
 'organization', 'org-sim-pmi', 'disaster_ecosystem', 'request_required', 'synced', 1),

('posko-sim-shelter', '$EVENT_ID', NULL,
 'Shelter Simulasi', 'shelter', 'Sekolah Simulasi',
 'community_verified', 'active',
 'posko', 'posko-sim-shelter', 'disaster_ecosystem', 'request_required', 'synced', 1)
ON CONFLICT (id) DO UPDATE SET
  disaster_event_id = EXCLUDED.disaster_event_id,
  organization_id = EXCLUDED.organization_id,
  name = EXCLUDED.name,
  node_type = EXCLUDED.node_type,
  location = EXCLUDED.location,
  verification_status = EXCLUDED.verification_status,
  operational_status = EXCLUDED.operational_status,
  owner_type = EXCLUDED.owner_type,
  owner_id = EXCLUDED.owner_id,
  visibility_scope = EXCLUDED.visibility_scope,
  access_policy = EXCLUDED.access_policy,
  sync_status = EXCLUDED.sync_status,
  version = EXCLUDED.version;

INSERT INTO disaster_ecosystem_members
(id, disaster_event_id, member_type, member_id, role_in_disaster,
 verification_status, trust_level, permissions_json, status)
VALUES
('eco-sim-bpbd', '$EVENT_ID', 'organization', 'org-sim-bpbd', 'command',
 'official_verified', 'official', '{}'::jsonb, 'active'),
('eco-sim-pmi', '$EVENT_ID', 'organization', 'org-sim-pmi', 'medical',
 'official_verified', 'trusted', '{}'::jsonb, 'active'),
('eco-sim-tni', '$EVENT_ID', 'organization', 'org-sim-tni', 'transport',
 'official_verified', 'official', '{}'::jsonb, 'active'),
('eco-sim-logistik', '$EVENT_ID', 'posko', 'posko-sim-logistik', 'logistics',
 'official_verified', 'official', '{}'::jsonb, 'active'),
('eco-sim-dapur', '$EVENT_ID', 'posko', 'posko-sim-dapur', 'kitchen',
 'community_verified', 'local_trusted', '{}'::jsonb, 'active'),
('eco-sim-shelter', '$EVENT_ID', 'posko', 'posko-sim-shelter', 'shelter',
 'community_verified', 'local_trusted', '{}'::jsonb, 'active')
ON CONFLICT (id) DO UPDATE SET
  disaster_event_id = EXCLUDED.disaster_event_id,
  member_type = EXCLUDED.member_type,
  member_id = EXCLUDED.member_id,
  role_in_disaster = EXCLUDED.role_in_disaster,
  verification_status = EXCLUDED.verification_status,
  trust_level = EXCLUDED.trust_level,
  permissions_json = EXCLUDED.permissions_json,
  status = EXCLUDED.status;
SQL

echo ""
echo "== 2. Verify base seed =="
call GET "/poskos"
call GET "/ai/context/$EVENT_ID"

echo ""
echo "== 3. Stock masuk =="
call POST "/stock-movements" "{
  \"disaster_event_id\": \"$EVENT_ID\",
  \"posko_id\": \"posko-sim-logistik\",
  \"item_name\": \"Air Mineral\",
  \"quantity\": 200,
  \"unit\": \"dus\",
  \"movement_type\": \"stock_in\",
  \"movement_direction\": \"in\",
  \"source_type\": \"simulation_seed\",
  \"source_id\": \"seed-stock-water\",
  \"notes\": \"Stok awal simulasi.\"
}"

call POST "/stock-movements" "{
  \"disaster_event_id\": \"$EVENT_ID\",
  \"posko_id\": \"posko-sim-medis\",
  \"item_name\": \"Paracetamol\",
  \"quantity\": 100,
  \"unit\": \"strip\",
  \"movement_type\": \"stock_in\",
  \"movement_direction\": \"in\",
  \"source_type\": \"simulation_seed\",
  \"source_id\": \"seed-stock-medical\",
  \"notes\": \"Stok obat awal simulasi.\"
}"

echo ""
echo "== 4. Public aid donor =="
call POST "/public/aid-offers" "{
  \"disaster_event_id\": \"$EVENT_ID\",
  \"donor_name\": \"Donor Simulasi\",
  \"donor_contact\": \"0800000000\",
  \"donor_type\": \"personal_guest\",
  \"item_name\": \"Beras\",
  \"quantity\": 50,
  \"unit\": \"karung\",
  \"pickup_location\": \"Kota Simulasi\",
  \"ready_at\": \"Hari ini 15:00\",
  \"delivery_mode\": \"need_pickup\",
  \"target_node_id\": \"posko-sim-logistik\",
  \"target_node_name\": \"Posko Logistik Simulasi\",
  \"notes\": \"Simulasi bantuan publik.\"
}"

echo ""
echo "== 5. Logistic need =="
call POST "/logistic-needs" "{
  \"disaster_event_id\": \"$EVENT_ID\",
  \"node_id\": \"posko-sim-shelter\",
  \"item_name\": \"Selimut\",
  \"quantity_needed\": 150,
  \"unit\": \"pcs\",
  \"priority\": \"urgent\",
  \"needed_before\": \"Besok pagi\",
  \"status\": \"open\"
}"

echo ""
echo "== 6. Transfer stock logistik ke dapur dan shelter =="
call POST "/stock-transfer" "{
  \"disaster_event_id\": \"$EVENT_ID\",
  \"source_posko_id\": \"posko-sim-logistik\",
  \"destination_posko_id\": \"posko-sim-dapur\",
  \"item_name\": \"Air Mineral\",
  \"quantity\": 30,
  \"unit\": \"dus\",
  \"notes\": \"Transfer air ke dapur umum simulasi.\"
}"

call POST "/stock-transfer" "{
  \"disaster_event_id\": \"$EVENT_ID\",
  \"source_posko_id\": \"posko-sim-logistik\",
  \"destination_posko_id\": \"posko-sim-shelter\",
  \"item_name\": \"Air Mineral\",
  \"quantity\": 40,
  \"unit\": \"dus\",
  \"notes\": \"Transfer air ke shelter simulasi.\"
}"

echo ""
echo "== 7. Dapur umum produksi makanan =="
call POST "/kitchen-meal-production" "{
  \"disaster_event_id\": \"$EVENT_ID\",
  \"posko_id\": \"posko-sim-dapur\",
  \"meal_name\": \"Nasi Bungkus Simulasi\",
  \"portions\": 120,
  \"production_time\": \"Hari ini sore\",
  \"target_distribution_location\": \"Shelter Simulasi\",
  \"ingredients\": [
    {\"item_name\": \"Air Mineral\", \"quantity\": 2, \"unit\": \"dus\"}
  ],
  \"notes\": \"Produksi dapur umum simulasi.\"
}"

echo ""
echo "== 8. Posko medis: case + supply use =="
MED_CASE_RESPONSE=$(curl -sS -X POST "$API/medical-cases" \
  -H "Content-Type: application/json" \
  -d "{
    \"disaster_event_id\": \"$EVENT_ID\",
    \"posko_id\": \"posko-sim-medis\",
    \"patient_code\": \"SIM-PAT-001\",
    \"age_group\": \"adult\",
    \"gender\": \"unknown\",
    \"complaint\": \"Demam setelah evakuasi\",
    \"severity\": \"minor\",
    \"triage_status\": \"green\",
    \"treatment_notes\": \"Diberi obat dan istirahat.\",
    \"referral_needed\": false,
    \"status\": \"treated\"
  }")
echo "$MED_CASE_RESPONSE"

MED_CASE_ID=$(echo "$MED_CASE_RESPONSE" | python3 -c 'import sys,json; d=json.load(sys.stdin); print((d.get("id") or d.get("medical_case",{}).get("id") or d.get("data",{}).get("id") or ""))' 2>/dev/null || true)

echo "MED_CASE_ID=$MED_CASE_ID"
if [ -n "$MED_CASE_ID" ]; then
  call POST "/medical-supply-use" "{
    \"disaster_event_id\": \"$EVENT_ID\",
    \"posko_id\": \"posko-sim-medis\",
    \"medical_case_id\": \"$MED_CASE_ID\",
    \"item_name\": \"Paracetamol\",
    \"quantity\": 1,
    \"unit\": \"strip\",
    \"notes\": \"Diberikan untuk pasien demam.\"
  }"
else
  echo "WARN: medical case id not found, skip medical supply use"
fi

echo ""
echo "== 9. Shelter occupancy + needs =="
call POST "/shelter-occupancy" "{
  \"disaster_event_id\": \"$EVENT_ID\",
  \"posko_id\": \"posko-sim-shelter\",
  \"shelter_name\": \"Shelter Simulasi\",
  \"capacity_total\": 200,
  \"current_occupancy\": 185,
  \"families_count\": 55,
  \"children_count\": 48,
  \"elderly_count\": 16,
  \"disabled_count\": 4,
  \"sanitation_status\": \"limited\",
  \"water_status\": \"needs_supply\",
  \"electricity_status\": \"partial\",
  \"safety_status\": \"safe\",
  \"notes\": \"Shelter hampir penuh.\"
}"

call POST "/shelter-needs" "{
  \"disaster_event_id\": \"$EVENT_ID\",
  \"posko_id\": \"posko-sim-shelter\",
  \"item_name\": \"Selimut\",
  \"quantity_needed\": 150,
  \"unit\": \"pcs\",
  \"priority\": \"urgent\",
  \"needed_before\": \"Besok pagi\",
  \"notes\": \"Untuk anak-anak dan lansia.\"
}"

echo ""
echo "== 10. Search & Found =="
MISSING_RESPONSE=$(curl -sS -X POST "$API/missing-person-reports" \
  -H "Content-Type: application/json" \
  -d "{
    \"disaster_event_id\": \"$EVENT_ID\",
    \"reporter_name\": \"Keluarga Simulasi\",
    \"reporter_contact\": \"0800000001\",
    \"reporter_relation\": \"keluarga\",
    \"person_code\": \"SIM-MP-001\",
    \"person_name\": \"Anonim Simulasi\",
    \"age_group\": \"adult\",
    \"gender\": \"unknown\",
    \"last_seen_location\": \"Pasar Simulasi\",
    \"last_seen_time\": \"Kemarin sore\",
    \"description\": \"Terpisah saat evakuasi\",
    \"clothing_description\": \"Baju gelap\",
    \"special_notes\": \"Restricted data.\"
  }")
echo "$MISSING_RESPONSE"
MISSING_ID=$(echo "$MISSING_RESPONSE" | python3 -c 'import sys,json; d=json.load(sys.stdin); print((d.get("id") or d.get("missing_report",{}).get("id") or d.get("data",{}).get("id") or ""))' 2>/dev/null || true)

FOUND_RESPONSE=$(curl -sS -X POST "$API/found-person-reports" \
  -H "Content-Type: application/json" \
  -d "{
    \"disaster_event_id\": \"$EVENT_ID\",
    \"finder_name\": \"Relawan Simulasi\",
    \"finder_contact\": \"0800000002\",
    \"person_code\": \"SIM-FP-001\",
    \"person_name\": \"Anonim Simulasi\",
    \"age_group\": \"adult\",
    \"gender\": \"unknown\",
    \"found_location\": \"Shelter Simulasi\",
    \"found_time\": \"Hari ini pagi\",
    \"current_location\": \"posko-sim-shelter\",
    \"condition_notes\": \"Selamat stabil\",
    \"description\": \"Mirip laporan keluarga\",
    \"clothing_description\": \"Baju gelap\"
  }")
echo "$FOUND_RESPONSE"
FOUND_ID=$(echo "$FOUND_RESPONSE" | python3 -c 'import sys,json; d=json.load(sys.stdin); print((d.get("id") or d.get("found_report",{}).get("id") or d.get("data",{}).get("id") or ""))' 2>/dev/null || true)

echo "MISSING_ID=$MISSING_ID"
echo "FOUND_ID=$FOUND_ID"
if [ -n "$MISSING_ID" ] && [ -n "$FOUND_ID" ]; then
  call POST "/search-found-matches" "{
    \"disaster_event_id\": \"$EVENT_ID\",
    \"missing_report_id\": \"$MISSING_ID\",
    \"found_report_id\": \"$FOUND_ID\",
    \"match_score\": 88,
    \"match_reason\": \"Nama alias, pakaian, dan lokasi cocok.\",
    \"status\": \"candidate\"
  }"
else
  echo "WARN: missing/found id not found, skip match"
fi

echo ""
echo "== 11. Resource / transport sharing if endpoint exists =="
call POST "/resource-requests" "{
  \"disaster_event_id\": \"$EVENT_ID\",
  \"resource_id\": \"res-tni-transport-air-01\",
  \"requested_by_type\": \"posko\",
  \"requested_by_id\": \"posko-sim-logistik\",
  \"request_reason\": \"Simulasi booking transport untuk distribusi ke shelter.\",
  \"requested_quantity\": 1,
  \"requested_time\": \"Besok pagi\"
}"

echo ""
echo "== 12. Sync Pull Consolidation =="
call GET "/sync/pull/$EVENT_ID"

echo ""
echo "== 13. AI Context Consolidation =="
call GET "/ai/context/$EVENT_ID"

echo ""
echo "== 14. Summary only =="
curl -sS "$API/ai/context/$EVENT_ID" | python3 -m json.tool | grep -A70 '"summary"' || true

echo ""
echo "===================================================="
echo "Simulation complete."
echo "Open War Room:"
echo "https://osiun.tail251e1e.ts.net/rescue-net/pages/war-room.html?event=$EVENT_ID&v=warroom-pro-2"
echo "===================================================="
