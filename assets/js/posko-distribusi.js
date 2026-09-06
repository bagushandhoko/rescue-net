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
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function fmt(n) { return Number(n || 0).toLocaleString("id-ID"); }
  var qs = new URLSearchParams(location.search);
  function getEvent() { return qs.get("event") || "event-sim-001"; }
  function getPosko() { return qs.get("id") || qs.get("posko") || ""; }
  function tel(v) { return v && v !== "-" ? '<a href="tel:' + esc(String(v).replace(/[^0-9+]/g, "")) + '">' + esc(v) + "</a>" : "-"; }
  function statusChip(s) {
    var l = String(s || "").toLowerCase();
    if (l === "confirmed" || l === "available" || l === "arrived") return "ok";
    if (l === "requested" || l === "in_transit" || l === "reserved" || l === "assigned") return "warning";
    if (l === "rejected" || l === "cancelled") return "danger";
    return "";
  }

  var MODE_CHIP = { space_only: "", courier_pickup: "warning", both: "ok" };

  var ARMADA_STATUS = [
    ["available", "Tersedia"], ["reserved", "Dipesan"], ["assigned", "Ditugaskan"],
    ["in_transit", "Dalam Perjalanan"], ["arrived", "Tiba"],
    ["completed", "Selesai"], ["cancelled", "Dibatalkan"],
  ];
  var SERVICE_MODE = [
    ["space_only", "Penyedia Space"], ["courier_pickup", "Kurir Jemput-Antar"],
    ["both", "Space + Kurir"],
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
  }

  /* ---------- armada table ---------- */
  function capMeter(a) {
    var pct = Math.min(100, Math.max(0, a.kapasitas_pct || 0));
    var cls = pct >= 90 ? "bad" : (pct >= 60 ? "warn" : "ok");
    return (
      '<div class="rn-md-cap"><div class="rn-md-cap-bar"><i class="' + cls + '" style="width:' + pct + '%"></i></div>' +
      "<small>Tersedia " + fmt(a.kapasitas_tersedia_kg) + " kg" +
      (a.kapasitas_total_m3 ? " · " + fmt(a.kapasitas_tersedia_m3) + " m³" : "") + "</small></div>"
    );
  }

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
        '<td><span class="chip ' + statusChip(a.status) + '">' + esc(a.status_label) + "</span></td>" +
        "<td>" + (a.bookings_count ? '<span class="chip">' + fmt(a.bookings_count) + "</span>" : '<span class="rn-muted">0</span>') + "</td>" +
        "</tr>"
      );
    }).join("");
    body.querySelectorAll("tr.rn-ba-row").forEach(function (tr) {
      tr.addEventListener("click", function () { openArmadaDetail(tr.getAttribute("data-armada")); });
    });
    if (shown) shown.textContent = "Menampilkan " + list.length + " armada";
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
        '<div class="rn-md-bk-contacts"><span>Pemesan: <b>' + esc(b.booker) + "</b>" +
        (b.supplier_contact_person ? " (" + esc(b.supplier_contact_person) + ")" : "") +
        (b.supplier_contact_phone ? " · " + tel(b.supplier_contact_phone) : "") + "</span></div>" +
        '<div class="rn-md-bk-meta"><span class="chip ' + statusChip(b.status) + '">' + esc(b.status_label) + "</span>" +
        (b.verification_pin ? '<code class="rn-md-bk-id">PIN ' + esc(b.verification_pin) + "</code>" : "") + "</div></div>"
      );
    }).join("") : '<p class="rn-muted">Belum ada booking pada armada ini.</p>';
    $("#pdDrillTitle").textContent = a.provider;
    $("#pdDrillSub").textContent = a.service_mode_label + " · " + a.status_label;
    $("#pdDrillBody").innerHTML =
      '<div class="rn-md-detail">' +
      row("Jenis", esc(a.jenis)) +
      row("Kebijakan booking", a.booking_policy === "open" ? "Langsung terkonfirmasi" : "Konfirmasi PIN posko") +
      row("Kapasitas total", fmt(a.kapasitas_total_kg) + " kg" + (a.kapasitas_total_m3 ? " · " + fmt(a.kapasitas_total_m3) + " m³" : "")) +
      row("Sisa kapasitas", fmt(a.kapasitas_tersedia_kg) + " kg" + (a.kapasitas_total_m3 ? " · " + fmt(a.kapasitas_tersedia_m3) + " m³" : "")) +
      row("Jadwal", esc(a.berangkat) + " → " + esc(a.eta)) +
      row("Lokasi saat ini", esc(a.current_location)) +
      row("Rute", esc(a.rute)) +
      row("Titik serah terima", esc(a.handover_location)) +
      row("Narahubung", esc(a.handover_contact_person) + (a.handover_contact_phone && a.handover_contact_phone !== "-" ? " · " + tel(a.handover_contact_phone) : "")) +
      row("Relawan pickup", esc(a.pickup_volunteer_name || "-")) +
      "</div>" +
      ((CACHE && CACHE.can_manage) ? armadaEditForm(a) : "") +
      ((CACHE && CACHE.can_coordinate) ? bookingForm(a) : "") +
      '<h4 class="rn-md-detail-h">Booking masuk</h4><div class="rn-md-bk-list">' + bkHtml + "</div>";
    if (CACHE && CACHE.can_manage) wireArmadaEdit(a.id);
    if (CACHE && CACHE.can_coordinate) wireBookingForm(a);
    $("#pdDrill").hidden = false;
    document.body.style.overflow = "hidden";
  }

  /* "Pesan Slot" — any logged-in user, on an open transport posko.
     api_logistics.book_transport_space (PIN back unless policy = open). */
  function bookingForm(a) {
    var courierOk = (a.service_mode || "both") !== "space_only";
    return (
      '<details class="rn-pd-edit" open><summary>Pesan slot pada armada ini</summary>' +
      '<form class="rn-form" id="pdBookForm">' +
      '<div class="form-grid">' +
      '<label>Muatan<input name="cargo_desc" placeholder="Beras 40 karung / Air mineral" required></label>' +
      '<label>Berat (kg)<input name="qty_weight_kg" type="number" step="0.01" placeholder="500"></label>' +
      '<label>Volume (m³)<input name="qty_volume_m3" type="number" step="0.01" placeholder="2"></label>' +
      '<label>Cara antar<select name="delivery_method">' +
        (courierOk ? '<option value="use_transporter">Dijemput kurir armada</option>' : "") +
        '<option value="self_deliver">Antar sendiri ke titik jemput</option></select></label>' +
      '<label>Lokasi barang<input name="pickup_location" placeholder="Gudang / alamat"></label>' +
      '<label>Tujuan / dropoff<input name="dropoff_location" placeholder="Posko tujuan"></label>' +
      '<label>Kontak Anda<input name="contact_person" placeholder="Nama"></label>' +
      '<label>No. HP<input name="contact_phone" placeholder="0812-…"></label>' +
      '<label>Perkiraan waktu<input name="requested_window" placeholder="Besok pagi"></label>' +
      "</div>" +
      '<div class="form-actions"><button class="btn primary" type="submit">Pesan Slot</button>' +
      '<span class="rn-pd-bk-msg" data-book-msg></span></div>' +
      "</form></details>"
    );
  }

  function wireBookingForm(a) {
    var form = $("#pdBookForm");
    if (!form) return;
    var msg = form.querySelector("[data-book-msg]");
    form.addEventListener("submit", async function (e) {
      e.preventDefault();
      var v = function (n) { return form[n] ? String(form[n].value).trim() : ""; };
      if (msg) msg.textContent = " memesan…";
      try {
        var r = await window.RN_FRAPPE.call("rescue_net.api_logistics.book_transport_space", {
          transport_space: a.id,
          cargo_desc: v("cargo_desc"),
          qty_weight_kg: Number(form.qty_weight_kg.value || 0),
          qty_volume_m3: Number(form.qty_volume_m3.value || 0),
          delivery_method: v("delivery_method") || "self_deliver",
          pickup_location: v("pickup_location"),
          dropoff_location: v("dropoff_location"),
          contact_person: v("contact_person"),
          contact_phone: v("contact_phone"),
          requested_window: v("requested_window"),
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

  function armadaEditForm(a) {
    return (
      '<details class="rn-pd-edit"><summary>Perbarui armada</summary>' +
      '<form class="rn-form" id="pdArmadaEditForm">' +
      '<div class="form-grid">' +
      '<label>Status<select name="transport_status">' + optionList(ARMADA_STATUS, a.status) + "</select></label>" +
      '<label>Mode layanan<select name="service_mode">' + optionList(SERVICE_MODE, a.service_mode) + "</select></label>" +
      '<label>Kebijakan booking<select name="booking_policy">' + optionList(BOOKING_POLICY, a.booking_policy) + "</select></label>" +
      '<label>Lokasi saat ini<input name="current_location" value="' + esc(clean(a.current_location)) + '"></label>' +
      '<label>Jam berangkat<input type="datetime-local" name="departure_at" value="' + esc(toLocalDT(a.berangkat)) + '"></label>' +
      '<label>ETA<input type="datetime-local" name="eta_at" value="' + esc(toLocalDT(a.eta)) + '"></label>' +
      '<label>Titik serah terima<input name="handover_location" value="' + esc(clean(a.handover_location)) + '"></label>' +
      '<label>Narahubung<input name="handover_contact_person" value="' + esc(clean(a.handover_contact_person)) + '"></label>' +
      '<label>No. kontak serah terima<input name="handover_contact_phone" value="' + esc(clean(a.handover_contact_phone)) + '"></label>' +
      "</div>" +
      '<label>Catatan koordinasi<textarea name="coordination_notes" rows="2">' + esc(clean(a.coordination_notes)) + "</textarea></label>" +
      '<div class="form-actions"><button class="btn primary" type="submit">Simpan Perubahan</button>' +
      '<span class="rn-pd-bk-msg" data-armada-edit-msg></span></div>' +
      "</form></details>"
    );
  }

  function wireArmadaEdit(id) {
    var form = $("#pdArmadaEditForm");
    if (!form) return;
    var msg = form.querySelector("[data-armada-edit-msg]");
    form.addEventListener("submit", async function (e) {
      e.preventDefault();
      var v = function (n) { return form[n] ? String(form[n].value).trim() : ""; };
      var payload = {
        transport_space: id,
        transport_status: v("transport_status"),
        service_mode: v("service_mode"),
        booking_policy: v("booking_policy"),
        current_location: v("current_location"),
        handover_location: v("handover_location"),
        handover_contact_person: v("handover_contact_person"),
        handover_contact_phone: v("handover_contact_phone"),
        coordination_notes: v("coordination_notes"),
      };
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
  function renderBookings(list) {
    var body = $("#bookingBody");
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
          '<input class="rn-pd-pin" placeholder="PIN" maxlength="8">' +
          '<button type="button" class="btn primary mini" data-do="confirm">Konfirmasi</button>' +
          '<button type="button" class="btn mini" data-do="reject">Tolak</button>' +
          '<span class="rn-pd-bk-msg"></span></div>';
      }
      return (
        "<tr><td><b>" + esc(b.cargo) + "</b><small class=\"rn-muted\">" + esc(b.armada) + "</small></td>" +
        "<td>" + fmt(b.qty_kg) + " kg" + (b.qty_m3 ? " · " + fmt(b.qty_m3) + " m³" : "") + "</td>" +
        "<td>" + esc(b.delivery_label) + "</td>" +
        "<td>" + esc(b.booker) + (b.supplier_contact_person ? " (" + esc(b.supplier_contact_person) + ")" : "") +
          "<small class=\"rn-muted\">" + tel(b.supplier_contact_phone) + "</small></td>" +
        "<td>" + esc(b.requested_window || b.requested_at || "-") + "</td>" +
        '<td><span class="chip ' + statusChip(b.status) + '">' + esc(b.status_label) + "</span></td>" +
        "<td>" + act + "</td></tr>"
      );
    }).join("");

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
                { booking: id, pin: pin.value.trim() }, { method: "POST" });
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
  function wireArmadaForm() {
    var form = $("[data-create-armada]"), msg = $("[data-armada-message]");
    if (!form) return;
    form.addEventListener("submit", async function (e) {
      e.preventDefault();
      var f = function (n) { return form[n] && form[n].value ? String(form[n].value).trim() : ""; };
      var posko = getPosko();
      if (!posko) { if (msg) msg.textContent = "Pilih posko distribusi dulu."; return; }
      if (msg) msg.textContent = "Menyimpan…";
      try {
        await window.RN_FRAPPE.call("rescue_net.api_logistics.create_transport_space", {
          coordination_posko: posko,
          disaster_event: f("disaster_event") || getEvent(),
          provider_name: f("provider_name"),
          transport_type: f("transport_type"),
          service_mode: f("service_mode"),
          booking_policy: f("booking_policy"),
          route_origin: f("route_origin"),
          route_destination: f("route_destination"),
          capacity_weight_kg: Number(form.capacity_weight_kg.value || 0),
          capacity_volume_m3: Number(form.capacity_volume_m3.value || 0),
          departure_at: f("departure_at").replace("T", " "),
          eta_at: f("eta_at").replace("T", " "),
          current_location: f("current_location"),
          handover_location: f("handover_location"),
          handover_contact_person: f("handover_contact_person"),
          handover_contact_phone: f("handover_contact_phone"),
          coordination_notes: f("coordination_notes"),
        }, { method: "POST" });
        if (msg) msg.textContent = "Armada tersimpan.";
        form.reset();
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
    CACHE = data;
    var t = String(data.generated_at || "").slice(11, 16);
    $("#pdUpdated").textContent = "Posko Distribusi · " + (t || "-");
    $("#pdStatus").textContent = data.posko_info
      ? "Posko: " + (data.posko_info.title || data.posko) + " · PIC: " + (data.posko_info.officer_in_charge_name || "-")
      : "Belum ada posko dipilih.";
    $("#pdTypeNote").textContent = data.posko && !data.is_transport_posko
      ? "Catatan: posko ini bukan bertipe ‘transport’ di registrasi posko — armada tetap bisa dikelola, tapi sebaiknya set Jenis Posko = Transport."
      : "";

    var badge = $("#pdModeBadge");
    if (badge && data.posko) {
      badge.hidden = false;
      badge.textContent = data.pickup_mode_label || (data.is_active_pickup ? "Pickup Aktif" : "Pasif");
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
    renderArmada(data.armada || []);
    renderBookings(data.booking_inbox || []);
    renderPickupQueue(data.pickup_queue || [], data.destination_options || []);
    renderRelawan(data.relawan_candidates || []);
  }

  /* Three levels: guest = read-only; operator of THIS posko (can_manage) =
     daftarkan/perbarui armada, konfirmasi booking, tugaskan relawan, klaim
     pickup; any logged-in user on an open transport posko (can_coordinate) =
     "Pesan Slot" on an armada. renderArmada/renderBookings/renderPickupQueue
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
    if (hint) {
      hint.hidden = manage || !data.posko;
      hint.textContent = data.can_coordinate
        ? "Anda bukan pengelola posko ini — Anda bisa memesan slot pada armada, tapi tidak mengelola armada / booking."
        : "Mode lihat. Login sebagai petugas / anggota posko ini untuk mengelola armada & booking.";
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
              '<option value="">— pilih armada —</option>' + armadaOpts + "</select></td>" +
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
          (isFlow ? "alur distribusi" : esc(r.aid_offer)) + "</small></td>" +
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
        if (!arm) { if (msg) msg.textContent = " pilih armada dulu"; return; }
        if (msg) msg.textContent = " memproses…";
        try {
          await window.RN_FRAPPE.call("rescue_net.api_logistics.claim_distribution_flow",
            { flow: flow, transport_space: arm }, { method: "POST" });
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
    load().catch(function (err) {
      console.error("[posko distribusi]", err);
      $("#pdStatus").textContent = "Gagal memuat: " + (err && err.message || err);
    });
  });
})();
