const RN_FRAPPE_BASE = location.origin + "/rescue-net-frappe/api/method";
let RN_FRAPPE_SESSION = null;

function getEventId() {
  const params = new URLSearchParams(window.location.search);
  return params.get("event") || params.get("id") || "event-sim-001";
}

function safe(v) {
  return v === null || v === undefined || v === "" ? "n/a" : v;
}

function setText(id, value) {
  const el = document.getElementById(id);
  if (el) el.textContent = value;
}

async function frappeCall(method, args = {}, write = false) {
  let url = `${RN_FRAPPE_BASE}/${method}`;

  const headers = {
    "Accept": "application/json"
  };

  const options = {
    credentials: "same-origin",
    headers
  };

  if (write) {
    if (!RN_FRAPPE_SESSION?.csrf_token) {
      throw new Error("Frappe session belum siap.");
    }

    headers["Content-Type"] = "application/json";
    headers["X-Frappe-CSRF-Token"] = RN_FRAPPE_SESSION.csrf_token;

    options.method = "POST";
    options.body = JSON.stringify(args);
  } else {
    const query = new URLSearchParams();

    Object.entries(args).forEach(([key, value]) => {
      if (value !== null && value !== undefined && value !== "") {
        query.set(key, value);
      }
    });

    if (query.toString()) {
      url += "?" + query.toString();
    }
  }

  const res = await fetch(url, options);
  const raw = await res.text();
  let data = {};
  try { data = raw ? JSON.parse(raw) : {}; } catch (_) {
    if (/^\s*<(?:!doctype|html)/i.test(raw || "")) {
      const e = new Error("Server sedang tidak tersedia (mungkin restart). Coba lagi sebentar.");
      e.transient = true;
      throw e;
    }
  }

  if (!res.ok) {
    const clean = String(data.message || data.exception || ("Frappe API error " + res.status))
      .replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
    const e = new Error(res.status === 403 ? "Perlu login untuk fitur ini." : clean);
    e.status = res.status;
    throw e;
  }

  return Object.prototype.hasOwnProperty.call(data, "message")
    ? data.message
    : data;
}

async function ensureSession() {
  if (RN_FRAPPE_SESSION) return RN_FRAPPE_SESSION;

  RN_FRAPPE_SESSION = await frappeCall(
    "rescue_net.api_ai.session_info"
  );

  const form = document.getElementById("aiAskForm");

  if (form?.user_id) {
    form.user_id.value = RN_FRAPPE_SESSION.user;
    form.user_id.readOnly = true;
  }

  return RN_FRAPPE_SESSION;
}

/* 2026-11-17 owner: "ai analisis harus bisa diklik ke object yang disarankan
   atau dikatakan". Peta link {type,id,posko,...} dari server -> halaman RN,
   plus registri ID/nama obyek supaya teks jawaban AI ikut jadi tautan. */
const RNAiLinks = (function () {
  const escH = s => String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const ev = () => String(getEventId() || "").replace(/^disaster_events:/, "");
  const abs = rel => { try { return new URL(rel, location.href).href; } catch (e) { return rel; } };
  const q = obj => Object.entries(obj).filter(([, v]) => v !== null && v !== undefined && v !== "")
    .map(([k, v]) => encodeURIComponent(k) + "=" + encodeURIComponent(v)).join("&");
  const KATEGORI = {
    logistics: "management-distribusi.html", distribution: "management-distribusi.html",
    transport: "management-distribusi.html", medical: "posko-medis-detail.html",
    shelter: "shelter-detail.html", kitchen: "dapur-umum.html",
  };

  // link -> {href, label} (label = teks tombol). null bila tidak ada tujuan.
  function target(link) {
    if (!link || typeof link !== "object") return null;
    const e = ev();
    switch (link.type) {
      case "posko":
        return link.id ? { href: "posko-detail.html?" + q({ id: link.id }), label: "Buka posko" } : null;
      case "logistic_need":
        if (link.posko) return { href: "posko-logistik.html?" + q({ id: link.posko, item: link.item, event: e }), label: "Buka kartu stok di " + (link.posko_name || "posko") };
        return { href: "kebutuhan-publik.html?" + q({ event: e }), label: "Buka daftar kebutuhan" };
      case "shelter_need":
        return link.posko ? { href: "shelter-detail.html?" + q({ id: link.posko }), label: "Buka shelter" } : null;
      case "open_needs":
        return { href: "kebutuhan-publik.html?" + q({ event: e }), label: "Lihat semua kebutuhan" };
      case "resource":
        return link.id ? { href: "penyedia-alat.html?" + q({ id: link.id, event: e }), label: "Buka alat" } : null;
      case "resource_list":
        if (link.id) return { href: "penyedia-alat.html?" + q({ id: link.id, event: e }), label: "Buka alat" };
        return { href: "alat-kerja.html?" + q({ event: e }) + "#penyedia", label: "Lihat daftar alat & penyedia" };
      case "recovery_project":
        return { href: "alat-kerja.html?" + q({ event: e, proyek: link.id }) + "#recovery", label: "Buka proyek" };
      case "recovery_list":
        return { href: "alat-kerja.html?" + q({ event: e }) + "#recovery", label: "Lihat proyek recovery" };
      case "action_plan": {
        if (link.posko) return { href: "posko-detail.html?" + q({ id: link.posko }), label: "Buka " + (link.posko_name || "posko") };
        const page = KATEGORI[String(link.category || "").toLowerCase()];
        return page ? { href: page + "?" + q({ event: e }), label: "Buka halaman " + String(link.category).toLowerCase() } : null;
      }
      case "page":
        return link.href ? { href: link.href, label: link.label || "Buka" } : null;
    }
    return null;
  }

  // Registri obyek dari konteks AI: ID & nama -> tautan.
  let REG = new Map(), RX = null;
  function add(key, link, minLen) {
    key = String(key || "").trim();
    if (!key || key.length < (minLen || 3) || REG.has(key.toLowerCase())) return;
    const t = target(link);
    if (t) REG.set(key.toLowerCase(), { href: abs(t.href), label: t.label });
  }
  function register(ctx) {
    REG = new Map();
    (ctx.poskos || []).forEach(p => {
      const l = { type: "posko", id: p.name };
      add(p.name, l); add(p.legacy_id, l); add(p.title || p.posko_name, l, 6);
    });
    (ctx.logistic_needs || []).forEach(n => add(n.name, { type: "logistic_need", id: n.name, posko: n.posko, posko_name: n.posko_name, item: n.item_name }));
    (ctx.shelter_needs || []).forEach(n => add(n.name, { type: "shelter_need", id: n.name, posko: n.posko }));
    (ctx.resource_profiles || []).forEach(r => { const l = { type: "resource", id: r.name }; add(r.name, l); add(r.resource_name, l, 8); });
    (ctx.recovery_projects || []).forEach(p => { const l = { type: "recovery_project", id: p.name }; add(p.name, l); add(p.project_name, l, 8); });
    (ctx.recommendations || []).forEach(r => { if (r && r.link && r.link.id) add(r.link.id, r.link); });
    const keys = [...REG.keys()].sort((a, b) => b.length - a.length).map(k => escH(k).replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
    try {
      RX = keys.length ? new RegExp("(?<![\\w-])(" + keys.join("|") + ")(?![\\w-])", "gi") : null;
    } catch (e) { RX = null; } // browser lama tanpa lookbehind: teks tetap tampil, tanpa tautan
  }
  // Tambah tautan pada HTML yang SUDAH di-escape (tanpa tag).
  function linkify(escaped) {
    let out = String(escaped || "");
    if (RX) {
      out = out.replace(RX, m => {
        const raw = m.replace(/&amp;/g, "&").replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&quot;/g, '"').replace(/&#39;/g, "'");
        const hit = REG.get(raw.toLowerCase());
        return hit ? `<a class="rn-ai-ref" href="${escH(hit.href)}" title="${escH(hit.label)}">${m}</a>` : m;
      });
    }
    // ID posko/alat yang belum terdaftar tetap bisa diklik.
    return out.replace(/(^|[^\w>"=\/-])((?:SIM-[A-Z0-9]+-POSKO-[A-Z0-9-]+)|(?:rn-posko-[a-f0-9]{8,})|(?:rn-resource-[a-f0-9]{8,}))(?![\w-])/g, (all, pre, id) => {
      const t = target(id.startsWith("rn-resource-") ? { type: "resource", id } : { type: "posko", id });
      return pre + `<a class="rn-ai-ref" href="${escH(abs(t.href))}" title="${escH(t.label)}">${id}</a>`;
    });
  }
  return { target, register, linkify, abs };
})();
window.RNAiLinks = RNAiLinks;

function card(title, body, chip = "", link = null) {
  const t = RNAiLinks.target(link);
  const href = t ? RNUI.esc(t.href) : "";
  return `
    <article class="event-card${t ? " rn-ai-klik" : ""}">
      <div class="event-main">
        <div>
          <h4>${t ? `<a class="rn-ai-judul" href="${href}">${title}</a>` : title}</h4>
          <p>${body}</p>
          ${t ? `<a class="rn-ai-buka" href="${href}">${RNUI.esc(t.label)} →</a>` : ""}
        </div>
        <div class="chips">${chip ? `<span class="chip warning">${chip}</span>` : ""}</div>
      </div>
    </article>
  `;
}

function buildOperationalRecommendations(ctx, resources, recoveryProjects) {
  const s = ctx.summary || {};
  const recommendations = [];

  const unavailableResources = resources.filter(r => {
    const status = r.availability_status || r.status || "";
    return status && status !== "available";
  });
  const transportAssets = resources.filter(r => ["transport", "vehicle"].includes(String(r.resource_type || r.category || "").toLowerCase()));
  const medicalAssets = resources.filter(r => String(r.resource_type || r.category || "").toLowerCase().includes("medical"));
  const recoveryActive = recoveryProjects.filter(p => !["completed", "cancelled"].includes(String(p.status || "").toLowerCase()));

  if (Number(s.open_need_count ?? s.open_needs_count ?? 0) > 0 && transportAssets.length > 0) {
    recommendations.push({ text: `Gunakan ${transportAssets.length} aset transport terdaftar untuk prioritas open logistic needs. Cocokkan kapasitas dan PIC sebelum assignment.`, link: { type: "resource_list" } });
  }

  if (Number(s.medical_case_count || 0) > 0 && medicalAssets.length > 0) {
    recommendations.push({ text: `Ada ${s.medical_case_count} kasus medis dan ${medicalAssets.length} resource medis terdata. Prioritaskan ketersediaan stok medis dan rujukan pasien berat.`, link: { type: "page", href: "posko-medis-detail.html?event=" + encodeURIComponent(getEventId()), label: "Buka Posko Medis" } });
  }

  if (unavailableResources.length > 0) {
    recommendations.push({ text: `${unavailableResources.length} resource tidak available. Command center perlu cek status ketersediaan sebelum membuat rencana distribusi.`, link: { type: "resource_list", id: unavailableResources.length === 1 ? unavailableResources[0].name : null } });
  }

  if (recoveryActive.length > 0) {
    recommendations.push({ text: `${recoveryActive.length} recovery/reconstruction project aktif. Sinkronkan kebutuhan alat kerja, relawan teknis, evidence, dan verifikasi progress.`, link: recoveryActive.length === 1 ? { type: "recovery_project", id: recoveryActive[0].name } : { type: "recovery_list" } });
  }

  if (Number(s.shelter_need_count || 0) > 0 && Number(s.shelter_occupancy_count || 0) > 0) {
    recommendations.push({ text: `Shelter memiliki kebutuhan terbuka. Bandingkan occupancy, kapasitas, air, sanitasi, dan distribusi bantuan sebelum perpindahan pengungsi.`, link: { type: "page", href: "shelter-detail.html?event=" + encodeURIComponent(getEventId()), label: "Buka Shelter" } });
  }

  return recommendations;
}

function renderResourceRecoverySources(resources, recoveryProjects) {
  const e = v => RNUI.esc(safe(v));
  const resourceCards = resources.slice(0, 8).map(r => card(
    e(r.resource_name),
    `Type: ${e(r.resource_type)}<br>Owner: ${e(r.owner_type)} / ${e(r.owner_id)}<br>Status: ${e(r.availability_status || r.status)}<br>Capacity: ${e(r.capacity_description)}`,
    "resource",
    { type: "resource", id: r.name }
  ));

  const recoveryCards = recoveryProjects.slice(0, 8).map(p => card(
    e(p.project_name),
    `Type: ${e(p.project_type)}<br>Location: ${e(p.location)}<br>Progress: ${e(p.progress_percent)}%<br>Status: ${e(p.status)}`,
    "recovery",
    { type: "recovery_project", id: p.name }
  ));

  return [...resourceCards, ...recoveryCards];
}

async function loadAiContext() {
  const eventId = getEventId();
  setText("aiStatus", "Memuat konteks AI…");

  // public_context is guest-safe (aggregate only); the "Tanya AI" form still
  // requires login. Don't gate the whole dashboard on a session.
  const ctx = await frappeCall(
    "rescue_net.api_ai.public_context",
    {
      disaster_event_id: eventId
    }
  );

  const resources = ctx.resource_profiles || [];
  const recoveryProjects = ctx.recovery_projects || [];
  const s = ctx.summary || {};
  RNAiLinks.register(ctx);
  const operationalRecommendations = buildOperationalRecommendations(ctx, resources || [], recoveryProjects || []);
  const combinedRecommendations = [
    ...(ctx.recommendations || []),
    ...operationalRecommendations
  ];

  setText("aiKpiPosko", safe(s.posko_count));
  setText(
    "aiKpiNeeds",
    Number(s.open_need_count ?? s.open_needs_count ?? 0)
  );
  setText("aiKpiAlerts", (ctx.alerts || []).length);
  setText(
    "aiKpiPrograms",
    Number(s.program_count || 0) +
    Number(recoveryProjects.length || 0)
  );

  document.getElementById("aiAlerts").innerHTML = (ctx.alerts || []).length
    ? ctx.alerts.slice(0, 10).map(a => card(
        RNUI.esc(safe(a.type)),
        RNAiLinks.linkify(RNUI.esc(safe(a.message))),
        RNUI.esc(safe(a.level || "alert")),
        a.link
      )).join("")
    : card("No alerts", "Belum ada alert.", "ok");

  document.getElementById("aiRecommendations").innerHTML = combinedRecommendations.length
    ? combinedRecommendations.map((r, i) => {
        // Rekomendasi dari server berupa objek {title, reason, priority}; operasional berupa teks.
        const esc = RNUI.esc;
        const sumber = i < (ctx.recommendations || []).length ? "AI" : "Ops";
        if (r && typeof r === "object") {
          const judul = r.title || r.message || `Rekomendasi ${i + 1}`;
          const alasan = r.reason || r.detail || r.description || "";
          const chip = r.priority ? `${sumber} · ${r.priority}` : sumber;
          if (r.text) return card(`${i + 1}. Saran operasional`, esc(r.text), sumber, r.link);
          return card(`${i + 1}. ${esc(judul)}`, esc(alasan), esc(chip), r.link);
        }
        return card(`${i + 1}. Saran operasional`, esc(r), sumber);
      }).join("")
    : card("No recommendation", "Belum ada rekomendasi.", "empty");

  const sourceCards = (ctx.sources || []).slice(0, 20).map(src => card(
        RNUI.esc(safe(src.source_table)),
        `ID: ${RNAiLinks.linkify(RNUI.esc(safe(src.source_id)))}`,
        "source"
      ));
  const resourceRecoveryCards = renderResourceRecoverySources(resources || [], recoveryProjects || []);

  document.getElementById("aiSources").innerHTML = (sourceCards.length || resourceRecoveryCards.length)
    ? [...sourceCards, ...resourceRecoveryCards].join("")
    : card("No sources", "Belum ada source.", "empty");

  setText("aiStatus", `AI context loaded: ${safe(ctx.generated_at)} | resources=${(resources || []).length} | recovery=${(recoveryProjects || []).length}`);
}

function setupAiAsk() {
  const form = document.getElementById("aiAskForm");
  if (!form) return;

  // Context picker: personal key or one of the user's organisations (only shown with a real choice).
  RNUI.aiContext(frappeCall).then(ctx => {
    const orgs = (ctx.contexts && ctx.contexts.organizations) || [];
    const personal = ctx.contexts && ctx.contexts.personal && ctx.contexts.personal.available;
    if (!orgs.length) return;
    const sel = document.createElement("select");
    sel.name = "ai_ctx";
    sel.innerHTML = (personal ? '<option value="personal">AI pribadi (kunci saya)</option>' : "")
      + orgs.map(o => `<option value="${RNUI.esc(o.id)}">AI organisasi: ${RNUI.esc(o.title)}</option>`).join("");
    sel.value = ctx.organization_id || "personal";
    sel.addEventListener("change", () => { try { localStorage.setItem("rn_ai_ctx", sel.value); } catch (e) {} });
    const label = document.createElement("label");
    label.append("Konteks AI ", sel);
    form.insertBefore(label, form.querySelector("button"));
  });

  form.addEventListener("submit", async e => {
    e.preventDefault();
    setText("aiAnswer", "Asking AI...");

    try {
      const session = await ensureSession();
      const ctx = await RNUI.aiContext(frappeCall);
      const picked = form.ai_ctx ? form.ai_ctx.value : ctx.organization_id;

      const res = await frappeCall(
        "rescue_net.api_ai.ask",
        {
          user_id: session.user,
          disaster_event_id: getEventId(),
          provider: "auto",
          organization_id: picked && picked !== "personal" ? picked : "",
          question: form.question.value.trim()
        },
        true
      );

      const jawab = String(res.answer || res.message || JSON.stringify(res, null, 2));
      const box = document.getElementById("aiAnswer");
      if (box) { box.style.whiteSpace = "pre-wrap"; box.innerHTML = RNAiLinks.linkify(RNUI.esc(jawab)); }
    } catch (err) {
      setText("aiAnswer", err.message);
    }
  });
}

document.addEventListener("DOMContentLoaded", () => {
  setupAiAsk();

  const refresh = document.getElementById("refreshAiContext");
  if (refresh) refresh.addEventListener("click", () => loadAiContext().catch(err => setText("aiStatus", err.message)));

  loadAiContext().catch(err => setText("aiStatus", err.message));
});
