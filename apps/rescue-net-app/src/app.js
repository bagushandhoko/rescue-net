function defaultApiBase() {
  if (location.protocol === "https:") return `${location.origin}/rescue-net-api`;
  if (/^192\.168\.|^10\.|^172\.(1[6-9]|2\d|3[0-1])\.|^127\.|^localhost$/i.test(location.hostname)) {
    return `http://${location.hostname}:8092`;
  }
  return "http://192.168.100.32:8092";
}

function storedApiBase() {
  const stored = localStorage.getItem("rn_api_base");
  if (location.protocol === "https:" && stored && stored.startsWith("http://")) {
    localStorage.setItem("rn_api_base", defaultApiBase());
    return defaultApiBase();
  }
  return stored || defaultApiBase();
}

let API_BASE = storedApiBase();
let EVENT_ID = localStorage.getItem("rn_active_event_id") || "";
const state = { admin: {}, gps: null };
const STORE_KEYS = {
  reports: "rn_local_reports",
  organizations: "rn_local_organizations",
  profile: "rn_device_profile",
  queue: "rn_sync_queue",
  cache: "rn_last_cache"
};
const WILAYAH_API = "https://wilayah.id/api";
const LOCATION_SOURCES = {
  dropdown: "Kemendagri/data.go.id master wilayah (target mirror RN), fallback wilayah.id API cache",
  gps: "GPS HP + future reverse-check BIG batas desa/kelurahan",
  map: "Pilih titik maps + future BIG boundary validation",
  manual: "Manual darurat, wajib review lokasi"
};
let deferredInstallPrompt = null;

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => Array.from(document.querySelectorAll(selector));

async function api(path, options = {}) {
  const res = await fetch(API_BASE + path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

async function apiForm(path, formData) {
  const res = await fetch(API_BASE + path, { method: "POST", body: formData });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

function readStore(key, fallback = []) {
  try {
    return JSON.parse(localStorage.getItem(key) || JSON.stringify(fallback));
  } catch {
    return fallback;
  }
}

function writeStore(key, value) {
  localStorage.setItem(key, JSON.stringify(value));
}

function readProfile() {
  return readStore(STORE_KEYS.profile, null);
}

function makeLocalId(prefix) {
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`;
}

function enqueueSync(item) {
  const queue = readStore(STORE_KEYS.queue);
  queue.unshift({
    id: makeLocalId("sync"),
    status: "pending",
    attempts: 0,
    last_error: "",
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    ...item
  });
  writeStore(STORE_KEYS.queue, queue);
  renderSyncQueue();
}

function cacheSet(name, value) {
  const cache = readStore(STORE_KEYS.cache, {});
  cache[name] = { value, updated_at: new Date().toISOString() };
  writeStore(STORE_KEYS.cache, cache);
}

function cacheGet(name, fallback = []) {
  return readStore(STORE_KEYS.cache, {})[name]?.value || fallback;
}

function text(selector, value) {
  const el = $(selector);
  if (el) el.textContent = value;
}

function card(title, body, chips = []) {
  return `<article><strong>${title || "n/a"}</strong><p>${body || ""}</p><div class="chips">${chips.map((c) => `<span class="chip ${c.tone || ""}">${c.label}</span>`).join("")}</div></article>`;
}

function syncEventPayload(type, payload) {
  return {
    event_id: payload.local_id || makeLocalId(type),
    device_id: payload.device_id || localStorage.getItem("rn_device_id") || "rn-pwa-device",
    disaster_event_id: EVENT_ID || payload.disaster_event_id || "pending-event-link",
    entity_type: type,
    entity_id: payload.local_id || payload.id || makeLocalId("entity"),
    operation: "upsert",
    payload_json: payload
  };
}

function activeEventId() {
  return EVENT_ID || localStorage.getItem("rn_active_event_id") || "";
}

function setActiveEvent(id) {
  EVENT_ID = id;
  localStorage.setItem("rn_active_event_id", id);
}

async function fileToDataUrl(file) {
  if (!file) return null;
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

function dataUrlToBlob(dataUrl) {
  const [meta, data] = dataUrl.split(",");
  const mime = /data:(.*?);base64/.exec(meta)?.[1] || "application/octet-stream";
  const binary = atob(data);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
  return new Blob([bytes], { type: mime });
}

async function refreshStatus() {
  const input = $("[data-api-base-input]");
  if (input) input.value = API_BASE;
  text("[data-api-url]", API_BASE);
  try {
    await api("/health");
    text("[data-api-status]", "Online");
  } catch (err) {
    text("[data-api-status]", "Offline cache");
    if (API_BASE.includes("/rescue-net-api")) {
      text("[data-api-url]", `${API_BASE} belum aktif. API pusat hidup, tapi reverse proxy web belum tersambung: /rescue-net-api -> 127.0.0.1:8092.`);
    } else {
      text("[data-api-url]", `${API_BASE} tidak terjangkau. Data lokal tetap tersimpan di HP.`);
    }
  }
}

async function loadContextGate() {
  const gate = $("[data-context-gate]");
  if (!gate) return;
  if (!navigator.onLine || activeEventId()) {
    gate.classList.add("hidden");
    return;
  }
  gate.classList.remove("hidden");
  try {
    const disasters = await api("/disasters");
    const active = disasters.filter((d) => (d.status || "").toLowerCase() === "active");
    $("[data-event-select]").innerHTML = '<option value="">Pilih bencana aktif</option>' + active.map((row) => `<option value="${row.id}">${row.name} - ${row.location}</option>`).join("");
  } catch {
    $("[data-event-select]").innerHTML = '<option value="">Tidak bisa memuat bencana</option>';
  }
  try {
    const orgs = await api("/organizations");
    cacheSet("activeOrganizations", orgs);
    $("[data-active-org-select]").innerHTML = '<option value="">Pilih organisasi</option>' + orgs.map((row) => `<option value="${row.id}">${row.name}</option>`).join("");
  } catch {
    const orgs = cacheGet("activeOrganizations", []);
    $("[data-active-org-select]").innerHTML = '<option value="">Pilih organisasi</option>' + orgs.map((row) => `<option value="${row.id}">${row.name}</option>`).join("");
  }
}

async function loadDashboard() {
  try {
    const central = await api(`/central-data/status?disaster_event_id=${activeEventId() || "event-sim-001"}`);
    cacheSet("central", central);
    const summary = central.summary || {};
    ["raw_reports_total", "consolidated_needs", "location_review_needed"].forEach((key) => {
      text(`[data-metric="${key}"]`, summary[key] || 0);
    });
    text("[data-unit-review]", central.unit_review_total || 0);
  } catch {
    const central = cacheGet("central", {});
    const summary = central.summary || {};
    ["raw_reports_total", "consolidated_needs", "location_review_needed"].forEach((key) => {
      text(`[data-metric="${key}"]`, summary[key] || 0);
    });
    text("[data-unit-review]", central.unit_review_total || 0);
  }
  try {
    const rows = await api(`/consolidated-needs?disaster_event_id=${activeEventId() || "event-sim-001"}`);
    cacheSet("consolidated", rows);
    $("[data-consolidated-list]").innerHTML = rows.length ? rows.map((row) => card(
      `${row.item_name} | ${row.quantity_final} ${row.quantity_unit}`,
      `Method: ${row.merge_method}. Sources: ${row.source_count}. Confidence: ${row.confidence_level}.`,
      [{ label: row.status, tone: row.status === "verified" ? "ok" : "warn" }]
    )).join("") : card("Belum ada consolidated need", "Tekan Rebuild untuk membuat draft konsolidasi.", [{ label: "empty" }]);
  } catch (err) {
    const rows = cacheGet("consolidated", []);
    $("[data-consolidated-list]").innerHTML = rows.length ? rows.map((row) => card(
      `${row.item_name} | ${row.quantity_final} ${row.quantity_unit}`,
      `Offline cache. Method: ${row.merge_method}. Sources: ${row.source_count}.`,
      [{ label: "cached", tone: "warn" }]
    )).join("") : card("Offline", "Belum ada cache consolidated needs di perangkat.", [{ label: "cache" }]);
  }
}

async function loadRawQueue() {
  try {
    const rows = await api(`/data-consolidation/raw-reports?disaster_event_id=${activeEventId() || "event-sim-001"}`);
    cacheSet("rawQueue", rows);
    $("[data-raw-list]").innerHTML = rows.length ? rows.map((row) => card(
      `${row.source_type}: ${row.title}`,
      `${row.location_text || "Lokasi belum rinci"}<br>${row.need_text || row.description || ""}`,
      [
        { label: row.location_status, tone: row.location_status?.includes("no_") ? "warn" : "ok" },
        { label: row.consolidation_status, tone: row.consolidation_status?.startsWith("ready") ? "ok" : "warn" }
      ]
    )).join("") : card("Raw queue kosong", "Belum ada laporan mentah.");
  } catch (err) {
    const rows = cacheGet("rawQueue", []);
    const localReports = readStore(STORE_KEYS.reports);
    const merged = [...localReports, ...rows];
    $("[data-raw-list]").innerHTML = merged.length ? merged.map((row) => card(
      `${row.source_type || "local_report"}: ${row.title}`,
      `${row.location_text || "Lokasi belum rinci"}<br>${row.need_text || row.description || ""}`,
      [{ label: row.local_status || "cached", tone: "warn" }]
    )).join("") : card("Offline", "Belum ada raw queue di cache HP.");
  }
}

async function loadUnits() {
  try {
    const catalog = await api("/unit-catalog");
    cacheSet("unitCatalog", catalog);
    const conversions = catalog.conversions || [];
    $("[data-unit-catalog]").innerHTML = conversions.map((row) => card(
      `${row.item_name || "global"}: ${row.from_unit} -> ${row.to_unit}`,
      `x ${row.multiplier}. ${row.notes || ""}`,
      [{ label: row.confidence_level, tone: row.confidence_level?.includes("estimate") ? "warn" : "ok" }]
    )).join("");
  } catch (err) {
    const catalog = cacheGet("unitCatalog", { conversions: [] });
    const conversions = catalog.conversions || [];
    $("[data-unit-catalog]").innerHTML = conversions.length ? conversions.map((row) => card(
      `${row.item_name || "global"}: ${row.from_unit} -> ${row.to_unit}`,
      `Offline cache. x ${row.multiplier}. ${row.notes || ""}`,
      [{ label: "cached", tone: "warn" }]
    )).join("") : card("Offline", "Belum ada unit catalog di cache HP.");
  }
}

async function loadBuildInfo() {
  const target = $("[data-build-info]");
  const apkLink = $("[data-apk-download]");
  if (!target) return;
  try {
    const res = await fetch("downloads/build-info.json", { cache: "no-store" });
    if (!res.ok) throw new Error("no build");
    const info = await res.json();
    const apk = info.apk || "rescue-net-latest.apk";
    target.textContent = `Android build: ${info.built_at || "pending"}\nAPK: ${apk}\nAAB: ${info.aab || "release AAB belum tersedia"}\nStatus: ${info.status || "ready"}`;
    if (apkLink && info.status !== "pending") {
      apkLink.href = `downloads/${apk}`;
      apkLink.textContent = "Download APK";
      apkLink.setAttribute("download", "");
      apkLink.removeAttribute("aria-disabled");
      apkLink.classList.remove("disabled");
    }
  } catch {
    if (apkLink) {
      apkLink.href = "#";
      apkLink.textContent = "APK belum tersedia";
      apkLink.removeAttribute("download");
      apkLink.setAttribute("aria-disabled", "true");
      apkLink.classList.add("disabled");
    }
    target.textContent = "Android APK belum dibuild. Jalankan di Synology: cd /volume1/web/rescue-net-build && sudo sh scripts/rn-build-android-sudo.sh";
  }
}

async function loadAdminChildren(parentCode, level, select) {
  const params = new URLSearchParams();
  if (parentCode) params.set("parent_code", parentCode);
  if (level) params.set("level", level);
  let rows = [];
  const cacheKey = `admin:${parentCode || "root"}:${level}`;
  try {
    rows = await api(`/admin-areas/children?${params}`);
    if (rows.length > 0 && !(level === "province" && rows.length <= 2)) {
      cacheSet(cacheKey, rows);
    } else {
      rows = await loadWilayahChildren(parentCode, level);
      cacheSet(cacheKey, rows);
    }
  } catch {
    try {
      rows = await loadWilayahChildren(parentCode, level);
      cacheSet(cacheKey, rows);
    } catch {
      rows = cacheGet(cacheKey, []);
    }
  }
  select.innerHTML = '<option value="">Pilih</option>' + rows.map((row) => `<option value="${row.name}" data-code="${row.code}">${row.name}</option>`).join("");
  select.disabled = false;
}

async function loadWilayahChildren(parentCode, level) {
  const map = {
    province: "provinces",
    city: `regencies/${parentCode}`,
    district: `districts/${parentCode}`,
    village: `villages/${parentCode}`
  };
  const path = map[level];
  if (!path || path.includes("undefined") || path.includes("null")) return [];
  const res = await fetch(`${WILAYAH_API}/${path}.json`, { cache: "force-cache" });
  if (!res.ok) throw new Error(`wilayah.id ${level} ${res.status}`);
  const body = await res.json();
  return (body.data || []).map((row) => ({
    code: row.code,
    parent_code: parentCode || null,
    name: row.name,
    level,
    source_name: "wilayah.id administrative area API",
    source_url: `${WILAYAH_API}/${path}.json`
  }));
}

function setupAreaTree(form, names = {}) {
  const province = form[names.province || "province"];
  const city = form[names.city || "city"];
  const district = form[names.district || "district"];
  const village = form[names.village || "village"];
  if (!province || !city || !district || !village) return;
  loadAdminChildren("", "province", province).catch(() => {});
  province.addEventListener("change", async () => {
    city.disabled = district.disabled = village.disabled = true;
    city.innerHTML = district.innerHTML = village.innerHTML = '<option value="">Pilih</option>';
    const code = province.selectedOptions[0]?.dataset.code;
    if (code) await loadAdminChildren(code, "city", city);
  });
  city.addEventListener("change", async () => {
    district.disabled = village.disabled = true;
    district.innerHTML = village.innerHTML = '<option value="">Pilih</option>';
    const code = city.selectedOptions[0]?.dataset.code;
    if (code) await loadAdminChildren(code, "district", district);
  });
  district.addEventListener("change", async () => {
    village.disabled = true;
    village.innerHTML = '<option value="">Pilih</option>';
    const code = district.selectedOptions[0]?.dataset.code;
    if (code) await loadAdminChildren(code, "village", village);
  });
}

function setupTabs() {
  $$(".tabbar button").forEach((btn) => btn.addEventListener("click", () => {
    $$(".tabbar button").forEach((b) => b.classList.remove("active"));
    $$(".view").forEach((v) => v.classList.remove("active"));
    btn.classList.add("active");
    $(`[data-panel="${btn.dataset.view}"]`)?.classList.add("active");
  }));
}

function setupReport() {
  const form = $("[data-report-form]");
  const province = form.province;
  const city = form.city;
  const district = form.district;
  const village = form.village;
  setupAreaTree(form);
  $("[data-use-gps]").addEventListener("click", () => {
    navigator.geolocation?.getCurrentPosition((pos) => {
      state.gps = pos.coords;
      text("[data-report-message]", `GPS tersimpan: ${pos.coords.latitude.toFixed(5)}, ${pos.coords.longitude.toFixed(5)}`);
    });
  });
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const locationText = [village.value, district.value, city.value, province.value].filter(Boolean).join(", ");
    const needLine = [form.need_item.value.trim(), form.need_quantity.value.trim(), form.need_unit.value.trim()].filter(Boolean).join(" ");
    const evidenceFile = form.evidence_file.files?.[0] || null;
    const evidenceDataUrl = await fileToDataUrl(evidenceFile);
    const payload = {
      disaster_event_id: activeEventId() || "pending-event-link",
      reporter_name: form.reporter_name.value.trim(),
      reporter_role: "warga_terdampak",
      reporter_verification_level: "anonymous",
      report_type: "kebutuhan_logistik",
      title: form.title.value.trim(),
      description: form.description.value.trim(),
      urgent_needs: [form.urgent_needs.value.trim(), needLine].filter(Boolean).join("; "),
      location_text: locationText,
      location_input_method: state.gps ? "gps_current_location" : "government_area_select",
      location_source: state.gps ? LOCATION_SOURCES.gps : LOCATION_SOURCES.dropdown,
      lat: state.gps?.latitude || null,
      lng: state.gps?.longitude || null,
      location_accuracy_meters: state.gps?.accuracy || null,
      area_level: village.value ? "village" : district.value ? "district" : city.value ? "city" : "province",
      province_name: province.value,
      city_name: city.value,
      district_name: district.value,
      village_name: village.value,
      admin_area_id: village.selectedOptions[0]?.dataset.code || district.selectedOptions[0]?.dataset.code || city.selectedOptions[0]?.dataset.code || province.selectedOptions[0]?.dataset.code || "",
      affected_people_count: 0,
      priority: "normal",
      consent_to_contact: true
    };
    const local = {
      ...payload,
      id: makeLocalId("local-report"),
      source_type: "local_report",
      local_status: activeEventId() ? "pending_sync" : "pending_event_link",
      evidence_data_url: evidenceDataUrl,
      evidence_filename: evidenceFile?.name || "",
      evidence_mime: evidenceFile?.type || "",
      created_at: new Date().toISOString()
    };
    try {
      if (!activeEventId()) throw new Error("Belum pilih bencana aktif");
      const res = await api("/public/community-reports", { method: "POST", body: JSON.stringify(payload) });
      if (evidenceDataUrl) await uploadEvidenceForReport(res.community_report.id, local);
      text("[data-report-message]", `Terkirim: ${res.community_report.id}. ${res.community_report.consolidation_status}`);
      form.reset();
      state.gps = null;
      await loadRawQueue();
    } catch (err) {
      const reports = readStore(STORE_KEYS.reports);
      reports.unshift(local);
      writeStore(STORE_KEYS.reports, reports);
      enqueueSync({ type: "community_report", method: "POST", path: "/public/community-reports", payload: local, local_id: local.id });
      text("[data-report-message]", `Offline tersimpan di HP: ${local.id}. Akan sync otomatis.`);
      await loadRawQueue();
      if (navigator.onLine && !activeEventId()) await loadContextGate();
    }
  });
}

async function uploadEvidenceForReport(reportId, local) {
  if (!local.evidence_data_url) return null;
  const formData = new FormData();
  const blob = dataUrlToBlob(local.evidence_data_url);
  formData.append("file", blob, local.evidence_filename || `${reportId}.jpg`);
  formData.append("disaster_event_id", activeEventId() || local.disaster_event_id || "event-sim-001");
  formData.append("linked_object_type", "community_report");
  formData.append("linked_object_id", reportId);
  formData.append("evidence_type", "photo");
  formData.append("uploaded_by", local.reporter_name || "rn-mobile");
  return apiForm("/evidence/upload", formData);
}

function setupRegistration() {
  const form = $("[data-register-form]");
  if (!form) return;
  setupAreaTree(form);
  const profile = readProfile();
  if (profile) {
    form.organization_name.value = profile.organization_name || "";
    form.member_name.value = profile.member_name || "";
    form.role.value = profile.role || "posko_operator";
    form.notes.value = profile.notes || "";
    form.verifier_mode.value = profile.verifier_mode || "none";
    form.requested_verifier_id.value = profile.requested_verifier_id || "";
    form.requested_verifier_name.value = profile.requested_verifier_name || "";
    form.requested_verifier_role.value = profile.requested_verifier_role || "";
    form.requested_verifier_phone.value = profile.requested_verifier_phone || "";
    form.requested_verifier_email.value = profile.requested_verifier_email || "";
    form.verifier_relationship.value = profile.verifier_relationship || "";
  }
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const locationText = [form.village.value, form.district.value, form.city.value, form.province.value].filter(Boolean).join(", ");
    const payload = {
      local_id: readProfile()?.local_id || makeLocalId("device-profile"),
      device_id: localStorage.getItem("rn_device_id") || makeLocalId("device"),
      organization_name: form.organization_name.value.trim(),
      disaster_event_id: activeEventId() || "pending-event-link",
      member_name: form.member_name.value.trim(),
      role: form.role.value,
      posko_name: form.organization_name.value.trim(),
      notes: form.notes.value.trim(),
      location_text: locationText,
      area_level: form.village.value ? "village" : form.district.value ? "district" : form.city.value ? "city" : "province",
      province_name: form.province.value,
      city_name: form.city.value,
      district_name: form.district.value,
      village_name: form.village.value,
      admin_area_id: form.village.selectedOptions[0]?.dataset.code || form.district.selectedOptions[0]?.dataset.code || form.city.selectedOptions[0]?.dataset.code || form.province.selectedOptions[0]?.dataset.code || "",
      verifier_mode: form.verifier_mode.value,
      requested_verifier_id: form.requested_verifier_id.value.trim(),
      requested_verifier_name: form.requested_verifier_name.value.trim(),
      requested_verifier_role: form.requested_verifier_role.value.trim(),
      requested_verifier_phone: form.requested_verifier_phone.value.trim(),
      requested_verifier_email: form.requested_verifier_email.value.trim(),
      verifier_relationship: form.verifier_relationship.value.trim(),
      status: "local_pending",
      updated_at: new Date().toISOString()
    };
    localStorage.setItem("rn_device_id", payload.device_id);
    writeStore(STORE_KEYS.profile, payload);
    registerDevice(payload);
  });
}

async function registerDevice(payload) {
  try {
    const result = await api("/device-registrations", { method: "POST", body: JSON.stringify(payload) });
    const registered = { ...payload, status: "synced", organization_id: result.organization?.id, posko_id: result.posko?.id, synced_at: new Date().toISOString() };
    registered.identity_verification_status = result.posko?.identity_verification_status || "unverified";
    registered.verification_request = result.verification_request || null;
    registered.verification_url = result.verification_url || null;
    writeStore(STORE_KEYS.profile, registered);
    text("[data-register-message]", `Terdaftar pusat: ${registered.organization_name}. Identitas: ${registered.identity_verification_status}. Lokasi/laporan/kebutuhan tetap diverifikasi terpisah.${registered.verification_url ? ` Link verifier: ${registered.verification_url}` : ""}`);
  } catch (err) {
    enqueueSync({
      type: "device_registration",
      method: "POST",
      path: "/device-registrations",
      payload,
      local_id: payload.local_id
    });
    text("[data-register-message]", `Offline tersimpan: ${payload.organization_name}. Akan sync ke database pusat otomatis.`);
  }
  applyProfile();
}

function applyProfile() {
  const profile = readProfile();
  if (!profile) return;
  text("[data-profile-name]", profile.organization_name || "Belum registrasi");
  text("[data-profile-detail]", `${profile.member_name || "PIC belum diisi"} | ${profile.role || "role"} | Identitas: ${profile.identity_verification_status || "pending"} | Lokasi: ${profile.location_verification_status || "pending"} | Laporan: terpisah | Kebutuhan: terpisah`);
  const reportForm = $("[data-report-form]");
  if (reportForm && !reportForm.reporter_name.value) {
    reportForm.reporter_name.value = profile.organization_name || profile.member_name || "";
  }
}

function setupOrganization() {
  const form = $("[data-org-form]");
  if (!form) return;
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const payload = {
      local_id: makeLocalId("org-member"),
      organization_name: form.organization_name.value.trim(),
      member_name: form.member_name.value.trim(),
      role: form.role.value,
      posko_name: form.posko_name.value.trim(),
      notes: form.notes.value.trim(),
      status: "local_pending",
      created_at: new Date().toISOString()
    };
    const rows = readStore(STORE_KEYS.organizations);
    rows.unshift(payload);
    writeStore(STORE_KEYS.organizations, rows);
    enqueueSync({
      type: "organization_member",
      method: "POST",
      path: "/sync/events",
      payload: syncEventPayload("organization_member", payload),
      local_id: payload.local_id
    });
    text("[data-org-message]", `Tersimpan offline: ${payload.member_name}. Menunggu sync.`);
    form.reset();
    renderOrganizations();
  });
  renderOrganizations();
}

function renderOrganizations() {
  const target = $("[data-org-list]");
  if (!target) return;
  const rows = readStore(STORE_KEYS.organizations);
  target.innerHTML = rows.length ? rows.map((row) => card(
    `${row.organization_name} | ${row.member_name}`,
    `${row.role}. ${row.posko_name || "Belum pilih posko"}<br>${row.notes || ""}`,
    [{ label: row.status || "local", tone: row.status === "synced" ? "ok" : "warn" }]
  )).join("") : card("Belum ada member organisasi", "Data organisasi/member bisa disimpan offline dulu.");
}

async function syncOne(item) {
  try {
    if (!activeEventId() && item.payload?.disaster_event_id === "pending-event-link") {
      return { ...item, status: "pending", last_error: "Pilih bencana aktif dulu sebelum sync.", updated_at: new Date().toISOString() };
    }
    if (item.payload?.disaster_event_id === "pending-event-link") {
      item.payload.disaster_event_id = activeEventId();
    }
    let result;
    if (item.path === "/sync/events") {
      result = await api("/sync/push", {
        method: "POST",
        body: JSON.stringify({
          source_device_id: item.payload?.device_id || "rn-pwa-device",
          events: [{
            event_id: item.payload?.event_id || item.id,
            object_type: item.payload?.entity_type || item.type,
            object_id: item.payload?.entity_id || item.local_id || item.id,
            operation: item.payload?.operation || "upsert",
            payload_json: item.payload?.payload_json || item.payload || {},
            source_device_id: item.payload?.device_id || "rn-pwa-device"
          }]
        })
      });
    } else {
      const evidence = item.payload?.evidence_data_url ? { ...item.payload } : null;
      const payload = { ...(item.payload || {}) };
      delete payload.evidence_data_url;
      delete payload.evidence_filename;
      delete payload.evidence_mime;
      result = await api(item.path, { method: item.method || "POST", body: JSON.stringify(payload) });
      if (item.type === "community_report" && evidence && result.community_report?.id) {
        await uploadEvidenceForReport(result.community_report.id, evidence);
      }
    }
    return { ...item, status: "synced", result, updated_at: new Date().toISOString(), last_error: "" };
  } catch (err) {
    const isConflict = /409|duplicate|conflict|already|Invalid|400|422/i.test(err.message);
    return {
      ...item,
      status: isConflict ? "conflict" : "pending",
      attempts: (item.attempts || 0) + 1,
      last_error: err.message.slice(0, 500),
      updated_at: new Date().toISOString()
    };
  }
}

async function runSync() {
  if (!navigator.onLine) {
    renderSyncQueue();
    return;
  }
  if (!activeEventId()) {
    await loadContextGate();
    renderSyncQueue();
    return;
  }
  const queue = readStore(STORE_KEYS.queue);
  const next = [];
  for (const item of queue) {
    if (item.status === "synced" || item.status === "conflict") {
      next.push(item);
      continue;
    }
    next.push(await syncOne(item));
  }
  writeStore(STORE_KEYS.queue, next);
  renderSyncQueue();
}

function renderSyncQueue() {
  const queue = readStore(STORE_KEYS.queue);
  const pending = queue.filter((x) => x.status === "pending").length;
  const synced = queue.filter((x) => x.status === "synced").length;
  const conflict = queue.filter((x) => x.status === "conflict").length;
  text("[data-sync-pending]", pending);
  text("[data-sync-synced]", synced);
  text("[data-sync-conflict]", conflict);
  const target = $("[data-sync-list]");
  if (!target) return;
  target.innerHTML = queue.length ? queue.map((item) => {
    const klass = item.status === "conflict" ? "sync-conflict" : item.status === "synced" ? "sync-ok" : "sync-local";
    return `<article class="${klass}">
      <strong>${item.type} | ${item.status}</strong>
      <p>${item.local_id || item.id}<br>${item.last_error || "Menunggu sinkronisasi otomatis."}</p>
      <div class="chips"><span class="chip">${item.attempts || 0} attempts</span><span class="chip">${item.updated_at || item.created_at}</span></div>
    </article>`;
  }).join("") : card("Queue kosong", "Data baru akan tersimpan di HP dulu lalu otomatis sync.");
}

function setupActions() {
  $("[data-save-api]").addEventListener("click", async () => {
    const value = $("[data-api-base-input]").value.trim().replace(/\/$/, "");
    if (value) {
      API_BASE = value;
      localStorage.setItem("rn_api_base", API_BASE);
      await refreshAll();
    }
  });
  $("[data-refresh]").addEventListener("click", refreshAll);
  $("[data-sync-now]").addEventListener("click", runSync);
  $("[data-save-context]")?.addEventListener("click", async () => {
    const id = $("[data-event-select]")?.value;
    if (!id) return;
    setActiveEvent(id);
    const profile = readProfile();
    if (profile) {
      profile.disaster_event_id = id;
      profile.organization_id = $("[data-active-org-select]")?.value || profile.organization_id || "";
      writeStore(STORE_KEYS.profile, profile);
      await registerDevice(profile);
    }
    await refreshAll();
  });
  $("[data-create-event]")?.addEventListener("click", async () => {
    const name = $("[data-new-event-name]")?.value.trim();
    const type = $("[data-new-event-type]")?.value.trim() || "other";
    const location = $("[data-new-event-location]")?.value.trim() || "Lokasi belum rinci";
    if (!name) return;
    const created = await api("/disasters", {
      method: "POST",
      body: JSON.stringify({ name, disaster_type: type, location, status: "active", severity: "normal" })
    });
    setActiveEvent(created.id);
    await refreshAll();
  });
  $("[data-install-app]")?.addEventListener("click", async () => {
    if (!deferredInstallPrompt) {
      text("[data-install-message]", "Jika tombol install tidak muncul, gunakan menu browser: Android Chrome Install app, iOS Safari Add to Home Screen, Desktop Chrome/Edge Install.");
      return;
    }
    deferredInstallPrompt.prompt();
    const choice = await deferredInstallPrompt.userChoice;
    text("[data-install-message]", choice.outcome === "accepted" ? "Install dimulai." : "Install dibatalkan.");
    deferredInstallPrompt = null;
  });
  $("[data-rebuild]").addEventListener("click", async () => {
    await api(`/consolidated-needs/rebuild?disaster_event_id=${EVENT_ID}`, { method: "POST" });
    await loadDashboard();
  });
  $("[data-check-duplicates]").addEventListener("click", async () => {
    await api("/duplicates/check", { method: "POST", body: JSON.stringify({ disaster_event_id: EVENT_ID, object_type: "all" }) });
    await loadRawQueue();
  });
  $("[data-unit-form]").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const result = await api("/unit-normalize", {
      method: "POST",
      body: JSON.stringify({
        item_name: form.item_name.value,
        quantity: Number(form.quantity.value || 0),
        unit: form.unit.value
      })
    });
    $("[data-unit-result]").textContent = JSON.stringify(result, null, 2);
  });
}

async function refreshAll() {
  await refreshStatus();
  await loadContextGate();
  await Promise.all([loadDashboard(), loadRawQueue(), loadUnits()]);
  await loadBuildInfo();
  renderOrganizations();
  renderSyncQueue();
  applyProfile();
  runSync();
}

document.addEventListener("DOMContentLoaded", () => {
  setupTabs();
  setupActions();
  setupReport();
  setupRegistration();
  setupOrganization();
  const initialView = window.location.hash.replace("#", "");
  if (initialView) {
    document.querySelector(`[data-view="${initialView}"]`)?.click();
  }
  window.addEventListener("online", async () => {
    await loadContextGate();
    runSync();
  });
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("sw.js").catch(() => {});
  }
  window.addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault();
    deferredInstallPrompt = event;
    text("[data-install-message]", "Aplikasi siap diinstall di perangkat ini.");
  });
  refreshAll();
});

