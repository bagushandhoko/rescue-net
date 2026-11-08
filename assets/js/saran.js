/* Menu Saran (owner 2026-11-03): kirim saran tanpa login + daftar saran publik.
   Kontak pengirim hanya terlihat super admin; status hanya diubah super admin. */
(function () {
  "use strict";
  var API = "rescue_net.api_saran.";
  var STATUS_LABEL = { baru: "Baru", ditinjau: "Ditinjau", dikerjakan: "Dikerjakan", selesai: "Selesai", disembunyikan: "Disembunyikan" };
  var filter = "";
  var canModerate = false;

  function $(id) { return document.getElementById(id); }
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function clean(err) {
    var m = (err && err.message) || "Gagal. Coba lagi.";
    try {
      var sm = err.payload && err.payload._server_messages;
      if (sm) { m = JSON.parse(JSON.parse(sm)[0]).message || m; }
    } catch (e) {}
    m = String(m).replace(/^.*?(ValidationError|PermissionError):\s*/, "");
    if (/rate|too many|429/i.test(m) || (err && err.status === 429)) m = "Terlalu banyak saran dalam waktu singkat. Coba lagi beberapa menit lagi.";
    return m;
  }
  function msg(text, cls) { var el = $("saranMsg"); el.textContent = text; el.className = "rn-saran-msg " + (cls || ""); }
  function fmtDate(s) {
    if (!s) return "";
    var d = new Date(String(s).replace(" ", "T"));
    return isNaN(d) ? "" : d.toLocaleDateString("id-ID", { day: "numeric", month: "short", year: "numeric" });
  }

  function renderFilters(counts) {
    var keys = ["", "baru", "ditinjau", "dikerjakan", "selesai"].concat(canModerate ? ["disembunyikan"] : []);
    var total = 0;
    Object.keys(counts || {}).forEach(function (k) { if (k !== "disembunyikan") total += counts[k] || 0; });
    $("saranFilters").innerHTML = keys.map(function (k) {
      var n = k ? (counts[k] || 0) : total;
      return '<button type="button" data-st="' + k + '" aria-pressed="' + (k === filter) + '">' + (k ? STATUS_LABEL[k] : "Semua") + " (" + n + ")</button>";
    }).join("");
    $("saranCount").textContent = "— " + total + " saran";
  }

  function itemHtml(s) {
    var mod = "";
    if (canModerate) {
      mod = '<div class="rn-saran-actions" data-name="' + esc(s.name) + '">' +
        '<select aria-label="Status">' + Object.keys(STATUS_LABEL).map(function (k) {
          return '<option value="' + k + '"' + (k === s.status ? " selected" : "") + ">" + STATUS_LABEL[k] + "</option>";
        }).join("") + "</select>" +
        '<input type="text" placeholder="Tanggapan (opsional)" aria-label="Tanggapan" style="flex:1;min-width:140px">' +
        '<button type="button" class="btn mini" data-act="status">Simpan</button></div>' +
        (s.author_contact ? '<div class="rn-saran-meta">Kontak (hanya admin): ' + esc(s.author_contact) + "</div>" : "");
    }
    return '<div class="rn-saran-item">' +
      '<div class="rn-saran-meta"><span class="rn-saran-chip st-' + esc(s.status) + '">' + esc(STATUS_LABEL[s.status] || s.status) + "</span>" +
      '<span class="rn-saran-chip">' + esc(s.category_label) + "</span>" +
      (s.page ? "<span>Halaman: " + esc(s.page) + "</span>" : "") + "</div>" +
      "<h4>" + esc(s.title) + "</h4><p>" + esc(s.body) + "</p>" +
      (s.response ? '<div class="rn-saran-resp"><b>Tanggapan pengelola:</b> ' + esc(s.response) + "</div>" : "") +
      '<div class="rn-saran-meta"><span>' + esc(s.author_name) + " · " + esc(fmtDate(s.created)) + "</span>" +
      '<button type="button" class="btn mini" data-act="support" data-name="' + esc(s.name) + '">👍 Dukung (' + (s.upvotes || 0) + ")</button></div>" +
      mod + "</div>";
  }

  async function load() {
    try {
      var out = await window.RN_FRAPPE.call(API + "list_suggestions", filter ? { status: filter } : {});
      out = out && out.message !== undefined ? out.message : out;
      canModerate = !!out.can_moderate;
      renderFilters(out.counts);
      var rows = out.suggestions || [];
      $("saranList").innerHTML = rows.length ? rows.map(itemHtml).join("") : '<p class="rn-muted">Belum ada saran di sini.</p>';
    } catch (e) {
      $("saranList").innerHTML = '<p class="rn-muted">Daftar saran belum bisa dimuat: ' + esc(clean(e)) + "</p>";
    }
  }

  function boot() {
    try {
      var ref = document.referrer ? new URL(document.referrer) : null;
      if (ref && ref.origin === location.origin && !/saran\.html/.test(ref.pathname)) {
        $("saranPage").value = (ref.pathname.split("/").pop() || "").replace(/\.html$/, "");
      }
    } catch (e) {}

    $("saranForm").addEventListener("submit", async function (e) {
      e.preventDefault();
      var f = e.target.elements;
      var body = (f.body.value || "").trim();
      if (body.length < 10) { msg("Tulis saran minimal 10 huruf.", "err"); f.body.focus(); return; }
      var btn = e.target.querySelector('button[type="submit"]');
      btn.disabled = true; msg("Mengirim…");
      try {
        await window.RN_FRAPPE.call(API + "submit_suggestion", {
          body: body, category: f.category.value, title: f.title.value.trim(), page: f.page.value.trim(),
          author_name: f.author_name.value.trim(), author_contact: f.author_contact.value.trim(), website: f.website.value
        }, { method: "POST" });
        e.target.reset();
        msg("Terima kasih! Saran Anda tersimpan dan tampil di daftar.", "ok");
        filter = ""; load();
      } catch (err) {
        msg(clean(err), "err");
      }
      btn.disabled = false;
    });

    $("saranFilters").addEventListener("click", function (e) {
      var b = e.target.closest("button[data-st]");
      if (!b) return;
      filter = b.getAttribute("data-st"); load();
    });

    $("saranList").addEventListener("click", async function (e) {
      var b = e.target.closest("button[data-act]");
      if (!b) return;
      b.disabled = true;
      try {
        if (b.getAttribute("data-act") === "support") {
          var r = await window.RN_FRAPPE.call(API + "support_suggestion", { suggestion: b.getAttribute("data-name") }, { method: "POST" });
          r = r && r.message !== undefined ? r.message : r;
          b.textContent = "👍 Dukung (" + (r.upvotes || 0) + ")";
          return;
        }
        var box = b.closest(".rn-saran-actions");
        await window.RN_FRAPPE.call(API + "set_suggestion_status", {
          suggestion: box.getAttribute("data-name"), status: box.querySelector("select").value,
          response: box.querySelector("input").value.trim()
        }, { method: "POST" });
        load();
      } catch (err) {
        alert(clean(err));
      } finally {
        b.disabled = false;
      }
    });
    load();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();
