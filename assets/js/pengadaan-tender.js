/* Pengadaan & Tender — api_tender.* */
(function () {
  "use strict";
  var A = "rescue_net.api_tender.";
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var qs = new URLSearchParams(location.search);
  function getEvent() { return qs.get("event") || "event-sim-001"; }
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function rp(n) { n = Number(n || 0); return n ? "Rp " + n.toLocaleString("id-ID") : "-"; }
  function dt(s) { return s ? String(s).slice(0, 16).replace("T", " ") : "-"; }

  var CACHE = [];

  function tenderCard(t) {
    var rab = t.rab_document_url
      ? '<a href="' + esc(t.rab_document_url) + '" target="_blank" rel="noopener">' + rp(t.rab_total) + " · unduh RAB ↓</a>"
      : rp(t.rab_total);
    return '<article class="td-card" data-tid="' + esc(t.name) + '">' +
      '<div class="rn-row"><span class="chip ' +
        (t.is_open ? "success" : (t.status === "awarded" ? "neutral" : "warning")) + '">' +
        esc(t.status_label) + "</span>" +
        (t.is_open ? '<span class="chip neutral">tutup ' + dt(t.bidding_closes_at) + "</span>" : "") + "</div>" +
      "<h4>" + esc(t.title) + "</h4>" +
      '<div class="td-meta">' + esc(t.location || "-") + " · RAB " + rab +
        " · " + (t.bid_count || 0) + " penawaran" +
        (t.lowest_bid ? " · terendah " + rp(t.lowest_bid) : "") + "</div>" +
      (t.scope_description ? '<div class="td-meta" style="margin-top:4px">' + esc(t.scope_description) + "</div>" : "") +
      '<div class="td-bids" data-bids></div>' +
      '<div class="td-actions">' +
        '<button type="button" class="btn ghost mini" data-act="detail">Lihat penawaran</button>' +
        (t.is_open ? '<button type="button" class="btn primary mini" data-act="bid">Ajukan Penawaran</button>' : "") +
        '<span class="rn-muted td-msg"></span></div>' +
      "</article>";
  }

  async function load() {
    var d;
    try {
      d = await window.RN_FRAPPE.call(A + "tender_board", { disaster_event: getEvent() });
    } catch (e) { $("#tdStatus").textContent = "Gagal memuat: " + (e && e.message || e); return; }
    CACHE = d.tenders || [];
    var t = d.totals || {};
    $("#kpiTotal").textContent = t.total || 0;
    $("#kpiOpen").textContent = t.open || 0;
    $("#kpiRab").textContent = rp(t.rab_value_total);
    $("#kpiBids").textContent = t.bids_total || 0;
    $("#tdStatus").textContent = (t.total || 0) + " tender · " + (t.open || 0) + " terbuka · " + (t.bids_total || 0) + " penawaran.";
    $("#tdCount").textContent = (t.total || 0) + " tender";
    $("#tdList").innerHTML = CACHE.length
      ? CACHE.map(tenderCard).join("")
      : '<p class="rn-muted" style="padding:10px 0">Belum ada tender.</p>';
    wireCards();
  }

  function wireCards() {
    document.querySelectorAll("#tdList .td-card [data-act]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var card = btn.closest("[data-tid]");
        var tid = card.getAttribute("data-tid");
        var act = btn.getAttribute("data-act");
        if (act === "detail") showBids(card, tid);
        else if (act === "bid") showBidForm(card, tid);
      });
    });
  }

  async function showBids(card, tid) {
    var box = card.querySelector("[data-bids]");
    box.innerHTML = '<span class="rn-muted">memuat…</span>';
    try {
      var d = await window.RN_FRAPPE.call(A + "tender_detail", { tender: tid });
      var bids = d.bids || [];
      box.innerHTML = bids.length ? bids.map(function (b) {
        var actions = d.can_manage && d.status !== "awarded"
          ? ' <button type="button" class="btn ghost mini" data-award="' + esc(b.name) + '">Tetapkan pemenang</button>'
          : "";
        return '<div class="td-bid"><b>' + esc(b.bidder_name) + "</b> " +
          (b.bidder_org ? "<span class=\"rn-muted\">" + esc(b.bidder_org) + "</span> " : "") +
          "· " + rp(b.bid_amount) + (b.bid_days ? " · " + b.bid_days + " hari" : "") +
          ' <span class="chip ' + (b.status === "awarded" ? "success" : "neutral") + '">' + esc(b.status) + "</span>" +
          (b.bidder_contact ? ' <span class="rn-muted">' + esc(b.bidder_contact) + "</span>" : "") +
          actions +
          (b.proposal_summary ? '<div class="rn-muted" style="flex-basis:100%">' + esc(b.proposal_summary) + "</div>" : "") +
          "</div>";
      }).join("") : '<span class="rn-muted">Belum ada penawaran.</span>';
      box.querySelectorAll("[data-award]").forEach(function (ab) {
        ab.addEventListener("click", async function () {
          try {
            await window.RN_FRAPPE.call(A + "set_bid_status",
              { bid: ab.getAttribute("data-award"), status: "awarded" }, { method: "POST" });
            await load();
          } catch (e) { card.querySelector(".td-msg").textContent = " gagal: " + (e && e.message || e); }
        });
      });
    } catch (e) { box.innerHTML = '<span class="rn-muted">gagal: ' + esc(e && e.message || e) + "</span>"; }
  }

  function showBidForm(card, tid) {
    var box = card.querySelector("[data-bids]");
    box.innerHTML =
      '<div class="rn-form" style="display:grid;gap:6px;max-width:420px">' +
      '<input data-f="bidder_name" placeholder="Nama penawar / perusahaan *">' +
      '<input data-f="bidder_org" placeholder="Organisasi (opsional)">' +
      '<input data-f="bidder_contact" placeholder="Kontak (HP/email)">' +
      '<input data-f="bid_amount" type="number" min="0" placeholder="Nilai penawaran (Rp) *">' +
      '<input data-f="bid_days" type="number" min="0" placeholder="Waktu pengerjaan (hari)">' +
      '<textarea data-f="proposal_summary" rows="2" placeholder="Ringkasan proposal"></textarea>' +
      '<div><button type="button" class="btn primary mini" data-send-bid>Kirim Penawaran</button>' +
      '<span class="rn-muted td-msg"></span></div></div>';
    box.querySelector("[data-send-bid]").addEventListener("click", async function () {
      var g = function (k) { var el = box.querySelector('[data-f="' + k + '"]'); return el ? el.value.trim() : ""; };
      if (!g("bidder_name") || !g("bid_amount")) { box.querySelector(".td-msg").textContent = " isi nama & nilai."; return; }
      box.querySelector(".td-msg").textContent = " mengirim…";
      try {
        await window.RN_FRAPPE.call(A + "submit_bid", {
          tender: tid, bidder_name: g("bidder_name"), bidder_org: g("bidder_org") || null,
          bidder_contact: g("bidder_contact") || null, bid_amount: g("bid_amount"),
          bid_days: g("bid_days") || null, proposal_summary: g("proposal_summary") || null,
        }, { method: "POST" });
        await load();
      } catch (e) { box.querySelector(".td-msg").textContent = " gagal: " + (e && e.message || e); }
    });
  }

  function wireForm() {
    var form = $("#tdForm");
    if (!form) return;
    var msg = form.querySelector("[data-td-msg]");
    form.addEventListener("submit", async function (e) {
      e.preventDefault();
      var fd = new FormData(form);
      msg.textContent = "Menyimpan…";
      try {
        await window.RN_FRAPPE.call(A + "create_tender", {
          disaster_event: fd.get("disaster_event"), title: fd.get("title"),
          location: fd.get("location") || null, rab_total: fd.get("rab_total") || 0,
          rab_document_url: fd.get("rab_document_url") || null,
          donor_program: fd.get("donor_program") || null,
          scope_description: fd.get("scope_description") || null,
          bidding_closes_at: (fd.get("bidding_closes_at") || "").replace("T", " ") || null,
          contact_person: fd.get("contact_person") || null,
          contact_phone: fd.get("contact_phone") || null,
        }, { method: "POST" });
        msg.textContent = "Tersimpan.";
        form.reset();
        await load();
      } catch (err) {
        var m = (err && err.message) || String(err);
        msg.textContent = "Gagal: " + m + (/login|diperlukan|permission|pengelola/i.test(m) ? " (perlu login)" : "");
      }
    });
  }

  if (document.readyState === "loading")
    document.addEventListener("DOMContentLoaded", function () { wireForm(); load(); });
  else { wireForm(); load(); }
})();
