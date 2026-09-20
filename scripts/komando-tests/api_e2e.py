import http.cookiejar, json, urllib.request, urllib.error
BASE = "http://127.0.0.1:8095"
PW = "CmdTest123"
ok = fail = 0
def check(name, cond, extra=""):
    global ok, fail
    if cond: ok += 1
    else: fail += 1
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else "  -> " + str(extra)[:400]))

class C:
    def __init__(self, email=None, pw=PW):
        self.jar = http.cookiejar.CookieJar(); self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar)); self.csrf = None
        self.login_status = self._req("POST", "/api/method/login", {"usr": email, "pwd": pw})[0] if email else None
        if email and self.login_status == 200:
            s, m = self._req("GET", "/api/method/rescue_net.api_auth.session_info")
            self.csrf = (m or {}).get("csrf_token") if isinstance(m, dict) else None
    def _req(self, method, path, body=None):
        h = {"Accept": "application/json", "Host": "osiun.localhost"}
        data = None
        if body is not None: data = json.dumps(body).encode(); h["Content-Type"] = "application/json"
        if self.csrf: h["X-Frappe-CSRF-Token"] = self.csrf
        try:
            r = self.op.open(urllib.request.Request(BASE + path, data=data, method=method, headers=h), timeout=90)
            t = r.read().decode(); s = r.status
        except urllib.error.HTTPError as e:
            t = e.read().decode(); s = e.code
        try: j = json.loads(t)
        except Exception: return s, t[:300]
        if s == 200: return s, j.get("message", j)
        msg = ""
        try: msg = " ".join(json.loads(m).get("message", "") for m in json.loads(j.get("_server_messages", "[]")))
        except Exception: pass
        return s, (msg or j.get("exception", "") or t[:200])
    def call(self, mod, fn, **kw): return self._req("POST", f"/api/method/rescue_net.{mod}.{fn}", kw)

def ok_(r): return r[0] == 200
pusat, sub, out, man = C("pusat@cmdtest.local"), C("sub@cmdtest.local"), C("out@cmdtest.local"), C("man@cmdtest.local")
check("login 4 akun uji", all(c.login_status == 200 for c in (pusat, sub, out, man)), [c.login_status for c in (pusat, sub, out, man)])

# ---------- 1. pusat mendaftar dgn skema terpusat ----------
r = pusat.call("api_community_cluster", "create_organization", title="[UJI-KOMANDO] Pusat Korem", organization_type="government", coordination_scheme="terpusat")
check("1. pusat mendaftar skema terpusat", ok_(r) and r[1]["coordination_scheme"] == "terpusat", r)
P = r[1]["organization"] if ok_(r) else None
r = pusat.call("api_command", "command_status", organization=P)
check("1. pusat = super admin (command owner) organisasinya", ok_(r) and r[1]["is_command_owner"] and r[1]["scheme"] == "terpusat" and P in r[1]["owned_centers"], r)
bad = pusat.call("api_community_cluster", "create_organization", title="[UJI-KOMANDO] X", coordination_scheme="rahasia")
check("1. skema tidak valid ditolak", not ok_(bad), bad)

# ---------- 2. pusat: posko sendiri langsung jadi; akun dibuat pusat ----------
r = pusat.call("api_community_cluster", "create_posko", title="[UJI-KOMANDO] Posko Alfa", posko_type="logistics", address="Jl. Uji 1", organization=P)
check("2. pusat membuat posko langsung (tanpa persetujuan)", ok_(r) and r[1].get("posko") and not r[1].get("pending"), r)
A = r[1]["posko"] if ok_(r) else None
r = pusat.call("api_command", "create_command_account", organization=P, full_name="Operator Alfa", email="alfa@cmdtest.local", posko=A, role="posko_operator")
check("2. pusat membuat akun operator posko", ok_(r) and r[1].get("temporary_password"), r)
TEMP = r[1]["temporary_password"] if ok_(r) else "x"; ALFA_ACC = r[1].get("user_account") if ok_(r) else None
dup = pusat.call("api_command", "create_command_account", organization=P, full_name="Dup", email="alfa@cmdtest.local", posko=A)
check("2. email ganda ditolak", not ok_(dup), dup)
alfa = C("alfa@cmdtest.local", TEMP)
check("2. operator login dgn password sementara", alfa.login_status == 200, alfa.login_status)
noposko = pusat.call("api_command", "create_command_account", organization=P, full_name="Tanpa Posko", email="np@cmdtest.local", role="posko_operator")
check("2. akun operator wajib punya posko", not ok_(noposko), noposko)

# ---------- 3. tak bisa daftar sendiri ke organisasi komando ----------
r = out.call("api_community_cluster", "request_membership", organization=P)
check("3. orang luar tak bisa mendaftar sendiri ke org komando", not ok_(r) and "komando" in str(r[1]).lower(), r)
r = out.call("api_command", "create_command_account", organization=P, full_name="Hack", email="hack@cmdtest.local", posko=A)
check("3. orang luar tak bisa membuat akun komando", not ok_(r), r)
r = alfa.call("api_command", "create_command_account", organization=P, full_name="Hack2", email="hack2@cmdtest.local", posko=A)
check("3. operator posko tak bisa membuat akun langsung", not ok_(r), r)

# ---------- 4. operator posko: operasional langsung, struktural diajukan ----------
r = alfa.call("api_community_cluster", "update_posko", posko=A, notes="catatan operasional", operational_status="active")
check("4. operator ubah catatan/status (operasional) langsung", ok_(r) and not r[1].get("pending"), r)
# panel Pengaturan Posko mengirim SEMUA kolom tiap simpan: nilai yang tak berubah tak boleh jadi permintaan
r = alfa.call("api_community_cluster", "update_posko", posko=A, title="[UJI-KOMANDO] Posko Alfa", posko_type="logistics", address="Jl. Uji 1", public_detail="inherit", active_from="", active_until="", notes="catatan 2")
check("4. simpan tanpa perubahan struktural TIDAK membuat permintaan", ok_(r) and not r[1].get("pending"), r)
r = alfa.call("api_community_cluster", "update_posko", posko=A, title="[UJI-KOMANDO] Alfa BARU", address="Jl. Baru 9")
check("4. operator ubah judul/alamat -> diajukan ke pusat", ok_(r) and r[1].get("pending") and r[1].get("command_request"), r)
R_TITLE = r[1].get("command_request") if ok_(r) else None
r = alfa.call("api_control_centre", "set_posko_functions", posko=A, functions=["shelter"])
check("4. operator ubah fungsi posko -> diajukan", ok_(r) and r[1].get("pending"), r)
R_FUNC = r[1].get("command_request") if ok_(r) else None
r = alfa.call("api_privacy", "update_posko", posko=A, public_detail="private")
check("4. operator ubah kebijakan publik -> diajukan", ok_(r) and r[1].get("pending"), r)
R_PRIV = r[1].get("command_request") if ok_(r) else None
r = alfa.call("api_privacy", "update_posko", posko=A, public_detail="public", public_participation=1)
R_PUB = r[1].get("command_request") if ok_(r) else None
r = alfa.call("api_community_cluster", "get_posko_settings", posko=A)
check("4. sebelum disetujui: judul BELUM berubah, catatan operasional sudah", ok_(r) and r[1]["posko"].get("title") == "[UJI-KOMANDO] Posko Alfa" and r[1]["posko"].get("notes") == "catatan 2" and r[1]["posko"].get("public_detail") != "private", r)
r = out.call("api_control_centre", "set_posko_functions", posko=A, functions=["kitchen"])
check("4. orang luar tak bisa mengubah fungsi posko komando", not ok_(r), r)

# ---------- 5. pusat memutuskan ----------
r = pusat.call("api_command", "command_overview", organization=P)
check("5. ringkasan pusat: 4 permintaan menunggu, akun & posko tampil", ok_(r) and r[1]["pending_count"] == 4 and any(a["email"] == "alfa@cmdtest.local" for a in r[1]["accounts"]) and any(p["name"] == A for p in r[1]["poskos"]), r if not ok_(r) else r[1]["pending_count"])
r = alfa.call("api_command", "decide_command_request", request=R_TITLE, decision="approve")
check("5. operator tak bisa menyetujui permintaannya sendiri", not ok_(r), r)
r = out.call("api_command", "decide_command_request", request=R_TITLE, decision="approve")
check("5. orang luar tak bisa memutuskan", not ok_(r), r)
r = pusat.call("api_command", "decide_command_request", request=R_FUNC, decision="reject")
check("5. tolak tanpa alasan ditolak", not ok_(r), r)
r = pusat.call("api_command", "decide_command_request", request=R_FUNC, decision="reject", note="Fungsi posko sudah ditetapkan.")
check("5. pusat menolak dgn alasan", ok_(r) and r[1]["status"] == "rejected", r)
r = pusat.call("api_command", "decide_command_request", request=R_TITLE, decision="approve", note="ok")
check("5. pusat menyetujui perubahan judul -> diterapkan", ok_(r) and r[1]["status"] == "applied", r)
r = pusat.call("api_command", "decide_command_request", request=R_PRIV, decision="approve")
check("5. pusat menyetujui kebijakan publik -> diterapkan", ok_(r) and r[1]["status"] == "applied", r)
r = pusat.call("api_command", "decide_command_request", request=R_TITLE, decision="approve")
check("5. permintaan yang sudah diputuskan tak bisa diputuskan lagi", not ok_(r), r)
r = alfa.call("api_community_cluster", "get_posko_settings", posko=A)
check("5. judul, alamat & kebijakan baru berlaku setelah disetujui", ok_(r) and r[1]["posko"].get("title") == "[UJI-KOMANDO] Alfa BARU" and r[1]["posko"].get("address") == "Jl. Baru 9" and r[1]["posko"].get("public_detail") == "private", r)
r = pusat.call("api_command", "decide_command_request", request=R_PUB, decision="approve")
check("5. persetujuan yg melanggar aturan organisasi -> failed dgn alasan, tanpa error 500", ok_(r) and r[1]["status"] == "failed" and "Gagal" in r[1]["apply_result"], r)
r = alfa.call("api_community_cluster", "get_posko_settings", posko=A)
check("5. permintaan failed tak mengubah apa pun (tetap private)", ok_(r) and r[1]["posko"].get("public_detail") == "private", r)
r = alfa.call("api_command", "my_command_requests")
check("5. pemohon melihat status permintaannya", ok_(r) and {x["status"] for x in r[1]["requests"]} >= {"applied", "rejected"}, r)

# ---------- 6. level bawah: organisasi anak + posko + akun lewat persetujuan ----------
r = sub.call("api_community_cluster", "create_organization", title="[UJI-KOMANDO] Kodim Bawahan", organization_type="government", parent_organization=P)
check("6. org bawahan mendaftar di bawah pusat -> menunggu persetujuan pusat", ok_(r) and r[1].get("parent_link_pending"), r)
C1 = r[1]["organization"] if ok_(r) else None; LINK = r[1].get("parent_link_request") if ok_(r) else None
r = pusat.call("api_community_cluster", "decide_org_link", request=LINK, action="approve")
check("6. pusat menyetujui penautan org bawahan", ok_(r), r)
r = sub.call("api_command", "command_status", organization=C1)
check("6. org bawahan kini berada di bawah komando & butuh persetujuan", ok_(r) and r[1]["under_command"] and r[1]["needs_approval"] and not r[1]["is_command_owner"] and r[1]["command_organization"] == P, r)
r = sub.call("api_community_cluster", "create_posko", title="[UJI-KOMANDO] Posko Bravo", posko_type="medical", address="Jl. Uji 2", organization=C1)
check("6. level bawah menambah posko -> diajukan", ok_(r) and r[1].get("pending"), r)
R_NEWPOSKO = r[1].get("command_request") if ok_(r) else None
r = sub.call("api_command", "request_command_account", organization=C1, full_name="Operator Bravo", email="bravo@cmdtest.local", role="posko_operator", posko=None)
check("6. level bawah minta akun (belum ada posko) -> diajukan", ok_(r) and r[1].get("pending"), r)
R_ACC = r[1].get("command_request") if ok_(r) else None
n_before = len(pusat.call("api_command", "command_overview", organization=P)[1]["poskos"])
r = pusat.call("api_command", "decide_command_request", request=R_NEWPOSKO, decision="approve")
check("6. pusat menyetujui posko baru -> dibuat", ok_(r) and r[1]["status"] == "applied", r)
ov = pusat.call("api_command", "command_overview", organization=P)[1]
newp = [p for p in ov["poskos"] if p["title"] == "[UJI-KOMANDO] Posko Bravo"]
check("6. posko baru ada di organisasi bawahan", len(newp) == 1 and newp[0]["organization"] == C1 and len(ov["poskos"]) == n_before + 1, newp)
BRAVO = newp[0]["name"] if newp else None
# akun diajukan tanpa posko untuk operator -> gagal diterapkan dgn pesan jelas (bukan 500)
r = pusat.call("api_command", "decide_command_request", request=R_ACC, decision="approve")
check("6. permintaan akun tak valid gagal dgn status failed (tanpa error 500)", ok_(r) and r[1]["status"] == "failed", r)
r = sub.call("api_command", "request_command_account", organization=C1, full_name="Operator Bravo", email="bravo@cmdtest.local", role="posko_operator", posko=BRAVO)
R_ACC2 = r[1].get("command_request") if ok_(r) else None
r = pusat.call("api_command", "decide_command_request", request=R_ACC2, decision="approve")
check("6. akun yang diajukan dibuat saat disetujui (pw sementara ke pusat)", ok_(r) and r[1]["status"] == "applied" and r[1].get("temporary_password"), r)
bravo = C("bravo@cmdtest.local", r[1].get("temporary_password", "x")) if ok_(r) else None
check("6. operator Bravo bisa login", bravo and bravo.login_status == 200, bravo and bravo.login_status)

# ---------- 7. pusat = super admin seluruh pohon ----------
r = pusat.call("api_community_cluster", "update_posko", posko=BRAVO, title="[UJI-KOMANDO] Bravo Direvisi")
check("7. pusat langsung mengubah posko org bawahan (tanpa persetujuan)", ok_(r) and not r[1].get("pending"), r)
r = out.call("api_community_cluster", "update_posko", posko=BRAVO, title="Diretas")
check("7. orang luar tak bisa mengubah posko itu", not ok_(r), r)

# ---------- 8. kelola akun ----------
r = pusat.call("api_command", "set_command_account_active", user_account=ALFA_ACC, active=0)
check("8. nonaktifkan akun wajib beralasan", not ok_(r), r)
r = pusat.call("api_command", "set_command_account_active", user_account=ALFA_ACC, active=0, note="Rotasi tugas")
check("8. pusat menonaktifkan akun", ok_(r) and r[1]["status"] == "suspended", r)
check("8. akun nonaktif tak bisa login", C("alfa@cmdtest.local", TEMP).login_status != 200)
r = pusat.call("api_command", "set_command_account_active", user_account=ALFA_ACC, active=1)
check("8. pusat mengaktifkan kembali", ok_(r) and C("alfa@cmdtest.local", TEMP).login_status == 200, r)
r = pusat.call("api_command", "reset_command_account_password", user_account=ALFA_ACC)
NEWPW = r[1].get("temporary_password") if ok_(r) else "x"
check("8. reset password -> pw lama mati, pw baru hidup", ok_(r) and C("alfa@cmdtest.local", TEMP).login_status != 200 and C("alfa@cmdtest.local", NEWPW).login_status == 200, r)
r = out.call("api_command", "reset_command_account_password", user_account=ALFA_ACC)
check("8. orang luar tak bisa reset password akun komando", not ok_(r), r)
me = pusat.call("api_command", "command_overview", organization=P)[1]["accounts"]
pusat_acc = [a for a in me if a["email"] == "pusat@cmdtest.local"]
r = pusat.call("api_command", "reset_command_account_password", user_account=pusat_acc[0]["user_account"]) if pusat_acc else (0, "no acc")
check("8. akun pemilik/diri sendiri tak bisa dikelola lewat jalur ini", not ok_(r), r)

# ---------- 9. skema bisa diubah hanya System Manager ----------
r = pusat.call("api_command", "set_coordination_scheme", organization=P, scheme="mandiri")
check("9. pemilik tak bisa menurunkan skema sendiri", not ok_(r), r)

# ---------- 10. kontrol: organisasi MANDIRI tidak berubah ----------
r = man.call("api_community_cluster", "create_organization", title="[UJI-KOMANDO] Mandiri Biasa", organization_type="community")
check("10. org mandiri (default) terdaftar", ok_(r) and r[1]["coordination_scheme"] == "mandiri", r)
M = r[1]["organization"] if ok_(r) else None
r = man.call("api_community_cluster", "create_posko", title="[UJI-KOMANDO] Posko Mandiri", posko_type="logistics", address="Jl. M", organization=M)
check("10. posko org mandiri dibuat langsung", ok_(r) and r[1].get("posko") and not r[1].get("pending"), r)
MP = r[1]["posko"] if ok_(r) else None
r = man.call("api_community_cluster", "update_posko", posko=MP, title="[UJI-KOMANDO] Mandiri Ubah", address="Jl. M2")
check("10. ubah judul/alamat posko mandiri langsung (tanpa persetujuan)", ok_(r) and not r[1].get("pending"), r)
r = out.call("api_community_cluster", "request_membership", organization=M)
check("10. daftar anggota ke org mandiri tetap bisa (menunggu owner)", ok_(r) and not (isinstance(r[1], str)), r)
r = man.call("api_command", "command_status", organization=M)
check("10. org mandiri: tidak di bawah komando", ok_(r) and not r[1]["under_command"] and not r[1]["needs_approval"], r)
r = man.call("api_command", "command_overview")
check("10. org mandiri: bukan pusat, tak bisa buka ringkasan komando", not ok_(r), r)

# ---------- 11. wakil pusat (deputy): keputusan & pembuatan akun, tapi bukan pengangkatan wakil ----------
PH_DEP, PH_REQ = "081234500002", "081234500001"
r = pusat.call("api_command", "create_command_account", organization=P, full_name="Wakil Uji", email="wakil@cmdtest.local", role="community_coordinator", phone=PH_DEP)
check("11. pusat membuat akun calon wakil (anggota pusat)", ok_(r) and r[1].get("temporary_password"), r)
WAKIL_ACC = r[1].get("user_account") if ok_(r) else None; WAKIL_PW = r[1].get("temporary_password") if ok_(r) else "x"
wakil = C("wakil@cmdtest.local", WAKIL_PW)
r = wakil.call("api_command", "command_overview", organization=P)
check("11. sebelum diangkat: anggota biasa tak bisa buka ringkasan pusat", not ok_(r), r)
r = out.call("api_command", "set_command_deputy", organization=P, user_account=WAKIL_ACC, active=1)
check("11. orang luar tak bisa mengangkat wakil", not ok_(r), r)
r = wakil.call("api_command", "set_command_deputy", organization=P, user_account=WAKIL_ACC, active=1)
check("11. calon wakil tak bisa mengangkat dirinya sendiri", not ok_(r), r)
r = pusat.call("api_command", "set_command_deputy", organization=P, user_account=pusat_acc[0]["user_account"], active=1)
check("11. pemilik tak bisa dijadikan wakil", not ok_(r), r)
r = pusat.call("api_command", "set_command_deputy", organization=P, user_account="RN-USER-TIDAK-ADA", active=1)
check("11. akun non-anggota tak bisa dijadikan wakil", not ok_(r), r)
r = pusat.call("api_command", "set_command_deputy", organization=P, user_account=WAKIL_ACC, active=1)
check("11. pemilik mengangkat wakil", ok_(r) and r[1]["membership_role"] == "deputy", r)
r = wakil.call("api_command", "command_overview", organization=P)
check("11. wakil melihat ringkasan pusat (bukan pemilik)", ok_(r) and r[1]["viewer_is_owner"] is False, r if not ok_(r) else r[1].get("viewer_is_owner"))
check("11. daftar penerima WA memuat wakil bernomor HP", ok_(r) and any(x["role"] == "deputy" and x["has_phone"] for x in r[1]["notify_recipients"]), r if not ok_(r) else r[1]["notify_recipients"])
r = wakil.call("api_command", "command_status", organization=P)
check("11. status wakil: authority=true, owner=false", ok_(r) and r[1]["is_command_authority"] and not r[1]["is_command_owner"] and not r[1]["needs_approval"], r)
r = wakil.call("api_command", "set_command_deputy", organization=P, user_account=WAKIL_ACC, active=0)
check("11. wakil tak bisa mengangkat/mencabut wakil", not ok_(r), r)
r = wakil.call("api_command", "create_command_account", organization=P, full_name="Charlie Uji", email="charlie@cmdtest.local", posko=A, role="posko_operator", phone=PH_REQ)
check("11. wakil membuat akun langsung (tanpa pengajuan)", ok_(r) and r[1].get("temporary_password"), r)
CHARLIE_PW = r[1].get("temporary_password") if ok_(r) else "x"; CHARLIE_ACC = r[1].get("user_account") if ok_(r) else None
charlie = C("charlie@cmdtest.local", CHARLIE_PW)
r = charlie.call("api_community_cluster", "update_posko", posko=A, address="Jl. Wakil 77")
check("11. operator mengajukan ubah alamat -> permintaan menunggu", ok_(r) and r[1].get("pending"), r)
R_DEP = r[1].get("command_request") if ok_(r) else None
r = wakil.call("api_command", "decide_command_request", request=R_DEP, decision="approve", note="oke dari wakil")
check("11. wakil memutuskan permintaan -> diterapkan", ok_(r) and r[1]["status"] == "applied", r)
r = charlie.call("api_community_cluster", "get_posko_settings", posko=A)
check("11. perubahan yang disetujui wakil berlaku", ok_(r) and r[1]["posko"].get("address") == "Jl. Wakil 77", r)
r = wakil.call("api_community_cluster", "update_posko", posko=A, title="[UJI-KOMANDO] Alfa oleh Wakil")
check("11. wakil mengubah posko langsung (tanpa pengajuan)", ok_(r) and not r[1].get("pending"), r)
r = wakil.call("api_command", "set_command_account_active", user_account=pusat_acc[0]["user_account"], active=0, note="coba")
check("11. wakil tak bisa menonaktifkan pemilik", not ok_(r), r)
r = wakil.call("api_command", "set_command_account_active", user_account=WAKIL_ACC, active=0, note="coba")
check("11. wakil tak bisa menonaktifkan dirinya sendiri", not ok_(r), r)
r = wakil.call("api_command", "reset_command_account_password", user_account=CHARLIE_ACC)
check("11. wakil bisa reset password operator", ok_(r) and r[1].get("temporary_password"), r)
CHARLIE_PW = r[1].get("temporary_password") if ok_(r) else "x"
# wakil kedua: hanya pemilik yang boleh menonaktifkan/reset wakil lain
r = pusat.call("api_command", "create_command_account", organization=P, full_name="Wakil Dua", email="wakil2@cmdtest.local", role="community_coordinator")
W2_ACC = r[1].get("user_account") if ok_(r) else None
pusat.call("api_command", "set_command_deputy", organization=P, user_account=W2_ACC, active=1)
r = wakil.call("api_command", "reset_command_account_password", user_account=W2_ACC)
check("11. wakil tak bisa reset password wakil lain", not ok_(r), r)
r = pusat.call("api_command", "reset_command_account_password", user_account=W2_ACC)
check("11. pemilik bisa reset password wakil", ok_(r) and r[1].get("temporary_password"), r)
r = pusat.call("api_command", "set_command_deputy", organization=P, user_account=WAKIL_ACC, active=0)
check("11. pemilik mencabut wakil", ok_(r) and r[1]["membership_role"] == "member", r)
r = wakil.call("api_command", "decide_command_request", request=R_DEP, decision="approve")
check("11. wakil yang dicabut kehilangan kewenangan", not ok_(r), r)
r = wakil.call("api_command", "create_command_account", organization=P, full_name="Ilegal", email="ilegal@cmdtest.local", posko=A)
check("11. wakil yang dicabut tak bisa membuat akun", not ok_(r), r)
r = pusat.call("api_command", "set_command_deputy", organization=M, user_account=WAKIL_ACC, active=1)
check("11. wakil hanya bisa diangkat di org pusat (bukan mandiri)", not ok_(r), r)

# ---------- 12. set_posko_functions: sebelumnya TANPA cek izin; kini org mandiri juga dijaga ----------
r = man.call("api_control_centre", "set_posko_functions", posko=MP, functions=["kitchen"])
check("12. pembuat posko mandiri masih bisa mengubah fungsi posko", ok_(r) and not r[1].get("pending"), r)
r = out.call("api_control_centre", "set_posko_functions", posko=MP, functions=["shelter"])
check("12. orang luar TIDAK bisa mengubah fungsi posko mandiri", not ok_(r), r)
r = C().call("api_control_centre", "set_posko_functions", posko=MP, functions=["shelter"])
check("12. tamu (belum login) tak bisa mengubah fungsi posko", not ok_(r), r)

# ---------- 13. penerima WA: nomor tak valid tak boleh menggagalkan pengajuan ----------
charlie = C("charlie@cmdtest.local", CHARLIE_PW)   # reset password mematikan sesi lama
r = charlie.call("api_community_cluster", "update_posko", posko=A, address="Jl. Notif 1")
check("13. pengajuan tetap tercatat walau ada penerima WA", ok_(r) and r[1].get("pending"), r)
print("PHONES", PH_DEP, PH_REQ, "REQ_FILED", r[1].get("command_request") if ok_(r) else None, "REQ_DECIDED", R_DEP)

print(f"ok={ok} fail={fail}")
