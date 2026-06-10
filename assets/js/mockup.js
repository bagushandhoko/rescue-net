const MOCKUP_ITEMS = [
  ["welcome", "Welcome", "welcome page rescue-net.png"],
  ["active-disasters", "Active Disasters", "bencana aktif.png"],
  ["war-room", "War Room", "war room.png"],
  ["organisasi-posko", "Organisasi & Posko", "organisasi & posko.png"],
  ["registrasi-verifikasi-posko", "Registrasi & Verifikasi Posko", "registrasi & verifikasi Posko.png"],
  ["posko-logistik", "Posko Logistik", "posko logistik.png"],
  ["distribusi", "Distribusi", "manajemen distribusi.png"],
  ["dapur-umum", "Dapur Umum", "dapur umum.png"],
  ["shelter", "Shelter & Akomodasi", "shelter & akomodasi.png"],
  ["search-found", "Search & Found", "search & found.png"],
  ["program-khusus", "Program Khusus", "program khusus.png"],
  ["relawan", "Relawan", "manajemen relawan.png"],
  ["alat-kerja", "Alat Kerja", "manajemen alat kerja.png"],
  ["sumber-daya", "Profil Sumber Daya", "Profil Sumber Daya.png"],
  ["evidence-centre", "Evidence Centre", "evidence centre.png"],
  ["verification-approval", "Verification & Approval", "verification & Approval.png"],
  ["komunikasi", "Alat Komunikasi", "alat komunikasi.png"],
  ["mobile", "Tampilan HP", "kompilasi tampilan HP.png"],
  ["login", "Login & Registrasi", "login & registrasi.png"]
].map(([key, title, file]) => ({
  key,
  title,
  image: `../assets/img/mockup/${file}`,
  file
}));

function getScreen() {
  const params = new URLSearchParams(window.location.search);
  return params.get("screen") || "welcome";
}

function renderMockup() {
  const activeKey = getScreen();
  const item = MOCKUP_ITEMS.find(x => x.key === activeKey) || MOCKUP_ITEMS[0];

  const nav = document.getElementById("mockNav");
  const frame = document.getElementById("mockFrame");

  if (!nav || !frame) {
    console.error("Mock-up container not found.");
    return;
  }

  nav.innerHTML = MOCKUP_ITEMS.map(x => {
    const cls = x.key === item.key ? "active" : "";
    return `<a class="${cls}" href="mockup.html?screen=${encodeURIComponent(x.key)}">${x.title}</a>`;
  }).join("");

  frame.innerHTML = `
    <img id="mockImage" src="${encodeURI(item.image)}" alt="${item.title}">
  `;

  const img = document.getElementById("mockImage");
  img.onerror = () => {
    frame.innerHTML = `
      <div class="missing">
        <div>
          <h3>Image belum ditemukan</h3>
          <p>File: <b>${item.file}</b></p>
          <p>Pastikan file ada di <b>assets/img/mockup</b>.</p>
        </div>
      </div>
    `;
  };
}


document.addEventListener("DOMContentLoaded", () => {
  const host = window.location.hostname || "";
  if (
    host.startsWith("192.") ||
    host.startsWith("10.") ||
    host.startsWith("172.") ||
    host === "localhost" ||
    host === "127.0.0.1"
  ) {
    document.body.classList.add("rn-local-access");
  }
  renderMockup();
});

