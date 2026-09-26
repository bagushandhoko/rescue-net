/* ============================================================
 * rn-ui.js — shared frontend helpers (phase 5).
 *
 * Page scripts used to carry their own copies of these (27 identical
 * esc(), 11 fmt(), 9 getEventId(), …). They now delegate here, keeping
 * their local names, so behaviour is exactly the same. New code calls
 * window.RNUI.* directly.
 *
 *   RNUI.esc(v)          HTML-escape (& < > " '), null/undefined -> ""
 *   RNUI.fmt(n)          number, Indonesian grouping, falsy -> "0"
 *   RNUI.shortDate(s)    "YYYY-MM-DD" from an ISO/datetime string, else "-"
 *   RNUI.fmtTime(s)      "YYYY-MM-DD HH:MM", else "-"
 *   RNUI.eventId(def)    ?event= from the URL, else def ("event-sim-001")
 *   RNUI.chip(label, tone)             <span class="chip tone">label</span>
 *   RNUI.kpiCard({label, value, hint, tone, icon, kpi})   KPI tile markup
 *   RNUI.modal(id).open(title, sub, html) / .close()      rn-ba-modal drawer
 * ============================================================ */
(function () {
  "use strict";
  if (window.RNUI) return;

  var ESC = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return ESC[c]; });
  }

  function fmt(n) { return Number(n || 0).toLocaleString("id-ID"); }

  function shortDate(s) { return s ? String(s).slice(0, 10) : "-"; }

  function fmtTime(t) { return t ? String(t).slice(0, 16).replace("T", " ") : "-"; }

  function eventId(fallback) {
    return new URLSearchParams(window.location.search).get("event") ||
      (fallback === undefined ? "event-sim-001" : fallback);
  }

  function chip(label, tone) {
    return '<span class="chip' + (tone ? " " + esc(tone) : "") + '">' + esc(label) + "</span>";
  }

  function kpiCard(o) {
    o = o || {};
    var tag = o.kpi ? "button" : "div";
    return (
      "<" + tag + (o.kpi ? ' type="button" data-kpi="' + esc(o.kpi) + '"' : "") +
      ' class="kpi-card' + (o.tone ? " " + esc(o.tone) : "") + (o.kpi ? " rn-kpi-btn" : "") + '">' +
      (o.icon ? '<span class="kpi-icon" data-icon="' + esc(o.icon) + '"></span>' : "") +
      "<span>" + esc(o.label) + "</span><strong>" + esc(o.value == null ? "-" : o.value) + "</strong>" +
      (o.hint ? "<small>" + esc(o.hint) + "</small>" : "") +
      "</" + tag + ">"
    );
  }

  // Drawer/modal in the rn-ba-modal markup used by Bencana Aktif, Alat Kerja, …
  function modal(id) {
    var root = document.getElementById(id);
    return {
      open: function (title, sub, html) {
        if (!root) return;
        var t = root.querySelector("[data-modal-title], h3");
        var s = root.querySelector("[data-modal-sub], .rn-muted");
        var b = root.querySelector("[data-modal-body], .rn-ba-modal-body");
        if (t && title != null) t.textContent = title;
        if (s && sub != null) s.textContent = sub;
        if (b && html != null) b.innerHTML = html;
        root.hidden = false;
        document.body.style.overflow = "hidden";
      },
      close: function () {
        if (!root) return;
        root.hidden = true;
        document.body.style.overflow = "";
      },
    };
  }

  window.RNUI = { esc: esc, fmt: fmt, shortDate: shortDate, fmtTime: fmtTime, eventId: eventId,
                  chip: chip, kpiCard: kpiCard, modal: modal };
})();
