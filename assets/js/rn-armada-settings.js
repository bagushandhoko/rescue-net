(function () {
  "use strict";

  // Public finder has no cargo catalogue in its response. Keep these codes
  // aligned with CARGO_TYPES in rescue_net/logistics/transport.py.
  var cargoTypes = {
    pangan: "Pangan / makanan", air: "Air minum", medis: "Obat & alat medis", pakaian: "Pakaian",
    hunian: "Tenda, terpal, selimut", kebersihan: "Kebersihan & sanitasi", bayi: "Kebutuhan bayi & anak",
    bangunan: "Bahan bangunan", alat: "Alat & perkakas", bbm: "BBM / energi", lainnya: "Lainnya"
  };

  function escapeHtml(value) {
    return String(value == null ? "" : value).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function options(labels, selected) {
    return Object.keys(labels).map(function (code) {
      return '<option value="' + escapeHtml(code) + '"' + (code === selected ? " selected" : "") +
        ">" + escapeHtml(labels[code]) + "</option>";
    }).join("");
  }

  function cargoFields(types, selected) {
    return '<div class="rn-armada-cargo"><p>Pilihan kosong berarti semua jenis diterima.</p>' +
      Object.keys(types).map(function (code) {
        return '<label><input type="checkbox" name="accepted_cargo_types" value="' + escapeHtml(code) + '"' +
          (selected.includes(code) ? " checked" : "") + '> <span>' + escapeHtml(types[code]) + "</span></label>";
      }).join("") + "</div>";
  }

  function cargoPayload(form) {
    return JSON.stringify(new FormData(form).getAll("accepted_cargo_types"));
  }

  function field(values, name, label, type, choices) {
    var value = values[name];
    var control;
    if (choices) {
      control = '<select name="' + name + '"' + (name === "transport_type" ? " required" : "") +
        ">" + options(choices, value || "") + "</select>";
    } else if (type === "textarea") {
      control = '<textarea name="' + name + '" rows="2">' + escapeHtml(value) + "</textarea>";
    } else {
      if (type === "datetime-local") value = String(value || "").replace(" ", "T");
      control = '<input name="' + name + '" type="' + (type || "text") + '" value="' + escapeHtml(value) + '"' +
        (type === "number" ? ' min="0" step="any"' : "") +
        (name === "provider_name" ? ' required maxlength="140"' : "") + ">";
    }
    return "<label>" + label + control + "</label>";
  }

  function identityFields(values) {
    return field(values, "provider_name", "Nama armada") +
      field(values, "transport_type", "Jenis transport", null,
        { "": "Pilih jenis", darat: "Darat", laut: "Laut", udara: "Udara", lainnya: "Lainnya" }) +
      field(values, "route_origin", "Asal") + field(values, "route_destination", "Tujuan");
  }

  function capacityFields(values) {
    return field(values, "capacity_weight_kg", "Kapasitas berat (kg)", "number") +
      field(values, "capacity_volume_m3", "Kapasitas volume (m³)", "number");
  }

  window.RN_ARMADA_SETTINGS = {
    cargoTypes: cargoTypes, esc: escapeHtml, options: options, cargoFields: cargoFields,
    cargoPayload: cargoPayload, field: field, identityFields: identityFields, capacityFields: capacityFields
  };
})();
