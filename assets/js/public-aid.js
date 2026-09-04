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
      if (preset) sel.value = preset;
      if (!sel.value) sel.selectedIndex = 0;
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

              ready_at:
                form.ready_at.value.trim() || null,

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

        form.reset();
        if (form.__resetAidItems) form.__resetAidItems();

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
