/* status-akses.js — status akses & infrastruktur (Fase 10e).
 * Publik: ringkasan + tempat tertutup/terbatas (api_access_status.board). Login: form lapor, daftar lengkap, verifikasi. */
(function () {
  "use strict";
  var $ = function (id) { return document.getElementById(id); };
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return "&#" + c.charCodeAt(0) + ";"; }); }
  function msg(el, text, kind) { el.textContent = text; el.className = "ak-msg " + (kind || ""); }
  function errText(e) { return String((e && (e.message || e.exception)) || e || "gagal").replace(/<[^>]+>/g, "").slice(0, 200); }
  var STATUS = { closed: "Tertutup", limited: "Terbatas", open: "Terbuka", unknown: "Tidak diketahui" };
  var C = function () { return window.RN_FRAPPE; };

  function age(h) { return h < 1 ? "baru saja" : h < 48 ? h + " jam lalu" : Math.round(h / 24) + " hari lalu"; }

  function loadBoard() {
    var ev = $("akEvent").value; if (!ev) return;
    C().call("rescue_net.api_access_status.board", { disaster_event: ev }).then(function (b) {
      $("akSummary").innerHTML = b.summary.map(function (s) {
        return "<li><b>" + esc(s.label) + "</b><span>tertutup " + s.closed + " · terbatas " + s.limited + " · terbuka " + s.open + " · tak diketahui " + s.unknown + "</span></li>";
      }).join("");
      $("akItems").innerHTML = b.items.map(function (i) {
        return "<li><span><b>" + esc(i.label) + "</b> " + esc(i.place_name) + (i.segment ? " <span class='ak-muted'>(" + esc(i.segment) + ")</span>" : "") +
          "</span><span>" + esc(STATUS[i.status]) + " · " + esc(age(i.age_hours)) + (i.verified ? " ✓" : " <span class='ak-muted'>belum diverifikasi</span>") + "</span></li>";
      }).join("");
      msg($("akPubMsg"), b.summary.length ? "" : "Belum ada laporan akses untuk bencana ini.", "warn");
    }).catch(function (e) { msg($("akPubMsg"), errText(e), "err"); });
    loadMine();
  }

  function loadMine() {
    C().call("rescue_net.api_access_status.list_status", { disaster_event: $("akEvent").value }).then(function (r) {
      $("akMine").innerHTML = r.rows.map(function (x) {
        var v = x.verification_status === "verified" ? " ✓" : " <button class='ak-btn alt' data-v='" + esc(x.name) + "'>Verifikasi</button>";
        return "<li><span><b>" + esc(x.place_name) + "</b> · " + esc(STATUS[x.effective_status]) + (x.stale ? " (basi)" : "") + "</span><span>" + esc(age(x.age_hours)) + v + "</span></li>";
      }).join("");
    }).catch(function () { $("akMine").innerHTML = ""; });  // tamu: bagian ini tidak tersedia
  }

  document.addEventListener("DOMContentLoaded", function () {
    var sel = $("akEvent"), q = new URLSearchParams(location.search).get("event");
    C().call("rescue_net.api_events.disasters", {}).then(function (r) {
      sel.innerHTML = r.disasters.map(function (d) { return "<option value='" + esc(d.frappe_name) + "'>" + esc(d.title) + "</option>"; }).join("");
      if (q) sel.value = q;
      loadBoard();
    });
    sel.addEventListener("change", loadBoard);
    $("akSend").addEventListener("click", function () {
      var args = { disaster_event: sel.value, kind: $("akKind").value, status: $("akStatus").value, place_name: $("akPlace").value,
        segment: $("akSegment").value, posko: $("akPosko").value, valid_hours: $("akHours").value, note: $("akNote").value };
      C().call("rescue_net.api_access_status.report", args, { method: "POST" }).then(function () {
        msg($("akMsg"), "Laporan tercatat.", "ok"); $("akPlace").value = ""; loadBoard();
      }).catch(function (e) { msg($("akMsg"), errText(e), "err"); });
    });
    $("akMine").addEventListener("click", function (e) {
      var b = e.target.closest("button[data-v]"); if (!b) return;
      C().call("rescue_net.api_access_status.verify", { name: b.dataset.v }, { method: "POST" }).then(loadBoard)
        .catch(function (er) { msg($("akMsg"), errText(er), "err"); });
    });
  });
})();
