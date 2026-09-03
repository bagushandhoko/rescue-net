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

  /* ---------- selector ---------- */
  function renderSelector(list, current) {
    var sel = $("#poskoSelect");
    if (!sel) return;
    var opts = (list || []).map(function (p) {
      return '<option value="' + esc(p.id) + '"' + (p.id === current ? " selected" : "") + ">" +
        esc(p.title) + (p.city ? " — " + esc(p.city) : "") + "</option>";
    }).join("");
    if (!current || !(list || []).some(function (p) { return p.id === current; })) {
      opts = '<option value="">— pilih posko distribusi —</option>' + opts;
    }
    sel.innerHTML = opts;
    sel.onchange = function () {
      qs.set("id", sel.value);
      qs.set("event", getEvent());
      location.search = qs.toString();
    };
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
      '<h4 class="rn-md-detail-h">Booking masuk</h4><div class="rn-md-bk-list">' + bkHtml + "</div>";
    $("#pdDrill").hidden = false;
    document.body.style.overflow = "hidden";
  }
  function closeDrill() { $("#pdDrill").hidden = true; document.body.style.overflow = ""; }

  /* ---------- booking inbox ---------- */
  function renderBookings(list) {
    var body = $("#bookingBody");
    if (!list || !list.length) {
      body.innerHTML = '<tr><td colspan="7"><em class="rn-muted">Belum ada booking masuk.</em></td></tr>';
      return;
    }
    body.innerHTML = list.map(function (b) {
      var act = "";
      if (b.status === "requested") {
        act =
          '<div class="rn-pd-bk-act" data-booking="' + esc(b.id) + '">' +
          '<input class="rn-pd-pin" placeholder="PIN" maxlength="8">' +
          '<button type="button" class="btn primary mini" data-do="confirm">Konfirmasi</button>' +
          '<button type="button" class="btn mini" data-do="reject">Tolak</button>' +
          '<span class="rn-pd-bk-msg"></span></div>';
      } else {
        act = '<span class="rn-muted">' + esc(b.id) + "</span>";
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

    renderSelector(data.transporter_poskos || [], data.posko || "");
    renderKpi(data.totals || {}, data.posko_info);
    renderArmada(data.armada || []);
    renderBookings(data.booking_inbox || []);
    renderPickupQueue(data.pickup_queue || [], data.destination_options || []);
    renderRelawan(data.relawan_candidates || []);
  }

  function renderPickupQueue(list, dests) {
    var body = $("#pickupQueueBody"), shown = $("#pickupQueueShown");
    if (!body) return;
    if (!list.length) {
      body.innerHTML = '<tr><td colspan="7"><em class="rn-muted">Tidak ada bantuan yang menunggu dijemput saat ini.</em></td></tr>';
      if (shown) shown.textContent = "0 antre";
      return;
    }
    var opts = (dests || []).map(function (d) {
      return '<option value="' + esc(d.id) + '">' + esc(d.title) + (d.city ? " — " + esc(d.city) : "") + "</option>";
    }).join("");
    body.innerHTML = list.map(function (r) {
      var sel = '<select class="rn-pd-dest" data-offer="' + esc(r.aid_offer) + '">' +
        '<option value="">— pilih posko —</option>' + opts + "</select>";
      return (
        "<tr>" +
        "<td><b>" + esc(r.item) + "</b><small class=\"rn-muted\">" + esc(r.aid_offer) + "</small></td>" +
        "<td>" + fmt(r.quantity) + " " + esc(r.unit) + "</td>" +
        "<td>" + esc(r.donor) + (r.donor_contact ? "<small class=\"rn-muted\">" + tel(r.donor_contact) + "</small>" : "") + "</td>" +
        "<td>" + esc(r.pickup_location) + "</td>" +
        "<td>" + esc(r.ready_at) + "</td>" +
        "<td>" + sel + "</td>" +
        '<td><button type="button" class="btn primary mini rn-pd-claim" data-offer="' + esc(r.aid_offer) + '">Ambil &amp; Antar</button>' +
        '<span class="rn-pd-bk-msg" data-msg="' + esc(r.aid_offer) + '"></span></td>' +
        "</tr>"
      );
    }).join("");
    // prefill suggested destination
    list.forEach(function (r) {
      if (r.suggested_destination) {
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
