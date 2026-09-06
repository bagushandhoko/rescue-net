/* ============================================================
 * rn-posko-scope.js — scopes a posko operational page to the viewer.
 *
 * Shared by posko-logistik.html / posko-distribusi.html / posko-detail.html.
 * Backend: rescue_net.api_control_centre.posko_edit_scope
 *
 * Behaviour (only for a logged-in ORG MEMBER — everyone else untouched):
 *   - no ?id= in the URL  -> redirect to the member's own posko
 *   - ?id= is a posko he does NOT manage -> read-only mode:
 *       hide create/record forms, show a "hanya-lihat" banner.
 *   - ?id= is his own posko -> nothing changes.
 * Guests, non-members, System Managers and the real operator are never
 * restricted, so existing flows are unaffected.
 * ============================================================ */
(function () {
  "use strict";

  if (!window.RN_FRAPPE || !window.RN_FRAPPE.call) return;

  var SCOPE = "rescue_net.api_control_centre.posko_edit_scope";
  var qs = new URLSearchParams(location.search);

  function currentPosko() { return qs.get("id") || qs.get("posko") || ""; }
  function currentEvent() {
    var ev = qs.get("event") || qs.get("disaster_event_id");
    if (!ev) { try { ev = localStorage.getItem("rn_active_event"); } catch (e) {} }
    return String(ev || "event-sim-001").replace(/^disaster_events:/, "");
  }
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function hideOne(host) {
    if (host && !host.dataset.rnScopeHidden) {
      host.dataset.rnScopeHidden = "1";
      host.hidden = true;
      return true;
    }
    return false;
  }

  // When the posko opened cross-org participation, a non-manager member may
  // still SEND AID to it — keep just that one form (+ its wrapper) visible.
  function isCoordinationForm(el) {
    return el.id === "aidOfferPanel" ||
      (el.closest && el.closest("#aidOfferPanel")) ||
      (el.matches && el.matches("[data-rn-create-aid-offer]"));
  }

  function hideEditForms(keepCoordination) {
    var sels = [
      ".panel.create-panel",
      "[data-rn-create-logistic-need]",
      "[data-rn-create-aid-offer]",
      "[data-create-armada]",
      "[data-assign-form]",
      "[data-armada-add-btn]",
      "#armadaForm", "#armadaAddBtn",
      "#stockForm", "#transferForm",
      // posko-medis-detail / shelter-detail / dapur-umum record forms
      "#caseForm", "#supplyUseForm", "#occupancyForm", "#needForm", "#mealForm"
    ];
    var seen = 0;
    sels.forEach(function (sel) {
      document.querySelectorAll(sel).forEach(function (el) {
        // keep read-only drawers that only display data
        if (el.classList.contains("rn-stockcards-panel")) return;
        if (keepCoordination && isCoordinationForm(el)) return;
        var host;
        if (el.tagName === "FORM") {
          // a record form living inside a mixed "Riwayat" drawer: hide just the
          // form (or its <aside> wrapper), never the whole drawer, so the
          // read-only history stays visible.
          host = el.closest("aside") || el.closest(".panel.create-panel") || el;
        } else {
          host = el.closest(".panel") && !el.classList.contains("panel")
            ? el.closest(".panel") : el;
        }
        if (hideOne(host)) seen++;
      });
    });
    return seen;
  }

  function banner(scope) {
    if (document.getElementById("rnPoskoScopeBanner")) return;
    var main = document.querySelector("main.main") || document.querySelector("main") || document.body;
    var accent = (scope.brand && scope.brand.accent) || "#8a5a2a";
    var mine = (scope.my_poskos || [])[0];
    var b = document.createElement("div");
    b.id = "rnPoskoScopeBanner";
    b.setAttribute("style", [
      "margin:10px 0 4px", "padding:10px 14px", "border-radius:10px",
      "border:1px solid " + accent, "border-left:4px solid " + accent,
      "background:rgba(255,255,255,.75)", "font-size:13px", "color:#3a2c22",
      "display:flex", "gap:10px", "align-items:center", "flex-wrap:wrap"
    ].join(";"));
    var coord = !!scope.can_coordinate_current;
    b.innerHTML =
      '<b style="color:' + esc(accent) + '">' +
        (coord ? "Koordinasi" : "Hanya-lihat") + "</b>" +
      "<span>Anda melihat posko ini sebagai koordinasi lintas organisasi. " +
      (coord
        ? "Anda boleh mengirim bantuan ke posko ini; perubahan data internal hanya di posko Anda sendiri."
        : "Input &amp; perubahan data hanya di posko Anda sendiri.") +
      "</span>" +
      (mine
        ? '<a class="btn primary mini" href="' + esc(mine.operate_href) + '">Ke posko saya</a>'
        : "") +
      '<a class="btn ghost mini" href="' + esc(scope.coordination_href) + '">Koordinasi Organisasi</a>' +
      '<a class="btn ghost mini" href="' + esc(scope.control_centre_href) + '">Control Centre</a>';
    var firstSection = main.querySelector("section, .content-grid, .kpi-grid");
    if (firstSection) main.insertBefore(b, firstSection);
    else main.appendChild(b);
  }

  function applyReadOnly(scope) {
    banner(scope);
    hideEditForms();
    // page JS may render forms after us — sweep again a couple of times
    var tries = 0;
    var iv = setInterval(function () {
      hideEditForms();
      if (++tries >= 6) clearInterval(iv);
    }, 800);
  }

  async function run() {
    var pid = currentPosko();
    var ev = currentEvent();
    var scope;
    try {
      scope = await window.RN_FRAPPE.call(SCOPE, { posko: pid, disaster_event: ev });
    } catch (e) {
      return; // scope endpoint unavailable -> leave page as-is
    }
    if (!scope || !scope.logged_in || !scope.is_org_member) return;
    if (scope.is_system_manager) return;

    // 1. no posko chosen yet -> default to the member's own posko.
    //    Only on the generic posko workspaces; the type-specific detail pages
    //    (medis / shelter / dapur) keep whatever ?id= the nav gave them so a
    //    logistics operator is not bounced onto a medical posko with no data.
    var REDIRECT_PAGES = /\/(posko-logistik|posko-distribusi|posko-detail)\.html$/;
    if (!pid && scope.primary_posko && REDIRECT_PAGES.test(location.pathname)) {
      var u = new URLSearchParams(location.search);
      u.set("id", scope.primary_posko);
      if (!u.get("event")) u.set("event", ev);
      location.replace(location.pathname + "?" + u.toString());
      return;
    }

    // 2. viewing a posko the member does not manage -> read-only
    if (pid && scope.can_edit_current === false) {
      if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", function () { applyReadOnly(scope); });
      } else {
        applyReadOnly(scope);
      }
    }
  }

  run();
})();
