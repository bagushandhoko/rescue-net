/* ============================================================
 * rn-item-groups.js — "Kelompok Barang (Normalisasi AI)" widget.
 * Mounts into #itemGroupPanel. Shows each canonical group with the
 * ACCURATE quantity and the AI ESTIMATE side by side; click a row to
 * drill to the member records, where the receiving posko can correct
 * the normalisation (ubah satuan/kemasan, pindah kelompok, jadikan
 * akurat, atau gabungkan jadi satu).
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
  function fmt(n) { return Number(n || 0).toLocaleString("id-ID"); }
  var qs = new URLSearchParams(location.search);
  function getPosko() { return qs.get("id") || qs.get("posko") || ""; }
  function getEvent() { return qs.get("event") || "event-sim-001"; }

  var CACHE = null;

  function modeBadge(m, isEst) {
    var l = String(m || "").toLowerCase();
    if (l === "range") return '<span class="chip warning">Range AI</span>';
    if (l === "estimated" || l === "estimate" || isEst) return '<span class="chip warning">Perkiraan AI</span>';
    return '<span class="chip ok">Akurat</span>';
  }
  function srcLabel(s) {
    return { manual: "Manual (dikoreksi)", ai: "AI", rule: "Aturan", tidak_diketahui: "Belum" }[s] || s;
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
          var review = g.needs_review
            ? '<span class="chip warning">' + fmt(g.needs_review) + " perlu review</span>"
            : '<span class="chip ok">ok</span>';
          var showRange = g.est_range && g.est_range[0] !== g.est_range[1];
          var est = g.estimate_member_count
            ? fmt(g.qty_estimated) + " " + esc(g.unit) +
              (showRange ? ' <small class="rn-muted">(total ' + fmt(g.est_range[0]) + "–" + fmt(g.est_range[1]) + ")</small>" : "")
            : '<span class="rn-muted">—</span>';
          return (
            '<tr class="rn-ba-row" data-ig-idx="' + i + '">' +
            "<td><b>" + esc(g.group) + "</b>" +
              (g.classified ? "" : ' <span class="chip">tak terklasifikasi</span>') + "</td>" +
            "<td>" + esc(g.unit) + "</td>" +
            "<td><b>" + fmt(g.qty_exact) + "</b> " + esc(g.unit) + "</td>" +
            "<td>" + est + "</td>" +
            "<td><b>" + fmt(g.qty_total) + "</b> " + esc(g.unit) + "</td>" +
            "<td>" + fmt(g.member_count) + " · " + fmt(g.posko_spread) + " posko</td>" +
            "<td>" + review + '<small class="rn-muted">' + esc(srcLabel(g.source)) + "</small></td>" +
            "</tr>"
          );
        }).join("")
      : '<tr><td colspan="7"><em class="rn-muted">Belum ada barang untuk dikelompokkan.</em></td></tr>';

    host.querySelector("[data-ig-body]").innerHTML = rows;
    host.querySelectorAll("tr[data-ig-idx]").forEach(function (tr) {
      tr.addEventListener("click", function () { openGroup(groups[Number(tr.getAttribute("data-ig-idx"))]); });
    });
    var note = host.querySelector("[data-ig-note]");
    if (note) note.textContent = data.method_note || "";
  }

  function memberRowHtml(m, idx) {
    var qty = m.quantity != null
      ? fmt(m.quantity) + " " + esc(m.unit || m.unit_canonical)
      : (m.quantity_min != null ? fmt(m.quantity_min) + "–" + fmt(m.quantity_max) + " " + esc(m.unit || "") : "-");
    return (
      '<div class="rn-ig-mem" data-ig-mem="' + idx + '">' +
      '<div class="rn-ig-mem-head">' +
        "<span><b>" + esc(m.posko_title || "-") + "</b> · " + esc(m.kind) + "</span>" +
        modeBadge(m.quantity_mode, m.is_estimate) +
        '<span class="chip">' + esc(srcLabel(m.normalization_source)) +
          (m.normalization_confidence ? " " + m.normalization_confidence + "%" : "") + "</span>" +
        '<span class="chip ' + (m.normalization_status === "accepted" ? "ok" : "warning") + '">' +
          (m.normalization_status === "accepted" ? "diterima" : "usulan") + "</span>" +
      "</div>" +
      '<div class="rn-ig-mem-body">' +
        "<span>Teks asli: <i>" + esc(m.raw_text || m.item_name) + "</i></span>" +
        "<span>Jumlah: <b>" + qty + "</b>" +
          (m.is_estimate ? ' <small class="rn-muted">(perkiraan · akurat ' + fmt(m.qty_exact) + ")</small>" : "") + "</span>" +
        (m.estimate_text ? '<span class="rn-muted">catatan estimasi: ' + esc(m.estimate_text) + "</span>" : "") +
        '<button type="button" class="btn mini rn-ig-fix-toggle">Koreksi</button>' +
      "</div>" +
      '<form class="rn-ig-fix" hidden>' +
        '<label>Satuan / kemasan <input name="unit" value="' + esc(m.unit || m.unit_canonical) + '"></label>' +
        '<label>Pindah ke kelompok <input name="canonical_group" value="' + esc(m.canonical_group) + '" placeholder="mis. Air Minum"></label>' +
        '<label class="rn-ig-fix-chk"><input type="checkbox" name="make_exact"' + (m.is_estimate ? "" : " checked disabled") + '> Tandai kuantitas akurat</label>' +
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
    $("#rnIgTitle").textContent = g.group + " · " + g.unit;
    $("#rnIgSub").textContent = "Akurat " + fmt(g.qty_exact) + " " + g.unit +
      (g.estimate_member_count ? " + perkiraan AI " + fmt(g.qty_estimated) + " " + g.unit : "") +
      " · " + fmt(g.member_count) + " catatan";
    $("#rnIgBody").innerHTML = '<p class="rn-muted">Memuat rincian…</p>';
    $("#rnIgModal").hidden = false;
    document.body.style.overflow = "hidden";

    var data;
    try {
      data = await window.RN_FRAPPE.call("rescue_net.api_logistics.item_group_members", {
        group: g.group, unit: g.unit,
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
      if (b) b.innerHTML = '<tr><td colspan="7"><em class="rn-muted">Gagal memuat kelompok barang: ' +
        esc(err && err.message || err) + "</em></td></tr>";
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    if (!window.RN_FRAPPE) return;
    load();
  });
})();
