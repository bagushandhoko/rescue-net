/* RNEventChecklist — pilih bencana yang ditangani posko (owner 2026-10-19).
 * Kartu dengan kotak centang (beberapa bencana: posko logistik / distribusi)
 * atau pilihan tunggal (jenis posko lain), cari nama/lokasi, dan rentang
 * waktu mulai bencana. Default: SEMUA bencana tampil.
 * Data: rescue_net.api_community_cluster.disaster_options (sekali muat,
 * filter di HP/browser).
 *
 *   var picker = RNEventChecklist.mount(el, { selected: [ids], multiple: true, onChange: fn });
 *   picker.getSelected()      -> [event names]
 *   picker.setSelected(ids)   picker.setMultiple(bool)   picker.ready (Promise)
 */
(function () {
  "use strict";

  var CACHE = null;
  function load() {
    if (!CACHE) {
      CACHE = window.RN_FRAPPE.call("rescue_net.api_community_cluster.disaster_options")
        .then(function (r) { return Array.isArray(r) ? r : []; })
        .catch(function (e) { CACHE = null; throw e; });
    }
    return CACHE;
  }

  function esc(v) {
    return String(v == null ? "" : v).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function bare(x) { return String(x || "").replace(/^disaster_events:/, ""); }
  function day(v) { return v ? String(v).slice(0, 10) : ""; }
  function fmtDate(v) {
    if (!v) return "tanggal mulai belum diisi";
    var d = new Date(String(v).replace(" ", "T"));
    return isNaN(d) ? day(v) : d.toLocaleDateString("id-ID", { day: "numeric", month: "short", year: "numeric" });
  }
  function isoDaysAgo(n) {
    var d = new Date(); d.setDate(d.getDate() - n);
    return d.toISOString().slice(0, 10);
  }

  var RANGES = [
    { key: "all", label: "Semua" },
    { key: "7", label: "7 hari" },
    { key: "30", label: "30 hari" },
    { key: "90", label: "3 bulan" },
    { key: "year", label: "Tahun ini" },
    { key: "custom", label: "Pilih tanggal" },
  ];

  var SEQ = 0;

  function mount(root, opts) {
    opts = opts || {};
    var uid = "rnevc" + (++SEQ);
    var state = {
      list: [], selected: [], multiple: opts.multiple !== false,
      q: "", range: "all", from: "", to: "",
    };
    (opts.selected || []).forEach(function (s) { if (s) state.selected.push(String(s)); });

    root.classList.add("rn-evc");
    root.innerHTML =
      '<div class="rn-evc-tools">' +
        '<input type="search" class="rn-evc-search" id="' + uid + '-q" placeholder="Cari nama atau lokasi bencana…" aria-label="Cari bencana">' +
        '<div class="rn-evc-range" role="group" aria-label="Rentang waktu mulai bencana">' +
          RANGES.map(function (r) {
            return '<button type="button" data-range="' + r.key + '" aria-pressed="' + (r.key === "all") + '">' + r.label + "</button>";
          }).join("") +
        "</div>" +
        '<div class="rn-evc-dates" hidden>' +
          '<label>Dari <input type="date" id="' + uid + '-from"></label>' +
          '<label>Sampai <input type="date" id="' + uid + '-to"></label>' +
        "</div>" +
      "</div>" +
      '<div class="rn-evc-summary" aria-live="polite"></div>' +
      '<div class="rn-evc-grid"><div class="rn-evc-empty">Memuat daftar bencana…</div></div>';

    var grid = root.querySelector(".rn-evc-grid");
    var summary = root.querySelector(".rn-evc-summary");
    var dates = root.querySelector(".rn-evc-dates");

    function isSel(id) {
      return state.selected.some(function (s) { return bare(s) === bare(id); });
    }

    function visible() {
      var q = state.q.toLowerCase();
      var from = "", to = "";
      if (state.range === "custom") { from = state.from; to = state.to; }
      else if (state.range === "year") { from = new Date().getFullYear() + "-01-01"; }
      else if (state.range !== "all") { from = isoDaysAgo(Number(state.range)); }
      return state.list.filter(function (e) {
        if (q && (e.title + " " + (e.location || "")).toLowerCase().indexOf(q) === -1) return false;
        var d = day(e.started_at);
        if (from && (!d || d < from)) return false;
        if (to && (!d || d > to)) return false;
        return true;
      });
    }

    function render() {
      var rows = visible();
      grid.innerHTML = rows.length ? rows.map(function (e) {
        var on = isSel(e.id);
        var sev = String(e.severity || "").toLowerCase();
        var sevCls = /crit|darurat/.test(sev) ? "critical" : /high|urgent|tinggi/.test(sev) ? "high" : "";
        return '<label class="rn-evc-card' + (on ? " is-on" : "") + '">' +
          '<input type="' + (state.multiple ? "checkbox" : "radio") + '" name="' + uid + '-ev" value="' + esc(e.id) + '"' + (on ? " checked" : "") + ">" +
          '<span class="rn-evc-title">' + esc(e.title) + "</span>" +
          '<span class="rn-evc-meta"><span class="rn-evc-dot ' + sevCls + '" title="Tingkat: ' + esc(e.severity || "-") + '"></span>' +
            "Mulai " + esc(fmtDate(e.started_at)) +
            ' <span class="rn-evc-badge' + (e.active ? "" : " closed") + '">' + (e.active ? "Aktif" : esc(e.status || "Selesai")) + "</span></span>" +
          (e.location ? '<span class="rn-evc-loc">' + esc(e.location) + "</span>" : "<span></span>") +
        "</label>";
      }).join("") : '<div class="rn-evc-empty">Tidak ada bencana pada rentang / pencarian ini.</div>';

      var shownIds = rows.map(function (e) { return bare(e.id); });
      var hidden = state.selected.filter(function (s) { return shownIds.indexOf(bare(s)) === -1; }).length;
      summary.innerHTML =
        "<span><b>" + rows.length + "</b> dari " + state.list.length + " bencana tampil</span>" +
        "<span><b>" + state.selected.length + "</b> dipilih" + (hidden ? " (" + hidden + " di luar filter)" : "") + "</span>" +
        (state.multiple && rows.length ? '<button type="button" data-act="all">Pilih semua yang tampil</button>' : "") +
        (state.selected.length ? '<button type="button" data-act="none">Kosongkan pilihan</button>' : "");
    }

    function changed() {
      render();
      if (typeof opts.onChange === "function") opts.onChange(state.selected.slice());
    }

    grid.addEventListener("change", function (ev) {
      var inp = ev.target;
      if (!inp || inp.name !== uid + "-ev") return;
      var id = inp.value;
      if (!state.multiple) state.selected = inp.checked ? [id] : [];
      else if (inp.checked) { if (!isSel(id)) state.selected.push(id); }
      else state.selected = state.selected.filter(function (s) { return bare(s) !== bare(id); });
      changed();
    });
    summary.addEventListener("click", function (ev) {
      var act = ev.target && ev.target.getAttribute("data-act");
      if (act === "all") visible().forEach(function (e) { if (!isSel(e.id)) state.selected.push(e.id); });
      else if (act === "none") state.selected = [];
      else return;
      changed();
    });
    root.querySelector(".rn-evc-range").addEventListener("click", function (ev) {
      var b = ev.target.closest("button[data-range]");
      if (!b) return;
      state.range = b.getAttribute("data-range");
      root.querySelectorAll(".rn-evc-range button").forEach(function (x) { x.setAttribute("aria-pressed", String(x === b)); });
      dates.hidden = state.range !== "custom";
      render();
    });
    root.querySelector("#" + uid + "-q").addEventListener("input", function (ev) { state.q = ev.target.value.trim(); render(); });
    root.querySelector("#" + uid + "-from").addEventListener("change", function (ev) { state.from = ev.target.value; render(); });
    root.querySelector("#" + uid + "-to").addEventListener("change", function (ev) { state.to = ev.target.value; render(); });

    var api = {
      getSelected: function () {
        // full event names (as stored) for the ones in the list, raw otherwise
        return state.selected.map(function (s) {
          var hit = state.list.filter(function (e) { return bare(e.id) === bare(s); })[0];
          return hit ? hit.id : s;
        });
      },
      setSelected: function (ids) { state.selected = (ids || []).filter(Boolean).map(String); render(); },
      setMultiple: function (m) {
        m = !!m;
        if (m === state.multiple) return;
        state.multiple = m;
        if (!m && state.selected.length > 1) state.selected = state.selected.slice(0, 1);
        changed();
      },
    };
    api.ready = load().then(function (list) {
      state.list = list;
      render();
      return api;
    }).catch(function (e) {
      grid.innerHTML = '<div class="rn-evc-empty">Gagal memuat daftar bencana: ' + esc((e && e.message) || e) + "</div>";
      return api;
    });
    return api;
  }

  window.RNEventChecklist = { mount: mount, load: load };
})();
