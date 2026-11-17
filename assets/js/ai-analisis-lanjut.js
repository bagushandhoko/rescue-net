/* Analisis AI Lanjutan (Suri 2026-11-16). Memakai frappeCall/ensureSession/getEventId dari ai-analyst.js.
   Semua hasil = SARAN tersimpan di RN AI Report; tidak ada data operasional yang diubah. */
(function () {
  const M = "rescue_net.api_ai.";
  const FITUR = [
    { id: "sitrep_ai", label: "SITREP AI", ikon: "📋", ket: "Laporan situasi naratif (gaya OCHA) + risiko 24–72 jam + rekomendasi.", param: "jam" },
    { id: "triase_laporan", label: "Triase Laporan Warga", ikon: "🚨", ket: "Kelompokkan laporan warga & tandai yang darurat.", param: "jam72" },
    { id: "prakiraan_stok", label: "Prakiraan Stok Habis", ikon: "📦", ket: "Perkiraan sisa hari stok per posko + saran realokasi." },
    { id: "tanya_berujukan", label: "Tanya Jawab Berujukan", ikon: "💬", ket: "Jawaban dengan rujukan ID data sumber.", param: "tanya" },
    { id: "dampak_gempa", label: "Dampak Gempa BMKG", ikon: "🌏", ket: "Posko dalam radius 200 km dari gempa terbaru + tindakan." },
    { id: "cek_kejanggalan", label: "Cek Kejanggalan", ikon: "🔎", ket: "Data yang perlu dicek: kembar, lonjakan, harga tak wajar." },
    { id: "analisis_foto", label: "Analisis Foto Bukti", ikon: "📷", ket: "Nilai kerusakan / banjir / bahaya dari foto.", param: "foto" },
    { id: "rencana_kirim", label: "Rencana Pengiriman", ikon: "🚚", ket: "Usulan siapa kirim apa ke mana (perlu persetujuan)." },
  ];
  const bersih = m => String(m || "").replace(/^(frappe\.exceptions\.)?\w+Error:\s*/, "");
  const esc = s => String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  // Markdown sederhana -> HTML aman (judul, daftar, tabel, tebal, kode baris).
  function md(text) {
    const lines = String(text || "").split(/\r?\n/); let out = "", list = null, table = [];
    const inline = s => esc(s).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/`([^`]+)`/g, "<code>$1</code>");
    const flushTable = () => {
      if (!table.length) return;
      const rows = table.filter(r => !/^\s*\|?\s*:?-{2,}/.test(r)).map(r => r.replace(/^\s*\||\|\s*$/g, "").split("|"));
      out += '<div class="aia-table"><table>' + rows.map((c, i) => "<tr>" + c.map(x => (i ? "<td>" : "<th>") + inline(x.trim()) + (i ? "</td>" : "</th>")).join("") + "</tr>").join("") + "</table></div>";
      table = [];
    };
    const closeList = () => { if (list) { out += "</" + list + ">"; list = null; } };
    for (const raw of lines) {
      const l = raw.trimEnd();
      if (/^\s*\|.*\|\s*$/.test(l)) { closeList(); table.push(l); continue; } else flushTable();
      let m;
      if ((m = l.match(/^(#{1,4})\s+(.*)$/))) { closeList(); const h = Math.min(6, m[1].length + 2); out += `<h${h}>${inline(m[2])}</h${h}>`; }
      else if ((m = l.match(/^\s*[-*]\s+(.*)$/))) { if (list !== "ul") { closeList(); out += "<ul>"; list = "ul"; } out += "<li>" + inline(m[1]) + "</li>"; }
      else if ((m = l.match(/^\s*\d+[.)]\s+(.*)$/))) { if (list !== "ol") { closeList(); out += "<ol>"; list = "ol"; } out += "<li>" + inline(m[1]) + "</li>"; }
      else if (!l.trim()) { closeList(); }
      else { closeList(); out += "<p>" + inline(l) + "</p>"; }
    }
    flushTable(); closeList(); return out;
  }

  function orgId() {
    const f = document.getElementById("aiAskForm");
    const v = f && f.ai_ctx ? f.ai_ctx.value : "";
    return v && v !== "personal" ? v : "";
  }

  function fileB64(file) {
    return new Promise((ok, err) => { const r = new FileReader(); r.onload = () => ok(String(r.result).split(",")[1]); r.onerror = err; r.readAsDataURL(file); });
  }

  let terakhir = null;
  function tampil(res) {
    terakhir = res;
    const box = document.getElementById("aiaHasil");
    box.innerHTML = `<div class="aia-head"><b>${esc(res.title || "")}</b><span class="aia-meta">${esc(res.dibuat || "")} · ${esc(res.provider || "")} ${esc(res.model_name || "")}</span>
      <span class="aia-act"><button type="button" class="btn" data-aia="unduh">Unduh .md</button> <button type="button" class="btn" data-aia="cetak">Cetak</button></span></div>
      <div class="aia-isi">${md(res.content)}</div><p class="aia-note">Hasil AI adalah saran — periksa kembali sebelum bertindak.</p>`;
    box.scrollIntoView({ behavior: "smooth", block: "start" });
    if (window.RNAiTautan) window.RNAiTautan.tautkan(box.querySelector(".aia-isi"), getEventId());
  }

  async function jalankan(f, form) {
    const box = document.getElementById("aiaHasil");
    box.innerHTML = `<p class="aia-load">⏳ ${esc(f.label)} sedang dianalisis AI… (bisa 20–90 detik)</p>`;
    try {
      const s = await ensureSession();
      const args = { user_id: s.user, disaster_event_id: getEventId(), provider: "auto", organization_id: orgId() };
      if (f.param === "jam" || f.param === "jam72") args.hours = form.querySelector("[name=jam]").value;
      if (f.param === "tanya") { args.question = form.querySelector("[name=tanya]").value.trim(); if (!args.question) throw new Error("Tulis pertanyaannya dulu."); }
      if (f.param === "foto") {
        const file = form.querySelector("[name=foto]").files[0];
        if (!file) throw new Error("Pilih foto dulu.");
        if (file.size > 4 * 1024 * 1024) throw new Error("Foto maksimal 4 MB.");
        args.image_b64 = await fileB64(file); args.mime = file.type || "image/jpeg"; args.note = form.querySelector("[name=catatan]").value.trim();
      }
      const res = await frappeCall(M + f.id, args, true);
      tampil(res); muatRiwayat();
    } catch (e) { box.innerHTML = `<p class="aia-err">Gagal: ${esc(bersih(e.message || e))}</p>`; }
  }

  async function muatRiwayat() {
    const el = document.getElementById("aiaRiwayat");
    try {
      const s = await ensureSession();
      const rows = await frappeCall(M + "daftar_laporan_ai", { user_id: s.user, disaster_event_id: getEventId(), limit: 30 });
      el.innerHTML = (rows || []).length ? rows.map(r => `<li><button type="button" class="aia-link" data-buka="${esc(r.name)}">${esc(r.title || r.report_type)}</button>
        <span class="aia-meta">${esc((FITUR.find(f => f.id.startsWith(r.report_type.split("_")[0])) || {}).label || r.report_type)} · ${esc(r.dibuat)}</span></li>`).join("")
        : "<li class='aia-meta'>Belum ada hasil analisis untuk bencana ini.</li>";
    } catch (e) { el.innerHTML = `<li class="aia-meta">Riwayat tampil setelah login.</li>`; }
  }

  function unduh() {
    if (!terakhir) return;
    const blob = new Blob([`# ${terakhir.title}\n\n${terakhir.content}\n`], { type: "text/markdown;charset=utf-8" });
    const a = document.createElement("a"); a.href = URL.createObjectURL(blob);
    a.download = (terakhir.title || "analisis-ai").replace(/[^\w\- ]+/g, "").slice(0, 60) + ".md"; a.click();
  }
  function cetak() {
    if (!terakhir) return;
    const w = window.open("", "_blank"); if (!w) return;
    w.document.write(`<!doctype html><meta charset="utf-8"><title>${esc(terakhir.title)}</title><style>body{font-family:sans-serif;max-width:820px;margin:24px auto;line-height:1.5}table{border-collapse:collapse}td,th{border:1px solid #ccc;padding:4px 8px}</style><h1>${esc(terakhir.title)}</h1>${md(terakhir.content)}<p><i>Hasil AI Rescue-Net — saran, periksa kembali.</i></p>`);
    w.document.close(); w.print();
  }

  function bangun() {
    const host = document.getElementById("aiaPanel"); if (!host) return;
    host.innerHTML = `<h3>Analisis AI Lanjutan</h3>
      <p class="aia-meta">Perlu login dan kunci AI (pribadi/organisasi) di AI Settings. Biaya memakai kuota kunci yang dipilih di "Konteks AI". Hasil = saran, tersimpan di riwayat.</p>
      <div class="aia-grid">${FITUR.map(f => `<form class="aia-card" data-fitur="${f.id}"><div class="aia-title">${f.ikon} ${esc(f.label)}</div><div class="aia-ket">${esc(f.ket)}</div>
        ${f.param === "jam" ? '<label>Periode <select name="jam"><option value="24">24 jam</option><option value="48">48 jam</option><option value="72">72 jam</option><option value="168">7 hari</option></select></label>' : ""}
        ${f.param === "jam72" ? '<label>Periode <select name="jam"><option value="24">24 jam</option><option value="72" selected>72 jam</option><option value="168">7 hari</option></select></label>' : ""}
        ${f.param === "tanya" ? '<textarea name="tanya" rows="2" placeholder="Contoh: posko mana yang paling kekurangan air bersih?"></textarea>' : ""}
        ${f.param === "foto" ? '<input type="file" name="foto" accept="image/*" capture="environment"><input name="catatan" placeholder="Catatan lokasi (opsional)">' : ""}
        <button class="btn primary" type="submit">Jalankan</button></form>`).join("")}</div>
      <div id="aiaHasil" class="aia-hasil"></div>
      <h4>Riwayat Analisis AI</h4><ul id="aiaRiwayat" class="aia-riwayat"></ul>`;
    host.addEventListener("submit", e => { const form = e.target.closest("form[data-fitur]"); if (!form) return; e.preventDefault(); jalankan(FITUR.find(f => f.id === form.dataset.fitur), form); });
    host.addEventListener("click", async e => {
      const b = e.target.closest("[data-buka]");
      if (b) { try { const s = await ensureSession(); tampil(await frappeCall(M + "baca_laporan_ai", { user_id: s.user, name: b.dataset.buka })); } catch (err) { document.getElementById("aiaHasil").innerHTML = `<p class="aia-err">${esc(bersih(err.message))}</p>`; } }
      const a = e.target.closest("[data-aia]"); if (a) (a.dataset.aia === "unduh" ? unduh : cetak)();
    });
    muatRiwayat();
  }
  document.addEventListener("DOMContentLoaded", bangun);
})();
