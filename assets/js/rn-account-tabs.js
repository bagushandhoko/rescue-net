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
  byId("account-tab-organisasi").hidden = !(session.manages_org || session.is_system_manager);
  byId("account-tab-admin").hidden = !session.is_system_manager;
  tablist.hidden = false;
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
      (Object.hasOwn(legacy, hash) ? legacy[hash] : (fromChat ? "ai" : "akun"));
    const wanted = byId("account-tab-" + requested);
    const active = wanted && !wanted.hidden ? wanted : tabs[0];
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
    byId("accountSettingsPosko").hidden = true;
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
