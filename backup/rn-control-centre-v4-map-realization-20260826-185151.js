
"use strict";

const FRAPPE_PREFIX =
  location.origin +
  "/rescue-net-frappe/api/method/";

const DEFAULT_EVENT =
  "event-sim-001";


function svg(path) {
  return `
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="1.8"
      stroke-linecap="round"
      stroke-linejoin="round"
      aria-hidden="true"
    >
      ${path}
    </svg>
  `;
}


const ICONS = {
  dashboard: svg(`
    <rect x="4" y="5" width="16" height="14" rx="2"/>
    <path d="M8 9h8M8 13h3M14 13h2"/>
  `),

  map: svg(`
    <path d="M3 6l6-3 6 3 6-3v15l-6 3-6-3-6 3z"/>
    <path d="M9 3v15M15 6v15"/>
  `),

  home: svg(`
    <path d="M3 11l9-7 9 7"/>
    <path d="M5 10v10h14V10"/>
    <path d="M9 20v-6h6v6"/>
  `),

  package: svg(`
    <path d="M4 7l8-4 8 4-8 4z"/>
    <path d="M4 7v10l8 4 8-4V7"/>
    <path d="M12 11v10"/>
  `),

  truck: svg(`
    <path d="M3 6h11v10H3z"/>
    <path d="M14 10h4l3 3v3h-7z"/>
    <circle cx="7" cy="18" r="2"/>
    <circle cx="18" cy="18" r="2"/>
  `),

  heart: svg(`
    <path d="M20 8c0 5-8 11-8 11S4 13 4 8a4 4 0 017-2 4 4 0 019 2z"/>
    <path d="M8 11h2l1-2 2 5 1-3h2"/>
  `),

  users: svg(`
    <circle cx="9" cy="8" r="3"/>
    <circle cx="17" cy="9" r="2.5"/>
    <path d="M3 20c.5-4 2.5-6 6-6s5.5 2 6 6"/>
    <path d="M14 15c3.5-.5 5.5 1 6 4"/>
  `),

  box: svg(`
    <path d="M4 8h16v12H4z"/>
    <path d="M3 8l3-4h12l3 4"/>
    <path d="M12 4v16"/>
  `),

  clipboard: svg(`
    <rect x="5" y="5" width="14" height="16" rx="2"/>
    <path d="M9 5V3h6v2"/>
    <path d="M9 10h6M9 14h6M9 18h4"/>
  `),

  search: svg(`
    <circle cx="10" cy="10" r="6"/>
    <path d="M15 15l6 6"/>
  `),

  report: svg(`
    <path d="M6 3h9l3 3v15H6z"/>
    <path d="M14 3v4h4"/>
    <path d="M9 11h6M9 15h6"/>
  `),

  menu: svg(`
    <path d="M4 7h16M4 12h16M4 17h16"/>
  `),

  bell: svg(`
    <path d="M6 17h12l-2-3V9a4 4 0 00-8 0v5z"/>
    <path d="M10 20h4"/>
  `),

  pin: svg(`
    <path d="M12 21s6-5 6-11a6 6 0 10-12 0c0 6 6 11 6 11z"/>
    <circle cx="12" cy="10" r="2"/>
  `),

  share: svg(`
    <circle cx="18" cy="5" r="2"/>
    <circle cx="6" cy="12" r="2"/>
    <circle cx="18" cy="19" r="2"/>
    <path d="M8 11l8-5M8 13l8 5"/>
  `),

  road: svg(`
    <path d="M9 3L7 21M15 3l2 18"/>
    <path d="M12 4v3M12 10v4M12 17v3"/>
  `),

  "people-risk": svg(`
    <circle cx="8" cy="7" r="2.5"/>
    <circle cx="16" cy="7" r="2.5"/>
    <path d="M3 17c.5-4 2-6 5-6s4.5 2 5 6"/>
    <path d="M11 17c.5-4 2-6 5-6s4.5 2 5 6"/>
  `),
};


function mountIcons() {
  document
    .querySelectorAll("[data-icon]")
    .forEach(el => {
      el.innerHTML =
        ICONS[el.dataset.icon]
        || ICONS.dashboard;
    });
}


function safe(v) {
  return String(
    v ?? ""
  ).replace(
    /[&<>"']/g,
    ch => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#039;",
    }[ch])
  );
}


function setText(id, value) {
  const el =
    document.getElementById(id);

  if (el) {
    el.textContent =
      value ?? "-";
  }
}


function normalizeEventId(value) {
  return String(
    value || ""
  ).replace(
    /^disaster_events:/,
    ""
  );
}


function getEventId() {
  const url =
    new URL(location.href);

  return normalizeEventId(
    url.searchParams.get("event")
    || DEFAULT_EVENT
  );
}


async function frappeCall(
  method,
  params = {}
) {
  const url =
    new URL(
      FRAPPE_PREFIX + method
    );

  for (
    const [key, value]
    of Object.entries(params)
  ) {
    if (
      value !== undefined
      && value !== null
    ) {
      url.searchParams.set(
        key,
        value
      );
    }
  }

  const res =
    await fetch(
      url,
      {
        credentials: "omit"
      }
    );

  const text =
    await res.text();

  let payload = null;

  try {
    payload =
      JSON.parse(text);
  } catch {
    throw new Error(
      "Frappe returned non-JSON: "
      + text.slice(0, 180)
    );
  }

  if (!res.ok) {
    throw new Error(
      payload?.exception
      || payload?.message
      || `HTTP ${res.status}`
    );
  }

  return payload.message;
}


async function loadActiveDisasters() {
  const rows =
    await frappeCall(
      "rescue_net.api_ai.public_active_disasters"
    );

  const select =
    document.getElementById(
      "activeEventSelect"
    );

  if (!select) {
    return [];
  }

  const active =
    Array.isArray(rows)
      ? rows
      : [];

  const current =
    getEventId();

  select.innerHTML =
    active.map(row => {
      const id =
        normalizeEventId(
          row.legacy_id
          || row.id
          || row.name
        );

      const selected =
        id === current
          ? " selected"
          : "";

      return `
        <option
          value="${safe(id)}"
          ${selected}
        >
          ${safe(row.title || id)}
        </option>
      `;
    }).join("");

  select.addEventListener(
    "change",
    () => {
      const url =
        new URL(
          location.href
        );

      url.searchParams.set(
        "event",
        select.value
      );

      location.href =
        url.toString();
    },
    {
      once: true
    }
  );

  return active;
}


function formatNumber(n) {
  const num =
    Number(n);

  if (
    !Number.isFinite(num)
  ) {
    return "-";
  }

  return new Intl.NumberFormat(
    "id-ID",
    {
      maximumFractionDigits: 1
    }
  ).format(num);
}


function firstNumber(
  object,
  keys,
  fallback = 0
) {
  for (const key of keys) {
    const value =
      Number(object?.[key]);

    if (
      Number.isFinite(value)
    ) {
      return value;
    }
  }

  return fallback;
}


function statusLabel(
  count,
  good = "Siap",
  bad = "Kritis"
) {
  return Number(count || 0) > 0
    ? bad
    : good;
}


function renderHeader(
  ctx,
  eventId
) {
  const disaster =
    ctx.disaster || {};

  const title =
    disaster.title
    || disaster.disaster_name
    || disaster.name
    || eventId;

  const severity =
    disaster.severity
    || "-";

  setText(
    "disasterName",
    title
  );

  setText(
    "mobileDisasterName",
    title
  );

  setText(
    "severityBadge",
    severity === "critical"
      ? "Siaga Tingkat Tinggi"
      : severity
  );

  setText(
    "mapTitle",
    `Peta Situasi ${title}`
  );

  const updated =
    ctx.generated_at
    || new Date().toISOString();

  setText(
    "lastUpdated",
    updated
  );

  setText(
    "sidebarUpdated",
    updated
  );

  setText(
    "lastUpdateRelative",
    "baru saja"
  );
}


function renderKpis(ctx) {
  const s =
    ctx.summary || {};

  const alerts =
    ctx.alerts || [];

  const criticalAlerts =
    alerts.filter(a =>
      String(
        a.severity
        || a.priority
        || ""
      ).toLowerCase()
      === "critical"
    ).length;

  const openNeeds =
    firstNumber(
      s,
      [
        "open_logistic_need_count",
        "logistic_need_count"
      ]
    );

  const shelterNeeds =
    firstNumber(
      s,
      [
        "shelter_need_count"
      ]
    );

  const posko =
    firstNumber(
      s,
      [
        "posko_count",
        "active_posko_count"
      ]
    );

  const flows =
    firstNumber(
      s,
      [
        "distribution_flow_count"
      ]
    );

  const medical =
    firstNumber(
      s,
      [
        "medical_case_count"
      ]
    );

  const aid =
    firstNumber(
      s,
      [
        "aid_offer_count"
      ]
    );

  /*
   * Do not invent unavailable metrics.
   * We use nearest live operational signals
   * and label them as live data.
   */
  setText(
    "kpiRisk",
    formatNumber(
      openNeeds + shelterNeeds
    )
  );

  setText(
    "kpiPoskoCritical",
    formatNumber(
      criticalAlerts || posko
    )
  );

  setText(
    "kpiAidFlow",
    formatNumber(flows)
  );

  setText(
    "kpiBlockedDistribution",
    formatNumber(
      alerts.filter(a =>
        /distribution|route|akses|jalan/i.test(
          `${a.type || ""} ${a.message || ""}`
        )
      ).length
    )
  );

  setText(
    "kpiMedicalOverload",
    formatNumber(medical)
  );

  setText(
    "kpiDonation",
    formatNumber(aid)
  );
}


function renderPriority(ctx) {
  const target =
    document.getElementById(
      "priorityDecisionList"
    );

  if (!target) {
    return;
  }

  const recommendations =
    Array.isArray(
      ctx.recommendations
    )
      ? ctx.recommendations
      : [];

  const alerts =
    Array.isArray(
      ctx.alerts
    )
      ? ctx.alerts
      : [];

  const items = [
    ...recommendations.map(
      (row, index) => ({
        title:
          row.title
          || row.recommendation
          || row.message
          || `Recommendation ${index + 1}`,

        detail:
          row.description
          || row.reason
          || "",

        priority:
          row.priority
          || row.severity
          || "tinggi"
      })
    ),

    ...alerts.map(
      row => ({
        title:
          row.title
          || row.message
          || row.type
          || "Alert",

        detail:
          row.description
          || row.detail
          || "",

        priority:
          row.priority
          || row.severity
          || "kritis"
      })
    )
  ].slice(0, 5);

  if (!items.length) {
    target.innerHTML =
      `<div class="cc-empty">
        Belum ada prioritas keputusan.
      </div>`;
    return;
  }

  target.innerHTML =
    items.map(
      (row, index) => `
        <div class="cc-priority-item">
          <span class="cc-priority-number">
            ${index + 1}
          </span>

          <div>
            <strong>
              ${safe(row.title)}
            </strong>

            <p>
              ${safe(row.detail)}
            </p>
          </div>

          <span class="cc-priority-tag">
            ${safe(row.priority)}
          </span>
        </div>
      `
    ).join("");
}


function renderCriticalNeeds(ctx) {
  const body =
    document.getElementById(
      "criticalNeedsBody"
    );

  if (!body) {
    return;
  }

  const stock = {};

  for (
    const row
    of (
      ctx.stock_summary
      || []
    )
  ) {
    const key =
      String(
        row.item_name
        || ""
      ).toLowerCase();

    stock[key] =
      (
        stock[key]
        || 0
      )
      + Number(
        row.current_quantity
        || row.quantity
        || 0
      );
  }

  const priorityRank = {
    critical: 0,
    urgent: 1,
    high: 1,
    normal: 2,
    low: 3
  };

  const rows =
    (
      ctx.logistic_needs
      || []
    )
      .filter(
        row =>
          ![
            "fulfilled",
            "closed",
            "cancelled"
          ].includes(
            String(
              row.status
              || ""
            ).toLowerCase()
          )
      )
      .sort(
        (a, b) =>
          (
            priorityRank[
              a.priority
            ]
            ?? 9
          )
          -
          (
            priorityRank[
              b.priority
            ]
            ?? 9
          )
      )
      .slice(0, 6);

  if (!rows.length) {
    body.innerHTML = `
      <tr>
        <td colspan="4">
          Belum ada kebutuhan kritis terbuka.
        </td>
      </tr>
    `;
    return;
  }

  body.innerHTML =
    rows.map(row => {
      const item =
        row.item_name
        || row.item_text
        || row.need_name
        || "Kebutuhan";

      const required =
        Number(
          row.quantity_required
          || row.quantity
          || row.required_quantity
          || 0
        );

      const available =
        Number(
          stock[
            String(item)
            .toLowerCase()
          ]
          || 0
        );

      const gap =
        Math.max(
          0,
          required
          - available
        );

      return `
        <tr>
          <td>
            ${safe(item)}
          </td>

          <td>
            ${formatNumber(required)}
          </td>

          <td>
            ${formatNumber(available)}
          </td>

          <td>
            ${formatNumber(gap)}
          </td>
        </tr>
      `;
    }).join("");
}


function renderEvidence(ctx) {
  const target =
    document.getElementById(
      "latestEvidenceList"
    );

  if (!target) {
    return;
  }

  const evidence =
    (
      ctx.evidence
      || ctx.latest_evidence
      || []
    )
    .slice(0, 3);

  if (!evidence.length) {
    target.innerHTML = `
      <div class="cc-empty">
        Belum ada bukti lapangan publik
        untuk event ini.
      </div>
    `;
    return;
  }

  target.innerHTML =
    evidence.map(row => {
      const image =
        row.file_url
        || row.image_url
        || "";

      const title =
        row.caption
        || row.title
        || row.evidence_type
        || "Bukti Lapangan";

      const detail =
        row.description
        || row.location_text
        || row.source
        || "";

      const time =
        row.observed_at
        || row.created_at
        || "";

      return `
        <div class="cc-evidence-item">

          <div class="cc-evidence-thumb">
            ${
              image
                ? `<img src="${safe(image)}" alt="">`
                : ""
            }
          </div>

          <div class="cc-evidence-content">
            <small>
              ${safe(time)}
            </small>

            <strong>
              ${safe(title)}
            </strong>

            <span>
              ${safe(detail)}
            </span>
          </div>

        </div>
      `;
    }).join("");
}


function renderModules(ctx) {
  const s =
    ctx.summary || {};

  const stocks =
    ctx.stock_summary
    || [];

  const stockTotal =
    stocks.reduce(
      (sum, row) =>
        sum
        + Number(
          row.current_quantity
          || row.quantity
          || 0
        ),
      0
    );

  const flows =
    firstNumber(
      s,
      ["distribution_flow_count"]
    );

  const medical =
    firstNumber(
      s,
      ["medical_case_count"]
    );

  const volunteers =
    firstNumber(
      s,
      [
        "volunteer_count",
        "active_volunteer_count"
      ]
    );

  const programs =
    firstNumber(
      s,
      [
        "donor_program_count",
        "program_count"
      ]
    );

  const missing =
    firstNumber(
      s,
      ["missing_person_count"]
    );

  const found =
    firstNumber(
      s,
      ["found_person_count"]
    );

  setText(
    "moduleLogisticsValue",
    formatNumber(stockTotal)
  );

  setText(
    "moduleLogisticsDetail",
    stocks.length
      ? `${stocks.length} item stok tercatat`
      : "Belum ada stok tercatat"
  );

  setText(
    "moduleLogisticsStatus",
    stockTotal > 0
      ? "Waspada"
      : "Belum Ada"
  );


  setText(
    "moduleDistributionValue",
    formatNumber(flows)
  );

  setText(
    "moduleDistributionDetail",
    `${flows} flow tercatat`
  );

  setText(
    "moduleDistributionStatus",
    flows > 0
      ? "Berjalan"
      : "Belum Ada"
  );


  setText(
    "moduleMedicalValue",
    formatNumber(medical)
  );

  setText(
    "moduleMedicalDetail",
    `${medical} kasus medis`
  );

  setText(
    "moduleMedicalStatus",
    statusLabel(
      medical,
      "Siap",
      "Kritis"
    )
  );


  setText(
    "moduleVolunteerValue",
    formatNumber(volunteers)
  );

  setText(
    "moduleVolunteerDetail",
    volunteers
      ? "Relawan aktif"
      : "Belum ada relawan"
  );

  setText(
    "moduleVolunteerStatus",
    volunteers > 0
      ? "Siap"
      : "Belum Ada"
  );


  setText(
    "moduleProgramValue",
    formatNumber(programs)
  );

  setText(
    "moduleProgramDetail",
    `${programs} program tercatat`
  );

  setText(
    "moduleProgramStatus",
    programs > 0
      ? "Berjalan"
      : "Belum Ada"
  );


  setText(
    "moduleSearchValue",
    formatNumber(
      missing + found
    )
  );

  setText(
    "moduleSearchDetail",
    `${missing} masih dicari`
  );

  setText(
    "moduleSearchStatus",
    missing > 0
      ? "Aktif"
      : "Siap"
  );
}


function configureMap(eventId) {
  const frame =
    document.getElementById(
      "situationMap"
    );

  if (!frame) {
    return;
  }

  frame.src =
    "map.html?event="
    + encodeURIComponent(
      eventId
    )
    + "&embedded=war-room";
}


function setupShare() {
  const button =
    document.getElementById(
      "shareButton"
    );

  if (!button) {
    return;
  }

  button.addEventListener(
    "click",
    async () => {
      const data = {
        title:
          document.title,

        text:
          document.getElementById(
            "disasterName"
          )?.textContent
          || "Rescue-Net Control Centre",

        url:
          location.href
      };

      if (
        navigator.share
      ) {
        try {
          await navigator.share(
            data
          );
          return;
        } catch {}
      }

      try {
        await navigator.clipboard
          .writeText(
            location.href
          );

        button.textContent =
          "Tautan disalin";

        setTimeout(
          () => {
            button.innerHTML =
              `${ICONS.share} Bagikan Situasi`;
          },
          1600
        );
      } catch {}
    }
  );
}


async function loadControlCentre() {
  setText(
    "warRoomStatus",
    "Memuat data Frappe..."
  );

  await loadActiveDisasters();

  const eventId =
    getEventId();

  configureMap(
    eventId
  );

  const ctx =
    await frappeCall(
      "rescue_net.api_ai.public_context",
      {
        disaster_event_id:
          eventId
      }
    );

  renderHeader(
    ctx,
    eventId
  );

  renderKpis(ctx);
  renderPriority(ctx);
  renderCriticalNeeds(ctx);
  renderEvidence(ctx);
  renderModules(ctx);

  setText(
    "warRoomStatus",
    `Loaded: ${
      ctx.generated_at
      || new Date().toISOString()
    }`
  );
}


document.addEventListener(
  "DOMContentLoaded",
  () => {
    mountIcons();
    setupShare();

    loadControlCentre()
      .catch(err => {
        console.error(
          "CONTROL_CENTRE_V4_FAIL",
          err
        );

        setText(
          "warRoomStatus",
          `Gagal memuat: ${err.message}`
        );
      });
  }
);
