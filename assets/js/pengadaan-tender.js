/* Pengadaan & Tender — api_tender.*
   Owner 2026-11-03: gambar kerja uploads, target selesai kerja and the usual tender information
   (syarat peserta, dokumen wajib, email penawaran, ...) on the create form, the public detail and the
   organiser's edit panel. File links are rewritten by rn-frappe-client (MutationObserver). */
(function () {
  "use strict";
  var A = "rescue_net.api_tender.";
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var qs = new URLSearchParams(location.search);
  function getEvent() { return qs.get("event") || "event-sim-001"; }
  function esc(s) { return window.RNUI.esc(s); }
  function rp(n) { n = Number(n || 0); return n ? "Rp " + n.toLocaleString("id-ID") : "-"; }
  function dt(s) { return s ? String(s).slice(0, 16).replace("T", " ") : "-"; }
  function tgl(s) {
    if (!s) return "";
    var d = new Date(String(s).slice(0, 10) + "T00:00:00");
    return isNaN(d) ? String(s) : d.toLocaleDateString("id-ID", { day: "numeric", month: "long", year: "numeric" });
  }
  function errMsg(e) { return (e && e.message) || String(e); }

  var CATEGORY = [["", "— pilih —"], ["construction", "Pekerjaan Konstruksi"], ["goods", "Pengadaan Barang"],
                  ["services", "Jasa Lainnya"], ["consultancy", "Jasa Konsultansi"]];
  var EVALUATION = [["", "— pilih —"], ["lowest_price", "Harga terendah (memenuhi syarat)"],
                    ["quality_price", "Kualitas dan harga"], ["quality", "Kualitas teknis"]];

  // One list drives the create form, the edit form and the public detail.
  var INFO = [
    { sec: "Informasi Umum" },
    { k: "tender_category", l: "Jenis Pengadaan", t: "select", o: CATEGORY },
    { k: "funding_source", l: "Sumber Dana", p: "Donasi publik Program …" },
    { sec: "Jadwal Pelaksanaan" },
    { k: "work_start_date", l: "Rencana Mulai Kerja", t: "date" },
    { k: "target_completion_date", l: "Target Selesai Kerja", t: "date" },
    { k: "work_duration_days", l: "Masa Pelaksanaan (hari kalender)", t: "number" },
    { k: "maintenance_days", l: "Masa Pemeliharaan (hari)", t: "number" },
    { k: "explanation_schedule", l: "Rapat Penjelasan / Peninjauan Lapangan", t: "textarea",
      p: "mis. Senin 10 Nov 2026 09.00 WIB di lokasi pekerjaan" },
    { sec: "Syarat & Ketentuan Tender" },
    { k: "bidder_requirements", l: "Syarat Peserta Tender", t: "textarea", r: 4,
      p: "- Badan usaha berizin (NIB)\n- Sertifikat badan usaha (SBU) sesuai bidang\n- NPWP & laporan pajak terakhir\n- Pengalaman pekerjaan sejenis min. 1 paket dalam 3 tahun" },
    { k: "required_documents", l: "Dokumen Penawaran yang Wajib Dilampirkan", t: "textarea", r: 4,
      p: "- Surat penawaran bertanda tangan\n- RAB penawaran (rincian harga)\n- Jadwal pelaksanaan\n- Daftar personel & peralatan\n- Salinan izin usaha" },
    { k: "bid_submission_email", l: "Email Pengiriman Penawaran", t: "email", p: "tender@organisasi.org" },
    { k: "evaluation_method", l: "Metode Evaluasi", t: "select", o: EVALUATION },
    { k: "bid_validity_days", l: "Masa Berlaku Penawaran (hari)", t: "number" },
    { k: "payment_terms", l: "Cara Pembayaran", t: "textarea", p: "mis. termin 30% - 40% - 30% sesuai progres" },
  ];

  function fieldHtml(f, val) {
    val = val == null ? "" : val;
    var name = ' name="' + f.k + '"';
    var ph = f.p ? ' placeholder="' + esc(f.p) + '"' : "";
    var input;
    if (f.t === "select") {
      input = "<select" + name + ">" + f.o.map(function (o) {
        return '<option value="' + o[0] + '"' + (String(val) === o[0] ? " selected" : "") + ">" + esc(o[1]) + "</option>";
      }).join("") + "</select>";
    } else if (f.t === "textarea") {
      input = "<textarea" + name + ' rows="' + (f.r || 2) + '"' + ph + ">" + esc(val) + "</textarea>";
    } else {
      input = '<input type="' + (f.t || "text") + '"' + name + ph + (f.t === "number" ? ' min="0"' : "") +
        ' value="' + esc(f.t === "date" ? String(val).slice(0, 10) : val) + '">';
    }
    return "<label" + (f.t === "textarea" ? ' style="grid-column:1/-1"' : "") + ">" + esc(f.l) + input + "</label>";
  }

  function infoFieldsHtml(t) {
    var out = "", open = false;
    INFO.forEach(function (f) {
      if (f.sec) {
        if (open) out += "</div>";
        out += '<h4 class="td-sec">' + esc(f.sec) + '</h4><div class="form-grid">';
        open = true;
      } else out += fieldHtml(f, t ? t[f.k] : "");
    });
    return out + (open ? "</div>" : "");
  }

  function readInfo(form) {
    var o = {};
    INFO.forEach(function (f) { if (f.k && form.elements[f.k]) o[f.k] = form.elements[f.k].value.trim(); });
    return o;
  }

  function readBase64(file) {
    return new Promise(function (res, rej) {
      var r = new FileReader();
      r.onload = function () { res(String(r.result).split(",")[1] || ""); };
      r.onerror = function () { rej(r.error); };
      r.readAsDataURL(file);
    });
  }

  async function uploadFiles(tid, files, kind, label, msg) {
    var done = 0, fail = [];
    for (var i = 0; i < files.length; i++) {
      var file = files[i];
      if (file.size > 10 * 1024 * 1024) { fail.push(file.name + " (lebih dari 10 MB)"); continue; }
      if (msg) msg.textContent = "Mengunggah " + file.name + "…";
      try {
        await window.RN_FRAPPE.call(A + "upload_tender_file", {
          tender: tid, kind: kind, filename: file.name, content_base64: await readBase64(file), label: label || "",
        }, { method: "POST" });
        done++;
      } catch (e) { fail.push(file.name + " (" + errMsg(e) + ")"); }
    }
    return { done: done, fail: fail };
  }

  var CACHE = [];

  function tenderCard(t) {
    var rab = t.rab_document_url
      ? '<a href="' + esc(t.rab_document_url) + '" target="_blank" rel="noopener">' + rp(t.rab_total) + " · unduh RAB ↓</a>"
      : rp(t.rab_total);
    var sched = [];
    if (t.target_completion_date) sched.push("target selesai <b>" + esc(tgl(t.target_completion_date)) + "</b>");
    if (t.work_duration_days) sched.push("pelaksanaan " + t.work_duration_days + " hari");
    if (t.drawing_count) sched.push(t.drawing_count + " gambar kerja");
    return '<article class="td-card" data-tid="' + esc(t.name) + '">' +
      '<div class="rn-row"><span class="chip ' +
        (t.is_open ? "success" : (t.status === "awarded" ? "neutral" : "warning")) + '">' +
        esc(t.status_label) + "</span>" +
        (t.category_label ? '<span class="chip neutral">' + esc(t.category_label) + "</span>" : "") +
        (t.is_open ? '<span class="chip neutral">tutup ' + dt(t.bidding_closes_at) + "</span>" : "") + "</div>" +
      "<h4>" + esc(t.title) + "</h4>" +
      (t.design_image_url
        ? '<img src="' + esc(t.design_image_url) + '" alt="Gambar desain" style="max-width:100%;border-radius:6px;margin:4px 0;display:block">'
        : "") +
      '<div class="td-meta">' + esc(t.location || "-") + " · RAB " + rab +
        " · " + (t.bid_count || 0) + " penawaran" +
        (t.lowest_bid ? " · terendah " + rp(t.lowest_bid) : "") + "</div>" +
      (sched.length ? '<div class="td-meta" style="margin-top:4px">' + sched.join(" · ") + "</div>" : "") +
      (t.scope_description ? '<div class="td-meta" style="margin-top:4px">' + esc(t.scope_description) + "</div>" : "") +
      '<div data-info></div>' +
      '<div class="td-bids" data-bids></div>' +
      '<div class="td-actions">' +
        '<button type="button" class="btn ghost mini" data-act="info">Detail tender &amp; gambar kerja</button>' +
        '<button type="button" class="btn ghost mini" data-act="detail">Lihat penawaran</button>' +
        (t.is_open ? '<button type="button" class="btn primary mini" data-act="bid">Ajukan Penawaran</button>' : "") +
        '<span class="rn-muted td-msg"></span></div>' +
      "</article>";
  }

  async function load() {
    var d;
    try {
      d = await window.RN_FRAPPE.call(A + "tender_board", { disaster_event: getEvent() });
    } catch (e) { $("#tdStatus").textContent = "Gagal memuat: " + errMsg(e); return; }
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
        if (act === "info") showInfo(card, tid);
        else if (act === "detail") showBids(card, tid);
        else if (act === "bid") showBidForm(card, tid);
      });
    });
  }

  function fileTile(f, canDel) {
    var name = f.label || f.name || "berkas";
    var thumb = f.pdf
      ? '<div class="td-pdf">PDF</div>'
      : '<img src="' + esc(f.url) + '" alt="' + esc(name) + '" loading="lazy">';
    return '<figure><a href="' + esc(f.url) + '" target="_blank" rel="noopener">' + thumb + "</a>" +
      '<figcaption><a href="' + esc(f.url) + '" target="_blank" rel="noopener">' + esc(name) + "</a>" +
      (canDel ? ' · <a href="#" data-del-file="' + esc(f.url) + '">hapus</a>' : "") + "</figcaption></figure>";
  }

  function infoRows(d) {
    var rows = [
      ["Jenis Pengadaan", d.category_label], ["Sumber Dana", d.funding_source],
      ["Lokasi", d.location], ["Nilai RAB / HPS", d.rab_total ? rp(d.rab_total) : ""],
      ["Batas Akhir Penawaran", d.bidding_closes_at ? dt(d.bidding_closes_at) : ""],
      ["Rapat Penjelasan / Peninjauan Lapangan", d.explanation_schedule],
      ["Rencana Mulai Kerja", tgl(d.work_start_date)], ["Target Selesai Kerja", tgl(d.target_completion_date)],
      ["Masa Pelaksanaan", d.work_duration_days ? d.work_duration_days + " hari kalender" : ""],
      ["Masa Pemeliharaan", d.maintenance_days ? d.maintenance_days + " hari" : ""],
      ["Syarat Peserta Tender", d.bidder_requirements],
      ["Dokumen Penawaran Wajib", d.required_documents],
      ["Metode Evaluasi", d.evaluation_label],
      ["Masa Berlaku Penawaran", d.bid_validity_days ? d.bid_validity_days + " hari" : ""],
      ["Cara Pembayaran", d.payment_terms],
      ["Narahubung", [d.contact_person, d.contact_phone].filter(Boolean).join(" · ")],
      ["Catatan", d.notes],
    ].filter(function (r) { return r[1]; });
    return rows.length
      ? "<dl>" + rows.map(function (r) { return "<dt>" + esc(r[0]) + "</dt><dd>" + esc(r[1]) + "</dd>"; }).join("") + "</dl>"
      : '<p class="rn-muted">Penyelenggara belum melengkapi informasi tender.</p>';
  }

  function emailBox(d) {
    if (!d.bid_submission_email) return "";
    var subj = encodeURIComponent("Penawaran Tender: " + (d.title || ""));
    return '<div class="td-email">Kirim dokumen penawaran lengkap ke <a href="mailto:' + esc(d.bid_submission_email) +
      "?subject=" + subj + '"><b>' + esc(d.bid_submission_email) + "</b></a>" +
      (d.bidding_closes_at ? " paling lambat " + esc(dt(d.bidding_closes_at)) : "") + ".</div>";
  }

  async function showInfo(card, tid) {
    var box = card.querySelector("[data-info]");
    if (box.dataset.shown === "1") { box.innerHTML = ""; box.dataset.shown = ""; return; }
    box.dataset.shown = "1";
    box.innerHTML = '<span class="rn-muted">memuat…</span>';
    var d;
    try { d = await window.RN_FRAPPE.call(A + "tender_detail", { tender: tid }); }
    catch (e) { box.innerHTML = '<span class="rn-muted">gagal: ' + esc(errMsg(e)) + "</span>"; return; }
    if (!d.found) { box.innerHTML = '<span class="rn-muted">Tender tidak ditemukan.</span>'; return; }
    var editable = d.can_manage && d.status !== "awarded" && d.status !== "cancelled";
    var drawings = d.drawings || [], rab = d.rab_pages || [];
    var html = '<div class="td-info">' + emailBox(d) + infoRows(d) +
      "<div><b>Gambar Kerja</b>" + (drawings.length
        ? '<div class="td-gallery">' + drawings.map(function (f) { return fileTile(f, editable); }).join("") + "</div>"
        : ' <span class="rn-muted">— belum ada.</span>') + "</div>" +
      (rab.length ? '<div><b>Halaman RAB / B&amp;Q</b><div class="td-gallery">' +
        rab.map(function (f) { return fileTile(f, editable); }).join("") + "</div></div>" : "");
    if (editable) {
      html += '<div class="td-manage"><b>Kelola tender (penyelenggara)</b>' +
        '<form class="rn-form" data-upload style="margin-top:8px"><div class="form-grid">' +
        '<label>Jenis berkas<select name="kind"><option value="gambar">Gambar kerja</option><option value="rab">Halaman RAB / B&amp;Q</option></select></label>' +
        '<label>Keterangan (opsional)<input name="label" placeholder="mis. Denah lantai 1"></label>' +
        '<label>Berkas (PDF / JPG / PNG, maks. 10 MB)<input name="files" type="file" multiple accept=".pdf,.png,.jpg,.jpeg,.webp,application/pdf,image/*"></label>' +
        '</div><div class="form-actions"><button class="btn primary mini" type="submit">Unggah</button><span class="rn-muted" data-up-msg></span></div></form>' +
        '<details style="margin-top:8px"><summary>Ubah informasi tender</summary>' +
        '<form class="rn-form" data-edit><div class="form-grid">' +
        '<label>Judul Pekerjaan<input name="title" required value="' + esc(d.title || "") + '"></label>' +
        '<label>Lokasi<input name="location" value="' + esc(d.location || "") + '"></label>' +
        '<label>Nilai RAB / HPS (Rp)<input name="rab_total" type="number" min="0" value="' + esc(d.rab_total || 0) + '"></label>' +
        '<label>Batas Akhir Penawaran<input name="bidding_closes_at" type="datetime-local" value="' +
          esc(d.bidding_closes_at ? String(d.bidding_closes_at).slice(0, 16).replace(" ", "T") : "") + '"></label>' +
        '<label>Narahubung<input name="contact_person" value="' + esc(d.contact_person || "") + '"></label>' +
        '<label>Kontak (HP)<input name="contact_phone" value="' + esc(d.contact_phone || "") + '"></label>' +
        '<label style="grid-column:1/-1">Lingkup Pekerjaan<textarea name="scope_description" rows="3">' + esc(d.scope_description || "") + "</textarea></label>" +
        "</div>" + infoFieldsHtml(d) +
        '<div class="form-actions"><button class="btn primary mini" type="submit">Simpan perubahan</button><span class="rn-muted" data-ed-msg></span></div>' +
        "</form></details></div>";
    }
    box.innerHTML = html + "</div>";
    if (!editable) return;

    var reopen = async function () { box.dataset.shown = ""; await showInfo(card, tid); };
    box.querySelectorAll("[data-del-file]").forEach(function (a) {
      a.addEventListener("click", async function (e) {
        e.preventDefault();
        if (window.confirm && !window.confirm("Hapus berkas ini?")) return;
        try {
          await window.RN_FRAPPE.call(A + "remove_tender_file", { tender: tid, file_url: a.getAttribute("data-del-file") }, { method: "POST" });
          await reopen();
        } catch (err) { window.alert("Gagal: " + errMsg(err)); }
      });
    });
    var up = box.querySelector("[data-upload]");
    up.addEventListener("submit", async function (e) {
      e.preventDefault();
      var m = up.querySelector("[data-up-msg]");
      var files = up.elements.files.files;
      if (!files.length) { m.textContent = "Pilih berkas dulu."; return; }
      var r = await uploadFiles(tid, files, up.elements.kind.value, up.elements.label.value, m);
      if (r.fail.length) { m.textContent = r.done + " terunggah; gagal: " + r.fail.join("; "); return; }
      await reopen();
    });
    var ed = box.querySelector("[data-edit]");
    ed.addEventListener("submit", async function (e) {
      e.preventDefault();
      var m = ed.querySelector("[data-ed-msg]");
      var args = readInfo(ed);
      ["title", "location", "rab_total", "contact_person", "contact_phone", "scope_description"].forEach(function (k) {
        args[k] = ed.elements[k].value.trim();
      });
      args.bidding_closes_at = ed.elements.bidding_closes_at.value.replace("T", " ");
      args.tender = tid;
      m.textContent = "Menyimpan…";
      try {
        await window.RN_FRAPPE.call(A + "update_tender_info", args, { method: "POST" });
        await load();
      } catch (err) { m.textContent = "Gagal: " + errMsg(err); }
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
          } catch (e) { card.querySelector(".td-msg").textContent = " gagal: " + errMsg(e); }
        });
      });
    } catch (e) { box.innerHTML = '<span class="rn-muted">gagal: ' + esc(errMsg(e)) + "</span>"; }
  }

  async function showBidForm(card, tid) {
    var box = card.querySelector("[data-bids]");
    var d = {};
    try { d = await window.RN_FRAPPE.call(A + "tender_detail", { tender: tid }); } catch (e) { d = {}; }
    var reqs = d.bidder_requirements
      ? '<div class="rn-muted" style="white-space:pre-line"><b>Syarat peserta:</b>\n' + esc(d.bidder_requirements) + "</div>" : "";
    var docs = d.required_documents
      ? '<div class="rn-muted" style="white-space:pre-line"><b>Dokumen wajib:</b>\n' + esc(d.required_documents) + "</div>" : "";
    box.innerHTML =
      '<div class="rn-form" style="display:grid;gap:6px;max-width:480px">' + emailBox(d) + reqs + docs +
      '<input data-f="bidder_name" placeholder="Nama penawar / perusahaan *">' +
      '<input data-f="bidder_org" placeholder="Organisasi (opsional)">' +
      '<input data-f="bidder_contact" placeholder="Kontak (HP/email)">' +
      '<input data-f="bid_amount" type="number" min="0" placeholder="Nilai penawaran (Rp) *">' +
      '<input data-f="bid_days" type="number" min="0" placeholder="Waktu pengerjaan (hari)' +
        (d.work_duration_days ? " — maks. " + d.work_duration_days : "") + '">' +
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
      } catch (e) { box.querySelector(".td-msg").textContent = " gagal: " + errMsg(e); }
    });
  }

  function wireForm() {
    var form = $("#tdForm");
    if (!form) return;
    var slot = form.querySelector("[data-info-fields]");
    if (slot) slot.innerHTML = infoFieldsHtml(null);
    var msg = form.querySelector("[data-td-msg]");
    form.addEventListener("submit", async function (e) {
      e.preventDefault();
      var fd = new FormData(form);
      var args = readInfo(form);
      Object.keys(args).forEach(function (k) { if (!args[k]) delete args[k]; });
      Object.assign(args, {
        disaster_event: fd.get("disaster_event"), title: fd.get("title"),
        location: fd.get("location") || null, rab_total: fd.get("rab_total") || 0,
        rab_document_url: fd.get("rab_document_url") || null,
        donor_program: fd.get("donor_program") || null,
        scope_description: fd.get("scope_description") || null,
        bidding_closes_at: (fd.get("bidding_closes_at") || "").replace("T", " ") || null,
        contact_person: fd.get("contact_person") || null,
        contact_phone: fd.get("contact_phone") || null,
      });
      msg.textContent = "Menyimpan…";
      var res;
      try {
        res = await window.RN_FRAPPE.call(A + "create_tender", args, { method: "POST" });
      } catch (err) {
        var m = errMsg(err);
        msg.textContent = "Gagal: " + m + (/login|diperlukan|permission|pengelola/i.test(m) ? " (perlu login)" : "");
        return;
      }
      var fail = [];
      var drawings = form.elements.drawings ? form.elements.drawings.files : [];
      var rabs = form.elements.rab_files ? form.elements.rab_files.files : [];
      if (drawings.length) fail = fail.concat((await uploadFiles(res.tender, drawings, "gambar", "", msg)).fail);
      if (rabs.length) fail = fail.concat((await uploadFiles(res.tender, rabs, "rab", "", msg)).fail);
      msg.textContent = "Tersimpan" + (res.status === "draft" ? " sebagai draf (organisasi belum terverifikasi / tanpa batas waktu)" : "") +
        "." + (fail.length ? " Berkas gagal: " + fail.join("; ") : "");
      form.reset();
      await load();
    });
  }

  if (document.readyState === "loading")
    document.addEventListener("DOMContentLoaded", function () { wireForm(); load(); });
  else { wireForm(); load(); }
})();
