/* ============================================================
 * rn-item-groups.js — "Kelompok Barang (Normalisasi AI)" widget.
 * Mounts into #itemGroupPanel. Each canonical group rolls up to ONE
 * base unit (liter / kg / bungkus / …) and shows three honest numbers:
 *   Terukur      — trusted conversion (isi eksplisit / tabel standar / satuan dasar)
 *   Perkiraan AI — fuzzy conversion or estimate/range input
 *   Belum terukur— rows with no usable number / kemasan tidak baku
 * Click a row to drill to the member records, where the receiving posko
 * can correct the normalisation (ubah satuan/kemasan, isi per dus,
 * kuantitas dasar, pindah kelompok, jadikan satu).
 * Endpoints: rescue_net.api_logistics.item_groups /
 * item_group_members / correct_item_normalization (login for the write).
 * ============================================================ */
(function () {
  "use strict";
  var PANEL = "#itemGroupPanel";
  if (!document.querySelector(PANEL)) return;

  var $ = function (s, r) { return (r || document).querySelector(s); };
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function fmt(n) {
    var v = Number(n || 0);
    return (Math.round(v * 100) / 100).toLocaleString("id-ID");
  }
  var qs = new URLSearchParams(location.search);
  function getPosko() { return qs.get("id") || qs.get("posko") || ""; }
  function getEvent() { return qs.get("event") || "event-sim-001"; }

  var CACHE = null;

  function srcLabel(s) {
    return { manual: "Manual (dikoreksi)", ai: "AI", rule: "Aturan", tidak_diketahui: "Belum" }[s] || s;
  }
  function convBadge(src, status) {
    var s = String(status || "ok").toLowerCase();
    if (s === "unmeasurable") return '<span class="chip warning">belum terukur</span>';
    if (s === "needs_review") return '<span class="chip warning">konversi perkiraan</span>';
    var map = { explicit: "isi eksplisit", table: "tabel", direct: "satuan dasar", manual: "manual", heuristic: "heuristik", none: "—" };
    return '<span class="chip ok">' + esc(map[String(src || "none")] || src) + "</span>";
  }

  function ensureModal() {
    if ($("#rnIgModal")) return;
    var d = document.createElement("div");
    d.id = "rnIgModal";
    d.className = "rn-ba-modal";
    d.hidden = true;
    d.innerHTML =
      '<div class="rn-ba-modal-backdrop" data-ig-close></div>' +
      '<div class="rn-ba-modal-card" role="dialog" aria-modal="true">' +
      '<div class="rn-ba-modal-head"><div><h3 id="rnIgTitle">-</h3>' +
      '<p id="rnIgSub" class="rn-muted"></p></div>' +
      '<button type="button" class="rn-ba-modal-close" data-ig-close>×</button></div>' +
      '<div class="rn-ba-modal-body" id="rnIgBody"></div></div>';
    document.body.appendChild(d);
    d.addEventListener("click", function (e) {
      if (e.target.closest("[data-ig-close]")) closeModal();
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && !d.hidden) closeModal();
    });
  }
  function closeModal() { var m = $("#rnIgModal"); if (m) m.hidden = true; document.body.style.overflow = ""; }

  function render(data) {
    CACHE = data;
    var groups = data.groups || [];
    var host = $(PANEL);
    var rows = groups.length
      ? groups.map(function (g, i) {
          var u = esc(g.base_unit || g.unit);
          var review = g.needs_review
            ? '<span class="chip warning">' + fmt(g.needs_review) + " kelompok?</span>"
            : '<span class="chip ok">ok</span>';
          var convR = g.conversion_review
            ? ' <span class="chip warning">' + fmt(g.conversion_review) + " konversi?</span>"
            : "";
          var est = g.estimated_member_count
            ? fmt(g.qty_estimated) + " " + u
            : '<span class="rn-muted">—</span>';
          var unmeas = g.unmeasurable_count
            ? '<span class="chip warning">' + fmt(g.unmeasurable_count) + " catatan</span>"
            : '<span class="rn-muted">—</span>';
          return (
            '<tr class="rn-ba-row" data-ig-idx="' + i + '">' +
            "<td><b>" + esc(g.group) + "</b>" +
              (g.classified ? "" : ' <span class="chip">tak terklasifikasi</span>') + "</td>" +
            "<td>" + u + "</td>" +
            "<td><b>" + fmt(g.qty_measurable) + "</b> " + u + "</td>" +
            "<td>" + est + "</td>" +
            "<td><b>" + fmt(g.qty_total) + "</b> " + u + "</td>" +
            "<td>" + unmeas + "</td>" +
            "<td>" + fmt(g.member_count) + " · " + fmt(g.posko_spread) + " posko</td>" +
            "<td>" + review + convR + '<br><small class="rn-muted">' + esc(srcLabel(g.source)) + "</small></td>" +
            "</tr>"
          );
        }).join("")
      : '<tr><td colspan="8"><em class="rn-muted">Belum ada barang untuk dikelompokkan.</em></td></tr>';

    host.querySelector("[data-ig-body]").innerHTML = rows;
    host.querySelectorAll("tr[data-ig-idx]").forEach(function (tr) {
      tr.addEventListener("click", function () { openGroup(groups[Number(tr.getAttribute("data-ig-idx"))]); });
    });
    var note = host.querySelector("[data-ig-note]");
    if (note) note.textContent = data.method_note || "";
  }

  function memberRowHtml(m, idx) {
    var rawU = esc(m.unit || m.unit_canonical || "");
    var rawQty = m.quantity != null
      ? fmt(m.quantity) + " " + rawU
      : (m.quantity_min != null ? fmt(m.quantity_min) + "–" + fmt(m.quantity_max) + " " + rawU : "-");
    var baseTxt = (m.base_quantity != null && m.base_quantity !== "")
      ? "<b>" + fmt(m.base_quantity) + "</b> " + esc(m.base_unit || "")
      : '<span class="rn-muted">belum terukur</span>';
    var bucket = { terukur: '<span class="chip ok">terukur</span>',
                   perkiraan: '<span class="chip warning">perkiraan</span>',
                   belum_terukur: '<span class="chip warning">belum terukur</span>' }[m.measured_bucket] || "";
    return (
      '<div class="rn-ig-mem" data-ig-mem="' + idx + '">' +
      '<div class="rn-ig-mem-head">' +
        "<span><b>" + esc(m.posko_title || "-") + "</b> · " + esc(m.kind) + "</span>" +
        bucket + convBadge(m.conversion_source, m.conversion_status) +
        '<span class="chip">' + esc(srcLabel(m.normalization_source)) +
          (m.normalization_confidence ? " " + m.normalization_confidence + "%" : "") + "</span>" +
        '<span class="chip ' + (m.normalization_status === "accepted" ? "ok" : "warning") + '">' +
          (m.normalization_status === "accepted" ? "diterima" : "usulan") + "</span>" +
      "</div>" +
      '<div class="rn-ig-mem-body">' +
        "<span>Teks asli: <i>" + esc(m.raw_text || m.item_name) + "</i></span>" +
        "<span>Input: <b>" + rawQty + "</b>" +
          (m.pack_size ? ' <small class="rn-muted">(isi/kemasan ' + fmt(m.pack_size) + ")</small>" : "") + "</span>" +
        "<span>Terukur (dasar): " + baseTxt + "</span>" +
        (m.estimate_text ? '<span class="rn-muted">catatan estimasi: ' + esc(m.estimate_text) + "</span>" : "") +
        '<button type="button" class="btn mini rn-ig-fix-toggle">Koreksi</button>' +
      "</div>" +
      '<form class="rn-ig-fix" hidden>' +
        '<label>Satuan / kemasan <input name="unit" value="' + esc(m.unit || m.unit_canonical) + '"></label>' +
        '<label>Isi per kemasan <input name="pack_size" type="number" step="any" placeholder="mis. 24 (bh per dus)"></label>' +
        '<label>Kuantitas dasar (' + esc(m.base_unit || "dasar") + ') <input name="base_quantity" type="number" step="any" placeholder="isi manual bila tahu pastinya"></label>' +
        '<label>Pindah ke kelompok <input name="canonical_group" value="' + esc(m.canonical_group) + '" placeholder="mis. Air Minum"></label>' +
        '<label class="rn-ig-fix-chk"><input type="checkbox" name="make_exact"' + (m.measured_bucket === "terukur" ? " checked disabled" : "") + '> Tandai kuantitas akurat</label>' +
        '<label>Catatan <input name="note" placeholder="alasan koreksi (opsional)"></label>' +
        '<div class="rn-ig-fix-actions">' +
          '<button type="submit" class="btn primary mini">Simpan koreksi</button>' +
          '<span class="rn-ig-fix-msg"></span></div>' +
      "</form>" +
      "</div>"
    );
  }

  async function openGroup(g) {
    if (!g) return;
    ensureModal();
    var u = g.base_unit || g.unit;
    $("#rnIgTitle").textContent = g.group + " · " + u;
    $("#rnIgSub").textContent = "Terukur " + fmt(g.qty_measurable) + " " + u +
      (g.estimated_member_count ? " + perkiraan AI " + fmt(g.qty_estimated) + " " + u : "") +
      (g.unmeasurable_count ? " · " + fmt(g.unmeasurable_count) + " belum terukur" : "") +
      " · " + fmt(g.member_count) + " catatan";
    $("#rnIgBody").innerHTML = '<p class="rn-muted">Memuat rincian…</p>';
    $("#rnIgModal").hidden = false;
    document.body.style.overflow = "hidden";

    var data;
    try {
      data = await window.RN_FRAPPE.call("rescue_net.api_logistics.item_group_members", {
        group: g.group, unit: u,
        disaster_event: getEvent(),
        posko: getPosko() || undefined,
      });
    } catch (err) {
      $("#rnIgBody").innerHTML = '<p class="rn-muted">Gagal memuat: ' + esc(err && err.message || err) + "</p>";
      return;
    }
    var members = data.members || [];
    var mergeBar =
      '<div class="rn-ig-merge">' +
      "<span>Gabungkan semua " + fmt(members.length) + " catatan ke satu kelompok:</span>" +
      '<input id="rnIgMergeName" value="' + esc(g.group) + '">' +
      '<button type="button" class="btn mini" id="rnIgMergeBtn">Jadikan Satu</button>' +
      '<span id="rnIgMergeMsg" class="rn-muted"></span></div>';
    $("#rnIgBody").innerHTML =
      mergeBar +
      (members.length
        ? members.map(memberRowHtml).join("")
        : '<p class="rn-muted">Tidak ada catatan.</p>');

    // wire per-member correction
    $("#rnIgBody").querySelectorAll(".rn-ig-mem").forEach(function (el) {
      var m = members[Number(el.getAttribute("data-ig-mem"))];
      var form = el.querySelector(".rn-ig-fix");
      el.querySelector(".rn-ig-fix-toggle").addEventListener("click", function () { form.hidden = !form.hidden; });
      form.addEventListener("submit", async function (e) {
        e.preventDefault();
        var msg = form.querySelector(".rn-ig-fix-msg");
        msg.textContent = "Menyimpan…";
        try {
          await window.RN_FRAPPE.call("rescue_net.api_logistics.correct_item_normalization", {
            doctype: m.doctype, name: m.name,
            unit: form.unit.value.trim() || undefined,
            pack_size: form.pack_size.value.trim() || undefined,
            base_quantity: form.base_quantity.value.trim() || undefined,
            canonical_group: form.canonical_group.value.trim(),
            quantity_mode: form.make_exact.checked ? "exact" : undefined,
            note: form.note.value.trim() || undefined,
          }, { method: "POST" });
          msg.textContent = "OK";
          await openGroup(g);            // refresh drill
          load();                        // refresh table
        } catch (err) {
          var t = (err && err.message) || String(err);
          msg.textContent = "Gagal: " + t + (/login|permission|akses|berhak/i.test(t) ? " (perlu login sbg posko)" : "");
        }
      });
    });

    // wire merge
    var mb = $("#rnIgMergeBtn");
    if (mb) mb.addEventListener("click", async function () {
      var name = ($("#rnIgMergeName").value || "").trim();
      var mm = $("#rnIgMergeMsg");
      if (!name) { mm.textContent = "isi nama kelompok"; return; }
      if (!members.length) return;
      mm.textContent = "Menggabungkan…";
      try {
        var primary = members[0];
        await window.RN_FRAPPE.call("rescue_net.api_logistics.correct_item_normalization", {
          doctype: primary.doctype, name: primary.name,
          canonical_group: name, canonical_item: name,
          also_apply: JSON.stringify(members.slice(1).map(function (x) {
            return { doctype: x.doctype, name: x.name };
          })),
        }, { method: "POST" });
        mm.textContent = "Digabung ✓";
        load();
        closeModal();
      } catch (err) {
        var t = (err && err.message) || String(err);
        mm.textContent = "Gagal: " + t + (/login|permission|akses|berhak/i.test(t) ? " (perlu login sbg posko)" : "");
      }
    });
  }

  async function load() {
    try {
      var data = await window.RN_FRAPPE.call("rescue_net.api_logistics.item_groups", {
        disaster_event: getEvent(),
        posko: getPosko() || undefined,
      });
      render(data);
    } catch (err) {
      var b = $(PANEL + " [data-ig-body]");
      if (b) b.innerHTML = '<tr><td colspan="8"><em class="rn-muted">Gagal memuat kelompok barang: ' +
        esc(err && err.message || err) + "</em></td></tr>";
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    if (!window.RN_FRAPPE) return;
    load();
  });
})();
