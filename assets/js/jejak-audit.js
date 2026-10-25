/* Jejak Audit (2026-10-26): rescue_net.api_audit.audit_trail — System
   Manager & Control Centre. Read-only. */
(function () {
  "use strict";
  var $ = function (id) { return document.getElementById(id); };
  var esc = function (s) { return window.RNUI ? window.RNUI.esc(s) : String(s == null ? "" : s); };
  var loadedTypes = false;

  function changesHtml(r) {
    if (r.kind === "buat" && !r.changes.length) return '<span class="chip">dibuat</span>';
    if (!r.changes.length) return '<span class="rn-muted">—</span>';
    return r.changes.slice(0, 12).map(function (c) {
      return "<div><b>" + esc(c.field) + "</b>" + (c.old || c.new ? ": " + esc(c.old) + " → " + esc(c.new) : "") + "</div>";
    }).join("") + (r.changes.length > 12 ? '<div class="rn-muted">+' + (r.changes.length - 12) + " perubahan lain</div>" : "");
  }

  async function load() {
    var f = $("auFilter");
    $("auStatus").textContent = "Memuat…";
    try {
      var res = await window.RN_FRAPPE.call("rescue_net.api_audit.audit_trail", {
        doctype: f.doctype.value || undefined, user: f.user.value.trim() || undefined,
        docname: f.docname.value.trim() || undefined, days: f.days.value,
      });
      if (!loadedTypes) {
        loadedTypes = true;
        $("auDoctype").insertAdjacentHTML("beforeend", (res.doctypes || []).map(function (d) {
          return '<option value="' + esc(d.id) + '">' + esc(d.label) + "</option>";
        }).join(""));
      }
      var rows = res.rows || [];
      $("auCount").textContent = rows.length;
      $("auBody").innerHTML = rows.length ? rows.map(function (r) {
        return "<tr><td>" + esc(r.at) + "</td><td>" + esc(r.user_name) + "<br><small class=\"rn-muted\">" + esc(r.user) + "</small></td>" +
          "<td><b>" + esc(r.doctype_label) + "</b><br>" + esc(r.title) + "<br><small class=\"rn-muted\">" + esc(r.docname) + "</small></td>" +
          "<td>" + changesHtml(r) + "</td></tr>";
      }).join("") : '<tr><td colspan="4" class="rn-muted">Belum ada perubahan tercatat di periode ini.</td></tr>';
      $("auStatus").textContent = rows.length + " perubahan dalam " + res.days + " hari terakhir.";
    } catch (e) {
      $("auBody").innerHTML = '<tr><td colspan="4" class="rn-muted">' + esc((e && e.message) || e) + "</td></tr>";
      $("auStatus").textContent = "Tidak bisa memuat. Halaman ini khusus System Manager dan Control Centre — masuk dengan akun tersebut.";
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    $("auFilter").addEventListener("submit", function (e) { e.preventDefault(); load(); });
    load();
  });
})();
