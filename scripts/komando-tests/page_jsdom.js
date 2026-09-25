// Browserless test of the Komando Pusat page: the page's real JS + real HTML run in jsdom,
// RN_FRAPPE.call goes to the LIVE API with real logged-in sessions (cookie jars).
const http = require("http");
const fs = require("fs");
const { JSDOM } = require("jsdom");

const WEB = "/volume1/web/rescue-net";
const PW = "CmdTest123";
let ok = 0, fail = 0;
const check = (n, c, x = "") => { c ? ok++ : fail++; console.log((c ? "PASS " : "FAIL ") + n + (c ? "" : "  -> " + JSON.stringify(x).slice(0, 400))); };
process.on("unhandledRejection", (e) => { if (!/getElementById|closed/.test(String(e && e.message))) { console.error("UNHANDLED", e); process.exit(3); } });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// ---------- HTTP with cookie jar (mirrors the browser session) ----------
function makeSession() {
  const jar = {};
  const req = (method, path, body) => new Promise((resolve, reject) => {
    const data = body ? body.toString() : null;
    const headers = { Host: "osiun.localhost", Accept: "application/json", Cookie: Object.entries(jar).map(([k, v]) => k + "=" + v).join("; ") };
    if (data) { headers["Content-Type"] = "application/x-www-form-urlencoded"; headers["Content-Length"] = Buffer.byteLength(data); }
    const r = http.request({ host: "127.0.0.1", port: 8095, path, method, headers }, (res) => {
      (res.headers["set-cookie"] || []).forEach((c) => { const [kv] = c.split(";"); const i = kv.indexOf("="); jar[kv.slice(0, i)] = kv.slice(i + 1); });
      let t = ""; res.on("data", (d) => (t += d)); res.on("end", () => resolve({ status: res.statusCode, text: t }));
    });
    r.on("error", reject); r.setTimeout(120000, () => r.destroy(new Error("timeout"))); if (data) r.write(data); r.end();
  });
  return { jar, req };
}
async function login(email, pw = PW) {
  const s = makeSession();
  const r = await s.req("POST", "/api/method/login", new URLSearchParams({ usr: email, pwd: pw }));
  s.loginStatus = r.status;
  return s;
}
function encodeArgs(args = {}) { // same rules as assets/js/rn-frappe-client.js
  const p = new URLSearchParams();
  Object.entries(args).forEach(([k, v]) => { if (v === undefined || v === null || v === "") return; p.set(k, typeof v === "object" ? JSON.stringify(v) : String(v)); });
  return p;
}
// RN_FRAPPE.call equivalent bound to a session
function clientFor(session, log) {
  return {
    call: async (method, args = {}, options = {}) => {
      const post = String(options.method || "GET").toUpperCase() !== "GET";
      const params = encodeArgs(args);
      const r = post ? await session.req("POST", "/api/method/" + method, params) : await session.req("GET", "/api/method/" + method + (params.toString() ? "?" + params : ""));
      if (log) log.push({ method, args, status: r.status });
      let j = {}; try { j = JSON.parse(r.text); } catch (_) { throw new Error("non-JSON " + r.status); }
      if (r.status >= 400) {
        let m = "";
        try { m = JSON.parse(j._server_messages || "[]").map((x) => JSON.parse(x).message).join(" "); } catch (_) { /* ignore */ }
        throw new Error(m || (j.exception || "").split(":").slice(1).join(":").trim() || "HTTP " + r.status);
      }
      return j.message;
    }
  };
}

// ---------- open the page in jsdom ----------
function openPage(htmlFile, scripts, session, opts = {}) {
  const html = fs.readFileSync(WEB + "/pages/" + htmlFile, "utf8").replace(/<script[\s\S]*?<\/script>/g, "");
  const dom = new JSDOM(html, { runScripts: "outside-only", url: "http://127.0.0.1/rescue-net/pages/" + htmlFile, pretendToBeVisual: true });
  const w = dom.window;
  w.calls = [];
  w.RN_FRAPPE = clientFor(session, w.calls);
  w.confirm = () => true;
  w.prompt = () => (opts.promptText === undefined ? "Rotasi tugas" : opts.promptText);
  Object.defineProperty(w.navigator, "clipboard", { value: { writeText: async () => {} }, configurable: true });
  for (const s of scripts) w.eval(fs.readFileSync(WEB + "/assets/js/" + s, "utf8"));
  // jsdom fires DOMContentLoaded itself while the document is still "loading"; only fire it by hand if it already passed.
  if (w.document.readyState !== "loading") w.document.dispatchEvent(new w.Event("DOMContentLoaded", { bubbles: true }));
  return w;
}
async function until(fn, ms = 60000, label = "") {
  const t0 = Date.now();
  while (Date.now() - t0 < ms) { try { if (await fn()) return true; } catch (_) { /* keep waiting */ } await sleep(150); }
  return false;
}
const text = (w, id) => (w.document.getElementById(id) ? w.document.getElementById(id).textContent : "");
const hidden = (w, id) => w.document.getElementById(id).hidden;

(async () => {
  // ================= A. tamu =================
  const guest = makeSession();
  let w = openPage("komando-pusat.html", ["komando-pusat.js"], guest);
  await until(() => !hidden(w, "kpNotice"));
  check("A tamu: halaman minta masuk, data pusat tersembunyi", !hidden(w, "kpNotice") && hidden(w, "kpCenterView"), text(w, "kpStatus"));
  check("A tamu: tombol Masuk tampil", !hidden(w, "kpNotice") && !w.document.getElementById("kpLoginBtn").hidden);
  w.close();

  // ================= B. form pendaftaran organisasi (org-posko.js) =================
  const pusat = await login("pusat@cmdtest.local");
  check("login pusat", pusat.loginStatus === 200, pusat.loginStatus);
  w = openPage("organisasi-posko.html", ["org-posko.js"], pusat);
  await sleep(1500);
  const form = w.document.querySelector("form[data-rn-create-org]");
  const orgMsg = () => (w.document.querySelector("[data-rn-org-message]") || {}).textContent || "";
  check("B form org: ada pilihan skema mandiri(default)/terpusat", !!form && form.elements.coordination_scheme.length === 2 && form.querySelector("input[value=mandiri]").checked);
  form.elements.name.value = "[UJI-KOMANDO] Pusat JS";
  form.elements.organization_type.value = "government";
  form.querySelector("input[value=terpusat]").checked = true;
  w.calls.length = 0;
  form.dispatchEvent(new w.Event("submit", { bubbles: true, cancelable: true }));
  await until(() => w.calls.some((c) => c.method.endsWith("create_organization")));
  const created = w.calls.find((c) => c.method.endsWith("create_organization"));
  check("B form org: nama terbaca (bug form.title diperbaiki) & skema terpusat terkirim", created && created.args.title === "[UJI-KOMANDO] Pusat JS" && created.args.coordination_scheme === "terpusat" && created.status === 200, created);
  await until(() => /komando terpusat tersimpan/i.test(orgMsg()), 30000);
  check("B form org: pesan sukses tampil DI FORM (super admin -> Komando Pusat)", /Organisasi komando terpusat tersimpan.*Komando Pusat/.test(orgMsg()), orgMsg());
  w.close();

  const c = clientFor(pusat);
  const orgs = await c.call("rescue_net.api_community_cluster.list_organizations");
  const org = orgs.find((o) => o.title === "[UJI-KOMANDO] Pusat JS");
  check("B organisasi terdaftar", !!org);
  const posko = await c.call("rescue_net.api_community_cluster.create_posko", { title: "[UJI-KOMANDO] Posko JS", posko_type: "logistics", address: "Jl. JS 1", organization: org.name }, { method: "POST" });
  const pid = posko.posko;
  check("B pusat membuat posko langsung", !!pid && !posko.pending, posko);

  // ================= C. halaman pusat =================
  w = openPage("komando-pusat.html", ["komando-pusat.js"], pusat);
  await until(() => !hidden(w, "kpCenterView"));
  check("C judul memuat nama pusat", /Pusat JS/.test(text(w, "kpTitle")), text(w, "kpTitle"));
  check("C tabel struktur memuat posko", /Posko JS/.test(text(w, "kpOrgTable")));
  check("C KPI tampil (4 kartu)", w.document.querySelectorAll("#kpKpis .kp-kpi").length === 4);
  check("C peran akun dimuat (4 peran)", w.document.querySelectorAll("#kpAccRole option").length === 4);
  const f = w.document.getElementById("kpAccountForm");
  check("C dropdown posko terisi posko organisasi terpilih", [...w.document.querySelectorAll("#kpAccPosko option")].some((o) => /Posko JS/.test(o.textContent)));

  // password tak sama -> ditolak di klien, API tak dipanggil
  f.elements.full_name.value = "Operator JS"; f.elements.email.value = "opjs@cmdtest.local"; f.elements.posko.value = pid;
  f.elements.password.value = "Abcdef123"; f.elements.password2.value = "Beda12345";
  w.calls.length = 0;
  f.dispatchEvent(new w.Event("submit", { bubbles: true, cancelable: true }));
  await sleep(300);
  check("C konfirmasi password tak sama ditolak di klien (tanpa panggilan API)", /Konfirmasi password tidak sama/.test(text(w, "kpAccMsg")) && !w.calls.some((x) => x.method.endsWith("create_command_account")), text(w, "kpAccMsg"));
  // operator tanpa posko ditolak di klien
  f.elements.password.value = ""; f.elements.password2.value = ""; f.elements.posko.value = "";
  f.dispatchEvent(new w.Event("submit", { bubbles: true, cancelable: true }));
  await sleep(300);
  check("C akun operator tanpa posko ditolak di klien", /Pilih posko/.test(text(w, "kpAccMsg")), text(w, "kpAccMsg"));
  // valid, tanpa password -> password sementara
  f.elements.posko.value = pid;
  f.dispatchEvent(new w.Event("submit", { bubbles: true, cancelable: true }));
  await until(() => !hidden(w, "kpSecret"));
  const tmp = text(w, "kpSecretPw").trim();
  check("C buat akun: password sementara tampil sekali", tmp.length >= 10 && /opjs@cmdtest.local/.test(text(w, "kpSecretEmail")), tmp);
  await until(() => /Operator JS/.test(text(w, "kpAccTable")));
  check("C akun baru muncul di tabel akun (Operator posko)", /Operator JS/.test(text(w, "kpAccTable")) && /Operator posko/.test(text(w, "kpAccTable")));
  check("C pemilik pusat tampil 'Pemilik (super admin)' tanpa tombol kelola", /Pemilik \(super admin\)/.test(text(w, "kpAccTable")));
  w.document.getElementById("kpSecretClose").click();
  check("C tombol Tutup menghapus password dari layar", hidden(w, "kpSecret") && text(w, "kpSecretPw") === "");
  w.close();

  // ================= D. operator level bawah =================
  const op = await login("opjs@cmdtest.local", tmp);
  check("D operator login dgn password sementara", op.loginStatus === 200, op.loginStatus);
  const oc = clientFor(op);
  const r1 = await oc.call("rescue_net.api_community_cluster.update_posko", { posko: pid, title: "[UJI-KOMANDO] Posko JS Ganti", notes: "op" }, { method: "POST" });
  const r2 = await oc.call("rescue_net.api_community_cluster.update_posko", { posko: pid, address: "Jl. Ganti 2" }, { method: "POST" });
  check("D perubahan struktural operator = permintaan (pending)", r1.pending && r2.pending, [r1, r2]);
  w = openPage("komando-pusat.html", ["komando-pusat.js"], op);
  await until(() => !hidden(w, "kpNotice") && !hidden(w, "kpMineWrap"));
  check("D operator: pesan 'bukan pengelola pusat' + permintaan sendiri tampil (Menunggu)", /bukan pengelola pusat/i.test(text(w, "kpNoticeTitle")) && /Menunggu/.test(text(w, "kpMineTable")) && hidden(w, "kpCenterView"), [text(w, "kpNoticeTitle"), text(w, "kpMineTable").slice(0, 100)]);
  w.close();

  // ================= E. pusat memutuskan =================
  w = openPage("komando-pusat.html", ["komando-pusat.js"], pusat);
  await until(() => w.document.querySelectorAll("#kpPending .kp-req").length === 2);
  check("E antrean: 2 permintaan", w.document.querySelectorAll("#kpPending .kp-req").length === 2 && /2 menunggu/.test(text(w, "kpBadge")), text(w, "kpBadge"));
  let req = w.document.querySelector("#kpPending .kp-req");
  w.calls.length = 0;
  req.querySelector("[data-decide=reject]").click();
  await sleep(400);
  check("E tolak tanpa alasan: tidak memanggil API, kolom catatan diminta", !w.calls.some((x) => x.method.endsWith("decide_command_request")) && /wajib/i.test(req.querySelector("input").placeholder), req.querySelector("input").placeholder);
  req.querySelector("input").value = "Nama posko sudah baku.";
  req.querySelector("[data-decide=reject]").click();
  await until(() => w.document.querySelectorAll("#kpPending .kp-req").length === 1);
  check("E ditolak dgn alasan -> antrean tinggal 1", w.document.querySelectorAll("#kpPending .kp-req").length === 1);
  w.document.querySelector("#kpPending .kp-req [data-decide=approve]").click();
  await until(() => w.document.querySelectorAll("#kpPending .kp-req").length === 0);
  await until(() => /Diterapkan/.test(text(w, "kpHistTable")) && /Ditolak/.test(text(w, "kpHistTable")));
  const hist = text(w, "kpHistTable");
  check("E riwayat: Ditolak (dgn alasan) & Diterapkan", /Ditolak/.test(hist) && /Diterapkan/.test(hist) && /Nama posko sudah baku/.test(hist), hist.slice(0, 200));
  const st = (await c.call("rescue_net.api_community_cluster.get_posko_settings", { posko: pid })).posko;
  check("E hanya permintaan yang disetujui yang berlaku", (st.title === "[UJI-KOMANDO] Posko JS" && st.address === "Jl. Ganti 2") || (st.title === "[UJI-KOMANDO] Posko JS Ganti" && st.address === "Jl. JS 1"), [st.title, st.address]);

  // ================= F. kelola akun =================
  w.document.querySelector("#kpAccTable [data-accact=suspend]").click();
  await until(() => /suspended/i.test(text(w, "kpAccTable")));
  check("F akun dinonaktifkan (status tampil)", /suspended/i.test(text(w, "kpAccTable")));
  const blocked = await login("opjs@cmdtest.local", tmp);
  check("F akun nonaktif tak bisa login", blocked.loginStatus !== 200, blocked.loginStatus);
  w.document.querySelector("#kpAccTable [data-accact=activate]").click();
  await until(() => !/suspended/i.test(text(w, "kpAccTable")));
  check("F akun diaktifkan kembali", (await login("opjs@cmdtest.local", tmp)).loginStatus === 200);
  w.document.querySelector("#kpAccTable [data-accact=reset]").click();
  await until(() => !hidden(w, "kpSecret"));
  const newPw = text(w, "kpSecretPw").trim();
  check("F reset password: pw baru tampil; pw lama mati, pw baru hidup", newPw.length >= 10 && (await login("opjs@cmdtest.local", tmp)).loginStatus !== 200 && (await login("opjs@cmdtest.local", newPw)).loginStatus === 200, newPw);
  w.close();

  // ================= G. wakil pusat + info notifikasi WA =================
  const wk = await c.call("rescue_net.api_command.create_command_account", { organization: org.name, full_name: "Wakil JS", email: "wakiljs@cmdtest.local", role: "community_coordinator", phone: "081234500009" }, { method: "POST" });
  w = openPage("komando-pusat.html", ["komando-pusat.js"], pusat);
  await until(() => /Wakil JS/.test(text(w, "kpAccTable")));
  check("G info notifikasi: pemilik tanpa nomor HP disebut, belum ada penerima", /belum ada penerima/.test(text(w, "kpNotifyInfo")) && /Tanpa nomor HP/.test(text(w, "kpNotifyInfo")), text(w, "kpNotifyInfo"));
  const wkRow = () => [...w.document.querySelectorAll("#kpAccTable tbody tr")].find((tr) => /Wakil JS/.test(tr.textContent));
  check("G pemilik melihat tombol 'Jadikan wakil pusat' untuk anggota pusat", !!wkRow().querySelector("[data-accact=deputy-on]"));
  check("G pemilik tak punya tombol wakil/kelola pada barisnya sendiri", ![...w.document.querySelectorAll("#kpAccTable tbody tr")].find((tr) => /Pemilik \(super admin\)/.test(tr.textContent)).querySelector("button"));
  wkRow().querySelector("[data-accact=deputy-on]").click();
  await until(() => /Wakil pusat/.test(wkRow().textContent));
  check("G diangkat: baris menampilkan 'Wakil pusat' + tombol Cabut wakil", /Wakil pusat/.test(wkRow().textContent) && !!wkRow().querySelector("[data-accact=deputy-off]") && !wkRow().querySelector("[data-accact=deputy-on]"));
  check("G info notifikasi kini memuat wakil bernomor HP", /Wakil JS \(wakil\)/.test(text(w, "kpNotifyInfo")), text(w, "kpNotifyInfo"));
  w.close();

  const wakilSess = await login("wakiljs@cmdtest.local", wk.temporary_password);
  check("G wakil login", wakilSess.loginStatus === 200, wakilSess.loginStatus);
  w = openPage("komando-pusat.html", ["komando-pusat.js"], wakilSess);
  await until(() => !hidden(w, "kpCenterView"));
  check("G wakil membuka halaman pusat (panel pusat tampil, bukan pesan 'bukan pengelola')", !hidden(w, "kpCenterView") && hidden(w, "kpNotice"), text(w, "kpNoticeTitle"));
  await until(() => /Pemilik \(super admin\)/.test(text(w, "kpAccTable")));
  check("G wakil TIDAK melihat tombol angkat/cabut wakil", !w.document.querySelector("#kpAccTable [data-accact^=deputy]"));
  const ownerRow = [...w.document.querySelectorAll("#kpAccTable tbody tr")].find((tr) => /Pemilik \(super admin\)/.test(tr.textContent));
  check("G wakil tak bisa mengelola akun pemilik", !ownerRow.querySelector("button"));
  const selfRow = [...w.document.querySelectorAll("#kpAccTable tbody tr")].find((tr) => /Wakil JS/.test(tr.textContent));
  check("G wakil tak punya tombol kelola pada wakil lain/dirinya (hanya pemilik)", !selfRow.querySelector("button"));
  w.close();

  // ================= H. panel skema koordinasi (System Manager) =================
  w = openPage("komando-pusat.html", ["komando-pusat.js"], pusat);
  await until(() => !hidden(w, "kpCenterView"));
  await sleep(1500);
  check("H bukan System Manager: panel skema tersembunyi", hidden(w, "kpSchemeAdmin"));
  w.close();
  const smSess = await login("sm@cmdtest.local");
  check("H System Manager login", smSess.loginStatus === 200, smSess.loginStatus);
  w = openPage("komando-pusat.html", ["komando-pusat.js"], smSess);
  await until(() => !hidden(w, "kpSchemeAdmin") && /UJI-KOMANDO/.test(text(w, "kpSchemeTable")));
  const orgRow = () => [...w.document.querySelectorAll("#kpSchemeTable tbody tr")].find((tr) => tr.textContent.indexOf(org.title) !== -1);
  check("H SM: panel skema tampil, org uji = Komando terpusat", !!orgRow() && /Komando terpusat/.test(orgRow().textContent), text(w, "kpSchemeTable").slice(0, 300));
  w.prompt = () => "";
  orgRow().querySelector("[data-scheme-to]") && orgRow().querySelector("[data-scheme-to]").click();
  await sleep(800);
  check("H SM: tanpa alasan tidak ada perubahan", /Komando terpusat/.test(orgRow().textContent));
  const btn = orgRow().querySelector("[data-scheme-to]");
  if (btn) {
    w.prompt = () => "uji jsdom";
    btn.click();
    await until(() => /Mandiri/.test(orgRow().textContent) || /menunggu/i.test(text(w, "kpSchemeMsg")));
    check("H SM: ubah ke mandiri lewat UI", /Mandiri/.test(orgRow().textContent), text(w, "kpSchemeMsg"));
    w.prompt = () => "uji jsdom kembali";
    orgRow().querySelector("[data-scheme-to]").click();
    await until(() => /Komando terpusat/.test(orgRow().textContent));
    check("H SM: kembalikan ke terpusat lewat UI", /Komando terpusat/.test(orgRow().textContent));
  } else {
    check("H SM: tombol ubah tersedia (tidak ada permintaan menunggu)", false, orgRow().textContent);
  }
  w.close();

  console.log(`ok=${ok} fail=${fail}`);
  process.exit(fail ? 1 : 0);
})().catch((e) => { console.error("CRASH", e); process.exit(2); });
