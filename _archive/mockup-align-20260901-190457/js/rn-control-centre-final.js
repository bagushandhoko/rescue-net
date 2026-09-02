"use strict";


const RN_SERVER =
  location.origin;

const API =
  RN_SERVER +
  "/rescue-net-frappe/api/method/";


let mapInstance = null;


function safe(value) {
  return String(
    value ?? ""
  ).replace(
    /[&<>"']/g,
    c => ({
      "&":"&amp;",
      "<":"&lt;",
      ">":"&gt;",
      '"':"&quot;",
      "'":"&#039;"
    }[c])
  );
}


function setText(
  id,
  value
) {
  const el =
    document.getElementById(id);

  if (el) {
    el.textContent =
      value ?? "-";
  }
}


function eventId() {
  const url =
    new URL(
      location.href
    );

  return String(
    url.searchParams.get("event")
    || "event-sim-001"
  ).replace(
    /^disaster_events:/,
    ""
  );
}


/* Make a KPI / module card open its follow-up page,
   carrying the active disaster event. */
function linkCard(
  startEl,
  href,
  extraParams,
  hint
) {
  const card =
    startEl
    && startEl.closest("article");

  if (!card || card.dataset.linked) {
    return;
  }

  card.dataset.linked = "1";

  const url =
    new URL(
      href,
      location.href
    );

  url.searchParams.set(
    "event",
    eventId()
  );

  Object.entries(
    extraParams || {}
  ).forEach(
    ([key, value]) =>
      url.searchParams.set(key, value)
  );

  const target =
    url.toString();

  card.classList.add("cc-clickable");
  card.setAttribute("role", "link");
  card.setAttribute("tabindex", "0");
  card.title =
    hint
    || "Buka detail untuk ditindaklanjuti";

  function go() {
    location.href = target;
  }

  card.addEventListener("click", go);

  card.addEventListener(
    "keydown",
    event => {
      if (
        event.key === "Enter"
        || event.key === " "
      ) {
        event.preventDefault();
        go();
      }
    }
  );
}


/* ==========================================================
   KPI / module drill-down — Rescue-Net integrates data from
   many groups. Clicking a figure opens the underlying list of
   items / objects / situations, grouped by organisation; a
   closed organisation contributes only its summary.
   ========================================================== */

const DRILL_MODULE = {
  kebutuhan: "posko-logistik.html?focus=kebutuhan",
  posko_kritis: "organisasi-posko.html?status=critical",
  distribusi: "management-distribusi.html?focus=flow",
  distribusi_terhambat: "management-distribusi.html?focus=pickup",
  medis: "posko-medis-detail.html?focus=cases",
  donasi: "posko-logistik.html?focus=bantuan",
  stok: "posko-logistik.html",
  relawan: "management-relawan.html",
  program: "donor-program.html",
  search: "search-found.html"
};


function drillCard(
  startEl,
  dimension,
  hint
) {
  const card =
    startEl
    && startEl.closest("article");

  if (!card || card.dataset.drill) {
    return;
  }

  card.dataset.drill = dimension;

  card.classList.add("cc-clickable");
  card.setAttribute("role", "button");
  card.setAttribute("tabindex", "0");
  card.title =
    hint
    || "Klik untuk membuka rincian lintas kelompok";

  function go() {
    openDrill(dimension);
  }

  card.addEventListener("click", go);

  card.addEventListener(
    "keydown",
    event => {
      if (
        event.key === "Enter"
        || event.key === " "
      ) {
        event.preventDefault();
        go();
      }
    }
  );
}


function priClass(value) {
  const v =
    String(value || "").toLowerCase();

  if (
    ["critical", "darurat", "tinggi", "urgent", "segera", "high"]
      .includes(v)
  ) {
    return "hi";
  }

  if (["medium", "sedang", "normal"].includes(v)) {
    return "mid";
  }

  return "lo";
}


async function openDrill(dimension) {
  const modal =
    document.getElementById("drillModal");

  if (!modal) {
    return;
  }

  modal.hidden = false;
  document.body.style.overflow = "hidden";

  setText("drillTitle", "Memuat…");
  setText("drillSub", "");

  const body =
    document.getElementById("drillBody");

  if (body) {
    body.innerHTML =
      `<div class="cc-drill-loading">Memuat rincian…</div>`;
  }

  const link =
    document.getElementById("drillModuleLink");

  if (link) {
    const u =
      new URL(
        DRILL_MODULE[dimension] || "#",
        location.href
      );

    u.searchParams.set("event", eventId());
    link.href = u.toString();
  }

  try {
    const data =
      await call(
        "rescue_net.api_control_centre.kpi_drilldown",
        {
          disaster_event: eventId(),
          dimension
        }
      );

    renderDrill(data);
  }
  catch (err) {
    if (body) {
      body.innerHTML =
        `<div class="cc-drill-loading">
           Gagal memuat rincian: ${safe(err && err.message || err)}
         </div>`;
    }
  }
}


function closeDrill() {
  const modal =
    document.getElementById("drillModal");

  if (modal) {
    modal.hidden = true;
  }

  document.body.style.overflow = "";
}


function drillItemsHtml(items) {
  if (!items || !items.length) {
    return `<p class="cc-drill-empty-items">Tidak ada baris rincian.</p>`;
  }

  return `
    <ul class="cc-drill-items">
      ${items.map(it => {
        const poskoLabel =
          it.posko_title || it.posko;

        const href =
          it.posko
            ? `posko-detail.html?id=${
                encodeURIComponent(it.posko)
              }&event=${
                encodeURIComponent(eventId())
              }`
            : "";

        const tag = href ? "a" : "div";

        const openAttrs =
          href
            ? `class="cc-drill-item is-link" href="${href}"`
            : `class="cc-drill-item"`;

        return `
          <li>
            <${tag} ${openAttrs}>
              <div class="cc-drill-item-main">
                <strong>${safe(it.title)}</strong>
                ${
                  it.priority
                    ? `<span
                         class="cc-drill-pri ${priClass(it.priority)}"
                       >${safe(it.priority)}</span>`
                    : ""
                }
                ${
                  it.status
                    ? `<span class="cc-drill-stat">${safe(it.status)}</span>`
                    : ""
                }
              </div>

              ${
                it.detail
                  ? `<div class="cc-drill-item-sub">${safe(it.detail)}</div>`
                  : ""
              }

              <div class="cc-drill-item-foot">
                ${
                  poskoLabel
                    ? `<span>📍 ${safe(poskoLabel)}</span>`
                    : ""
                }
                <span>🏢 ${safe(it.organization_title || "-")}</span>
                ${
                  href
                    ? `<span class="cc-drill-go" aria-hidden="true">→</span>`
                    : ""
                }
              </div>
            </${tag}>
          </li>
        `;
      }).join("")}
    </ul>
  `;
}


function drillGroupHtml(g) {
  const open =
    g.share_mode === "full";

  const totals = [];

  totals.push(`<span><b>${format(g.count)}</b> item</span>`);

  if (g.posko_count) {
    totals.push(`<span><b>${format(g.posko_count)}</b> posko</span>`);
  }

  if (g.total_quantity) {
    totals.push(`<span>Total <b>${format(g.total_quantity)}</b></span>`);
  }

  if (g.total_gap) {
    totals.push(`<span>Gap <b>${format(g.total_gap)}</b></span>`);
  }

  if (g.critical_count) {
    totals.push(
      `<span class="crit"><b>${format(g.critical_count)}</b> kritis</span>`
    );
  }

  const bodyHtml =
    open
      ? drillItemsHtml(g.items)
      : `<p class="cc-drill-locked">
           🔒 <strong>${safe(g.organization_title)}</strong>
           menutup koordinasi rinci — hanya ringkasan di atas yang
           dibagikan ke Control Centre${
             g.hidden_count
               ? ` (${format(g.hidden_count)} baris disembunyikan)`
               : ""
           }.
         </p>`;

  return `
    <section class="cc-drill-group ${open ? "is-open" : "is-closed"}">
      <header class="cc-drill-group-head">
        <div class="cc-drill-org">
          <strong>${safe(g.organization_title || "-")}</strong>
          ${
            g.organization_type
              ? `<span class="cc-drill-type">${safe(g.organization_type)}</span>`
              : ""
          }
        </div>
        <span class="cc-drill-badge ${open ? "open" : "closed"}">
          ${open ? "Terbuka · rincian" : "Tertutup · ringkasan"}
        </span>
      </header>

      <div class="cc-drill-summary">
        ${totals.join("")}
      </div>

      ${bodyHtml}
    </section>
  `;
}


function renderDrill(data) {
  data = data || {};

  setText(
    "drillTitle",
    data.title || "Rincian"
  );

  setText(
    "drillSub",
    `${format(data.total || 0)} item · `
    + `${format(data.org_count || 0)} kelompok · `
    + `${format(data.shown_total || 0)} rincian terbuka · `
    + `${format(data.hidden_total || 0)} ringkasan`
  );

  const body =
    document.getElementById("drillBody");

  if (!body) {
    return;
  }

  const groups =
    data.groups || [];

  body.innerHTML =
    groups.length
      ? groups.map(drillGroupHtml).join("")
      : `<div class="cc-drill-loading">Belum ada data untuk dimensi ini.</div>`;
}


async function call(
  method,
  params = {}
) {
  const url =
    new URL(
      API + method
    );

  Object.entries(
    params
  ).forEach(
    ([key,value]) => {
      url.searchParams.set(
        key,
        value
      );
    }
  );

  const res =
    await fetch(
      url,
      {
        credentials:
          "omit"
      }
    );

  const payload =
    await res.json();

  if (!res.ok) {
    throw new Error(
      payload.exception
      || payload.message
      || `HTTP ${res.status}`
    );
  }

  return payload.message;
}


function num(value) {
  const n =
    Number(value);

  return Number.isFinite(n)
    ? n
    : 0;
}


function format(value) {
  return new Intl.NumberFormat(
    "id-ID",
    {
      maximumFractionDigits: 1
    }
  ).format(
    num(value)
  );
}


function renderEventSelector(
  dashboard
) {
  const select =
    document.getElementById(
      "activeEventSelect"
    );

  if (!select) {
    return;
  }

  const current =
    eventId();

  select.innerHTML =
    (
      dashboard.active_disasters
      || []
    ).map(
      row => {
        const id =
          String(
            row.legacy_id
            || row.id
            || row.name
            || ""
          ).replace(
            /^disaster_events:/,
            ""
          );

        return `
          <option
            value="${safe(id)}"
            ${
              id === current
                ? "selected"
                : ""
            }
          >
            ${safe(
              row.title
              || id
            )}
          </option>
        `;
      }
    ).join("");

  select.onchange =
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
    };
}


function renderHeader(ctx) {
  const disaster =
    ctx.disaster
    || {};

  const title =
    disaster.title
    || disaster.disaster_name
    || disaster.name
    || eventId();

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
    disaster.severity
    || "-"
  );

  setText(
    "mapTitle",
    `Peta Situasi — ${title}`
  );

  setText(
    "lastUpdateRelative",
    "baru saja"
  );

  setText(
    "sidebarUpdated",
    ctx.generated_at
    || "-"
  );
}


function renderNeeds(ctx) {
  const left =
    document.getElementById(
      "criticalNeedsBodyLeft"
    );

  const right =
    document.getElementById(
      "criticalNeedsBodyRight"
    );

  const rows =
    (
      ctx.logistic_needs
      || []
    )
    .filter(
      row =>
        ![
          "closed",
          "cancelled"
        ].includes(
          String(
            row.status
            || ""
          ).toLowerCase()
        )
    )
    .slice(
      0,
      12
    );

  function html(row) {
    const item =
      row.item_name
      || row.item_text
      || row.need_name
      || "Kebutuhan";

    const need =
      num(
        row.quantity_required
        || row.required_quantity
        || row.quantity
      );

    const realized =
      num(
        row.realized_quantity
        || row.fulfilled_quantity
        || row.delivered_quantity
        || row.quantity_fulfilled
        || row.quantity_delivered
      );

    const gap =
      Math.max(
        0,
        need - realized
      );

    const pct =
      need > 0
        ? Math.min(
            100,
            realized
            / need
            * 100
          )
        : 0;

    let cls = "";

    if (pct >= 80) {
      cls = "good";
    }
    else if (pct < 40) {
      cls = "low";
    }

    return `
      <tr>

        <td
          class="cc-need-item"
          data-need-item="${safe(item)}"
          role="button"
          tabindex="0"
          title="Klik: lihat posko mana yang membutuhkan ${safe(item)} — pilih tujuan bantuan"
        >
          ${safe(item)}
        </td>

        <td>
          ${format(need)}
        </td>

        <td>
          ${format(realized)}
        </td>

        <td>
          <div class="cc-progress-wrap">

            <div class="cc-progress-label">
              ${format(pct)}%
            </div>

            <div class="cc-progress-track">

              <div
                class="
                  cc-progress-bar
                  ${cls}
                "
                style="
                  width:${pct}%
                "
              ></div>

            </div>

          </div>
        </td>

        <td>
          ${format(gap)}
        </td>

      </tr>
    `;
  }


  const a = [];
  const b = [];

  rows.forEach(
    (row,index) => {
      (
        index % 2 === 0
          ? a
          : b
      ).push(row);
    }
  );

  left.innerHTML =
    a.length
      ? a.map(html).join("")
      : `
        <tr>
          <td colspan="5">
            Belum ada kebutuhan.
          </td>
        </tr>
      `;

  right.innerHTML =
    b.length
      ? b.map(html).join("")
      : "";

  [left, right].forEach(host => {
    host
      .querySelectorAll("[data-need-item]")
      .forEach(el => {
        function go() {
          openNeedPoskoDrill(el.dataset.needItem);
        }
        el.addEventListener("click", go);
        el.addEventListener("keydown", event => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            go();
          }
        });
      });
  });
}


/* ==========================================================
   Kebutuhan Kritis → "posko mana yang butuh item ini".
   Reuses the guest 'papan kebutuhan' feed (logistik_open_needs)
   — the SAME data an outside/collector posko uses to choose an
   aid destination — so clicking an item in the Control Centre
   lands on a pick-a-target list.
   ========================================================== */

let __RN_OPEN_NEEDS = null;

async function fetchOpenNeeds() {
  if (__RN_OPEN_NEEDS) {
    return __RN_OPEN_NEEDS;
  }
  const res =
    await call(
      "rescue_net.api_control_centre.logistik_open_needs",
      { disaster_event: eventId() }
    );
  __RN_OPEN_NEEDS =
    (res && res.needs)
    || (Array.isArray(res) ? res : [])
    || [];
  return __RN_OPEN_NEEDS;
}

async function openNeedPoskoDrill(item) {
  const modal =
    document.getElementById("drillModal");

  if (!modal) {
    return;
  }

  modal.hidden = false;
  document.body.style.overflow = "hidden";

  setText("drillTitle", item || "Kebutuhan");
  setText(
    "drillSub",
    "Posko yang membutuhkan item ini — pilih satu sebagai tujuan bantuan."
  );

  const body =
    document.getElementById("drillBody");

  if (body) {
    body.innerHTML =
      `<div class="cc-drill-loading">Memuat papan kebutuhan…</div>`;
  }

  const link =
    document.getElementById("drillModuleLink");

  if (link) {
    const u =
      new URL("posko-logistik.html", location.href);
    u.searchParams.set("event", eventId());
    link.href = u.toString();
    link.textContent = "Buka Posko Logistik →";
  }

  try {
    const needs =
      await fetchOpenNeeds();

    const key =
      String(item || "").trim().toLowerCase();

    const rows =
      needs.filter(
        n => String(n.item || "").trim().toLowerCase() === key
      );

    if (body) {
      body.innerHTML =
        renderNeedPoskoList(item, rows);
    }
  }
  catch (err) {
    if (body) {
      body.innerHTML =
        `<div class="cc-drill-loading">
           Gagal memuat papan kebutuhan: ${safe(err && err.message || err)}
         </div>`;
    }
  }
}

function renderNeedPoskoList(item, rows) {
  if (!rows || !rows.length) {
    return `
      <p class="cc-drill-empty-items">
        Tidak ada posko dengan kebutuhan terbuka untuk
        "${safe(item)}".
      </p>`;
  }

  const sorted =
    rows.slice().sort(
      (a, b) => (Number(b.gap) || 0) - (Number(a.gap) || 0)
    );

  const ev =
    encodeURIComponent(eventId());

  return `
    <ul class="cc-need-posko-list">
      ${sorted.map(n => {
        const pct =
          Math.max(0, Math.min(100, Number(n.percent) || 0));

        const penuhi =
          new URL("posko-logistik.html", location.href);
        penuhi.searchParams.set("event", eventId());
        if (n.posko) {
          penuhi.searchParams.set("id", n.posko);
        }
        penuhi.searchParams.set("penuhi", item || "");

        const kirim =
          new URL("kirim-bantuan.html", location.href);
        kirim.searchParams.set("event", eventId());
        if (n.posko) {
          kirim.searchParams.set("target_node_id", n.posko);
        }
        if (n.posko_title) {
          kirim.searchParams.set("target_node_name", n.posko_title);
        }
        kirim.searchParams.set("item", item || "");

        const logi =
          `posko-logistik.html?id=${
            encodeURIComponent(n.posko || "")
          }&event=${ev}`;

        return `
          <li class="cc-need-posko">
            <div class="cc-need-posko-head">
              <strong>${safe(n.posko_title || n.posko || "Posko")}</strong>
              ${
                n.priority
                  ? `<span
                       class="cc-drill-pri ${priClass(n.priority)}"
                     >${safe(n.priority)}</span>`
                  : ""
              }
            </div>

            ${
              n.posko_area
                ? `<div class="cc-need-posko-sub">${safe(n.posko_area)}</div>`
                : ""
            }

            <div class="cc-need-posko-stats">
              <span>Butuh <b>${format(n.required)}</b> ${safe(n.unit)}</span>
              <span>Realisasi <b>${format(n.realized)}</b></span>
              <span class="crit">Gap <b>${format(n.gap)}</b></span>
              ${
                n.beneficiary_count
                  ? `<span>${format(n.beneficiary_count)} jiwa</span>`
                  : ""
              }
            </div>

            <div class="cc-need-posko-bar"><i style="width:${pct}%"></i></div>

            <div class="cc-need-posko-actions">
              <a class="cc-need-btn primary" href="${penuhi.toString()}">
                Jadikan tujuan bantuan →
              </a>
              <a class="cc-need-btn" href="${logi}">
                Lihat posko logistik
              </a>
              <a class="cc-need-btn" href="${kirim.toString()}">
                Donasi publik
              </a>
            </div>
          </li>`;
      }).join("")}
    </ul>`;
}


function renderKpi(
  ctx,
  dashboard
) {
  const s =
    ctx.summary
    || {};

  const alerts =
    ctx.alerts
    || [];

  setText(
    "kpiRisk",
    num(
      s.open_logistic_need_count
    )
    +
    num(
      s.shelter_need_count
    )
  );

  setText(
    "kpiPoskoCritical",
    dashboard.map
      ?.summary
      ?.critical
      || 0
  );

  setText(
    "kpiAidFlow",
    s.distribution_flow_count
    || 0
  );

  setText(
    "kpiBlockedDistribution",
    alerts.filter(
      a =>
        /jalan|akses|route|distribution/i.test(
          `${a.type || ""} ${a.message || ""}`
        )
    ).length
  );

  setText(
    "kpiMedicalOverload",
    s.medical_case_count
    || 0
  );

  setText(
    "kpiDonation",
    s.aid_offer_count
    || 0
  );

  // Setiap KPI membuka rincian lintas kelompok: daftar item/objek/
  // situasi di baliknya, dikelompokkan per organisasi; klik "Lanjut"
  // membuka poskonya. Organisasi tertutup hanya membagi ringkasan.
  drillCard(
    document.getElementById("kpiRisk"),
    "kebutuhan",
    "Jiwa Berisiko = kebutuhan logistik & shelter yang belum terpenuhi. "
    + "Klik untuk rincian per kelompok."
  );

  drillCard(
    document.getElementById("kpiPoskoCritical"),
    "posko_kritis",
    "Posko Kritis = posko berstatus kritis. Klik untuk daftar posko "
    + "per kelompok."
  );

  drillCard(
    document.getElementById("kpiAidFlow"),
    "distribusi",
    "Bantuan Mengalir = alur distribusi bantuan yang berjalan. Klik "
    + "untuk rincian per kelompok."
  );

  drillCard(
    document.getElementById("kpiBlockedDistribution"),
    "distribusi_terhambat",
    "Distribusi Terhambat = alur distribusi yang macet/menunggu pickup. "
    + "Klik untuk rincian per kelompok."
  );

  drillCard(
    document.getElementById("kpiMedicalOverload"),
    "medis",
    "Medis Overload = kasus medis tercatat. Klik untuk rincian per "
    + "kelompok."
  );

  drillCard(
    document.getElementById("kpiDonation"),
    "donasi",
    "Donasi Menumpuk = tawaran bantuan yang belum tersalur. Klik untuk "
    + "rincian per kelompok."
  );
}


function renderMap(
  dashboard
) {
  if (
    typeof L
    === "undefined"
  ) {
    throw new Error(
      "Leaflet gagal dimuat"
    );
  }

  const host =
    document.getElementById(
      "situationMap"
    );

  const points =
    (
      dashboard.map
        ?.points
      || []
    ).filter(
      point => {
        const lat =
          Number(
            point.latitude
          );

        const lng =
          Number(
            point.longitude
          );

        return (
          Number.isFinite(lat)
          &&
          Number.isFinite(lng)
          &&
          !(lat === 0 && lng === 0)
        );
      }
    );

  setText(
    "mapSummary",
    `${points.length} Posko`
  );


  if (mapInstance) {
    mapInstance.remove();
  }


  mapInstance =
    L.map(
      host,
      {
        zoomControl:
          true
      }
    );


  L.tileLayer(
    "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    {
      maxZoom:
        19,

      attribution:
        "© OpenStreetMap"
    }
  ).addTo(
    mapInstance
  );


  const bounds = [];


  points.forEach(
    point => {
      const lat =
        Number(
          point.latitude
        );

      const lng =
        Number(
          point.longitude
        );

      if (
        !Number.isFinite(lat)
        ||
        !Number.isFinite(lng)
      ) {
        return;
      }


      const situation =
        point.situation
        || "safe";


      const icon =
        L.divIcon({
          className:
            "",

          html:
            `
              <span
                class="
                  cc-posko-marker
                  ${safe(situation)}
                "
              ></span>
            `,

          iconSize:
            [20,20],

          iconAnchor:
            [10,10]
        });


      L.marker(
        [lat,lng],
        {
          icon
        }
      )
      .addTo(
        mapInstance
      )
      .bindPopup(
        `
          <strong>
            ${safe(point.name)}
          </strong>

          <br>

          <small>
            ${safe(
              point.address
              || ""
            )}
          </small>

          <br>

          Status:
          <b>
            ${safe(
              point.status
              || "-"
            )}
          </b>

          <br>

          Koordinasi:
          <b>
            ${
              point.detail_allowed
                ? "detail terbuka"
                : "ringkasan (tertutup)"
            }
          </b>

          <br><br>

          <a
            href="posko-detail.html?id=${
              encodeURIComponent(
                point.posko_id
                || point.id
                || ""
              )
            }&event=${
              encodeURIComponent(eventId())
            }"
          >
            ${
              point.detail_allowed
                ? "Buka detail posko →"
                : "Buka ringkasan posko →"
            }
          </a>

          <br>

          <a
            target="_blank"
            rel="noopener"
            href="${safe(
              point.google_maps_url
            )}"
          >
            Buka di Google Maps →
          </a>
        `
      );


      bounds.push(
        [lat,lng]
      );
    }
  );


  if (bounds.length) {
    mapInstance.fitBounds(
      bounds,
      {
        padding:
          [20,20],

        maxZoom:
          12
      }
    );
  }
  else {
    mapInstance.setView(
      [4.22,96.15],
      9
    );
  }


  setTimeout(
    () =>
      mapInstance
        .invalidateSize(),
    100
  );
}


function renderPriority(ctx) {
  const host =
    document.getElementById(
      "priorityDecisionList"
    );

  const items = [
    ...(
      ctx.recommendations
      || []
    ),

    ...(
      ctx.alerts
      || []
    )
  ].slice(
    0,
    5
  );


  host.innerHTML =
    items.length
      ? items.map(
          (row,index) => `
            <div class="cc-priority-item">

              <span>
                ${index + 1}
              </span>

              <div>

                <strong>
                  ${safe(
                    row.title
                    || row.recommendation
                    || row.message
                    || row.type
                    || "Prioritas"
                  )}
                </strong>

                <p>
                  ${safe(
                    row.description
                    || row.reason
                    || ""
                  )}
                </p>

              </div>

            </div>
          `
        ).join("")
      : `
        <div class="cc-priority-item">
          Belum ada prioritas.
        </div>
      `;
}


function renderEvidence(
  dashboard
) {
  const host =
    document.getElementById(
      "latestEvidenceList"
    );

  const rows =
    (
      dashboard.evidence
      || dashboard.community_reports
      || []
    ).slice(
      0,
      5
    );

  window.__RN_EVIDENCE_ROWS =
    rows;

  host.innerHTML =
    rows.length
      ? rows.map(
          (row,index) => `
            <div
              class="cc-evidence-item"
              data-evidence-index="${index}"
              tabindex="0"
              role="button"
            >

              <div class="cc-evidence-thumb">

                ${
                  row.evidence_url
                    ? `
                      <img
                        src="${safe(
                          row.evidence_url
                        )}"
                        alt="${safe(
                          row.evidence_caption
                          || row.title
                          || "Bukti Lapangan"
                        )}"
                      >
                    `
                    : ""
                }

              </div>

              <div>

                <strong>
                  ${safe(
                    row.evidence_caption
                    || row.title
                    || "Laporan"
                  )}
                </strong>

                <span>
                  ${safe(
                    row.location_text
                    || ""
                  )}
                </span>

                <span>
                  ${safe(
                    row.reporter_name
                    || ""
                  )}
                </span>

              </div>

            </div>
          `
        ).join("")
      : `
        <div class="cc-evidence-item">
          Belum ada bukti publik.
        </div>
      `;

  host
    .querySelectorAll(
      "[data-evidence-index]"
    )
    .forEach(el => {

      function open() {
        const index =
          Number(
            el.dataset
              .evidenceIndex
          );

        openEvidenceModal(
          rows[index]
        );
      }

      el.addEventListener(
        "click",
        open
      );

      el.addEventListener(
        "keydown",
        event => {
          if (
            event.key
            === "Enter"
          ) {
            open();
          }
        }
      );
    });
}


function openEvidenceModal(
  row
) {
  if (!row) {
    return;
  }

  const modal =
    document.getElementById(
      "evidenceModal"
    );

  const image =
    document.getElementById(
      "evidenceModalImage"
    );

  if (
    !modal
    || !image
  ) {
    return;
  }

  image.src =
    row.evidence_url
    || "";

  image.alt =
    row.evidence_caption
    || row.title
    || "";

  setText(
    "evidenceModalTitle",
    row.evidence_caption
    || row.title
    || "Bukti Lapangan"
  );

  setText(
    "evidenceModalLocation",
    row.location_text
    || "-"
  );

  setText(
    "evidenceModalDescription",
    row.evidence_details
    || row.description
    || "-"
  );

  setText(
    "evidenceModalReporter",
    (
      row.uploader
      || row.evidence_photographer
      || row.reporter_name
      || "-"
    )
    + (
      row.uploader_role
        ? ` (${row.uploader_role})`
        : ""
    )
  );

  setText(
    "evidenceModalPriority",
    row.priority
    || "-"
  );

  setText(
    "evidenceModalStatus",
    row.status
    || "-"
  );

  setText(
    "evidenceModalType",
    row.report_type
    || row.type
    || "Laporan lapangan"
  );

  const lat =
    Number(row.latitude);

  const lng =
    Number(row.longitude);

  setText(
    "evidenceModalCoords",
    (
      Number.isFinite(lat)
      && Number.isFinite(lng)
      && !(lat === 0 && lng === 0)
    )
      ? `${lat.toFixed(5)}, ${lng.toFixed(5)}`
      : "-"
  );

  const when =
    row.modified
    || row.creation
    || row.observed_at;

  setText(
    "evidenceModalTime",
    when
      ? String(when).replace("T", " ").slice(0, 16)
      : "-"
  );

  const badge =
    document.getElementById(
      "evidenceModalBadge"
    );

  if (badge) {
    const isSim =
      /simulasi|\[sim/i.test(
        `${row.title || ""} ${row.evidence_caption || ""}`
      );

    badge.hidden = !isSim;
  }

  const coordsCell =
    document.getElementById(
      "evidenceModalCoords"
    );

  if (
    coordsCell
    && coordsCell.parentElement
  ) {
    if (
      Number.isFinite(lat)
      && Number.isFinite(lng)
      && !(lat === 0 && lng === 0)
    ) {
      coordsCell.parentElement.style.cursor =
        "pointer";

      coordsCell.parentElement.title =
        "Buka di Google Maps";

      coordsCell.parentElement.onclick =
        () => window.open(
          `https://maps.google.com/?q=${lat},${lng}`,
          "_blank",
          "noopener"
        );
    }
    else {
      coordsCell.parentElement.onclick = null;
    }
  }

  modal.hidden =
    false;

  document.body.style.overflow =
    "hidden";
}


function closeEvidenceModal() {
  const modal =
    document.getElementById(
      "evidenceModal"
    );

  if (modal) {
    modal.hidden =
      true;
  }

  document.body.style.overflow =
    "";
}



function renderModules(ctx) {
  const s =
    ctx.summary
    || {};

  setText(
    "moduleLogisticsValue",
    s.stock_item_count
    || 0
  );

  setText(
    "moduleLogisticsDetail",
    "item stok"
  );

  setText(
    "moduleLogisticsStatus",
    "Live"
  );


  setText(
    "moduleDistributionValue",
    s.distribution_flow_count
    || 0
  );

  setText(
    "moduleDistributionDetail",
    "flow distribusi"
  );

  setText(
    "moduleDistributionStatus",
    "Live"
  );


  setText(
    "moduleMedicalValue",
    s.medical_case_count
    || 0
  );

  setText(
    "moduleMedicalDetail",
    "kasus medis"
  );

  setText(
    "moduleMedicalStatus",
    "Live"
  );


  setText(
    "moduleVolunteerValue",
    s.volunteer_count
    || 0
  );

  setText(
    "moduleVolunteerDetail",
    "relawan"
  );

  setText(
    "moduleVolunteerStatus",
    "Live"
  );


  setText(
    "moduleProgramValue",
    s.program_count
    || s.donor_program_count
    || 0
  );

  setText(
    "moduleProgramDetail",
    "program"
  );

  setText(
    "moduleProgramStatus",
    "Live"
  );


  setText(
    "moduleSearchValue",
    (
      num(
        s.missing_person_count
      )
      +
      num(
        s.found_person_count
      )
    )
  );

  setText(
    "moduleSearchDetail",
    "laporan"
  );

  setText(
    "moduleSearchStatus",
    "Live"
  );

  drillCard(
    document.getElementById("moduleLogisticsValue"),
    "stok",
    "Stok barang tercatat per posko. Klik untuk rincian per kelompok."
  );

  drillCard(
    document.getElementById("moduleDistributionValue"),
    "distribusi",
    "Alur distribusi bantuan. Klik untuk rincian per kelompok."
  );

  drillCard(
    document.getElementById("moduleMedicalValue"),
    "medis",
    "Kasus medis tercatat. Klik untuk rincian per kelompok."
  );

  drillCard(
    document.getElementById("moduleVolunteerValue"),
    "relawan",
    "Penugasan relawan. Klik untuk rincian per kelompok."
  );

  drillCard(
    document.getElementById("moduleProgramValue"),
    "program",
    "Program khusus & donasi terarah. Klik untuk rincian per kelompok."
  );

  drillCard(
    document.getElementById("moduleSearchValue"),
    "search",
    "Laporan orang hilang & ditemukan. Klik untuk rincian per kelompok."
  );
}


function renderMiniChart(
  id,
  values
) {
  const host =
    document.getElementById(
      id
    );

  if (!host) {
    return;
  }


  if (
    !Array.isArray(values)
    ||
    values.length < 2
  ) {
    host.innerHTML =
      `
        <div class="cc-chart-empty">
          menunggu histori
        </div>
      `;

    return;
  }


  const nums =
    values
      .map(Number)
      .filter(
        Number.isFinite
      );


  if (nums.length < 2) {
    return;
  }


  const min =
    Math.min(
      ...nums
    );

  const max =
    Math.max(
      ...nums
    );

  const range =
    max - min
    || 1;


  const points =
    nums.map(
      (v,i) => {
        const x =
          2
          +
          i
          *
          96
          /
          (
            nums.length
            - 1
          );

        const y =
          31
          -
          (
            v - min
          )
          /
          range
          * 25;

        return (
          `${x},${y}`
        );
      }
    ).join(" ");


  host.innerHTML =
    `
      <svg
        viewBox="0 0 100 35"
        preserveAspectRatio="none"
      >
        <polyline
          points="${points}"
          fill="none"
          stroke="currentColor"
          stroke-width="1.5"
        />
      </svg>
    `;
}


async function load() {
  const id =
    eventId();

  __RN_OPEN_NEEDS = null;


  const dashboard =
    await call(
      "rescue_net.api_control_centre.public_dashboard",
      {
        disaster_event_id:
          id
      }
    );


  const ctx =
    dashboard.context
    || {};


  renderEventSelector(
    dashboard
  );

  renderHeader(
    ctx
  );

  renderNeeds(
    ctx
  );

  renderKpi(
    ctx,
    dashboard
  );

  renderMap(
    dashboard
  );

  renderPriority(
    ctx
  );

  renderEvidence(
    dashboard
  );

  renderModules(
    ctx
  );


  const trends =
    ctx.trends
    || {};


  renderMiniChart(
    "chartLogistics",
    trends.logistics
  );

  renderMiniChart(
    "chartDistribution",
    trends.distribution
  );

  renderMiniChart(
    "chartMedical",
    trends.medical
  );

  renderMiniChart(
    "chartVolunteer",
    trends.volunteer
  );

  renderMiniChart(
    "chartProgram",
    trends.program
  );

  renderMiniChart(
    "chartSearch",
    trends.search_found
  );


  setText(
    "warRoomStatus",
    "Loaded"
  );
}

/* ==========================================================
   RN CONTROL CENTRE — SINGLE RELIABLE BOOT
   ========================================================== */

(() => {
  async function rnControlCentreBoot() {
    if (window.__RN_CONTROL_CENTRE_BOOTED) {
      return;
    }

    window.__RN_CONTROL_CENTRE_BOOTED = true;

    console.log(
      "RN_CONTROL_CENTRE_BOOT_START"
    );

    try {
      document
        .getElementById(
          "evidenceModalClose"
        )
        ?.addEventListener(
          "click",
          closeEvidenceModal
        );

      document
        .getElementById(
          "evidenceModal"
        )
        ?.addEventListener(
          "click",
          event => {
            if (
              event.target.id
              === "evidenceModal"
            ) {
              closeEvidenceModal();
            }
          }
        );

      document
        .getElementById(
          "drillModalClose"
        )
        ?.addEventListener(
          "click",
          closeDrill
        );

      document
        .getElementById(
          "drillModal"
        )
        ?.addEventListener(
          "click",
          event => {
            if (
              event.target.id
              === "drillModal"
            ) {
              closeDrill();
            }
          }
        );

      document
        .addEventListener(
          "keydown",
          event => {
            if (
              event.key
              === "Escape"
            ) {
              closeEvidenceModal();
              closeDrill();
            }
          }
        );

      await load();

      console.log(
        "RN_CONTROL_CENTRE_BOOT_PASS"
      );
    }
    catch (err) {
      window.__RN_CONTROL_CENTRE_BOOTED = false;

      console.error(
        "RN_CONTROL_CENTRE_BOOT_FAIL",
        err,
        err?.stack
      );

      setText(
        "warRoomStatus",
        err?.message
        || "Control Centre gagal dimuat"
      );
    }
  }

  window.rnControlCentreBoot =
    rnControlCentreBoot;

  if (
    document.readyState === "loading"
  ) {
    document.addEventListener(
      "DOMContentLoaded",
      rnControlCentreBoot,
      {
        once: true
      }
    );
  }
  else {
    rnControlCentreBoot();
  }
})();
