/* tawarkan-alat.js — Tawarkan / Sumbangkan Alat (owner 2026-11-03): a tool owner offers a tool (hibah /
   pinjam / sewa) with its data, usable date range, operator included or not, and mobilisation needs; lists
   "Alat Saya" with edit / withdraw. api_recovery_support.{tool_form_options, offer_tool, update_tool_offer,
   withdraw_tool, my_tools} */
(function () {
  "use strict";
  var A = "rescue_net.api_recovery_support.";
  var $ = function (s) { return document.querySelector(s); };
  var qs = new URLSearchParams(location.search);
  function esc(s) { return window.RNUI.esc(s); }
  function fmt(n) { return window.RNUI.fmt(n); }
  function errMsg(e) { return (e && e.message) || String(e); }
  function day(s) { return s ? String(s).slice(0, 10).split("-").reverse().join("/") : ""; }
  var ev = qs.get("event") || "event-sim-001";
  var CHECKS = ["operator_included", "support_operator", "support_transport", "support_fuel", "support_accommodation", "contact_public"];
  var FIELDS = ["resource_name", "category", "quantity", "unit", "availability_status", "current_location", "capacity_description",
    "coverage_area", "available_from", "available_until", "daily_operating_cost", "operator_count", "mobilization_needs",
    "mobilization_cost", "support_notes", "pic_name", "pic_phone", "pic_email", "notes", "offer_type",
    "brand", "model", "manufacture_year", "serial_number", "tool_condition"];
  var CATALOG = null, CONDITIONS = [], renderSpecs = null;
  var MINE = [];

  function options(sel, list) {
    sel.innerHTML = list.map(function (o) { return '<option value="' + esc(o.value) + '">' + esc(o.label) + "</option>"; }).join("");
  }

  function collect(f) {
    var a = {};
    FIELDS.forEach(function (k) { if (f.elements[k]) a[k] = f.elements[k].value.trim(); });
    CHECKS.forEach(function (k) { a[k] = f.elements[k].checked ? 1 : 0; });
    a.specs = window.RNEquip.readSpecs($("#taSpecs"));
    return a;
  }

  function fill(f, t) {
    f.elements.category.value = t.category || "lainnya";
    f.elements.category.disabled = true;
    $("#taIdentity").innerHTML = window.RNEquip.identityHtml(t, CONDITIONS);
    renderSpecs(t.specs);
    FIELDS.forEach(function (k) {
      if (k === "category") return;
      if (!f.elements[k]) return;
      var v = t[k];
      if (k === "available_from" || k === "available_until") v = v ? String(v).slice(0, 10) : "";
      f.elements[k].value = v == null ? "" : v;
    });
    CHECKS.forEach(function (k) { f.elements[k].checked = !!t[k]; });
    f.elements.resource_profile.value = t.name;
    var showPhotos = function (photos) {
      $("#taPhotos").hidden = false;
      $("#taPhotos").innerHTML = "<small class=\"rn-muted\">Foto tersimpan:</small>" + window.RNEquip.photosHtml(photos, true);
      window.RNEquip.wirePhotoDelete($("#taPhotos"), t.name, function (p) { t.photos = p; showPhotos(p); });
    };
    showPhotos(t.photos || []);
    f.elements.disaster_event.value = t.disaster_event || ev;
    f.elements.disaster_event.disabled = true;
    f.elements.owner_choice.disabled = true;
    $("#taFormTitle").textContent = "Ubah: " + t.resource_name;
    $("#taSubmit").textContent = "Simpan perubahan";
    $("#taReset").hidden = false;
    f.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function resetForm() {
    var f = $("#taForm");
    f.reset();
    f.elements.resource_profile.value = "";
    f.elements.disaster_event.value = ev;
    f.elements.disaster_event.disabled = false;
    f.elements.owner_choice.disabled = false;
    f.elements.category.disabled = false;
    $("#taPhotos").hidden = true; $("#taPhotos").innerHTML = "";
    $("#taIdentity").innerHTML = window.RNEquip.identityHtml({}, CONDITIONS);
    renderSpecs();
    $("#taFormTitle").textContent = "Data Alat yang Ditawarkan";
    $("#taSubmit").textContent = "Tawarkan Alat";
    $("#taReset").hidden = true;
  }

  async function uploadPhoto(id, files) {
    var fail = await window.RNEquip.uploadPhotos(id, files, $("#taMsg"));
    if (fail.length) window.alert("Data tersimpan, sebagian foto gagal: " + fail.join("; "));
  }

  function renderMine() {
    $("#taMinePanel").hidden = false;
    $("#taMine").innerHTML = MINE.length ? MINE.map(function (t) {
      var when = (t.available_from || t.available_until) ? day(t.available_from) + " – " + (day(t.available_until) || "tanpa batas") : "masa pakai belum diisi";
      return '<div class="rn-pa-mine"><b><a href="penyedia-alat.html?id=' + encodeURIComponent(t.name) + "&event=" + encodeURIComponent(t.disaster_event || ev) + '">' +
        esc(t.resource_name) + "</a></b> · " + fmt(t.quantity || 1) + " " + esc(t.unit || "") +
        ' <span class="chip">' + esc(t.status_label) + "</span>" + (t.offer_label ? ' <span class="chip success">' + esc(t.offer_label) + "</span>" : "") +
        '<div class="rn-muted" style="font-size:13px;margin-top:4px">' + esc((t.provider || {}).label || "") + " · " + esc(when) +
        (t.operator_included ? " · termasuk operator" : "") + "</div>" +
        '<div style="margin-top:6px;display:flex;gap:8px;flex-wrap:wrap"><button type="button" class="btn ghost mini" data-edit="' + esc(t.name) + '">Ubah</button>' +
        (t.availability_status !== "unavailable" ? '<button type="button" class="btn ghost mini" data-withdraw="' + esc(t.name) + '">Tarik penawaran</button>' : "") +
        "</div></div>";
    }).join("") : '<p class="rn-muted">Belum ada alat yang Anda tawarkan.</p>';
  }

  async function loadMine() {
    try { MINE = (await window.RN_FRAPPE.call(A + "my_tools")).tools || []; } catch (e) { MINE = []; }
    renderMine();
    var want = qs.get("edit");
    if (want) {
      var t = MINE.filter(function (x) { return x.name === want; })[0];
      if (t) fill($("#taForm"), t);
    }
  }

  async function init() {
    var back = "alat-kerja.html?event=" + encodeURIComponent(ev) + "#penyedia";
    $("#taBack").href = back;
    var o;
    try { o = await window.RN_FRAPPE.call(A + "tool_form_options"); }
    catch (e) {
      $("#taLogin").hidden = false;
      $("#taLoginLink").href = "auth.html?next=" + encodeURIComponent(location.pathname + location.search);
      $("#taWho").textContent = "Tamu";
      return;
    }
    $("#taWho").textContent = "Pemilik alat";
    $("#taFormPanel").hidden = false;
    var f = $("#taForm");
    CATALOG = o.catalog; CONDITIONS = o.conditions || [];
    $("#taCategory").innerHTML = window.RNEquip.categoryOptions(CATALOG, "lainnya");
    $("#taIdentity").innerHTML = window.RNEquip.identityHtml({}, CONDITIONS);
    renderSpecs = window.RNEquip.wire(f, CATALOG, $("#taSpecs"), $("#taUnit"));
    options($("#taOfferType"), o.offer_types);
    options($("#taStatus"), o.statuses);
    $("#taOfferType").value = "pinjam";
    (o.organizations || []).forEach(function (g) {
      var opt = document.createElement("option");
      opt.value = "org:" + g.name;
      opt.textContent = "Organisasi: " + g.title;
      $("#taOwner").appendChild(opt);
    });
    f.elements.disaster_event.value = ev;
    f.elements.operator_included.addEventListener("change", function () {
      if (f.elements.operator_included.checked) f.elements.support_operator.checked = false;
    });
    $("#taReset").addEventListener("click", resetForm);
    f.addEventListener("submit", async function (e) {
      e.preventDefault();
      var m = $("#taMsg");
      var args = collect(f);
      var id = f.elements.resource_profile.value;
      m.textContent = "Menyimpan…";
      try {
        var photo = f.elements.photo.files;
        if (id) {
          args.resource_profile = id;
          delete args.category;
          await window.RN_FRAPPE.call(A + "update_tool_offer", args, { method: "POST" });
          if (photo.length) await uploadPhoto(id, photo);
          m.innerHTML = 'Tersimpan. <a href="penyedia-alat.html?id=' + encodeURIComponent(id) + "&event=" + encodeURIComponent(ev) + '">Lihat halaman alat</a>';
        } else {
          var owner = f.elements.owner_choice.value;
          args.disaster_event = f.elements.disaster_event.value.trim();
          if (owner.indexOf("org:") === 0) { args.owner_type = "organization"; args.organization = owner.slice(4); }
          else args.owner_type = "individual";
          var r = await window.RN_FRAPPE.call(A + "offer_tool", args, { method: "POST" });
          if (photo.length) await uploadPhoto(r.resource_profile, photo);
          m.innerHTML = 'Terima kasih, alat sudah tercatat. <a href="penyedia-alat.html?id=' + encodeURIComponent(r.resource_profile) +
            "&event=" + encodeURIComponent(args.disaster_event) + '">Lihat halaman alat</a> · <a href="' + back + '">ke daftar penyedia</a>';
        }
        resetForm();
        await loadMine();
      } catch (err) { m.textContent = "Gagal: " + errMsg(err); }
    });
    $("#taMine").addEventListener("click", async function (e) {
      var b = e.target.closest("button");
      if (!b) return;
      if (b.dataset.edit) {
        var t = MINE.filter(function (x) { return x.name === b.dataset.edit; })[0];
        if (t) fill(f, t);
      } else if (b.dataset.withdraw) {
        if (window.confirm && !window.confirm("Tarik penawaran alat ini? Status menjadi 'Tidak tersedia'.")) return;
        try { await window.RN_FRAPPE.call(A + "withdraw_tool", { resource_profile: b.dataset.withdraw }, { method: "POST" }); await loadMine(); }
        catch (err) { window.alert("Gagal: " + errMsg(err)); }
      }
    });
    await loadMine();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
})();
