/* Bencana Aktif dashboard — pages/bencana-aktif.html
 * Reads rescue_net.api_control_centre.active_disasters_board (guest).
 * Left: paginated, expandable per-region list. Right: selected-event summary.
 */
(function () {
  "use strict";

  var PAGE_SIZE = 7;
  var METHOD = "rescue_net.api_control_centre.active_disasters_board";

  var state = {
    events: [],
    filtered: [],
    totals: {},
    page: 0,
    selectedId: null,
    expanded: {},
    expandAll: false,
    // "Jiwa Berisiko" drill is 2 steps: null = level 1 (category list per
    // event), {eventId,key} = level 2 (that one category's specific
    // posko/laporan items). Reset to null every time the modal (re)opens.
    jiwaOpen: null,
    // Set when a drill was opened by clicking a number in the table
    // (main row or an expanded region row) instead of the top KPI card —
    // scopes the drill to that one disaster instead of every active one.
    drillFocusEventId: null,
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
    var sec = Math.round(diff / 1000);
    if (sec < 60) return sec < 10 ? "baru saja" : sec + " detik lalu";
    var m = Math.round(diff / 60000);
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

  // owner 2026-11-09: "update terakhir pastikan bener2 real time" — muat ulang diam-diam tiap 60 detik,
  // label waktu relatif diperbarui tiap 15 detik, jam data ditampilkan apa adanya.
  var GENERATED_AT = null;
  function clock(iso) {
    var d = new Date(String(iso || "").replace(" ", "T"));
    return isNaN(d.getTime()) ? "" : d.toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  }
  function paintUpdated() {
    var el = $("#baUpdated");
    if (!el || !GENERATED_AT) return;
    el.textContent = "Data pukul " + clock(GENERATED_AT) + " · " + relTime(GENERATED_AT) + " · otomatis tiap 60 dtk";
  }
  var boardRequest = 0;
  function quietReload() {
    if (document.hidden) return;
    var request = ++boardRequest;
    publicCall(METHOD).then(function (res) {
      if (request !== boardRequest) return;
      var data = res || {};
      state.events = data.events || [];
      state.totals = data.totals || {};
      GENERATED_AT = data.generated_at;
      renderKpi(state.totals);
      setStatus("");
      if (!selectedEvent()) state.selectedId = state.events[0]?.id || null;
      applyFilter();
      renderSummary();
      renderMap(true);
      loadOperations(selectedEvent(), true);
      paintUpdated();
    }).catch(function () { /* coba lagi di putaran berikut */ });
  }
  setInterval(quietReload, 60000);
  setInterval(function () { paintUpdated(); if (!document.hidden) applyFilter(); }, 15000);
  document.addEventListener("visibilitychange", function () { if (!document.hidden) quietReload(); });

  function load() {
    var request = ++boardRequest;
    setStatus("Memuat data bencana…");
    return publicCall(METHOD)
      .then(function (res) {
        if (request !== boardRequest) return;
        var data = res || {};
        state.events = data.events || [];
        state.totals = data.totals || {};
        renderKpi(state.totals);
        GENERATED_AT = data.generated_at;
        paintUpdated();
        applyFilter();
        renderMap();
        var requested = new URLSearchParams(location.search).get("event");
        var initial = state.events.find(function (ev) {
          return requested && (ev.event_id === requested || shortId(ev.id) === shortId(requested));
        }) || state.events[0];
        if (initial) select(initial.id, true);
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

  function openDrill(kind, focusEventId) {
    var cfg = DRILL[kind];
    if (!cfg) return;
    state.jiwaOpen = null;
    // A click on a number in the "Daftar Bencana Aktif" table (main row
    // or an expanded region row) — those numbers used to just sit there
    // with no click handler at all. Now they open the SAME drill as the
    // KPI card above, but scoped to just that one disaster instead of
    // every active one.
    state.drillFocusEventId = focusEventId || null;
    $("#baDrillTitle").textContent = cfg.title;
    $("#baDrillBody").innerHTML = renderDrill(kind);
    var focusEv = state.drillFocusEventId
      ? state.events.filter(function (e) { return e.id === state.drillFocusEventId; })[0]
      : null;
    var sub = "";
    if (focusEv) {
      if (kind === "kebutuhan") sub = fmt(focusEv.kebutuhan_kritis) + " item di " + focusEv.name;
      else if (kind === "distribusi") sub = fmt(focusEv.distribusi_terhambat) + " item di " + focusEv.name;
      else if (kind === "jiwa") sub = fmt(focusEv.jiwa_berisiko) + " jiwa berisiko di " + focusEv.name + (focusEv.jiwa_missing_poskos ? " · " + focusEv.jiwa_missing_poskos + " posko belum melaporkan jumlah jiwa" : "");
    } else if (kind === "kebutuhan")
      sub = fmt(state.totals.kebutuhan_kritis) + " item · klik untuk buka posko & isi bantuan";
    else if (kind === "distribusi")
      sub = fmt(state.totals.distribusi_terhambat) + " item";
    else if (kind === "jiwa")
      sub = "Total " + fmt(state.totals.jiwa_berisiko) + " jiwa berisiko (pasien ditangani, penghuni shelter overload, jiwa yang kebutuhan mendesaknya belum dikirim)";
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
    var evs = state.drillFocusEventId
      ? state.events.filter(function (e) { return e.id === state.drillFocusEventId; })
      : state.events;

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
      // Level 2: one category already picked — show exactly what's
      // wrong and where (posko/laporan), with a way back to the
      // category list. Owner: a number with nowhere to click into
      // "posko medis mana yang bermasalah" isn't good enough.
      if (state.jiwaOpen) {
        var openEv = evs.filter(function (e) { return e.id === state.jiwaOpen.eventId; })[0];
        var cat = openEv && (openEv.jiwa_categories || [])
          .filter(function (c) { return c.key === state.jiwaOpen.key; })[0];
        if (!openEv || !cat) {
          state.jiwaOpen = null;
          return renderDrill("jiwa");
        }
        var detailRows = (cat.items || [])
          .map(function (it) {
            return (
              '<a class="rn-ba-ditem" href="' + esc(it.href) + '">' +
              "<span><b>" + esc(it.title) + "</b><small>" +
              esc(it.detail || "") + (it.region ? " · " + esc(it.region) : "") + "</small></span>" +
              '<span class="rn-ba-pill is-kritis">' + fmt(it.count) + "</span>" +
              '<span class="rn-ba-ditem-go">→</span>' +
              "</a>"
            );
          })
          .join("");
        return (
          '<button type="button" class="btn ghost mini rn-ba-back" data-jiwa-back>← Kembali ke daftar kategori</button>' +
          drillGroup(openEv, '<div class="rn-ba-ditems">' +
            (detailRows || '<p class="rn-muted">Tidak ada rincian.</p>') + "</div>")
        );
      }

      // Level 1: WHAT is critical, per event, not just how many people —
      // each category is a button into level 2 above.
      return evs
        .filter(function (ev) { return ev.jiwa_berisiko > 0 || (ev.jiwa_categories || []).some(function (c) { return c.count; }); })
        .sort(function (a, b) { return b.jiwa_berisiko - a.jiwa_berisiko; })
        .map(function (ev) {
          // one row per posko (jiwa_poskos): the per-category list used to
          // repeat the same posko once per problem. Old backend: categories.
          var perPosko = ev.jiwa_poskos;
          var catList = (ev.jiwa_categories || []).filter(function (c) {
            return !perPosko || c.key === "laporan_korban" || c.key === "jiwa_belum_lapor";
          });
          var poskoRows = (perPosko || [])
            .map(function (r) {
              var lines = (r.problems || []).map(function (pb) {
                return "<small>" + (pb.is_jiwa ? "" : "⚠ ") + esc(pb.label) + ": " + esc(pb.detail || fmt(pb.count)) + "</small>";
              }).join("");
              return (
                '<a class="rn-ba-ditem" href="' + esc(r.href) + '">' +
                "<span><b>" + esc(r.title) + "</b>" + lines +
                (r.region ? "<small>" + esc(r.region) + "</small>" : "") + "</span>" +
                '<span class="rn-ba-pill ' + (r.jiwa ? "is-kritis" : "is-siaga") + '">' +
                (r.jiwa ? fmt(r.jiwa) + " jiwa" : (r.problems || []).length + " masalah") + "</span>" +
                '<span class="rn-ba-ditem-go">→</span>' +
                "</a>"
              );
            })
            .join("");
          var aspects = ev.jiwa_aspects
            ? '<p class="rn-muted">Jiwa per aspek: logistik ' + fmt(ev.jiwa_aspects.logistik) +
              " · shelter " + fmt(ev.jiwa_aspects.shelter) + " · medis " + fmt(ev.jiwa_aspects.medis) + "</p>"
            : "";
          var cats = catList
            .map(function (c) {
              var disabled = !c.count;
              return (
                '<button type="button" class="rn-ba-ditem rn-ba-catbtn' + (disabled ? " is-disabled" : "") + '"' +
                (disabled ? " disabled" : (' data-jiwa-cat="' + esc(c.key) + '" data-jiwa-event="' + esc(ev.id) + '"')) + ">" +
                "<span><b>" + esc(c.label) + "</b></span>" +
                '<span class="rn-ba-pill ' + (c.count ? "is-kritis" : "is-ok") + '">' + fmt(c.count) + "</span>" +
                (disabled ? "" : '<span class="rn-ba-ditem-go">→</span>') +
                "</button>"
              );
            })
            .join("");

          var links =
            '<div class="rn-ba-drill-links">' +
            '<a class="btn ghost mini" href="war-room.html?event=' +
            encodeURIComponent(shortId(ev.id)) + '">Buka Control Centre ↗</a>' +
            '<a class="btn ghost mini" href="laporan-masyarakat.html?event=' +
            encodeURIComponent(shortId(ev.id)) + '">Semua Laporan Masyarakat ↗</a>' +
            '<a class="btn ghost mini" href="data-consolidation.html?event=' +
            encodeURIComponent(shortId(ev.id)) + '">Data Konsolidasi (AI) ↗</a>' +
            "</div>";

          return drillGroup(ev, (perPosko ? aspects + '<div class="rn-ba-ditems">' + poskoRows + "</div>" : "") +
            '<div class="rn-ba-ditems">' + cats + "</div>" + links);
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
        // Raw per-posko needs/flows above are un-consolidated (no dedup/MAX
        // across overlapping reports) — link out to the AI rollup so an
        // operator can cross-check before deciding what to send.
        var consolidationLink =
          '<a class="btn ghost mini" href="data-consolidation.html?event=' +
          encodeURIComponent(shortId(ev.id)) +
          '">Lihat Analisa AI / Data Konsolidasi ↗</a>';
        return drillGroup(
          ev,
          '<div class="rn-ba-ditems">' + rows + "</div>" + consolidationLink
        );
      })
      .join("");
  }

  /* ---------- filter + pagination ---------- */

  function applyFilter() {
    var q = ($("#baSearch").value || "").trim().toLowerCase();
    // owner 2026-11-12: cari juga berdasarkan WILAYAH (kabupaten/kota tempat posko bencana itu). Bencana yang cocok
    // karena wilayahnya dibuka otomatis supaya baris wilayah yang dicari langsung terlihat.
    state.regionHit = {};
    state.filtered = state.events.filter(function (ev) {
      if (!q && !state.wil) return true;
      var regionMatch = (ev.regions || []).some(function (rg) { return String(rg.name || "").toLowerCase().indexOf(q) !== -1; });
      var areaMatch = (ev.area_names || []).some(function (n) { return String(n).toLowerCase().indexOf(q) !== -1; }) ||
        !!(state.areaHit[ev.id] && state.areaQ === q);
      if (regionMatch || areaMatch) state.regionHit[ev.id] = true;
      if (state.wil && !state.wil.hits[ev.id]) return false;          // pilihan lokasi bertingkat
      if (state.wil) state.regionHit[ev.id] = true;
      if (!q) return true;
      return (
        areaMatch ||
        (ev.name || "").toLowerCase().indexOf(q) !== -1 ||
        (ev.location || "").toLowerCase().indexOf(q) !== -1 ||
        shortId(ev.id).toLowerCase().indexOf(q) !== -1 ||
        regionMatch
      );
    });
    var maxPage = Math.max(0, Math.ceil(state.filtered.length / PAGE_SIZE) - 1);
    if (state.page > maxPage) state.page = maxPage;
    renderAreaHint(q);
    renderTable();
  }

  /* ---------- owner 2026-11-12: cari sampai desa/kelurahan (data wilayah Kemendagri di RN) ----------
   * Nama yang diketik dicari di daftar wilayah resmi; bencana cocok bila poskonya berada di wilayah itu,
   * atau wilayah itu berada di dalam kab/kota/kecamatan tempat posko bencana tersebut. */
  state.areaHit = {}; state.areaInfo = {}; state.areaQ = ""; state.areaFound = [];
  var areaTimer = null, areaSeq = 0;
  function areaWithin(a, c) { return a === c || a.indexOf(c + ".") === 0 || c.indexOf(a + ".") === 0; }
  function lookupAreas(q) {
    clearTimeout(areaTimer);
    if (q.length < 3) { state.areaHit = {}; state.areaInfo = {}; state.areaQ = ""; state.areaFound = []; return; }
    var seq = ++areaSeq;
    areaTimer = setTimeout(function () {
      fetch("/rescue-net-frappe/api/method/rescue_net.api_control_centre.cari_wilayah_bencana?q=" + encodeURIComponent(q), { credentials: "include" })
        .then(function (r) { return r.ok ? r.json() : null; })
        .then(function (j) {
          if (seq !== areaSeq) return;
          var areas = (j && j.message) || [];
          state.areaHit = {}; state.areaInfo = {}; state.areaQ = q; state.areaFound = areas;
          state.events.forEach(function (ev) {
            var codes = ev.area_codes || [];
            areas.forEach(function (a) {
              if (codes.some(function (c) { return areaWithin(a.code, c); })) {
                state.areaHit[ev.id] = true;
                (state.areaInfo[ev.id] = state.areaInfo[ev.id] || []).push(a);
              }
            });
          });
          applyFilter();
        })
        .catch(function () {});
    }, 350);
  }
  /* ---------- owner 2026-11-12: pilihan lokasi bertingkat (seperti data.go.id) ---------- */
  state.wil = null;
  var WIL_API = "/rescue-net-frappe/api/method/rescue_net.api_admin_areas.get_children?";
  var WIL_ORDER = ["province", "city", "district", "village"];
  function wilFill(sel, parent) {
    var lv = sel.getAttribute("data-lv"), ph = sel.options[0].textContent;
    sel.innerHTML = '<option value="">Memuat…</option>';
    fetch(WIL_API + "level=" + lv + (parent ? "&parent_code=" + encodeURIComponent(parent) : ""), { credentials: "include" })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (j) {
        var rows = (j && j.message) || [];
        sel.innerHTML = '<option value="">' + ph + "</option>" + rows.map(function (a) {
          return '<option value="' + esc(a.code) + '">' + esc(a.area_name) + "</option>"; }).join("");
        sel.disabled = !rows.length;
      })
      .catch(function () { sel.innerHTML = '<option value="">' + ph + "</option>"; });
  }
  function wilApply() {
    var box = $("#baWil"); if (!box) return;
    var sels = box.querySelectorAll("select"), code = "", names = [];
    sels.forEach(function (s) { if (s.value) { code = s.value; names.push(s.selectedOptions[0].textContent); } });
    $("#baWilReset").hidden = !code;
    if (!code) { state.wil = null; }
    else {
      var hits = {};
      state.events.forEach(function (ev) {
        if ((ev.area_codes || []).some(function (c) { return areaWithin(code, c); })) hits[ev.id] = true;
      });
      state.wil = { code: code, label: names.reverse().join(", "), hits: hits };
    }
    state.page = 0; applyFilter();
  }
  function wilInit() {
    var box = $("#baWil"); if (!box) return;
    var sels = Array.prototype.slice.call(box.querySelectorAll("select"));
    wilFill(sels[0], "");
    sels.forEach(function (sel, i) {
      sel.addEventListener("change", function () {
        for (var k = i + 1; k < sels.length; k++) {
          sels[k].innerHTML = '<option value="">' + ["Provinsi", "Kab/Kota", "Kecamatan", "Desa/Kel."][k] + "</option>"; sels[k].disabled = true;
        }
        if (sel.value && sels[i + 1]) wilFill(sels[i + 1], sel.value);
        wilApply();
      });
    });
    $("#baWilReset").addEventListener("click", function () {
      sels.forEach(function (s, k) { if (k) { s.innerHTML = '<option value="">' + ["Provinsi", "Kab/Kota", "Kecamatan", "Desa/Kel."][k] + "</option>"; s.disabled = true; } else s.value = ""; });
      wilApply();
    });
  }

  function renderAreaHint(q) {
    var el = $("#baAreaHint");
    if (!el) {
      el = document.createElement("div"); el.id = "baAreaHint";
      el.style.cssText = "margin:6px 0 10px;padding:8px 12px;border-radius:10px;font-size:13px;line-height:1.5;background:rgba(104,64,45,.05);border:1px solid rgba(104,64,45,.15)";
      var tbl = document.querySelector(".rn-ba-table"); if (!tbl) return;
      tbl.parentNode.insertBefore(el, tbl);
    }
    if (state.wil) {
      var nW = Object.keys(state.wil.hits).length;
      el.innerHTML = "Lokasi: <b>" + esc(state.wil.label) + "</b> — " + (nW
        ? nW + " bencana aktif dengan posko di wilayah ini atau di kecamatan/kab/kota yang mencakupnya."
        : "belum ada bencana aktif dengan posko di wilayah ini.");
      el.hidden = false; return;
    }
    if (!q || q.length < 3 || state.areaQ !== q) { el.hidden = true; return; }
    var ids = Object.keys(state.areaInfo);
    var raw = (($("#baSearch") || {}).value || q).trim();
    if (!state.areaFound.length) {
      if (state.filtered.length) { el.hidden = true; return; }
      el.innerHTML = "Tidak ada bencana atau wilayah resmi bernama <b>" + esc(raw) + "</b>."; el.hidden = false; return;
    }
    var lines = ids.map(function (id) {
      var ev = state.events.filter(function (e) { return e.id === id; })[0]; if (!ev) return "";
      var a = state.areaInfo[id].slice(0, 3).map(function (x) { return "<b>" + esc(x.label) + "</b>" + (x.path ? " (" + esc(x.path) + ")" : ""); }).join("; ");
      return "<li>" + a + " → <b>" + esc(ev.name) + "</b></li>";
    }).join("");
    el.innerHTML = ids.length
      ? "Wilayah ditemukan dan terkait bencana aktif (posko berada di wilayah itu atau di kecamatan/kab/kota yang sama):<ul style='margin:4px 0 0 18px;padding:0'>" + lines + "</ul>"
      : "Ditemukan " + state.areaFound.length + " wilayah bernama <b>" + esc(raw) + "</b> (mis. " +
        state.areaFound.slice(0, 2).map(function (x) { return esc(x.label + (x.path ? ", " + x.path : "")); }).join("; ") +
        "), tetapi belum ada posko bencana aktif di wilayah tersebut.";
    el.hidden = false;
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
      var open = state.expandAll || !!state.expanded[ev.id] || !!(state.regionHit && state.regionHit[ev.id]);
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
        '<td class="rn-ba-clickcell" data-drill-focus="jiwa">' +
        fmt(ev.jiwa_berisiko) +
        "</td>" +
        '<td class="rn-ba-clickcell" data-drill-focus="kebutuhan">' +
        fmt(ev.kebutuhan_kritis) +
        "</td>" +
        '<td class="rn-ba-clickcell" data-drill-focus="distribusi">' +
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
            '<td class="rn-ba-clickcell" data-drill-focus="jiwa">' +
            fmt(rg.jiwa_berisiko) +
            "</td>" +
            '<td class="rn-ba-clickcell" data-drill-focus="kebutuhan">' +
            fmt(rg.kebutuhan_kritis) +
            "</td>" +
            '<td class="rn-ba-clickcell" data-drill-focus="distribusi">' +
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

  function select(id, quiet) {
    state.selectedId = id;
    renderTable();
    renderSummary();
    focusMap(quiet);
    loadOperations(selectedEvent());
  }

  /* ---------- map (owner 2026-10-19): one marker per disaster at the
     centre of its poskos; the selected one also shows its posko dots ---------- */

  var map = null, eventLayer = null, poskoLayer = null;
  var SEV_COLOR = { critical: "#d84545", kritis: "#d84545", high: "#dd8a2f", tinggi: "#dd8a2f" };

  function sevColor(ev) { return SEV_COLOR[String(ev.severity || "").toLowerCase()] || "#b88918"; }

  function renderMap(keepView) {
    var host = $("#baMap");
    if (!host || !window.L) return;
    var withCenter = state.events.filter(function (e) { return e.center; });
    $("#baMapCount").textContent = withCenter.length;
    var note = $("#baMapNote");
    var missing = state.events.length - withCenter.length;
    if (note) {
      note.hidden = !missing;
      note.textContent = missing ? missing + " bencana belum tampil di peta karena posko-poskonya belum punya koordinat." : "";
    }
    if (!map) {
      map = L.map(host, { zoomControl: true, scrollWheelZoom: false }).setView([-2.5, 118], 5);
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 19, attribution: "© OpenStreetMap" }).addTo(map);
      eventLayer = L.layerGroup().addTo(map);
      poskoLayer = L.layerGroup().addTo(map);
      if (window.RNInaRisk) window.RNInaRisk.attach(map);
      // the panel stretches to the summary's height after the map is built:
      // re-measure whenever the box changes size, or tiles stay grey
      if (window.ResizeObserver) new ResizeObserver(function () { map.invalidateSize(); }).observe(host);
      window.addEventListener("load", function () { map.invalidateSize(); });
    }
    eventLayer.clearLayers();
    var bounds = [];
    withCenter.forEach(function (ev) {
      var ll = [ev.center.lat, ev.center.lng];
      bounds.push(ll);
      var m = L.circleMarker(ll, {
        radius: Math.min(22, 9 + Math.sqrt(ev.jiwa_berisiko || 0) / 2),
        color: "#fff", weight: 2, fillColor: sevColor(ev), fillOpacity: .9
      });
      m.bindTooltip(esc(ev.name), { direction: "top" });
      m.bindPopup('<div class="rn-ba-pop"><b>' + esc(ev.name) + "</b>" + esc(ev.location || "") +
        "<br>" + fmt(ev.jiwa_berisiko) + " jiwa berisiko · " + fmt(ev.posko_count) + " posko" +
        '<br><a href="war-room.html?event=' + encodeURIComponent(shortId(ev.id)) + '">Buka Control Centre ↗</a></div>');
      m.on("click", function () { select(ev.id); });
      m.addTo(eventLayer);
    });
    if (!keepView && bounds.length) map.fitBounds(bounds, { padding: [40, 40], maxZoom: 9 });
    setTimeout(function () { map.invalidateSize(); }, 50);
    focusMap(true);
  }

  function focusMap(quiet) {
    if (!map || !poskoLayer) return;
    poskoLayer.clearLayers();
    var ev = selectedEvent();
    if (!ev) return;
    var colors = { critical: "#a81d2b", warning: "#8a4d0d", safe: "#176548" };
    var labels = { critical: "Kritis", warning: "Waspada", safe: "Aman" };
    var pts = (ev.posko_points || []).map(function (p) {
      var point = operationalMap.get(p.name);
      var color = colors[point?.situation] || sevColor(ev);
      var label = labels[point?.situation];
      var title = esc(p.title || p.name);
      var href = p.href + "&event=" + encodeURIComponent(shortId(ev.id));
      L.circleMarker([p.lat, p.lng], { radius: 6, color: color, weight: 2, fillColor: color, fillOpacity: .8 })
        .bindTooltip(title + (label ? " · " + label : ""), { direction: "top" })
        .bindPopup("<b>" + title + "</b>" + (label ? "<br>" + label : "") +
          '<br><a href="' + esc(href) + '">Buka detail posko</a>')
        .addTo(poskoLayer);
      return [p.lat, p.lng];
    });
    if (quiet) return;                          // first load: keep the overview of all disasters
    if (pts.length > 1) map.flyToBounds(pts, { padding: [40, 40], maxZoom: 12, duration: .6 });
    else if (ev.center) map.flyTo([ev.center.lat, ev.center.lng], 10, { duration: .6 });
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
    $("#baOpenDetail").href = "back-office.html?" + evParam;
    $("#baOpenConsolidation").href = "data-consolidation.html?" + evParam;
  }

  // Control Centre membaca dashboard publik sebagai Guest, termasuk saat pengguna login.
  // Jangan bawa cookie sesi ke kartu publik. Mode tampilan dikirim eksplisit.
  function viewMode() {
    return /(?:^|;\s*)rn_tampilan=simulasi(?:;|$)/.test(document.cookie) ? "simulasi" : "riil";
  }

  async function publicCall(method, args) {
    var query = new URLSearchParams(args);
    query.set("rn_tampilan", viewMode());
    var response = await fetch("/rescue-net-frappe/api/method/" + method + "?" + query, {
      credentials: "omit",
      headers: { Accept: "application/json" }
    });
    if (!response.ok) throw new Error("HTTP " + response.status);
    return (await response.json()).message;
  }

  var operationKey = "";
  var operationRequest = 0;
  var operationalMap = new Map();

  function opsRows(rows) {
    return "<dl>" + rows.map(function (row) {
      return "<div><dt>" + esc(row[0]) + "</dt><dd>" +
        (typeof row[1] === "number" ? fmt(row[1]) : esc(row[1] ?? "—")) + "</dd></div>";
    }).join("") + "</dl>";
  }

  function opsCard(title, body, link, label) {
    return '<article class="rn-ba-ops-card"><h4>' + esc(title) + "</h4>" + body +
      (link ? '<a href="' + esc(link) + '">' + esc(label) + "</a>" : "") + "</article>";
  }

  function opsList(items) {
    return "<ul>" + items.map(function (item) {
      return "<li>" + esc(item) + "</li>";
    }).join("") + "</ul>";
  }

  function dashboardCards(data, ev, link) {
    var ctx = data.context || {};
    var summary = ctx.summary || {};
    var kpi = ctx.kpi_totals || {};
    var mapSummary = data.map?.summary || {};
    var priorities = (ctx.recommendations || []).concat(ctx.alerts || []).slice(0, 5)
      .map(function (row) { return row.title || row.recommendation || row.message; }).filter(Boolean);
    var needs = (ctx.logistic_needs || []).filter(function (row) {
      return !["closed", "cancelled", "fulfilled"].includes(String(row.status || "").toLowerCase());
    }).map(function (row) {
      var required = Number(row.quantity_required || row.required_quantity || row.quantity || 0);
      var fulfilled = Number(row.realized_quantity || row.fulfilled_quantity || row.delivered_quantity ||
        row.quantity_fulfilled || row.quantity_delivered || 0);
      return { item: row.item_name || row.item_text || row.need_name, unit: row.unit,
        required: required, fulfilled: fulfilled, gap: Math.max(0, required - fulfilled) };
    }).filter(function (row) { return row.item; }).sort(function (a, b) { return b.gap - a.gap; }).slice(0, 6);
    return [
      opsCard("Korban dan pengungsi", opsRows([
        ["Jiwa dilayani posko", kpi.base?.jiwa], ["Jiwa berisiko", kpi.jiwa],
        ["Risiko dari logistik", kpi.jiwa_aspects?.logistik],
        ["Risiko dari shelter", kpi.jiwa_aspects?.shelter], ["Risiko dari medis", kpi.jiwa_aspects?.medis],
        ["Posko belum lapor jumlah jiwa", kpi.jiwa_missing], ["Kasus medis tercatat", kpi.medis], ["Laporan orang hilang", summary.missing_person_count],
        ["Laporan orang ditemukan", summary.found_person_count], ["Pengungsi", ev.pengungsi],
        ["Catatan okupansi shelter", summary.shelter_occupancy_count]
      ]), link("search-found"), "Buka Search & Found"),
      opsCard("Posko dan peta", opsRows([
        ["Posko tercatat", ev.posko_count], ["Posko kritis", kpi.posko_kritis],
        ["Titik pada peta Control Centre", mapSummary.total], ["Titik waspada", mapSummary.warning],
        ["Titik aman", mapSummary.safe]
      ]), "#baMap", "Lihat peta Bencana Aktif"),
      opsCard("Logistik dan kebutuhan", opsRows([
        ["Catatan stok barang", kpi.stok], ["Kebutuhan terbuka", summary.open_need_count],
        ["Kebutuhan kritis", ev.kebutuhan_kritis], ["Kebutuhan shelter", summary.shelter_need_count],
        ["Tawaran belum tersalur", kpi.donasi]
      ]), link("kebutuhan-publik"), "Lihat kebutuhan publik"),
      opsCard("Distribusi", opsRows([
        ["Alur bantuan", kpi.distribusi], ["Alur terhambat", kpi.distribusi_terhambat]
      ]), link("management-distribusi"), "Buka Manajemen Distribusi"),
      opsCard("Relawan dan program", opsRows([
        ["Penugasan relawan", kpi.relawan], ["Program berjalan", kpi.program]
      ]), link("program-khusus"), "Buka Program Khusus"),
      opsCard("Laporan masyarakat dan bukti", opsRows([
        ["Laporan dalam dashboard publik", (data.community_reports || []).length],
        ["Bukti dalam dashboard publik", (data.evidence || []).length]
      ]), link("evidence"), "Buka bukti lapangan"),
      opsCard("Kebutuhan dan pemenuhan", needs.length ? opsList(needs.map(function (row) {
        return row.item + " · kebutuhan " + fmt(row.required) + " · terpenuhi " + fmt(row.fulfilled) +
          " · kurang " + fmt(row.gap) + (row.unit ? " " + row.unit : "");
      })) : "<p>Belum ada kebutuhan terbuka dalam dashboard.</p>", link("war-room"), "Buka rincian per posko"),
      opsCard("Prioritas penanganan", priorities.length ? opsList(priorities) : "<p>Belum ada prioritas tercatat.</p>",
        link("war-room"), "Buka daftar prioritas"),
      activityCard(ctx.trends, link),
      opsCard("Laporan Situasi (SITREP)", "<p>Laporan per periode mencakup perubahan situasi, layanan dan koordinasi.</p>",
        link("sitrep"), "Buka laporan situasi bencana")
    ].join("");
  }

  function activityCard(trends, link) {
    var days = trends?.days || [];
    var series = [
      ["logistics", "Logistik"], ["distribution", "Distribusi"], ["medical", "Medis"],
      ["volunteer", "Relawan"], ["program", "Program"], ["search_found", "Search & Found"]
    ];
    var periods = days.map(function (day, i) {
      return '<details><summary>' + esc(day) + '</summary>' + opsRows(series.map(function (item) {
        return [item[1], trends[item[0]]?.[i]];
      })) + '</details>';
    }).reverse();
    return opsCard("Tren aktivitas", periods.length ? periods.join("") : "<p>Tren belum tersedia.</p>",
      link("war-room"), "Lihat grafik di Control Centre");
  }

  function loadOperations(ev, refresh) {
    var grid = $("#baOpsGrid");
    var status = $("#baOpsStatus");
    var mode = viewMode();
    var key = ev ? mode + ":" + ev.id : "";
    if (key === operationKey && (!refresh || grid.contains(document.activeElement))) return;
    var changed = key !== operationKey;
    operationKey = key;
    var request = ++operationRequest;
    if (changed) {
      grid.replaceChildren();
      operationalMap.clear();
      focusMap(true);
    }
    if (!ev) {
      status.textContent = "Pilih bencana dari daftar.";
      return;
    }

    var label = ev.name + " · " + (mode === "simulasi" ? "Tampilan Simulasi" : "Tampilan Riil");
    status.textContent = label;
    var id = ev.event_id || shortId(ev.id);
    var link = function (page) { return page + ".html?event=" + encodeURIComponent(id); };
    var sections = [
      ["Data Control Centre", "rescue_net.api_control_centre.public_dashboard", { disaster_event_id: id },
        function (data) {
          if (request === operationRequest) {
            operationalMap = new Map((data.map?.points || []).map(function (point) {
              return [point.posko_id, point];
            }));
            focusMap(true);
          }
          return dashboardCards(data, ev, link);
        }],
      ["Donasi, tender dan pelacakan program", "rescue_net.api_donor_program.program_kpi",
        { disaster_event: id }, function (data) {
          var donor = data.donor || {};
          var tender = data.tender || {};
          var tracking = data.tracking || {};
          var rupiah = function (value) { return value == null ? "—" : "Rp " + fmt(value); };
          return [
            opsCard("Donasi terarah", opsRows([
              ["Program donasi", donor.programs], ["Donatur", donor.donors],
              ["Dana diterima", rupiah(donor.received)], ["Target", rupiah(donor.target)]
            ]), link("donor-program"), "Buka Donor Program"),
            opsCard("Pengadaan dan tender", opsRows([
              ["Tender", tender.total], ["Terbuka", tender.open], ["Sudah ada pemenang", tender.awarded],
              ["Penawaran", tender.bids], ["Nilai RAB", rupiah(tender.rab_total)]
            ]), link("pengadaan-tender"), "Buka Pengadaan & Tender"),
            opsCard("Pelacakan program", opsRows([
              ["Aktif", tracking.active], ["Kritis", tracking.critical], ["Selesai", tracking.done],
              ["Target tahap terlambat", tracking.late_milestones], ["Lokasi belum terlayani", tracking.unserved_locations]
            ]), link("program-khusus"), "Buka Program Khusus")
          ].join("");
        }],
      ["Armada", "rescue_net.api_armada.armada_finder", { disaster_event: id }, function (data) {
        var counts = data.counts || {};
        return opsCard("Armada", opsRows([
          ["Tersedia", counts.tersedia ?? 0], ["Penuh", counts.penuh ?? 0], ["Dipakai", counts.dipakai ?? 0],
          ["Jadwal lewat", counts.lewat ?? 0], ["Selesai", counts.selesai ?? 0]
        ]), link("management-distribusi"), "Lihat rincian distribusi dan armada");
      }],
      ["Akses dan infrastruktur", "rescue_net.api_access_status.board", { disaster_event: id }, function (data) {
        var summary = data.summary || [];
        var items = (data.items || []).slice(0, 5).map(function (item) {
          return item.place_name + " · " + (item.status === "closed" ? "Ditutup" : "Terbatas");
        });
        return opsCard("Akses dan infrastruktur", (summary.length ? opsRows(summary.map(function (row) {
          return [row.label, fmt(row.closed) + " ditutup · " + fmt(row.limited) + " terbatas"];
        })) : "<p>Belum ada status akses tercatat.</p>") + (items.length ? opsList(items) : ""),
        link("status-akses"), "Buka Status Akses");
      }]
    ];
    if (changed) status.textContent = label + " · Memuat…";
    Promise.all(sections.map(async function (section) {
      try {
        return section[3](await publicCall(section[1], section[2]));
      } catch (error) {
        return opsCard(section[0], "<p>Data belum dapat dimuat. Halaman akan mencoba lagi.</p>");
      }
    })).then(function (cards) {
      if (request !== operationRequest) return;
      var openPeriods = Array.from(grid.querySelectorAll("details[open]"), function (el) {
        return el.querySelector("summary").textContent;
      });
      grid.innerHTML = cards.join("");
      grid.querySelectorAll("details").forEach(function (el) {
        el.open = openPeriods.includes(el.querySelector("summary").textContent);
      });
      status.textContent = label;
    });
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
        return;
      }
      var catBtn = e.target.closest("[data-jiwa-cat]");
      if (catBtn) {
        state.jiwaOpen = {
          eventId: catBtn.getAttribute("data-jiwa-event"),
          key: catBtn.getAttribute("data-jiwa-cat"),
        };
        $("#baDrillBody").innerHTML = renderDrill("jiwa");
        return;
      }
      if (e.target.closest("[data-jiwa-back]")) {
        state.jiwaOpen = null;
        $("#baDrillBody").innerHTML = renderDrill("jiwa");
      }
    });

    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && !$("#baDrill").hidden) closeDrill();
    });

    wilInit();
    $("#baSearch").addEventListener("input", function () {
      state.page = 0;
      lookupAreas((this.value || "").trim().toLowerCase());
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
      // A number cell (main row or an expanded region row) — open that
      // KPI's drill scoped to just this one disaster, same as clicking
      // the KPI card up top but focused. Checked first since a region
      // row (tr.rn-ba-sub) isn't a tr.rn-ba-row and the row-select logic
      // below would just silently do nothing for it.
      var cell = e.target.closest("[data-drill-focus]");
      if (cell) {
        var anyRow = e.target.closest("tr[data-id]");
        if (anyRow) openDrill(cell.getAttribute("data-drill-focus"), anyRow.getAttribute("data-id"));
        return;
      }

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
