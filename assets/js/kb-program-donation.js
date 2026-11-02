/* Kirim Bantuan → Donasi ke Program Khusus (owner 2026-11-02: "program khusus ... isi contoh datanya pakai user
 * atau donatur lengkap dengan nama atau tidak mau disebutkan namanya, itu bisa melalui kirim bantuan").
 * Same path as the Donor Program page: create_cash_donation (login) → pending → the initiator confirms →
 * public wall shows the name or "Donatur Anonim". */
(function () {
  "use strict";
  var API = "rescue_net.api_donor_program.";
  var box = document.getElementById("kbDonasi");
  if (!box) return;
  var form = document.getElementById("kbDonForm");
  var msg = document.getElementById("kbDonMsg");
  var wall = document.getElementById("kbDonWall");
  var bank = document.getElementById("kbDonBank");
  var picker = document.querySelector("[data-disaster-picker]");
  var PROGRAMS = [];
  function esc(v) { return String(v == null ? "" : v).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function rp(v) { return "Rp " + new Intl.NumberFormat("id-ID").format(Math.round(v || 0)); }
  function call(m, a, post) { return window.RN_FRAPPE.call(API + m, a || {}, post ? { method: "POST" } : undefined); }
  function event() {
    var q = new URLSearchParams(location.search);
    return (picker && picker.value) || q.get("event") || "";
  }

  async function loadPrograms() {
    var sel = form.donor_program;
    sel.innerHTML = '<option value="">Memuat program…</option>';
    try {
      var b = await call("program_board", { disaster_event: event() });
      PROGRAMS = (b.programs || []).filter(function (p) { return p.status !== "completed" && p.status !== "cancelled"; });
    } catch (e) { PROGRAMS = []; }
    sel.innerHTML = PROGRAMS.length
      ? '<option value="">— pilih program —</option>' + PROGRAMS.map(function (p) {
          return '<option value="' + esc(p.name) + '">' + esc(p.program_name) + (p.initiator_verified ? " ✔" : "") + "</option>"; }).join("")
      : '<option value="">Belum ada program khusus di bencana ini</option>';
    var want = new URLSearchParams(location.search).get("program");
    if (want && PROGRAMS.some(function (p) { return p.name === want; })) { sel.value = want; showProgram(want); }
    else { wall.innerHTML = ""; bank.hidden = true; }
  }

  async function showProgram(id) {
    wall.innerHTML = ""; bank.hidden = true;
    if (!id) return;
    try {
      var d = await call("program_detail", { program: id });
      var b = d.bank || {};
      if (b.account_number) {
        bank.hidden = false;
        bank.innerHTML = "Transfer ke rekening pemrakarsa: <b>" + esc(b.bank_name) + " " + esc(b.account_number) + "</b> a.n. " + esc(b.account_holder) +
          "<br><small>Setelah transfer, kirim formulir ini. Jangan transfer ke rekening yang dikirim lewat pesan pribadi.</small>";
      }
      var w = d.donations || {};
      var rows = w.public || [];
      wall.innerHTML = '<h4 style="margin:14px 0 6px">Donasi masuk — ' + esc(d.program && d.program.program_name || "") + "</h4>" +
        '<p class="rn-muted" style="margin:0 0 6px">' + rows.length + " donatur · total <b>" + rp(w.total_received) + "</b></p>" +
        (rows.length ? '<table class="rn-table" style="width:100%"><thead><tr><th>Donatur</th><th style="text-align:right">Nominal</th><th>Pesan</th></tr></thead><tbody>' +
          rows.map(function (r) { return "<tr><td>" + esc(r.donor_name) + '</td><td style="text-align:right">' + rp(r.amount) + "</td><td>" + esc(r.message || "") + "</td></tr>"; }).join("") +
          '</tbody><tfoot><tr><th>Total</th><th style="text-align:right">' + rp(w.total_received) + "</th><th></th></tr></tfoot></table>"
          : '<p class="rn-muted">Belum ada donasi yang dikonfirmasi.</p>') +
        '<p style="margin-top:8px"><a href="donor-program.html?id=' + encodeURIComponent(id) + '">Lihat program lengkap ›</a></p>';
    } catch (e) { wall.innerHTML = ""; }
  }

  async function init() {
    var me = null;
    try { me = await window.RN_FRAPPE.call("rescue_net.api_auth.session_info", {}); } catch (e) {}
    var logged = !!(me && (me.logged_in || (me.user && me.user !== "Guest")));
    document.getElementById("kbDonLogin").hidden = logged;
    form.hidden = !logged;
    if (logged && me && (me.full_name || me.name) && !form.donor_name.value) form.donor_name.value = me.full_name || me.name || "";
    await loadPrograms();
  }

  form.donor_program.addEventListener("change", function () { showProgram(form.donor_program.value); });
  if (picker) picker.addEventListener("change", function () { if (!form.hidden) loadPrograms(); });
  form.addEventListener("submit", async function (e) {
    e.preventDefault();
    var id = form.donor_program.value;
    if (!id) { msg.textContent = "Pilih program dulu."; return; }
    msg.textContent = "Mengirim…";
    try {
      await call("create_cash_donation", {
        donor_program: id, amount: form.amount.value, is_anonymous: form.is_anonymous.checked ? 1 : 0,
        donor_name: form.donor_name.value.trim(), donor_contact: form.donor_contact.value.trim(), message: form.message.value.trim(),
      }, true);
      msg.textContent = "Terima kasih! Donasi tercatat dan menunggu konfirmasi pemrakarsa" +
        (form.is_anonymous.checked ? " — akan tampil sebagai Donatur Anonim." : ".");
      form.amount.value = ""; form.message.value = "";
      showProgram(id);
    } catch (err) { msg.textContent = "Gagal: " + ((err && err.message) || err); }
  });
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
})();
