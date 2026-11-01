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
      '<a class="kp-item" href="#kpExpiry"><span>Stok sudah / segera kedaluwarsa</span>' + badge(h.pending.kedaluwarsa) + "</a>";
    loadExpiry();

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
