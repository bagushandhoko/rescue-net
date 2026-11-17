/* A public action on pages displaying one receiving posko. */
(function () {
  "use strict";
  function init() {
    var q = new URLSearchParams(location.search);
    var id = q.get("id") || q.get("posko");
    var title = document.querySelector("main .topbar h2");
    if (!id || !title || document.getElementById("rnKirimBantuan")) return;
    var event = q.get("event") || "", resolvedTitle = "";
    var link = document.createElement("a");
    link.id = "rnKirimBantuan";
    link.className = "btn primary";
    link.textContent = "Kirim Bantuan";
    link.style.cssText = "display:inline-flex;min-height:44px;max-width:100%;box-sizing:border-box;margin-top:10px;white-space:normal";
    function update() {
      var params = new URLSearchParams({ posko: id, event: event,
        target_node_name: resolvedTitle || title.textContent.trim() });
      link.href = "kirim-bantuan.html?" + params;
    }
    title.insertAdjacentElement("afterend", link);
    update();
    new MutationObserver(update).observe(title, { childList: true, characterData: true, subtree: true });
    // Several boards keep a generic heading; resolve the actual posko name for prefill.
    if (event && window.RN_FRAPPE) {
      window.RN_FRAPPE.call("rescue_net.api_control_centre.event_poskos", { disaster_event: event }, { method: "GET" })
        .then(function (r) {
          var p = (r.points || []).find(function (p) { return (p.posko_id || p.id) === id; });
          if (p) { resolvedTitle = p.name || p.title || ""; update(); }
        }).catch(function () { /* The header still provides a usable prefill. */ });
    }
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();

/* Public incoming activity, shared by every receiving posko detail. */
(function () {
  'use strict';
  function init() {
    var q = new URLSearchParams(location.search), id = q.get('id') || q.get('posko');
    var button = document.getElementById('rnKirimBantuan');
    if (!id || !button || !window.RN_FRAPPE) return;
    var panel = document.createElement('section');
    panel.id = 'rnMenujuPosko';
    panel.setAttribute('aria-label', 'Menuju posko ini');
    panel.style.cssText = 'margin:16px 0;padding:16px;border:1px solid #ccd6df;border-radius:12px;background:var(--card,#fff);max-width:100%;box-sizing:border-box;overflow-wrap:anywhere';
    button.parentElement.insertAdjacentElement('afterend', panel);
    function el(tag, text, parent) {
      var e = document.createElement(tag); e.textContent = text; parent.appendChild(e); return e;
    }
    el('h3', 'Menuju posko ini', panel);
    var chart = document.createElement('div'); chart.className = 'rn-pie-grid'; panel.appendChild(chart);
    var body = document.createElement('div'); panel.appendChild(body);
    var refresh = el('button', 'Perbarui pantauan', panel);
    refresh.type = 'button'; refresh.className = 'btn'; refresh.style.minHeight = '44px';
    function render(data) {
      if (window.RNPoskoCharts) RNPoskoCharts.incoming(chart, data);
      body.replaceChildren();
      [['in_transit', 'Bantuan dalam perjalanan'], ['booked', 'Sudah dibooking'],
        ['arrivals', 'Armada & relawan yang akan datang']].forEach(function (group) {
        el('h4', group[1], body);
        var rows = data[group[0]] || [];
        if (!rows.length) el('p', 'Belum ada yang tercatat.', body);
        rows.forEach(function (r) {
          var card = el('div', '', body); card.style.cssText = 'padding:12px 0;border-bottom:1px solid #dde3ea;min-width:0';
          el('strong', r.item || 'Bantuan', card);
          var chip = el('span', r.status_label, card);
          chip.style.cssText = 'display:inline-block;padding:3px 8px;margin:4px 8px;border-radius:12px;background:#e8f2ff;color:#183e68;font-size:12px;max-width:100%;box-sizing:border-box';
          var details = [];
          if (r.quantity) details.push(r.quantity + ' ' + (r.unit || ''));
          if (r.sender) details.push('Pengirim: ' + r.sender);
          if (r.armada) details.push('Armada: ' + r.armada);
          if (r.eta) details.push('Perkiraan / jadwal: ' + r.eta);
          if (details.length) el('p', details.join(' · '), card);
          if (r.href) { var a = el('a', r.kind === 'flow' ? 'Pantau kiriman' : 'Lihat pantauan', card); a.href = r.href; a.style.cssText = 'display:inline-flex;align-items:center;min-height:44px'; }
        });
      });
    }
    function load() {
      refresh.disabled = true;
      chart.replaceChildren();
      body.textContent = 'Memuat pantauan…';
      window.RN_FRAPPE.call('rescue_net.api_public_needs.incoming_for_posko',
        {posko: id, event: q.get('event') || undefined}, {method: 'GET'})
        .then(render).catch(function () { body.textContent = 'Pantauan belum dapat dimuat. Coba perbarui kembali.'; })
        .finally(function () { refresh.disabled = false; });
    }
    refresh.addEventListener('click', load); load();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
