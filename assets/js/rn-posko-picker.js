/* ============================================================
 * rn-posko-picker.js — shared grouped posko <select> builder for the
 * operational workspaces (posko-logistik.html, posko-distribusi.html).
 * Data: rescue_net.api_control_centre.event_poskos → { points, viewer }.
 *
 * Three viewer levels, mirrored by the selector:
 *   - Guest / not-logged-in / non-org user → ONE flat list of every posko
 *     for the event (national coordination view, read-only — the page hides
 *     all input forms for this viewer).
 *   - Logged-in ORG MEMBER (viewer.org set) → grouped:
 *       "Posko organisasi saya"                 — own-org poskos (full manage)
 *       "Posko lain — terbuka untuk koordinasi" — other orgs' poskos that
 *         opened themselves up (point.public_participation); the member may
 *         coordinate with these (booking / kirim bantuan) but NOT edit their
 *         internal data. Always shown, no toggle.
 *   Non-open poskos of other orgs are simply not in the operational picker —
 *   there is nothing an outside member can do on them here.
 *
 * The currently-selected posko (?id=) is always kept selectable even when it
 * falls outside both groups, so a deep link never breaks.
 * ============================================================ */
(function () {
  "use strict";

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function poskoValue(pt) {
    return pt.posko_id || pt.name || pt.id || "";
  }

  function matchId(pt, want) {
    if (!want) return false;
    want = String(want);
    return want === String(pt.posko_id || "") ||
           want === String(pt.name || "") ||
           want === String(pt.id || "");
  }

  function optionHtml(pt, current, labelFn) {
    var val = poskoValue(pt);
    var label = labelFn ? labelFn(pt) : (pt.name || pt.title || val);
    return '<option value="' + esc(val) + '"' +
      (matchId(pt, current) ? " selected" : "") + ">" + esc(label) + "</option>";
  }

  function groupHtml(label, rows, current, labelFn) {
    if (!rows.length) return "";
    return '<optgroup label="' + esc(label) + '">' +
      rows.map(function (pt) { return optionHtml(pt, current, labelFn); }).join("") +
      "</optgroup>";
  }

  /* opts:
   *   selectEl   (required) the <select>
   *   points     (required) array from event_poskos res.points
   *   viewer     res.viewer  ({ logged_in, org, org_title, manages })
   *   current    currently-selected posko id (docname or legacy id)
   *   scopeHostEl (optional, legacy) element kept empty — no toggle any more
   *   sortFn     optional (a,b)=>number applied within each group
   *   labelFn    optional (pt)=>string for the option text
   *   onChange   fn(value) on select change
   */
  function mount(opts) {
    opts = opts || {};
    var sel = opts.selectEl;
    if (!sel) return;

    if (opts.scopeHostEl) opts.scopeHostEl.innerHTML = "";

    var points = (opts.points || []).slice();
    var viewer = opts.viewer || {};
    var current = opts.current || "";
    var labelFn = opts.labelFn || null;

    if (opts.sortFn) points.sort(opts.sortFn);

    var myOrg = viewer && viewer.org ? String(viewer.org) : "";

    // ---- guest / non-org member: one flat list ---------------------------
    if (!myOrg) {
      if (!points.length) {
        sel.innerHTML = '<option value="' + esc(current) + '">' +
          esc(current || "posko") + "</option>";
      } else {
        sel.innerHTML = points.map(function (pt) {
          return optionHtml(pt, current, labelFn);
        }).join("");
        if (!current && sel.options.length) sel.selectedIndex = 0;
      }
      wireChange(sel, opts.onChange);
      return;
    }

    // ---- logged-in org member: own poskos + other orgs' open poskos ------
    var mine = points.filter(function (p) {
      return String(p.organization || "") === myOrg;
    });
    var openOthers = points.filter(function (p) {
      return String(p.organization || "") !== myOrg && p.public_participation;
    });

    var cur = current;
    // keep a deep-linked posko that is in neither group selectable
    var curPt = cur && points.filter(function (p) { return matchId(p, cur); })[0];
    var curInGroups = curPt && (
      String(curPt.organization || "") === myOrg || !!curPt.public_participation
    );

    var html = "";
    if (curPt && !curInGroups) {
      html += groupHtml("Posko dipilih", [curPt], cur, labelFn);
    }
    if (mine.length) {
      html += groupHtml("Posko organisasi saya", mine, cur, labelFn);
    } else {
      html += '<optgroup label="Posko organisasi saya">' +
        '<option value="" disabled>— tidak ada posko untuk bencana ini —</option></optgroup>';
    }
    html += groupHtml("Posko lain — terbuka untuk koordinasi", openOthers, cur, labelFn);

    sel.innerHTML = html;

    // nothing chosen yet -> first real option (own organisation)
    if (!cur) {
      var first = sel.querySelector('option:not([disabled])');
      if (first) first.selected = true;
    }

    wireChange(sel, opts.onChange);
  }

  function wireChange(sel, onChange) {
    if (!onChange || sel.dataset.rnPickerWired) return;
    sel.dataset.rnPickerWired = "1";
    sel.addEventListener("change", function () { onChange(sel.value); });
  }

  window.RNPoskoPicker = { mount: mount, poskoValue: poskoValue, matchId: matchId };
})();
