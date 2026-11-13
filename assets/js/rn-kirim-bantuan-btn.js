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
