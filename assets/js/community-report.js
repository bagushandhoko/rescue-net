
// Backend-shape mapping for a community report submission — shared by the
// live POST below and by the offline queue (see setupCommunityReportForm),
// so a report queued while offline reaches api_sync._apply_community_report
// with the exact same field shape submit_community_report expects.
function communityReportBridgePayload(body) {
  return {
    title: body.title,
    description: body.description,
    report_type: body.report_type || null,
    priority: body.priority || null,
    affected_people_count: Number(body.affected_people_count || 0),
    urgent_needs: body.urgent_needs || null,
    location_text: body.location_text || null,
    latitude: body.latitude ?? body.lat ?? null,
    longitude: body.longitude ?? body.lng ?? null,
    province_code: body.province_code || null,
    city_code: body.city_code || null,
    district_code: body.district_code || null,
    village_code: body.village_code || null,
    consent_to_contact: body.consent_to_contact ? 1 : 0,
    reporter_phone: body.reporter_phone || null,
    location_input_method: body.location_input_method || null,
    create_need: body.create_need ? 1 : 0,
    damage_scale_value: body.damage_scale_value ?? null,
    damage_scale_unit: body.damage_scale_unit || null,
    disaster_event: body.disaster_event_id || null,
    intake_mode: body.intake_mode || "form",
    intake_parser: body.intake_parser || null
  };
}

async function rnFetch(path, options = {}) {
  const method =
    String(
      options.method || "GET"
    ).toUpperCase();

  const url =
    new URL(
      path,
      location.origin
    );

  let body = {};

  if (options.body) {
    body =
      typeof options.body === "string"
        ? JSON.parse(options.body)
        : options.body;
  }

  if (
    url.pathname ===
      "/admin-areas/children"
  ) {
    return await RN_FRAPPE.call(
      "rescue_net.api_frontend_bridge."
      + "admin_area_children",
      {
        parent_code:
          url.searchParams.get(
            "parent_code"
          )
          || url.searchParams.get(
            "parent"
          )
          || "",

        level:
          url.searchParams.get(
            "level"
          )
          || ""
      }
    );
  }

  if (
    url.pathname ===
      "/community-reports"
    && method === "GET"
  ) {
    return await RN_FRAPPE.call(
      "rescue_net.api_frontend_bridge."
      + "community_reports",
      {
        disaster_event:
          url.searchParams.get(
            "disaster_event_id"
          )
          || window.rnActiveEvent
          || "event-sim-001",

        status:
          url.searchParams.get(
            "status"
          )
          || null
      }
    );
  }

  if (
    url.pathname ===
      "/public/community-reports"
    && method === "POST"
  ) {
    return await RN_FRAPPE.call(
      "rescue_net.api_frontend_bridge."
      + "submit_community_report_bridge",
      communityReportBridgePayload(body),
      {
        method: "POST"
      }
    );
  }

  const statusMatch =
    url.pathname.match(
      /^\/community-reports\/([^/]+)\/status$/
    );

  if (
    statusMatch
    && (
      method === "POST"
      || method === "PATCH"
    )
  ) {
    return await RN_FRAPPE.call(
      "rescue_net.api_frontend_bridge."
      + "set_community_report_status",
      {
        report:
          decodeURIComponent(
            statusMatch[1]
          ),

        status:
          body.status
      },
      {
        method: "POST"
      }
    );
  }

  const convertMatch =
    url.pathname.match(
      /^\/community-reports\/([^/]+)\/convert$/
    );

  if (
    convertMatch
    && method === "POST"
  ) {
    return await RN_FRAPPE.call(
      "rescue_net.api_frontend_bridge."
      + "convert_community_report",
      {
        report:
          decodeURIComponent(
            convertMatch[1]
          )
      },
      {
        method: "POST"
      }
    );
  }

  throw new Error(
    "Unsupported Community Report route: "
    + method
    + " "
    + url.pathname
  );
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

function predictedNeedsLine(predicted_needs) {
  if (!predicted_needs || !predicted_needs.length) return "";
  const list = predicted_needs
    .map((n) => `${n.predicted_qty} ${safeText(n.unit)} ${safeText(n.label)}${n.per_day ? "/hari" : ""}`)
    .join(", ");
  return `<p class="community-report-predicted"><b>Perkiraan kebutuhan (heuristik):</b> ${list}</p>`;
}

function escHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

const AI_STATUS_LABEL = {
  pending_ai: "belum diproses AI",
  ai_suggested: "saran AI menunggu keputusan posko",
  ai_applied: "saran AI diterima",
  ai_rejected: "saran AI ditolak"
};

function aiStatusLine(report) {
  const label = AI_STATUS_LABEL[report.ai_status];
  return label ? `<p class="community-report-predicted"><small><b>AI:</b> ${escHtml(label)}</small></p>` : "";
}

function routingLine(report) {
  if (!report.posko && !report.routing_reason) return "";
  const target = report.posko_title || report.posko;
  return `<p class="community-report-predicted"><b>Posko tujuan:</b> ${target ? escHtml(target) : "belum ada"}`
    + (report.routing_reason ? ` <small>— ${escHtml(report.routing_reason)}</small>` : "") + "</p>";
}

/* ---------- Session: a report belongs to a logged-in reporter ---------- */
let RN_REPORTER = null;

async function loadReporterSession(form) {
  let session = null;
  try {
    session = await RN_FRAPPE.session();
  } catch (err) {
    session = null;
  }
  const loggedIn = !!(session && session.user && session.user !== "Guest");
  RN_REPORTER = loggedIn ? session : null;
  document.body.dataset.rnLogged = loggedIn ? "1" : "";
  applyPhoneRule(form, loggedIn ? session : null);
  const gate = document.querySelector("[data-report-login]");
  if (gate) gate.hidden = loggedIn;
  // Buttons stay fully visible for guests; pressing one without a session shows the login box instead.
  form.querySelectorAll("button[type='submit'], [data-draft-report]").forEach((b) => { b.disabled = false; });
  const rnLogin = document.querySelector("[data-login-rn]");
  if (rnLogin) rnLogin.href = "auth.html?next=" + encodeURIComponent(location.pathname + location.search);
  if (loggedIn && form.reporter_name && !form.reporter_name.value) {
    form.reporter_name.value = session.full_name || session.user;
  }
  document.querySelector("[data-my-reports-panel]")?.toggleAttribute("hidden", !loggedIn);
  if (loggedIn) loadMyReports().catch(() => {});
  return loggedIn;
}

/* Google logins must leave a phone number the verifier can call (owner 2026-10-08). */
const PHONE_RE = /^(\+?62|0)8[0-9]{8,12}$/;
function phoneOk(v) { return PHONE_RE.test(String(v || "").replace(/[\s\-.()]/g, "")); }

function applyPhoneRule(form, session) {
  const input = form.reporter_phone;
  if (!input) return;
  const must = !!(session && session.login_provider === "google");
  form.dataset.phoneRequired = must ? "1" : "";
  input.required = must;
  input.placeholder = must ? "Wajib, mis. 081234567890" : "Opsional, menaikkan trust score";
  const label = input.closest("label");
  if (label && !label.dataset.phoneLabel) label.dataset.phoneLabel = label.firstChild ? label.firstChild.textContent : "";
  if (label && label.firstChild && label.firstChild.nodeType === 3) {
    label.firstChild.textContent = must ? "No HP / WhatsApp (wajib, untuk dihubungi verifikator) " : (label.dataset.phoneLabel || "No HP / WhatsApp ");
  }
  if (session && session.phone && !input.value) input.value = session.phone;
}

function requireLogin() {
  if (RN_REPORTER) return true;
  const gate = document.querySelector("[data-report-login]");
  if (gate) {
    gate.hidden = false;
    gate.scrollIntoView({ behavior: "smooth", block: "center" });
    gate.classList.add("is-attention");
    setTimeout(() => gate.classList.remove("is-attention"), 1600);
  }
  return false;
}

async function loginWithGoogle(btn) {
  btn.disabled = true;
  try {
    const r = await RN_FRAPPE.call("rescue_net.api_auth.social_login_url", {
      provider: "google",
      redirect_to: location.href
    });
    if (r && r.available && r.url) {
      location.href = r.url;
      return;
    }
    alert((r && r.reason) || "Login Google belum tersedia.");
  } catch (err) {
    alert(err.message);
  }
  btn.disabled = false;
}

/* ---------- Cukup ceritakan: uraian -> form (AI / aturan) ---------- */
function setIntakeMode(form, mode) {
  form.dataset.mode = mode;
}

function draftSummary(d) {
  const f = d.fields || {};
  const needs = (d.predicted_needs || [])
    .map((n) => `${n.predicted_qty} ${escHtml(n.unit)} ${escHtml(n.label)}${n.per_day ? "/hari" : ""}`).join(", ");
  const notes = (f.notes || []).map((n) => `<li>${escHtml(n)}</li>`).join("");
  return `
    <b>Diolah dengan ${escHtml(d.parser_label)} — periksa dan perbaiki kolom di bawah sebelum kirim.</b>
    <span>Jenis: ${escHtml(d.report_type_label || f.report_type)} · Prioritas: ${escHtml(f.priority)} · Terdampak: ${Number(f.affected_people_count || 0)} orang</span>
    <span>Posko tujuan: ${d.suggested_posko_title ? escHtml(d.suggested_posko_title) : "belum ada"} <small>— ${escHtml(d.routing_reason || "")}</small></span>
    ${needs ? `<span>Perkiraan kebutuhan: ${needs}</span>` : ""}
    ${notes ? `<ul>${notes}</ul>` : ""}`;
}

function applyDraft(form, d) {
  const f = d.fields || {};
  const set = (name, value) => {
    if (form[name] && value !== null && value !== undefined && value !== "") form[name].value = value;
  };
  set("title", f.title);
  set("report_type", f.report_type);
  set("priority", f.priority);
  set("affected_people_count", f.affected_people_count);
  set("urgent_needs", f.urgent_needs);
  set("damage_scale_value", f.damage_scale_value);
  set("damage_scale_unit", f.damage_scale_unit);
  set("location_text", f.location_text);
  form.description.value = form.narrative.value.trim();
  form.dataset.intakeParser = d.parser || "rules";
  form.dataset.drafted = "1";
}

/* A readable error line: the server's own message first, never a bare "Perlu login" for a logged-in user. */
function readableError(err) {
  const p = (err && err.payload) || {};
  try {
    const list = JSON.parse(p._server_messages || "[]");
    const texts = list.map((m) => { try { return JSON.parse(m).message; } catch (_) { return String(m); } }).filter(Boolean);
    if (texts.length) return texts.join(" ").replace(/<[^>]+>/g, "").trim();
  } catch (_) { /* fall through */ }
  if (err && err.status === 403 && RN_REPORTER) {
    return "Akun Anda belum diizinkan melapor (403). Pastikan akun Rescue-Net Anda aktif atau hubungi admin posko.";
  }
  if (err && err.status === 429) return "Terlalu banyak percobaan. Tunggu beberapa menit lalu coba lagi.";
  return (err && err.message) || "Terjadi kesalahan. Coba lagi.";
}

function showMsg(el, text, isError) {
  if (!el) return;
  el.textContent = text;
  el.classList.toggle("is-error", !!isError);
}

async function draftReport(form) {
  const msg = document.querySelector("[data-draft-message]");
  const box = document.querySelector("[data-draft-result]");
  const narrative = form.narrative.value.trim();
  if (narrative.length < 15) {
    showMsg(msg, "Ceritakan sedikit lebih lengkap (min. 15 karakter): apa yang terjadi, di mana, siapa terdampak, apa yang dibutuhkan.", true);
    form.narrative.focus();
    return;
  }
  showMsg(msg, "Mengolah uraian…", false);
  const draftBtn = document.querySelector("[data-draft-report]");
  if (draftBtn) { draftBtn.disabled = true; draftBtn.dataset.label = draftBtn.textContent; draftBtn.textContent = "Memproses…"; }
  try {
    const d = await RN_FRAPPE.call("rescue_net.api_reports.draft_community_report", {
      narrative,
      disaster_event: window.rnActiveEvent || null,
      latitude: numberOrNull(form.lat.value),
      longitude: numberOrNull(form.lng.value),
      province_code: form.province_code.value || null,
      city_code: form.city_code.value || null,
      district_code: form.district_code.value || null,
      village_code: form.village_code.value || null
    }, { method: "POST" });
    applyDraft(form, d);
    box.innerHTML = draftSummary(d);
    box.hidden = false;
    showMsg(msg, "Form sudah terisi. Periksa lalu tekan Kirim Laporan.", false);
    document.querySelector("[data-report-fields]")?.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (err) {
    showMsg(msg, readableError(err), true);
  } finally {
    if (draftBtn) { draftBtn.disabled = false; draftBtn.textContent = draftBtn.dataset.label || "Konversi ke Form"; }
  }
}

/* ---------- Laporan Saya + tindak lanjut ---------- */
const UPDATE_TYPE_LABEL = { info: "Info terbaru", additional_need: "Kebutuhan tambahan", resolved: "Sudah tertangani" };

function myReportCard(r) {
  const thread = (r.updates || []).map((u) => `
    <div><b>${u.author_role === "posko" ? "Posko" : "Anda"}</b> · ${escHtml(UPDATE_TYPE_LABEL[u.update_type] || u.update_type)}
      <small>${escHtml(u.posted_at || "")}</small><br>${escHtml(u.body)}
      ${u.urgent_needs ? `<br><small>Kebutuhan: ${escHtml(u.urgent_needs)}</small>` : ""}
      ${u.affected_people_count ? `<br><small>Terdampak kini: ${Number(u.affected_people_count)} orang</small>` : ""}</div>`).join("");
  return `
    <article class="event-card community-report-item">
      <div class="event-main">
        <div>
          <h4>${escHtml(r.title)}</h4>
          <p>${escHtml(r.location_text || "-")} | <b>${escHtml(r.report_type || "-")}</b> | ${escHtml(r.status)}</p>
          ${routingLine(r)}
          ${r.ai_status === "pending_ai" ? aiStatusLine(r) : ""}
          ${thread ? `<div class="rn-report-thread">${thread}</div>` : ""}
        </div>
        <div class="chips"><span class="chip neutral">${escHtml(r.name)}</span></div>
      </div>
      ${r.status === "rejected" ? "" : `
      <form class="rn-form rn-report-followup" data-followup="${escHtml(r.name)}">
        <label>Jenis
          <select name="update_type">
            <option value="additional_need">Kebutuhan tambahan</option>
            <option value="info">Info terbaru</option>
            <option value="resolved">Sudah tertangani</option>
          </select>
        </label>
        <label>Kebutuhan (opsional)<input name="urgent_needs" placeholder="mis. susu bayi 50 kotak"></label>
        <label>Jumlah terdampak kini<input name="affected_people_count" type="number" min="0" placeholder="opsional"></label>
        <textarea name="body" rows="2" required placeholder="Apa yang berubah / bantuan apa lagi yang dibutuhkan?"></textarea>
        <div class="form-actions"><button class="btn" type="submit">Kirim Tindak Lanjut</button><span class="form-message"></span></div>
      </form>`}
    </article>`;
}

async function loadMyReports() {
  const target = document.querySelector("[data-my-reports]");
  if (!target) return;
  const rows = await RN_FRAPPE.call("rescue_net.api_reports.my_community_reports");
  target.innerHTML = rows.length
    ? rows.map(myReportCard).join("")
    : "<p class=\"subtitle\">Anda belum mengirim laporan.</p>";
}

function setupFollowUps() {
  document.addEventListener("submit", async (e) => {
    const f = e.target.closest("[data-followup]");
    if (!f) return;
    e.preventDefault();
    const out = f.querySelector(".form-message");
    out.textContent = "Mengirim…";
    try {
      await RN_FRAPPE.call("rescue_net.api_reports.add_community_report_update", {
        report: f.dataset.followup,
        update_type: f.update_type.value,
        body: f.body.value.trim(),
        urgent_needs: f.urgent_needs.value.trim() || null,
        affected_people_count: numberOrNull(f.affected_people_count.value)
      }, { method: "POST" });
      await loadMyReports();
    } catch (err) {
      out.textContent = err.message;
    }
  });
}

function reportCard(report) {
  const locationStatus = report.location_status || "no_coordinate";
  const consolidationStatus = report.consolidation_status || "not_ready_no_location";
  return `
    <article class="event-card community-report-item" id="report-${report.id}">
      <div class="event-main">
        <div>
          <h4>${safeText(report.title)}</h4>
          <p>${safeText(report.location_text)} | <b>${safeText(report.report_type)}</b> | ${safeText(report.status)}</p>
          <p>${safeText(report.description)}</p>
          ${predictedNeedsLine(report.predicted_needs)}
          ${routingLine(report)}
          ${aiStatusLine(report)}
          <small>${safeText(report.reporter_name)}${verifiedBadge(report, true)} · ${safeText(report.reporter_role)} | ${trustLabel(report.trust_score || 0)} (${report.trust_score || 0})</small>
          ${report.can_contact_reporter ? `
          <div class="rn-reporter-actions">
            <button class="btn mini" type="button" data-reporter-view="contact" data-report-id="${report.id}">Hubungi pelapor</button>
            <button class="rn-link-btn" type="button" data-reporter-view="level" data-report-id="${report.id}">Verifikator &amp; level ›</button>
          </div>` : (isVerified(report) ? `
          <div class="rn-reporter-actions">
            <button class="rn-link-btn" type="button" data-reporter-view="level" data-report-id="${report.id}">Lihat verifikator ›</button>
          </div>` : "")}
          ${(report.can_contact_reporter || isVerified(report)) ? `<div class="rn-reporter-panel" data-reporter-panel="${report.id}" data-local="${escHtml(JSON.stringify({ status: report.reporter_verification_status || "self_reported", count: report.reporter_verified_count || 0, verifiers: report.reporter_verifiers || [] }))}" hidden></div>` : ""}
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
    const activeEvent = window.rnActiveEvent || "event-sim-001";
    const reports = await rnFetch(`/community-reports?disaster_event_id=${encodeURIComponent(activeEvent)}${status ? `&status=${status}` : ""}`);
    const PAGE = 10;
    target.innerHTML = reports.length
      ? reports.map((r, i) => reportCard(r).replace("community-report-item", `community-report-item${i >= PAGE ? " is-later" : ""}`)).join("")
        + (reports.length > PAGE ? `<button class="btn queue-more" type="button" data-queue-more>Tampilkan lebih banyak (${reports.length - PAGE} lagi)</button>` : "")
      : "<p class=\"subtitle\">Belum ada laporan pada filter ini.</p>";

    // Deep link from another page (e.g. Data Konsolidasi's rollup source
    // drill-down) — ?report=<id> scrolls to and briefly highlights it.
    const wantedReport = new URLSearchParams(location.search).get("report");
    if (wantedReport) {
      const el = document.getElementById(`report-${wantedReport}`);
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "center" });
        el.classList.add("rn-kpi-jump-highlight");
        setTimeout(() => el.classList.remove("rn-kpi-jump-highlight"), 1600);
      }
    }
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

  form.querySelectorAll("input[name='intake_mode']").forEach((r) => {
    r.addEventListener("change", () => setIntakeMode(form, r.value));
  });
  setIntakeMode(form, form.querySelector("input[name='intake_mode']:checked")?.value || "narrative");
  // "Cukup ceritakan" needs the intake backend (draft_community_report);
  // until that is deployed the page stays on the plain form.
  RN_FRAPPE.call("rescue_net.api_ai.ai_providers").catch(() => {
    form.querySelector("input[name='intake_mode'][value='form']").checked = true;
    setIntakeMode(form, "form");
    document.querySelector(".rn-report-mode")?.setAttribute("hidden", "");
  });
  form.narrative?.addEventListener("input", () => { delete form.dataset.drafted; });
  document.querySelector("[data-draft-report]")?.addEventListener("click", () => { if (requireLogin()) draftReport(form); });
  document.querySelector("[data-login-google]")?.addEventListener("click", (e) => loginWithGoogle(e.currentTarget));
  loadReporterSession(form);

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
    if (!requireLogin()) return;
    if (form.dataset.phoneRequired === "1" && !phoneOk(form.reporter_phone.value)) {
      showMsg(document.querySelector("[data-community-report-message]"),
        "Nomor HP wajib diisi (08… atau +62…) agar verifikator dapat menghubungi Anda.", true);
      form.reporter_phone.focus();
      form.reporter_phone.scrollIntoView({ behavior: "smooth", block: "center" });
      return;
    }
    const method = selectedLocationMethod(form);
    const lat = numberOrNull(form.lat.value);
    const lng = numberOrNull(form.lng.value);
    const payload = {
      disaster_event_id: window.rnActiveEvent || "event-sim-001",
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
      consent_to_contact: form.consent_to_contact.checked,
      damage_scale_value: numberOrNull(form.damage_scale_value.value),
      damage_scale_unit: form.damage_scale_unit.value.trim() || null,
      intake_mode: form.dataset.mode === "narrative" ? "narrative" : "form",
      intake_parser: form.dataset.mode === "narrative" ? (form.dataset.intakeParser || null) : null
    };

    if (!RN_REPORTER) {
      if (msg) msg.textContent = "Masuk dulu (akun Rescue-Net atau Google) untuk mengirim laporan.";
      return;
    }

    if (payload.intake_mode === "narrative") {
      // narrative only: the server fills whatever the draft did not
      if (!payload.description) payload.description = form.narrative.value.trim();
      if (!payload.description) {
        if (msg) msg.textContent = "Tuliskan uraian kondisi lapangan dulu.";
        return;
      }
    } else if (!payload.reporter_name || !payload.title || !payload.description || !payload.location_text) {
      if (msg) msg.textContent = "Lengkapi nama, judul, lokasi/wilayah, dan deskripsi laporan.";
      return;
    }

    if (method === "manual_map_pin" && (lat === null || lng === null)) {
      if (msg) msg.textContent = "Untuk pilihan titik peta, latitude dan longitude harus diisi.";
      return;
    }

    function queueOffline() {
      window.RNSync.queueEvent({
        object_type: "community_report",
        operation: "create",
        payload_json: communityReportBridgePayload(payload)
      });
      form.reset();
      form.querySelector("input[name='location_input_method'][value='government_area_select']").checked = true;
      updateLocationMessage();
      if (msg) {
        msg.textContent = "Tidak ada koneksi internet. Laporan disimpan di perangkat ini dan akan " +
          "otomatis terkirim saat online kembali.";
      }
    }

    // No signal at all: don't even attempt the request, queue right away.
    if (!navigator.onLine && window.RNSync) {
      queueOffline();
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
      delete form.dataset.drafted;
      delete form.dataset.intakeParser;
      const mode = document.querySelector(".rn-report-mode")?.hidden ? "form" : "narrative";
      form.querySelector(`input[name='intake_mode'][value='${mode}']`).checked = true;
      setIntakeMode(form, mode);
      const draftBox = document.querySelector("[data-draft-result]");
      if (draftBox) draftBox.hidden = true;
      if (RN_REPORTER && form.reporter_name) form.reporter_name.value = RN_REPORTER.full_name || RN_REPORTER.user;
      updateLocationMessage();
      let successText = `Laporan masuk: ${data.name}. Status: ${data.status || "submitted"}, koordinat: ${data.has_coordinates ? "ada" : "belum ada"}.`;
      successText += data.posko_title
        ? ` Diteruskan ke ${data.posko_title}.`
        : " Belum ada posko yang cocok — menunggu triase Control Centre.";
      if (data.predicted_needs && data.predicted_needs.length) {
        const list = data.predicted_needs
          .map((n) => `${n.predicted_qty} ${n.unit} ${n.label}${n.per_day ? "/hari" : ""}`)
          .join(", ");
        successText += ` Perkiraan kebutuhan (heuristik): ${list}.`;
      }
      if (msg) showMsg(msg, successText, false);
      await loadCommunityReports();
      loadMyReports().catch(() => {});
    } catch (err) {
      // err.status is only set once a response actually came back (see
      // rn-frappe-client.js) — a bare fetch() network failure (offline, DNS,
      // connection reset) throws a plain TypeError with no .status at all.
      // Only THAT case is safe to queue; a real server-side validation
      // error (400/403/500 with a message) must still surface as-is so the
      // citizen can fix the form instead of queuing a request that will
      // fail again identically once it syncs.
      const isNetworkFailure = err.status === undefined;
      if (isNetworkFailure && window.RNSync) {
        queueOffline();
      } else if (msg) {
        showMsg(msg, readableError(err), true);
      }
    }
  });

  updateLocationMessage();
}

/* Same shared badge as the posko pages (RNVerifBadge): status from the Jaringan Verifikator.
   A reporter nobody has vouched for shows no badge. */
/* Wording for a person (the shared posko labels talk about a posko). */
const REPORTER_TEXT = {
  organization_verified: { label: "Terverifikasi organisasi", hint: "Mendaftar lewat organisasi yang terverifikasi, identitasnya dikonfirmasi organisasi" },
  community_verified: { label: "Diverifikasi verifikator", hint: "Dikenal / dijamin oleh verifikator di Jaringan Verifikator" },
  official_verified: { label: "Diverifikasi resmi", hint: "Dijamin oleh 2+ verifikator atau verifikator pemerintah" }
};
function reporterBadgeHtml(status, count) {
  return window.RNVerifBadge ? window.RNVerifBadge.html(status, count, REPORTER_TEXT[status]) : escHtml(status);
}

function isVerified(report) { return (report.reporter_verification_status || "self_reported") !== "self_reported"; }

function verifiedBadge(report) {
  if (!isVerified(report) || !window.RNVerifBadge) return "";
  return ` <button type="button" class="rn-vb-btn" data-reporter-view="level" data-report-id="${report.id}" title="Lihat siapa yang memverifikasi">` +
    reporterBadgeHtml(report.reporter_verification_status, report.reporter_verified_count) + "</button>";
}

function endorsementItem(e) {
  const name = escHtml(e.verifier || "Verifikator");
  const link = e.verifier_id
    ? `<a href="verification-approval.html?cari=${encodeURIComponent(e.verifier || "")}#verifikator/direktori" title="Buka di Verifikasi › Verifikator">${name}</a>` : name;
  const pos = e.position ? ` — ${escHtml(e.position)}` : "";
  return `<li><b>${link}</b>${pos}<br>
    <small>${escHtml(e.role_label || "")} · ${escHtml(e.method_label || "")}${e.verified_at ? " · " + escHtml(e.verified_at) : ""}${e.vouched_via ? " · via " + escHtml(e.vouched_via) : ""}</small>
    ${e.statement ? `<br><small>“${escHtml(e.statement)}”</small>` : ""}</li>`;
}

function verifyFormHtml(d) {
  if (!d.viewer_is_verifier) return "";
  return `
    <form class="rn-rp-verify" data-verify-reporter="${escHtml(d.reporter_account || "")}" data-report-id="${escHtml(d.report)}">
      <div class="rn-rp-title">Verifikasi pelapor ini sebagai verifikator</div>
      <select name="method">
        <option value="site_visit">Kenal langsung / kunjungan</option>
        <option value="network_vouch">Rekomendasi jaringan</option>
        <option value="document_review">Cek dokumen</option>
      </select>
      <input name="vouched_via" placeholder="Direkomendasikan via (wajib untuk rekomendasi jaringan)" hidden>
      <textarea name="statement" rows="2" required minlength="10" placeholder="Bagaimana Anda mengenal pelapor ini? (min. 10 karakter)"></textarea>
      <div class="rn-rp-row"><button class="btn primary mini" type="submit">Verifikasi pelapor</button><span class="rn-muted" data-verify-msg></span></div>
    </form>`;
}

function reporterPanelHtml(d, view) {
  const v = d.verification || { status: "self_reported", count: 0, verifiers: [], evidence: [] };
  const pill = reporterBadgeHtml(v.status, v.count);
  const contact = d.phone
    ? `<a class="btn primary mini" href="${escHtml(d.whatsapp_url)}" target="_blank" rel="noopener">WhatsApp</a>
       <a class="btn mini" href="${escHtml(d.tel_url)}">Telepon ${escHtml(d.phone)}</a>`
    : `<span class="rn-muted">${escHtml(d.reason_no_contact || "Kontak tidak tersedia.")}</span>`;
  const evidence = (v.evidence || []).map((e) =>
    `<li class="${e.ok ? "ok" : "no"}"><b>${escHtml(e.label)}</b> — ${escHtml(e.detail)}</li>`).join("");
  const ends = (v.verifiers || []).map(endorsementItem).join("");
  const contactSection = d.local ? "" : `
    <div class="rn-rp-section" data-section="contact" ${view === "contact" ? "" : "hidden"}>
      <div class="rn-rp-title">Hubungi ${escHtml(d.reporter_name || "pelapor")}</div>
      <div class="rn-rp-row">${contact}</div>
      <small class="rn-muted">Pembukaan kontak ini dicatat. Hubungi hanya untuk keperluan verifikasi laporan.</small>
    </div>`;
  return contactSection + `
    <div class="rn-rp-section" data-section="level" ${view === "level" || d.local ? "" : "hidden"}>
      <div class="rn-rp-title">Verifikasi pelapor: ${pill}</div>
      <div class="rn-rp-title">Diverifikasi oleh</div>
      ${ends ? `<ul class="rn-rp-ends">${ends}</ul>` : `<p class="rn-muted">Belum ada organisasi atau verifikator yang memverifikasi pelapor ini.</p>`}
      ${evidence ? `<ul class="rn-rp-evidence">${evidence}</ul>` : ""}
      <small class="rn-muted">Status mengikuti Jaringan Verifikator yang sama dengan posko.
        <a href="verification-approval.html#verifikator/direktori">Lihat Verifikator</a></small>
      ${verifyFormHtml(d)}
    </div>`;
}

function localPanelData(panel) {
  const l = JSON.parse(panel.dataset.local || "{}");
  return { local: true, verification: { status: l.status || "self_reported", count: l.count || 0,
    verifiers: l.verifiers || [], evidence: [] } };
}

async function toggleReporterPanel(button) {
  const id = button.getAttribute("data-report-id");
  const view = button.getAttribute("data-reporter-view");
  const panel = document.querySelector(`[data-reporter-panel="${CSS.escape(id)}"]`);
  if (!panel) return;
  if (!panel.hidden && panel.dataset.view === view) { panel.hidden = true; return; }
  panel.dataset.view = view;
  panel.hidden = false;
  const privileged = !!button.closest(".community-report-item")?.querySelector('[data-reporter-view="contact"]');
  if (!privileged) { panel.innerHTML = reporterPanelHtml(localPanelData(panel), "level"); return; }
  if (!panel.dataset.loaded) {
    panel.innerHTML = '<span class="rn-muted">Memuat…</span>';
    try {
      const d = await RN_FRAPPE.call("rescue_net.api_reports.reporter_contact", { report: id }, { method: "POST" });
      panel.dataset.data = JSON.stringify(d);
      panel.dataset.loaded = "1";
    } catch (err) {
      panel.innerHTML = `<span class="rn-error">${escHtml(readableError(err))}</span>`;
      return;
    }
  }
  panel.innerHTML = reporterPanelHtml(JSON.parse(panel.dataset.data), view);
}

async function submitVerifyReporter(form) {
  const msg = form.querySelector("[data-verify-msg]");
  const panel = form.closest("[data-reporter-panel]");
  const btn = form.querySelector("button[type=submit]");
  btn.disabled = true;
  showMsg(msg, "Menyimpan…", false);
  try {
    await RN_FRAPPE.call("rescue_net.api_verifier.endorse_reporter", {
      user_account: form.getAttribute("data-verify-reporter"),
      method: form.method.value,
      vouched_via: form.vouched_via.value.trim() || null,
      statement: form.statement.value.trim()
    }, { method: "POST" });
    const d = await RN_FRAPPE.call("rescue_net.api_reports.reporter_contact", { report: form.getAttribute("data-report-id") }, { method: "POST" });
    panel.dataset.data = JSON.stringify(d);
    panel.innerHTML = reporterPanelHtml(d, "level");
  } catch (err) {
    showMsg(msg, readableError(err), true);
    btn.disabled = false;
  }
}

function setupCommunityReportActions() {
  const say = (text, isError) => {
    const box = document.querySelector("[data-community-queue-message]");
    if (!box) return;
    box.textContent = text || "";
    box.classList.toggle("is-error", !!isError);
  };

  document.addEventListener("click", async (e) => {
    const reporterBtn = e.target.closest("[data-reporter-view]");
    if (reporterBtn) { toggleReporterPanel(reporterBtn); return; }
    const more = e.target.closest("[data-queue-more]");
    if (more) {
      const hidden = [...document.querySelectorAll(".community-report-item.is-later")];
      hidden.slice(0, 10).forEach((el) => el.classList.remove("is-later"));
      const left = hidden.length - 10;
      if (left > 0) more.textContent = `Tampilkan lebih banyak (${left} lagi)`; else more.remove();
      return;
    }
    const statusButton = e.target.closest("[data-report-action]");
    const convertButton = e.target.closest("[data-report-convert]");
    const button = statusButton || convertButton;
    if (!button || button.disabled) return;

    const row = button.closest(".community-report-actions");
    const buttons = row ? row.querySelectorAll("button") : [button];
    buttons.forEach((b) => { b.disabled = true; });
    button.classList.add("is-busy");
    try {
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
        say(`Laporan ${id} ditandai ${status}.`);
      } else {
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
        say(`Laporan ${id} dikonversi menjadi kebutuhan logistik.`);
      }
      await loadCommunityReports();
    } catch (err) {
      say(err && err.message ? err.message : "Aksi gagal. Pastikan Anda masuk sebagai operator posko.", true);
      buttons.forEach((b) => { b.disabled = false; });
      button.classList.remove("is-busy");
    }
  });

  document.addEventListener("submit", (e) => {
    const f = e.target.closest("[data-verify-reporter]");
    if (f) { e.preventDefault(); submitVerifyReporter(f); }
  });
  document.addEventListener("change", (e) => {
    const sel = e.target.closest("[data-verify-reporter] select[name=method]");
    if (sel) sel.form.vouched_via.hidden = sel.value !== "network_vouch";
  });

  document.querySelector("[data-community-status-filter]")?.addEventListener("change", loadCommunityReports);
}

document.addEventListener("DOMContentLoaded", () => {
  setupCommunityReportForm();
  setupCommunityReportActions();
  setupFollowUps();
  loadCommunityReports();

  // Reconciliation: a report queued offline gets pushed automatically by
  // rn-sync-engine.js once the device is back online (see rnSetupAutoSync
  // in laporan-masyarakat.html) — refresh the list so it stops showing
  // only the local placeholder state once the real record exists server-side.
  window.addEventListener("rn:sync-complete", () => {
    loadCommunityReports().catch(() => {});
  });
});
