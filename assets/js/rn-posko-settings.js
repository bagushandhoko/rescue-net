/* ============================================================
 * rn-posko-settings.js — shared "⚙ Pengaturan Posko" for every
 * posko workspace page. Shows a button (only when the logged-in
 * viewer can edit THIS posko) that opens a modal to change the
 * posko's name, location, active period, PIC & contacts, and
 * other posko-level data.
 *
 * Backend:
 *   rescue_net.api_community_cluster.get_posko_settings  (prefill + gate)
 *   rescue_net.api_community_cluster.update_posko         (save)
 * ============================================================ */
(function () {
  "use strict";
  if (!window.RN_FRAPPE || !window.RN_FRAPPE.call) return;

  var qs = new URLSearchParams(location.search);
  var POSKO = qs.get("id") || qs.get("posko") || "";

  /* owner 2026-11-02 23:20: form & tombol pengaturan/pencatatan (data-owner-only) hanya tampil
     untuk pengelola posko ini. Tanpa ?id= (dasbor semua posko saya): tampil bila login — server
     tetap menolak posko yang bukan milik pengguna. */
  var settingsRequest = POSKO ? getSettings() : null;
  (function ownerOnly() {
    var st = document.createElement("style");
    st.textContent = "html:not(.rn-can-operate) [data-owner-only]{display:none!important}";
    (document.head || document.documentElement).appendChild(st);
    var grant = function () { document.documentElement.classList.add("rn-can-operate"); };
    var p = POSKO
      ? settingsRequest.then(function (d) { if (d && (d.can_operate || d.can_edit)) grant(); })
      : window.RN_FRAPPE.call("rescue_net.api_auth.session_info", {})
          .then(function (d) { if (d && d.user && d.user !== "Guest") grant(); });
    p.catch(function () {});
  })();
  if (!POSKO) return;

  function esc(s) { return window.RNUI.esc(s); }
  function el(html) { var d = document.createElement("div"); d.innerHTML = html.trim(); return d.firstChild; }
  function v(x) { return x == null ? "" : String(x); }

  var STATUS_OPTS = ["active", "standby", "reducing", "closing", "offline"];
  var STATUS_LABEL = {
    active: "Aktif", standby: "Siaga", reducing: "Pengurangan",
    closing: "Persiapan tutup", offline: "Nonaktif / tutup",
  };
  var DETAIL_OPTS = ["inherit", "private", "public"];
  var DETAIL_LABEL = { inherit: "Ikuti kebijakan organisasi", private: "Privat", public: "Publik" };

  function styleOnce() {
    if (document.getElementById("rn-ps-style")) return;
    var s = document.createElement("style");
    s.id = "rn-ps-style";
    s.textContent = [
      ".rn-ps-btn{display:inline-flex;align-items:center;gap:6px;padding:6px 12px;border-radius:8px;",
      "border:1px solid rgba(0,0,0,.18);background:rgba(255,255,255,.85);font:inherit;font-size:13px;",
      "cursor:pointer;color:#3a2c22}",
      ".rn-ps-btn:hover{background:#fff}",
      "a.rn-ps-btn.rn-public-login{color:#3a2c22!important;background:#fff!important;font-weight:700;text-decoration:none}",
      ".rn-ps-ov{position:fixed;inset:0;background:rgba(20,14,10,.5);display:flex;align-items:flex-start;",
      "justify-content:center;padding:32px 16px;z-index:9999;overflow:auto}",
      ".rn-ps-card{background:#fff;max-width:820px;width:100%;min-width:0;box-sizing:border-box;overflow-wrap:anywhere;border-radius:14px;box-shadow:0 20px 60px rgba(0,0,0,.3);",
      "padding:20px 22px;color:#2a2018}",
      ".rn-ps-card h3{margin:0 0 2px}",
      ".rn-ps-sub{color:#6b5c4f;font-size:13px;margin:0 0 14px}",
      ".rn-ps-sec{font-weight:700;font-size:13px;letter-spacing:.04em;text-transform:uppercase;color:#8a5a2a;",
      "margin:16px 0 6px}",
      ".rn-ps-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px 14px}",
      ".rn-ps-grid label{display:flex;flex-direction:column;gap:3px;font-size:13px}",
      ".rn-ps-grid label.wide{grid-column:1/-1}",
      ".rn-ps-grid input,.rn-ps-grid select,.rn-ps-grid textarea{font:inherit;font-size:13px;padding:7px 9px;",
      "border:1px solid rgba(0,0,0,.2);border-radius:7px;background:#fff}",
      ".rn-ps-grid textarea{resize:vertical;min-height:52px}",
      ".rn-ps-act{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin-top:18px}",
      ".rn-ps-act .rn-ps-msg{font-size:13px;color:#6b5c4f}",
      ".rn-ps-save{padding:8px 16px;border-radius:8px;border:0;background:#8a471e;color:#fff;font:inherit;cursor:pointer}",
      ".rn-ps-cancel,.rn-ps-secondary{padding:8px 14px;border-radius:8px;border:1px solid #887467;background:#fff;color:#2a2018;font:inherit;cursor:pointer}",
      ".rn-ps-card [hidden]{display:none!important}",
      ".rn-ps-tabs{display:flex;gap:4px;overflow-x:auto;padding:4px 4px 8px;border-bottom:1px solid #c8b8ad;margin-bottom:12px}",
      ".rn-ps-tabs button{flex:none;padding:8px 12px;border:1px solid #b6a598;border-radius:8px;background:#fff;color:#2a2018;font:inherit;cursor:pointer}",
      ".rn-ps-tabs [aria-selected=true]{background:#f4e4d7;border-color:#8a471e;color:#632e12;font-weight:700}",
      ".rn-ps-arm{margin:8px 0;padding:10px;border:1px solid #b6a598;border-radius:8px;min-width:0}",
      ".rn-ps-arm>summary{cursor:pointer;font-weight:700}",
      ".rn-ps-arm form{display:grid;gap:12px;margin-top:12px}",
      ".rn-ps-arm fieldset{min-inline-size:0;margin:0;padding:10px;border:1px solid #b6a598;border-radius:8px}",
      ".rn-ps-arm legend{padding:0 4px;font-weight:700}",
      ".rn-ps-arm-grid,.rn-armada-cargo{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,190px),1fr));gap:8px 12px}",
      ".rn-armada-cargo{margin-bottom:12px}.rn-armada-cargo p{grid-column:1/-1;margin:0}",
      ".rn-armada-cargo label{display:flex;align-items:flex-start;gap:6px}.rn-armada-cargo input{flex:none}",
      ".rn-ps-arm-grid label{display:grid;gap:4px;min-width:0;font-size:13px}",
      ".rn-ps-arm-grid :is(input,select,textarea),.rn-ps-grid :is(input,select,textarea){min-width:0;max-width:100%;box-sizing:border-box;background:#fff;color:#2a2018}",
      ".rn-ps-arm-grid :is(input,select,textarea){width:100%;min-height:38px;padding:6px 8px;border:1px solid #887467;border-radius:6px;font:inherit}",
      ".rn-ps-arm-totals{margin:0 0 10px}",
      ".rn-ps-arm-actions{display:flex;flex-wrap:wrap;align-items:center;gap:8px 12px}",
      ".rn-ps-arm>summary,.rn-ps-bookings{overflow-wrap:anywhere}",
      ".rn-ps-arm>summary small,.rn-ps-booking-state{color:#632e12;background:#f4e4d7;border-radius:6px;padding:2px 5px}",
      ".rn-ps-bookings{margin-top:20px;border-top:1px solid #b6a598}",
      ".rn-ps-bookings :is(h3,h4,p){margin:8px 0}",
      ".rn-ps-bookings [data-booking-message]:empty{display:none}",
      ".rn-ps-booking{border:1px solid #b6a598;border-radius:8px;padding:10px;margin:8px 0;background:#fff;color:#2a2018}",
      ".rn-ps-booking dl{display:grid;grid-template-columns:auto minmax(0,1fr);gap:3px 10px;margin:8px 0}",
      ".rn-ps-booking dt{font-weight:600}.rn-ps-booking dd{margin:0;white-space:pre-wrap}",
      ".rn-ps-booking a{color:#632e12;text-decoration:underline}",
      "@media(max-width:560px){.rn-ps-grid{grid-template-columns:minmax(0,1fr)}.rn-ps-ov{padding:16px 10px}.rn-ps-card{padding:14px}}",
    ].join("");
    document.head.appendChild(s);
  }

  function optionList(opts, labels, cur) {
    var seen = false;
    var h = opts.map(function (o) {
      if (o === cur) seen = true;
      return '<option value="' + esc(o) + '"' + (o === cur ? " selected" : "") + ">" +
        esc(labels[o] || o) + "</option>";
    }).join("");
    if (cur && !seen) h = '<option value="' + esc(cur) + '" selected>' + esc(cur) + " (saat ini)</option>" + h;
    return h;
  }

  var tabs = { posko: "Posko", kontak: "Kontak & Notifikasi", armada: "Armada & Ruang Muat", data: "Data lain" };

  function openModal(p, tab, armada, add) {
    if (document.querySelector(".rn-ps-ov")) return;
    var previousFocus = document.activeElement;
    var previousOverflow = document.body.style.overflow;
    styleOnce();
    var ov = el('<div class="rn-ps-ov"></div>');
    var loc = [p.village_name, p.district_name, p.city_name, p.province_name].filter(Boolean).join(", ");
    ov.appendChild(el(
      '<div class="rn-ps-card" role="dialog" aria-modal="true" aria-labelledby="rnPsTitle">' +
      "<h3 id=\"rnPsTitle\">Pengaturan Posko</h3>" +
      '<p class="rn-ps-sub">' + esc(p.name) + (loc ? " · " + esc(loc) : "") + "</p>" +
      '<div class="rn-ps-tabs" role="tablist" aria-label="Bagian pengaturan">' +
      Object.keys(tabs).map(function (key) {
        return '<button type="button" role="tab" id="rnPsTab-' + key + '" aria-controls="rnPsPanel-' + key +
          '" data-tab="' + key + '">' + esc(tabs[key]) + '</button>';
      }).join("") + '</div>' +
      '<form id="rnPsForm">' +
      panel("posko") +

      '<div class="rn-ps-sec">Identitas</div>' +
      '<div class="rn-ps-grid">' +
      '<label class="wide">Nama posko<input name="title" value="' + esc(v(p.title)) + '"></label>' +
      '<label>Jenis posko<input name="posko_type" value="' + esc(v(p.posko_type)) + '" placeholder="logistics / medical / shelter / kitchen / transport"></label>' +
      '<label>Status operasional<select name="operational_status">' +
        optionList(STATUS_OPTS, STATUS_LABEL, v(p.operational_status)) + "</select></label>" +
      "</div>" +

      '<div class="rn-ps-sec">Periode Aktif</div>' +
      '<div class="rn-ps-grid">' +
      '<label>Berdiri / aktif sejak<input type="date" name="active_from" value="' + esc(v(p.active_from)) + '"></label>' +
      '<label>Rencana aktif sampai<input type="date" name="active_until" value="' + esc(v(p.active_until)) + '"></label>' +
      "</div>" +

      '<div class="rn-ps-sec">Lokasi</div>' +
      '<div class="rn-ps-grid">' +
      '<label class="wide">Alamat<textarea name="address">' + esc(v(p.address)) + "</textarea></label>" +
      '<label>Latitude<input name="latitude" value="' + esc(v(p.latitude)) + '" placeholder="-6.2000"></label>' +
      '<label>Longitude<input name="longitude" value="' + esc(v(p.longitude)) + '" placeholder="106.8000"></label>' +
      "</div>" +

      '</section>' + panel("kontak") +
      '<div class="rn-ps-sec">Penanggung Jawab &amp; Kontak</div>' +
      '<div class="rn-ps-grid">' +
      '<label>Nama PIC<input name="officer_in_charge_name" value="' + esc(v(p.officer_in_charge_name)) + '"></label>' +
      '<label>Jabatan PIC<input name="officer_in_charge_role" value="' + esc(v(p.officer_in_charge_role)) + '"></label>' +
      '<label>No. HP<input name="officer_in_charge_phone" value="' + esc(v(p.officer_in_charge_phone)) + '" placeholder="0812-…"></label>' +
      '<label>WhatsApp<input name="officer_in_charge_whatsapp" value="' + esc(v(p.officer_in_charge_whatsapp)) + '" placeholder="0812-…"></label>' +
      '<label>Email<input name="officer_in_charge_email" value="' + esc(v(p.officer_in_charge_email)) + '"></label>' +
      '<label>Kontak darurat<input name="emergency_contact" value="' + esc(v(p.emergency_contact)) + '"></label>' +
      "</div>" +

      '<div class="rn-ps-sec">Notifikasi WhatsApp</div>' +
      '<div class="rn-ps-grid">' +
      '<label class="wide" style="flex-direction:row;align-items:center;gap:8px">' +
        '<input type="checkbox" name="notify_whatsapp_enabled"' + (p.notify_whatsapp_enabled ? " checked" : "") +
        ' style="width:auto"> Kirim notifikasi posko ke WhatsApp</label>' +
      '<label class="wide">Nomor WhatsApp (boleh beberapa — pisah dengan koma / baris baru)' +
        '<textarea name="notify_whatsapp_numbers" placeholder="0812xxxxxxx, 0813xxxxxxx — nomor PIC dan/atau koordinator">' +
        esc(v(p.notify_whatsapp_numbers)) + "</textarea></label>" +
      "</div>" +

      '<div class="rn-ps-grid">' +
      '<label class="wide">Kirim pesan sekarang ke nomor di atas' +
        '<textarea id="rnPsBroadcast" placeholder="mis. Beras 50 karung tiba di posko pukul 14.00. Butuh 4 relawan bongkar."></textarea></label>' +
      '<div class="wide" style="grid-column:1/-1;display:flex;gap:8px;align-items:center;flex-wrap:wrap">' +
        '<button type="button" class="rn-ps-secondary" id="rnPsBroadcastBtn">Kirim WhatsApp</button>' +
        '<button type="button" class="rn-ps-secondary" id="rnPsLogBtn">Lihat log kiriman</button>' +
        '<span class="rn-ps-msg" id="rnPsWaMsg" role="status"></span>' +
      "</div>" +
      '<div class="wide" id="rnPsLog" style="grid-column:1/-1;font-size:13px;color:#5b4a3d"></div>' +
      "</div>" +

      '</section>' + panel("data") +
      '<div class="rn-ps-grid">' +
      '<label>Jumlah jiwa dilayani<input type="number" name="rn_beneficiary_count" value="' + esc(v(p.rn_beneficiary_count)) + '"></label>' +
      '<label>Detail publik<select name="public_detail">' +
        optionList(DETAIL_OPTS, DETAIL_LABEL, v(p.public_detail) || "inherit") + "</select></label>" +
      '<label class="wide">Fasilitas tersedia<textarea name="facilities">' + esc(v(p.facilities)) + "</textarea></label>" +
      '<label class="wide">Catatan<textarea name="notes">' + esc(v(p.notes)) + "</textarea></label>" +
      "</div>" +

      '</section><div id="rnPsSaveActions" class="rn-ps-act">' +
      '<button type="submit" class="rn-ps-save">Simpan</button>' +
      '<button type="button" class="rn-ps-cancel" id="rnPsCancel">Batal</button>' +
      '<span class="rn-ps-msg" id="rnPsSaveMsg" role="status"></span>' +
      "</div>" +
      "</form>" + panel("armada") +
      '<div id="rnPsArmada"></div><div class="rn-ps-act"><button type="button" class="rn-ps-cancel" id="rnPsArmadaCancel">Batal</button></div></section></div>'
    ));

    function panel(key) {
      return '<section role="tabpanel" id="rnPsPanel-' + key + '" aria-labelledby="rnPsTab-' + key + '" hidden>';
    }

    var changed = false;
    var buttons = Array.from(ov.querySelectorAll("[data-tab]"));
    function onSaved() {
      if (ov.isConnected) changed = true;
      else document.dispatchEvent(new Event("rn-posko-settings-saved"));
    }
    var active;
    var armadaLoaded = false;
    function selectTab(key) {
      active = Object.hasOwn(tabs, key) ? key : "posko";
      buttons.forEach(function (button) {
        var selected = button.dataset.tab === active;
        button.setAttribute("aria-selected", String(selected));
        button.tabIndex = selected ? 0 : -1;
        ov.querySelector("#rnPsPanel-" + button.dataset.tab).hidden = !selected;
      });
      ov.querySelector("#rnPsSaveActions").hidden = active === "armada";
      if (active === "armada" && !armadaLoaded) {
        armadaLoaded = true;
        window.RN_ARMADA_SETTINGS.mount(ov.querySelector("#rnPsArmada"), POSKO,
          qs.get("event") || p.disaster_event, armada, add, onSaved);
      }
    }
    buttons.forEach(function (button, index) {
      button.addEventListener("click", function () { selectTab(button.dataset.tab); });
      button.addEventListener("keydown", function (e) {
        var next = { ArrowRight: (index + 1) % buttons.length, ArrowLeft: (index + buttons.length - 1) % buttons.length,
          Home: 0, End: buttons.length - 1 }[e.key];
        if (next == null) return;
        e.preventDefault();
        buttons[next].click();
        buttons[next].focus();
      });
    });
    function close() {
      ov.remove();
      document.body.style.overflow = previousOverflow;
      document.removeEventListener("keydown", onKey);
      if (previousFocus.isConnected) previousFocus.focus();
      if (changed) document.dispatchEvent(new Event("rn-posko-settings-saved"));
    }
    function onKey(e) {
      if (document.getElementById("rnPrivacyAsk")) return;
      if (e.key === "Escape") { e.preventDefault(); close(); return; }
      if (e.key !== "Tab") return;
      var controls = Array.from(ov.querySelectorAll("button,input,select,textarea,a[href],summary")).filter(function (control) {
        return !control.disabled && control.tabIndex >= 0 && control.getClientRects().length > 0;
      });
      var edge = e.shiftKey ? controls[0] : controls[controls.length - 1];
      if (document.activeElement === edge || !ov.contains(document.activeElement)) {
        e.preventDefault();
        (e.shiftKey ? controls[controls.length - 1] : controls[0]).focus();
      }
    }
    document.addEventListener("keydown", onKey);
    ov.addEventListener("click", function (e) { if (e.target === ov) close(); });
    ["#rnPsCancel", "#rnPsArmadaCancel"].forEach(function (selector) {
      ov.querySelector(selector).addEventListener("click", close);
    });

    ov.querySelector("#rnPsForm").addEventListener("submit", async function (e) {
      e.preventDefault();
      var save = ov.querySelector(".rn-ps-save");
      var msg = ov.querySelector("#rnPsSaveMsg");
      var payload = { posko: p.name };
      Array.from(ov.querySelector("#rnPsPanel-" + active).querySelectorAll("[name]")).forEach(function (input) {
        payload[input.name] = input.type === "checkbox" ? Number(input.checked) : input.value.trim();
      });
      if (active === "posko" && !payload.title) {
        msg.textContent = "Nama posko wajib diisi.";
        return;
      }
      msg.textContent = "Menyimpan…";
      save.disabled = true;
      try {
        var saved = await window.RN_FRAPPE.call("rescue_net.api_community_cluster.update_posko", payload,
          { method: "POST", keepEmpty: Object.keys(payload) });
        msg.textContent = saved && saved.pending
          ? "Perubahan data pokok menunggu persetujuan pusat komando. Perubahan operasional tersimpan."
          : "Tersimpan ✓";
        onSaved();
        getSettings().then(function (data) { if (data && data.posko) Object.assign(p, data.posko); }).catch(function () {});
      } catch (err) {
        msg.textContent = "Gagal: " + ((err && err.message) || err);
      } finally {
        save.disabled = false;
      }
    });

    var bBtn = ov.querySelector("#rnPsBroadcastBtn");
    if (bBtn) bBtn.addEventListener("click", async function () {
      var box = ov.querySelector("#rnPsBroadcast");
      var m = ov.querySelector("#rnPsWaMsg");
      var text = String(box && box.value || "").trim();
      if (!text) { m.textContent = "Isi pesan dulu."; return; }
      m.textContent = "Mengirim…";
      try {
        var r = await window.RN_FRAPPE.call(
          "rescue_net.api_notify.posko_broadcast_whatsapp",
          { posko: POSKO, message: text }, { method: "POST" });
        if (r && r.status === "skipped") {
          m.textContent = "Tidak terkirim: " + (r.reason || "notifikasi nonaktif / tidak ada nomor") +
            ". Aktifkan toggle & isi nomor, lalu Simpan dulu.";
        } else {
          var st = ((r && r.results) || []).map(function (x) { return x.status; }).join(", ");
          m.textContent = "Terkirim ke " + ((r && r.count) || 0) + " nomor" + (st ? " (" + st + ")" : "") + ".";
          if (box) box.value = "";
        }
      } catch (e) { m.textContent = "Gagal: " + ((e && e.message) || e); }
    });

    var lBtn = ov.querySelector("#rnPsLogBtn");
    if (lBtn) lBtn.addEventListener("click", async function () {
      var wrap = ov.querySelector("#rnPsLog");
      wrap.textContent = "Memuat…";
      try {
        var r = await window.RN_FRAPPE.call(
          "rescue_net.api_notify.posko_notification_log", { posko: POSKO, limit: 15 });
        var rows = (r && r.rows) || [];
        if (!rows.length) { wrap.textContent = "Belum ada kiriman."; return; }
        wrap.innerHTML = rows.map(function (x) {
          return '<div style="padding:4px 0;border-top:1px solid rgba(0,0,0,.08)">' +
            esc(x.sent_at || x.creation || "") + " — " + esc(x.to_number || "") +
            " · <b>" + esc(x.status) + "</b>" + (x.provider ? " (" + esc(x.provider) + ")" : "") +
            (x.error ? " · " + esc(x.error) : "") +
            '<br><span style="color:#7a6a5c">' + esc(String(x.body || "").slice(0, 120)) + "</span></div>";
        }).join("");
      } catch (e) { wrap.textContent = "Gagal: " + ((e && e.message) || e); }
    });

    document.body.appendChild(ov);
    document.body.style.overflow = "hidden";
    selectTab(tab);
    ov.querySelector('[aria-selected="true"]').focus();
  }

  function mountButton(p) {
    if (document.getElementById("rnPoskoSettingsBtn")) return;
    styleOnce();
    // Lives in the public header's right-side action cluster. CSS `order`
    // (see .rn-public-actions in style.css) keeps it just before Logout
    // regardless of which script's item lands in the DOM first.
    var btn = el('<a href="#" id="rnPoskoSettingsBtn" class="rn-public-login" ' +
      'title="Ubah data posko ini">⚙ Pengaturan</a>');
    btn.addEventListener("click", function (e) { e.preventDefault(); openModal(p); });
    // Kelola Posko (owner 2026-11-01): managers' own hub, only shown to people who can edit this posko
    var kelola = el('<a id="rnKelolaPoskoBtn" class="rn-public-login" title="Halaman khusus pengelola posko" href="kelola-posko.html?id=' +
      encodeURIComponent(POSKO) + '">🔧 Kelola Posko</a>');
    document.addEventListener("click", function (e) {
      var link = e.target.closest("[data-posko-armada-settings]");
      if (!link || new URL(link.href).searchParams.get("id") !== POSKO ||
          e.ctrlKey || e.metaKey || e.shiftKey || e.altKey) return;
      e.preventDefault();
      openModal(p, "armada", link.dataset.poskoArmadaSettings, false);
    });
    var legacyAdd = location.hash === "#armadaForm";
    var legacyArmada = qs.get("armada");
    if (qs.get("settings") === "1" || legacyAdd || legacyArmada) {
      openModal(p, qs.get("tab") || (legacyAdd || legacyArmada ? "armada" : "posko"), legacyArmada, legacyAdd);
    }

    var tries = 0;
    (function place() {
      if (document.getElementById("rnPoskoSettingsBtn")) return;
      var actions = document.querySelector(".rn-public-header .rn-public-actions");
      if (actions) { actions.appendChild(kelola); actions.appendChild(btn); return; }
      if (++tries <= 24) { setTimeout(place, 250); return; }
      // no public header on this page — fall back to the page's own topbar
      btn.classList.add("rn-ps-btn");
      kelola.classList.add("rn-ps-btn");
      var host =
        document.querySelector("header.topbar .rn-logistik-controls") ||
        document.querySelector("header.topbar") ||
        document.querySelector(".topbar") ||
        document.querySelector("main.main") || document.body;
      if (host.classList && host.classList.contains("main")) {
        btn.style.margin = "8px 0"; kelola.style.margin = "8px 8px 8px 0";
        host.insertBefore(btn, host.firstChild); host.insertBefore(kelola, btn);
      } else {
        host.appendChild(kelola); host.appendChild(btn);
      }
    })();
  }

  function getSettings() {
    return window.RN_FRAPPE.call("rescue_net.api_community_cluster.get_posko_settings", { posko: POSKO });
  }

  (async function run() {
    var data;
    try {
      data = await settingsRequest;
    } catch (e) { return; }
    if (!data || !data.can_edit || !data.posko) return;
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", function () { mountButton(data.posko); });
    } else {
      mountButton(data.posko);
    }
  })();
})();
