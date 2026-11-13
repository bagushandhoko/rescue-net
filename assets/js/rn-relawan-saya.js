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
  var msg = function (t, bad) { var m = $("rsMsg"); if (m) { m.textContent = t || ""; m.style.color = bad ? "#c0392b" : ""; } else if (bad && t) { window.alert(t); } };

  function guestButton() {
    // a guest goes to the account registration with the Relawan role picked
    var old = $("openRegisterBtn");
    if (!old) return;
    var a = document.createElement("a");
    a.className = old.className; a.id = "openRegisterBtn";
    a.textContent = "+ Daftar sebagai Relawan";
    a.href = "auth.html?next=" + encodeURIComponent("management-relawan.html#saya") + "#daftar-relawan";
    old.replaceWith(a);
  }

  // owner 2026-11-13: Relawan Saya digabung ke Posko Relawan -> panel "Pengaturan Relawan" (#saya)
  function openSelf(scroll) {
    var box = $("saya");
    if (!box) return;
    box.hidden = false;
    try { if (location.hash !== "#saya") history.replaceState(null, "", location.pathname + location.search + "#saya"); } catch (e) {}
    if (scroll) box.scrollIntoView({ behavior: "smooth", block: "start" });
  }
  function memberButton() {
    // akun terdaftar yang belum relawan: tombol membuka panel di langkah 1 (centang bencana = jadi relawan)
    var old = $("openRegisterBtn");
    if (!old) return;
    var b = document.createElement("button");
    b.type = "button"; b.className = old.className; b.id = "openRegisterBtn";
    b.textContent = "+ Daftar Jadi Relawan";
    b.addEventListener("click", function () { openSelf(true); });
    old.replaceWith(b);
  }
  function selfButton(isVolunteer) {
    var b = $("rsSelfBtn");
    if (!b) return;
    b.disabled = !isVolunteer;
    b.classList.toggle("primary", !!isVolunteer);
    b.title = isVolunteer ? "Ubah kesediaan, peralatan, kemampuan, bencana, booking & lihat statusnya" : "Aktif bila akun Anda terdaftar sebagai relawan";
    if (isVolunteer && !b.dataset.bound) {
      b.dataset.bound = "1";
      b.addEventListener("click", function () { var box = $("saya"); if (box && !box.hidden) { box.hidden = true; } else { openSelf(true); } });
    }
    var reg = $("openRegisterBtn");
    if (reg && isVolunteer) reg.hidden = true;   // sudah relawan: tidak perlu tombol daftar
  }

  // owner 2026-11-12: berangkat, menginap (shelter relawan / posko shelter), pulang — masing-masing bisa dipesan
  function optRow(icon, title, sub, kind, target, evId, label, ok, leg) {
    return '<div class="rs-opt"><div><b>' + icon + " " + esc(title) + "</b><br><small>" + sub + "</small></div>" +
      '<button class="btn mini" type="button" data-book="' + kind + '" data-target="' + esc(target) + '" data-ev="' + esc(evId) + '"' +
      (leg ? ' data-leg="' + leg + '"' : "") + (ok ? "" : " disabled") + ">" + label + "</button></div>";
  }
  function armRow(a, evId, leg) {
    return optRow(leg === "pulang" ? "↩" : "🚚", a.title, esc(a.posko_title || "") + (a.route ? " · " + esc(a.route) : "") +
      (a.departure_at ? " · " + (leg === "pulang" ? "pulang " : "berangkat ") + esc(a.departure_at) : "") +
      (a.pickup && leg !== "pulang" ? " · jemput: " + esc(a.pickup) : "") + " · sisa " + a.seats_left + "/" + a.seats + " kursi",
      "transport", a.id, evId, leg === "pulang" ? "Pesan kursi pulang" : "Pesan kursi berangkat", a.seats_left > 0, leg);
  }
  function renderOptions(evId, title, opt) {
    var none = function (t) { return '<p class="rn-muted">' + t + "</p>"; };
    var pos = (opt.posko || []).map(function (p) {
      return optRow("📍", p.title, esc(p.type || "") + (p.city ? " · " + esc(p.city) : "") + " · " + p.volunteers + " relawan bertugas",
        "posko", p.id, evId, "Tawarkan diri", true);
    }).join("");
    var go = (opt.armada || []).map(function (a) { return armRow(a, evId, "berangkat"); }).join("");
    var back = (opt.armada_pulang || []).map(function (a) { return armRow(a, evId, "pulang"); }).join("");
    var ako = (opt.akomodasi || []).map(function (a) {
      return optRow("🏠", a.title, esc(a.posko_title || "") + (a.safety ? " · " + esc(a.safety) : "") + " · sisa " + a.beds_left + "/" + a.beds + " tempat tidur",
        "akomodasi", a.id, evId, "Pesan tempat", a.beds_left > 0);
    }).join("");
    var sh = (opt.shelter || []).map(function (p) {
      return optRow("⛺", p.title, "Posko shelter" + (p.city ? " · " + esc(p.city) : "") + " · pengelola shelter yang memutuskan",
        "shelter", p.id, evId, "Minta menginap", true);
    }).join("");
    return '<div class="rs-ev-opts"><h4 style="margin:12px 0 6px">' + esc(title) + "</h4>" +
      "<h5>a. Posko tempat Anda membantu</h5>" + (pos || none("Belum ada posko untuk bencana ini.")) +
      "<h5>b. Berangkat ke lokasi bencana (kursi armada)</h5>" + (go || none("Belum ada armada yang membawa relawan ke lokasi.")) +
      "<h5>c. Tempat menginap (shelter relawan / posko shelter)</h5>" + (ako + sh || none("Belum ada tempat menginap untuk bencana ini.")) +
      "<h5>d. Pulang (kursi armada)</h5>" + (back || none("Belum ada armada yang melayani kepulangan relawan.")) + "</div>";
  }
  var KIND = function (b) {
    if (b.booking_kind === "transport") return b.trip_leg === "pulang" ? "↩ Kursi pulang: " : "🚚 Kursi berangkat: ";
    return b.booking_kind === "posko" ? "📍 Tawaran ke posko: " : b.booking_kind === "shelter" ? "⛺ Menginap di posko shelter: " : "🏠 Tempat menginap: ";
  };

  async function loadMine() {
    var r = await call("my_volunteer");
    var offered = new Set(r.offered || []);
    $("rsEvents").innerHTML = (r.events || []).map(function (e) {
      return '<label class="rs-ev"><input type="checkbox" name="ev" value="' + esc(e.id) + '"' + (offered.has(e.id) ? " checked" : "") + "> " + esc(e.title) + "</label>";
    }).join("") || '<p class="rn-muted">Belum ada bencana aktif.</p>';
    $("rsFirst").hidden = (r.profiles || []).length > 0;
    selfButton((r.profiles || []).length > 0);
    var pf = $("rsProfileForm");
    if (pf) {
      $("rsProfilePanel").hidden = !(r.profiles || []).length;
      var v = r.profile || {};
      Array.prototype.forEach.call(pf.elements, function (el) {
        if (!el.name || !(el.name in v)) return;
        if (el.type === "checkbox") el.checked = !!Number(v[el.name]); else el.value = v[el.name] == null ? "" : v[el.name];
      });
    }
    var titles = {}; (r.events || []).forEach(function (e) { titles[e.id] = e.title; });
    var blocks = [];
    for (var i = 0; i < (r.offered || []).length; i++) {
      var ev = r.offered[i];
      try { blocks.push(renderOptions(ev, titles[ev] || ev, await call("booking_options", { disaster_event: ev }))); } catch (e) {}
    }
    $("rsOptions").innerHTML = blocks.join("");
    $("rsBookings").innerHTML = (r.bookings || []).length ? r.bookings.map(function (b) {
      var kind = KIND(b);
      return '<div class="rs-opt"><div><b>' + kind + esc(b.target_title || "-") + "</b> " + chip(b.status) +
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
          "<br><small>" + KIND(b) + esc(b.target_title || "") +
          (b.date_from ? " · " + esc(b.date_from) + (b.date_to ? " s/d " + esc(b.date_to) : "") : "") +
          (b.pickup_location ? " · jemput: " + esc(b.pickup_location) : "") + (b.contact ? " · " + esc(b.contact) : "") +
          (b.note ? "<br>" + esc(b.note) : "") + "</small></div>" +
          (b.status === "requested" ? '<div><button class="btn primary mini" data-decide="confirm" data-id="' + esc(b.name) + '">Setujui</button> ' +
            '<button class="btn ghost mini" data-decide="reject" data-id="' + esc(b.name) + '">Tolak</button></div>' : "") + "</div>";
      }).join("");
    } catch (e) { $("rsPoskoPanel").hidden = true; }
  }

  // audit 2026-11-11 (T3): status akun — login saja belum cukup, akun Rescue-Net harus aktif
  async function rnAccountStatus() {
    try { return await window.RN_FRAPPE.call("rescue_net.api_auth.account_status", {}); } catch (e) { return { logged_in: false }; }
  }
  function rnRegMsg(st) {
    return st.rn_status === "pending"
      ? "Akun Rescue-Net Anda masih menunggu verifikasi admin. Fitur ini bisa dipakai setelah akun aktif."
      : 'Akun Anda sudah login tetapi belum terdaftar di Rescue-Net. <a href="auth.html#daftar">Lengkapi pendaftaran</a>.';
  }
  document.addEventListener("DOMContentLoaded", async function () {
    if (!$("rsPanel") && !$("rsPoskoPanel") && !$("openRegisterBtn")) return;
    var sess = null;
    var st = await rnAccountStatus();
    if (st.logged_in && st.registered) { try { sess = await window.RN_FRAPPE.call("rescue_net.api_auth.session_info"); } catch (e) {} }
    var guest = !st.logged_in;
    if ($("rsStatus")) $("rsStatus").textContent = "";
    if (guest) { guestButton(); if ($("rsLogin")) $("rsLogin").hidden = false; if (location.hash === "#saya") openSelf(false); return; }
    if (!st.registered) { guestButton(); if ($("rsStatus")) $("rsStatus").innerHTML = rnRegMsg(st); return; }
    if (st.is_system_manager && st.rn_status === "none") {
      // audit 2026-11-11 (T4): super admin tidak punya profil relawan
      guestButton();
      if ($("rsStatus")) $("rsStatus").innerHTML = 'Anda login sebagai super admin, yang tidak punya profil relawan. Pengaturan Relawan hanya untuk akun relawan; untuk mencoba gunakan akun relawan.';
      if (location.hash === "#saya") openSelf(false);
      return;
    }
    memberButton();
    var mine = !!$("rsPanel");
    if (mine) $("rsPanel").hidden = false;
    if (location.hash === "#saya") openSelf(true);   // relawan yang baru login langsung ke Pengaturan Relawan
    var pform = $("rsProfileForm");
    if (pform) pform.addEventListener("submit", async function (e) {
      e.preventDefault();
      var args = {};
      Array.prototype.forEach.call(pform.elements, function (el) {
        if (!el.name) return;
        args[el.name] = el.type === "checkbox" ? (el.checked ? 1 : 0) : el.value;
      });
      var m = $("rsProfileMsg"); m.textContent = "Menyimpan…";
      try { await call("update_my_profile", args, true); m.textContent = "Profil tersimpan."; await loadMine(); }
      catch (err) { m.textContent = (err && err.message) || err; }
    });
    if ($("rsOfferForm")) $("rsOfferForm").addEventListener("submit", async function (e) {
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
          var row = bk.closest(".rs-opt"), old = document.querySelector(".rs-book-form");
          if (old) old.remove();
          var tr = bk.dataset.book === "transport", stay = bk.dataset.book === "akomodasi" || bk.dataset.book === "shelter";
          var f = document.createElement("form");
          f.className = "rn-form rs-book-form"; f.style.cssText = "margin:6px 0 12px;padding:10px;border:1px solid rgba(104,64,45,.2);border-radius:10px";
          f.innerHTML = '<div class="form-grid">' +
            "<label>" + (tr ? (bk.dataset.leg === "pulang" ? "Tanggal pulang" : "Tanggal berangkat") : stay ? "Menginap dari" : "Mulai membantu") + '<input type="date" name="date_from"></label>' +
            (tr ? "" : "<label>" + (stay ? "Sampai" : "Sampai (opsional)") + '<input type="date" name="date_to"></label>') +
            (tr ? '<label>Titik jemput Anda<input name="pickup_location" placeholder="mis. Terminal Meulaboh"></label>' : "") +
            '<label>Catatan untuk posko<input name="note" maxlength="500" placeholder="opsional"></label></div>' +
            '<div class="form-actions"><button class="btn primary" type="submit">Kirim</button> <button class="btn ghost" type="button" data-batal>Batal</button></div>';
          row.after(f);
          f.querySelector("[data-batal]").onclick = function () { f.remove(); };
          f.onsubmit = async function (ev) {
            ev.preventDefault();
            try {
              await call("book", { kind: bk.dataset.book, target: bk.dataset.target, disaster_event: bk.dataset.ev, trip_leg: bk.dataset.leg || undefined,
                date_from: f.date_from.value || undefined, date_to: f.date_to ? f.date_to.value || undefined : undefined,
                pickup_location: f.pickup_location ? f.pickup_location.value || undefined : undefined, note: f.note.value || undefined }, true);
              msg(bk.dataset.book === "posko" ? "Tawaran terkirim ke posko. Bila disetujui, Anda langsung ditempatkan di sana." : "Permintaan terkirim. Menunggu persetujuan posko.");
              f.remove(); await loadMine();
            } catch (err) { msg((err && err.message) || err, true); }
          };
          return;
        } else if (cn) {
          await call("cancel_booking", { booking: cn.dataset.cancel }, true);
        } else {
          await call("decide_booking", { booking: dc.dataset.id, action: dc.dataset.decide }, true);
        }
        if (mine) await loadMine();
        if ($("rsPoskoPanel")) await loadPosko();
      } catch (err) { msg((err && err.message) || err, true); }
    });
    if (mine) { try { await loadMine(); } catch (e) { msg((e && e.message) || e, true); } }
    if ($("rsPoskoPanel")) loadPosko();
  });
})();
