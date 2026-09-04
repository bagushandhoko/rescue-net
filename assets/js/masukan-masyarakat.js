/* Masukan Masyarakat — api_forum.* */
(function () {
  "use strict";
  var A = "rescue_net.api_forum.";
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var qs = new URLSearchParams(location.search);
  function getEvent() { return qs.get("event") || "event-sim-001"; }
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function fmt(s) { return s ? String(s).slice(0, 16).replace("T", " ") : ""; }

  var CAT = "";
  var CAN_RESPOND = false;
  try {
    var sr = window.RN_SESSION_ROLE || {};
    CAN_RESPOND = sr.is_system_manager ||
      ["community_coordinator", "posko_operator", "command_center", "system_manager"].indexOf(sr.role) !== -1;
  } catch (e) {}

  function threadHtml(t) {
    var resp = t.official_response
      ? '<div class="mf-resp"><b>Tanggapan resmi</b>' + (t.responded_by ? " · " + esc(t.responded_by) : "") +
        "<br>" + esc(t.official_response) + "</div>"
      : "";
    var replies = (t.replies || []).map(function (r) {
      return '<div class="mf-reply"><b>' + esc(r.author_name || "Warga") + "</b> <span class=\"rn-muted\">" +
        fmt(r.creation) + "</span><br>" + esc(r.body) + "</div>";
    }).join("");
    var actions = '<div class="mf-actions" data-fid="' + esc(t.name) + '">' +
      '<button type="button" class="btn ghost mini" data-act="up">▲ Dukung <b>' + (t.upvotes || 0) + "</b></button>" +
      '<button type="button" class="btn ghost mini" data-act="reply">Balas</button>' +
      (CAN_RESPOND ? '<button type="button" class="btn ghost mini" data-act="respond">Tanggapi (resmi)</button>' +
        '<button type="button" class="btn ghost mini" data-act="resolve">Tandai selesai</button>' : "") +
      '<span class="rn-muted mf-msg"></span></div>' +
      '<div class="mf-inline" hidden></div>';
    return '<article class="mf-thread">' +
      '<div class="rn-row"><span class="mf-cat">' + esc(t.category) + "</span>" +
      '<span class="chip ' + (t.status === "resolved" ? "success" : (t.status === "noted" ? "neutral" : "warning")) + '">' + esc(t.status) + "</span></div>" +
      "<h4>" + esc(t.topic) + "</h4>" +
      '<div class="mf-meta">' + esc(t.author_name || "Warga") + (t.wilayah ? " · " + esc(t.wilayah) : "") + " · " + fmt(t.creation) +
      (t.reply_count ? " · " + t.reply_count + " balasan" : "") + "</div>" +
      '<div class="mf-body">' + esc(t.body) + "</div>" +
      resp + replies + actions + "</article>";
  }

  async function load() {
    var d;
    try {
      d = await window.RN_FRAPPE.call(A + "feedback_threads", { disaster_event: getEvent(), category: CAT || null });
    } catch (e) {
      $("#mfStatus").textContent = "Gagal memuat: " + (e && e.message || e);
      return;
    }
    var threads = d.threads || [];
    $("#mfStatus").textContent = threads.length + " topik · " + (d.open_count || 0) + " terbuka.";
    $("#mfCount").textContent = threads.length + " topik";
    $("#mfThreads").innerHTML = threads.length
      ? threads.map(threadHtml).join("")
      : '<p class="rn-muted" style="padding:10px 0">Belum ada masukan' + (CAT ? " kategori " + esc(CAT) : "") + ". Jadilah yang pertama.</p>";
    wireThreadActions();
  }

  function wireThreadActions() {
    document.querySelectorAll("#mfThreads .mf-actions [data-act]").forEach(function (btn) {
      btn.addEventListener("click", async function () {
        var box = btn.closest("[data-fid]");
        var fid = box.getAttribute("data-fid");
        var msg = box.querySelector(".mf-msg");
        var inline = box.nextElementSibling;
        var act = btn.getAttribute("data-act");
        try {
          if (act === "up") {
            var r = await window.RN_FRAPPE.call(A + "upvote_feedback", { feedback: fid }, { method: "POST" });
            btn.innerHTML = "▲ Dukung <b>" + r.upvotes + "</b>";
          } else if (act === "resolve") {
            await window.RN_FRAPPE.call(A + "respond_feedback", { feedback: fid, status: "resolved" }, { method: "POST" });
            await load();
          } else if (act === "reply" || act === "respond") {
            inline.hidden = false;
            inline.innerHTML = '<textarea rows="2" style="width:100%" placeholder="' +
              (act === "respond" ? "Tanggapan resmi…" : "Balasan Anda…") + '"></textarea>' +
              '<button type="button" class="btn primary mini" style="margin-top:5px">Kirim</button>';
            inline.querySelector("button").addEventListener("click", async function () {
              var val = inline.querySelector("textarea").value.trim();
              if (!val) return;
              try {
                if (act === "respond") {
                  await window.RN_FRAPPE.call(A + "respond_feedback",
                    { feedback: fid, response: val, status: "noted" }, { method: "POST" });
                } else {
                  await window.RN_FRAPPE.call(A + "post_feedback",
                    { topic: "Re: balasan", body: val, disaster_event: getEvent(), parent_feedback: fid }, { method: "POST" });
                }
                await load();
              } catch (e2) { msg.textContent = " gagal: " + (e2 && e2.message || e2); }
            });
          }
        } catch (err) {
          msg.textContent = " gagal: " + (err && err.message || err);
        }
      });
    });
  }

  function wireTabs() {
    document.querySelectorAll("#mfTabs button").forEach(function (b) {
      b.addEventListener("click", function () {
        document.querySelectorAll("#mfTabs button").forEach(function (x) { x.classList.remove("is-active"); });
        b.classList.add("is-active");
        CAT = b.getAttribute("data-cat");
        load();
      });
    });
  }

  function wireForm() {
    var form = $("#mfForm");
    var msg = form.querySelector("[data-mf-msg]");
    form.addEventListener("submit", async function (e) {
      e.preventDefault();
      var fd = new FormData(form);
      msg.textContent = "Mengirim…";
      try {
        await window.RN_FRAPPE.call(A + "post_feedback", {
          topic: fd.get("topic"), body: fd.get("body"),
          disaster_event: fd.get("disaster_event"), category: fd.get("category"),
          author_name: fd.get("author_name") || null,
          author_contact: fd.get("author_contact") || null,
          wilayah: fd.get("wilayah") || null,
        }, { method: "POST" });
        msg.textContent = "Terkirim.";
        form.reset();
        await load();
      } catch (err) {
        msg.textContent = "Gagal: " + (err && err.message || err);
      }
    });
  }

  if (document.readyState === "loading")
    document.addEventListener("DOMContentLoaded", function () { wireTabs(); wireForm(); load(); });
  else { wireTabs(); wireForm(); load(); }
})();
