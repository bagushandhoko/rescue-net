/* rn-equipment-specs.js — shared spec form for tools (owner 2026-11-03: data alat lebih detail secara speks).
   The catalog comes from the server (services/equipment_specs.py via api_equipment.equipment_catalog or
   api_recovery_support.tool_form_options). window.RNEquip:
     categoryOptions(catalog, selected)  -> <optgroup>/<option> html
     category(catalog, key)              -> {value, label, unit, fields}
     identityHtml(values, opts)          -> brand / model / year / serial / condition inputs
     specFieldsHtml(catalog, key, specs) -> inputs for the category's spec fields (data-spec="key")
     readSpecs(root)                     -> JSON string of the filled spec fields
     wire(form, catalog)                 -> re-render spec fields when the category select changes
     readPhoto(file)                     -> base64 of an image file */
(function () {
  "use strict";
  function esc(v) {
    return String(v == null ? "" : v).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function category(catalog, key) {
    var hit = null;
    (catalog || []).forEach(function (g) { g.categories.forEach(function (c) { if (c.value === key) hit = c; }); });
    return hit;
  }
  function categoryOptions(catalog, selected) {
    return (catalog || []).map(function (g) {
      return '<optgroup label="' + esc(g.group) + '">' + g.categories.map(function (c) {
        return '<option value="' + esc(c.value) + '"' + (c.value === selected ? " selected" : "") + ">" + esc(c.label) + "</option>";
      }).join("") + "</optgroup>";
    }).join("");
  }
  function parseSpecs(specs) {
    if (!specs) return {};
    if (typeof specs === "object") return specs;
    try { return JSON.parse(specs) || {}; } catch (e) { return {}; }
  }
  function specFieldsHtml(catalog, key, specs) {
    var c = category(catalog, key);
    if (!c || !c.fields.length) return "";
    var v = parseSpecs(specs);
    return '<div class="form-grid rn-eq-specs">' + c.fields.map(function (f) {
      var val = v[f.key] == null ? "" : v[f.key];
      var input;
      if (f.type === "select") {
        input = '<select data-spec="' + esc(f.key) + '"><option value="">—</option>' + f.options.map(function (o) {
          return '<option' + (String(val) === o ? " selected" : "") + ">" + esc(o) + "</option>";
        }).join("") + "</select>";
      } else if (f.type === "number") {
        input = '<input data-spec="' + esc(f.key) + '" type="number" min="0" step="any" value="' + esc(val) + '">';
      } else {
        input = '<input data-spec="' + esc(f.key) + '" value="' + esc(val) + '"' + (f.placeholder ? ' placeholder="' + esc(f.placeholder) + '"' : "") + ">";
      }
      return "<label>" + esc(f.label) + (f.unit ? " (" + esc(f.unit) + ")" : "") + input + "</label>";
    }).join("") + "</div>";
  }
  function readSpecs(root) {
    var o = {};
    root.querySelectorAll("[data-spec]").forEach(function (el) {
      var v = String(el.value || "").trim();
      if (v !== "") o[el.getAttribute("data-spec")] = v;
    });
    return JSON.stringify(o);
  }
  function identityHtml(v, conditions) {
    v = v || {};
    return '<div class="form-grid">' +
      '<label>Merek<input name="brand" value="' + esc(v.brand || "") + '" placeholder="mis. Komatsu, Honda, Yamaha"></label>' +
      '<label>Model / tipe<input name="model" value="' + esc(v.model || "") + '" placeholder="mis. PC200-8"></label>' +
      '<label>Tahun pembuatan<input name="manufacture_year" type="number" min="1950" max="2100" value="' + esc(v.manufacture_year || "") + '"></label>' +
      '<label>No. seri / plat / kode aset<input name="serial_number" value="' + esc(v.serial_number || "") + '"></label>' +
      '<label>Kondisi<select name="tool_condition"><option value="">—</option>' + (conditions || []).map(function (c) {
        return '<option value="' + esc(c.value) + '"' + (v.tool_condition === c.value ? " selected" : "") + ">" + esc(c.label) + "</option>";
      }).join("") + "</select></label></div>";
  }
  function wire(form, catalog, slot, unitInput) {
    var sel = form.elements.category;
    var render = function (keep) {
      slot.innerHTML = specFieldsHtml(catalog, sel.value, keep || null);
      var c = category(catalog, sel.value);
      if (unitInput && c && (!unitInput.value || unitInput.dataset.auto === "1")) { unitInput.value = c.unit; unitInput.dataset.auto = "1"; }
    };
    sel.addEventListener("change", function () { render(); });
    if (unitInput) unitInput.addEventListener("input", function () { unitInput.dataset.auto = ""; });
    render();
    return render;
  }
  function readPhoto(file) {
    return new Promise(function (res, rej) {
      var r = new FileReader();
      r.onload = function () { res(String(r.result).split(",")[1] || ""); };
      r.onerror = function () { rej(r.error); };
      r.readAsDataURL(file);
    });
  }
  var R = "rescue_net.api_recovery_support.";
  /* several photos per tool (owner 2026-11-03: "pemilik alat untuk upload foto2 alatnya") */
  async function uploadPhotos(id, files, msg) {
    var fail = [];
    for (var i = 0; i < files.length; i++) {
      var f = files[i];
      if (f.size > 10 * 1024 * 1024) { fail.push(f.name + " (lebih dari 10 MB)"); continue; }
      if (msg) msg.textContent = "Mengunggah foto " + (i + 1) + "/" + files.length + "…";
      try {
        await window.RN_FRAPPE.call(R + "upload_tool_photo", { resource_profile: id, filename: f.name,
          content_base64: await readPhoto(f) }, { method: "POST" });
      } catch (e) { fail.push(f.name + " (" + ((e && e.message) || e) + ")"); }
    }
    return fail;
  }
  function photosHtml(photos, canDelete) {
    if (!photos || !photos.length) return '<p class="rn-muted" style="font-size:12px">Belum ada foto.</p>';
    return '<div class="rn-eq-photos">' + photos.map(function (p) {
      return '<figure><a href="' + esc(p.url) + '" target="_blank" rel="noopener"><img src="' + esc(p.url) + '" alt="" loading="lazy"></a>' +
        (canDelete ? '<button type="button" class="btn ghost mini" data-photo-del="' + esc(p.url) + '">hapus</button>' : "") + "</figure>";
    }).join("") + "</div>";
  }
  function wirePhotoDelete(root, id, after) {
    root.querySelectorAll("[data-photo-del]").forEach(function (b) {
      b.addEventListener("click", async function () {
        if (window.confirm && !window.confirm("Hapus foto ini?")) return;
        try {
          var r = await window.RN_FRAPPE.call(R + "remove_tool_photo", { resource_profile: id, file_url: b.getAttribute("data-photo-del") }, { method: "POST" });
          if (after) after(r.photos || []);
        } catch (e) { window.alert("Gagal: " + ((e && e.message) || e)); }
      });
    });
  }
  (function css() {
    var st = document.createElement("style");
    st.textContent = ".rn-eq-photos{display:grid;grid-template-columns:repeat(auto-fill,minmax(96px,1fr));gap:8px;margin:6px 0}" +
      ".rn-eq-photos figure{margin:0;display:grid;gap:4px}.rn-eq-photos img{width:100%;height:90px;object-fit:cover;border-radius:8px;display:block}";
    document.head.appendChild(st);
  })();
  window.RNEquip = { uploadPhotos: uploadPhotos, photosHtml: photosHtml, wirePhotoDelete: wirePhotoDelete, category: category, categoryOptions: categoryOptions, specFieldsHtml: specFieldsHtml,
    readSpecs: readSpecs, identityHtml: identityHtml, wire: wire, readPhoto: readPhoto, parseSpecs: parseSpecs };
})();
