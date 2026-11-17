/* Shared accessible donut renderer. No requests: use only the page's permitted response. */
(function () {
  'use strict';
  var UI = window.RNUI, esc = UI.esc, fmt = UI.fmt;
  var colors = ['#3f8f65', '#3b82c4', '#dd8a2f', '#e8835d', '#8768a6', '#d9d2c8'];
  function num(v) { v = Number(v); return Number.isFinite(v) && v > 0 ? v : 0; }
  function color(v, i) { return /^#[0-9a-f]{6}$/i.test(v || '') ? v : colors[i % colors.length]; }
  function model(segments) {
    var rows = (segments || []).map(function (s, i) {
      return {label: String(s.label || 'Lainnya'), value: num(s.value), color: color(s.color, i)};
    });
    var total = rows.reduce(function (a, s) { return a + s.value; }, 0), acc = 0;
    rows.forEach(function (s) { s.start = acc; s.pct = total ? s.value / total * 100 : 0; acc += s.pct; s.end = acc; });
    return {rows: rows, total: total};
  }
  function pct(n) { return n.toLocaleString('id-ID', {maximumFractionDigits: 1}); }
  // Also accepts existing ring/legend nodes so older posko charts share the same math and accessibility.
  function paint(ring, legend, options) {
    var m = model(options.segments), unit = options.unit || '';
    if (ring) {
      var stops = m.rows.filter(function (s) { return s.value; }).map(function (s) {
        return s.color + ' ' + s.start + '% ' + s.end + '%';
      });
      ring.style.background = stops.length ? 'conic-gradient(' + stops.join(',') + ')' : '#e5e0da';
      ring.setAttribute('role', 'img');
      ring.setAttribute('aria-label', (options.title || 'Ringkasan') + ': ' +
        (options.unavailable ? options.note : m.total ? m.rows.map(function (s) { return s.label + ' ' + fmt(s.value) + ' ' + unit + ' (' + pct(s.pct) + '%)'; }).join('; ') : 'Belum ada data'));
    }
    if (legend) legend.innerHTML = m.rows.map(function (s) {
      return '<li><span class="rn-donut-dot" style="background:' + s.color + '"></span><span>' + esc(s.label) +
        '<br><b>' + fmt(s.value) + '</b> ' + esc(unit) + ' <small>(' + pct(s.pct) + '%)</small></span></li>';
    }).join('') + (!m.total ? '<li>Belum ada data untuk grafik.</li>' : '');
    return m.total;
  }
  function donut(options) {
    var m = model(options.segments);
    return '<article class="panel rn-pie-card"><h3>' + esc(options.title) + '</h3><div class="rn-pie-wrap">' +
      '<div class="rn-donut rn-pie-ring"><div class="rn-donut-center" aria-hidden="true"><strong>' + (options.unavailable ? '—' : fmt(m.total)) +
      '</strong><small>' + esc(options.unit || 'catatan') + '</small></div></div><ul class="rn-donut-legend rn-pie-legend"></ul></div>' +
      (options.note ? '<p class="rn-muted">' + esc(options.note) + '</p>' : '') + '</article>';
  }
  donut.paint = paint;
  UI.donut = donut;
  function mount(id, charts) {
    var host = typeof id === 'string' ? document.getElementById(id) : id;
    if (!host) return;
    host.hidden = false;
    host.innerHTML = charts.map(donut).join('');
    host.querySelectorAll('.rn-pie-card').forEach(function (card, i) {
      paint(card.querySelector('.rn-pie-ring'), card.querySelector('.rn-pie-legend'), charts[i]);
    });
  }
  function category(name) {
    var s = String(name || '').toLowerCase();
    if (/(air|minum|mineral|galon|aqua)/.test(s)) return 'Air & Minuman';
    if (/(beras|mie|instan|sembako|makan|nasi|biskuit|roti|gula|garam|minyak|susu|pangan|lauk)/.test(s)) return 'Pangan';
    if (/(selimut|pakaian|baju|sandang|terpal|tenda|tikar|matras|seprai)/.test(s)) return 'Sandang & Hunian';
    if (/(obat|medis|p3k|masker|perban|antiseptik|vitamin|infus|oralit)/.test(s)) return 'Obat & Medis';
    if (/(popok|pembalut|sabun|pasta|higien|hygiene|sanitasi|tissue|diapers)/.test(s)) return 'Higienis';
    return 'Lainnya';
  }
  function grouped(rows, label) {
    var groups = new Map();
    rows.forEach(function (r) { var k = label(r) || 'Lainnya'; groups.set(k, (groups.get(k) || 0) + 1); });
    var segs = Array.from(groups, function (p) { return {label: p[0], value: p[1]}; }).sort(function (a, b) { return b.value - a.value || a.label.localeCompare(b.label); });
    var other = segs.filter(function (s) { return s.label === 'Lainnya'; }).reduce(function (n, s) { return n + s.value; }, 0);
    segs = segs.filter(function (s) { return s.label !== 'Lainnya'; });
    other += segs.slice(5).reduce(function (n, s) { return n + s.value; }, 0);
    return segs.slice(0, 5).concat(other ? [{label: 'Lainnya', value: other}] : []);
  }
  function needs(rows, note) {
    var met = 0, short = 0, critical = 0;
    (rows || []).forEach(function (n) {
      var status = String(n.need_status || n.status || '').toLowerCase();
      if (/^(cancelled|rejected)$/.test(status)) return;
      if (/^(fulfilled|closed|met)$/.test(status)) met++;
      else if (/^(critical|urgent|high|tinggi|darurat)$/.test(String(n.urgency || n.priority || '').toLowerCase())) critical++;
      else short++;
    });
    return {title: 'Kebutuhan tercatat', unit: 'catatan', note: note || 'Berdasarkan status kebutuhan pada daftar yang dimuat.', segments: [
      {label: 'Terpenuhi / ditutup', value: met, color: '#3f8f65'},
      {label: 'Kurang / terbuka', value: short, color: '#dd8a2f'},
      {label: 'Kritis / mendesak', value: critical, color: '#c9534f'}]};
  }
  function stocks(rows, title) {
    // Latest per item; observations are returned newest first. Never add kg to litres.
    var seen = new Set();
    var ready = (rows || []).filter(function (r) {
      var key = String(r.item || r.item_name || '').trim().toLowerCase();
      if (!key || seen.has(key)) return false;
      seen.add(key);
      return num(r.stok_ada == null ? (r.quantity == null ? r.current_quantity : r.quantity) : r.stok_ada) > 0;
    });
    return {title: title || 'Stok tersedia per kategori', unit: 'jenis barang', segments: grouped(ready, function (r) { return r.category_label || category(r.item || r.item_name); }),
      note: 'Jumlah jenis dengan stok positif, bukan total volume. Lima kategori terbesar + lainnya; mengikuti data yang dimuat.'};
  }
  function logistics(b) {
    var k = b.kpi || {}, open = num(k.kebutuhan_terbuka), crit = Math.min(open, num(k.kebutuhan_kritis));
    mount('rnPoskoCharts', [{title: 'Kebutuhan terbuka', unit: 'catatan', segments: [
      {label: 'Kritis / mendesak', value: crit, color: '#c9534f'}, {label: 'Terbuka lainnya', value: open - crit, color: '#dd8a2f'}],
      note: 'Dari ringkasan posko. Kebutuhan yang sudah ditutup tidak termasuk.'},
      b.detail_allowed ? stocks(b.stock_cards) : {title: 'Stok tersedia per kategori', unavailable: true, segments: [], unit: 'jenis barang', note: 'Rincian stok dibatasi oleh pengaturan berbagi posko.'}]);
  }
  function equipment(d) {
    var rows = (d.tools || []).filter(function (t) { return t.availability_status === 'available' && num(t.quantity || 1) > num(t.deployed_qty); });
    mount('rnPoskoCharts', [
      {title: 'Permintaan alat terbuka', unit: 'permintaan', segments: [
        {label: 'Kategori ada di posko', value: (d.requests || []).filter(function (r) { return r.can_serve; }).length},
        {label: 'Kategori belum tersedia', value: (d.requests || []).filter(function (r) { return !r.can_serve; }).length, color: '#dd8a2f'}],
        note: 'Permintaan bencana yang dimuat. Kecocokan kategori belum berarti stok cukup atau booking disetujui.'},
      {title: 'Alat siap per kategori', unit: 'jenis alat', segments: grouped(rows, function (t) { return t.category_label || t.group; }),
        note: 'Jenis alat berstatus tersedia dengan sisa unit setelah penugasan. Lima kategori terbesar + lainnya.'}]);
  }
  function incoming(host, d) {
    var rows = [].concat(d.in_transit || [], d.booked || [], d.arrivals || []);
    mount(host, [{title: 'Menuju posko per status', unit: 'catatan', segments: grouped(rows, function (r) { return r.status_label || r.status; }),
      note: 'Catatan bantuan, booking, armada dan relawan pada panel ini; satu pengiriman dapat memiliki catatan terkait.'}]);
  }
  window.RNPoskoCharts = {mount: mount, needs: needs, stocks: stocks, logistics: logistics, equipment: equipment, incoming: incoming, category: category};
})();
