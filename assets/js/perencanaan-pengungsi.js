/* Perencanaan Pengungsi — api_displacement.* */
(function () {
  "use strict";
  var A = "rescue_net.api_displacement.";
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var qs = new URLSearchParams(location.search);
  function getEvent() { return qs.get("event") || "event-sim-001"; }
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function rp(n) {
    n = Number(n || 0);
    return n ? "Rp " + n.toLocaleString("id-ID") : "-";
  }
  function n(x) { return Number(x || 0).toLocaleString("id-ID"); }

  async function load() {
    var d;
    try {
      d = await window.RN_FRAPPE.call(A + "displacement_board", { disaster_event: getEvent() });
    } catch (e) {
      $("#dpStatus").textContent = "Gagal memuat: " + (e && e.message || e);
      return;
    }
    var t = d.totals || {};
    $("#kpiKK").textContent = n(t.household_count);
    $("#kpiJiwa").textContent = n(t.people_total);
    $("#kpiNonCamp").textContent = n(t.non_camp);
    $("#kpiRentan").textContent = n((t.orphan_households || 0) + (t.needs_care_households || 0));
    $("#kpiDana").textContent = rp(t.est_dana_total);
    $("#dpStatus").textContent = t.household_count + " KK terencana · " + t.people_total + " jiwa · " +
      t.non_camp + " non-camp.";
    $("#dpCount").textContent = (d.plans || []).length + " KK";

    var body = $("#dpBody");
    body.innerHTML = (d.plans || []).length ? d.plans.map(function (p) {
      return "<tr>" +
        "<td><b>" + esc(p.household_code || "-") + "</b><small class=\"rn-muted\">" + esc(p.origin_area || "-") + "</small></td>" +
        "<td>" + esc(p.current_location || "-") + (p.in_camp ? "" : ' <span class="chip warning">non-camp</span>') + "</td>" +
        "<td>" + n(p.people_count) + (p.vulnerable_count ? " <small class=\"rn-muted\">(" + p.vulnerable_count + " rentan)</small>" : "") + "</td>" +
        "<td>" + esc(p.health_label) + "</td>" +
        "<td>" + esc(p.plan_label) + "</td>" +
        "<td>" + rp(p.est_total) + "</td>" +
        '<td><span class="chip neutral">' + esc(p.status_label) + "</span></td>" +
        "</tr>";
    }).join("") : '<tr><td colspan="7"><em class="rn-muted">Belum ada rencana. Tambahkan lewat form di bawah.</em></td></tr>';

    var pb = t.people_by_plan || {};
    $("#dpRollup").innerHTML =
      row("Kembali ke asal", t.return_home + " KK · " + n(pb.return_home) + " jiwa") +
      row("Relokasi", t.relocate + " KK · " + n(pb.relocate) + " jiwa") +
      row("Belum diputuskan", t.undecided + " KK · " + n(pb.undecided) + " jiwa") +
      row("Estimasi dana total", rp(t.est_dana_total)) +
      row("Yatim piatu (KK)", n(t.orphan_households)) +
      row("Perlu perawatan (KK)", n(t.needs_care_households));
  }
  function row(k, v) { return "<div><span>" + esc(k) + "</span><b>" + esc(v) + "</b></div>"; }

  function wireForm() {
    var form = $("#dpForm");
    if (!form) return;
    var msg = form.querySelector("[data-dp-msg]");
    form.addEventListener("submit", async function (e) {
      e.preventDefault();
      var fd = new FormData(form);
      msg.textContent = "Menyimpan…";
      try {
        await window.RN_FRAPPE.call(A + "create_displacement_plan", {
          disaster_event: fd.get("disaster_event"),
          household_code: fd.get("household_code") || null,
          origin_area: fd.get("origin_area"),
          current_location: fd.get("current_location") || null,
          people_count: fd.get("people_count"),
          vulnerable_count: fd.get("vulnerable_count") || 0,
          in_camp: fd.get("in_camp"),
          health_status: fd.get("health_status"),
          plan_type: fd.get("plan_type"),
          est_return_cost: fd.get("est_return_cost") || 0,
          est_rebuild_support: fd.get("est_rebuild_support") || 0,
          support_needed: fd.get("support_needed") || null,
          notes: fd.get("notes") || null,
        }, { method: "POST" });
        msg.textContent = "Tersimpan.";
        form.reset();
        await load();
      } catch (err) {
        var m = (err && err.message) || String(err);
        msg.textContent = "Gagal: " + m + (/login|diperlukan|permission/i.test(m) ? " (perlu login)" : "");
      }
    });
  }

  if (document.readyState === "loading")
    document.addEventListener("DOMContentLoaded", function () { wireForm(); load(); });
  else { wireForm(); load(); }
})();
