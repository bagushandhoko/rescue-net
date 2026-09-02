/* Bencana Aktif dashboard — pages/bencana-aktif.html
 * Reads rescue_net.api_control_centre.active_disasters_board (guest).
 * Left: paginated, expandable per-region list. Right: selected-event summary.
 */
(function () {
  "use strict";

  var PAGE_SIZE = 3;
  var METHOD = "rescue_net.api_control_centre.active_disasters_board";

  var state = {
    events: [],
    filtered: [],
    totals: {},
    page: 0,
    selectedId: null,
    expanded: {},
    expandAll: false,
  };

  var $ = function (sel, root) {
    return (root || document).querySelector(sel);
  };

  function fmt(n) {
    var v = Number(n || 0);
    return v.toLocaleString("id-ID");
  }

  function shortId(id) {
    return String(id || "").replace(/^disaster_events:/, "");
  }

  function relTime(iso) {
    if (!iso) return "—";
    var then = new Date(iso).getTime();
    if (isNaN(then)) return "—";
    var diff = Math.max(0, Date.now() - then);
    var m = Math.round(diff / 60000);
    if (m < 1) return "baru saja";
    if (m < 60) return m + " menit lalu";
    var h = Math.round(m / 60);
    if (h < 24) return h + " jam lalu";
    var d = Math.round(h / 24);
    return d + " hari lalu";
  }

  function statusClass(label) {
    var l = String(label || "").toLowerCase();
    if (l === "kritis") return "is-kritis";
    if (l === "siaga") return "is-siaga";
    return "is-waspada";
  }

  function pill(label) {
    return (
      '<span class="rn-ba-pill ' +
      statusClass(label) +
      '">' +
      (label || "—") +
      "</span>"
    );
  }

  /* ---------- data ---------- */

  function load() {
    setStatus("Memuat data bencana…");
    return window.RN_FRAPPE.call(METHOD)
      .then(function (res) {
        var data = res || {};
        state.events = data.events || [];
        state.totals = data.totals || {};
        renderKpi(state.totals);
        $("#baUpdated").textContent =
          "Diperbarui " + relTime(data.generated_at);
        applyFilter();
        if (!state.selectedId && state.events.length) {
          select(state.events[0].id);
        }
        setStatus("");
      })
      .catch(function (err) {
        console.error("[bencana-aktif]", err);
        setStatus("Gagal memuat data: " + (err && err.message || err));
        $("#baTableBody").innerHTML =
          '<tr><td colspan="6">Gagal memuat data bencana.</td></tr>';
      });
  }

  function setStatus(msg) {
    var el = $("#baStatus");
    if (!el) return;
    el.textContent = msg || "";
    el.hidden = !msg;
  }

  /* ---------- KPI ---------- */

  function renderKpi(totals) {
    ["bencana_aktif", "jiwa_berisiko", "kebutuhan_kritis", "distribusi_terhambat"].forEach(
      function (key) {
        var el = document.querySelector('.kpi-grid [data-k="' + key + '"]');
        if (el) el.textContent = fmt(totals[key]);
      }
    );
  }

  /* ---------- KPI drill-down modal ---------- */

  var DRILL = {
    bencana: { title: "Semua Bencana Aktif" },
    jiwa: { title: "Jiwa Berisiko per Bencana & Wilayah" },
    kebutuhan: { title: "Kebutuhan Kritis Belum Terpenuhi" },
    distribusi: { title: "Distribusi Terhambat / Menunggu" },
  };

  function openDrill(kind) {
    var cfg = DRILL[kind];
    if (!cfg) return;
    $("#baDrillTitle").textContent = cfg.title;
    $("#baDrillBody").innerHTML = renderDrill(kind);
    var sub = "";
    if (kind === "kebutuhan")
      sub = fmt(state.totals.kebutuhan_kritis) + " item · klik untuk buka posko & isi bantuan";
    else if (kind === "distribusi")
      sub = fmt(state.totals.distribusi_terhambat) + " item";
    else if (kind === "jiwa")
      sub = "Total " + fmt(state.totals.jiwa_berisiko) + " jiwa dilayani posko";
    else sub = fmt(state.totals.bencana_aktif) + " bencana berstatus aktif";
    $("#baDrillSub").textContent = sub;
    var m = $("#baDrill");
    m.hidden = false;
    document.body.style.overflow = "hidden";
  }

  function closeDrill() {
    $("#baDrill").hidden = true;
    document.body.style.overflow = "";
  }

  function drillGroup(ev, inner) {
    return (
      '<div class="rn-ba-dg">' +
      '<div class="rn-ba-dg-head">' +
      pill(ev.status_label) +
      "<b>" + esc(ev.name) + "</b>" +
      '<small class="rn-muted">' + esc(ev.location) + "</small>" +
      "</div>" +
      inner +
      "</div>"
    );
  }

  function renderDrill(kind) {
    var evs = state.events;

    if (kind === "bencana") {
      return (
        '<table class="rn-table"><thead><tr><th>Bencana</th><th>Status</th>' +
        "<th>Jiwa</th><th>Keb. Kritis</th><th>Posko</th></tr></thead><tbody>" +
        evs
          .map(function (ev) {
            return (
              '<tr class="rn-ba-drow" data-select="' + ev.id + '">' +
              "<td><b>" + esc(ev.name) + "</b><small>" + esc(ev.location) + "</small></td>" +
              "<td>" + pill(ev.status_label) + "</td>" +
              "<td>" + fmt(ev.jiwa_berisiko) + "</td>" +
              "<td>" + fmt(ev.kebutuhan_kritis) + "</td>" +
              "<td>" + fmt(ev.posko_count) + "</td>" +
              "</tr>"
            );
          })
          .join("") +
        "</tbody></table>"
      );
    }

    if (kind === "jiwa") {
      return evs
        .filter(function (ev) { return ev.jiwa_berisiko > 0 || (ev.regions || []).length; })
        .sort(function (a, b) { return b.jiwa_berisiko - a.jiwa_berisiko; })
        .map(function (ev) {
          var rows = (ev.regions || [])
            .map(function (rg) {
              return (
                "<tr><td>" + esc(rg.name) + "</td><td>" + fmt(rg.jiwa_berisiko) +
                "</td><td>" + fmt(rg.posko_count) + "</td><td>" + pill(rg.status_label) + "</td></tr>"
              );
            })
            .join("");
          var tbl =
            '<table class="rn-table"><thead><tr><th>Wilayah</th><th>Jiwa</th>' +
            "<th>Posko</th><th>Status</th></tr></thead><tbody>" +
            (rows || '<tr><td colspan="4"><em class="rn-muted">Belum ada data wilayah</em></td></tr>') +
            "</tbody></table>" +
            '<a class="btn ghost mini" href="war-room.html?event=' +
            encodeURIComponent(shortId(ev.id)) + '">Buka Control Centre ↗</a>';
          return drillGroup(ev, tbl);
        })
        .join("") || '<p class="rn-muted">Belum ada jiwa berisiko tercatat.</p>';
    }

    // kebutuhan / distribusi — item lists with deep links
    var field = kind === "kebutuhan" ? "kebutuhan_items" : "distribusi_items";
    var any = evs.some(function (ev) { return (ev[field] || []).length; });
    if (!any) {
      return (
        '<p class="rn-muted">Tidak ada ' +
        (kind === "kebutuhan" ? "kebutuhan kritis" : "distribusi terhambat") +
        " saat ini.</p>"
      );
    }
    return evs
      .filter(function (ev) { return (ev[field] || []).length; })
      .map(function (ev) {
        var rows = ev[field]
          .map(function (it) {
            var badge =
              kind === "kebutuhan"
                ? '<span class="rn-ba-pill ' +
                  (it.urgency === "critical" ? "is-kritis" : "is-siaga") +
                  '">' + esc(it.urgency || "-") + "</span>"
                : '<span class="rn-ba-pill is-siaga">' + esc(it.status || "-") + "</span>";
            return (
              '<a class="rn-ba-ditem" href="' + esc(it.href) + '">' +
              "<span><b>" + esc(it.item) + "</b><small>" +
              esc(it.posko_title) + " · " + esc(it.region) + "</small></span>" +
              badge + '<span class="rn-ba-ditem-go">→</span>' +
              "</a>"
            );
          })
          .join("");
        return drillGroup(ev, '<div class="rn-ba-ditems">' + rows + "</div>");
      })
      .join("");
  }

  /* ---------- filter + pagination ---------- */

  function applyFilter() {
    var q = ($("#baSearch").value || "").trim().toLowerCase();
    state.filtered = state.events.filter(function (ev) {
      if (!q) return true;
      return (
        (ev.name || "").toLowerCase().indexOf(q) !== -1 ||
        (ev.location || "").toLowerCase().indexOf(q) !== -1 ||
        shortId(ev.id).toLowerCase().indexOf(q) !== -1
      );
    });
    var maxPage = Math.max(0, Math.ceil(state.filtered.length / PAGE_SIZE) - 1);
    if (state.page > maxPage) state.page = maxPage;
    renderTable();
  }

  function renderTable() {
    var body = $("#baTableBody");
    $("#baCount").textContent = state.filtered.length;

    if (!state.filtered.length) {
      body.innerHTML = '<tr><td colspan="6">Tidak ada bencana yang cocok.</td></tr>';
      $("#baShown").textContent = "0 bencana";
      $("#baPager").innerHTML = "";
      return;
    }

    var start = state.page * PAGE_SIZE;
    var rows = state.filtered.slice(start, start + PAGE_SIZE);
    var html = "";

    rows.forEach(function (ev) {
      var open = state.expandAll || !!state.expanded[ev.id];
      var isSel = ev.id === state.selectedId;
      html +=
        '<tr class="rn-ba-row' +
        (isSel ? " is-selected" : "") +
        '" data-id="' +
        ev.id +
        '">' +
        '<td class="rn-ba-name">' +
        '<button class="rn-ba-caret" type="button" aria-label="Perluas">' +
        (open ? "▾" : "▸") +
        "</button>" +
        "<span><b>" +
        esc(ev.name) +
        "</b><small>" +
        esc(ev.location) +
        "</small></span>" +
        "</td>" +
        "<td>" +
        pill(ev.status_label) +
        "</td>" +
        "<td>" +
        fmt(ev.jiwa_berisiko) +
        "</td>" +
        "<td>" +
        fmt(ev.kebutuhan_kritis) +
        "</td>" +
        "<td>" +
        fmt(ev.distribusi_terhambat) +
        " / " +
        fmt(ev.distribusi_total) +
        "</td>" +
        "<td>" +
        relTime(ev.last_updated) +
        "</td>" +
        "</tr>";

      if (open) {
        var regions = ev.regions || [];
        if (!regions.length) {
          html +=
            '<tr class="rn-ba-sub"><td colspan="6"><em class="rn-muted">' +
            "Belum ada data wilayah untuk bencana ini.</em></td></tr>";
        }
        regions.forEach(function (rg) {
          html +=
            '<tr class="rn-ba-sub" data-id="' +
            ev.id +
            '">' +
            '<td class="rn-ba-subname">' +
            "<span></span>" +
            esc(rg.name) +
            '<small class="rn-muted">' +
            fmt(rg.posko_count) +
            " posko</small>" +
            "</td>" +
            "<td>" +
            pill(rg.status_label) +
            "</td>" +
            "<td>" +
            fmt(rg.jiwa_berisiko) +
            "</td>" +
            "<td>" +
            fmt(rg.kebutuhan_kritis) +
            "</td>" +
            "<td>" +
            fmt(rg.distribusi) +
            "</td>" +
            "<td>" +
            relTime(rg.last_updated) +
            "</td>" +
            "</tr>";
        });
      }
    });

    body.innerHTML = html;

    var end = Math.min(start + PAGE_SIZE, state.filtered.length);
    $("#baShown").textContent =
      "Menampilkan " +
      (start + 1) +
      "–" +
      end +
      " dari " +
      state.filtered.length +
      " bencana";
    renderPager();
  }

  function renderPager() {
    var pages = Math.ceil(state.filtered.length / PAGE_SIZE);
    var pager = $("#baPager");
    if (pages <= 1) {
      pager.innerHTML = "";
      return;
    }
    var html =
      '<button class="rn-ba-pg" data-pg="prev"' +
      (state.page === 0 ? " disabled" : "") +
      ">‹</button>";
    for (var i = 0; i < pages; i++) {
      html +=
        '<button class="rn-ba-pg' +
        (i === state.page ? " is-active" : "") +
        '" data-pg="' +
        i +
        '">' +
        (i + 1) +
        "</button>";
    }
    html +=
      '<button class="rn-ba-pg" data-pg="next"' +
      (state.page >= pages - 1 ? " disabled" : "") +
      ">›</button>";
    pager.innerHTML = html;
  }

  /* ---------- selection + right rail ---------- */

  function select(id) {
    state.selectedId = id;
    renderTable();
    renderSummary();
  }

  function selectedEvent() {
    return state.events.filter(function (e) {
      return e.id === state.selectedId;
    })[0];
  }

  function renderSummary() {
    var ev = selectedEvent();
    var card = $("#baSummaryCard");
    var statusChip = $("#baSummaryStatus");
    var isu = $("#baIsuList");

    if (!ev) {
      card.innerHTML = '<p class="rn-muted">Pilih bencana dari daftar.</p>';
      statusChip.hidden = true;
      isu.innerHTML = '<p class="rn-muted">—</p>';
      return;
    }

    statusChip.hidden = false;
    statusChip.textContent = ev.status_label;
    statusChip.className = "chip rn-ba-pill " + statusClass(ev.status_label);

    card.innerHTML =
      '<div class="rn-ba-sum-head">' +
      '<span class="rn-ba-sum-ic" aria-hidden="true">▲</span>' +
      "<div><b>" +
      esc(ev.name) +
      "</b><small>" +
      esc(ev.location) +
      "</small></div>" +
      "</div>" +
      '<div class="rn-ba-sum-meta">' +
      "<span>ID: " +
      esc(shortId(ev.id)) +
      "</span><span>Diperbarui " +
      relTime(ev.last_updated) +
      "</span>" +
      "</div>" +
      '<div class="rn-ba-sum-stats">' +
      statBox("Jiwa Berisiko", fmt(ev.jiwa_berisiko)) +
      statBox("Kebutuhan Kritis", fmt(ev.kebutuhan_kritis)) +
      statBox("Pengungsi", fmt(ev.pengungsi)) +
      statBox("Distribusi Terhambat", fmt(ev.distribusi_terhambat)) +
      "</div>";

    var items = ev.isu_kritis || [];
    if (!items.length) {
      isu.innerHTML = '<p class="rn-muted">Tidak ada isu kritis tercatat.</p>';
    } else {
      isu.innerHTML = items
        .map(function (it) {
          var inner =
            '<span class="rn-ba-isu-ic" aria-hidden="true">' +
            (it.kind === "posko" ? "⚑" : "▤") +
            "</span>" +
            "<div><b>" +
            esc(it.title) +
            "</b><small>" +
            esc(it.detail || "") +
            "</small></div>" +
            '<span class="rn-ba-lvl ' +
            (String(it.level).toLowerCase().indexOf("sangat") === 0
              ? "is-hi"
              : "is-mid") +
            '">' +
            esc(it.level) +
            "</span>";
          return it.href
            ? '<a class="rn-ba-isu-item is-link" href="' + esc(it.href) + '">' + inner + "</a>"
            : '<div class="rn-ba-isu-item">' + inner + "</div>";
        })
        .join("");
    }

    var evParam = "event=" + encodeURIComponent(shortId(ev.id));
    $("#baOpenWarRoom").href = "war-room.html?" + evParam;
    $("#baOpenDetail").href = "disaster-detail.html?" + evParam;
  }

  function statBox(label, value) {
    return (
      '<div class="rn-ba-stat"><span>' +
      label +
      "</span><b>" +
      value +
      "</b></div>"
    );
  }

  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  /* ---------- events ---------- */

  function wire() {
    document.querySelectorAll(".rn-kpi-btn").forEach(function (btn) {
      btn.addEventListener("click", function () {
        if (!state.events.length) return;
        openDrill(btn.getAttribute("data-kpi"));
      });
    });

    $("#baDrill").addEventListener("click", function (e) {
      if (e.target.closest("[data-close]")) {
        closeDrill();
        return;
      }
      var row = e.target.closest(".rn-ba-drow[data-select]");
      if (row) {
        select(row.getAttribute("data-select"));
        closeDrill();
        $(".rn-ba-list-panel").scrollIntoView({ behavior: "smooth", block: "start" });
      }
    });

    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && !$("#baDrill").hidden) closeDrill();
    });

    $("#baSearch").addEventListener("input", function () {
      state.page = 0;
      applyFilter();
    });

    $("#baExpandAll").addEventListener("click", function () {
      state.expandAll = !state.expandAll;
      this.textContent = state.expandAll ? "Tutup Semua" : "Buka Semua";
      renderTable();
    });

    $("#baPager").addEventListener("click", function (e) {
      var btn = e.target.closest("[data-pg]");
      if (!btn || btn.disabled) return;
      var pg = btn.getAttribute("data-pg");
      var pages = Math.ceil(state.filtered.length / PAGE_SIZE);
      if (pg === "prev") state.page = Math.max(0, state.page - 1);
      else if (pg === "next") state.page = Math.min(pages - 1, state.page + 1);
      else state.page = parseInt(pg, 10) || 0;
      renderTable();
    });

    $("#baTableBody").addEventListener("click", function (e) {
      var row = e.target.closest("tr.rn-ba-row");
      if (!row) return;
      var id = row.getAttribute("data-id");
      if (e.target.closest(".rn-ba-caret")) {
        if (state.expandAll) {
          state.expandAll = false;
          $("#baExpandAll").textContent = "Buka Semua";
          state.events.forEach(function (ev) {
            state.expanded[ev.id] = true;
          });
        }
        state.expanded[id] = !state.expanded[id];
        renderTable();
        return;
      }
      select(id);
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    wire();
    load();
  });
})();
