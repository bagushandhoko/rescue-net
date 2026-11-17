/* Tautan objek di hasil AI (owner 2026-11-17: "ai analisis harus bisa di klik sampai ke objek
   yang disarankan atau dikatakan"). Dibuat Suri (Claude CT105).
   RNAiTautan.tautkan(el, eventId): ID data (posko, kebutuhan, armada, kiriman, laporan, dll.) dan
   nama posko di dalam `el` diubah menjadi tautan ke halaman objeknya. Server
   (rescue_net.api_ai.tautan_objek) hanya mengembalikan objek yang benar-benar ada. */
(function () {
  var CALON = /[A-Za-z0-9_][A-Za-z0-9_:.\-]{3,139}/g;
  var LEWATI = { A: 1, SCRIPT: 1, STYLE: 1, BUTTON: 1, TEXTAREA: 1, INPUT: 1, SELECT: 1 };

  function teksNode(el) {
    var out = [], w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT, {
      acceptNode: function (n) {
        for (var p = n.parentNode; p && p !== el; p = p.parentNode) if (LEWATI[p.nodeName]) return NodeFilter.FILTER_REJECT;
        return n.nodeValue && n.nodeValue.trim() ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT;
      }
    });
    while (w.nextNode()) out.push(w.currentNode);
    return out;
  }

  function calonId(teks) {
    var set = {};
    (teks.match(CALON) || []).forEach(function (t) {
      t = t.replace(/[.:\-]+$/, "");
      if (t.length >= 4 && /[-:]/.test(t) && /\d|SIM|sim|posko|event/.test(t)) set[t] = 1;
    });
    return Object.keys(set).slice(0, 400);
  }

  function escRe(s) { return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"); }

  async function tautkan(el, eventId) {
    if (!el || typeof frappeCall !== "function") return;
    var nodes = teksNode(el);
    var semua = nodes.map(function (n) { return n.nodeValue; }).join("\n");
    var ids = calonId(semua);
    var res;
    try {
      res = await frappeCall("rescue_net.api_ai.tautan_objek", { ids: JSON.stringify(ids), disaster_event_id: eventId || "" }, true);
    } catch (e) { return; }
    var peta = {};
    Object.keys((res && res.objek) || {}).forEach(function (k) { peta[k] = res.objek[k]; });
    ((res && res.posko) || []).forEach(function (p) {
      if (p.title && semua.indexOf(p.title) !== -1 && !peta[p.title]) peta[p.title] = { url: p.url, label: p.label || ("Posko: " + p.title) };
    });
    var kunci = Object.keys(peta).sort(function (a, b) { return b.length - a.length; });
    if (!kunci.length) return;
    var re = new RegExp("(" + kunci.map(escRe).join("|") + ")", "g");
    nodes.forEach(function (n) {
      var v = n.nodeValue;
      if (!re.test(v)) return;
      re.lastIndex = 0;
      var frag = document.createDocumentFragment(), last = 0, m;
      while ((m = re.exec(v))) {
        if (m.index > last) frag.appendChild(document.createTextNode(v.slice(last, m.index)));
        var o = peta[m[1]], a = document.createElement("a");
        a.href = o.url; a.target = "_blank"; a.rel = "noopener";
        a.className = "rn-ai-obj"; a.title = (o.label || "") + " — buka halaman";
        a.textContent = m[1];
        frag.appendChild(a);
        last = m.index + m[1].length;
      }
      if (last < v.length) frag.appendChild(document.createTextNode(v.slice(last)));
      n.parentNode.replaceChild(frag, n);
    });
  }

  if (!document.getElementById("rnAiObjCss")) {
    var st = document.createElement("style");
    st.id = "rnAiObjCss";
    st.textContent = "a.rn-ai-obj{color:var(--rn-link,#0b62c4);text-decoration:underline dotted;text-underline-offset:2px;font-weight:600}a.rn-ai-obj:hover{text-decoration:underline}";
    document.head.appendChild(st);
  }
  window.RNAiTautan = { tautkan: tautkan };
})();
