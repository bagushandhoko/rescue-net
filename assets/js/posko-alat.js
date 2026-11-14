/* posko-alat.js — Posko Alat Kerja / Support (owner 2026-11-03). api_equipment.{equipment_poskos, posko_equipment,
   equipment_catalog, save_equipment} + api_recovery_support.{upload_tool_photo, withdraw_tool}. */
(function () {
  "use strict";
  var A = "rescue_net.api_equipment.";
  var R = "rescue_net.api_recovery_support.";
  var $ = function (s) { return document.querySelector(s); };
  var qs = new URLSearchParams(location.search);
  function esc(s) { return window.RNUI.esc(s); }
  function fmt(n) { return window.RNUI.fmt(n); }
  function errMsg(e) { return (e && e.message) || String(e); }
  function day(s) { return s ? String(s).slice(0, 10).split("-").reverse().join("/") : ""; }
  function call(m, a, post) { return window.RN_FRAPPE.call(m, a || {}, post ? { method: "POST" } : undefined); }
  var POSKO = qs.get("id") || qs.get("posko") || "";
  var EVENT = qs.get("event") || "";
  var DATA = null, CATALOG = null, CONDITIONS = [], renderSpecs = null;
  var STATUS_CHIP = { available: "success", limited: "warning", maintenance: "warning", unavailable: "danger" };
  var CHECKS = ["operator_included", "support_operator", "support_transport", "support_fuel", "support_accommodation", "contact_public"];
  var FIELDS = ["category", "resource_name", "quantity", "unit", "availability_status", "current_location", "capacity_description",
    "available_from", "available_until", "coverage_area", "operator_count", "daily_operating_cost", "mobilization_cost",
    "mobilization_needs", "pic_name", "pic_phone", "pic_email", "brand", "model", "manufacture_year", "serial_number", "tool_condition"];

  function toolHref(code) { return "penyedia-alat.html?id=" + encodeURIComponent(code) + "&event=" + encodeURIComponent(EVENT); }

  async function pick() {
    $("#eqPickPanel").hidden = false;
    $("#eqRegLink").href = "registrasi-posko.html?event=" + encodeURIComponent(EVENT) + "&type=equipment";
    var d;
    try { d = await call(A + "equipment_poskos", { disaster_event: EVENT || null }); }
    catch (e) { $("#eqPick").innerHTML = '<p class="rn-muted">Gagal memuat: ' + esc(errMsg(e)) + "</p>"; return; }
    var rows = d.poskos || [];
    $("#eqPill").textContent = rows.length + " posko";
    $("#eqPick").innerHTML = rows.length ? rows.map(function (p) {
      return '<a href="posko-alat.html?id=' + encodeURIComponent(p.name) + "&event=" + encodeURIComponent(EVENT) + '"><span><b>' +
        esc(p.title) + "</b><br><small class=\"rn-muted\">" + esc(p.is_equipment_posko ? "Posko Alat Kerja / Support" : "Posko lain dengan alat") +
        (p.address ? " · " + esc(p.address) : "") + "</small></span><span>" + fmt(p.items) + " jenis · " + fmt(p.units) + " unit" +
        (p.can_manage ? ' <span class="chip success">Anda kelola</span>' : "") + "</span></a>";
    }).join("") : '<p class="rn-muted">Belum ada posko alat kerja di bencana ini. Daftarkan lewat tombol di atas (jenis: Posko Alat Kerja / Support).</p>';
  }

  function itemHtml(t) {
    var specs = (t.spec_rows || []).map(function (s) { return "<span>" + esc(s.label) + ": <b>" + esc(s.value) + "</b></span>"; }).join("");
    var ident = [t.brand, t.model, t.manufacture_year].filter(Boolean).join(" · ");
    var out = t.deployed_qty ? fmt(t.deployed_qty) + " sedang dipakai" : "";
    var needs = [t.operator_included ? "termasuk operator" + (t.operator_count ? " (" + t.operator_count + ")" : "") : "",
      t.support_transport ? "butuh transport" : "", t.support_fuel ? "butuh BBM" : ""].filter(Boolean).join(" · ");
    return '<div class="rn-eq-item' + (t.photo_url ? "" : " nophoto") + '" data-q="' + esc([t.resource_name, t.category_label, ident,
        (t.spec_rows || []).map(function (s) { return s.value; }).join(" ")].join(" ").toLowerCase()) + '">' +
      (t.photo_url ? '<a href="' + esc(toolHref(t.name)) + '"><img src="' + esc(t.photo_url) + '" alt="" loading="lazy"></a>' : "") +
      ""
      "<div><h4><a href=\"" + esc(toolHref(t.name)) + '">' + esc(t.resource_name) + "</a></h4>" +
      '<div class="rn-eq-meta">' + esc(t.category_label) + " · " + fmt(t.quantity || 1) + " " + esc(t.unit || "") +
        (ident ? " · " + esc(ident) : "") + (t.serial_number ? " · " + esc(t.serial_number) : "") +
        ((t.photos || []).length > 1 ? " · " + t.photos.length + " foto" : "") + "</div>" +
      '<div class="rn-eq-specs-view">' + specs + "</div>" +
      '<div class="rn-eq-meta"><span class="chip ' + (STATUS_CHIP[t.availability_status] || "") + '">' + esc(t.status_label) + "</span> " +
        (t.condition_label ? '<span class="chip">' + esc(t.condition_label) + "</span> " : "") +
        (out ? '<span class="chip warning">' + esc(out) + "</span> " : "") + esc(needs) +
        ((t.available_from || t.available_until) ? " · bisa dipakai " + esc(day(t.available_from) || "sekarang") + " – " + esc(day(t.available_until) || "tanpa batas") : "") + "</div>" +
      (DATA.can_manage ? '<div class="rn-eq-actions"><button type="button" class="btn ghost mini" data-edit="' + esc(t.name) + '">Ubah</button>' +
        (t.availability_status !== "unavailable" ? '<button type="button" class="btn ghost mini" data-withdraw="' + esc(t.name) + '">Tandai tidak tersedia</button>' : "") + "</div>" : "") +
      "</div></div>";
  }

  function render() {
    var d = DATA, p = d.posko;
    document.title = "Rescue-Net | " + p.title;
    $("#eqTitle").textContent = p.title;
    $("#eqSub").textContent = [p.is_equipment_posko ? "Posko Alat Kerja / Support" : "Posko", p.organization_title, p.area || p.address].filter(Boolean).join(" · ");
    $("#eqPill").textContent = fmt(d.totals.units) + " unit · " + fmt(d.totals.ready) + " siap";
    $("#eqSum").innerHTML = (d.summary || []).map(function (g) {
      return '<div class="kpi-card"><span>' + esc(g.group) + "</span><strong>" + fmt(g.units) + "</strong><small>" + fmt(g.items) + " jenis · " +
        fmt(g.ready) + " siap · " + fmt(g.deployed) + " dipakai" + (g.repair ? " · " + fmt(g.repair) + " perlu perbaikan" : "") + "</small></div>";
    }).join("") || '<p class="rn-muted">Belum ada alat di inventaris posko ini.</p>';
    var groups = {};
    (d.tools || []).forEach(function (t) { (groups[t.group] = groups[t.group] || []).push(t); });
    $("#eqList").innerHTML = Object.keys(groups).length ? (d.summary || []).map(function (g) {
      return '<h4 class="rn-eq-group">' + esc(g.group) + ' <span class="chip">' + fmt(g.items) + "</span></h4>" + (groups[g.group] || []).map(itemHtml).join("");
    }).join("") : '<p class="rn-muted">Belum ada alat.' + (d.can_manage ? " Tambahkan lewat form di bawah." : "") + "</p>";
    $("#eqDispatch").innerHTML = (d.dispatch || []).length ? d.dispatch.map(function (x) {
      return '<div class="rn-eq-row"><b><a href="' + esc(toolHref(x.resource)) + '">' + esc(x.tool_name || "Alat") + "</a></b>" +
        '<span class="chip">' + esc(x.status_label) + "</span><span>" + esc(x.destination || "-") + "</span>" +
        '<span class="rn-muted">operator ' + esc(x.operator || "-") + (x.deployed_at ? " · " + esc(day(x.deployed_at)) : "") + "</span></div>";
    }).join("") : '<p class="rn-muted">Tidak ada alat yang sedang dipakai.</p>';
    $("#eqRequests").innerHTML = (d.requests || []).length ? d.requests.slice(0, 30).map(function (q) {
      return '<div class="rn-eq-row">' + (q.can_serve ? '<span class="chip success">✓ ada</span>' : '<span class="chip neutral">—</span>') +
        "<b>" + esc(q.tool_name) + "</b><span>" + fmt(q.quantity) + " " + esc(q.unit || "") + "</span><span class=\"rn-muted\">" +
        esc(q.location || "-") + (q.needed_for ? " · " + esc(q.needed_for) : "") + "</span></div>";
    }).join("") : '<p class="rn-muted">Tidak ada permintaan alat terbuka.</p>';
    $("#eqAkLink").href = "alat-kerja.html?event=" + encodeURIComponent(EVENT) + "#penyedia";
    $("#eqContact").innerHTML = (d.contacts || []).length ? d.contacts.map(function (c) {
      return '<div class="rn-eq-row"><b>' + esc(c.name || "-") + '</b><span class="rn-muted">' + esc(c.role || c.source || "") + "</span>" +
        (c.whatsapp_url ? '<a class="btn primary mini" href="' + esc(c.whatsapp_url) + '" target="_blank" rel="noopener">WhatsApp</a>' : "") +
        (c.phone ? '<a href="tel:' + esc(c.phone) + '">' + esc(c.phone) + "</a>" : "") + "</div>";
    }).join("") : (d.contact_locked ? '<p class="rn-muted">Kontak posko hanya untuk pengguna yang berwenang. Kontak per alat ada di halaman detail alat.</p>'
      : '<p class="rn-muted">Kontak posko belum diisi.</p>');
    $("#eqFormPanel").hidden = !d.can_manage;
    filter();
  }

  function filter() {
    var q = String($("#eqSearch").value || "").trim().toLowerCase();
    document.querySelectorAll("#eqList [data-q]").forEach(function (el) { el.hidden = q && el.getAttribute("data-q").indexOf(q) < 0; });
  }

  async function load() {
    try { DATA = await call(A + "posko_equipment", { posko: POSKO }); }
    catch (e) { $("#eqSub").textContent = "Gagal memuat: " + errMsg(e); return; }
    if (!EVENT) EVENT = DATA.posko.disaster_event || "";
    $("#eqMain").hidden = false;
    if (DATA.can_manage && !CATALOG) await setupForm();
    render();
  }

  async function setupForm() {
    var c = await call(A + "equipment_catalog");
    CATALOG = c.catalog; CONDITIONS = c.conditions;
    var f = $("#eqForm");
    $("#eqCategory").innerHTML = window.RNEquip.categoryOptions(CATALOG, "ekskavator");
    $("#eqIdentity").innerHTML = window.RNEquip.identityHtml({}, CONDITIONS);
    renderSpecs = window.RNEquip.wire(f, CATALOG, $("#eqSpecs"), $("#eqUnit"));
    f.elements.operator_included.addEventListener("change", function () { if (f.elements.operator_included.checked) f.elements.support_operator.checked = false; });
    $("#eqCancel").addEventListener("click", resetForm);
    f.addEventListener("submit", save);
  }

  function resetForm() {
    var f = $("#eqForm");
    f.reset();
    f.elements.resource_profile.value = "";
    f.elements.category.disabled = false;
    $("#eqIdentity").innerHTML = window.RNEquip.identityHtml({}, CONDITIONS);
    renderSpecs();
    $("#eqPhotos").hidden = true; $("#eqPhotos").innerHTML = "";
    $("#eqFormTitle").textContent = "+ Tambah Alat ke Inventaris";
    $("#eqCancel").hidden = true;
  }

  function fillForm(t) {
    var f = $("#eqForm");
    f.elements.category.value = t.category || "lainnya";
    f.elements.category.disabled = true;                 // specs belong to the category
    $("#eqIdentity").innerHTML = window.RNEquip.identityHtml(t, CONDITIONS);
    renderSpecs(t.specs);
    FIELDS.forEach(function (k) {
      if (!f.elements[k] || k === "category") return;
      var v = t[k];
      if (k === "available_from" || k === "available_until") v = v ? String(v).slice(0, 10) : "";
      if (k === "manufacture_year" && !Number(v)) v = "";   // 0 = kosong; nilai 0 melanggar min=1950 dan diam-diam menahan Simpan perubahan
      f.elements[k].value = v == null ? "" : v;
    });
    CHECKS.forEach(function (k) { f.elements[k].checked = !!t[k]; });
    f.elements.resource_profile.value = t.name;
    var showPhotos = function (photos) {
      $("#eqPhotos").hidden = false;
      $("#eqPhotos").innerHTML = "<small class=\"rn-muted\">Foto tersimpan:</small>" + window.RNEquip.photosHtml(photos, true);
      window.RNEquip.wirePhotoDelete($("#eqPhotos"), t.name, function (p) { t.photos = p; showPhotos(p); load(); });
    };
    showPhotos(t.photos || []);
    $("#eqFormTitle").textContent = "Ubah: " + t.resource_name;
    $("#eqCancel").hidden = false;
    f.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  async function save(e) {
    e.preventDefault();
    var f = $("#eqForm"), m = $("#eqMsg");
    var args = { posko: DATA.posko.name };
    FIELDS.forEach(function (k) { if (f.elements[k]) args[k] = String(f.elements[k].value || "").trim(); });
    CHECKS.forEach(function (k) { args[k] = f.elements[k].checked ? 1 : 0; });
    args.specs = window.RNEquip.readSpecs($("#eqSpecs"));
    var id = f.elements.resource_profile.value;
    if (id) { args.resource_profile = id; delete args.category; }
    m.textContent = "Menyimpan…";
    try {
      var r = await call(A + "save_equipment", args, true);
      var files = f.elements.photo.files;
      if (files.length) {
        var fail = await window.RNEquip.uploadPhotos(r.resource_profile, files, m);
        if (fail.length) window.alert("Alat tersimpan, sebagian foto gagal: " + fail.join("; "));
      }
      m.textContent = "Tersimpan.";
      resetForm();
      await load();
    } catch (err) { m.textContent = "Gagal: " + errMsg(err); }
  }

  function wire() {
    $("#eqSearch").addEventListener("input", filter);
    $("#eqList").addEventListener("click", async function (e) {
      var b = e.target.closest("button");
      if (!b) return;
      var t = (DATA.tools || []).filter(function (x) { return x.name === (b.dataset.edit || b.dataset.withdraw); })[0];
      if (!t) return;
      if (b.dataset.edit) fillForm(t);
      else if (b.dataset.withdraw) {
        if (window.confirm && !window.confirm("Tandai '" + t.resource_name + "' tidak tersedia?")) return;
        try { await call(R + "withdraw_tool", { resource_profile: t.name }, true); await load(); }
        catch (err) { window.alert("Gagal: " + errMsg(err)); }
      }
    });
  }

  function init() {
    if (!POSKO) { pick(); return; }
    wire();
    load();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
})();
