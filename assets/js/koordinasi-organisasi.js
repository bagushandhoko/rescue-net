/* ============================================================
 * Koordinasi Internal Organisasi — the org-member workspace.
 * Board: rescue_net.api_control_centre.my_org_coordination
 *
 * A logged-in org member sees his OWN posko (editable) plus his
 * organisation's other poskos and open external poskos (read-only).
 * The full cross-org picture stays on the Control Centre page.
 * ============================================================ */
(function () {
  "use strict";

  var BOARD = "rescue_net.api_control_centre.my_org_coordination";

  var $ = function (s, r) { return (r || document).querySelector(s); };
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  var qs = new URLSearchParams(location.search);
  function getEvent() { return qs.get("event") || "event-sim-001"; }

  var TYPE_LABEL = {
    logistics: "Logistik", collection_hub: "Gudang Pengumpul", transport: "Transport / Distribusi",
    medical: "Medis", shelter: "Shelter", kitchen: "Dapur Umum",
    field_assessment: "Assessment Lapangan", posko_operator: "Operator Posko", org_admin: "Admin Organisasi"
  };
  function typeLabel(t) { return TYPE_LABEL[String(t || "").toLowerCase()] || (t || "Posko"); }

  function statusChip(s) {
    var l = String(s || "").toLowerCase();
    var cls = "neutral", label = s || "normal";
    if (l === "critical") { cls = "danger"; label = "Kritis"; }
    else if (l === "urgent") { cls = "warning"; label = "Mendesak"; }
    else if (l === "active" || l === "normal") { cls = "success"; label = l === "active" ? "Aktif" : "Normal"; }
    return '<span class="chip ' + cls + '">' + esc(label) + "</span>";
  }

  function shareTag(mode) {
    return mode === "full"
      ? '<span class="ko-tag full">Detail terbuka</span>'
      : '<span class="ko-tag summary">Ringkasan</span>';
  }

  function card(c, opts) {
    opts = opts || {};
    var mine = !!opts.mine;
    var actions = [];
    if (c.can_edit) {
      actions.push('<a class="btn primary mini" href="' + esc(c.operate_href) + '">Kelola Posko</a>');
    }
    actions.push('<a class="btn ghost mini" href="' + esc(c.detail_href) + '">Lihat detail</a>');

    return (
      '<article class="ko-posko-card' + (mine ? " is-mine" : "") + '">' +
      '<div class="rn-row">' +
        (c.can_edit ? '<span class="ko-tag edit">Bisa dikelola</span>' : '<span class="ko-tag view">Hanya-lihat</span>') +
        shareTag(c.share_mode) +
      "</div>" +
      "<h4>" + esc(c.title) + "</h4>" +
      '<div class="ko-posko-meta">' + esc(typeLabel(c.posko_type)) + " · " + esc(c.city_name || "-") + "</div>" +
      '<div class="rn-row">' + statusChip(c.operational_status) + "</div>" +
      '<div class="ko-card-actions">' + actions.join("") + "</div>" +
      "</article>"
    );
  }

  function setBrand(brand) {
    if (!brand) return;
    var shell = $("#koShell");
    if (shell && brand.accent) shell.style.setProperty("--ko-accent", brand.accent);
    var initial = $("#koInitial");
    if (initial) {
      if (brand.logo) {
        initial.innerHTML = '<img src="' + esc(brand.logo) + '" alt="" '
          + 'style="width:100%;height:100%;object-fit:cover;border-radius:inherit">';
        initial.style.background = "transparent";
        initial.hidden = false;
      } else if (brand.initial) {
        initial.textContent = brand.initial;
        initial.hidden = false;
      }
    }
    if (brand.title) {
      $("#koTitleText").textContent = brand.title;
      document.title = "Rescue-Net | Koordinasi " + brand.title;
    }
  }

  function showNotice(title, text, loginHref, ccHref) {
    $("#koNoticeTitle").textContent = title;
    $("#koNoticeText").textContent = text;
    if (loginHref) $("#koLoginBtn").href = loginHref;
    $("#koLoginBtn").hidden = !loginHref;
    if (ccHref) { $("#koNoticeCc").href = ccHref; $("#koFootCc").href = ccHref; }
    $("#koNoticeWrap").hidden = false;
  }

  function render(d) {
    var ev = getEvent();
    var ccHref = d.control_centre_href || ("war-room.html?event=" + ev);
    $("#koCcLink").href = ccHref;
    $("#koNoticeCc").href = ccHref;
    $("#koFootCc").href = ccHref;

    if (!d.logged_in) {
      $("#koStatus").textContent = "Belum masuk.";
      showNotice(
        "Masuk sebagai anggota organisasi",
        "Halaman ini untuk anggota organisasi yang terdaftar (mis. Komunitas Landrover). "
        + "Masuk dulu, atau lihat gambaran publik lintas organisasi di Control Centre.",
        d.login_href || window.RN_FRAPPE.loginUrl(), ccHref
      );
      return;
    }
    if (!d.is_org_member) {
      $("#koStatus").textContent = "Akun Anda belum terhubung ke organisasi.";
      showNotice(
        "Akun belum terhubung ke organisasi",
        "Akun Anda aktif tapi belum menjadi anggota organisasi mana pun, jadi tidak ada posko organisasi untuk dikoordinasikan. "
        + "Hubungi koordinator organisasi Anda, atau lihat Control Centre.",
        null, ccHref
      );
      return;
    }

    setBrand(d.brand);
    var t = d.totals || {};
    var roleTxt = d.actor && d.actor.role ? d.actor.role.replace(/_/g, " ") : "anggota";
    $("#koStatus").textContent =
      "Masuk sebagai " + roleTxt + " · " + (t.org_posko_count || 0) + " posko organisasi · "
      + (t.editable_count || 0) + " bisa Anda kelola · " + (t.open_external_count || 0) + " posko organisasi lain terbuka.";
    $("#koUpdated").textContent = (d.brand && d.brand.title ? d.brand.title : "Organisasi") + " · Koordinasi Internal";

    // Posko Saya
    var myWrap = $("#koMyPosko");
    if (d.my_posko) {
      myWrap.innerHTML = '<div class="ko-card-grid">' + card(d.my_posko, { mine: true }) + "</div>";
    } else {
      myWrap.innerHTML =
        '<p class="ko-empty">Anda tidak memegang posko tertentu (mis. koordinator organisasi). '
        + "Semua posko di bawah ini hanya-lihat; kelola lewat operator posko masing-masing.</p>";
    }
    $("#koMyPoskoSection").hidden = false;

    // Posko Organisasi
    var org = d.my_org_poskos || [];
    $("#koOrgSectionTitle").textContent = "Posko " + (d.brand && d.brand.title ? d.brand.title : "Organisasi");
    $("#koOrgCount").textContent = org.length + " posko";
    $("#koOrgPoskos").innerHTML = org.length
      ? org.map(function (c) { return card(c); }).join("")
      : '<p class="ko-empty">Tidak ada posko lain di organisasi Anda untuk bencana ini.</p>';
    $("#koOrgSection").hidden = false;

    // Posko organisasi lain (terbuka)
    var ext = d.open_external_poskos || [];
    $("#koExtCount").textContent = ext.length + " posko";
    $("#koExtPoskos").innerHTML = ext.length
      ? ext.map(function (c) { return card(c); }).join("")
      : '<p class="ko-empty">Belum ada posko organisasi lain yang membuka detail koordinasi untuk bencana ini. '
        + "Sisanya bisa dilihat sebagai ringkasan di Control Centre.</p>";
    $("#koExtSection").hidden = false;

    $("#koFootNote").hidden = false;
  }

  async function load() {
    try {
      var d = await window.RN_FRAPPE.call(BOARD, { disaster_event: getEvent() });
      render(d || {});
    } catch (err) {
      console.error("[koordinasi organisasi]", err);
      $("#koStatus").textContent = "Gagal memuat data koordinasi organisasi.";
      showNotice(
        "Gagal memuat",
        "Tidak bisa memuat data koordinasi organisasi saat ini. Coba muat ulang, atau buka Control Centre.",
        null, "war-room.html?event=" + getEvent()
      );
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", load);
  } else {
    load();
  }
})();
