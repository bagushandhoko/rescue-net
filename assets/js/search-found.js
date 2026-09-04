let SF_CONTEXT_CACHE = null;

function statusMsg(msg) {
  const el =
    document.getElementById(
      "sfStatus"
    );

  if (el) {
    el.textContent = msg;
  }
}

function getDisasterId() {
  const params =
    new URLSearchParams(
      window.location.search
    );

  return (
    params.get("event") ||
    "event-sim-001"
  );
}

function safe(v) {
  return (
    v === null ||
    v === undefined ||
    v === ""
  )
    ? "n/a"
    : v;
}

function rowId(row) {
  if (!row) {
    return "";
  }

  return (
    row.name ||
    row.id ||
    row.legacy_id ||
    ""
  );
}

function reportStatus(row) {
  if (!row) {
    return "";
  }

  return (
    row.report_status ||
    row.status ||
    ""
  );
}

function matchStatus(row) {
  if (!row) {
    return "";
  }

  return (
    row.match_status ||
    row.status ||
    ""
  );
}

function evidenceLink(
  objectType,
  objectId,
  label = "Add Evidence"
) {
  if (
    !objectId ||
    objectId === "n/a"
  ) {
    return "";
  }

  const eventId =
    encodeURIComponent(
      getDisasterId()
    );

  return (
    `<br><a href="evidence.html?event=${eventId}` +
    `&object_type=${encodeURIComponent(objectType)}` +
    `&object_id=${encodeURIComponent(objectId)}">` +
    `${label}</a>`
  );
}

function card(
  title,
  body,
  chip = ""
) {
  return `
    <article class="event-card">
      <div class="event-main">
        <div>
          <h4>${title}</h4>
          <p>${body}</p>
        </div>

        <div class="chips">
          ${
            chip
              ? `<span class="chip warning">${chip}</span>`
              : ""
          }
        </div>
      </div>
    </article>
  `;
}

function renderMissing(items) {
  const el =
    document.getElementById(
      "missingReports"
    );

  if (!el) {
    return;
  }

  el.innerHTML =
    items.length
      ? items.map(m => {
          const id = rowId(m);

          return card(
            `${safe(m.person_code)} · ${safe(m.person_name)}`,
            `Last seen: ${safe(m.last_seen_location)} · ` +
            `${safe(m.last_seen_time)}<br>` +
            `${safe(m.description)}<br>` +
            `Clothing: ${safe(m.clothing_description)}` +
            evidenceLink(
              "missing_person_report",
              id
            ),
            reportStatus(m)
          );
        }).join("")
      : card(
          "Belum ada laporan hilang",
          "Tambahkan missing report.",
          "empty"
        );
}

function renderFound(items) {
  const el =
    document.getElementById(
      "foundReports"
    );

  if (!el) {
    return;
  }

  el.innerHTML =
    items.length
      ? items.map(f => {
          const id = rowId(f);

          return card(
            `${safe(f.person_code)} · ${safe(f.person_name)}`,
            `Found: ${safe(f.found_location)} · ` +
            `${safe(f.found_time)}<br>` +
            `${safe(f.description)}<br>` +
            `Clothing: ${safe(f.clothing_description)}` +
            evidenceLink(
              "found_person_report",
              id
            ),
            reportStatus(f)
          );
        }).join("")
      : card(
          "Belum ada laporan ditemukan",
          "Tambahkan found report.",
          "empty"
        );
}

function renderMatches(items) {
  const el =
    document.getElementById(
      "matches"
    );

  if (!el) {
    return;
  }

  el.innerHTML =
    items.length
      ? items.map(m => {
          const id =
            rowId(m);

          const status =
            matchStatus(m);

          return `
            <article class="event-card">
              <div class="event-main">
                <div>
                  <h4>
                    ${safe(
                      m.missing_person_code ||
                      m.missing_report
                    )}
                    ↔
                    ${safe(
                      m.found_person_code ||
                      m.found_report
                    )}
                  </h4>

                  <p>
                    Basis:
                    ${safe(
                      m.match_basis ||
                      m.match_reason
                    )}
                    <br>

                    Review:
                    ${safe(
                      m.review_notes
                    )}
                  </p>
                </div>

                <div class="chips">
                  <span class="chip warning">
                    ${safe(status)}
                  </span>

                  ${
                    status !== "reunited"
                      ? `<button class="btn primary"
                           type="button"
                           onclick="updateMatchStatus(
                             '${id}',
                             'reunited'
                           )">
                           Mark Reunited
                         </button>`
                      : ""
                  }

                  ${
                    status === "candidate"
                      ? `<button class="btn"
                           type="button"
                           onclick="updateMatchStatus(
                             '${id}',
                             'investigating'
                           )">
                           Investigating
                         </button>`
                      : ""
                  }

                  ${
                    status !== "rejected" &&
                    status !== "reunited"
                      ? `<button class="btn"
                           type="button"
                           onclick="updateMatchStatus(
                             '${id}',
                             'rejected'
                           )">
                           Reject
                         </button>`
                      : ""
                  }
                </div>
              </div>
            </article>
          `;
        }).join("")
      : card(
          "Belum ada match",
          "Match bisa dibuat melalui pencocokan laporan.",
          "empty"
        );
}

async function updateMatchStatus(
  matchId,
  status
) {
  const notes =
    prompt(
      "Review notes",
      status === "reunited"
        ? "Keluarga sudah dikonfirmasi dan dipertemukan."
        : ""
    );

  statusMsg(
    "Updating match status..."
  );

  await window.RN_FRAPPE.call(
    "rescue_net.api_search_found." +
    "update_match_status",
    {
      match: matchId,
      new_status: status,
      review_notes:
        notes || ""
    },
    {
      method: "POST"
    }
  );

  statusMsg(
    "Match status updated."
  );

  await loadSearchFound();
}

window.updateMatchStatus =
  updateMatchStatus;

async function loadSearchFound() {
  const disasterId =
    getDisasterId();

  statusMsg(
    "Loading Search & Found context..."
  );

  const ctx =
    await window.RN_FRAPPE.call(
      "rescue_net.api_search_found.dashboard",
      {
        disaster_event:
          disasterId
      }
    );

  SF_CONTEXT_CACHE =
    ctx || {};

  const missing =
    ctx.missing ||
    ctx.missing_person_reports ||
    ctx.missing_reports ||
    [];

  const found =
    ctx.found ||
    ctx.found_person_reports ||
    ctx.found_reports ||
    [];

  const matches =
    ctx.matches ||
    ctx.search_found_matches ||
    [];

  const summary =
    ctx.summary || {};

  const reunitedCount =
    matches.filter(
      row =>
        matchStatus(row) ===
        "reunited"
    ).length;

  const kpiMissing =
    document.getElementById(
      "kpiMissing"
    );

  const kpiFound =
    document.getElementById(
      "kpiFound"
    );

  const kpiMatches =
    document.getElementById(
      "kpiMatches"
    );

  const kpiReunited =
    document.getElementById(
      "kpiReunited"
    );

  if (kpiMissing) {
    kpiMissing.textContent =
      summary.missing_count ??
      summary.missing_person_count ??
      missing.length;
  }

  if (kpiFound) {
    kpiFound.textContent =
      summary.found_count ??
      summary.found_person_count ??
      found.length;
  }

  if (kpiMatches) {
    kpiMatches.textContent =
      summary.match_count ??
      summary.search_found_match_count ??
      matches.length;
  }

  if (kpiReunited) {
    kpiReunited.textContent =
      summary.reunited_count ??
      reunitedCount;
  }

  renderMissing(missing);
  renderFound(found);
  renderMatches(matches);

  const missingForm =
    document.getElementById(
      "missingForm"
    );

  if (
    missingForm &&
    missingForm.disaster_event_id
  ) {
    missingForm
      .disaster_event_id
      .value =
      disasterId;
  }

  statusMsg(
    "Loaded: " +
    safe(
      ctx.generated_at
    )
  );
}

function setupMissingForm() {
  const form =
    document.getElementById(
      "missingForm"
    );

  if (!form) {
    return;
  }

  form.addEventListener(
    "submit",
    async e => {
      e.preventDefault();

      const disasterEvent =
        (
          form.disaster_event_id
            ? form.disaster_event_id.value
            : getDisasterId()
        ).trim();

      const payload = {
        person_code:
          form.person_code.value.trim(),

        person_name:
          form.person_name.value.trim(),

        disaster_event:
          disasterEvent,

        last_seen_location:
          form.last_seen_location.value.trim(),

        last_seen_time:
          form.last_seen_time.value.trim(),

        description:
          form.description.value.trim(),

        clothing_description:
          form.clothing_description.value.trim()
      };

      statusMsg(
        "Saving missing report..."
      );

      await window.RN_FRAPPE.call(
        "rescue_net.api_search_found." +
        "create_missing_report",
        payload,
        {
          method: "POST"
        }
      );

      statusMsg(
        "Missing report saved."
      );

      form.reset();

      await loadSearchFound();
    }
  );
}

function setupFoundForm() {
  const form =
    document.getElementById(
      "foundForm"
    );

  if (!form) {
    return;
  }

  form.addEventListener(
    "submit",
    async e => {
      e.preventDefault();

      const payload = {
        person_code:
          form.person_code.value.trim(),

        person_name:
          form.person_name.value.trim(),

        disaster_event:
          getDisasterId(),

        found_location:
          form.found_location.value.trim(),

        found_time:
          form.found_time.value.trim(),

        description:
          form.description.value.trim(),

        clothing_description:
          form.clothing_description.value.trim()
      };

      statusMsg(
        "Saving found report..."
      );

      await window.RN_FRAPPE.call(
        "rescue_net.api_search_found." +
        "create_found_report",
        payload,
        {
          method: "POST"
        }
      );

      statusMsg(
        "Found report saved."
      );

      form.reset();

      await loadSearchFound();
    }
  );
}

document.addEventListener(
  "DOMContentLoaded",
  () => {
    if (!window.RN_FRAPPE) {
      statusMsg(
        "Frappe client tidak tersedia."
      );

      return;
    }

    setupMissingForm();
    setupFoundForm();

    const btn =
      document.getElementById(
        "refreshSf"
      );

    if (btn) {
      btn.addEventListener(
        "click",
        () => {
          loadSearchFound().catch(
            err =>
              statusMsg(
                err.message
              )
          );
        }
      );
    }

    loadSearchFound().catch(
      err =>
        statusMsg(
          err.message
        )
    );
  }
);
