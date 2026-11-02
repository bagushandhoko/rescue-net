/* Kelola Posko (owner 2026-11-01, tahap 1) — managers' hub.
 * API: rescue_net.api_posko_manage.my_managed_poskos / manage_hub, api_comms.set_posko_comms_support. */
(function () {
  "use strict";
  var API = "rescue_net.api_posko_manage.";
  var $ = function (id) { return document.getElementById(id); };
  var esc = function (s) { return window.RNUI ? window.RNUI.esc(s) : String(s == null ? "" : s); };
  var qs = new URLSearchParams(location.search);
  var POSKO = qs.get("id") || qs.get("posko") || "";
  var STATUS = { active: "Aktif", standby: "Siaga", reducing: "Pengurangan", closing: "Persiapan tutup", offline: "Nonaktif / tutup" };
  var VERIF = { verified: "Terverifikasi", pending: "Menunggu verifikasi", self_reported: "Belum diajukan",
    needs_correction: "Perlu koreksi", rejected: "Ditolak" };

  function status(t) { var s = $("kpStatus"); if (s) s.textContent = t || ""; }
  function badge(n) { return '<span class="kp-badge' + (n ? "" : " zero") + '">' + (n || 0) + "</span>"; }

  async function showList() {
    var r = await window.RN_FRAPPE.call(API + "my_managed_poskos");
    var rows = r.poskos || [];
    $("kpPick").hidden = false;
    if (rows.length === 1 && !POSKO) { location.replace("kelola-posko.html?id=" + encodeURIComponent(rows[0].posko)); return; }
    $("kpList").innerHTML = rows.length ? rows.map(function (p) {
      return '<a class="kp-item" href="kelola-posko.html?id=' + encodeURIComponent(p.posko) + '"><span><b>' + esc(p.title) +
        "</b><br><small>" + esc(p.type_label) + (p.status ? " · " + esc(STATUS[p.status] || p.status) : "") + "</small></span>" +
        badge(p.pending_total) + "</a>";
    }).join("") : '<p class="rn-muted">Anda belum tercatat sebagai pengelola posko mana pun. Daftarkan posko di <a href="registrasi-posko.html">Registrasi Posko</a>.</p>';
    status("");
  }

  function contactText(c) {
    var x = [c.name, c.phone, c.whatsapp && c.whatsapp !== c.phone ? "WA " + c.whatsapp : "", c.emergency ? "Darurat " + c.emergency : ""];
    return x.filter(Boolean).join(" · ") || "— belum diisi —";
  }

  async function showHub() {
    var h;
    try { h = await window.RN_FRAPPE.call(API + "manage_hub", { posko: POSKO }); }
    catch (err) {
      status((err && err.message) || "Anda bukan pengelola posko ini.");
      await showList();
      return;
    }
    document.title = "Rescue-Net | Kelola " + h.title;
    $("kpTitle").textContent = "Kelola: " + h.title;
    $("kpHub").hidden = false;
    $("kpPublic").href = h.public_href;
    var settings = (h.tools || []).filter(function (t) { return t.key === "settings"; })[0];
    $("kpEdit").href = settings ? settings.href : h.public_href;

    $("kpWarn").innerHTML = (h.warnings || []).map(function (w) { return '<p class="kp-warn">⚠️ ' + esc(w) + "</p>"; }).join("");
    var relawan = (h.tools || []).filter(function (t) { return t.key === "relawan"; })[0];
    $("kpPending").innerHTML =
      '<a class="kp-item" href="' + esc(relawan ? relawan.href : "management-relawan.html") + '"><span>Relawan menawarkan diri / minta jemputan &amp; shelter</span>' + badge(h.pending.relawan) + "</a>" +
      '<div class="kp-item"><span>Permintaan jadi operator posko <small class="rn-muted">(disetujui super admin)</small></span>' + badge(h.pending.operator) + "</div>" +
      '<a class="kp-item" href="#kpExpiry"><span>Stok sudah / segera kedaluwarsa</span>' + badge(h.pending.kedaluwarsa) + "</a>" +
      '<a class="kp-item" href="#kpArmada"><span>Pesanan ruang muat armada menunggu</span>' + badge(h.pending.pesanan_armada) + "</a>";
    loadExpiry();
    loadArmada();
    loadWorkbench();

    var ev = (h.events || []).map(function (e) { return esc(e.title); }).join(", ") || "—";
    $("kpInfo").innerHTML =
      "<dt>Jenis</dt><dd>" + esc(h.type_label) + "</dd>" +
      "<dt>Status</dt><dd>" + esc(STATUS[h.status] || h.status || "—") + "</dd>" +
      "<dt>Verifikasi</dt><dd>" + esc(VERIF[h.verification] || h.verification) + "</dd>" +
      (h.organization ? "<dt>Organisasi</dt><dd>" + esc(h.organization) + "</dd>" : "") +
      "<dt>Bencana dilayani</dt><dd>" + ev + "</dd>" +
      "<dt>Kontak</dt><dd>" + esc(contactText(h.contact || {})) + "</dd>";

    $("kpTools").innerHTML = (h.tools || []).map(function (t) {
      return '<a class="kp-tool" href="' + esc(t.href) + '"><b>' + esc(t.label) + "</b><small>" + esc(t.desc) + "</small></a>";
    }).join("");

    var f = $("kpComms");
    f.offered.value = (h.comms || {}).offered || "";
    f.needed.value = (h.comms || {}).needed || "";
    status("");
  }

  /* Kelola Posko tahap 2 (owner 2026-11-02): kontak & status, permintaan relawan, kebutuhan, stok */
  var URG = { normal: "", urgent: "warning", critical: "danger" };
  var KIND = { posko: "Menawarkan diri bertugas", transport: "Minta kursi armada / jemputan", akomodasi: "Minta tempat menginap" };
  function call(m, a, post) { return window.RN_FRAPPE.call(m, a || {}, post ? { method: "POST" } : undefined); }
  function say(id, t) { var m = $(id); if (m) m.textContent = t || ""; }

  async function loadWorkbench() {
    var w;
    try { w = await call("rescue_net.api_posko_manage.workbench", { posko: POSKO }); }
    catch (e) { return; }
    var f = $("kpContactForm");
    if (f) Object.keys(w.contact).forEach(function (k) { if (f[k]) f[k].value = w.contact[k] || (k === "operational_status" ? "active" : ""); });
    $("kpVolList").innerHTML = w.volunteer_requests.length ? w.volunteer_requests.map(function (v) {
      return '<div class="kp-bk"><span><b>' + esc(v.volunteer_name || "Relawan") + "</b> · " + esc(KIND[v.booking_kind] || v.booking_kind) +
        "<br><small>" + esc(v.main_skill || "") + (v.contact ? " · " + esc(v.contact) : "") + (v.note ? " · " + esc(v.note) : "") + " · " + esc(v.creation) + "</small></span>" +
        '<span><button class="btn primary mini" type="button" data-vol="' + esc(v.name) + '" data-d="confirm">Setujui</button> ' +
        '<button class="btn mini" type="button" data-vol="' + esc(v.name) + '" data-d="reject">Tolak</button></span></div>';
    }).join("") : '<p class="rn-muted">Tidak ada permintaan relawan yang menunggu.</p>';
    $("kpNeedBody").innerHTML = w.needs.length ? w.needs.map(function (n) {
      return "<tr><td>" + esc(n.item_name) + "</td><td>" + esc(n.quantity == null ? "?" : n.quantity) + " " + esc(n.unit || "") + '</td><td><span class="chip ' +
        (URG[n.urgency] || "") + '">' + esc(n.urgency || "normal") + "</span></td><td>" + esc(n.need_status) + "</td><td>" + esc(n.creation) + "</td></tr>";
    }).join("") : '<tr><td colspan="5" class="rn-muted">Tidak ada kebutuhan terbuka.</td></tr>';
    $("kpStockBody").innerHTML = w.stock.length ? w.stock.map(function (s) {
      return "<tr><td>" + esc(s.item) + "</td><td>" + esc(s.quantity) + " " + esc(s.unit || "") + "</td><td>" + esc(s.observed_at) + "</td></tr>";
    }).join("") : '<tr><td colspan="3" class="rn-muted">Belum ada catatan stok.</td></tr>';
    var dl = $("kpStockItems");
    if (dl) dl.innerHTML = w.stock.map(function (s) { return '<option value="' + esc(s.item) + '">'; }).join("");
  }

  function wireWorkbench() {
    var cf = $("kpContactForm");
    if (cf) cf.addEventListener("submit", async function (e) {
      e.preventDefault(); say("kpContactMsg", "Menyimpan…");
      var a = { posko: POSKO };
      Array.prototype.forEach.call(cf.elements, function (el) { if (el.name) a[el.name] = el.value.trim(); });
      try { var r = await call("rescue_net.api_community_cluster.update_posko", a, true);
        say("kpContactMsg", r && r.pending ? "Tersimpan — sebagian menunggu persetujuan pusat." : "Tersimpan."); }
      catch (err) { say("kpContactMsg", "Gagal: " + ((err && err.message) || err)); }
    });
    var vl = $("kpVolList");
    if (vl) vl.addEventListener("click", async function (e) {
      var b = e.target.closest("[data-vol]"); if (!b) return;
      if (b.dataset.d === "reject" && !window.confirm("Tolak permintaan ini?")) return;
      try { await call("rescue_net.api_volunteer_booking.decide_booking", { booking: b.dataset.vol, action: b.dataset.d }, true); loadWorkbench(); }
      catch (err) { window.alert((err && err.message) || err); }
    });
    var nf = $("kpNeedForm");
    if (nf) nf.addEventListener("submit", async function (e) {
      e.preventDefault();
      if (["urgent", "critical"].indexOf(nf.urgency.value) !== -1 && !(Number(nf.jiwa_terdampak.value) > 0)) {
        say("kpNeedMsg", "Isi jumlah jiwa untuk kebutuhan urgent/critical."); return; }
      say("kpNeedMsg", "Menyimpan…");
      try {
        await call("rescue_net.api_logistics.create_need", { posko: POSKO, item_text: nf.item_text.value.trim(), quantity: nf.quantity.value,
          unit: nf.unit.value.trim(), quantity_mode: "exact", urgency: nf.urgency.value, needed_before: nf.needed_before.value.trim(),
          jiwa_terdampak: nf.jiwa_terdampak.value || null }, true);
        say("kpNeedMsg", "Kebutuhan tersimpan."); nf.reset(); loadWorkbench();
      } catch (err) { say("kpNeedMsg", "Gagal: " + ((err && err.message) || err)); }
    });
    var sf = $("kpStockForm");
    if (sf) sf.addEventListener("submit", async function (e) {
      e.preventDefault(); say("kpStockMsg", "Menyimpan…");
      try {
        await call("rescue_net.api_logistics.create_stock_observation", { posko: POSKO, item_text: sf.item_text.value.trim(),
          quantity: sf.quantity.value, unit: sf.unit.value.trim(), quantity_mode: "exact" }, true);
        say("kpStockMsg", "Stok tersimpan."); sf.reset(); loadWorkbench();
      } catch (err) { say("kpStockMsg", "Gagal: " + ((err && err.message) || err)); }
    });
  }

  /* Alat transport posko (owner 2026-11-02) — api_posko_manage.armada_list + existing armada / booking endpoints */
  var GPS_WATCH = null;
  function armadaRow(a, statuses) {
    var opts = Object.keys(statuses).map(function (k) {
      return '<option value="' + k + '"' + (k === a.status ? " selected" : "") + ">" + esc(statuses[k]) + "</option>"; }).join("");
    var chip = { tersedia: "ok", penuh: "warning", dipakai: "danger", lewat: "", selesai: "" }[a.avail] || "";
    var avail = { tersedia: "tersedia", penuh: "penuh", dipakai: "sedang dipakai", lewat: "jadwal lewat — perbarui jadwal", selesai: "selesai" }[a.avail] || a.avail;
    var bks = (a.requested || []).map(function (b) {
      return '<div class="kp-bk"><span><b>' + esc(b.cargo_desc || "Muatan") + "</b> · " + esc(b.qty_weight_kg || 0) + " kg" +
        (b.qty_volume_m3 ? " · " + esc(b.qty_volume_m3) + " m³" : "") + "<br><small>" + esc(b.booker_name || b.contact_person || b.booked_by_type || "") +
        (b.contact_phone ? " · " + esc(b.contact_phone) : "") + (b.requested_window ? " · " + esc(b.requested_window) : "") + "</small></span>" +
        '<span><button class="btn primary mini" type="button" data-bk-ok="' + esc(b.name) + '" data-pin="' + (b.needs_pin ? 1 : 0) + '">Konfirmasi</button> ' +
        '<button class="btn mini" type="button" data-bk-no="' + esc(b.name) + '">Tolak</button></span></div>';
    }).join("");
    return '<details class="kp-arm"' + (a.requested.length ? " open" : "") + "><summary>" +
      '<span class="chip ' + chip + '">' + esc(avail) + "</span><b>" + esc(a.title) + "</b><small>" + esc(a.type) + " · " + esc(a.route) + "</small>" +
      (a.requested.length ? '<span class="kp-badge">' + a.requested.length + "</span>" : "") + "</summary>" +
      '<div class="kp-arm-body">' +
      "<div>Berangkat: " + esc(a.departure || "fleksibel") + (a.left_kg != null ? " · sisa " + esc(a.left_kg) + " dari " + esc(a.capacity_kg) + " kg" : "") + "</div>" +
      '<div class="kp-arm-row"><label>Status <select data-arm-status="' + esc(a.name) + '">' + opts + "</select></label>" +
      '<button class="btn mini" type="button" data-arm-gps="' + esc(a.name) + '">📍 Kirim posisi sekarang</button>' +
      '<label class="kp-auto"><input type="checkbox" data-arm-auto="' + esc(a.name) + '"' + (GPS_WATCH && GPS_WATCH.armada === a.name ? " checked" : "") + "> Lacak otomatis</label></div>" +
      '<small class="rn-muted">Posisi terakhir: ' + esc(a.position_at || "belum ada") + "</small>" +
      (bks ? "<h5>Pesanan menunggu</h5>" + bks : "") +
      '<div><a class="btn ghost mini" href="posko-distribusi.html?id=' + encodeURIComponent(POSKO) + "&armada=" + encodeURIComponent(a.name) + '">Detail &amp; ubah armada</a></div>' +
      "</div></details>";
  }

  async function loadArmada() {
    var box = $("kpArmadaList");
    if (!box) return;
    $("kpArmadaAdd").href = "posko-distribusi.html?id=" + encodeURIComponent(POSKO) + "#armadaForm";
    try {
      var r = await window.RN_FRAPPE.call("rescue_net.api_posko_manage.armada_list", { posko: POSKO });
      box.innerHTML = r.armada.length ? r.armada.map(function (a) { return armadaRow(a, r.statuses); }).join("")
        : '<p class="rn-muted">Posko ini belum punya armada. Klik "+ Daftarkan armada" bila posko Anda menyediakan kendaraan / ruang muat.</p>';
    } catch (e) { box.innerHTML = '<p class="rn-muted">' + esc((e && e.message) || e) + "</p>"; }
  }

  function armadaMsg(t) { var m = $("kpArmadaMsg"); if (m) m.textContent = t || ""; }
  function sendPos(id, p) {
    return window.RN_FRAPPE.call("rescue_net.api_armada.update_armada_position", { transport_space: id,
      latitude: p.coords.latitude, longitude: p.coords.longitude, accuracy_m: p.coords.accuracy }, { method: "POST" })
      .then(function (r) { armadaMsg(r.skipped ? "Posisi belum berubah." : "Posisi terkirim " + String(r.position_at).slice(11, 16) + "."); })
      .catch(function (e) { armadaMsg("Gagal: " + ((e && e.message) || e)); });
  }
  function wireArmada() {
    var box = $("kpArmadaList");
    if (!box) return;
    box.addEventListener("change", async function (e) {
      var st = e.target.closest("[data-arm-status]"), au = e.target.closest("[data-arm-auto]");
      if (st) {
        armadaMsg("Menyimpan status…");
        try {
          await window.RN_FRAPPE.call("rescue_net.api_logistics.update_transport_space",
            { transport_space: st.dataset.armStatus, transport_status: st.value }, { method: "POST" });
          armadaMsg("Status armada disimpan."); loadArmada();
        } catch (err) { armadaMsg("Gagal: " + ((err && err.message) || err)); loadArmada(); }
      }
      if (au) {
        if (GPS_WATCH) { navigator.geolocation.clearWatch(GPS_WATCH.id); GPS_WATCH = null; }
        box.querySelectorAll("[data-arm-auto]").forEach(function (x) { if (x !== au) x.checked = false; });
        if (!au.checked) { armadaMsg("Lacak otomatis dimatikan."); return; }
        if (!navigator.geolocation) { armadaMsg("HP/peramban tidak mendukung GPS."); au.checked = false; return; }
        var last = 0, id = au.dataset.armAuto;
        GPS_WATCH = { armada: id, id: navigator.geolocation.watchPosition(function (p) {
          if (Date.now() - last < 60000) return; last = Date.now(); sendPos(id, p);
        }, function () { armadaMsg("Izin lokasi ditolak."); }, { enableHighAccuracy: true }) };
        armadaMsg("Lacak otomatis aktif (±1 menit) selama halaman ini terbuka.");
      }
    });
    box.addEventListener("click", async function (e) {
      var g = e.target.closest("[data-arm-gps]"), ok = e.target.closest("[data-bk-ok]"), no = e.target.closest("[data-bk-no]");
      if (g) {
        if (!navigator.geolocation) return armadaMsg("HP/peramban tidak mendukung GPS.");
        armadaMsg("Mencari posisi…");
        navigator.geolocation.getCurrentPosition(function (p) { sendPos(g.dataset.armGps, p).then(loadArmada); },
          function () { armadaMsg("Izin lokasi ditolak."); }, { enableHighAccuracy: true, timeout: 20000 });
      }
      if (ok || no) {
        try {
          if (ok) {
            var pin = null;
            if (ok.dataset.pin === "1") { pin = window.prompt("Masukkan PIN dari pemesan:", ""); if (pin === null) return; }
            await window.RN_FRAPPE.call("rescue_net.api_logistics.confirm_transport_booking", { booking: ok.dataset.bkOk, pin: pin }, { method: "POST" });
            armadaMsg("Pesanan dikonfirmasi.");
          } else {
            var why = window.prompt("Alasan menolak (opsional):", ""); if (why === null) return;
            await window.RN_FRAPPE.call("rescue_net.api_logistics.reject_transport_booking", { booking: no.dataset.bkNo, reason: why }, { method: "POST" });
            armadaMsg("Pesanan ditolak.");
          }
          loadArmada();
        } catch (err) { armadaMsg("Gagal: " + ((err && err.message) || err)); }
      }
    });
  }

  /* S14 (2026-11-02): expiring stock + give stock an expiry date */
  var STATE = { expired: ["Sudah kedaluwarsa", "danger"], soon: ["Segera kedaluwarsa", "warning"], ok: ["Aman", "ok"] };
  async function loadExpiry() {
    var body = $("kpExpiryBody");
    try {
      var r = await window.RN_FRAPPE.call("rescue_net.api_stock_expiry.expiring", { posko: POSKO });
      var rows = r.rows || [];
      body.innerHTML = rows.length ? rows.map(function (x) {
        var st = STATE[x.state] || [x.state, ""];
        return "<tr><td>" + esc(x.item_name) + "</td><td>" + esc(x.batch_no || "-") + "</td><td>" + esc(x.expiry_date) + "</td><td>" +
          esc(x.quantity != null ? x.quantity : "") + " " + esc(x.unit || "") + '</td><td><span class="chip ' + st[1] + '">' + esc(st[0]) + "</span></td></tr>";
      }).join("") : '<tr><td colspan="5" class="rn-muted">Belum ada stok bertanggal kedaluwarsa.</td></tr>';
    } catch (e) { body.innerHTML = '<tr><td colspan="5" class="rn-muted">' + esc((e && e.message) || e) + "</td></tr>"; }
  }

  document.addEventListener("DOMContentLoaded", async function () {
    if (!window.RN_FRAPPE) return;
    var sess = null;
    try { sess = await window.RN_FRAPPE.call("rescue_net.api_auth.session_info"); } catch (e) {}
    if (!sess || !sess.user || sess.user === "Guest") { status(""); $("kpLogin").hidden = false; return; }

    $("kpComms").addEventListener("submit", async function (e) {
      e.preventDefault();
      var m = $("kpCommsMsg"); m.textContent = "Menyimpan…";
      try {
        await window.RN_FRAPPE.call("rescue_net.api_comms.set_posko_comms_support",
          { posko: POSKO, offered: e.target.offered.value, needed: e.target.needed.value }, { method: "POST" });
        m.textContent = "Tersimpan.";
      } catch (err) { m.textContent = (err && err.message) || err; }
    });

    wireArmada();
    wireWorkbench();
    var lf = $("kpLotForm");
    if (lf) lf.addEventListener("submit", async function (e) {
      e.preventDefault();
      var m = $("kpLotMsg"); m.textContent = "Menyimpan…";
      try {
        await window.RN_FRAPPE.call("rescue_net.api_stock_expiry.add_lot", { posko: POSKO, item_name: lf.item_name.value.trim(),
          unit: lf.unit.value.trim(), quantity: lf.quantity.value, expiry_date: lf.expiry_date.value, batch_no: lf.batch_no.value.trim() || null },
          { method: "POST" });
        m.textContent = "Tersimpan."; lf.reset(); loadExpiry();
      } catch (err) { m.textContent = (err && err.message) || err; }
    });

    try { if (POSKO) await showHub(); else await showList(); }
    catch (err) { status((err && err.message) || err); }
  });
})();
