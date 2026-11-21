/* Optional aid files: held in the form until the aid and private files save together. */
function setupAidAttachments(form) {
  const box = form.querySelector('[data-aid-attachments]');
  if (!box) return;
  const list = box.querySelector('[data-attachment-list]');
  const msg = box.querySelector('[data-attachment-message]');
  const files = [];
  const mb = 1024 * 1024;
  function render() {
    list.replaceChildren();
    files.forEach((file, i) => {
      const row = document.createElement('li');
      row.style.cssText = 'display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:8px 0';
      const name = document.createElement('span');
      name.style.cssText = 'overflow-wrap:anywhere;flex:1;min-width:0';
      name.textContent = file.name + ' (' + (file.size / mb).toFixed(1) + ' MB)';
      const remove = document.createElement('button');
      remove.type = 'button'; remove.className = 'btn mini'; remove.textContent = 'Hapus';
      remove.setAttribute('aria-label', 'Hapus lampiran ' + file.name);
      remove.onclick = () => { files.splice(i, 1); render(); msg.textContent = ''; };
      row.append(name, remove); list.appendChild(row);
    });
  }
  function addFiles(selected) {
    msg.textContent = '';
    const before = files.length;
    for (const file of Array.from(selected || [])) {
      if (files.length >= 3) { msg.textContent = 'Maksimal 3 lampiran. Hapus salah satu untuk mengganti.'; break; }
      const image = /^image\//.test(file.type);
      const pdf = /\.pdf$/i.test(file.name) && (!file.type || file.type === 'application/pdf');
      if (!image && !pdf) { msg.textContent = 'Pilih gambar atau dokumen PDF.'; continue; }
      if (!file.size || file.size > (image ? 20 : 2) * mb) {
        msg.textContent = image ? 'Foto sumber maksimal 20 MB; foto akan diperkecil sebelum dikirim.' : 'PDF maksimal 2 MB.';
        continue;
      }
      files.push(file);
    }
    render();
    return files.length - before;
  }
  const picker = box.querySelector('[data-attachment-picker]');
  picker.addEventListener('change', () => { addFiles(picker.files); picker.value = ''; });
  box.querySelector('[data-pick-attachment]').onclick = () => picker.click();

  const cameraDialog = box.querySelector('[data-camera-dialog]');
  const cameraVideo = box.querySelector('[data-camera-video]');
  const cameraStatus = box.querySelector('[data-camera-status]');
  const captureButton = box.querySelector('[data-camera-capture]');
  let cameraStream = null;
  function stopCamera() {
    if (cameraStream) cameraStream.getTracks().forEach(track => track.stop());
    cameraStream = null;
    cameraVideo.srcObject = null;
    captureButton.disabled = true;
  }
  cameraDialog.addEventListener('close', stopCamera);
  box.querySelector('[data-camera-close]').addEventListener('click', () => cameraDialog.close());
  box.querySelector('[data-camera-cancel]').addEventListener('click', () => cameraDialog.close());
  box.querySelector('[data-take-photo]').addEventListener('click', async () => {
    if (typeof cameraDialog.showModal !== 'function') {
      msg.textContent = 'Browser belum mendukung kamera langsung. Pilih foto dari perangkat.';
      return;
    }
    cameraDialog.showModal();
    cameraStatus.textContent = 'Meminta izin kamera...';
    if (!window.isSecureContext || !navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      cameraStatus.textContent = 'Kamera memerlukan halaman HTTPS dan browser yang mendukung kamera. Pilih foto dari perangkat bila kamera tidak tersedia.';
      return;
    }
    try {
      try {
        cameraStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: 'environment' } }, audio: false });
      } catch (firstError) {
        if (firstError && firstError.name === 'OverconstrainedError') {
          cameraStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
        } else {
          throw firstError;
        }
      }
      if (!cameraDialog.open) { stopCamera(); return; }
      cameraVideo.srcObject = cameraStream;
      await cameraVideo.play();
      cameraStatus.textContent = 'Kamera aktif. Pastikan objek terlihat, lalu tekan Gunakan foto.';
      captureButton.disabled = false;
    } catch (error) {
      const messages = {
        NotAllowedError: 'Izin kamera ditolak. Izinkan kamera untuk situs ini di pengaturan browser, lalu coba lagi.',
        NotFoundError: 'Kamera tidak ditemukan pada perangkat ini.',
        NotReadableError: 'Kamera sedang dipakai aplikasi lain. Tutup aplikasi itu lalu coba lagi.',
      };
      cameraStatus.textContent = messages[error && error.name] || 'Kamera tidak bisa dibuka. Periksa izin browser atau pilih foto dari perangkat.';
      stopCamera();
    }
  });
  captureButton.addEventListener('click', async () => {
    const width = cameraVideo.videoWidth, height = cameraVideo.videoHeight;
    if (!width || !height) { cameraStatus.textContent = 'Kamera belum siap. Tunggu sebentar lalu coba lagi.'; return; }
    captureButton.disabled = true;
    cameraStatus.textContent = 'Menyiapkan foto...';
    const scale = Math.min(1, 1600 / Math.max(width, height));
    const canvas = document.createElement('canvas');
    canvas.width = Math.max(1, Math.round(width * scale));
    canvas.height = Math.max(1, Math.round(height * scale));
    canvas.getContext('2d').drawImage(cameraVideo, 0, 0, canvas.width, canvas.height);
    const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/jpeg', .88));
    if (!blob) {
      cameraStatus.textContent = 'Foto gagal dibuat. Coba lagi atau pilih foto dari perangkat.';
      captureButton.disabled = false;
      return;
    }
    const added = addFiles([new File([blob], 'foto-bantuan-' + Date.now() + '.jpg', { type: 'image/jpeg' })]);
    cameraDialog.close();
    if (added) msg.textContent = 'Foto berhasil ditambahkan.';
  });
  window.addEventListener('pagehide', stopCamera, { once: true });
  function read(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result).split(',')[1]);
      reader.onerror = () => reject(new Error('Lampiran tidak bisa dibaca. Pilih berkas kembali.'));
      reader.readAsDataURL(file);
    });
  }
  async function payload(file) {
    if (!/^image\//.test(file.type)) return { filename: file.name.length > 140 ? file.name.slice(0, 136) + '.pdf' : file.name, content_base64: await read(file) };
    // Camera files may be very large. Resize and remove EXIF/GPS before upload.
    const image = new Image(), url = URL.createObjectURL(file);
    try {
      await new Promise((resolve, reject) => { image.onload = resolve; image.onerror = () => reject(new Error('Foto tidak bisa dibuka. Gunakan JPG, PNG, atau WebP.')); image.src = url; });
      const scale = Math.min(1, 1600 / Math.max(image.width, image.height));
      const canvas = document.createElement('canvas');
      canvas.width = Math.max(1, Math.round(image.width * scale)); canvas.height = Math.max(1, Math.round(image.height * scale));
      const ctx = canvas.getContext('2d');
      ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, canvas.width, canvas.height); ctx.drawImage(image, 0, 0, canvas.width, canvas.height);
      const encoded = canvas.toDataURL('image/jpeg', .85).split(',')[1];
      if (encoded.length > Math.ceil(2 * mb / 3) * 4) throw new Error('Foto masih melebihi 2 MB. Pilih foto yang lebih kecil.');
      return { filename: file.name.replace(/\.[^.]*$/, '').slice(0, 120) + '.jpg', content_base64: encoded };
    } finally { URL.revokeObjectURL(url); }
  }
  form.__readAidAttachments = async () => {
    const rows = await Promise.all(files.map(payload));
    // The deployed proxy accepts 10 MiB requests. Reserve room for aid fields
    // and count percent-encoding overhead, not merely the decoded file bytes.
    if (new URLSearchParams({ attachments_json: JSON.stringify(rows) }).toString().length > 9 * mb) {
      throw new Error('Total lampiran terlalu besar untuk dikirim. Hapus satu lampiran atau pilih berkas yang lebih kecil.');
    }
    return rows;
  };
  form.__resetAidAttachments = () => { files.length = 0; msg.textContent = ''; render(); };
}

function addGuestAttachmentButtons(container, rows, creds) {
  if (!rows || !rows.length) return;
  const box = document.createElement('div');
  box.className = 'panel'; box.style.marginTop = '10px';
  const title = document.createElement('p'); title.textContent = 'Lampiran privat pengiriman ini'; box.appendChild(title);
  rows.forEach(row => {
    const button = document.createElement('button'); button.type = 'button'; button.className = 'btn mini';
    button.style.cssText = 'margin:4px;max-width:100%;white-space:normal;overflow-wrap:anywhere'; button.textContent = row.file_name;
    button.onclick = async () => {
      button.disabled = true;
      try {
        const data = await RN_FRAPPE.call('rescue_net.api_logistics.guest_aid_attachment', { ...creds, attachment: row.name }, { method: 'POST' });
        const bytes = Uint8Array.from(atob(data.content_base64), c => c.charCodeAt(0));
        const url = URL.createObjectURL(new Blob([bytes], { type: 'application/octet-stream' }));
        const link = document.createElement('a'); link.href = url; link.download = data.file_name; document.body.appendChild(link); link.click(); link.remove();
        setTimeout(() => URL.revokeObjectURL(url), 30000);
      } catch (err) { alert(err.message || 'Lampiran tidak bisa dibuka.'); }
      finally { button.disabled = false; }
    };
    box.appendChild(button);
  });
  container.appendChild(box);
}

function safe(v) {
  return (
    v === null ||
    v === undefined ||
    v === ""
  )
    ? "n/a"
    : v;
}


function mapDeliveryMode(value) {
  if (
    value === "self_deliver_to_posko"
  ) {
    return "active_booking";
  }

  return "need_pickup";
}


function setupDeliveryModeToggle(form) {
  if (!form) return;

  const deliveryMode =
    form.querySelector(
      '[name="delivery_mode"]'
    );

  const selfDeliverBox =
    document.querySelector(
      "[data-self-deliver-fields]"
    );

  function update() {
    if (
      !selfDeliverBox ||
      !deliveryMode
    ) {
      return;
    }

    selfDeliverBox.style.display =
      deliveryMode.value ===
      "self_deliver_to_posko"
        ? "grid"
        : "none";
  }

  if (deliveryMode) {
    deliveryMode.addEventListener(
      "change",
      update
    );

    update();
  }
}


function renderCreateSuccess(
  result,
  data
) {
  const offers = data.aid_offers || (data.aid_offer ? [{ aid_offer: data.aid_offer, offer_status: data.offer_status }] : []);
  const rows = offers.map(o => `
        <div>
          <span>${safe(o.item || "Aid Offer")}${o.quantity ? " — " + safe(o.quantity) + " " + safe(o.unit || "") : ""}${o.ready_at ? " · siap: " + safe(o.ready_at) : ""}</span>
          <strong>${safe(o.aid_offer)} · ${safe(o.offer_status)}</strong>
        </div>`).join("");
  const firstId = offers.length ? safe(offers[0].aid_offer) : "";
  const editCode = safe(data.edit_code || "");
  result.innerHTML = `
    <div class="success-box">
      <h3>Bantuan berhasil dicatat${offers.length > 1 ? " (" + offers.length + " item)" : ""}</h3>

      <p>Tiap item menjadi satu Aid Offer yang bisa dipantau di Manajemen Distribusi &amp; Posko Logistik.</p>

      ${editCode ? `
      <div class="alert warning" style="margin:10px 0">
        <b>Simpan sekarang — Kode Edit hanya ditampilkan sekali:</b>
        <div class="code-grid" style="margin-top:8px">
          <div><span>Aid ID</span><strong>${firstId}</strong></div>
          <div><span>Kode Edit</span><strong style="letter-spacing:2px">${editCode}</strong></div>
          <div><span>HP terdaftar</span><strong>${safe(data.donor_name)}</strong></div>
        </div>
        <p class="subtitle" style="margin-top:6px">Edit / batalkan bantuan nanti pakai <b>Aid ID + Kode Edit + nomor HP</b> yang sama. Tanpa akun.</p>
      </div>` : ""}

      <div class="code-grid">
        ${rows}
        <div>
          <span>Handling</span>
          <strong>${safe(data.handling_mode)}</strong>
        </div>
        <div>
          <span>Target Posko</span>
          <strong>${safe(data.target_posko) || "—"}</strong>
        </div>
      </div>

      <a class="btn primary" href="edit-bantuan.html?aid=${encodeURIComponent(firstId)}">Edit / Batalkan Bantuan</a>
    </div>
  `;
}


/* ---------- repeatable item rows ---------- */
function initAidItems(form) {
  const wrap = form.querySelector("[data-aid-items]");
  if (!wrap) return;
  const rowsEl = wrap.querySelector("[data-aid-rows]");
  const tpl = wrap.querySelector("[data-aid-row-tpl]");

  function addRow(preset) {
    const node = tpl.content.firstElementChild.cloneNode(true);
    if (preset) {
      ["item_name", "quantity", "unit", "ready_at"].forEach(k => {
        const i = node.querySelector('[data-f="' + k + '"]');
        if (i && preset[k] != null) i.value = preset[k];
      });
    }
    node.querySelector("[data-del-item]").addEventListener("click", () => {
      if (rowsEl.querySelectorAll(".rn-aid-row").length > 1) node.remove();
      else clearRow(node);
      syncDelState();
    });
    rowsEl.appendChild(node);
    syncDelState();
    return node;
  }
  function clearRow(node) {
    node.querySelectorAll("input").forEach(i => { i.value = ""; });
  }
  function syncDelState() {
    const only = rowsEl.querySelectorAll(".rn-aid-row").length <= 1;
    rowsEl.querySelectorAll("[data-del-item]").forEach(b => { b.disabled = only; });
  }

  wrap.querySelector("[data-add-item]").addEventListener("click", () => addRow());
  if (!rowsEl.querySelector(".rn-aid-row")) addRow();

  form.__collectAidItems = function () {
    const out = [];
    rowsEl.querySelectorAll(".rn-aid-row").forEach(r => {
      const g = k => (r.querySelector('[data-f="' + k + '"]').value || "").trim();
      const item = g("item_name");
      if (!item) return;
      out.push({
        item_text: item,
        quantity: g("quantity") ? Number(g("quantity")) : null,
        unit: g("unit") || null,
        ready_at: g("ready_at") || null,
      });
    });
    return out;
  };
  form.__resetAidItems = function () {
    rowsEl.innerHTML = "";
    addRow();
  };
}


/* ---------- Lokasi pickup: GPS sekarang / pilih di peta ---------- */
function setupAidLocationPicker(form) {
  const latEl = document.getElementById("kbLat");
  const lngEl = document.getElementById("kbLng");
  const nowBtn = document.getElementById("kbGeoNow");
  const mapBtn = document.getElementById("kbGeoMap");
  const mapWrap = document.getElementById("kbMapWrap");
  const msgEl = document.getElementById("kbGeoMsg");
  if (!latEl || !lngEl || !nowBtn || !mapBtn) return;

  const GEO = { map: null, marker: null };

  function msg(t) { if (msgEl) msgEl.textContent = t ? " " + t : ""; }

  function setLatLng(lat, lng) {
    latEl.value = Number(lat).toFixed(6);
    lngEl.value = Number(lng).toFixed(6);
    if (GEO.marker) GEO.marker.setLatLng([lat, lng]);
  }

  nowBtn.addEventListener("click", () => {
    if (!navigator.geolocation) {
      msg("Peramban tidak mendukung geolokasi. Isi lokasi manual di kolom teks.");
      return;
    }
    msg("Mengambil lokasi…");
    navigator.geolocation.getCurrentPosition(
      pos => {
        setLatLng(pos.coords.latitude, pos.coords.longitude);
        msg("Lokasi terisi (±" + Math.round(pos.coords.accuracy || 0) + " m).");
        if (GEO.map) GEO.map.setView([pos.coords.latitude, pos.coords.longitude], 16);
      },
      err => {
        msg("Gagal: " + ((err && err.message) || "izin lokasi ditolak") + ". Pakai peta atau isi alamat manual.");
      },
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
    );
  });

  function initMap() {
    if (GEO.map || typeof L === "undefined") return;
    const lat = Number(latEl.value), lng = Number(lngEl.value);
    const start = (latEl.value && lngEl.value && isFinite(lat) && isFinite(lng)) ? [lat, lng] : [-2.5, 118.0];
    const zoom = (latEl.value && lngEl.value) ? 16 : 4;
    GEO.map = L.map("kbMap").setView(start, zoom);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
      { maxZoom: 19, attribution: "© OpenStreetMap" }).addTo(GEO.map);
    const icon = L.divIcon({
      className: "rn-geo-pin",
      html: '<span style="display:block;width:16px;height:16px;border-radius:50% 50% 50% 0;background:#c0392b;border:2px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,.4);transform:rotate(-45deg)"></span>',
      iconSize: [16, 16], iconAnchor: [8, 16],
    });
    GEO.marker = L.marker(start, { draggable: true, icon }).addTo(GEO.map);
    GEO.marker.on("dragend", () => {
      const p = GEO.marker.getLatLng();
      setLatLng(p.lat, p.lng);
      msg("Titik diperbarui dari peta.");
    });
    GEO.map.on("click", e => {
      setLatLng(e.latlng.lat, e.latlng.lng);
      msg("Titik dipilih dari peta.");
    });
  }

  mapBtn.addEventListener("click", () => {
    if (typeof L === "undefined") { msg("Peta tidak tersedia — pakai lokasi saat ini atau isi alamat manual."); return; }
    if (!mapWrap) return;
    mapWrap.hidden = !mapWrap.hidden;
    if (!mapWrap.hidden) {
      initMap();
      setTimeout(() => {
        if (GEO.map) GEO.map.invalidateSize();
      }, 60);
    }
  });

  form.__resetAidLocation = function () {
    latEl.value = "";
    lngEl.value = "";
    msg("");
  };
}


async function populateDisasterPicker(form) {
  const sel = form.querySelector("[data-disaster-picker]");
  if (!sel || !window.RN_FRAPPE) return;
  const preset = new URLSearchParams(location.search).get("event");
  try {
    const rows = await RN_FRAPPE.call("rescue_net.api_ai.public_active_disasters", {});
    if (Array.isArray(rows) && rows.length) {
      sel.innerHTML = rows.map(d => {
        const id = d.id || d.legacy_id || d.name;
        return `<option value="${safe(id)}">${safe(d.title || id)}${d.severity ? " — " + safe(d.severity) : ""}</option>`;
      }).join("");
      if (preset) {
        // ?event=event-sim-001 must also pick "disaster_events:event-sim-001" (legacy id)
        const opt = [...sel.options].find(o => o.value === preset || o.value.endsWith(":" + preset) || preset.endsWith(":" + o.value));
        if (opt) sel.value = opt.value;
      }
      if (!sel.value) sel.selectedIndex = 0;
      sel.dispatchEvent(new Event("change"));
    }
  } catch (e) { /* keep the fallback option */ }
}


function setupPublicAidForm() {
  const form =
    document.querySelector(
      "[data-public-aid-form]"
    );

  const result =
    document.querySelector(
      "[data-public-aid-result]"
    );

  if (!form) return;

  populateDisasterPicker(form);
  setupDeliveryModeToggle(form);
  initAidItems(form);
  setupAidLocationPicker(form);
  setupAidAttachments(form);

  form.addEventListener(
    "submit",
    async e => {
      e.preventDefault();

      if (!window.RN_FRAPPE) {
        result.innerHTML =
          `<div class="alert danger">` +
          `Frappe client tidak tersedia.` +
          `</div>`;

        return;
      }

      const deliveryMode =
        form.delivery_mode.value;

      const handlingMode =
        mapDeliveryMode(
          deliveryMode
        );

      const targetPosko =
        deliveryMode ===
        "self_deliver_to_posko"
          ? (
              form.target_node_id.value
                .trim() ||
              null
            )
          : null;

      const donorName =
        form.donor_name.value.trim();

      const donorContact =
        form.donor_contact.value.trim();

      const items = form.__collectAidItems
        ? form.__collectAidItems()
        : [];

      if (!donorName || !donorContact || !items.length) {
        result.innerHTML =
          `<div class="alert danger">` +
          `Lengkapi nama, HP, dan minimal satu item barang.` +
          `</div>`;
        return;
      }

      const incomplete = items.find(it => !it.quantity || !it.unit);
      if (incomplete) {
        result.innerHTML =
          `<div class="alert danger">` +
          `Lengkapi jumlah &amp; satuan untuk "${safe(incomplete.item_text)}".` +
          `</div>`;
        return;
      }

      try {
        result.innerHTML =
          `<div class="alert neutral">` +
          `Menyimpan ${items.length} item bantuan ke Frappe...` +
          `</div>`;

        const submit = form.querySelector('[type="submit"]');
        if (submit) submit.disabled = true;
        const attachments = form.__readAidAttachments ? await form.__readAidAttachments() : [];
        const notesRaw = form.notes.value.trim();
        const arrival = (form.expected_arrival_at && form.expected_arrival_at.value.trim()) || "";
        const notesOut = [notesRaw, arrival ? ("Perkiraan sampai posko: " + arrival) : ""]
          .filter(Boolean).join(" | ") || null;

        const data =
          await RN_FRAPPE.call(
            "rescue_net.api_logistics." +
            "submit_guest_aid_offer_multi",
            {
              disaster_event:
                form.disaster_event_id.value.trim(),

              donor_name: donorName,
              donor_contact: donorContact,

              items_json: JSON.stringify(items),

              handling_mode:
                deliveryMode === "need_pickup" ? "need_pickup" : "self_deliver",
              target_posko: targetPosko,

              pickup_location:
                form.pickup_location.value.trim() || null,

              pickup_latitude:
                form.pickup_lat && form.pickup_lat.value
                  ? Number(form.pickup_lat.value)
                  : null,

              pickup_longitude:
                form.pickup_lng && form.pickup_lng.value
                  ? Number(form.pickup_lng.value)
                  : null,

              ready_at:
                form.ready_at.value.trim() || null,

              attachments_json: JSON.stringify(attachments),
              notes: notesOut
            },
            {
              method: "POST"
            }
          );

        renderCreateSuccess(
          result,
          data
        );

        addGuestAttachmentButtons(result, data.attachments, { aid_offer: data.aid_offers[0].aid_offer, edit_code: data.edit_code, donor_contact: donorContact });
        form.reset();
        if (form.__resetAidAttachments) form.__resetAidAttachments();
        if (form.__resetAidItems) form.__resetAidItems();
        if (form.__resetAidLocation) form.__resetAidLocation();

        if (
          form.disaster_event_id
        ) {
          form.disaster_event_id.value =
            "event-sim-001";
        }

        if (
          form.delivery_mode
        ) {
          form.delivery_mode.value =
            "need_pickup";
        }

        setupDeliveryModeToggle(
          form
        );

      } catch (err) {
        result.innerHTML =
          `<div class="alert danger">` +
          `${safe(err.message)}` +
          `</div>`;
      } finally {
        const submit = form.querySelector('[type="submit"]');
        if (submit) submit.disabled = false;
      }
    }
  );
}


function setupEditAidForm() {
  const form = document.querySelector("[data-edit-aid-form]");
  const result = document.querySelector("[data-edit-aid-result]");
  if (!form) return;

  const fields = form.querySelector("[data-edit-fields]");
  const loadBtn = form.querySelector("[data-load-aid]");

  // pre-fill Aid ID from ?aid= (link from the submit success box)
  try {
    const qa = new URLSearchParams(location.search).get("aid");
    if (qa) form.aid_offer_id.value = qa;
  } catch (e) {}

  function creds() {
    return {
      aid_offer: form.aid_offer_id.value.trim(),
      edit_code: form.edit_code.value.trim(),
      donor_contact: form.donor_contact.value.trim(),
    };
  }

  async function loadAid() {
    const c = creds();
    if (!c.aid_offer || !c.edit_code || !c.donor_contact) {
      result.innerHTML = `<div class="alert danger">Isi Aid ID, Kode Edit, dan HP.</div>`;
      return;
    }
    result.innerHTML = `<div class="alert neutral">Memuat…</div>`;
    try {
      const d = await RN_FRAPPE.call(
        "rescue_net.api_logistics.get_guest_aid_offer", c, { method: "POST" }
      );
      form.item_name.value = d.item_name || "";
      form.quantity.value = d.quantity != null ? d.quantity : "";
      form.unit.value = d.unit || "";
      form.pickup_location.value = d.pickup_location || "";
      form.ready_at.value = d.ready_at || "";
      form.notes.value = d.notes || "";
      form.cancel.checked = false;
      fields.hidden = false;
      const sib = (d.batch_items || []).map(b =>
        `<div><span>${safe(b.item_name)}</span><strong>${safe(b.name)} · ${safe(b.offer_status)}</strong></div>`
      ).join("");
      result.innerHTML = `
        <div class="alert neutral">
          Bantuan dimuat: <b>${safe(d.item_name)}</b> · ${safe(d.offer_status)}
          ${d.canonical_group ? ` · kelompok: ${safe(d.canonical_group)}` : ""}
        </div>
        ${sib ? `<div class="panel" style="margin-top:8px"><h4>Item lain di pengiriman yang sama</h4><div class="code-grid">${sib}</div><p class="subtitle">Kode Edit yang sama berlaku untuk semua. Ubah satu per satu lewat Aid ID masing-masing.</p></div>` : ""}
      `;
      addGuestAttachmentButtons(result, d.attachments, c);
    } catch (err) {
      fields.hidden = true;
      result.innerHTML = `<div class="alert danger">${safe(err.message)}</div>`;
    }
  }

  if (loadBtn) loadBtn.addEventListener("click", loadAid);

  form.addEventListener("submit", async e => {
      e.preventDefault();
      if (!window.RN_FRAPPE) {
        result.innerHTML = `<div class="alert danger">Frappe client tidak tersedia.</div>`;
        return;
      }
      const c = creds();
      if (!c.aid_offer || !c.edit_code || !c.donor_contact) {
        result.innerHTML = `<div class="alert danger">Isi Aid ID, Kode Edit, dan HP lalu klik Muat dulu.</div>`;
        return;
      }
      const cancel = form.cancel && form.cancel.checked;
      try {
        result.innerHTML = `<div class="alert neutral">${cancel ? "Membatalkan" : "Menyimpan"} bantuan…</div>`;
        const data = await RN_FRAPPE.call(
            "rescue_net.api_logistics.edit_guest_aid_offer",
            {
              aid_offer: c.aid_offer,
              edit_code: c.edit_code,
              donor_contact: c.donor_contact,
              cancel: cancel ? 1 : 0,
              item_text: form.item_name.value.trim() || null,
              quantity: form.quantity.value ? Number(form.quantity.value) : null,
              unit: form.unit.value.trim() || null,
              pickup_location: form.pickup_location.value.trim() || null,
              ready_at: form.ready_at.value.trim() || null,
              notes: form.notes.value.trim() || null,
            },
            { method: "POST" }
          );

        result.innerHTML = `
          <div class="success-box">
            <h3>${cancel ? "Bantuan dibatalkan" : "Bantuan berhasil diupdate"}</h3>
            <div class="code-grid">
              <div><span>Aid ID</span><strong>${safe(data.aid_offer)}</strong></div>
              <div><span>Status</span><strong>${safe(data.offer_status)}</strong></div>
              ${data.item_name ? `<div><span>Item</span><strong>${safe(data.item_name)}${data.quantity ? " — " + safe(data.quantity) + " " + safe(data.unit || "") : ""}</strong></div>` : ""}
              ${data.canonical_group ? `<div><span>Kelompok</span><strong>${safe(data.canonical_group)}</strong></div>` : ""}
            </div>
          </div>
        `;
      } catch (err) {
        result.innerHTML = `<div class="alert danger">${safe(err.message)}</div>`;
      }
    }
  );
}


document.addEventListener(
  "DOMContentLoaded",
  () => {
    setupPublicAidForm();
    setupEditAidForm();
  }
);

// Fase 10f: "Kirim ke posko ini" from kebutuhan-publik.html -> ?posko=<name>
// Audit SOP 12 Nov (S3): posko tujuan dipilih dari daftar NAMA (bencana yang dibuka); ID & nama tersembunyi terisi otomatis.
document.addEventListener("DOMContentLoaded", () => {
  const qs = new URLSearchParams(location.search);
  const posko = qs.get("posko") || "";
  const presetName = qs.get("target_node_name") || "";
  let ev = (qs.get("event") || "").replace(/^disaster_events:/, "");
  if (!ev) { try { ev = (localStorage.getItem("rn_active_event") || "").replace(/^disaster_events:/, ""); } catch (e) {} }
  document.querySelectorAll("form").forEach(form => {
    if (!form.target_node_id) return;
    const pick = form.querySelector("[data-posko-pick]");
    const setVal = (id, name) => { form.target_node_id.value = id || ""; if (form.target_node_name) form.target_node_name.value = name || ""; };
    if (posko) {
      setVal(posko, presetName);
      if (form.delivery_mode) {
        form.delivery_mode.value = "self_deliver_to_posko";
        form.delivery_mode.dispatchEvent(new Event("change", { bubbles: true }));
      }
    }
    if (!pick) return;
    pick.addEventListener("change", () => setVal(pick.value, pick.selectedOptions[0] ? pick.selectedOptions[0].textContent : ""));
    if (!ev) { pick.innerHTML = '<option value="">Pilih bencana dulu</option>'; return; }
    fetch("/rescue-net-frappe/api/method/rescue_net.api_control_centre.event_poskos?disaster_event=" + encodeURIComponent(ev), { credentials: "include" })
      .then(r => r.ok ? r.json() : null)
      .then(j => {
        const pts = ((j && j.message && j.message.points) || []).filter(pt => (pt.posko_id || pt.id));
        pick.innerHTML = '<option value="">— pilih posko tujuan —</option>' + pts.map(pt => {
          const id = String(pt.posko_id || pt.id), nm = String(pt.name || id);
          return '<option value="' + id.replace(/"/g, "&quot;") + '">' + nm.replace(/</g, "&lt;") + "</option>";
        }).join("");
        if (posko) {
          const opt = [...pick.options].find(o => o.value === posko);
          if (opt) { pick.value = posko; setVal(posko, opt.textContent); }
          else { pick.insertAdjacentHTML("beforeend", '<option value="' + posko.replace(/"/g, "&quot;") + '">' + (presetName || "Posko pilihan Anda").replace(/</g, "&lt;") + "</option>"); pick.value = posko; }
        }
      })
      .catch(() => { pick.innerHTML = '<option value="">Daftar posko gagal dimuat — coba muat ulang</option>'; });
  });
});
