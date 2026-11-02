/* Kelola Bencana (SOP owner 2026-11-01): rescue_net.api_disaster_admin.
   Everyone logged in: create (with duplicate check) + "Bencana yang saya buat".
   Super admin: verify proposals, review live events, merge suggestions, manual merge, undo. */
(function () {
  "use strict";
  var API = "rescue_net.api_disaster_admin.";
  var $ = function (id) { return document.getElementById(id); };
  var esc = function (s) { return window.RNUI ? window.RNUI.esc(s) : String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return "&#" + c.charCodeAt(0) + ";"; }); };
  var STATUS = { active: "Aktif", proposed: "Usulan (belum publik)", draft: "Draf BMKG", rejected: "Ditolak", merged: "Digabung" };
  var TYPE = { banjir: "Banjir", gempa: "Gempa bumi", tsunami: "Tsunami", longsor: "Tanah longsor", erupsi: "Erupsi gunung api",
    karhutla: "Kebakaran hutan & lahan", kebakaran: "Kebakaran", angin: "Angin kencang / puting beliung", kekeringan: "Kekeringan",
    abrasi: "Abrasi / gelombang pasang", wabah: "Wabah", lainnya: "Lainnya" };
  var DOCLABEL = { "RN Posko": "posko", "RN Posko Served Event": "layanan posko", "RN Community Report": "laporan", "RN Logistic Need": "kebutuhan",
    "RN Distribution Flow": "kiriman", "RN Volunteer Profile": "relawan", "RN Volunteer Assignment": "penugasan relawan", "RN Medical Case": "kasus medis",
    "RN Shelter Occupancy": "shelter", "RN Transport Space": "armada", "RN Missing Person Report": "orang hilang", "RN Stock Observation": "stok" };
  var call = function (m, args, post) { return window.RN_FRAPPE.call(API + m, args || {}, post ? { method: "POST" } : undefined); };
  var errText = function (e) { return (e && e.message) || String(e); };
  var timer = null, lastProbe = "";

  function fmt(dt) { return dt ? String(dt).slice(0, 16).replace("T", " ") : "—"; }
  function chip(s) { return '<span class="chip">' + esc(STATUS[s] || s || "—") + "</span>"; }
  function counts(c) {
    var keys = Object.keys(c || {});
    if (!keys.length) return '<span class="rn-muted">belum ada data</span>';
    return keys.map(function (k) { return c[k] + " " + esc(DOCLABEL[k] || k.replace(/^RN /, "").toLowerCase()); }).join(", ");
  }
  function link(name, title) { return '<a href="war-room.html?event=' + encodeURIComponent(name) + '">' + esc(title || name) + "</a>"; }

  function formData() {
    var f = $("kbForm"), o = {};
    ["title", "event_type", "location_summary", "started_at", "severity", "organization", "latitude", "longitude"].forEach(function (k) {
      var v = (f[k].value || "").trim(); if (v) o[k] = k === "started_at" ? v.replace("T", " ") + ":00" : v;
    });
    return o;
  }

  function showDup(list, blocking) {
    var box = $("kbDup");
    if (!list || !list.length) { box.hidden = true; box.innerHTML = ""; return; }
    box.hidden = false;
    box.innerHTML = "<b>" + (blocking ? "Sepertinya bencana ini sudah ada." : "Bencana mirip yang sudah ada:") + "</b> Bila sama, jangan buat baru — buka bencana itu dan bergabung (daftarkan posko/relawan Anda ke sana)." +
      "<ul>" + list.map(function (m) {
        return "<li>" + link(m.name, m.title) + " " + chip(m.event_status) + " · " + esc(m.location_summary || "") + " · mulai " + esc(fmt(m.started_at)) +
          ' · <small class="rn-muted">kemiripan ' + m.score + "% (" + esc((m.reasons || []).join(", ")) + ")</small>" +
          ' <a class="btn" href="registrasi-posko.html?event=' + encodeURIComponent(m.name) + '">Gabung ke bencana ini</a></li>';
      }).join("") + "</ul>" +
      (blocking ? '<button class="btn" type="button" id="kbForce">Bukan, ini bencana lain — kirim tetap</button>' : "");
    var fb = $("kbForce");
    if (fb) fb.addEventListener("click", function () { submit(true); });
  }

  function probe() {
    var d = formData();
    var key = [d.title, d.event_type, d.location_summary, d.latitude, d.longitude, d.started_at].join("|");
    if (key === lastProbe || !(d.title || d.location_summary)) return;
    lastProbe = key;
    call("check_duplicates", d).then(function (r) { showDup(r.matches, false); }).catch(function () {});
  }

  async function submit(force) {
    var d = formData(); if (force) d.force = 1;
    $("kbSubmit").disabled = true; $("kbResult").textContent = "Mengirim…";
    try {
      var r = await call("create_event", d, true);
      if (!r.created) { showDup(r.duplicates, true); $("kbResult").textContent = r.message; return; }
      showDup([], false);
      $("kbResult").innerHTML = esc(r.message) + " " + link(r.name, r.title);
      $("kbForm").reset(); lastProbe = "";
      loadMine(); if (window.__kbAdmin) loadAdmin();
    } catch (e) { $("kbResult").textContent = errText(e); }
    finally { $("kbSubmit").disabled = false; }
  }

  async function loadMine() {
    var rows = await call("my_events");
    $("kbMinePanel").hidden = !rows.length;
    $("kbMine").innerHTML = rows.map(function (r) {
      var note = r.event_status === "merged" ? "Digabung ke " + link(r.merged_into, r.merged_into_title) : esc(r.review_note || "");
      return "<tr><td>" + (r.event_status === "active" ? link(r.name, r.title) : esc(r.title)) + "<br><small class=\"rn-muted\">" + esc(TYPE[r.event_type] || r.event_type || "") +
        "</small></td><td>" + chip(r.event_status) + "</td><td>" + esc(r.location_summary || "") + "</td><td>" + note + "</td></tr>";
    }).join("");
  }

  function evRow(e, actions) {
    return "<tr><td><b>" + esc(e.title) + "</b><br><small class=\"rn-muted\">" + esc(TYPE[e.event_type] || e.event_type || "") + " · " + esc(e.severity || "") + "</small></td>" +
      "<td>" + esc(e.organization_title || "perorangan") + "<br><small class=\"rn-muted\">" + esc(e.created_by_user || "") + "</small></td>" +
      "<td>" + esc(e.location_summary || "") + "<br><small class=\"rn-muted\">" + esc(fmt(e.started_at)) +
      (e.latitude ? " · " + Number(e.latitude).toFixed(3) + ", " + Number(e.longitude).toFixed(3) : "") + "</small></td><td>" + actions + "</td></tr>";
  }
  function btn(act, data, label, primary) {
    return '<button class="btn' + (primary ? " primary" : "") + '" type="button" data-act="' + act + '" ' +
      Object.keys(data).map(function (k) { return "data-" + k + '="' + esc(data[k]) + '"'; }).join(" ") + ">" + label + "</button> ";
  }

  /* owner 2026-11-02: pick the disaster location on a map (click / drag pin) + search an admin area */
  var MAP = null, PIN = null, FORM = null;
  function mapSync(center) {
    if (!MAP || !FORM) return;
    var la = parseFloat(String(FORM.latitude.value).replace(",", ".")), lo = parseFloat(String(FORM.longitude.value).replace(",", "."));
    if (!isFinite(la) || !isFinite(lo) || Math.abs(la) > 90 || Math.abs(lo) > 180) return;
    if (!PIN) PIN = L.marker([la, lo], { draggable: true }).addTo(MAP).on("dragend", function () { setPoint(PIN.getLatLng(), false); });
    else PIN.setLatLng([la, lo]);
    if (center) MAP.setView([la, lo], Math.max(MAP.getZoom(), 10));
  }
  function setPoint(ll, center) {
    FORM.latitude.value = ll.lat.toFixed(5); FORM.longitude.value = ll.lng.toFixed(5);
    mapSync(center);
    FORM.dispatchEvent(new Event("input"));   // re-run the duplicate check
  }
  function setupMap(f) {
    FORM = f;
    var host = $("kbMap");
    if (!host || typeof L === "undefined") { if (host) host.hidden = true; return; }
    MAP = L.map(host, { scrollWheelZoom: false }).setView([-2.5, 118], 4);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 18, attribution: "© OpenStreetMap" }).addTo(MAP);
    MAP.on("click", function (e) { setPoint(e.latlng, false); });
    ["latitude", "longitude"].forEach(function (k) { f[k].addEventListener("change", function () { mapSync(true); }); });
    setTimeout(function () { MAP.invalidateSize(); mapSync(true); }, 200);
    var inp = $("kbArea"), list = $("kbAreaList"), found = {}, t = null;
    inp.addEventListener("input", function () {
      clearTimeout(t);
      var q = inp.value.trim();
      if (found[q]) return pickArea(found[q]);
      if (q.length < 3) return;
      t = setTimeout(async function () {
        try {
          // villages sort first alphabetically and would crowd out kab/kota & kecamatan: ask per level
          var res = await Promise.all(["city", "district"].map(function (lv) {
            return window.RN_FRAPPE.call("rescue_net.api_admin_areas.search_areas", { q: q, level: lv, limit: 8 }).catch(function () { return { rows: [] }; });
          }));
          var rows = res[0].rows.concat(res[1].rows);
          found = {};
          list.innerHTML = rows.map(function (a) {
            var label = a.area_name + " (" + ({ province: "provinsi", city: "kab/kota", district: "kecamatan" }[a.level] || a.level) + ")";
            found[label] = a.code;
            return '<option value="' + esc(label) + '">';
          }).join("");
        } catch (e) { /* search is a convenience */ }
      }, 300);
    });
    async function pickArea(code) {
      try {
        var r = await window.RN_FRAPPE.call("rescue_net.api_admin_areas.get_area", { code: code });
        var path = (r.path || []).map(function (p) { return p.area_name; }).reverse().join(", ");
        if (path) { FORM.location_summary.value = path; }
        var a = r.area || {};
        if (a.center_lat && a.center_lng) MAP.setView([a.center_lat, a.center_lng], a.level === "district" ? 12 : 10);
        FORM.dispatchEvent(new Event("input"));
      } catch (e) { /* ignore */ }
    }
  }

  async function loadAdmin() {
    var q = await call("admin_queue");
    // S13 / owner 2026-11-02: BMKG notices are announcements; the super admin turns one into a disaster
    function quakeLine(w) {
      var near = (w.nearby || []).map(function (p) { return esc(p.title) + " (" + esc(p.km) + " km)"; }).join(", ");
      return (w.magnitude ? "<div>M" + esc(w.magnitude) + " · kedalaman " + esc(w.depth_km) + " km · " + esc(w.area || "") +
        (w.potential ? " · " + esc(w.potential) : "") + " · " + esc(String(w.issued_at || "").slice(0, 16)) + "</div>" : "") +
        "<div>Posko dalam jangkauan: <b>" + (w.nearby_count || 0) + "</b>" + (near ? " — " + near + (w.nearby_count > 8 ? ", …" : "") : "") + "</div>";
    }
    var notices = q.bmkg_notices || [], drafts = q.bmkg_drafts || [];
    $("kbBmkgCount").textContent = notices.length + drafts.length;
    $("kbBmkg").innerHTML = (notices.length || drafts.length) ? notices.map(function (w) {
      return '<div class="rn-callout"><b>📢 ' + esc(w.title) + '</b> <span class="chip">pengumuman</span>' + quakeLine(w) +
        '<div class="form-actions">' + btn("promote", { w: w.warning }, "Jadikan bencana", true) + btn("dismissw", { w: w.warning }, "Abaikan") + "</div></div>";
    }).join("") + drafts.map(function (e) {
      return '<div class="rn-callout"><b>' + esc(e.title) + '</b> <span class="chip">draf lama</span>' + quakeLine(e.quake || {}) +
        '<div class="form-actions">' + btn("review", { ev: e.name, d: "approve" }, "Jadikan bencana", true) + btn("review", { ev: e.name, d: "reject" }, "Abaikan") + "</div></div>";
    }).join("") : '<p class="rn-muted">Tidak ada pengumuman BMKG yang perlu diputuskan.</p>';
    $("kbPropCount").textContent = q.proposed.length;
    $("kbProposed").innerHTML = q.proposed.length ? q.proposed.map(function (e) {
      return evRow(e, btn("review", { ev: e.name, d: "approve" }, "Setujui", true) + btn("review", { ev: e.name, d: "reject" }, "Tolak"));
    }).join("") : '<tr><td colspan="4" class="rn-muted">Tidak ada usulan.</td></tr>';
    $("kbLiveCount").textContent = q.recent_live.length;
    $("kbLive").innerHTML = q.recent_live.length ? q.recent_live.map(function (e) {
      return evRow(e, btn("review", { ev: e.name, d: "ok" }, "Sudah diperiksa", true) + btn("review", { ev: e.name, d: "demote" }, "Turunkan ke usulan"));
    }).join("") : '<tr><td colspan="4" class="rn-muted">Tidak ada.</td></tr>';
    $("kbSugCount").textContent = q.suggestions.length;
    $("kbSugs").innerHTML = q.suggestions.length ? q.suggestions.map(function (s) {
      return '<div class="rn-callout"><b>Kemiripan ' + s.score + "%</b> — " + esc((s.reasons || []).join(", ")) +
        "<div>Digabung: " + link(s.source.name, s.source.title) + " " + chip(s.source.event_status) + " · " + counts(s.source_counts) + "</div>" +
        "<div>Utama: " + link(s.target.name, s.target.title) + " " + chip(s.target.event_status) + " · " + counts(s.target_counts) + "</div>" +
        '<div class="form-actions">' + btn("sug", { s: s.name, d: "accept" }, "Gabungkan", true) + btn("sug", { s: s.name, d: "accept", swap: 1 }, "Gabungkan (arah sebaliknya)") +
        btn("sug", { s: s.name, d: "reject" }, "Bukan bencana yang sama") + "</div></div>";
    }).join("") : '<p class="rn-muted">Tidak ada usulan gabung.</p>';
    var opts = '<option value="">— pilih —</option>' + q.events.map(function (e) {
      return '<option value="' + esc(e.name) + '">' + esc(e.title) + " [" + esc(STATUS[e.event_status] || e.event_status) + "]" + (e.is_drill ? " (latihan)" : "") + "</option>";
    }).join("");
    var mf = $("kbMerge"); mf.source.innerHTML = opts; mf.target.innerHTML = opts; $("kbMergePreview").textContent = "";
    $("kbLogs").innerHTML = q.logs.length ? q.logs.map(function (l) {
      return "<tr><td>" + esc(fmt(l.merged_at)) + "<br><small class=\"rn-muted\">" + esc(l.merged_by) + "</small></td><td>" + esc(l.source_title) + " → " + esc(l.target_title) +
        "</td><td>" + (l.moved_count || 0) + " dipindah" + (l.status === "undone" ? "<br><small>Dibatalkan: " + esc(l.undo_note || "") + "</small>" : "") + "</td><td>" +
        (l.status === "done" ? btn("undo", { log: l.name }, "Batalkan gabung") : '<span class="chip">dibatalkan</span>') + "</td></tr>";
    }).join("") : '<tr><td colspan="4" class="rn-muted">Belum ada.</td></tr>';
  }

  async function onAdminClick(ev) {
    var b = ev.target.closest("button[data-act]"); if (!b) return;
    var act = b.dataset.act;
    try {
      if (act === "promote") {
        var t = prompt("Pengumuman ini sudah dinyatakan sebagai bencana? Nama bencana di Rescue-Net:", "");
        if (t === null) return;
        await call("promote_warning", { warning: b.dataset.w, title: t || null }, true);
      } else if (act === "dismissw") {
        if (!confirm("Abaikan pengumuman ini (bukan bencana)?")) return;
        await call("dismiss_warning", { warning: b.dataset.w }, true);
      } else if (act === "review") {
        var note = "";
        if (b.dataset.d === "reject" || b.dataset.d === "demote") { note = prompt("Alasan (dikirim ke pembuat):", "") ; if (note === null) return; }
        await call("review_event", { event: b.dataset.ev, decision: b.dataset.d, note: note }, true);
      } else if (act === "sug") {
        if (b.dataset.d === "accept" && !confirm("Gabungkan kedua bencana ini? Semua data dipindah ke bencana utama. Bisa dibatalkan dari Riwayat gabung.")) return;
        var r = await call("decide_merge_suggestion", { suggestion: b.dataset.s, decision: b.dataset.d, swap: b.dataset.swap || 0 }, true);
        if (r.moved !== undefined) alert("Selesai: " + r.moved + " data dipindah.");
      } else if (act === "undo") {
        if (!confirm("Batalkan penggabungan ini? Data dikembalikan ke bencana asal (data yang dibuat setelah gabung tetap di bencana utama).")) return;
        var u = await call("undo_merge", { log: b.dataset.log }, true);
        alert(u.restored + " data dikembalikan, " + u.skipped + " dilewati.");
      }
      loadAdmin();
    } catch (e) { alert(errText(e)); }
  }

  async function mergePreview() {
    var f = $("kbMerge"), s = f.source.value;
    if (!s) { $("kbMergePreview").textContent = ""; return; }
    try { var r = await call("event_counts", { event: s }); $("kbMergePreview").innerHTML = "Akan dipindah: " + counts(r.counts); } catch (e) { /* ignore */ }
  }

  async function init() {
    var opt;
    try { opt = await call("create_options"); }
    catch (e) { $("kbStatus").innerHTML = 'Silakan <a href="auth.html?next=' + encodeURIComponent("kelola-bencana.html#kbCreatePanel") + '">login</a> untuk membuat atau mengusulkan bencana.'; return; }
    $("kbStatus").textContent = "";
    var f = $("kbForm");
    f.event_type.innerHTML = opt.event_types.map(function (t) { return '<option value="' + esc(t) + '">' + esc(TYPE[t] || t) + "</option>"; }).join("");
    f.organization.innerHTML = '<option value="">' + (opt.organizations.length ? "— pilih —" : "(perorangan)") + "</option>" + opt.organizations.map(function (o) {
      return '<option value="' + esc(o.name) + '">' + esc(o.title) + (o.verified ? " ✓ terverifikasi" : " (belum terverifikasi)") + "</option>";
    }).join("");
    var v = opt.organizations.filter(function (o) { return o.verified; })[0]; if (v) f.organization.value = v.name;
    $("kbLiveNote").textContent = opt.goes_live ? "Akun/organisasi Anda terverifikasi: bencana langsung aktif (super admin tetap diberi tahu)."
      : "Organisasi Anda belum terverifikasi: bencana masuk sebagai usulan dan tampil setelah disetujui super admin.";
    $("kbCreatePanel").hidden = false;
    if (location.hash === "#kbCreatePanel") setTimeout(function () { $("kbCreatePanel").scrollIntoView({ block: "start" }); var t = document.querySelector("#kbForm input, #kbForm select"); if (t) t.focus(); }, 100);
    f.addEventListener("input", function () { clearTimeout(timer); timer = setTimeout(probe, 700); });
    f.addEventListener("submit", function (e) { e.preventDefault(); submit(false); });
    $("kbGeo").addEventListener("click", function () {
      if (!navigator.geolocation) return alert("Peramban tidak mendukung lokasi.");
      navigator.geolocation.getCurrentPosition(function (p) {
        f.latitude.value = p.coords.latitude.toFixed(5); f.longitude.value = p.coords.longitude.toFixed(5); probe();
        mapSync(true);
      }, function () { alert("Lokasi tidak diizinkan."); });
    });
    setupMap(f);
    loadMine().catch(function () {});
    if (opt.is_super_admin) {
      window.__kbAdmin = true; $("kbAdmin").hidden = false;
      $("kbAdmin").addEventListener("click", onAdminClick);
      $("kbScan").addEventListener("click", async function () {
        try { var r = await call("scan_now", {}, true); alert(r.created + " usulan gabung baru."); loadAdmin(); } catch (e) { alert(errText(e)); }
      });
      $("kbMerge").source.addEventListener("change", mergePreview);
      $("kbMerge").addEventListener("submit", async function (e) {
        e.preventDefault(); var mf = e.target;
        if (!confirm("Gabungkan? Semua data bencana yang digabung dipindah ke bencana utama. Bisa dibatalkan.")) return;
        try {
          var r = await call("merge_events", { source: mf.source.value, target: mf.target.value, note: mf.note.value }, true);
          alert("Selesai: " + r.moved + " data dipindah."); mf.reset(); loadAdmin();
        } catch (err) { alert(errText(err)); }
      });
      loadAdmin().catch(function (e) { $("kbStatus").textContent = errText(e); });
    }
  }

  document.addEventListener("DOMContentLoaded", init);
})();
