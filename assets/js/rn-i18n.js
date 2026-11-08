/* Dua bahasa Indonesia / English (owner 2026-11-03, pola sac-energi.online): tombol ID | EN di header,
   pilihan disimpan di browser (rn-lang) atau ?lang=en. Bahasa sumber = Indonesia; mode EN menerjemahkan
   teks & atribut (placeholder/title/aria-label/alt) memakai kamus assets/i18n/en.json, termasuk teks yang
   muncul belakangan (MutationObserver). Teks yang belum ada di kamus tetap Indonesia.
   Elemen bertanda [data-no-i18n] (mis. data pengguna) tidak diterjemahkan. */
(function () {
  "use strict";
  if (window.RN_I18N) return;
  var KEY = "rn-lang";
  var me = document.currentScript && document.currentScript.src || "";
  var base = me ? me.replace(/assets\/js\/rn-i18n\.js.*$/, "") : "../";
  var DICT = null, lang = "id", observer = null, busy = false;
  var origText = new WeakMap();          // text node -> original Indonesian
  var origAttr = new WeakMap();          // element -> {attr: original}
  var ATTRS = ["placeholder", "title", "aria-label", "alt"];
  var SKIP = { SCRIPT: 1, STYLE: 1, NOSCRIPT: 1, TEXTAREA: 1, CODE: 1, PRE: 1, svg: 1 };
  var EDGE = /^([\s·:—\-–•→←›»«✓✕×*()\[\]"']*)([\s\S]*?)([\s·:—\-–•→←›»«✓✕×*()\[\]"'.!?,]*)$/;

  function getLang() {
    var q = /[?&]lang=(id|en)\b/.exec(location.search);
    if (q) { save(q[1]); return q[1]; }
    try { var v = localStorage.getItem(KEY); if (v === "en" || v === "id") return v; } catch (e) {}
    return "id";
  }
  function save(l) { try { localStorage.setItem(KEY, l); } catch (e) {} }

  function lookup(src) {
    if (!DICT || !src) return null;
    var s = src.replace(/\s+/g, " ").trim();
    if (!s) return null;
    if (DICT[s] != null) return DICT[s];
    var m = EDGE.exec(s);
    if (m && m[2] && DICT[m[2]] != null) return m[1] + DICT[m[2]] + m[3];
    return null;
  }

  function skipEl(el) {
    for (var e = el; e && e !== document.body; e = e.parentNode) {
      if (e.nodeType !== 1) continue;
      if (SKIP[e.tagName] || e.isContentEditable || e.hasAttribute("data-no-i18n")) return true;
    }
    return false;
  }

  function doText(n) {
    var cur = n.nodeValue;
    if (!cur || !/[A-Za-z]{2}/.test(cur)) return;
    var orig = origText.get(n);
    if (orig != null && cur !== orig && cur === n.__rnEn) {
      // still showing our translation
    } else {
      orig = cur;
      origText.set(n, orig);
    }
    if (lang === "en") {
      var t = lookup(orig);
      if (t != null) {
        var lead = orig.match(/^\s*/)[0], tail = orig.match(/\s*$/)[0];
        var v = lead + t + tail;
        n.__rnEn = v;
        if (n.nodeValue !== v) n.nodeValue = v;
      }
    } else if (n.nodeValue !== orig) {
      n.nodeValue = orig;
    }
  }

  function doAttrs(el) {
    var store = origAttr.get(el);
    for (var i = 0; i < ATTRS.length; i++) {
      var a = ATTRS[i];
      if (!el.hasAttribute(a)) continue;
      var cur = el.getAttribute(a);
      if (!store) { store = {}; origAttr.set(el, store); }
      if (!(a in store) || (cur !== store[a] && cur !== (store["__en_" + a]))) store[a] = cur;
      if (lang === "en") {
        var t = lookup(store[a]);
        if (t != null) { store["__en_" + a] = t; if (cur !== t) el.setAttribute(a, t); }
      } else if (cur !== store[a]) {
        el.setAttribute(a, store[a]);
      }
    }
  }

  function walk(root) {
    if (!root) return;
    if (root.nodeType === 3) { if (!skipEl(root.parentNode)) doText(root); return; }
    if (root.nodeType !== 1 || skipEl(root)) return;
    doAttrs(root);
    var tw = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT, {
      acceptNode: function (n) {
        if (n.nodeType === 1) return (SKIP[n.tagName] || n.hasAttribute("data-no-i18n")) ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT;
        return NodeFilter.FILTER_ACCEPT;
      }
    });
    var n;
    while ((n = tw.nextNode())) { if (n.nodeType === 3) doText(n); else doAttrs(n); }
  }

  var pending = [], scheduled = false;
  function flush() {
    scheduled = false;
    var list = pending; pending = [];
    busy = true;
    try { list.forEach(walk); if (lang === "en") translateTitle(); } finally { busy = false; observer && observer.takeRecords(); }
  }
  function queue(n) { pending.push(n); if (!scheduled) { scheduled = true; requestAnimationFrame(flush); } }

  var origTitle = null;
  function translateTitle() {
    if (origTitle == null || (document.title !== origTitle && document.title !== document.__rnEnTitle)) origTitle = document.title;
    if (lang === "en") {
      var parts = origTitle.split(" | ").map(function (p) { return lookup(p) || p; });
      document.__rnEnTitle = parts.join(" | ");
      if (document.title !== document.__rnEnTitle) document.title = document.__rnEnTitle;
    } else if (document.title !== origTitle) document.title = origTitle;
  }

  function startObserver() {
    if (observer || !window.MutationObserver) return;
    observer = new MutationObserver(function (recs) {
      if (busy) return;
      recs.forEach(function (r) {
        if (r.type === "childList") r.addedNodes.forEach(queue);
        else if (r.type === "characterData") queue(r.target);
        else if (r.type === "attributes") queue(r.target);
      });
    });
    observer.observe(document.body, { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ATTRS });
  }

  function loadDict() {
    if (DICT) return Promise.resolve(DICT);
    var ss = null;
    try { ss = sessionStorage.getItem("rn-i18n-en@" + VERSION); } catch (e) {}
    if (ss) { try { DICT = JSON.parse(ss); return Promise.resolve(DICT); } catch (e) {} }
    return fetch(base + "assets/i18n/en.json?v=" + VERSION, { credentials: "omit" })
      .then(function (r) { return r.ok ? r.json() : {}; })
      .catch(function () { return {}; })
      .then(function (d) { DICT = d || {}; try { sessionStorage.setItem("rn-i18n-en@" + VERSION, JSON.stringify(DICT)); } catch (e) {} return DICT; });
  }
  var VERSION = (/[?&]v=([^&]+)/.exec(me) || [])[1] || "1";

  function paintButtons() {
    document.querySelectorAll(".rn-lang button").forEach(function (b) {
      b.setAttribute("aria-pressed", b.getAttribute("data-lang") === lang ? "true" : "false");
    });
  }

  function apply(l) {
    lang = l;
    document.documentElement.lang = l;
    paintButtons();
    var run = function () { busy = true; try { walk(document.body); translateTitle(); } finally { busy = false; observer && observer.takeRecords(); } startObserver(); };
    if (l === "en") return loadDict().then(run);
    run();
    return Promise.resolve();
  }

  function set(l) { save(l); apply(l); }

  function makeToggle() {
    var w = document.createElement("div");
    w.className = "rn-lang";
    w.setAttribute("role", "group");
    w.setAttribute("aria-label", "Language / Bahasa");
    w.setAttribute("data-no-i18n", "");
    w.innerHTML = '<button type="button" data-lang="id">ID</button><button type="button" data-lang="en">EN</button>';
    w.addEventListener("click", function (e) { var b = e.target.closest("button[data-lang]"); if (b) set(b.getAttribute("data-lang")); });
    return w;
  }

  function mountToggles(final) {
    var spots = [];
    var act = document.querySelector(".rn-public-header .rn-public-actions");
    if (act && !act.querySelector(".rn-lang")) { act.insertBefore(makeToggle(), act.firstChild); spots.push(act); }
    var top = document.querySelector(".rn-drawer-topbar");
    if (top && !top.querySelector(".rn-lang")) { var t = makeToggle(); t.classList.add("rn-lang-top"); top.appendChild(t); spots.push(top); }
    if (spots.length || document.querySelector(".rn-public-header .rn-lang, .rn-drawer-topbar .rn-lang")) {
      document.querySelectorAll(".rn-lang-float").forEach(function (x) { x.remove(); });
    } else if (final && !document.querySelector(".rn-lang")) {          // halaman tanpa header publik
      var f = makeToggle(); f.classList.add("rn-lang-float"); document.body.appendChild(f);
    }
    paintButtons();
  }

  function css() {
    if (document.getElementById("rn-i18n-css")) return;
    var st = document.createElement("style"); st.id = "rn-i18n-css";
    st.textContent = ".rn-lang{display:inline-flex;border:1px solid rgba(104,64,45,.3);border-radius:8px;overflow:hidden;font:700 12px/1 system-ui,sans-serif;flex-shrink:0;margin-right:8px;vertical-align:middle}" +
      ".rn-lang button{border:0;background:#fff;color:#5e4b40;padding:6px 9px;cursor:pointer;font:inherit}" +
      ".rn-lang button[aria-pressed=true]{background:#e8755a;color:#fff}" +
      ".rn-lang button:focus-visible{outline:2px solid #e8755a;outline-offset:-2px}" +
      ".rn-lang-top{margin:0 6px 0 auto}" +
      ".rn-lang-float{position:fixed;right:max(12px,env(safe-area-inset-right,0px));bottom:calc(84px + env(safe-area-inset-bottom,0px));z-index:900;box-shadow:0 2px 8px rgba(0,0,0,.15)}";
    document.head.appendChild(st);
  }

  function boot() {
    css();
    mountToggles();
    // header/topbar can be built after us — try again a little later
    setTimeout(mountToggles, 600); setTimeout(function () { mountToggles(true); }, 2000);
    apply(getLang());
  }

  window.RN_I18N = { set: set, get lang() { return lang; }, t: function (s) { return lang === "en" ? (lookup(s) || s) : s; } };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot); else boot();
})();
