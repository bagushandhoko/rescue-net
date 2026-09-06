/* ============================================================
 * rn-posko-picker.js — shared grouped posko <select> builder.
 *
 * Used by every operational page that carries a posko selector
 * (posko-logistik.html, posko-distribusi.html). Data comes from
 * rescue_net.api_control_centre.event_poskos → { points, viewer }.
 *
 * Behaviour:
 *   - Logged-in org member (viewer.org set): the select defaults to
 *     "Posko organisasi saya" only. A "Posko nasional" toggle (state kept
 *     in localStorage) adds a second <optgroup> with every OTHER org's
 *     posko whose Control Centre detail is open to the public
 *     (detail_allowed). One select, two groups — org poskos on top.
 *   - Guest / non-org user: no toggle, a single flat list of all poskos.
 *     These viewers are read-only anyway (rn-posko-scope.js / page gating).
 *
 * The currently selected posko (from ?id=) is always kept selectable even
 * when it falls outside the visible groups, so a deep link never breaks.
 * ============================================================ */
(function () {
  "use strict";

  var DEFAULT_KEY = "rn_posko_picker_national";

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

  function readToggle(key) {
    try { return localStorage.getItem(key) === "1"; } catch (e) { return false; }
  }
  function writeToggle(key, on) {
    try { localStorage.setItem(key, on ? "1" : "0"); } catch (e) {}
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
   *   scopeHostEl element to inject the "Posko nasional" toggle into
   *   sortFn     optional (a,b)=>number applied within each group
   *   labelFn    optional (pt)=>string for the option text
   *   onChange   fn(value) on select change
   *   storageKey localStorage key for the toggle (default rn_posko_picker_national)
   */
  function mount(opts) {
    opts = opts || {};
    var sel = opts.selectEl;
    if (!sel) return;

    var points = (opts.points || []).slice();
    var viewer = opts.viewer || {};
    var current = opts.current || "";
    var key = opts.storageKey || DEFAULT_KEY;
    var labelFn = opts.labelFn || null;

    if (opts.sortFn) points.sort(opts.sortFn);

    var myOrg = viewer && viewer.org ? String(viewer.org) : "";

    // ---- guest / non-org member: one flat list -----------------------------
    if (!myOrg) {
      if (opts.scopeHostEl) opts.scopeHostEl.innerHTML = "";
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

    // ---- org member: grouped, with a "national" toggle --------------------
    var mine = points.filter(function (p) { return String(p.organization || "") === myOrg; });
    var national = points.filter(function (p) {
      return String(p.organization || "") !== myOrg && p.detail_allowed;
    });

    // The live selection: what the user has actually picked so far, falling
    // back to the deep-link value. Re-rendering on a toggle must not snap the
    // select back to the ?id= posko after the user has moved on from it.
    function activeId() {
      var v = sel.value;
      if (v && points.some(function (p) { return matchId(p, v); })) return v;
      return current;
    }

    function render() {
      var showNational = readToggle(key);
      var cur = activeId();
      var html = "";

      // keep the selected posko listed even if it's outside the currently
      // visible groups (deep link, or a national pick then toggled off)
      var currentPt = cur && points.filter(function (p) { return matchId(p, cur); })[0];
      var currentVisible = currentPt && (
        String(currentPt.organization || "") === myOrg ||
        (showNational && currentPt.detail_allowed)
      );
      if (currentPt && !currentVisible) {
        html += groupHtml("Posko dipilih", [currentPt], cur, labelFn);
      }

      if (mine.length) {
        html += groupHtml("Posko organisasi saya", mine, cur, labelFn);
      } else {
        html += '<optgroup label="Posko organisasi saya">' +
          '<option value="" disabled>— tidak ada posko untuk bencana ini —</option></optgroup>';
      }

      if (showNational) {
        html += groupHtml(
          "Posko lain (nasional · detail publik)", national, cur, labelFn
        );
      }

      sel.innerHTML = html;

      // nothing chosen yet -> first real option in "my organisation"
      if (!cur) {
        var first = sel.querySelector('option:not([disabled])');
        if (first) first.selected = true;
      }
    }

    // toggle UI
    if (opts.scopeHostEl) {
      opts.scopeHostEl.innerHTML =
        '<label class="rn-posko-scope-toggle">' +
        '<input type="checkbox" id="' + esc(sel.id || "poskoSel") + 'National"' +
        (readToggle(key) ? " checked" : "") + "> " +
        "<span>Posko nasional</span></label>";
      var cb = opts.scopeHostEl.querySelector("input[type=checkbox]");
      if (cb) {
        cb.addEventListener("change", function () {
          writeToggle(key, cb.checked);
          render();
        });
      }
    }

    render();
    wireChange(sel, opts.onChange);
  }

  function wireChange(sel, onChange) {
    if (!onChange || sel.dataset.rnPickerWired) return;
    sel.dataset.rnPickerWired = "1";
    sel.addEventListener("change", function () { onChange(sel.value); });
  }

  window.RNPoskoPicker = { mount: mount, poskoValue: poskoValue, matchId: matchId };
})();
