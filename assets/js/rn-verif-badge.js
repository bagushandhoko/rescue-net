/* ============================================================
 * rn-verif-badge.js — one shared "level verifikasi posko" badge.
 * window.RNVerifBadge.html(status, count?)  -> markup
 * window.RNVerifBadge.label(status)         -> text
 * window.RNVerifBadge.decorate(root?)       -> fill any
 *     <span data-rn-verif="STATUS" data-rn-verif-count="N"></span>
 * Levels mirror RN Posko.verification_status; `count` is
 * RN Posko.trusted_verifier_count (endorsement dari jaringan verifikator).
 * ============================================================ */
(function () {
  "use strict";
  var MAP = {
    self_reported:        { cls: "self",  label: "Mandiri", hint: "Belum diverifikasi pihak lain" },
    "":                   { cls: "self",  label: "Mandiri", hint: "Belum diverifikasi pihak lain" },
    needs_correction:     { cls: "warn",  label: "Perlu perbaikan", hint: "Verifikator meminta perbaikan data" },
    pending:              { cls: "pend",  label: "Menunggu verifikasi", hint: "Sudah diajukan, menunggu verifikator" },
    community_verified:   { cls: "comm",  label: "Terverifikasi komunitas", hint: "Di-endorse verifikator wilayah" },
    organization_verified:{ cls: "org",   label: "Terverifikasi organisasi", hint: "Diverifikasi organisasi induk" },
    official_verified:    { cls: "off",   label: "Terverifikasi resmi", hint: "Di-endorse verifikator pemerintah / berlapis" },
    verified:             { cls: "off",   label: "Terverifikasi", hint: "Terverifikasi" }
  };
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function info(status) {
    return MAP[String(status || "").toLowerCase()] || MAP.self_reported;
  }
  function label(status) { return info(status).label; }
  function html(status, count) {
    var i = info(status);
    var n = Number(count || 0);
    var extra = n > 0 ? ' <b class="rn-vbadge-n">' + n + "</b>" : "";
    return '<span class="rn-vbadge rn-vbadge--' + i.cls + '" title="' + esc(i.hint) + '">' +
      '<span class="rn-vbadge-dot"></span>' + esc(i.label) + extra + "</span>";
  }
  function decorate(root) {
    (root || document).querySelectorAll("[data-rn-verif]").forEach(function (el) {
      if (el.dataset.rnVerifDone === "1") return;
      el.dataset.rnVerifDone = "1";
      el.innerHTML = html(el.getAttribute("data-rn-verif"), el.getAttribute("data-rn-verif-count"));
    });
  }
  window.RNVerifBadge = { html: html, label: label, decorate: decorate, info: info };
  if (document.readyState !== "loading") decorate();
  else document.addEventListener("DOMContentLoaded", function () { decorate(); });
})();
