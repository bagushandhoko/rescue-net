/* Profil Kerja Organisasi (owner 2026-11-08) — halaman publik: rescue_net.api_org_profile.org_profile / org_list.
   Tanpa kontak pribadi, nama pasien, atau daftar anggota; organisasi tertutup hanya angka gabungan. */
(function () {
  "use strict";
  var COLORS = { logistics: "#e8755a", medical: "#d64545", kitchen: "#d99a1e", shelter: "#3f8fcf", transport: "#6b5bd1",
    collection_hub: "#8c6a4f", field_assessment: "#2e9e8f", communication: "#5f7d95", equipment: "#7a7a2e",
    volunteer: "#3aa35b", sar: "#c2410c", command: "#333" };
  var METRIC = { pasien: "pasien dilayani", porsi: "porsi dimasak", pengungsi: "pengungsi tertampung", dicari: "laporan orang hilang",
    ditemukan: "orang ditemukan", penugasan_relawan: "penugasan relawan", kiriman_diterima: "kiriman diterima",
    kiriman_keluar: "kiriman disalurkan" };
  var VERIF_OK = /verified|approved|trusted/i;
  var params = new URLSearchParams(location.search);
  var map = null;

  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function num(n) { return Number(n || 0).toLocaleString("id-ID"); }
  function rp(n) { return "Rp " + num(Math.round(Number(n || 0))); }
  function $(id) { return document.getElementById(id); }
  function card(title, sub, inner) {
    return '<section class="po-card"><h2>' + esc(title) + "</h2>" + (sub ? '<p class="sub">' + esc(sub) + "</p>" : "") + inner + "</section>";
  }
  function call(m, a) { return window.RN_FRAPPE.call("rescue_net.api_org_profile." + m, a || {}); }

  async function pickList() {
    $("poTitle").textContent = "Profil Kerja Organisasi";
    $("poLead").textContent = "Pilih organisasi untuk melihat posko, peran, dan hasil kerjanya.";
    try {
      var rows = await call("org_list");
      $("poBody").innerHTML = card("Organisasi", "Organisasi induk yang punya posko di Rescue-Net.",
        '<div class="po-pick">' + (rows.length ? rows.map(function (r) {
          return '<a href="profil-organisasi.html?id=' + encodeURIComponent(r.id) + '"><b>' + esc(r.title) + "</b><br><span class=\"po-muted\">" +
            num(r.posko) + " posko" + (r.organisasi_anak ? " · " + num(r.organisasi_anak) + " organisasi anak" : "") +
            (r.open ? "" : " · tertutup") + "</span></a>";
        }).join("") : "<p>Belum ada organisasi.</p>") + "</div>");
    } catch (e) { $("poBody").innerHTML = card("Gagal memuat", "", "<p>" + esc(e.message || e) + "</p>"); }
  }

  function renderMap(poskos) {
    var pts = poskos.filter(function (p) { return p.lat != null && p.lng != null; });
    if (!window.L || !pts.length) { $("poMap").outerHTML = '<p class="po-muted">Belum ada posko dengan koordinat.</p>'; return; }
    if (map) { map.remove(); }
    map = L.map("poMap", { scrollWheelZoom: false });
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 18, attribution: "© OpenStreetMap" }).addTo(map);
    var ev = $("poEvent").value;
    var bounds = [];
    pts.forEach(function (p) {
      var c = COLORS[p.type] || "#555";
      var m = L.circleMarker([p.lat, p.lng], { radius: 8, color: "#fff", weight: 2, fillColor: c, fillOpacity: 0.95 }).addTo(map);
      var href = p.href + "?id=" + encodeURIComponent(p.id) + (ev || p.events[0] ? "&event=" + encodeURIComponent(ev || p.events[0]) : "");
      var met = p.metrics ? Object.keys(p.metrics).filter(function (k) { return METRIC[k]; }).map(function (k) { return num(p.metrics[k]) + " " + METRIC[k]; }).join("<br>") : "";
      m.bindPopup("<b>" + esc(p.title) + "</b><br>" + esc(p.type_label) + " · " + esc(p.organization_title) +
        (p.open ? "" : "<br><i>Organisasi tertutup: hanya angka gabungan</i>") + (met ? "<br>" + met : "") +
        '<br><a href="' + href + '">Buka halaman posko →</a>');
      bounds.push([p.lat, p.lng]);
    });
    map.fitBounds(bounds, { padding: [30, 30], maxZoom: 11 });
  }

  function render(d) {
    var o = d.organization, t = d.totals;
    document.title = "Rescue-Net | " + o.title;
    $("poTitle").textContent = o.title;
    $("poLead").textContent = "Peran " + o.title + " dalam penanganan bencana di Rescue-Net: " + num(t.posko) + " posko dari " +
      num(t.organisasi) + " organisasi (induk & organisasi anak), " + num(t.bencana) + " bencana.";
    $("poBadges").innerHTML =
      '<span class="po-badge ' + (VERIF_OK.test(o.verification_status || "") ? "ok" : "") + '">' + (VERIF_OK.test(o.verification_status || "") ? "✓ Terverifikasi" : "Belum terverifikasi") + "</span>" +
      '<span class="po-badge ' + (o.open ? "" : "lock") + '">' + (o.open ? "Organisasi terbuka" : "Organisasi tertutup — angka gabungan") + "</span>" +
      (o.parent ? '<a class="po-badge" href="profil-organisasi.html?id=' + encodeURIComponent(o.parent.id) + '">Induk: ' + esc(o.parent.title) + "</a>" : "");

    var sel = $("poEvent");
    if (sel.options.length <= 1 && d.events.length) {
      d.events.forEach(function (e) { var op = document.createElement("option"); op.value = e.id; op.textContent = e.title; sel.appendChild(op); });
      if (d.disaster_event) sel.value = d.disaster_event;
      $("poFilterWrap").hidden = d.events.length < 2 && !d.disaster_event;
    }

    var kpi = [["posko_aktif", "posko aktif"], ["bencana", "bencana ditangani"], ["anggota", "anggota terdaftar"],
      ["kiriman_diterima", "kiriman bantuan diterima"], ["kiriman_keluar", "kiriman disalurkan"], ["pasien", "pasien dilayani"],
      ["porsi", "porsi makanan"], ["pengungsi", "pengungsi tertampung"], ["dicari", "laporan orang hilang"],
      ["ditemukan", "orang ditemukan"], ["penugasan_relawan", "penugasan relawan"], ["kebutuhan_terbuka", "kebutuhan terbuka"]];
    var totalDana = d.programs.reduce(function (s, p) { return s + (p.dana_terkonfirmasi || 0); }, 0);
    var html = card("Ringkasan kerja", "Angka dari catatan posko dan program organisasi ini beserta organisasi anaknya.",
      '<div class="po-kpis">' + kpi.filter(function (k) { return t[k[0]] || ["posko_aktif", "bencana"].indexOf(k[0]) >= 0; })
        .map(function (k) { return '<div class="po-kpi"><b>' + num(t[k[0]]) + "</b><span>" + k[1] + "</span></div>"; }).join("") +
      (totalDana ? '<div class="po-kpi"><b>' + rp(totalDana) + "</b><span>dana program terkonfirmasi</span></div>" : "") + "</div>");

    var types = {};
    d.poskos.forEach(function (p) { types[p.type] = p.type_label; });
    html += card("Peta posko", "Klik titik untuk melihat peran posko dan membuka halamannya.",
      '<div id="poMap" role="region" aria-label="Peta posko"></div><div class="po-legend">' +
      Object.keys(types).map(function (k) { return '<span><i style="background:' + (COLORS[k] || "#555") + '"></i>' + esc(types[k]) + "</span>"; }).join("") + "</div>");

    html += card("Peran per bidang", "Apa yang dikerjakan tiap jenis posko.",
      '<div class="po-roles">' + d.roles.map(function (r) {
        var ms = Object.keys(r.metrics || {}).filter(function (k) { return METRIC[k] && r.metrics[k]; });
        var names = d.poskos.filter(function (p) { return p.type === r.type; }).map(function (p) { return p.title.replace(/^\[SIMULASI\]\s*/, ""); });
        return '<div class="po-role"><h3><i style="display:inline-block;width:10px;height:10px;border-radius:50%;background:' + (COLORS[r.type] || "#555") +
          '"></i> ' + esc(r.label) + '</h3><span class="po-muted">' + num(r.posko) + " posko: " + esc(names.slice(0, 3).join(", ")) + (names.length > 3 ? ", …" : "") + "</span>" +
          (ms.length ? "<ul>" + ms.map(function (k) { return "<li>" + num(r.metrics[k]) + " " + METRIC[k] + "</li>"; }).join("") + "</ul>" : "") + "</div>";
      }).join("") + "</div>");

    if (d.organizations.length > 1) {
      html += card("Organisasi dalam jaringan", "Organisasi induk dan organisasi anak (ortom / cabang) yang tercatat.",
        '<div class="po-orgs">' + d.organizations.map(function (x) {
          return '<span class="po-badge ' + (x.open ? "" : "lock") + '">' + esc(x.title) + (x.is_root ? " · induk" : "") + (x.open ? "" : " · tertutup") + "</span>";
        }).join("") + "</div>");
    }

    var two = "";
    if (d.alur.length) {
      two += card("Alur bantuan", "Kiriman terbaru dari dan ke posko organisasi ini.",
        '<ul class="po-list">' + d.alur.slice(0, 10).map(function (a) {
          return "<li><b>" + num(a.jumlah) + " " + esc(a.satuan || "") + " " + esc(a.barang || "") + "</b><br>" + esc(String(a.dari).replace(/^\[SIMULASI\]\s*/, "")) + " → " +
            esc(String(a.ke || "").replace(/^\[SIMULASI\]\s*/, "")) + (a.angkutan ? '<br><span class="po-muted">Angkutan: ' + esc(String(a.angkutan).replace(/^\[SIMULASI\]\s*/, "")) + "</span>" : "") +
            ' <span class="po-badge">' + esc(a.status) + "</span></li>";
        }).join("") + "</ul>");
    }
    if (d.partners.length) {
      two += card("Mitra", "Organisasi lain yang bekerja bersama: pengirim, angkutan, atau penerima bantuan.",
        '<ul class="po-list">' + d.partners.map(function (p) { return "<li><b>" + esc(p.title) + "</b><br><span class=\"po-muted\">" + esc(p.peran.join(", ")) + "</span></li>"; }).join("") + "</ul>");
    }
    if (d.timeline.length) {
      two += card("Kegiatan terbaru", "", '<ul class="po-list">' + d.timeline.slice(0, 12).map(function (x) {
        return "<li>" + esc(String(x.teks).replace(/\[SIMULASI\]\s*/g, "")) + (x.waktu ? '<br><span class="po-muted">' + esc(x.waktu.slice(0, 16)) + "</span>" : "") + "</li>";
      }).join("") + "</ul>");
    }
    if (two) html += '<div class="po-two">' + two + "</div>";

    if (d.programs.length) {
      html += card("Program & donasi", "Program khusus organisasi. Donasi dihitung setelah dikonfirmasi penyelenggara.",
        '<ul class="po-list">' + d.programs.map(function (p) {
          var pct = p.target ? Math.min(100, Math.round(p.terkumpul / p.target * 100)) : 0;
          return "<li><b>" + esc(String(p.title).replace(/^\[SIMULASI\]\s*/, "")) + "</b><br><span class=\"po-muted\">" + esc(p.organisasi) + (p.lokasi ? " · " + esc(p.lokasi) : "") + "</span>" +
            '<div class="po-bar"><i style="width:' + pct + '%"></i></div>' + rp(p.terkumpul) + " dari " + rp(p.target) + " · " + num(p.donatur) + " donatur" +
            (p.progres ? " · progres " + p.progres + "%" : "") + (p.update_terakhir ? '<br><span class="po-muted">' + esc(String(p.update_terakhir).replace(/\[SIMULASI\]\s*/g, "")) + "</span>" : "") +
            (p.event ? '<br><a href="program-khusus.html?event=' + encodeURIComponent(p.event) + '">Lihat program khusus bencana ini →</a>' : "") + "</li>";
        }).join("") + "</ul>");
    }

    html += card("Cara membantu", d.needs.length ? "Kebutuhan yang masih terbuka di posko organisasi ini." : "Belum ada kebutuhan terbuka yang dicatat.",
      (d.needs.length ? '<ul class="po-list">' + d.needs.slice(0, 10).map(function (n) {
        return "<li><b>" + esc(n.item) + "</b> — " + num(n.jumlah) + " " + esc(n.satuan || "") + '<br><span class="po-muted">' + esc(String(n.posko || "").replace(/^\[SIMULASI\]\s*/, "")) +
          (n.urgensi ? " · urgensi " + esc(n.urgensi) : "") + "</span></li>";
      }).join("") + "</ul>" : "") +
      '<div class="po-cta"><a class="btn primary" href="kirim-bantuan.html' + ($("poEvent").value ? "?event=" + encodeURIComponent($("poEvent").value) : "") + '">Kirim Bantuan</a>' +
      '<a class="btn" href="management-relawan.html">Jadi Relawan</a></div>');

    var c = d.checklist;
    html += card("Kredibilitas", "Kelengkapan data organisasi di Rescue-Net.",
      '<ul class="po-list"><li>' + (c.identitas_organisasi ? "✓" : "–") + " Identitas organisasi diverifikasi</li><li>" +
      (c.kontak_person ? "✓" : "–") + " Ada narahubung resmi (kontak hanya untuk petugas)</li><li>" +
      (c.trusted_verifier ? "✓" : "–") + " Didukung verifikator wilayah</li></ul>");

    $("poBody").innerHTML = html;
    renderMap(d.poskos);
  }

  async function load() {
    var id = params.get("id");
    if (!id) return pickList();
    try {
      var d = await call("org_profile", { organization: id, disaster_event: $("poEvent").value || params.get("event") || undefined });
      render(d);
    } catch (e) {
      $("poTitle").textContent = "Organisasi tidak ditemukan";
      $("poBody").innerHTML = card("Tidak bisa dimuat", "", '<p>' + esc(e.message || e) + '</p><p><a href="profil-organisasi.html">Lihat semua organisasi</a></p>');
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    $("poEvent").addEventListener("change", load);
    load();
  });
})();
