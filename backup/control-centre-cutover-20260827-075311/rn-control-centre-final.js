"use strict";


const API =
  location.origin
  + "/rescue-net-frappe/api/method/";


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

        <td title="${safe(item)}">
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
    dashboard.map
      ?.points
      || [];

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

          <br><br>

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
      dashboard.community_reports
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
    row.evidence_photographer
    || row.reporter_name
    || "-"
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


document.addEventListener(
  "DOMContentLoaded",
  () => {

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
      .addEventListener(
        "keydown",
        event => {
          if (
            event.key
            === "Escape"
          ) {
            closeEvidenceModal();
          }
        }
      );
    load()
      .catch(
        err => {
          console.error(
            "CONTROL_CENTRE_FINAL_FAIL",
            err
          );

          setText(
            "warRoomStatus",
            err.message
          );
        }
      );
  }
);
