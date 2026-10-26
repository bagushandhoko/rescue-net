/* Scenario Tested (owner 2026-10-26): renders assets/data/scenario-tested.json.
   Add every new test run to that file (newest first). */
(function () {
  "use strict";
  var $ = function (id) { return document.getElementById(id); };
  var esc = function (s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return "&#" + c.charCodeAt(0) + ";"; }); };
  var STATUS = { "lulus": ["Lulus", "st-ok"], "lulus-perbaikan": ["Lulus setelah perbaikan", "st-fix"], "rencana": ["Rencana", "st-plan"] };
  var DATA = null, CAT = "";

  function card(u) {
    var st = STATUS[u.status] || [u.hasil, "st-plan"];
    return '<section class="st-card" id="uji-' + esc(u.id) + '">' +
      '<div class="st-meta"><span class="st-chip ' + st[1] + '">' + esc(st[0]) + "</span><span>" + esc(u.id) + "</span><span>" + esc(u.tanggal) +
      "</span><span>" + esc(u.kategori) + "</span>" + (u.skor && u.skor !== "-" ? "<span>Skor: " + esc(u.skor) + "</span>" : "") + "</div>" +
      "<h3>" + esc(u.judul) + "</h3><p>" + esc(u.tujuan) + "</p>" +
      (u.akun && u.akun.length ? "<p><b>Akun:</b> " + u.akun.map(esc).join(", ") + "</p>" : "") +
      "<b>Langkah</b><ol>" + (u.langkah || []).map(function (l) { return "<li>" + esc(l) + "</li>"; }).join("") + "</ol>" +
      ((u.temuan || []).length ? "<b>Temuan & perbaikan</b>" + u.temuan.map(function (t) {
        return '<div class="st-find"><b>' + esc(t.masalah) + "</b>→ " + esc(t.perbaikan) + "</div>";
      }).join("") : "") + "</section>";
  }

  function render() {
    var rows = DATA.uji.filter(function (u) { return !CAT || u.kategori === CAT; });
    $("stList").innerHTML = rows.map(card).join("") || "<p>Belum ada uji di kategori ini.</p>";
  }

  fetch("../assets/data/scenario-tested.json?v=" + Date.now().toString().slice(0, -5))
    .then(function (r) { return r.json(); })
    .then(function (d) {
      DATA = d;
      $("stUpdated").textContent = d.diperbarui || "-";
      var finds = d.uji.reduce(function (n, u) { return n + (u.temuan || []).length; }, 0);
      var ok = d.uji.filter(function (u) { return u.status !== "rencana"; }).length;
      $("stSum").innerHTML = "<div><b>" + d.uji.length + "</b>skenario diuji</div><div><b>" + ok + "</b>lulus</div><div><b>" + finds +
        "</b>temuan & perbaikan</div><div><b>" + (d.rencana || []).length + "</b>rencana uji</div>";
      var cats = Array.from(new Set(d.uji.map(function (u) { return u.kategori; })));
      $("stFilters").innerHTML = ['<button type="button" class="is-on" data-cat="">Semua</button>'].concat(cats.map(function (c) {
        return '<button type="button" data-cat="' + esc(c) + '">' + esc(c) + "</button>";
      })).join("");
      $("stFilters").addEventListener("click", function (e) {
        var b = e.target.closest("[data-cat]"); if (!b) return;
        CAT = b.dataset.cat;
        $("stFilters").querySelectorAll("button").forEach(function (x) { x.classList.toggle("is-on", x === b); });
        render();
      });
      $("stPlan").innerHTML = (d.rencana || []).map(function (r) { return "<li><b>" + esc(r.id) + "</b> — " + esc(r.judul) + "</li>"; }).join("");
      render();
    })
    .catch(function () { $("stList").innerHTML = "<p>Gagal memuat data uji.</p>"; });
})();
