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
      var placeholder = name === "vehicle_spec" ? ' placeholder="Hino Dutro, BL 1234 AB, bak 4 x 2 m, ada terpal"' : "";
      control = '<textarea name="' + name + '" rows="2"' + placeholder + ">" + escapeHtml(value) + "</textarea>";
    } else {
      if (type === "datetime-local") value = localDate(value);
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
      field(values, "vehicle_spec", "Spesifikasi alat", "textarea") +
      field(values, "route_origin", "Asal") + field(values, "route_destination", "Tujuan");
  }

  function capacityFields(values) {
    return field(values, "capacity_weight_kg", "Kapasitas berat (kg)", "number") +
      field(values, "capacity_volume_m3", "Kapasitas volume (m³)", "number");
  }

  function localDate(value) { return String(value || "").replace(" ", "T").slice(0, 16); }

  // owner 2026-11-12: centang "bisa mengangkut relawan/orang" + jumlah orang + arah perjalanan (ke lokasi / pulang / PP)
  var TRIP_OPTS = [["ke_lokasi", "Berangkat ke lokasi bencana"], ["pulang", "Pulang dari lokasi bencana"], ["pergi_pulang", "Pergi & pulang"]];
  function heavyFields(a) {
    a = a || {};
    var on = !!a.carries_heavy_equipment, trip = a.heavy_trip || "mob";
    return '<fieldset class="rn-pd-heavy" style="grid-column:1/-1;border:1px solid rgba(104,64,45,.2);border-radius:10px;padding:8px 12px">' +
      '<label style="display:flex;gap:8px;align-items:center;font-weight:600"><input type="checkbox" data-heavy style="width:20px;height:20px"' + (on ? " checked" : "") + '> Bisa mengangkut alat berat</label>' +
      '<div class="rn-ps-arm-grid" data-heavy-isi' + (on ? "" : " hidden") + '>' +
      '<label>Muatan alat berat maks (ton)<input type="number" min="0.001" step="any" name="heavy_max_ton" value="' + escapeHtml(on ? a.heavy_max_ton : "") + '"' + (on ? ' required' : ' disabled') + '></label>' +
      '<label>Jenis bak/dek<select name="heavy_deck_type">' + options(Object.fromEntries([["", "Pilih jenis"], ["lowbed", "Lowbed"], ["selfloader", "Selfloader"], ["flatbed", "Flatbed"], ["tongkang", "Tongkang"], ["lainnya", "Lainnya"]]), a.heavy_deck_type || "") + '</select></label>' +
      '<label>Arah perjalanan<select name="heavy_trip">' + options(Object.fromEntries([["mob", "Mob — ke lokasi"], ["demob", "Demob — pulang"], ["mob_demob", "Mob & demob"]]), trip) + '</select></label>' +
      '<label data-demob-at' + (trip === "mob" ? " hidden" : "") + '>Jadwal demob<input type="datetime-local" name="heavy_demob_at" value="' + escapeHtml(localDate(a.heavy_demob_at || "")) + '"></label>' +
      '</div></fieldset>';
  }
  function heavyPayload(form) {
    var on = !!(form.querySelector("[data-heavy]") || {}).checked;
    var trip = on && form.heavy_trip ? form.heavy_trip.value : "";
    return {
      carries_heavy_equipment: on ? 1 : 0,
      heavy_max_ton: on ? Number(form.heavy_max_ton.value || 0) : 0,
      heavy_deck_type: on ? form.heavy_deck_type.value : "",
      heavy_trip: trip,
      heavy_demob_at: on && trip !== "mob" && form.heavy_demob_at.value ? form.heavy_demob_at.value.replace("T", " ") : "",
    };
  }
  document.addEventListener("change", function (e) {
    var box = e.target.closest && e.target.closest(".rn-pd-heavy"); if (!box) return;
    var on = box.querySelector("[data-heavy]").checked;
    box.querySelector("[data-heavy-isi]").hidden = !on;
    var ton = box.querySelector('[name="heavy_max_ton"]');
    ton.required = on; ton.disabled = !on;
    box.querySelector("[data-demob-at]").hidden = box.querySelector('[name="heavy_trip"]').value === "mob";
  });

  function peopleFields(a) {
    a = a || {};
    var on = Number(a.volunteer_capacity_seats || 0) > 0, trip = a.people_trip || "ke_lokasi";
    return '<fieldset class="rn-pd-orang" style="grid-column:1/-1;border:1px solid rgba(104,64,45,.2);border-radius:10px;padding:8px 12px">' +
      '<label style="display:flex;gap:8px;align-items:center;font-weight:600"><input type="checkbox" data-angkut style="width:20px;height:20px"' + (on ? " checked" : "") +
      "> Bisa mengangkut relawan / orang</label>" +
      '<div class="rn-ps-arm-grid" data-angkut-isi' + (on ? "" : " hidden") + ">" +
      '<label>Jumlah orang<input type="number" min="1" name="volunteer_capacity_seats" value="' + escapeHtml(on ? a.volunteer_capacity_seats : "") + '" placeholder="mis. 10"></label>' +
      '<label>Untuk perjalanan<select name="people_trip">' + TRIP_OPTS.map(function (o) {
        return '<option value="' + o[0] + '"' + (o[0] === trip ? " selected" : "") + ">" + o[1] + "</option>"; }).join("") + "</select></label>" +
      '<label>Titik jemput<input name="volunteer_pickup_location" value="' + escapeHtml(a.volunteer_pickup_location || "") + '" placeholder="mis. Halaman posko"></label>' +
      "</div></fieldset>";
  }
  function peoplePayload(form) {
    var on = !!(form.querySelector("[data-angkut]") || {}).checked;
    var n = on ? Number((form.volunteer_capacity_seats && form.volunteer_capacity_seats.value) || 0) : 0;
    var trip = on && form.people_trip ? form.people_trip.value : "";
    return {
      volunteer_capacity_seats: n,
      volunteer_pickup_location: on && form.volunteer_pickup_location ? form.volunteer_pickup_location.value.trim() : "",
      people_trip: n > 0 ? trip : "",
    };
  }
  document.addEventListener("change", function (e) {
    var box = e.target.closest && e.target.closest(".rn-pd-orang"); if (!box) return;
    var on = box.querySelector("[data-angkut]").checked, isi = box.querySelector("[data-angkut-isi]");
    isi.hidden = !on;
    var n = box.querySelector('[name="volunteer_capacity_seats"]'); if (on && n && !n.value) n.value = 1;
  });

  function mountServedPickers(evEl, pkEl, events, poskos) {
    if (!evEl || !pkEl || !window.RNEventChecklist) return null;
    var pk = window.RNEventChecklist.mountPoskos(pkEl, { selected: poskos || [] });
    var ev = window.RNEventChecklist.mount(evEl, {
      selected: events, multiple: true,
      onChange: function (sel) { pk.setEvents(sel); },
    });
    ev.ready.then(function () { pk.setEvents(ev.getSelected()); });
    return { ev: ev, pk: pk };
  }

  function quantity(value, unit) {
    return value == null ? "belum diatur" : Number(value).toLocaleString("id-ID", { maximumFractionDigits: 6 }) + " " + unit;
  }

  function armadaTotals(a) {
    return '<p class="rn-ps-arm-totals"><strong>Sisa tersedia</strong> ' +
      quantity(a.left_kg, "kg") + " / " + quantity(a.settings.left_m3, "m³") +
      '<br><strong>Sudah dipesan</strong> ' + quantity(a.settings.committed_kg, "kg") + " / " +
      quantity(a.settings.committed_m3, "m³") + "</p>";
  }

  function bookingCount(a) {
    return (a.booking_counts.requested || 0) + " menunggu · " + (a.booking_counts.confirmed || 0) + " disetujui";
  }

  var bookingLabels = {
    requested: "Menunggu persetujuan", confirmed: "Disetujui", rejected: "Ditolak",
    cancelled: "Batal", completed: "Selesai"
  };
  var bookerTypes = { individu: "Individu", relawan: "Relawan", organization: "Organisasi", posko: "Posko" };

  function bookingRow(b) {
    var phone = String(b.contact_phone || "").trim();
    var digits = phone.replace(/\D/g, "");
    var wa = digits.replace(/^0062/, "62").replace(/^0/, "62");
    if (wa.startsWith("8")) wa = "62" + wa;
    var phoneLink = digits ? '<a href="tel:' + (phone.startsWith("+") ? "+" : "") + digits + '">' +
      escapeHtml(phone) + '</a>' : escapeHtml(phone);
    if (/^62[1-9][0-9]{6,12}$/.test(wa)) {
      phoneLink += ' · <a href="https://wa.me/' + wa + '" target="_blank" rel="noopener noreferrer">WhatsApp</a>';
    }
    var fields = [
      ["Muatan", b.cargo_desc],
      ["Jumlah", [b.qty_weight_kg == null ? "" : quantity(b.qty_weight_kg, "kg"),
        b.qty_volume_m3 == null ? "" : quantity(b.qty_volume_m3, "m³")].filter(Boolean).join(" · ")],
      ["Jadwal diminta", b.requested_window], ["Jemput", b.pickup_location], ["Antar", b.dropoff_location],
      ["Catatan", b.notes], ["Waktu pemesanan", b.requested_at || b.creation],
      ["Waktu persetujuan", b.confirmed_at], ["Alasan penolakan", b.reject_reason]
    ];
    return '<article class="rn-ps-booking"><strong>' + escapeHtml(b.booker_name || "Pemesan") + '</strong>' +
      (b.booked_by_type ? " · " + escapeHtml(bookerTypes[b.booked_by_type] || b.booked_by_type) : "") +
      ' <span class="rn-ps-booking-state">' + escapeHtml(bookingLabels[b.status] || b.status) + '</span>' +
      ((b.contact_person || phone) ? '<p>Narahubung · ' + [escapeHtml(b.contact_person), phoneLink].filter(Boolean).join(" · ") + '</p>' : "") +
      '<dl>' + fields.filter(function (item) { return item[1]; }).map(function (item) {
        return '<dt>' + item[0] + '</dt><dd>' + escapeHtml(item[1]) + '</dd>';
      }).join("") + '</dl>' +
      (b.status === "requested" ? '<div class="rn-ps-arm-actions">' +
        '<button type="button" class="rn-ps-save" data-booking-action="confirm" data-booking="' + escapeHtml(b.name) +
        '" data-needs-pin="' + (b.needs_pin ? "1" : "0") + '">Setujui</button>' +
        '<button type="button" class="rn-ps-secondary" data-booking-action="reject" data-booking="' + escapeHtml(b.name) + '">Tolak</button></div>' : "") +
      '</article>';
  }

  function bookingList(a) {
    var bookings = a.bookings || [];
    if (!bookings.length) return '<p>Belum ada pemesanan.</p>';
    return ["requested", "confirmed", "other"].map(function (status) {
      var rows = bookings.filter(function (b) {
        return status === "other" ? b.status !== "requested" && b.status !== "confirmed" : b.status === status;
      });
      return '<h4>' + (bookingLabels[status] || "Lainnya") + '</h4>' +
        (rows.length ? rows.map(bookingRow).join("") : '<p>Tidak ada pesanan.</p>');
    }).join("");
  }

  function armadaForm(a, types, statuses) {
    var settings = a ? a.settings : { service_mode: "both", accepted_cargo_types: [] };
    function input(name, label, type, choices) { return field(settings, name, label, type, choices); }
    function group(title, fields, extra) {
      return '<fieldset><legend>' + title + '</legend>' + (extra || "") +
        '<div class="rn-ps-arm-grid">' + fields + '</div></fieldset>';
    }
    return '<details class="rn-ps-arm"><summary>' + escapeHtml(a ? a.title : "+ Tambah armada") +
      (a ? ' <small data-booking-count>' + escapeHtml(bookingCount(a)) + '</small>' : "") + '</summary>' +
      '<form data-arm-settings="' + escapeHtml(a ? a.name : "") + '">' +
      group("Identitas", identityFields(settings)) +
      group("Ukuran ruang muat", capacityFields(settings) +
        input("own_load_kg", "Muatan sendiri (kg)", "number") +
        input("own_load_m3", "Muatan sendiri (m³)", "number") +
        input("own_cargo_desc", "Keterangan muatan sendiri", "textarea"), a ? '<div data-arm-totals>' + armadaTotals(a) + "</div>" : "") +
      group("Jenis barang yang diterima",
        input("prohibited_items", "Barang dilarang", "textarea") +
        input("cargo_requirements", "Syarat barang", "textarea") +
        input("packing_required", "Packing", null, { "": "Tidak diatur", tidak: "Tidak wajib", dianjurkan: "Dianjurkan", wajib: "Wajib" }) +
        input("packing_spec", "Spesifikasi packing") +
        input("max_piece_weight_kg", "Berat maksimum per koli (kg)", "number") +
        input("documents_required", "Dokumen yang diperlukan"),
        cargoFields(types, settings.accepted_cargo_types)) +
      group("Jadwal", input("departure_at", "Berangkat", "datetime-local") +
        input("eta_at", "Perkiraan tiba", "datetime-local") +
        input("cargo_cutoff_at", "Batas serah barang", "datetime-local") +
        input("return_departure_at", "Jadwal balik", "datetime-local")) +
      group("Serah terima", input("current_location", "Lokasi sekarang") +
        input("handover_location", "Titik serah terima") +
        input("handover_contact_person", "Narahubung") +
        input("handover_contact_phone", "Nomor HP", "tel") +
        input("coordination_notes", "Catatan koordinasi", "textarea")) +
      group("Layanan", input("service_mode", "Mode layanan", null, {
        "": "Pilih mode", space_only: "Hanya ruang muat", courier_pickup: "Jemput-antar", both: "Keduanya"
      }) + input("booking_policy", "Kebijakan booking", null, { pin_verify: "Konfirmasi PIN", open: "Terbuka" })) +
      (a ? group("Status", field({ transport_status: a.status }, "transport_status", "Status armada", null, statuses)) : "") +
      peopleFields(settings) + heavyFields(settings) +
      '<fieldset><legend>Bencana yang dilayani</legend><div data-arm-events></div></fieldset>' +
      '<fieldset><legend>Posko logistik yang dilayani (kosong = semua)</legend><div data-arm-poskos></div></fieldset>' +
      '<div class="rn-ps-arm-actions"><button class="rn-ps-save" type="submit">Simpan</button>' +
      '<span data-settings-message role="status"></span></div></form>' +
      (a ? '<section class="rn-ps-bookings"><h3>Pemesan / Booking</h3>' +
        '<p data-booking-message role="status"></p><div data-booking-list>' + bookingList(a) + '</div></section>' : "") +
      '</details>';
  }

  function mount(host, posko, event, wanted, add, onSaved) {
    function list() {
      return window.RN_FRAPPE.call("rescue_net.api_posko_manage.armada_list", { posko: posko });
    }

    function row(armada, data) {
      var template = document.createElement("template");
      template.innerHTML = armadaForm(armada, data.cargo_types, data.statuses);
      var detail = template.content.firstElementChild;
      var form = detail.querySelector("form");
      var served;
      detail.addEventListener("toggle", function () {
        if (!detail.open || served) return;
        var settings = armada && armada.settings;
        served = mountServedPickers(form.querySelector("[data-arm-events]"), form.querySelector("[data-arm-poskos]"),
          settings ? settings.served_events : (event ? [event] : []), settings ? settings.served_poskos : []);
      });
      var bookings = detail.querySelector(".rn-ps-bookings");
      if (bookings) bookings.addEventListener("click", async function (e) {
        var action = e.target.closest("[data-booking-action]");
        if (!action || action.disabled) return;
        var confirm = action.dataset.bookingAction === "confirm";
        var payload = { booking: action.dataset.booking };
        if (confirm && action.dataset.needsPin === "1") {
          payload.pin = window.prompt("Masukkan PIN dari pemesan:", "");
          if (payload.pin === null) return;
          if (!payload.pin.trim()) {
            bookings.querySelector("[data-booking-message]").textContent = "Isi PIN dari pemesan.";
            return;
          }
        }
        if (!confirm) {
          payload.reason = window.prompt("Alasan menolak (opsional):", "");
          if (payload.reason === null) return;
        }
        var msg = bookings.querySelector("[data-booking-message]");
        var buttons = bookings.querySelectorAll("[data-booking-action]");
        buttons.forEach(function (button) { button.disabled = true; });
        msg.textContent = "Memproses pesanan…";
        try {
          await window.RN_FRAPPE.call("rescue_net.api_logistics." +
            (confirm ? "confirm_transport_booking" : "reject_transport_booking"), payload, { method: "POST" });
        } catch (err) {
          msg.textContent = "Gagal. " + String((err && err.message) || err).replace(/^frappe\.exceptions\.\w+:\s*/, "");
          buttons.forEach(function (button) { button.disabled = false; });
          return;
        }
        msg.textContent = confirm ? "Pesanan disetujui." : "Pesanan ditolak.";
        onSaved();
        try {
          var latest = await list();
          var byId = new Map(latest.armada.map(function (item) { return [item.name, item]; }));
          host.querySelectorAll("form[data-arm-settings]").forEach(function (current) {
            var updated = byId.get(current.dataset.armSettings);
            if (!updated) return;
            var row = current.closest("details");
            row.querySelector("[data-booking-count]").textContent = bookingCount(updated);
            row.querySelector("[data-arm-totals]").innerHTML = armadaTotals(updated);
            row.querySelector("[data-booking-list]").innerHTML = bookingList(updated);
          });
          msg.tabIndex = -1;
          msg.focus();
        } catch (err) {
          msg.textContent += " Gagal memuat ulang daftar. " + ((err && err.message) || err);
        }
      });
      form.addEventListener("submit", async function (e) {
        e.preventDefault();
        var button = form.querySelector('button[type="submit"]');
        var msg = form.querySelector("[data-settings-message]");
        var events = served ? served.ev.getSelected() : [];
        if (!events.length) {
          msg.textContent = "Pilih minimal satu bencana yang dilayani armada.";
          return;
        }
        var payload = Object.fromEntries(new FormData(form));
        form.querySelectorAll(".rn-evc input[name]").forEach(function (input) { delete payload[input.name]; });
        payload.accepted_cargo_types = cargoPayload(form);
        payload.served_events = JSON.stringify(events);
        payload.served_poskos = JSON.stringify(served.pk.getSelected());
        form.querySelectorAll('input[type="datetime-local"]').forEach(function (input) {
          payload[input.name] = input.value.replace("T", " ");
        });
        Object.assign(payload, peoplePayload(form), heavyPayload(form));
        ["own_load_kg", "own_load_m3"].forEach(function (key) { payload[key] = payload[key] || "0"; });
        if (armada) {
          payload.transport_space = armada.name;
          if (!payload.service_mode) delete payload.service_mode;
        } else {
          payload.coordination_posko = posko;
          payload.disaster_event = events[0];
        }
        button.disabled = true;
        msg.textContent = "Menyimpan…";
        var saved;
        try {
          saved = await window.RN_FRAPPE.call("rescue_net.api_logistics." +
            (armada ? "update_transport_space" : "create_transport_space"), payload,
            { method: "POST", keepEmpty: armada ? Object.keys(payload) : [] });
        } catch (err) {
          msg.textContent = "Gagal menyimpan. " + String((err && err.message) || err).replace(/^frappe\.exceptions\.\w+:\s*/, "");
          button.disabled = false;
          return;
        }
        onSaved();
        msg.textContent = "Pengaturan armada tersimpan.";
        try {
          var latest = await list();
          var updated = latest.armada.find(function (item) { return item.name === saved.transport; });
          if (!updated) throw new Error("Armada belum muncul dalam daftar.");
          if (!detail.isConnected) return;
          var replacement = row(updated, latest);
          replacement.open = true;
          if (armada) {
            detail.replaceWith(replacement);
          } else {
            detail.before(replacement);
            detail.replaceWith(row(null, latest));
          }
          var status = replacement.querySelector("[data-settings-message]");
          status.textContent = msg.textContent;
          status.tabIndex = -1;
          status.focus();
        } catch (err) {
          msg.textContent += " Gagal memuat ulang data. " + ((err && err.message) || err);
          if (!armada) return; // prevent duplicating a creation that already succeeded
        }
        button.disabled = false;
      });
      return detail;
    }

    host.textContent = "Memuat armada…";
    list().then(function (data) {
      host.textContent = "";
      var found = false;
      data.armada.forEach(function (armada) {
        var detail = row(armada, data);
        if (armada.name === wanted) { detail.open = true; found = true; }
        host.appendChild(detail);
      });
      if (wanted && !found) host.prepend(document.createTextNode("Armada pilihan tidak ditemukan di posko ini."));
      if (!wanted && !data.armada.length) host.textContent = "Posko ini belum punya armada.";
      var create = row(null, data);
      host.appendChild(create);
      create.open = Boolean(add);
    }).catch(function (err) {
      host.textContent = "Gagal memuat armada. " + ((err && err.message) || err);
    });
  }

  window.RN_ARMADA_SETTINGS = {
    mount: mount,
    cargoTypes: cargoTypes, esc: escapeHtml, options: options
  };
})();
