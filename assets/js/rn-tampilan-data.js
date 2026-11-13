/* Tombol tampilan data di Home (owner 2026-11-13): "Lihat Simulasi" / "Riil Data Bencana".
 * Pilihan per pengunjung, disimpan di cookie rn_tampilan (dibaca server: services/drill.simulation_hidden).
 * Tanpa cookie = simulasi tampil (bawaan). Saklar Mode Operasional super admin tetap saklar utama. */
(function () {
  var COOKIE = 'rn_tampilan';
  function current() {
    var m = document.cookie.match(/(?:^|;\s*)rn_tampilan=([^;]*)/);
    return m && decodeURIComponent(m[1]) === 'riil' ? 'riil' : 'simulasi';
  }
  function choose(v) {
    var sec = location.protocol === 'https:' ? '; Secure' : '';
    if (v === 'riil') document.cookie = COOKIE + '=riil; path=/; max-age=31536000; SameSite=Lax' + sec;
    else document.cookie = COOKIE + '=; path=/; max-age=0; SameSite=Lax' + sec;
    location.reload();
  }
  function css() {
    if (document.getElementById('rnTampilanCss')) return;
    var s = document.createElement('style'); s.id = 'rnTampilanCss';
    s.textContent =
      '.rn-tampilan{display:flex;flex-wrap:wrap;align-items:center;gap:8px 12px;margin:10px 40px 0;padding:8px 12px;' +
      'border:1px solid #e3d5c8;border-radius:10px;background:#fff;font-size:14px}' +
      '.rn-tampilan-label{font-weight:700}' +
      '.rn-tampilan-btns{display:inline-flex;border:1px solid #c9b8a6;border-radius:8px;overflow:hidden}' +
      '.rn-tampilan-btns button{border:0;background:#fff;padding:7px 14px;font:inherit;font-weight:600;cursor:pointer;color:#5a4636}' +
      '.rn-tampilan-btns button+button{border-left:1px solid #c9b8a6}' +
      '.rn-tampilan-btns button[aria-pressed="true"]{background:#b4532a;color:#fff}' +
      '.rn-tampilan-btns button[aria-pressed="true"].riil{background:#1f6f43}' +
      '.rn-tampilan-btns button:disabled{opacity:.45;cursor:not-allowed}' +
      '.rn-tampilan-note{color:#6b5a4c;font-size:13px;flex:1 1 260px}' +
      '@media (max-width:900px){.rn-tampilan{margin:8px 12px 0}.rn-tampilan-btns{width:100%}.rn-tampilan-btns button{flex:1}}';
    document.head.appendChild(s);
  }
  function render(box, operational) {
    var v = operational ? 'riil' : current();
    var note = operational
      ? 'Mode Operasional Riil aktif: data simulasi disembunyikan untuk semua pengunjung.'
      : (v === 'riil'
        ? 'Hanya data bencana riil. Data simulasi/latihan disembunyikan.'
        : 'Termasuk data SIMULASI (latihan, bukan kejadian nyata).');
    box.innerHTML =
      '<span class="rn-tampilan-label">Tampilan data:</span>' +
      '<span class="rn-tampilan-btns" role="group" aria-label="Pilih tampilan data">' +
      '<button type="button" data-v="simulasi" aria-pressed="' + (v === 'simulasi') + '"' + (operational ? ' disabled' : '') + '>Lihat Simulasi</button>' +
      '<button type="button" class="riil" data-v="riil" aria-pressed="' + (v === 'riil') + '"' + (operational ? ' disabled' : '') + '>Riil Data Bencana</button>' +
      '</span><span class="rn-tampilan-note">' + note + '</span>';
    Array.prototype.forEach.call(box.querySelectorAll('button[data-v]'), function (b) {
      b.addEventListener('click', function () { if (b.getAttribute('data-v') !== current()) choose(b.getAttribute('data-v')); });
    });
  }
  function init() {
    var box = document.getElementById('rnTampilanData');
    if (!box) return;
    css(); render(box, false);
    fetch('/rescue-net-frappe/api/method/rescue_net.api_operational_mode.status', { credentials: 'same-origin' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (j) { if (j && j.message && j.message.operational) render(box, true); })
      .catch(function () {});
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
