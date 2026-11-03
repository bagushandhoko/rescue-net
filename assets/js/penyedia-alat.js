/* penyedia-alat.js — Detail Alat & Penyedia (owner 2026-11-03): one tool, who provides it (link to the
   organisation / posko page), the contact person (logged-in, or public when the owner allows), how long it can
   be used, operator, mobilisation needs, and other tools of the same provider.
   api_recovery_support.tool_detail */
(function () {
  "use strict";
  var $ = function (s) { return document.querySelector(s); };
  var qs = new URLSearchParams(location.search);
  function esc(s) { return window.RNUI.esc(s); }
  function fmt(n) { return window.RNUI.fmt(n); }
  function rp(n) { n = Number(n || 0); return n ? "Rp " + n.toLocaleString("id-ID") : ""; }
  function tgl(s) {
    if (!s) return "";
    var d = new Date(String(s).slice(0, 10) + "T00:00:00");
    return isNaN(d) ? String(s) : d.toLocaleDateString("id-ID", { day: "numeric", month: "long", year: "numeric" });
  }
  var ev = qs.get("event") || "";

  function dl(rows) {
    rows = rows.filter(function (r) { return r[1] !== "" && r[1] != null; });
    return '<dl class="rn-pa-dl">' + rows.map(function (r) {
      return "<dt>" + esc(r[0]) + "</dt><dd>" + (r[2] ? r[1] : esc(r[1])) + "</dd>";
    }).join("") + "</dl>";
  }

  function usage(d) {
    if (!d.available_from && !d.available_until) return "belum diisi";
    var s = (d.available_from ? tgl(d.available_from) : "sekarang") + " – " + (d.available_until ? tgl(d.available_until) : "tanpa batas");
    if (d.available_until) {
      var a = d.available_from ? new Date(d.available_from) : new Date();
      var n = Math.round((new Date(d.available_until) - a) / 86400000) + 1;
      if (n > 0) s += " (± " + fmt(n) + " hari)";
    }
    return s;
  }

  function render(d) {
    document.title = "Rescue-Net | " + d.resource_name;
    $("#paTitle").textContent = d.resource_name;
    $("#paSub").textContent = [d.category_label, d.provider && d.provider.label, d.current_location].filter(Boolean).join(" · ");
    $("#paStatus").textContent = d.status_label || "—";
    var needs = [];
    if (d.support_transport) needs.push("Transport / mobilisasi");
    if (d.support_fuel) needs.push("BBM");
    if (d.support_operator) needs.push("Operator dari penerima");
    if (d.support_accommodation) needs.push("Akomodasi / konsumsi operator");
    var operator = d.operator_included
      ? "Termasuk operator" + (d.operator_count ? " (" + fmt(d.operator_count) + " orang)" : "")
      : (d.support_operator ? "Tidak termasuk — butuh operator" : "Tidak termasuk operator");
    $("#paTool").innerHTML =
      '<div class="rn-pa-tags">' +
        (d.offer_label ? '<span class="chip success">' + esc(d.offer_label) + "</span>" : "") +
        '<span class="chip">' + esc(operator) + "</span>" +
        (d.verification_status === "self_reported" ? '<span class="chip neutral">Data dari pemilik (belum diverifikasi)</span>' : "") +
      "</div>" +
      dl([
        ["Kategori", d.category_label], ["Jumlah", fmt(d.quantity || 1) + " " + (d.unit || "")],
        ["Spesifikasi / kondisi", d.capacity_description || ""],
        ["Status", d.status_label], ["Lokasi sekarang", d.current_location || ""], ["Area layanan", d.coverage_area || ""],
        ["Bisa dipakai", usage(d)], ["Operator", operator],
        ["Biaya operasional", d.daily_operating_cost ? rp(d.daily_operating_cost) + " / hari" : ""],
      ]) +
      '<h4 class="rn-pa-sec">Kebutuhan pendukung mobilisasi</h4>' +
      (needs.length || d.mobilization_needs || d.mobilization_cost || d.support_notes
        ? (needs.length ? '<div class="rn-pa-tags">' + needs.map(function (n) { return '<span class="chip warning">' + esc(n) + "</span>"; }).join("") + "</div>" : "") +
          dl([["Rincian", d.mobilization_needs || ""], ["Perkiraan biaya mobilisasi", rp(d.mobilization_cost)],
              ["Dukungan lain", d.support_notes || ""]])
        : '<p class="rn-muted">Tidak ada kebutuhan pendukung yang dicatat.</p>') +
      (d.can_manage ? '<p style="margin-top:12px"><a class="btn" href="tawarkan-alat.html?edit=' + encodeURIComponent(d.name) +
        "&event=" + encodeURIComponent(ev || d.disaster_event || "") + '">Ubah data alat ini</a></p>' : "");

    var p = d.provider || {};
    var c = d.contact || {};
    var contact;
    if (c.shown) {
      contact = '<div class="rn-pa-contact">' +
        (c.name ? "<div><b>" + esc(c.name) + "</b><br><span class=\"rn-muted\">Kontak person</span></div>" : "") +
        (c.whatsapp_url ? '<a class="btn primary" href="' + esc(c.whatsapp_url) + '" target="_blank" rel="noopener">WhatsApp ' + esc(c.phone) + "</a>" : "") +
        (c.phone ? '<a class="btn" href="tel:' + esc(c.phone) + '">Telepon ' + esc(c.phone) + "</a>" : "") +
        (c.email ? '<a class="btn ghost" href="mailto:' + esc(c.email) + "?subject=" + encodeURIComponent("Alat: " + d.resource_name) + '">' + esc(c.email) + "</a>" : "") +
        "</div>";
    } else if (c.available) {
      contact = '<p>Kontak person tersedia untuk pengguna yang login. <a href="auth.html?next=' +
        encodeURIComponent(location.pathname + location.search) + '">Login / Registrasi</a></p>';
    } else if (c.org_contact) {
      contact = "<p><b>" + esc(c.org_contact.name || "") + "</b>" + (c.org_contact.note ? "<br>" + esc(c.org_contact.note) : "") + "</p>";
    } else {
      contact = '<p class="rn-muted">Penyedia belum mencantumkan kontak person.</p>';
    }
    $("#paProvider").innerHTML =
      '<p style="margin:0 0 10px"><span class="rn-muted">Penyedia</span><br><b style="font-size:16px">' +
        (p.href ? '<a href="' + esc(p.href) + '">' + esc(p.label) + " →</a>" : esc(p.label || "-")) + "</b>" +
        (p.type === "individual" ? '<br><small class="rn-muted">Pemilik perorangan — nama pribadi tidak ditampilkan publik.</small>' : "") + "</p>" +
      contact;

    var others = d.other_tools || [];
    $("#paOtherPanel").hidden = !others.length;
    $("#paOther").innerHTML = others.map(function (o) {
      return '<a href="penyedia-alat.html?id=' + encodeURIComponent(o.name) + "&event=" + encodeURIComponent(ev) + '"><span>' +
        esc(o.resource_name) + "</span><span class=\"rn-muted\">" + fmt(o.quantity || 1) + " " + esc(o.unit || "") + " · " + esc(o.status_label) + "</span></a>";
    }).join("");
  }

  async function load() {
    var id = qs.get("id");
    if (ev) $("#paBack").href = "alat-kerja.html?event=" + encodeURIComponent(ev) + "#penyedia";
    if (!id) { $("#paSub").textContent = "Alat tidak dipilih."; return; }
    try {
      var d = await window.RN_FRAPPE.call("rescue_net.api_recovery_support.tool_detail", { resource_profile: id });
      if (!d.found) { $("#paSub").textContent = "Alat tidak ditemukan."; $("#paTool").innerHTML = ""; $("#paProvider").innerHTML = ""; return; }
      if (!ev && d.disaster_event) { ev = d.disaster_event; $("#paBack").href = "alat-kerja.html?event=" + encodeURIComponent(ev) + "#penyedia"; }
      render(d);
    } catch (e) { $("#paSub").textContent = "Gagal memuat: " + ((e && e.message) || e); }
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", load); else load();
})();
