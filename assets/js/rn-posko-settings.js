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
  if (!POSKO) return;

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
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
      ".rn-ps-ov{position:fixed;inset:0;background:rgba(20,14,10,.5);display:flex;align-items:flex-start;",
      "justify-content:center;padding:32px 16px;z-index:9999;overflow:auto}",
      ".rn-ps-card{background:#fff;max-width:720px;width:100%;border-radius:14px;box-shadow:0 20px 60px rgba(0,0,0,.3);",
      "padding:20px 22px;color:#2a2018}",
      ".rn-ps-card h3{margin:0 0 2px}",
      ".rn-ps-sub{color:#6b5c4f;font-size:13px;margin:0 0 14px}",
      ".rn-ps-sec{font-weight:700;font-size:12px;letter-spacing:.04em;text-transform:uppercase;color:#8a5a2a;",
      "margin:16px 0 6px}",
      ".rn-ps-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px 14px}",
      ".rn-ps-grid label{display:flex;flex-direction:column;gap:3px;font-size:13px}",
      ".rn-ps-grid label.wide{grid-column:1/-1}",
      ".rn-ps-grid input,.rn-ps-grid select,.rn-ps-grid textarea{font:inherit;font-size:13px;padding:7px 9px;",
      "border:1px solid rgba(0,0,0,.2);border-radius:7px;background:#fff}",
      ".rn-ps-grid textarea{resize:vertical;min-height:52px}",
      ".rn-ps-act{display:flex;gap:10px;align-items:center;margin-top:18px}",
      ".rn-ps-act .rn-ps-msg{font-size:13px;color:#6b5c4f}",
      ".rn-ps-save{padding:8px 16px;border-radius:8px;border:0;background:#b5642d;color:#fff;font:inherit;cursor:pointer}",
      ".rn-ps-cancel{padding:8px 14px;border-radius:8px;border:1px solid rgba(0,0,0,.2);background:#fff;font:inherit;cursor:pointer}",
      "@media(max-width:560px){.rn-ps-grid{grid-template-columns:1fr}}",
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

  function openModal(p) {
    styleOnce();
    var ov = el('<div class="rn-ps-ov"></div>');
    var loc = [p.village_name, p.district_name, p.city_name, p.province_name].filter(Boolean).join(", ");
    ov.appendChild(el(
      '<div class="rn-ps-card" role="dialog" aria-modal="true">' +
      "<h3>Pengaturan Posko</h3>" +
      '<p class="rn-ps-sub">' + esc(p.name) + (loc ? " · " + esc(loc) : "") + "</p>" +
      '<form id="rnPsForm">' +

      '<div class="rn-ps-sec">Identitas</div>' +
      '<div class="rn-ps-grid">' +
      '<label class="wide">Nama posko<input name="title" value="' + esc(v(p.title)) + '" required></label>' +
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
        '<button type="button" class="rn-ps-cancel" id="rnPsBroadcastBtn">Kirim WhatsApp</button>' +
        '<button type="button" class="rn-ps-cancel" id="rnPsLogBtn">Lihat log kiriman</button>' +
        '<span class="rn-ps-msg" id="rnPsWaMsg"></span>' +
      "</div>" +
      '<div class="wide" id="rnPsLog" style="grid-column:1/-1;font-size:12px;color:#5b4a3d"></div>' +
      "</div>" +

      '<div class="rn-ps-sec">Data Lain</div>' +
      '<div class="rn-ps-grid">' +
      '<label>Jumlah jiwa dilayani<input type="number" name="rn_beneficiary_count" value="' + esc(v(p.rn_beneficiary_count)) + '"></label>' +
      '<label>Detail publik<select name="public_detail">' +
        optionList(DETAIL_OPTS, DETAIL_LABEL, v(p.public_detail) || "inherit") + "</select></label>" +
      '<label class="wide">Fasilitas tersedia<textarea name="facilities">' + esc(v(p.facilities)) + "</textarea></label>" +
      '<label class="wide">Catatan<textarea name="notes">' + esc(v(p.notes)) + "</textarea></label>" +
      "</div>" +

      '<div class="rn-ps-act">' +
      '<button type="submit" class="rn-ps-save">Simpan</button>' +
      '<button type="button" class="rn-ps-cancel">Batal</button>' +
      '<span class="rn-ps-msg"></span>' +
      "</div>" +
      "</form></div>"
    ));

    function close() { ov.remove(); document.removeEventListener("keydown", onKey); }
    function onKey(e) { if (e.key === "Escape") close(); }
    document.addEventListener("keydown", onKey);
    ov.addEventListener("click", function (e) { if (e.target === ov) close(); });
    ov.querySelector(".rn-ps-cancel").addEventListener("click", close);

    ov.querySelector("#rnPsForm").addEventListener("submit", async function (e) {
      e.preventDefault();
      var f = e.target, msg = ov.querySelector(".rn-ps-msg");
      var g = function (n) { return f[n] ? String(f[n].value).trim() : ""; };
      msg.textContent = "Menyimpan…";
      try {
        await window.RN_FRAPPE.call("rescue_net.api_community_cluster.update_posko", {
          posko: POSKO,
          title: g("title"),
          posko_type: g("posko_type"),
          operational_status: g("operational_status"),
          active_from: g("active_from"),
          active_until: g("active_until"),
          address: g("address"),
          latitude: g("latitude"),
          longitude: g("longitude"),
          officer_in_charge_name: g("officer_in_charge_name"),
          officer_in_charge_role: g("officer_in_charge_role"),
          officer_in_charge_phone: g("officer_in_charge_phone"),
          officer_in_charge_whatsapp: g("officer_in_charge_whatsapp"),
          officer_in_charge_email: g("officer_in_charge_email"),
          emergency_contact: g("emergency_contact"),
          rn_beneficiary_count: g("rn_beneficiary_count"),
          public_detail: g("public_detail"),
          facilities: g("facilities"),
          notes: g("notes"),
          notify_whatsapp_enabled: f.notify_whatsapp_enabled && f.notify_whatsapp_enabled.checked ? 1 : 0,
          notify_whatsapp_numbers: g("notify_whatsapp_numbers"),
        }, { method: "POST" });
        msg.textContent = "Tersimpan ✓ — memuat ulang…";
        setTimeout(function () { location.reload(); }, 600);
      } catch (err) {
        msg.textContent = "Gagal: " + ((err && err.message) || err);
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
    var t = ov.querySelector('input[name="title"]');
    if (t) t.focus();
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

    var tries = 0;
    (function place() {
      if (document.getElementById("rnPoskoSettingsBtn")) return;
      var actions = document.querySelector(".rn-public-header .rn-public-actions");
      if (actions) { actions.appendChild(btn); return; }
      if (++tries <= 24) { setTimeout(place, 250); return; }
      // no public header on this page — fall back to the page's own topbar
      btn.classList.add("rn-ps-btn");
      var host =
        document.querySelector("header.topbar .rn-logistik-controls") ||
        document.querySelector("header.topbar") ||
        document.querySelector(".topbar") ||
        document.querySelector("main.main") || document.body;
      if (host.classList && host.classList.contains("main")) {
        btn.style.margin = "8px 0"; host.insertBefore(btn, host.firstChild);
      } else {
        host.appendChild(btn);
      }
    })();
  }

  (async function run() {
    var data;
    try {
      data = await window.RN_FRAPPE.call(
        "rescue_net.api_community_cluster.get_posko_settings", { posko: POSKO });
    } catch (e) { return; }
    if (!data || !data.can_edit || !data.posko) return;
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", function () { mountButton(data.posko); });
    } else {
      mountButton(data.posko);
    }
  })();
})();
