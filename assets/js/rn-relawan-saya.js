/* Relawan Saya (owner 2026-10-26): guests go straight to registration; a
   logged-in volunteer ticks the disasters they help, books an armada seat
   (posko distribusi) or a bed (posko shelter); posko managers confirm.
   Backend: rescue_net.api_volunteer_booking. */
(function () {
  "use strict";
  var $ = function (id) { return document.getElementById(id); };
  var esc = function (s) { return window.RNUI ? window.RNUI.esc(s) : String(s == null ? "" : s); };
  var API = "rescue_net.api_volunteer_booking.";
  var call = function (m, a, post) { return window.RN_FRAPPE.call(API + m, a || {}, post ? { method: "POST" } : undefined); };
  var STATUS = { requested: ["Menunggu posko", "warning"], confirmed: ["Disetujui", "good"], rejected: ["Ditolak", "danger"], cancelled: ["Dibatalkan", "neutral"] };
  var chip = function (st) { var x = STATUS[st] || [st, "neutral"]; return '<span class="chip ' + x[1] + '">' + esc(x[0]) + "</span>"; };
  var msg = function (t, bad) { var m = $("rsMsg"); if (m) { m.textContent = t || ""; m.style.color = bad ? "#c0392b" : ""; } };

  function guestButton() {
    // a guest goes to the account registration with the Relawan role picked
    var old = $("openRegisterBtn");
    if (!old) return;
    var a = document.createElement("a");
    a.className = old.className; a.id = "openRegisterBtn";
    a.textContent = "+ Daftar sebagai Relawan";
    a.href = "auth.html?next=" + encodeURIComponent("management-relawan.html") + "#daftar-relawan";
    old.replaceWith(a);
  }

  function memberButton() {
    var old = $("openRegisterBtn");
    if (!old) return;
    var b = old.cloneNode(true);                  // drop the anonymous-form listener
    b.textContent = "Tawarkan diri untuk bencana";
    b.addEventListener("click", function () { $("rsPanel").scrollIntoView({ behavior: "smooth", block: "start" }); });
    old.replaceWith(b);
  }

  function renderOptions(evId, title, opt) {
    var arm = (opt.armada || []).map(function (a) {
      return '<div class="rs-opt"><div><b>🚚 ' + esc(a.title) + "</b><br><small>" + esc(a.posko_title || "") +
        (a.departure_at ? " · berangkat " + esc(a.departure_at) : "") + (a.pickup ? " · jemput: " + esc(a.pickup) : "") +
        " · sisa " + a.seats_left + "/" + a.seats + " kursi</small></div>" +
        '<button class="btn mini" type="button" data-book="transport" data-target="' + esc(a.id) + '" data-ev="' + esc(evId) + '"' +
        (a.seats_left > 0 ? "" : " disabled") + ">Pesan kursi</button></div>";
    }).join("");
    var ako = (opt.akomodasi || []).map(function (a) {
      return '<div class="rs-opt"><div><b>🏠 ' + esc(a.title) + "</b><br><small>" + esc(a.posko_title || "") +
        (a.safety ? " · " + esc(a.safety) : "") + " · sisa " + a.beds_left + "/" + a.beds + " tempat tidur</small></div>" +
        '<button class="btn mini" type="button" data-book="akomodasi" data-target="' + esc(a.id) + '" data-ev="' + esc(evId) + '"' +
        (a.beds_left > 0 ? "" : " disabled") + ">Pesan tempat</button></div>";
    }).join("");
    return '<div class="rs-ev-opts"><h4 style="margin:12px 0 6px">' + esc(title) + "</h4>" +
      (arm || ako ? arm + ako : '<p class="rn-muted">Belum ada armada dengan kursi relawan atau tempat menginap untuk bencana ini.</p>') + "</div>";
  }

  async function loadMine() {
    var r = await call("my_volunteer");
    var offered = new Set(r.offered || []);
    $("rsEvents").innerHTML = (r.events || []).map(function (e) {
      return '<label class="rs-ev"><input type="checkbox" name="ev" value="' + esc(e.id) + '"' + (offered.has(e.id) ? " checked" : "") + "> " + esc(e.title) + "</label>";
    }).join("") || '<p class="rn-muted">Belum ada bencana aktif.</p>';
    $("rsFirst").hidden = (r.profiles || []).length > 0;
    var titles = {}; (r.events || []).forEach(function (e) { titles[e.id] = e.title; });
    var blocks = [];
    for (var i = 0; i < (r.offered || []).length; i++) {
      var ev = r.offered[i];
      try { blocks.push(renderOptions(ev, titles[ev] || ev, await call("booking_options", { disaster_event: ev }))); } catch (e) {}
    }
    $("rsOptions").innerHTML = blocks.join("");
    $("rsBookings").innerHTML = (r.bookings || []).length ? r.bookings.map(function (b) {
      return '<div class="rs-opt"><div><b>' + (b.booking_kind === "transport" ? "🚚 " : "🏠 ") + esc(b.target_title || "-") + "</b> " + chip(b.status) +
        "<br><small>" + esc(b.posko_title || "") + (b.date_from ? " · " + esc(b.date_from) + (b.date_to ? " s/d " + esc(b.date_to) : "") : "") +
        (b.decision_note ? " · catatan posko: " + esc(b.decision_note) : "") + "</small></div>" +
        (b.status === "requested" || b.status === "confirmed" ? '<button class="btn ghost mini" type="button" data-cancel="' + esc(b.name) + '">Batalkan</button>' : "") + "</div>";
    }).join("") : '<p class="rn-muted">Belum ada booking.</p>';
  }

  async function loadPosko() {
    try {
      var r = await call("posko_bookings");
      var rows = r.bookings || [];
      $("rsPoskoPanel").hidden = !rows.length;
      $("rsPoskoList").innerHTML = rows.map(function (b) {
        return '<div class="rs-opt"><div><b>' + esc(b.volunteer_name || b.volunteer) + "</b> · " + esc(b.main_skill || "") + " " + chip(b.status) +
          "<br><small>" + (b.booking_kind === "transport" ? "Kursi armada " : "Tempat menginap ") + esc(b.target_title || "") +
          (b.date_from ? " · " + esc(b.date_from) + (b.date_to ? " s/d " + esc(b.date_to) : "") : "") +
          (b.pickup_location ? " · jemput: " + esc(b.pickup_location) : "") + (b.contact ? " · " + esc(b.contact) : "") +
          (b.note ? "<br>" + esc(b.note) : "") + "</small></div>" +
          (b.status === "requested" ? '<div><button class="btn primary mini" data-decide="confirm" data-id="' + esc(b.name) + '">Setujui</button> ' +
            '<button class="btn ghost mini" data-decide="reject" data-id="' + esc(b.name) + '">Tolak</button></div>' : "") + "</div>";
      }).join("");
    } catch (e) { $("rsPoskoPanel").hidden = true; }
  }

  document.addEventListener("DOMContentLoaded", async function () {
    if (!$("rsPanel")) return;
    var sess = null;
    try { sess = await window.RN_FRAPPE.call("rescue_net.api_auth.session_info"); } catch (e) {}
    if (!sess || !sess.user || sess.user === "Guest") { guestButton(); return; }
    memberButton();
    $("rsPanel").hidden = false;
    $("rsOfferForm").addEventListener("submit", async function (e) {
      e.preventDefault();
      var f = e.target, evs = Array.prototype.map.call(f.querySelectorAll('input[name="ev"]:checked'), function (x) { return x.value; });
      msg("Menyimpan…");
      try {
        await call("offer_events", { events: JSON.stringify(evs), contact: f.contact.value || undefined,
          main_skill: f.main_skill.value || undefined, current_location: f.current_location.value || undefined }, true);
        msg("Tersimpan. Anda terdaftar sebagai relawan untuk " + evs.length + " bencana.");
        await loadMine();
      } catch (err) { msg((err && err.message) || err, true); }
    });
    document.addEventListener("click", async function (e) {
      var bk = e.target.closest("[data-book]"), cn = e.target.closest("[data-cancel]"), dc = e.target.closest("[data-decide]");
      if (!bk && !cn && !dc) return;
      e.preventDefault();
      try {
        if (bk) {
          var note = window.prompt ? (window.prompt("Catatan untuk posko (opsional, mis. tanggal tiba / lokasi jemput):") || "") : "";
          await call("book", { kind: bk.dataset.book, target: bk.dataset.target, disaster_event: bk.dataset.ev, note: note }, true);
          msg("Booking terkirim. Menunggu persetujuan posko.");
        } else if (cn) {
          await call("cancel_booking", { booking: cn.dataset.cancel }, true);
        } else {
          await call("decide_booking", { booking: dc.dataset.id, action: dc.dataset.decide }, true);
        }
        await loadMine(); await loadPosko();
      } catch (err) { msg((err && err.message) || err, true); }
    });
    try { await loadMine(); } catch (e) { msg((e && e.message) || e, true); }
    loadPosko();
  });
})();
