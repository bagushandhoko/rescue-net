(async function () {
  "use strict";

  const tablist = document.querySelector(".rn-account-tabs");
  const tabs = Array.from(tablist.querySelectorAll('[role="tab"]'));
  const session = await window.RNAccount.session();
  if (!session?.user || session.user === "Guest") {
    document.getElementById("accountSettingsLogin").hidden = false;
    return;
  }
  const byId = id => document.getElementById(id);
  // owner 2026-11-24: Pengaturan dipisah 3 — Akun (pribadi), Organisasi (pengelola org), Sistem RN (super admin).
  // Satu halaman, ?bagian=akun|organisasi|sistem; tautan lama (#tab=admin, #orgKeySection, ...) diarahkan otomatis.
  const SECTIONS = {
    akun: { tabs: ["akun", "ai"], title: "Pengaturan Akun", eyebrow: "Akun pribadi" },
    organisasi: { tabs: ["organisasi"], title: "Pengaturan Organisasi", eyebrow: "Pengelola organisasi" },
    sistem: { tabs: ["admin"], title: "Pengaturan Sistem RN", eyebrow: "Super admin" }
  };
  const params = new URLSearchParams(location.search);
  const rawHash = location.hash.slice(1);
  const legacyBagian = { "tab=admin": "sistem", platformKeySection: "sistem", "tab=organisasi": "organisasi", orgKeySection: "organisasi" };
  let bagian = params.get("bagian") || legacyBagian[rawHash] || "akun";
  const allowed = {
    akun: true,
    organisasi: !!(session.manages_org || session.is_system_manager),
    sistem: !!session.is_system_manager
  };
  if (!SECTIONS[bagian]) bagian = "akun";
  let deniedNote = false;
  if (!allowed[bagian]) {
    deniedNote = true;
    const note = byId("accountSettingsPosko");
    note.textContent = bagian === "sistem" ? "Pengaturan Sistem RN hanya untuk super admin." : "Pengaturan Organisasi hanya untuk pengelola organisasi.";
    note.hidden = false;
    bagian = "akun";
  }
  const sec = SECTIONS[bagian];
  document.body.dataset.rnSettings = bagian;
  document.title = sec.title + " | Rescue-Net";
  document.querySelectorAll(".topbar h2, .rn-page-mobile-title").forEach(el => { el.textContent = sec.title; });
  const eb = document.querySelector(".topbar .eyebrow"); if (eb) eb.textContent = sec.eyebrow;
  // Kunci AI organisasi pindah ke Pengaturan Organisasi
  const orgKey = byId("orgKeySection");
  if (orgKey && bagian === "organisasi") byId("account-panel-organisasi").prepend(orgKey);
  tabs.forEach(tab => { tab.hidden = !sec.tabs.includes(tab.id.slice("account-tab-".length)); });
  tablist.hidden = sec.tabs.length < 2;
  if (bagian === "sistem" && window.RNDonVerify) window.RNDonVerify.load();
  const fromChat = new URLSearchParams(location.search).get("from") === "ai-chat";
  if (fromChat) byId("aiFromChat").hidden = false;

  const legacy = {
    changePasswordForm: "akun",
    twofaSection: "akun",
    aiKeySection: "ai",
    orgKeySection: "ai",
    platformKeySection: "admin"
  };

  function readHash() {
    const hash = location.hash.slice(1);
    const requested = hash.startsWith("tab=") ? hash.slice(4) :
      (Object.hasOwn(legacy, hash) ? legacy[hash] : (fromChat ? "ai" : sec.tabs[0]));
    const wanted = byId("account-tab-" + requested);
    const active = wanted && !wanted.hidden ? wanted : byId("account-tab-" + sec.tabs[0]);
    tabs.forEach(tab => {
      const selected = tab === active;
      tab.setAttribute("aria-selected", String(selected));
      tab.tabIndex = selected ? 0 : -1;
      byId(tab.getAttribute("aria-controls")).hidden = !selected;
    });
    const tabBounds = active.getBoundingClientRect();
    const listBounds = tablist.getBoundingClientRect();
    tablist.scrollLeft += Math.max(0, tabBounds.right - listBounds.right) +
      Math.min(0, tabBounds.left - listBounds.left);
    if (deniedNote) deniedNote = false; else byId("accountSettingsPosko").hidden = true;
    if (Object.hasOwn(legacy, hash) && requested === active.id.slice("account-tab-".length)) {
      byId(hash)?.scrollIntoView({ block: "nearest" });
    }
    if (hash === "poskoEventsPanel") openPoskoSettings();
  }

  async function openPoskoSettings() {
    const href = await window.RNAccount.poskoSettingsHref();
    if (location.hash !== "#poskoEventsPanel") return;
    if (href) {
      const target = new URL(href, location.href);
      target.searchParams.set("tab", "bencana");
      location.replace(target);
    } else {
      const status = byId("accountSettingsPosko");
      status.textContent = "Pengaturan Posko tersedia untuk pengelola posko.";
      status.hidden = false;
    }
  }

  tabs.forEach(tab => {
    tab.addEventListener("click", () => {
      location.hash = "tab=" + tab.id.slice("account-tab-".length);
    });
    tab.addEventListener("keydown", event => {
      const visible = tabs.filter(button => !button.hidden);
      const index = visible.indexOf(tab);
      const next = {
        ArrowLeft: visible[(index + visible.length - 1) % visible.length],
        ArrowRight: visible[(index + 1) % visible.length],
        Home: visible[0],
        End: visible[visible.length - 1]
      }[event.key];
      if (!next) return;
      event.preventDefault();
      next.click();
      next.focus();
    });
  });
  window.addEventListener("hashchange", readHash);
  readHash();
})();
