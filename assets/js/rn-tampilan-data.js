/* Tampilan data (owner 2026-11-13): "Lihat Simulasi" / "Riil Data Bencana", pilihan per pengunjung.
 * Disimpan di cookie rn_tampilan (dibaca server: services/drill.simulation_hidden + services/sim_scrub).
 * Tanpa cookie = simulasi tampil (bawaan). Pilihan riil berlaku 1 tahun, diperpanjang tiap membuka Home.
 * Home: bilah #rnTampilanData; klik -> simpan lalu ke halaman Bencana Aktif. Registrasi: radio name="rn_tampilan".
 * Saklar Mode Operasional super admin tetap saklar utama. */
(function () {
  var COOKIE = 'rn_tampilan';
  function current() {
    var m = document.cookie.match(/(?:^|;\s*)rn_tampilan=([^;]*)/);
    return m && decodeURIComponent(m[1]) === 'riil' ? 'riil' : 'simulasi';
  }
  function save(v) {
    var sec = location.protocol === 'https:' ? '; Secure' : '';
    try { sessionStorage.removeItem('rn_opmode'); } catch (e) {}
    if (v === 'riil') { try { localStorage.removeItem('rn_active_event'); localStorage.removeItem('rn-active-event'); } catch (e) {} }
    if (v === 'riil') document.cookie = COOKIE + '=riil; path=/; max-age=31536000; SameSite=Lax' + sec;
    else document.cookie = COOKIE + '=; path=/; max-age=0; SameSite=Lax' + sec;
  }
  window.RNTampilan = { current: current, save: save };

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
      '.rn-tampilan-note{color:#6b5a4c;font-size:13px;flex:1 1 260px;line-height:1.4}' +
      '.rn-tampilan-note small{display:block;color:#8a7766}' +
      '@media (max-width:900px){.rn-tampilan{margin:8px 12px 0}.rn-tampilan-btns{width:100%}.rn-tampilan-btns button{flex:1}}';
    document.head.appendChild(s);
  }
  function render(box, operational) {
    var v = operational ? 'riil' : current();
    var note = operational
      ? 'Mode Operasional Riil aktif: data simulasi disembunyikan untuk semua pengunjung.'
      : (v === 'riil'
        ? 'Sekarang: hanya data bencana riil. Data simulasi/latihan disembunyikan di semua halaman.'
        : 'Sekarang: termasuk data SIMULASI (latihan, bukan kejadian nyata).');
    var hint = operational ? '' : '<small>Pilihan berlaku di semua halaman. Untuk mengganti pilihan, kembali ke halaman Home ini.</small>';
    box.innerHTML =
      '<span class="rn-tampilan-label">Tampilan data:</span>' +
      '<span class="rn-tampilan-btns" role="group" aria-label="Pilih tampilan data">' +
      '<button type="button" data-v="simulasi" aria-pressed="' + (v === 'simulasi') + '"' + (operational ? ' disabled' : '') + '>Lihat Simulasi</button>' +
      '<button type="button" class="riil" data-v="riil" aria-pressed="' + (v === 'riil') + '"' + (operational ? ' disabled' : '') + '>Riil Data Bencana</button>' +
      '</span><span class="rn-tampilan-note">' + note + hint + '</span>';
    Array.prototype.forEach.call(box.querySelectorAll('button[data-v]'), function (b) {
      b.addEventListener('click', function () {
        save(b.getAttribute('data-v'));
        location.href = 'pages/bencana-aktif.html';   // owner: setelah memilih langsung ke Bencana Aktif
      });
    });
  }
  function initHome() {
    var box = document.getElementById('rnTampilanData');
    if (!box) return;
    if (current() === 'riil') save('riil');   // perpanjang 1 tahun tiap membuka Home
    css(); render(box, false);
    fetch('/rescue-net-frappe/api/method/rescue_net.api_operational_mode.status', { credentials: 'same-origin' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (j) { if (j && j.message && j.message.operational) render(box, true); })
      .catch(function () {});
  }
  function initRegister() {
    var radios = document.querySelectorAll('input[name="rn_tampilan"]');
    if (!radios.length) return;
    var v = current();
    Array.prototype.forEach.call(radios, function (r) {
      r.checked = r.value === v;
      r.addEventListener('change', function () { if (r.checked) save(r.value); });
    });
    var form = document.getElementById('registerForm');
    if (form) form.addEventListener('submit', function () {
      var c = form.querySelector('input[name="rn_tampilan"]:checked');
      if (c) save(c.value);
    });
  }
  function init() { initHome(); initRegister(); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
