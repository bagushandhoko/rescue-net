const RN_API_BASE = (location.protocol === "https:" ? location.origin + "/rescue-net-api" : "http://192.168.100.32:8092");

async function rnFetch(path, options = {}) {
  const res = await fetch(RN_API_BASE + path, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {})
    },
    ...options
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API error ${res.status}: ${text}`);
  }
  return await res.json();
}

function trustLabel(score) {
  if (score >= 86) return "verified/trusted";
  if (score >= 61) return "high confidence";
  if (score >= 31) return "medium confidence";
  return "low confidence";
}

function safeText(value, fallback = "-") {
  return value === null || value === undefined || value === "" ? fallback : value;
}

function numberOrNull(value) {
  if (value === null || value === undefined || String(value).trim() === "") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function selectedLocationMethod(form) {
  return form.querySelector("input[name='location_input_method']:checked")?.value || "government_area_select";
}

function selectText(select) {
  return select?.selectedOptions?.[0]?.textContent?.trim() || "";
}

function selectCode(select) {
  return select?.selectedOptions?.[0]?.dataset?.code || "";
}

function buildLocationText(form) {
  const manual = form.location_text.value.trim();
  if (manual) return manual;
  return [
    selectText(form.village_name),
    selectText(form.district_name),
    selectText(form.city_name),
    selectText(form.province_name)
  ].filter(Boolean).join(", ");
}

async function loadAdminAreaChildren(parentCode = "", level = "") {
  const query = new URLSearchParams();
  if (parentCode) query.set("parent_code", parentCode);
  if (level) query.set("level", level);
  return rnFetch(`/admin-areas/children?${query.toString()}`);
}

function fillAdminSelect(select, rows, placeholder) {
  if (!select) return;
  select.innerHTML = `<option value="">${placeholder}</option>` + rows.map((row) => (
    `<option value="${row.name}" data-code="${row.code}" data-level="${row.level}">${row.name}</option>`
  )).join("");
  select.disabled = false;
}

function resetAdminSelect(select, placeholder) {
  if (!select) return;
  select.innerHTML = `<option value="">${placeholder}</option>`;
  select.disabled = true;
}

function setupAdminAreaTree(form, updateLocationMessage) {
  const province = form.querySelector("[data-admin-area-select='province']");
  const city = form.querySelector("[data-admin-area-select='city']");
  const district = form.querySelector("[data-admin-area-select='district']");
  const village = form.querySelector("[data-admin-area-select='village']");
  if (!province || !city || !district || !village) return;

  loadAdminAreaChildren("", "province").then((rows) => {
    fillAdminSelect(province, rows, "Pilih provinsi");
  }).catch(() => {
    province.innerHTML = '<option value="">Data wilayah belum tersedia</option>';
  });

  province.addEventListener("change", async () => {
    resetAdminSelect(city, "Pilih kabupaten/kota");
    resetAdminSelect(district, "Pilih kecamatan");
    resetAdminSelect(village, "Pilih desa/kelurahan");
    form.province_code.value = selectCode(province);
    form.city_code.value = "";
    form.district_code.value = "";
    form.village_code.value = "";
    if (form.province_code.value) {
      fillAdminSelect(city, await loadAdminAreaChildren(form.province_code.value, "city"), "Pilih kabupaten/kota");
      form.area_level.value = "province";
    }
    updateLocationMessage();
  });

  city.addEventListener("change", async () => {
    resetAdminSelect(district, "Pilih kecamatan");
    resetAdminSelect(village, "Pilih desa/kelurahan");
    form.city_code.value = selectCode(city);
    form.district_code.value = "";
    form.village_code.value = "";
    if (form.city_code.value) {
      fillAdminSelect(district, await loadAdminAreaChildren(form.city_code.value, "district"), "Pilih kecamatan");
      form.area_level.value = "city";
    }
    updateLocationMessage();
  });

  district.addEventListener("change", async () => {
    resetAdminSelect(village, "Pilih desa/kelurahan");
    form.district_code.value = selectCode(district);
    form.village_code.value = "";
    if (form.district_code.value) {
      fillAdminSelect(village, await loadAdminAreaChildren(form.district_code.value, "village"), "Pilih desa/kelurahan");
      form.area_level.value = "district";
    }
    updateLocationMessage();
  });

  village.addEventListener("change", () => {
    form.village_code.value = selectCode(village);
    if (form.village_code.value) {
      form.area_level.value = "village";
    }
    updateLocationMessage();
  });
}

function reportCard(report) {
  const locationStatus = report.location_status || "no_coordinate";
  const consolidationStatus = report.consolidation_status || "not_ready_no_location";
  return `
    <article class="event-card community-report-item">
      <div class="event-main">
        <div>
          <h4>${safeText(report.title)}</h4>
          <p>${safeText(report.location_text)} | <b>${safeText(report.report_type)}</b> | ${safeText(report.status)}</p>
          <p>${safeText(report.description)}</p>
          <small>${safeText(report.reporter_role)} | ${trustLabel(report.trust_score || 0)} (${report.trust_score || 0})</small>
        </div>
        <div class="chips">
          <span class="chip ${report.priority === "critical" ? "danger" : report.priority === "urgent" ? "warning" : "neutral"}">${report.priority}</span>
          <span class="chip ${locationStatus === "verified_location" || locationStatus === "admin_area_detected" ? "success" : "warning"}">${locationStatus}</span>
          <span class="chip ${consolidationStatus === "ready_for_review" || consolidationStatus === "verified_unique" ? "success" : "neutral"}">${consolidationStatus}</span>
          <span class="chip neutral">${report.id}</span>
        </div>
      </div>
      <div class="community-report-actions">
        <button class="btn" type="button" data-report-action="needs_verification" data-report-id="${report.id}">Triage</button>
        <button class="btn" type="button" data-report-action="verified" data-report-id="${report.id}">Verify</button>
        <button class="btn" type="button" data-report-action="escalated" data-report-id="${report.id}">Escalate</button>
        <button class="btn" type="button" data-report-action="rejected" data-report-id="${report.id}">Reject</button>
        <button class="btn primary" type="button" data-report-convert="${report.id}">Convert Logistik</button>
      </div>
    </article>
  `;
}

async function loadCommunityReports() {
  const target = document.querySelector("[data-community-report-list]");
  if (!target) return;
  target.innerHTML = "<p class=\"subtitle\">Loading laporan masyarakat...</p>";
  try {
    const status = document.querySelector("[data-community-status-filter]")?.value || "";
    const reports = await rnFetch(`/community-reports?disaster_event_id=event-sim-001${status ? `&status=${status}` : ""}`);
    target.innerHTML = reports.length
      ? reports.map(reportCard).join("")
      : "<p class=\"subtitle\">Belum ada laporan pada filter ini.</p>";
  } catch (err) {
    target.innerHTML = `<p class="subtitle">${err.message}</p>`;
  }
}

function setupCommunityReportForm() {
  const form = document.querySelector("[data-community-report-form]");
  const msg = document.querySelector("[data-community-report-message]");
  const locationMsg = document.querySelector("[data-location-status]");
  const currentLocationButton = document.querySelector("[data-use-current-location]");
  if (!form) return;

  function updateLocationMessage() {
    if (!locationMsg) return;
    const method = selectedLocationMethod(form);
    const lat = numberOrNull(form.lat.value);
    const lng = numberOrNull(form.lng.value);
    const areaLevel = form.area_level.value;
    if (method === "gps_current_location") {
      locationMsg.textContent = lat !== null && lng !== null
        ? "Titik GPS sudah terisi. Laporan siap masuk antrian review lokasi."
        : "Tekan Gunakan lokasi saya agar koordinat perangkat terisi.";
      return;
    }
    if (method === "manual_map_pin") {
      locationMsg.textContent = lat !== null && lng !== null
        ? "Titik pin manual sudah terisi. Verifikator tetap perlu cek area administrasi."
        : "Masukkan latitude dan longitude dari titik peta.";
      return;
    }
    locationMsg.textContent = ["province", "city", "district"].includes(areaLevel)
      ? "Area masih luas. Laporan diterima, tetapi belum dipakai untuk konsolidasi sampai desa/titik jelas."
      : "Wilayah pemerintah dipilih. Tambahkan titik GPS/peta jika memungkinkan.";
  }

  form.querySelectorAll("input[name='location_input_method'], input[name='lat'], input[name='lng'], select[name='area_level']").forEach((field) => {
    field.addEventListener("change", updateLocationMessage);
    field.addEventListener("input", updateLocationMessage);
  });
  setupAdminAreaTree(form, updateLocationMessage);

  currentLocationButton?.addEventListener("click", () => {
    if (!navigator.geolocation) {
      if (locationMsg) locationMsg.textContent = "Browser tidak mendukung geolocation. Masukkan titik lat/lng manual.";
      return;
    }
    if (locationMsg) locationMsg.textContent = "Mengambil lokasi perangkat...";
    navigator.geolocation.getCurrentPosition((pos) => {
      form.querySelector("input[name='location_input_method'][value='gps_current_location']").checked = true;
      form.lat.value = pos.coords.latitude.toFixed(6);
      form.lng.value = pos.coords.longitude.toFixed(6);
      form.location_accuracy_meters.value = Math.round(pos.coords.accuracy || 0);
      form.area_level.value = "point";
      updateLocationMessage();
    }, () => {
      if (locationMsg) locationMsg.textContent = "Lokasi perangkat gagal diambil. Masukkan lat/lng manual atau pilih wilayah pemerintah.";
    }, {
      enableHighAccuracy: true,
      timeout: 10000,
      maximumAge: 60000
    });
  });

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const method = selectedLocationMethod(form);
    const lat = numberOrNull(form.lat.value);
    const lng = numberOrNull(form.lng.value);
    const payload = {
      disaster_event_id: "event-sim-001",
      reporter_name: form.reporter_name.value.trim(),
      reporter_phone: form.reporter_phone.value.trim(),
      reporter_role: form.reporter_role.value,
      reporter_verification_level: form.reporter_phone.value.trim() ? "phone_verified" : "anonymous",
      report_type: form.report_type.value,
      title: form.title.value.trim(),
      description: form.description.value.trim(),
      location_text: buildLocationText(form),
      lat,
      lng,
      location_accuracy_meters: numberOrNull(form.location_accuracy_meters.value),
      location_input_method: method,
      location_source: method === "gps_current_location" ? "browser_geolocation" : method,
      admin_level: form.area_level.value,
      area_level: form.area_level.value,
      admin_area_id: form.village_code.value || form.district_code.value || form.city_code.value || form.province_code.value || "",
      province_name: selectText(form.province_name),
      city_name: selectText(form.city_name),
      district_name: selectText(form.district_name),
      village_name: selectText(form.village_name),
      affected_people_count: Number(form.affected_people_count.value || 0),
      priority: form.priority.value,
      urgent_needs: form.urgent_needs.value.trim(),
      evidence_url: form.evidence_url.value.trim(),
      evidence_caption: form.evidence_caption.value.trim(),
      consent_to_contact: form.consent_to_contact.checked
    };

    if (!payload.reporter_name || !payload.title || !payload.description || !payload.location_text) {
      if (msg) msg.textContent = "Lengkapi nama, judul, lokasi/wilayah, dan deskripsi laporan.";
      return;
    }

    if (method === "manual_map_pin" && (lat === null || lng === null)) {
      if (msg) msg.textContent = "Untuk pilihan titik peta, latitude dan longitude harus diisi.";
      return;
    }

    try {
      if (msg) msg.textContent = "Mengirim laporan...";
      const data = await rnFetch("/public/community-reports", {
        method: "POST",
        body: JSON.stringify(payload)
      });
      form.reset();
      form.querySelector("input[name='location_input_method'][value='government_area_select']").checked = true;
      updateLocationMessage();
      if (msg) msg.textContent = `Laporan masuk: ${data.community_report.id}. Lokasi: ${data.community_report.location_status || "no_coordinate"}, konsolidasi: ${data.community_report.consolidation_status || "not_ready_no_location"}.`;
      await loadCommunityReports();
    } catch (err) {
      if (msg) msg.textContent = err.message;
    }
  });

  updateLocationMessage();
}

function setupCommunityReportActions() {
  document.addEventListener("click", async (e) => {
    const statusButton = e.target.closest("[data-report-action]");
    const convertButton = e.target.closest("[data-report-convert]");

    if (statusButton) {
      const id = statusButton.getAttribute("data-report-id");
      const status = statusButton.getAttribute("data-report-action");
      await rnFetch(`/community-reports/${id}/status`, {
        method: "PATCH",
        body: JSON.stringify({
          status,
          verifier_id: "operator-web",
          verifier_role: "command_center",
          notes: `Marked ${status} from operator UI`
        })
      });
      await loadCommunityReports();
    }

    if (convertButton) {
      const id = convertButton.getAttribute("data-report-convert");
      await rnFetch(`/community-reports/${id}/convert`, {
        method: "POST",
        body: JSON.stringify({
          target_type: "logistic_need",
          quantity_needed: 1,
          unit: "paket",
          notes: "Converted from Laporan Masyarakat"
        })
      });
      await loadCommunityReports();
    }
  });

  document.querySelector("[data-community-status-filter]")?.addEventListener("change", loadCommunityReports);
}

document.addEventListener("DOMContentLoaded", () => {
  setupCommunityReportForm();
  setupCommunityReportActions();
  loadCommunityReports();
});

