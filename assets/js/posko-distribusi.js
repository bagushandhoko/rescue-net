/* ============================================================
 * Posko Distribusi — the transport-provider posko workspace.
 * Board: rescue_net.api_control_centre.posko_distribusi_board
 * Writes: api_logistics.create_transport_space / confirm_transport_booking /
 * reject_transport_booking / assign_pickup_volunteer (login required).
 * ============================================================ */
(function () {
  "use strict";

  var BOARD = "rescue_net.api_control_centre.posko_distribusi_board";
  var CACHE = null;

  var $ = function (s, r) { return (r || document).querySelector(s); };
  function esc(s) { return window.RNUI.esc(s); }
  function fmt(n) { return window.RNUI.fmt(n); }
  var qs = new URLSearchParams(location.search);
  function getEvent() { return qs.get("event") || "event-sim-001"; }
  function getPosko() { return qs.get("id") || qs.get("posko") || ""; }
  function tel(v) { return v && v !== "-" ? '<a href="tel:' + esc(String(v).replace(/[^0-9+]/g, "")) + '">' + esc(v) + "</a>" : "-"; }
  // owner 2026-11-10: kontak pembooking "tinggal diklik bisa dihubungi" -> telepon + WhatsApp
  function waNum(v) {
    var n = String(v || "").replace(/[^0-9]/g, "");
    if (/^0/.test(n)) n = "62" + n.slice(1);
    return n.length >= 9 ? n : "";
  }
  function contact(v) {
    if (!v || v === "-") return "-";
    var w = waNum(v);
    return tel(v) + (w ? ' <a class="rn-pd-wa" href="https://wa.me/' + w + '" target="_blank" rel="noopener">WhatsApp</a>' : "");
  }

  /* owner 2026-11-10: "bedakan halaman untuk publik atau user dan halaman/menu sebagai pemilik".
     Pengelola posko (can_manage) mendapat dua tab: Menu Pemilik (booking masuk + kontak di atas,
     kelola armada) dan Tampilan Publik / Pembooking (persis yang dilihat publik & user, tanpa
     kontak pembooking lain). Publik & user biasa tidak melihat tab. Pilihan disimpan di ?view=. */
  function currentView() { return qs.get("view") === "publik" ? "publik" : "pemilik"; }
  function setView(v) {
    if (v === "publik") qs.set("view", "publik"); else qs.delete("view");
    var q = qs.toString();
    history.replaceState(null, "", location.pathname + (q ? "?" + q : "") + location.hash);
    load();
  }
  function injectViewCss() {
    if (document.getElementById("pdViewCss")) return;
    var st = document.createElement("style");
    st.id = "pdViewCss";
    st.textContent =
      ".rn-pd-viewtabs{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:10px 0 12px}" +
      ".rn-pd-viewtabs button{border:1px solid #c9b8a6;background:#fff;border-radius:999px;padding:9px 16px;font-size:15px;font-weight:700;cursor:pointer;color:#3a2c22}" +
      ".rn-pd-viewtabs button[aria-pressed=true]{background:#8a3b12;border-color:#8a3b12;color:#fff}" +
      ".rn-pd-viewtabs small{flex-basis:100%;color:#6b5a4c;font-size:13px}" +
      ".rn-pd-wa{display:inline-block;margin-left:6px;padding:1px 8px;border-radius:999px;background:#25d366;color:#fff!important;font-size:12px;font-weight:700;text-decoration:none}" +
      ".rn-md-bk-own{margin-top:10px}";
    document.head.appendChild(st);
  }
  function renderViewTabs(data) {
    var box = document.getElementById("pdViewTabs");
    if (!data.can_manage_real) { if (box) box.remove(); return; }
    injectViewCss();
    if (!box) {
      box = document.createElement("div");
      box.id = "pdViewTabs";
      box.className = "rn-pd-viewtabs";
      box.setAttribute("role", "tablist");
      var anchor = document.querySelector(".rn-pd-kpi");
      if (anchor) anchor.parentNode.insertBefore(box, anchor);
    }
    var v = currentView();
    var waiting = (data.booking_inbox_all || []).filter(function (b) { return b.status === "requested"; }).length;
    box.innerHTML =
      '<button type="button" role="tab" data-view="pemilik" aria-pressed="' + (v === "pemilik") + '">🔧 Menu Pemilik — Booking Masuk & Armada' +
        (waiting ? " (" + fmt(waiting) + " menunggu)" : "") + "</button>" +
      '<button type="button" role="tab" data-view="publik" aria-pressed="' + (v === "publik") + '">👁 Tampilan Publik / Pembooking</button>' +
      "<small>" + (v === "pemilik"
        ? "Anda pengelola posko ini: lihat siapa yang booking, hubungi lewat telepon / WhatsApp, konfirmasi atau tolak."
        : "Ini yang dilihat publik dan pengguna: pilih armada lalu isi booking. Kontak pembooking lain tidak tampil di sini.") + "</small>";
    box.querySelectorAll("button[data-view]").forEach(function (b) {
      b.addEventListener("click", function () { if (b.getAttribute("data-view") !== currentView()) setView(b.getAttribute("data-view")); });
    });
  }
  // Menu Pemilik: Booking Masuk naik ke atas daftar armada; tampilan publik: posisi semula.
  function placeBookingSection(data) {
    var sec = $("#bookingSection"), armadaSec = $("#armadaBody") && $("#armadaBody").closest("section"), row2 = $("#pdRow2");
    if (!sec || !armadaSec || !row2) return;
    if (data.can_manage) armadaSec.parentNode.insertBefore(sec, armadaSec);
    else row2.parentNode.insertBefore(sec, row2);
  }

  /* Google Maps link: prefer lat/lng, fall back to a text search. */
  function mapsUrl(lat, lng, text) {
    var a = parseFloat(lat), o = parseFloat(lng);
    if (isFinite(a) && isFinite(o)) return "https://www.google.com/maps?q=" + a + "," + o;
    var q = String(text == null ? "" : text).trim();
    return (q && q !== "-") ? "https://www.google.com/maps/search/?api=1&query=" + encodeURIComponent(q) : "";
  }
  function mapsLink(text, lat, lng) {
    var u = mapsUrl(lat, lng, text);
    var t = String(text == null ? "" : text).trim();
    if (!u) return esc(t || "-");
    return '<a href="' + u + '" target="_blank" rel="noopener">' + esc(t || "Lihat di peta") + " ↗</a>";
  }
  function statusChip(s) {
    var l = String(s || "").toLowerCase();
    if (l === "confirmed" || l === "available" || l === "arrived") return "ok";
    if (l === "requested" || l === "in_transit" || l === "reserved" || l === "assigned") return "warning";
    if (l === "rejected" || l === "cancelled") return "danger";
    return "";
  }

  var MODE_CHIP = { space_only: "", courier_pickup: "warning", both: "ok" };

  var ARMADA_STATUS = [
    ["available", "Tersedia"], ["reserved", "Sudah dibooking"], ["assigned", "Ditugaskan"],
    ["in_transit", "Dalam Perjalanan"], ["arrived", "Tiba"],
    ["completed", "Selesai"], ["cancelled", "Dibatalkan"],
  ];
  var SERVICE_MODE = [
    ["space_only", "Penyedia Ruang Muat"], ["courier_pickup", "Kurir Jemput-Antar"],
    ["both", "Ruang Muat + Kurir"],
  ];
  var BOOKING_POLICY = [
    ["pin_verify", "Konfirmasi PIN posko"], ["open", "Langsung terkonfirmasi"],
  ];

  // board sends "-" for empty fields; don't feed that back into a form
  function clean(v) { return (!v || v === "-") ? "" : String(v); }
  // "YYYY-MM-DD HH:MM" -> "YYYY-MM-DDTHH:MM" for <input type=datetime-local>
  function toLocalDT(v) {
    var s = clean(v);
    return /^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}/.test(s) ? s.slice(0, 16).replace(" ", "T") : "";
  }
  function optionList(pairs, current) {
    return pairs.map(function (p) {
      return '<option value="' + p[0] + '"' + (p[0] === current ? " selected" : "") + ">" + esc(p[1]) + "</option>";
    }).join("");
  }

  /* ---------- selector ---------- */
  function navToPosko(v) {
    if (!v) return;
    qs.set("id", v);
    qs.set("event", getEvent());
    location.search = qs.toString();
  }

  function renderSelector(list, current, viewer) {
    var sel = $("#poskoSelect");
    if (!sel) return;
    // owner 2026-11-09: tanpa ?id= pemilih menampilkan posko pertama tetapi isi halaman masih gabungan
    // ("Belum ada posko dipilih", tabel armada kosong) — langsung buka posko pertama agar isi = pilihan.
    if (!current && (list || []).length && !window.RN_POSKO_SUMMARY_MODE) { navToPosko(list[0].id); return; }

    // shared grouped picker: org member → "Posko organisasi saya" +
    // "Posko lain — terbuka untuk koordinasi"; guest → one flat list.
    if (window.RNPoskoPicker && viewer) {
      window.RNPoskoPicker.mount({
        selectEl: sel,
        viewer: viewer,
        current: current,
        points: (list || []).map(function (p) {
          return {
            posko_id: p.id, name: p.title, title: p.title,
            organization: p.organization,
            public_participation: p.public_participation,
            city: p.city,
          };
        }),
        labelFn: function (p) { return (p.name || p.title || "") + (p.city ? " — " + p.city : ""); },
        onChange: navToPosko,
      });
      return;
    }

    var opts = (list || []).map(function (p) {
      return '<option value="' + esc(p.id) + '"' + (p.id === current ? " selected" : "") + ">" +
        esc(p.title) + (p.city ? " — " + esc(p.city) : "") + "</option>";
    }).join("");
    if (!current || !(list || []).some(function (p) { return p.id === current; })) {
      opts = '<option value="">— pilih posko distribusi —</option>' + opts;
    }
    sel.innerHTML = opts;
    sel.onchange = function () { navToPosko(sel.value); };
  }

  /* ---------- KPI ---------- */
  function renderKpi(t, info) {
    $("#kpiArmada").textContent = fmt(t.armada_count);
    $("#kpiKapasitas").textContent = fmt(t.kapasitas_total_kg) + " kg";
    $("#kpiTerpakai").textContent = fmt(t.kapasitas_terpakai_kg) + " kg";
    $("#kpiMenunggu").textContent = fmt(t.booking_menunggu);
    // owner 2026-11-09: publik/pengguna lain melihat ruang yang masih tersedia + antrean, pemilik melihat beban kerja
    var manage = !!(CACHE && CACHE.can_manage);
    function lab(id, label, sub) {
      var card = $(id) && $(id).closest(".kpi-card"); if (!card) return;
      var sp = card.querySelectorAll("span")[1], sm = card.querySelector("small");
      if (sp) sp.textContent = label; if (sm) sm.textContent = sub;
    }
    if (!manage) {
      $("#kpiTerpakai").textContent = fmt(t.kapasitas_tersedia_kg) + " kg";
      lab("#kpiTerpakai", "Masih Tersedia", "ruang muat yang bisa dibooking");
      lab("#kpiMenunggu", "Antre Booking", "booking tempat menunggu konfirmasi posko");
      lab("#kpiKapasitas", "Kapasitas Total", "armada yang belum berangkat/selesai");
    }
  }

  /* ---------- armada table ---------- */
  function capMeter(a) {
    var pct = Math.min(100, Math.max(0, a.kapasitas_pct || 0));
    var cls = pct >= 90 ? "bad" : (pct >= 60 ? "warn" : "ok");
    var own = (a.muatan_sendiri_kg || 0) > 0
      ? '<small class="rn-muted">Muatan sendiri ' + fmt(a.muatan_sendiri_kg) + " kg · ditawarkan " +
        fmt(a.kapasitas_ditawarkan_kg) + " kg</small>"
      : "";
    return (
      '<div class="rn-md-cap"><div class="rn-md-cap-bar"><i class="' + cls + '" style="width:' + pct + '%"></i></div>' +
      "<small>Tersedia " + fmt(a.kapasitas_tersedia_kg) + " kg" +
      (a.kapasitas_total_m3 ? " · " + fmt(a.kapasitas_tersedia_m3) + " m³" : "") + "</small>" + own + "</div>"
    );
  }

  /* owner 2026-11-02: filter Jenis / Berangkat dari-sampai / Status / Cari */
  var ARMADA_ALL = [];
  function applyArmadaFilter() {
    var v = function (id) { var e = document.getElementById(id); return e ? e.value.trim() : ""; };
    var type = v("pdfType"), from = v("pdfFrom"), to = v("pdfTo"), st = v("pdfStatus"), q = v("pdfQ").toLowerCase();
    var list = ARMADA_ALL.filter(function (a) {
      if (type && a.jenis !== type) return false;
      if (st ? a.avail !== st : a.avail === "selesai") return false;
      var d = (a.departure_at_raw || "").slice(0, 10);
      if (from && d && d < from) return false;
      if (to && d && d > to) return false;
      if (q && (a.provider + " " + (a.rute || "") + " " + (a.coordination_notes || "")).toLowerCase().indexOf(q) === -1) return false;
      return true;
    });
    renderArmada(list);
    var shown = $("#armadaShown");
    if (shown && list.length !== ARMADA_ALL.length) shown.textContent = "Menampilkan " + list.length + " dari " + ARMADA_ALL.length + " armada";
    // owner 2026-11-09: armada yang sudah selesai disembunyikan oleh filter bawaan — jelaskan, jangan "Belum ada armada"
    var done = ARMADA_ALL.filter(function (a) { return a.avail === "selesai"; }).length;
    if (!list.length && ARMADA_ALL.length && !st && done) {
      $("#armadaBody").innerHTML = '<tr><td colspan="8"><em class="rn-muted">Tidak ada armada yang sedang aktif. ' + done +
        ' armada sudah selesai perjalanan — <a href="#" data-pd-showdone>tampilkan</a>.</em></td></tr>';
    }
  }
  document.addEventListener("click", function (e) {
    if (!e.target.closest("[data-pd-showdone]")) return;
    e.preventDefault(); var f = document.getElementById("pdfStatus"); if (f) { f.value = "selesai"; applyArmadaFilter(); }
  });
  ["pdfType", "pdfFrom", "pdfTo", "pdfStatus", "pdfQ"].forEach(function (id) {
    document.addEventListener(id === "pdfQ" ? "input" : "change", function (e) { if (e.target && e.target.id === id) applyArmadaFilter(); });
  });

  function renderArmada(list) {
    var body = $("#armadaBody"), shown = $("#armadaShown");
    if (!list || !list.length) {
      body.innerHTML = '<tr><td colspan="8"><em class="rn-muted">Belum ada armada. Gunakan "Daftarkan Armada".</em></td></tr>';
      if (shown) shown.textContent = "0 armada";
      return;
    }
    body.innerHTML = list.map(function (a) {
      var relawan = a.pickup_volunteer_name
        ? esc(a.pickup_volunteer_name)
        : (a.service_mode === "space_only" ? '<span class="rn-muted">—</span>' : '<span class="chip warning">belum ada</span>');
      return (
        '<tr class="rn-ba-row" data-armada="' + esc(a.id) + '" title="Lihat detail + booking">' +
        "<td><b>" + esc(a.provider) + "</b>" + (a.coordination_notes ? '<small class="rn-muted">' + esc(a.coordination_notes) + "</small>" : "") + "</td>" +
        "<td>" + esc(a.jenis) + "</td>" +
        '<td><span class="chip ' + (MODE_CHIP[a.service_mode] || "") + '">' + esc(a.service_mode_label) + "</span>" +
          '<small class="rn-muted">' + (a.booking_policy === "open" ? "booking terbuka" : "PIN") + "</small></td>" +
        "<td>" + capMeter(a) + "</td>" +
        "<td>" + esc(a.berangkat) + '<small class="rn-muted">→ ' + esc(a.eta) + "</small></td>" +
        "<td>" + relawan + "</td>" +
        '<td><span class="chip ' + statusChip(a.status) + '">' + esc(a.status_label) + "</span>" +
          (a.avail === "lewat" ? '<small class="rn-muted">jadwal lewat</small>' : a.avail === "penuh" ? '<small class="rn-muted">penuh</small>' : "") + "</td>" +
        // owner 2026-11-09: pemilik lihat jumlah booking; publik lihat antrean (isi booking hanya untuk pemilik)
        "<td>" + ((CACHE && CACHE.can_manage)
          ? (a.bookings_count ? '<span class="chip">' + fmt(a.bookings_count) + "</span>" : '<span class="rn-muted">0</span>')
          : (a.antri_booking ? '<span class="chip warning">' + fmt(a.antri_booking) + " antre</span><small class=\"rn-muted\">" + fmt(a.antri_kg) + " kg menunggu</small>" : '<span class="rn-muted">0 antre</span>') +
            (a.booking_konfirmasi ? '<small class="rn-muted">' + fmt(a.booking_konfirmasi) + " terkonfirmasi</small>" : "")) + "</td>" +
        "</tr>"
      );
    }).join("");
    body.querySelectorAll("tr.rn-ba-row").forEach(function (tr) {
      tr.addEventListener("click", function () { openArmadaDetail(tr.getAttribute("data-armada")); });
    });
    if (shown) shown.textContent = "Menampilkan " + list.length + " armada";
    // owner 2026-11-02: booking from Cari Armada (Manajemen Distribusi) opens that armada's detail + booking
    if (location.hash === "#armadaForm" && !window.__pdFormOpened) {
      window.__pdFormOpened = true;
      var fd = document.getElementById("armadaForm");
      if (fd) setTimeout(function () { fd.open = true; fd.scrollIntoView({ block: "start" }); }, 100);
    }
    var want = qs.get("armada");
    if (want && !window.__pdArmadaOpened) { window.__pdArmadaOpened = true; setTimeout(function () { openArmadaDetail(want); }, 50); }
  }

  function openArmadaDetail(id) {
    var a = ((CACHE && CACHE.armada) || []).filter(function (x) { return x.id === id; })[0];
    if (!a) return;
    var bk = ((CACHE && CACHE.booking_inbox) || []).filter(function (b) { return b.armada_id === id; });
    function row(k, v) { return v && v !== "-" ? '<div class="rn-md-dl"><span>' + esc(k) + "</span><b>" + v + "</b></div>" : ""; }
    var bkHtml = bk.length ? bk.map(function (b) {
      return (
        '<div class="rn-md-bk"><div class="rn-md-bk-main"><b>' + esc(b.cargo) + "</b> " +
        fmt(b.qty_kg) + " kg" + (b.qty_m3 ? " · " + fmt(b.qty_m3) + " m³" : "") +
        '<small class="rn-muted"> · ' + esc(b.delivery_label) + (b.requested_window ? " · " + esc(b.requested_window) : "") + "</small></div>" +
        '<div class="rn-md-bk-contacts"><span>Pembooking: <b>' + esc(b.booker) + "</b>" +
        (b.supplier_contact_person ? " (" + esc(b.supplier_contact_person) + ")" : "") +
        (b.supplier_contact_phone ? " · " + contact(b.supplier_contact_phone) : "") + "</span></div>" +
        '<div class="rn-md-bk-meta"><span class="chip ' + statusChip(b.status) + '">' + esc(b.status_label) + "</span>" +
        (b.verification_pin ? '<code class="rn-md-bk-id">PIN ' + esc(b.verification_pin) + "</code>" : "") + "</div></div>"
      );
    }).join("") : '<p class="rn-muted">Belum ada booking pada armada ini.</p>';
    $("#pdDrillTitle").textContent = a.provider;
    $("#pdDrillSub").textContent = a.service_mode_label + " · " + a.status_label;
    // Booking harus langsung tampak di detail kendaraan, sebelum rincian panjang.
    var bookingPanel = CACHE && CACHE.session_user_logged_in && !CACHE.logged_in
      ? '<section class="rn-md-booking-note"><h4>Booking Tempat</h4><p>Lengkapi pendaftaran Rescue-Net untuk booking tempat.</p><a class="btn primary mini" href="auth.html#daftar">Lengkapi pendaftaran</a></section>'
      : CACHE && CACHE.can_manage
      ? '<h4 class="rn-md-detail-h">Booking Masuk untuk kendaraan ini</h4><div class="rn-md-bk-list">' + bkHtml + "</div>" +
        '<section class="rn-md-bk-own"><h4 class="rn-md-detail-h">Booking Tempat</h4>' + bookingForm(a) + "</section>"
      : CACHE && CACHE.logged_in
      ? '<h4 class="rn-md-detail-h">Booking Tempat</h4>' + bookingForm(a)
      : '<section class="rn-md-booking-note"><h4>Booking Tempat</h4><p>Login untuk mengisi muatan, berat/volume, kontak, dan waktu pengiriman.</p><a class="btn primary mini" href="auth.html?next=' +
        encodeURIComponent(location.pathname.replace(/^.*\/pages\//, "") + location.search.replace(/&?armada=[^&]*/, "") + "&armada=" + a.id) +
        '">Login untuk booking tempat</a></section>';
    $("#pdDrillBody").innerHTML =
      bookingPanel +
      '<div class="rn-md-detail">' +
      row("Jenis", esc(a.jenis)) +
      row("Kebijakan booking", a.booking_policy === "open" ? "Langsung terkonfirmasi" : "Konfirmasi PIN posko") +
      row("Kapasitas total", fmt(a.kapasitas_total_kg) + " kg" + (a.kapasitas_total_m3 ? " · " + fmt(a.kapasitas_total_m3) + " m³" : "")) +
      ((a.muatan_sendiri_kg || a.muatan_sendiri_m3 || a.muatan_sendiri_desc)
        ? row("Muatan sendiri",
            esc(a.muatan_sendiri_desc || "milik penyedia") +
            ((a.muatan_sendiri_kg || a.muatan_sendiri_m3)
              ? " · " + fmt(a.muatan_sendiri_kg) + " kg" +
                (a.muatan_sendiri_m3 ? " · " + fmt(a.muatan_sendiri_m3) + " m³" : "")
              : "")) +
          row("Ditawarkan untuk umum", fmt(a.kapasitas_ditawarkan_kg) + " kg" +
            (a.kapasitas_total_m3 ? " · " + fmt(a.kapasitas_ditawarkan_m3) + " m³" : ""))
        : "") +
      row("Sisa kapasitas", fmt(a.kapasitas_tersedia_kg) + " kg" + (a.kapasitas_total_m3 ? " · " + fmt(a.kapasitas_tersedia_m3) + " m³" : "")) +
      row("Antrean booking", fmt(a.antri_booking || 0) + " menunggu konfirmasi" + (a.antri_kg ? " (" + fmt(a.antri_kg) + " kg)" : "") +
        " · " + fmt(a.booking_konfirmasi || 0) + " terkonfirmasi") +
      row("Rencana berangkat → tiba", esc(a.berangkat) + " → " + esc(a.eta)) +
      termsRows(a.syarat) +
      row("Lokasi saat ini", mapsLink(a.current_location)) +
      row("Rute", esc(a.rute)) +
      row("Titik serah terima", mapsLink(a.handover_location)) +
      row("Narahubung", esc(a.handover_contact_person) + (a.handover_contact_phone && a.handover_contact_phone !== "-" ? " · " + tel(a.handover_contact_phone) : "")) +
      row("Relawan jemput", esc(a.pickup_volunteer_name || "-")) +
      "</div>" +
      ((CACHE && CACHE.can_manage) ? gpsBlock(a) + armadaEditForm(a) : "") +
      // owner 2026-11-02: booking tempat wajib login — logged-in users get the normal form, guests a login link
      // pemilik sudah melihat "Booking Masuk" di atas (bookingPanel) - jangan dobel
      ((CACHE && CACHE.can_manage) ? ""
        : bk.length ? '<h4 class="rn-md-detail-h">Booking Anda</h4><div class="rn-md-bk-list">' + bkHtml + "</div>" : "");
    if (CACHE && CACHE.can_manage) wireArmadaEdit(a.id);
    if (CACHE && CACHE.logged_in) wireBookingForm(a);
    if (CACHE && CACHE.can_manage) wireGps(a);
    $("#pdDrill").hidden = false;
    document.body.style.overflow = "hidden";
  }

  /* "Booking Tempat" — any logged-in user, on an open transport posko.
     api_logistics.book_transport_space (PIN back unless policy = open). */
  // Syarat barang + pernyataan pembooking (wajib dicentang bila armada punya syarat).
  function termsAckBlock(a) {
    var t = a.syarat;
    if (!t || !t.ada) return "";
    return '<div class="rn-dispatch-terms">' + '<b>Syarat barang armada ini</b>' + termsRows(t).replace(/rn-md-dl/g, "rn-md-dl") +
      '<label class="rn-dispatch-ack"><input type="checkbox" name="terms_ack"> Barang saya memenuhi syarat di atas (packing, berat per koli, dokumen).</label></div>';
  }

  /* owner 2026-11-11: tujuan = tujuan armada; bila armada hanya perantara (estafet),
     pembooking boleh mengisi tujuan akhirnya sendiri. */
  function dropoffField(a) {
    var dest = a.route_destination || "";
    if (!dest) return '<label>Tujuan / dropoff *<input name="dropoff_location" placeholder="Posko / alamat tujuan" required></label>';
    return '<label>Tujuan / dropoff *<input name="dropoff_location" required readonly value="' + esc(dest) + '" data-armada-dest="' + esc(dest) + '"></label>' +
      '<label class="rn-pd-relay-own"><input type="checkbox" data-dest-own> Armada ini hanya perantara — saya isi tujuan akhir sendiri</label>';
  }
  function wireDropoff(form) {
    var cb = form.querySelector("[data-dest-own]"), inp = form.querySelector("[name=dropoff_location]");
    if (!cb || !inp) return;
    cb.addEventListener("change", function () {
      if (cb.checked) { inp.readOnly = false; inp.value = ""; inp.placeholder = "Tujuan akhir barang"; inp.focus(); }
      else { inp.readOnly = true; inp.value = inp.getAttribute("data-armada-dest") || ""; }
    });
  }

  function bookingIdentities() {
    var viewer = (CACHE && CACHE.viewer) || {};
    return { viewer: viewer, poskos: viewer.manages || (CACHE && CACHE.my_managed_poskos) || [] };
  }

  function bookingForm(a) {
    var me = (CACHE && CACHE.me) || {};
    var courierOk = (a.service_mode || "both") !== "space_only";
    return (
      '<details class="rn-pd-edit" open><summary>Booking Tempat</summary>' +
      '<form class="rn-form" id="pdBookForm">' +
      '<div class="form-grid">' +
      '<label>Pembooking atas nama<select name="booked_by_type">' +
        '<option value="posko">Posko pengantar / pengumpul</option>' +
        '<option value="individu">Pribadi / warga</option>' +
        '<option value="organization">Organisasi</option>' +
        '<option value="relawan">Relawan</option></select></label>' +
      '<label data-book-identity>Posko / organisasi pembooking<select name="booked_by_id"></select></label>' +
      '<label>Muatan<input name="cargo_desc" placeholder="Beras 40 karung / Air mineral" required></label>' +
      '<label>Berat (kg) *<input name="qty_weight_kg" type="number" step="0.01" min="0.01" placeholder="500" required></label>' +
      '<label>Volume (m³)<input name="qty_volume_m3" type="number" step="0.01" placeholder="2"></label>' +
      '<label>Cara antar<select name="delivery_method">' +
        (courierOk ? '<option value="use_transporter">Dijemput kurir armada</option>' : "") +
        '<option value="self_deliver">Antar sendiri ke titik jemput</option></select></label>' +
      '<label>Lokasi barang<input name="pickup_location" placeholder="Gudang / alamat"></label>' +
      dropoffField(a) +
      '<label>Kontak Anda *<input name="contact_person" placeholder="Nama" required value="' + esc(me.name || "") + '"></label>' +
      '<label>No. HP / WhatsApp *<input name="contact_phone" type="tel" inputmode="tel" pattern="[0-9+ ()-]{8,}" title="Nomor HP yang bisa dihubungi pemilik armada" placeholder="0812-…" required value="' + esc(me.phone || "") + '"></label>' +
      (me.name || me.phone ? '<small class="rn-muted rn-pd-autofill">Kontak diisi otomatis dari akun Anda — boleh diubah.</small>' : "") +
      '<label>Kapan barang dikirim *<input name="requested_window" placeholder="Besok pagi / 12 Nov 08:00" required></label>' +
      "</div>" +
      termsAckBlock(a) +
      '<div class="form-actions"><button class="btn primary" type="submit">Booking Tempat</button>' +
      '<span class="rn-pd-bk-msg" data-book-msg></span></div>' +
      "</form></details>"
    );
  }

  function wireBookingForm(a) {
    var form = $("#pdBookForm");
    if (!form) return;
    wireDropoff(form);
    function syncIdentity() {
      var ids = bookingIdentities(), type = form.elements.booked_by_type.value;
      var select = form.elements.booked_by_id;
      var values = type === "posko" ? ids.poskos : (type === "organization" && ids.viewer.org ? [ids.viewer.org] : []);
      select.innerHTML = values.map(function (p) {
        var id = typeof p === "string" ? p : (p.name || p.id);
        var known = ((CACHE && CACHE.transporter_poskos) || []).filter(function (t) { return (t.name || t.id) === id; })[0];
        var label = typeof p === "string" ? ((known && known.title) || p) : (p.title || id);
        if (type === "organization") label = ids.viewer.org_title || id;
        return '<option value="' + esc(id) + '">' + esc(label) + '</option>';
      }).join("");
      var needed = type === "posko" || type === "organization";
      if (needed && !values.length) select.innerHTML = '<option value="">Tidak ada posko/organisasi yang dapat dipakai</option>';
      select.required = needed;
      select.disabled = !needed;
      form.querySelector("[data-book-identity]").hidden = !needed;
    }
    form.elements.booked_by_type.addEventListener("change", syncIdentity);
    // audit S1 (review Suri): pengguna tanpa posko yang dikelola tidak boleh tertahan di pilihan "Posko"
    (function () {
      var ids = bookingIdentities(), t = form.elements.booked_by_type;
      if (t.value === "posko" && !ids.poskos.length) t.value = ids.viewer.org ? "organization" : "individu";
    })();
    syncIdentity();
    var msg = form.querySelector("[data-book-msg]");
    form.addEventListener("submit", async function (e) {
      e.preventDefault();
      var v = function (n) { return form[n] ? String(form[n].value).trim() : ""; };
      if (form.terms_ack && !form.terms_ack.checked) { if (msg) msg.textContent = " centang pernyataan memenuhi syarat barang"; return; }
      if (msg) msg.textContent = " booking tempat…";
      try {
        var r = await window.RN_FRAPPE.call("rescue_net.api_logistics.book_transport_space", {
          transport_space: a.id,
          booked_by_type: v("booked_by_type") || "posko",
          booked_by_id: form.elements.booked_by_id.disabled ? null : v("booked_by_id"),
          cargo_desc: v("cargo_desc"),
          qty_weight_kg: Number(form.qty_weight_kg.value || 0),
          qty_volume_m3: Number(form.qty_volume_m3.value || 0),
          delivery_method: v("delivery_method") || "self_deliver",
          pickup_location: v("pickup_location"),
          dropoff_location: v("dropoff_location"),
          contact_person: v("contact_person"),
          contact_phone: v("contact_phone"),
          requested_window: v("requested_window"),
          terms_ack: form.terms_ack && form.terms_ack.checked ? 1 : 0,
        }, { method: "POST" });
        var pin = r && (r.verification_pin || r.pin);
        if (msg) msg.textContent = pin
          ? " diminta ✓ — PIN konfirmasi: " + pin + " (berikan ke posko armada)"
          : " terkonfirmasi ✓";
        form.reset();
        await load();
      } catch (err) {
        var m = (err && err.message) || String(err);
        if (msg) msg.textContent = " gagal: " + m + (/login|permission|akses/i.test(m) ? " (perlu login)" : "");
      }
    });
  }

  /* Posisi armada dari GPS HP (owner 2026-11-02) — pengelola armada. api_armada.update_armada_position. */
  var GPS_WATCH = null;
  function gpsBlock(a) {
    var last = a.position_at ? "Posisi terakhir: " + esc(String(a.position_at).slice(0, 16)) +
      (a.position_lat ? ' · <a href="https://www.openstreetmap.org/?mlat=' + a.position_lat + "&mlon=" + a.position_lng +
        "#map=14/" + a.position_lat + "/" + a.position_lng + '" target="_blank" rel="noopener">lihat di peta</a>' : "") : "Belum ada posisi GPS.";
    return '<div class="rn-pd-gps"><b>📍 Posisi armada (GPS)</b><div class="rn-muted" data-gps-last>' + last + "</div>" +
      '<div class="form-actions"><button class="btn primary mini" type="button" data-gps-now>Kirim posisi sekarang</button>' +
      '<label class="rn-pd-gps-auto"><input type="checkbox" data-gps-auto' + (GPS_WATCH ? " checked" : "") + "> Lacak otomatis selama halaman ini terbuka</label></div>" +
      '<small class="rn-muted">Publik melihat posisi & jejak armada di Manajemen Distribusi → Cari Armada. Bawa HP di armada saat lacak otomatis.</small>' +
      '<span class="rn-pd-bk-msg" data-gps-msg></span></div>';
  }
  function sendPos(id, p, msgEl, lastEl) {
    return window.RN_FRAPPE.call("rescue_net.api_armada.update_armada_position", { transport_space: id,
      latitude: p.coords.latitude, longitude: p.coords.longitude, accuracy_m: p.coords.accuracy }, { method: "POST" })
      .then(function (r) {
        if (msgEl) msgEl.textContent = r.skipped ? " posisi belum berubah" : " terkirim " + String(r.position_at).slice(11, 16);
        if (lastEl && !r.skipped) lastEl.textContent = "Posisi terakhir: " + String(r.position_at).slice(0, 16) +
          " (" + p.coords.latitude.toFixed(5) + ", " + p.coords.longitude.toFixed(5) + ")";
      }).catch(function (e) { if (msgEl) msgEl.textContent = " gagal: " + ((e && e.message) || e); });
  }
  function wireGps(a) {
    var box = document.querySelector(".rn-pd-gps");
    if (!box) return;
    var msg = box.querySelector("[data-gps-msg]"), last = box.querySelector("[data-gps-last]");
    box.querySelector("[data-gps-now]").addEventListener("click", function () {
      if (!navigator.geolocation) { msg.textContent = " HP/peramban tidak mendukung GPS"; return; }
      msg.textContent = " mencari posisi…";
      navigator.geolocation.getCurrentPosition(function (p) { sendPos(a.id, p, msg, last); },
        function () { msg.textContent = " izin lokasi ditolak"; }, { enableHighAccuracy: true, timeout: 20000 });
    });
    box.querySelector("[data-gps-auto]").addEventListener("change", function (e) {
      if (GPS_WATCH) { navigator.geolocation.clearWatch(GPS_WATCH.id); GPS_WATCH = null; }
      if (!e.target.checked) { msg.textContent = " lacak otomatis dimatikan"; return; }
      if (!navigator.geolocation) { msg.textContent = " HP/peramban tidak mendukung GPS"; e.target.checked = false; return; }
      var lastSent = 0;
      GPS_WATCH = { armada: a.id, id: navigator.geolocation.watchPosition(function (p) {
        if (Date.now() - lastSent < 60000) return;   // at most once a minute
        lastSent = Date.now(); sendPos(a.id, p, msg, last);
      }, function () { msg.textContent = " izin lokasi ditolak"; }, { enableHighAccuracy: true }) };
      msg.textContent = " lacak otomatis aktif (tiap ±1 menit)";
    });
  }

  /* Public (no-account) booking — DISABLED 2026-11-02 (owner: booking tempat wajib login); kept for reference.
     api_logistics.book_transport_space_public -> returns a Kode Edit. */
  function publicBookingForm(a) {
    var courierOk = (a.service_mode || "both") !== "space_only";
    return (
      '<details class="rn-pd-edit" open><summary>Booking tempat tanpa akun (warga)</summary>' +
      '<form class="rn-form" id="pdPublicBookForm">' +
      '<div class="form-grid">' +
      '<label>Nama Anda<input name="contact_person" placeholder="Nama lengkap" required></label>' +
      '<label>No. HP / WhatsApp<input name="contact_phone" placeholder="0812-…" required></label>' +
      '<label>Muatan<input name="cargo_desc" placeholder="Beras 20 karung / Air mineral" required></label>' +
      '<label>Berat (kg)<input name="qty_weight_kg" type="number" step="0.01" placeholder="100"></label>' +
      '<label>Volume (m³)<input name="qty_volume_m3" type="number" step="0.01" placeholder="0.5"></label>' +
      '<label>Cara antar<select name="delivery_method">' +
        (courierOk ? '<option value="use_transporter">Dijemput kurir armada</option>' : "") +
        '<option value="self_deliver">Antar sendiri ke titik jemput</option></select></label>' +
      '<label>Lokasi barang<input name="pickup_location" placeholder="Rumah / gudang / alamat"></label>' +
      '<label>Tujuan / dropoff<input name="dropoff_location" placeholder="Posko tujuan"></label>' +
      '<label>Kapan barang dikirim *<input name="requested_window" placeholder="Besok pagi / 12 Nov 08:00" required></label>' +
      "</div>" +
      termsAckBlock(a) +
      '<div class="form-actions"><button class="btn primary" type="submit">Booking tempat (tanpa akun)</button>' +
      '<span class="rn-pd-bk-msg" data-pub-msg></span></div>' +
      '<p class="rn-muted rn-pd-code" data-pub-code hidden></p>' +
      "</form></details>"
    );
  }

  function wirePublicBookingForm(a) {
    var form = $("#pdPublicBookForm");
    if (!form) return;
    var msg = form.querySelector("[data-pub-msg]");
    var codeBox = form.querySelector("[data-pub-code]");
    form.addEventListener("submit", async function (e) {
      e.preventDefault();
      var v = function (n) { return form[n] ? String(form[n].value).trim() : ""; };
      if (form.terms_ack && !form.terms_ack.checked) { if (msg) msg.textContent = " centang pernyataan memenuhi syarat barang"; return; }
      if (msg) msg.textContent = " booking tempat…";
      try {
        var r = await window.RN_FRAPPE.call("rescue_net.api_logistics.book_transport_space_public", {
          transport_space: a.id,
          contact_person: v("contact_person"),
          contact_phone: v("contact_phone"),
          cargo_desc: v("cargo_desc"),
          qty_weight_kg: Number(form.qty_weight_kg.value || 0),
          qty_volume_m3: Number(form.qty_volume_m3.value || 0),
          delivery_method: v("delivery_method") || "self_deliver",
          pickup_location: v("pickup_location"),
          dropoff_location: v("dropoff_location"),
          requested_window: v("requested_window"),
                  terms_ack: form.terms_ack && form.terms_ack.checked ? 1 : 0,
        }, { method: "POST" });
        if (msg) msg.textContent = " terkirim ✓";
        if (codeBox) {
          codeBox.hidden = false;
          codeBox.innerHTML =
            "<b>Simpan kode ini</b> untuk melacak / mengubah booking (lihat panel " +
            "“Lacak / Ubah Booking Tamu”):<br>Booking ID: <code>" + esc(r.booking) +
            "</code><br>Kode Edit: <code>" + esc(r.edit_code) + "</code>" +
            (r.verification_pin ? "<br>PIN untuk posko: <code>" + esc(r.verification_pin) + "</code>" : "") +
            "<br><small>Kode Edit hanya ditampilkan sekali.</small>";
        }
        form.reset();
        await load();
      } catch (err) {
        if (msg) msg.textContent = " gagal: " + ((err && err.message) || String(err));
      }
    });
  }

  /* "Lacak / Ubah Booking Tamu" drawer (page-level, not per-armada). */
  function wireGuestTrack() {
    var form = $("#pdGuestTrackForm");
    if (!form) return;
    var msg = form.querySelector("[data-gt-msg]");
    var out = $("#pdGuestTrackResult");
    var current = null;

    function creds() {
      return {
        booking: form.booking.value.trim(),
        edit_code: form.edit_code.value.trim(),
        contact_phone: form.contact_phone.value.trim(),
      };
    }

    function wireEdit() {
      var ef = $("#pdGuestEditForm");
      if (!ef) return;
      var em = ef.querySelector("[data-ge-msg]");
      ef.addEventListener("submit", async function (e) {
        e.preventDefault();
        em.textContent = " menyimpan…";
        try {
          var p = creds();
          p.cargo_desc = ef.cargo_desc.value.trim();
          p.qty_weight_kg = Number(ef.qty_weight_kg.value || 0);
          p.qty_volume_m3 = Number(ef.qty_volume_m3.value || 0);
          p.pickup_location = ef.pickup_location.value.trim();
          p.dropoff_location = ef.dropoff_location.value.trim();
          p.requested_window = ef.requested_window.value.trim();
          var r = await window.RN_FRAPPE.call(
            "rescue_net.api_logistics.update_public_transport_booking", p, { method: "POST" });
          em.textContent = " tersimpan ✓";
          render(r);
          await load();
        } catch (err) { em.textContent = " gagal: " + ((err && err.message) || err); }
      });
      var cancelBtn = $("#pdGuestCancelBtn");
      if (cancelBtn) cancelBtn.addEventListener("click", async function () {
        if (!window.confirm("Batalkan booking ini?")) return;
        em.textContent = " membatalkan…";
        try {
          var p = creds(); p.cancel = 1;
          var r = await window.RN_FRAPPE.call(
            "rescue_net.api_logistics.update_public_transport_booking", p, { method: "POST" });
          render(r);
          await load();
        } catch (err) { em.textContent = " gagal: " + ((err && err.message) || err); }
      });
    }

    function render(b) {
      current = b;
      out.hidden = false;
      var editable = b.status === "requested" || b.status === "confirmed";
      out.innerHTML =
        '<div class="rn-md-detail">' +
        '<div class="rn-md-dl"><span>Armada</span><b>' + esc(b.armada) + "</b></div>" +
        '<div class="rn-md-dl"><span>Status</span><b>' + esc(b.status_label) + "</b></div>" +
        (b.verification_pin ? '<div class="rn-md-dl"><span>PIN posko</span><b>' + esc(b.verification_pin) + "</b></div>" : "") +
        "</div>" +
        (editable
          ? '<form class="rn-form" id="pdGuestEditForm"><div class="form-grid">' +
            '<label>Muatan<input name="cargo_desc" value="' + esc(b.cargo_desc) + '"></label>' +
            '<label>Berat (kg)<input name="qty_weight_kg" type="number" step="0.01" value="' + esc(b.qty_weight_kg || "") + '"></label>' +
            '<label>Volume (m³)<input name="qty_volume_m3" type="number" step="0.01" value="' + esc(b.qty_volume_m3 || "") + '"></label>' +
            '<label>Lokasi barang<input name="pickup_location" value="' + esc(b.pickup_location) + '"></label>' +
            '<label>Tujuan<input name="dropoff_location" value="' + esc(b.dropoff_location) + '"></label>' +
            '<label>Perkiraan waktu<input name="requested_window" value="' + esc(b.requested_window) + '"></label>' +
            "</div><div class=\"form-actions\">" +
            '<button class="btn primary" type="submit">Simpan Perubahan</button>' +
            '<button class="btn" type="button" id="pdGuestCancelBtn">Batalkan Booking</button>' +
            '<span class="rn-pd-bk-msg" data-ge-msg></span></div></form>'
          : '<p class="rn-muted">Booking sudah ' + esc(b.status_label) + " — tidak bisa diubah.</p>");
      if (editable) wireEdit();
    }

    form.addEventListener("submit", async function (e) {
      e.preventDefault();
      msg.textContent = "mengecek…";
      try {
        var b = await window.RN_FRAPPE.call(
          "rescue_net.api_logistics.get_public_transport_booking", creds());
        msg.textContent = "";
        render(b);
      } catch (err) {
        msg.textContent = "gagal: " + ((err && err.message) || err);
        out.hidden = true;
      }
    });
  }

  // Syarat barang (packing, berat per koli, terlarang, dokumen, batas serah) — satu blok untuk detail armada.
  function termsRows(t) {
    if (!t || !t.ada) return '<div class="rn-md-dl"><span>Syarat barang</span><b class="rn-muted">Belum diatur penyedia</b></div>';
    var parts = [];
    if (t.packing_label) parts.push("<b>" + esc(t.packing_label) + "</b>" + (t.packing_spec ? " — " + esc(t.packing_spec) : ""));
    else if (t.packing_spec) parts.push(esc(t.packing_spec));
    if (t.maks_koli_kg) parts.push("Maks " + fmt(t.maks_koli_kg) + " kg per koli");
    if (t.batas_serah) parts.push("Serah barang paling lambat " + esc(t.batas_serah));
    if (t.terlarang) parts.push("Terlarang/dibatasi: " + esc(t.terlarang));
    if (t.dokumen) parts.push("Dokumen: " + esc(t.dokumen));
    if (t.syarat) parts.push(esc(t.syarat));
    return '<div class="rn-md-dl"><span>Syarat barang</span><b style="font-weight:500">' +
      parts.map(function (p) { return '<span style="display:block;margin:0 0 4px">' + p + "</span>"; }).join("") + "</b></div>";
  }

  function armadaEditForm(a) {
    return (
      '<details class="rn-pd-edit"><summary>Perbarui armada</summary>' +
      '<form class="rn-form" id="pdArmadaEditForm">' +
      '<div class="form-grid">' +
      '<label>Status<select name="transport_status">' + optionList(ARMADA_STATUS, a.status) + "</select></label>" +
      '<label>Mode layanan<select name="service_mode">' + optionList(SERVICE_MODE, a.service_mode) + "</select></label>" +
      '<label>Kebijakan booking<select name="booking_policy">' + optionList(BOOKING_POLICY, a.booking_policy) + "</select></label>" +
      '<label>Kursi relawan<input type="number" min="0" name="volunteer_capacity_seats" value="' + esc(a.kursi_relawan || 0) + '"></label>' +
      '<label>Titik jemput relawan<input name="volunteer_pickup_location" value="' + esc(clean(a.jemput_relawan || "")) + '"></label>' +
      '<label>Muatan sendiri (kg)<input type="number" step="0.01" name="own_load_kg" value="' + esc(a.muatan_sendiri_kg || "") + '"></label>' +
      '<label>Muatan sendiri (m³)<input type="number" step="0.01" name="own_load_m3" value="' + esc(a.muatan_sendiri_m3 || "") + '"></label>' +
      '<label>Lokasi saat ini<input name="current_location" value="' + esc(clean(a.current_location)) + '"></label>' +
      '<label>Jam berangkat<input type="datetime-local" name="departure_at" value="' + esc(toLocalDT(a.berangkat)) + '"></label>' +
      '<label>ETA<input type="datetime-local" name="eta_at" value="' + esc(toLocalDT(a.eta)) + '"></label>' +
      '<label>Titik serah terima<input name="handover_location" value="' + esc(clean(a.handover_location)) + '"></label>' +
      '<label>Narahubung<input name="handover_contact_person" value="' + esc(clean(a.handover_contact_person)) + '"></label>' +
      '<label>No. kontak serah terima<input name="handover_contact_phone" value="' + esc(clean(a.handover_contact_phone)) + '"></label>' +
      "</div>" +
      '<label>Muatan sendiri (deskripsi)<input name="own_cargo_desc" value="' + esc(clean(a.muatan_sendiri_desc)) + '"></label>' +
      '<label>Catatan koordinasi<textarea name="coordination_notes" rows="2">' + esc(clean(a.coordination_notes)) + "</textarea></label>" +
      '<fieldset class="rn-evc-field rn-pd-terms"><legend>Syarat barang</legend><div class="form-grid">' +
      '<label>Packing<select name="packing_required">' + optionList([["", "Tidak diatur"], ["dianjurkan", "Dianjurkan"], ["wajib", "Wajib"]], (a.syarat && a.syarat.packing) || "") + "</select></label>" +
      '<label>Berat maks per koli (kg)<input type="number" step="0.1" min="0" name="max_piece_weight_kg" value="' + esc((a.syarat && a.syarat.maks_koli_kg) || "") + '"></label>' +
      '<label>Batas serah barang<input type="datetime-local" name="cargo_cutoff_at" value="' + esc(toLocalDT((a.syarat && a.syarat.batas_serah) || "")) + '"></label>' +
      '<label class="rn-form-wide">Spesifikasi packing<input name="packing_spec" value="' + esc((a.syarat && a.syarat.packing_spec) || "") + '"></label>' +
      '<label class="rn-form-wide">Syarat lain<textarea name="cargo_requirements" rows="2">' + esc((a.syarat && a.syarat.syarat) || "") + "</textarea></label>" +
      '<label class="rn-form-wide">Barang terlarang / dibatasi<input name="prohibited_items" value="' + esc((a.syarat && a.syarat.terlarang) || "") + '"></label>' +
      '<label class="rn-form-wide">Dokumen yang diperlukan<input name="documents_required" value="' + esc((a.syarat && a.syarat.dokumen) || "") + '"></label>' +
      "</div></fieldset>" +
      '<fieldset class="rn-evc-field"><legend>Bencana yang dilayani armada *</legend><div id="pdEditEventPicker"></div></fieldset>' +
      '<fieldset class="rn-evc-field"><legend>Posko logistik yang dilayani <small>— kosong = semua</small></legend><div id="pdEditPoskoPicker"></div></fieldset>' +
      '<div class="form-actions"><button class="btn primary" type="submit">Simpan Perubahan</button>' +
      '<span class="rn-pd-bk-msg" data-armada-edit-msg></span></div>' +
      "</form></details>"
    );
  }

  function wireArmadaEdit(id) {
    var form = $("#pdArmadaEditForm");
    if (!form) return;
    var msg = form.querySelector("[data-armada-edit-msg]");
    var a = ((CACHE && CACHE.armada) || []).filter(function (x) { return x.id === id; })[0] || {};
    var served = mountServedPickers($("#pdEditEventPicker"), $("#pdEditPoskoPicker"),
      (a.served_events && a.served_events.length) ? a.served_events : [getEvent()], a.served_poskos || []);
    form.addEventListener("submit", async function (e) {
      e.preventDefault();
      var v = function (n) { return form[n] ? String(form[n].value).trim() : ""; };
      var payload = {
        transport_space: id,
        transport_status: v("transport_status"),
        service_mode: v("service_mode"),
        booking_policy: v("booking_policy"),
        volunteer_capacity_seats: v("volunteer_capacity_seats"),
        volunteer_pickup_location: v("volunteer_pickup_location"),
        current_location: v("current_location"),
        own_load_kg: v("own_load_kg"),
        own_load_m3: v("own_load_m3"),
        own_cargo_desc: v("own_cargo_desc"),
        handover_location: v("handover_location"),
        handover_contact_person: v("handover_contact_person"),
        handover_contact_phone: v("handover_contact_phone"),
        coordination_notes: v("coordination_notes"),
        packing_required: v("packing_required"),
        max_piece_weight_kg: v("max_piece_weight_kg"),
        cargo_cutoff_at: v("cargo_cutoff_at").replace("T", " "),
        packing_spec: v("packing_spec"),
        cargo_requirements: v("cargo_requirements"),
        prohibited_items: v("prohibited_items"),
        documents_required: v("documents_required"),
      };
      if (served) {
        var evs = served.ev.getSelected();
        if (!evs.length) { if (msg) msg.textContent = " pilih minimal satu bencana"; return; }
        payload.served_events = JSON.stringify(evs);
        payload.served_poskos = JSON.stringify(served.pk.getSelected());
      }
      var d1 = v("departure_at"), e1 = v("eta_at");
      if (d1) payload.departure_at = d1.replace("T", " ");
      if (e1) payload.eta_at = e1.replace("T", " ");
      if (msg) msg.textContent = " menyimpan…";
      try {
        await window.RN_FRAPPE.call("rescue_net.api_logistics.update_transport_space", payload, { method: "POST" });
        if (msg) msg.textContent = " tersimpan ✓";
        closeDrill();
        await load();
      } catch (err) {
        var m = (err && err.message) || String(err);
        if (msg) msg.textContent = " gagal: " + m + (/login|permission|akses/i.test(m) ? " (perlu login)" : "");
      }
    });
  }
  function closeDrill() { $("#pdDrill").hidden = true; document.body.style.overflow = ""; }

  /* ---------- booking inbox ---------- */
  // estafet: pilih armada lain yang melayani bencana ini (Cari Armada), lalu api_logistics.book_relay_leg
  function wireRelay(box) {
    var flow = box.getAttribute("data-flow"), msg = box.querySelector(".rn-pd-bk-msg");
    box.querySelector('[data-relay="scan"]').addEventListener("click", async function () {
      msg.textContent = " mencatat…";
      try {
        await window.RN_FRAPPE.call("rescue_net.api_custody.record_scan", { flow: flow, scan_type: "handover",
          note: "Serah-terima di " + ((CACHE && CACHE.posko_info && CACHE.posko_info.title) || "posko distribusi") }, { method: "POST" });
        msg.textContent = " serah-terima tercatat ✓";
      } catch (e) { msg.textContent = " " + ((e && e.message) || e); }
    });
    box.querySelector('[data-relay="open"]').addEventListener("click", async function () {
      if (box.querySelector("form")) return;
      msg.textContent = " memuat armada…";
      var r;
      try { r = await window.RN_FRAPPE.call("rescue_net.api_armada.armada_finder", { disaster_event: getEvent() || null, status: "tersedia" }); }
      catch (e) { msg.textContent = " " + ((e && e.message) || e); return; }
      var mine = ((CACHE && CACHE.armada) || []).map(function (a) { return a.id; });
      var rows = (r.rows || []).filter(function (a) { return mine.indexOf(a.name) === -1; });
      if (!rows.length) { msg.textContent = " belum ada armada lain yang tersedia."; return; }
      msg.textContent = "";
      var f = document.createElement("form");
      f.className = "rn-form rn-pd-relay-form";
      f.innerHTML = '<label>Armada berikutnya<select name="space">' + rows.map(function (a) {
          return '<option value="' + esc(a.name) + '">' + esc(a.title) + " — " + esc(a.posko_title || "") + " (" + esc(a.type_label) +
            (a.left_kg != null ? ", sisa " + fmt(a.left_kg) + " kg" : "") + ")</option>";
        }).join("") + "</select></label>" +
        '<label>Titik serah<input name="from" placeholder="mis. pelabuhan / simpang kota"></label>' +
        '<label>Tujuan kaki ini<input name="to" placeholder="mis. posko distribusi berikutnya / posko tujuan"></label>' +
        '<label class="rn-dispatch-ack"><input type="checkbox" name="ack"> Barang memenuhi syarat armada berikutnya</label>' +
        '<div class="form-actions"><button class="btn primary mini" type="submit">Booking tempat kaki estafet</button><span class="rn-pd-bk-msg"></span></div>';
      box.appendChild(f);
      f.addEventListener("submit", async function (ev) {
        ev.preventDefault();
        var m = f.querySelector(".rn-pd-bk-msg");
        m.textContent = " booking tempat…";
        try {
          var x = await window.RN_FRAPPE.call("rescue_net.api_logistics.book_relay_leg", { flow: flow, transport_space: f.space.value,
            pickup_location: f.from.value.trim(), dropoff_location: f.to.value.trim(), terms_ack: f.ack.checked ? 1 : 0 }, { method: "POST" });
          m.textContent = " estafet ke-" + x.leg_seq + " " + (x.status === "confirmed" ? "terkonfirmasi" :
            "menunggu konfirmasi posko armada" + (x.verification_pin ? " (PIN " + x.verification_pin + ")" : ""));
        } catch (e) { m.textContent = " " + ((e && e.message) || e); }
      });
    });
  }

  function renderBookings(list) {
    var body = $("#bookingBody");
    var sec = $("#bookingSection"), manage = !!(CACHE && CACHE.can_manage);
    if (sec) sec.hidden = !manage && !(list && list.length);
    if ($("#bookingTitle")) $("#bookingTitle").textContent = manage ? "Booking Masuk" : "Booking Anda";
    if ($("#bookingSub")) $("#bookingSub").textContent = manage
      ? "Permintaan ruang dari posko / donatur / organisasi. Konfirmasi (dengan PIN bila pembooking publik), atau tolak."
      : "Booking tempat ruang muat yang Anda buat di armada posko ini. Isi booking pihak lain hanya terlihat oleh pengelola posko.";
    if (!list || !list.length) {
      body.innerHTML = '<tr><td colspan="7"><em class="rn-muted">Belum ada booking masuk.</em></td></tr>';
      return;
    }
    var canManage = !!(CACHE && CACHE.can_manage);
    body.innerHTML = list.map(function (b) {
      var act = '<span class="rn-muted">' + esc(b.id) + "</span>";
      if (b.status === "requested" && canManage) {
        act =
          '<div class="rn-pd-bk-act" data-booking="' + esc(b.id) + '">' +
          (b.needs_pin ? '<input class="rn-pd-pin" placeholder="PIN" maxlength="8">' : "") +
          '<button type="button" class="btn primary mini" data-do="confirm">Konfirmasi</button>' +
          '<button type="button" class="btn mini" data-do="reject">Tolak</button>' +
          '<span class="rn-pd-bk-msg"></span></div>';
      } else if (b.status === "confirmed" && canManage && b.flow) {
        // owner 2026-11-09 estafet: pembawa mencatat serah-terima & meneruskan ke posko distribusi berikutnya
        act =
          '<div class="rn-pd-relay" data-flow="' + esc(b.flow) + '">' +
          '<button type="button" class="btn mini" data-relay="scan">Catat serah-terima</button>' +
          '<button type="button" class="btn mini" data-relay="open">Teruskan estafet</button>' +
          '<span class="rn-pd-bk-msg"></span></div>';
      }
      return (
        "<tr><td><b>" + esc(b.cargo) + "</b><small class=\"rn-muted\">" + esc(b.armada) + "</small>" +
          (b.is_shipment ? '<small class="rn-muted">' + (b.leg === "first_mile" ? "Jemput ke titik serah: " : b.leg === "relay" ? "Kaki estafet: " : "Kiriman posko: ") +
            esc(b.pickup || "-") + " → " + esc(b.dropoff || "-") +
            (b.event_title ? " · " + esc(b.event_title) : "") + "</small>" : "") +
          (b.note ? '<small class="rn-muted">' + esc(b.note) + "</small>" : "") +
          (b.terms_ack ? '<small class="rn-muted">✓ Pembooking menyatakan memenuhi syarat barang</small>' : "") + "</td>" +
        "<td>" + fmt(b.qty_kg) + " kg" + (b.qty_m3 ? " · " + fmt(b.qty_m3) + " m³" : "") + "</td>" +
        "<td>" + esc(b.delivery_label) + "</td>" +
        "<td>" + esc(b.booker) + (b.is_guest ? ' <span class="chip">tamu</span>' : "") +
          (b.supplier_contact_person ? " (" + esc(b.supplier_contact_person) + ")" : "") +
          "<small class=\"rn-muted\">" + contact(b.supplier_contact_phone) + "</small></td>" +
        "<td>" + esc((b.window_from || b.window_to) ? (b.window_from || "…") + " s/d " + (b.window_to || "…")
          : (b.requested_window || b.requested_at || "-")) + "</td>" +
        '<td><span class="chip ' + statusChip(b.status) + '">' + esc(b.status_label) + "</span></td>" +
        "<td>" + act + "</td></tr>"
      );
    }).join("");

    body.querySelectorAll(".rn-pd-relay").forEach(wireRelay);
    body.querySelectorAll(".rn-pd-bk-act").forEach(function (box) {
      var id = box.getAttribute("data-booking");
      var pin = box.querySelector(".rn-pd-pin");
      var msg = box.querySelector(".rn-pd-bk-msg");
      box.querySelectorAll("button[data-do]").forEach(function (btn) {
        btn.addEventListener("click", async function () {
          var doWhat = btn.getAttribute("data-do");
          msg.textContent = "Memproses…";
          try {
            if (doWhat === "confirm") {
              await window.RN_FRAPPE.call("rescue_net.api_logistics.confirm_transport_booking",
                { booking: id, pin: pin ? pin.value.trim() : "" }, { method: "POST" });
            } else {
              await window.RN_FRAPPE.call("rescue_net.api_logistics.reject_transport_booking",
                { booking: id }, { method: "POST" });
            }
            msg.textContent = "OK";
            await load();
          } catch (err) {
            var m = (err && err.message) || String(err);
            msg.textContent = "Gagal: " + m + (/login|permission|akses/i.test(m) ? " (perlu login)" : "");
          }
        });
      });
    });
  }

  /* ---------- relawan ---------- */
  function renderRelawan(list) {
    var el = $("#relawanList");
    if (!list || !list.length) {
      el.innerHTML = '<p class="rn-muted">Belum ada relawan distribusi di posko ini.</p>';
      return;
    }
    el.innerHTML = '<div class="rn-md-pm-cands">' + list.map(function (v) {
      return '<span class="chip" title="ID: ' + esc(v.id) + '">' + esc(v.name) + " · " + esc(v.status || "") + "</span>";
    }).join("") + "</div>";
  }

  /* ---------- forms ---------- */
  // owner 2026-10-19: every armada lists the disasters it serves and (optional)
  // the posko logistik whose cargo it carries
  function mountServedPickers(evEl, pkEl, events, poskos) {
    if (!evEl || !pkEl || !window.RNEventChecklist) return null;
    var pk = window.RNEventChecklist.mountPoskos(pkEl, { selected: poskos || [] });
    var ev = window.RNEventChecklist.mount(evEl, {
      selected: events, multiple: true,
      onChange: function (sel) { pk.setEvents(ev ? ev.getSelected() : sel); },
    });
    ev.ready.then(function () { pk.setEvents(ev.getSelected()); });
    return { ev: ev, pk: pk };
  }

  function wireArmadaForm() {
    var form = $("[data-create-armada]"), msg = $("[data-armada-message]");
    if (!form) return;
    var served = mountServedPickers($("#armadaEventPicker"), $("#armadaPoskoPicker"), [getEvent()], []);
    form.addEventListener("submit", async function (e) {
      e.preventDefault();
      var f = function (n) { return form[n] && form[n].value ? String(form[n].value).trim() : ""; };
      var posko = getPosko();
      if (!posko) { if (msg) msg.textContent = "Pilih posko distribusi dulu."; return; }
      var events = served ? served.ev.getSelected() : [getEvent()];
      if (!events.length) { if (msg) msg.textContent = "Pilih minimal satu bencana yang dilayani armada."; return; }
      if (msg) msg.textContent = "Menyimpan…";
      try {
        await window.RN_FRAPPE.call("rescue_net.api_logistics.create_transport_space", {
          coordination_posko: posko,
          disaster_event: events[0],
          served_events: JSON.stringify(events),
          served_poskos: JSON.stringify(served ? served.pk.getSelected() : []),
          provider_name: f("provider_name"),
          transport_type: f("transport_type"),
          service_mode: f("service_mode"),
          booking_policy: f("booking_policy"),
          volunteer_capacity_seats: Number((form.volunteer_capacity_seats && form.volunteer_capacity_seats.value) || 0),
          volunteer_pickup_location: form.volunteer_pickup_location ? form.volunteer_pickup_location.value.trim() : "",
          route_origin: f("route_origin"),
          route_destination: f("route_destination"),
          capacity_weight_kg: Number(form.capacity_weight_kg.value || 0),
          capacity_volume_m3: Number(form.capacity_volume_m3.value || 0),
          own_load_kg: Number((form.own_load_kg && form.own_load_kg.value) || 0),
          own_load_m3: Number((form.own_load_m3 && form.own_load_m3.value) || 0),
          own_cargo_desc: f("own_cargo_desc"),
          departure_at: f("departure_at").replace("T", " "),
          eta_at: f("eta_at").replace("T", " "),
          current_location: f("current_location"),
          handover_location: f("handover_location"),
          handover_contact_person: f("handover_contact_person"),
          handover_contact_phone: f("handover_contact_phone"),
          coordination_notes: f("coordination_notes"),
          packing_required: f("packing_required"),
          max_piece_weight_kg: f("max_piece_weight_kg"),
          cargo_cutoff_at: f("cargo_cutoff_at").replace("T", " "),
          packing_spec: f("packing_spec"),
          cargo_requirements: f("cargo_requirements"),
          prohibited_items: f("prohibited_items"),
          documents_required: f("documents_required"),
        }, { method: "POST" });
        if (msg) msg.textContent = "Armada tersimpan.";
        form.reset();
        if (served) served.ev.setSelected([getEvent()]);
        await load();
      } catch (err) {
        var m = (err && err.message) || String(err);
        if (msg) msg.textContent = "Gagal: " + m + (/login|permission|akses/i.test(m) ? " (perlu login)" : "");
      }
    });
  }

  function wireAssignForm() {
    var form = $("[data-assign-form]"), msg = $("[data-assign-message]");
    if (!form) return;
    form.addEventListener("submit", async function (e) {
      e.preventDefault();
      if (msg) msg.textContent = "Memproses…";
      try {
        await window.RN_FRAPPE.call("rescue_net.api_logistics.assign_pickup_volunteer", {
          transport_space: form.transport_space.value.trim(),
          volunteer_profile: form.volunteer_profile.value.trim(),
        }, { method: "POST" });
        if (msg) msg.textContent = "Tersimpan.";
        form.reset();
        await load();
      } catch (err) {
        var m = (err && err.message) || String(err);
        if (msg) msg.textContent = "Gagal: " + m + (/login|permission|akses/i.test(m) ? " (perlu login)" : "");
      }
    });
  }

  /* ---------- load ---------- */
  async function load() {
    var data = await window.RN_FRAPPE.call(BOARD, { posko: getPosko(), disaster_event: getEvent() });
    data.can_manage_real = !!data.can_manage;
    data.booking_inbox_all = data.booking_inbox || [];
    if (data.can_manage_real && currentView() === "publik") {
      // pratinjau publik: perlakukan seperti pengguna biasa, jangan tampilkan kontak pembooking lain
      data.can_manage = false;
      data.booking_inbox = [];
    }
    CACHE = data;
    renderViewTabs(data);
    placeBookingSection(data);
    var t = String(data.generated_at || "").slice(11, 16);
    $("#pdUpdated").textContent = "Posko Distribusi · " + (t || "-");
    if (data.posko_info) {
      var _pi = data.posko_info;
      var _loc = mapsUrl(_pi.latitude, _pi.longitude, _pi.city_name);
      $("#pdStatus").innerHTML =
        "Posko: " + esc(_pi.title || data.posko) + " · PIC: " + esc(_pi.officer_in_charge_name || "-") +
        (_loc ? ' · <a href="' + _loc + '" target="_blank" rel="noopener">📍 Lokasi di peta ↗</a>' : "");
    } else {
      $("#pdStatus").textContent = "Belum ada posko dipilih.";
    }
    $("#pdTypeNote").textContent = data.posko && !data.is_transport_posko
      ? "Catatan: posko ini bukan bertipe ‘transport’ di registrasi posko — armada tetap bisa dikelola, tapi sebaiknya set Jenis Posko = Transport."
      : "";

    var badge = $("#pdModeBadge");
    if (badge && data.posko) {
      badge.hidden = false;
      badge.textContent = data.pickup_mode_label || (data.is_active_pickup ? "Jemput Aktif" : "Pasif");
      badge.className = "chip " + (data.is_active_pickup ? "ok" : "");
    } else if (badge) { badge.hidden = true; }

    var qSec = $("#pickupQueueSection"), pNote = $("#pdPassiveNote");
    if (data.posko && data.is_active_pickup) {
      if (qSec) qSec.hidden = false;
      if (pNote) pNote.hidden = true;
    } else {
      if (qSec) qSec.hidden = true;
      if (pNote) pNote.hidden = !data.posko;
    }

    renderSelector(data.transporter_poskos || [], data.posko || "", data.viewer);
    applyAccess(data);
    renderKpi(data.totals || {}, data.posko_info);
    ARMADA_ALL = data.armada || [];
    applyArmadaFilter();
    renderBookings(data.booking_inbox || []);
    var scanBtn = $("#pdScanBtn");     // kurir memindai label saat jemput / serah (owner 2026-10-25)
    if (scanBtn) {
      scanBtn.hidden = !data.can_manage;
      scanBtn.href = "scan.html?back=" + encodeURIComponent(location.pathname.split("/").pop() + location.search);
    }
    renderPickupQueue(data.pickup_queue || [], data.destination_options || []);
    renderRelawan(data.relawan_candidates || []);
  }

  /* Three levels: guest = read-only; operator of THIS posko (can_manage) =
     daftarkan/perbarui armada, konfirmasi booking, tugaskan relawan, klaim
     pickup; any logged-in user on an open transport posko (can_coordinate) =
     "Booking Tempat" on an armada. renderArmada/renderBookings/renderPickupQueue
     read CACHE.can_manage / CACHE.can_coordinate directly. */
  function applyAccess(data) {
    var manage = !!data.can_manage;

    var addBtn = $("#armadaAddBtn");
    if (addBtn) addBtn.hidden = !manage;
    var addForm = $("#armadaForm");
    if (addForm) addForm.hidden = !manage;

    // "Relawan Pickup" is operator tooling — hide the whole panel for
    // non-managers and let "Panduan" span the row.
    var relawanPanel = $("#pdRelawanPanel");
    if (relawanPanel) relawanPanel.hidden = !manage;
    var row2 = $("#pdRow2");
    if (row2) row2.classList.toggle("rn-md-row2--solo", !manage);

    // the pickup-queue claim columns only mean something to a manager
    document.querySelectorAll("#pickupQueueSection .pd-claim-col").forEach(function (th) {
      th.hidden = !manage;
    });

    var hint = $("#pdNoManage");
    if (hint && data.can_manage_real && !manage) {
      hint.hidden = false;
      hint.textContent = "Pratinjau tampilan publik / pembooking. Kembali ke \u201cMenu Pemilik\u201d untuk melihat booking masuk dan mengelola armada.";
    } else if (hint) {
      hint.hidden = manage || !data.posko;
      hint.textContent = data.can_coordinate
        ? "Anda bukan pengelola posko ini — Anda bisa booking tempat ruang muat pada armada (buka detail armada), tapi tidak mengelola armada / booking."
        : (data.logged_in
          ? "Anda bisa booking tempat ruang muat: klik armada lalu isi booking di detailnya. Mengelola armada & booking masuk hanya untuk pengelola posko ini."
          : data.session_user_logged_in
          ? "Lengkapi pendaftaran Rescue-Net untuk booking tempat."
          : "Mode lihat. Login untuk booking tempat ruang muat (sebagai posko pengantar atau warga) atau untuk mengelola armada & booking.");
    }
  }

  function renderPickupQueue(list, dests) {
    var body = $("#pickupQueueBody"), shown = $("#pickupQueueShown");
    if (!body) return;
    var canManage = !!(CACHE && CACHE.can_manage);
    var cols = canManage ? 7 : 5;
    if (!list.length) {
      body.innerHTML = '<tr><td colspan="' + cols + '"><em class="rn-muted">Tidak ada bantuan yang menunggu dijemput saat ini.</em></td></tr>';
      if (shown) shown.textContent = "0 antre";
      return;
    }
    var destOpts = (dests || []).map(function (d) {
      return '<option value="' + esc(d.id) + '">' + esc(d.title) + (d.city ? " — " + esc(d.city) : "") + "</option>";
    }).join("");
    // this transport posko's own armada (for claiming an outgoing flow)
    var armadaOpts = ((CACHE && CACHE.armada) || []).filter(function (a) {
      return (a.status || "") !== "completed" && (a.status || "") !== "cancelled";
    }).map(function (a) {
      return '<option value="' + esc(a.id) + '">' + esc(a.provider) + " · " + esc(a.jenis) +
        " · sisa " + fmt(a.kapasitas_tersedia_kg) + " kg</option>";
    }).join("");

    body.innerHTML = list.map(function (r) {
      var key = esc(r.aid_offer);
      var isFlow = r.kind === "flow";
      var claimCells = "";
      if (canManage) {
        if (isFlow) {
          // destination already chosen by the collector posko — assign one of
          // OUR armada. api_logistics.claim_distribution_flow.
          claimCells =
            '<td><select class="rn-pd-arm" data-flow="' + key + '">' +
              '<option value="">— pilih armada —</option>' + armadaOpts + "</select>" +
              (r.first_leg ? '<input class="rn-pd-kg" data-flow="' + key + '" type="number" step="0.1" min="0" placeholder="berat muatan (kg)">' : "") + "</td>" +
            '<td><button type="button" class="btn primary mini rn-pd-claimflow" data-flow="' + key + '">Booking</button>' +
            '<span class="rn-pd-bk-msg" data-msg="' + key + '"></span></td>';
        } else {
          claimCells =
            '<td><select class="rn-pd-dest" data-offer="' + key + '">' +
              '<option value="">— pilih posko —</option>' + destOpts + "</select></td>" +
            '<td><button type="button" class="btn primary mini rn-pd-claim" data-offer="' + key + '">Ambil &amp; Antar</button>' +
            '<span class="rn-pd-bk-msg" data-msg="' + key + '"></span></td>';
        }
      }
      return (
        "<tr>" +
        '<td><b>' + esc(r.item) + '</b><small class="rn-muted">' +
          (r.first_leg
            ? "jemput ke titik serah " + esc((r.handover_to && r.handover_to.provider_name) || "armada utama") +
              (r.handover_to && r.handover_to.handover_location ? " (" + esc(r.handover_to.handover_location) + ")" : "")
            : (isFlow ? "alur distribusi" : esc(r.aid_offer))) + "</small></td>" +
        "<td>" + fmt(r.quantity) + " " + esc(r.unit) + "</td>" +
        "<td>" + esc(r.donor) + (r.donor_contact ? "<small class=\"rn-muted\">" + tel(r.donor_contact) + "</small>" : "") + "</td>" +
        "<td>" + esc(r.pickup_location) + "</td>" +
        "<td>" + esc(r.ready_at) + "</td>" +
        claimCells +
        "</tr>"
      );
    }).join("");

    // prefill suggested destination (aid-offer rows only)
    list.forEach(function (r) {
      if (r.kind !== "flow" && r.suggested_destination) {
        var s = body.querySelector('.rn-pd-dest[data-offer="' + CSS.escape(r.aid_offer) + '"]');
        if (s && [].some.call(s.options, function (o) { return o.value === r.suggested_destination; })) {
          s.value = r.suggested_destination;
        }
      }
    });

    body.querySelectorAll(".rn-pd-claim").forEach(function (btn) {
      btn.addEventListener("click", async function () {
        var offer = btn.getAttribute("data-offer");
        var sel = body.querySelector('.rn-pd-dest[data-offer="' + CSS.escape(offer) + '"]');
        var msg = body.querySelector('[data-msg="' + CSS.escape(offer) + '"]');
        var dest = sel && sel.value;
        if (!dest) { if (msg) msg.textContent = " pilih posko tujuan dulu"; return; }
        if (msg) msg.textContent = " memproses…";
        try {
          await window.RN_FRAPPE.call("rescue_net.api_logistics.claim_aid_pickup",
            { transporter_posko: getPosko(), aid_offer: offer, destination_posko: dest },
            { method: "POST" });
          if (msg) msg.textContent = " diambil ✓";
          await load();
        } catch (err) {
          var m = (err && err.message) || String(err);
          if (msg) msg.textContent = " gagal: " + m + (/login|permission|akses/i.test(m) ? " (perlu login)" : "");
        }
      });
    });

    body.querySelectorAll(".rn-pd-claimflow").forEach(function (btn) {
      btn.addEventListener("click", async function () {
        var flow = btn.getAttribute("data-flow");
        var sel = body.querySelector('.rn-pd-arm[data-flow="' + CSS.escape(flow) + '"]');
        var msg = body.querySelector('[data-msg="' + CSS.escape(flow) + '"]');
        var arm = sel && sel.value;
        var kgIn = body.querySelector('.rn-pd-kg[data-flow="' + CSS.escape(flow) + '"]');
        if (!arm) { if (msg) msg.textContent = " pilih armada dulu"; return; }
        if (msg) msg.textContent = " memproses…";
        try {
          await window.RN_FRAPPE.call("rescue_net.api_logistics.claim_distribution_flow",
            { flow: flow, transport_space: arm, weight_kg: kgIn && kgIn.value ? Number(kgIn.value) : undefined }, { method: "POST" });
          if (msg) msg.textContent = " dibooking ✓";
          await load();
        } catch (err) {
          var m = (err && err.message) || String(err);
          if (msg) msg.textContent = " gagal: " + m + (/login|permission|akses/i.test(m) ? " (perlu login)" : "");
        }
      });
    });
    if (shown) shown.textContent = "Menampilkan " + list.length + " bantuan menunggu jemput";
  }

  // KPI -> bagian yang menjelaskan angkanya (sebelumnya tombol tanpa aksi).
  var KPI_TARGET = { armada: "#armadaBody", kapasitas: "#armadaBody", terpakai: "#armadaBody", menunggu: "#bookingBody" };
  function wireKpiLinks() {
    document.querySelectorAll(".rn-pd-kpi .rn-kpi-btn[data-kpi]").forEach(function (btn) {
      var target = KPI_TARGET[btn.getAttribute("data-kpi")];
      if (!target) return;
      btn.addEventListener("click", function () {
        var el = $(target);
        if (el) (el.closest(".panel") || el).scrollIntoView({ behavior: "smooth", block: "start" });
      });
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    if (!window.RN_FRAPPE) { console.error("RN_FRAPPE unavailable"); return; }
    document.querySelectorAll("#pdDrill [data-close]").forEach(function (el) { el.addEventListener("click", closeDrill); });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape") closeDrill(); });

    var addBtn = $("#armadaAddBtn"), addForm = $("#armadaForm");
    if (addBtn && addForm) {
      addBtn.addEventListener("click", function () {
        addForm.open = true;
        addForm.scrollIntoView({ behavior: "smooth", block: "center" });
        var fp = addForm.querySelector('input[name="provider_name"]');
        if (fp) setTimeout(function () { fp.focus(); }, 300);
      });
    }
    wireArmadaForm();
    wireAssignForm();
    wireGuestTrack();
    wireKpiLinks();
    load().catch(function (err) {
      console.error("[posko distribusi]", err);
      $("#pdStatus").textContent = "Gagal memuat: " + (err && err.message || err);
    });
  });
})();
