"""Real-login checks for flows that were only bench/unit tested: Search & Found operator actions, Program Khusus
plan, Sistem Verifikasi (endorse/revoke/overview/badges), AI suggestion decisions, Laporan Masyarakat queue +
reporter_contact. HTTP + CSRF + cookie jar against `bench serve` on the TEST stack. Seed: setup_flows_users.py."""
import http.cookiejar
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

SITE = os.environ.get("RN_SITE", "rescuenet-test.localhost")
if SITE == "osiun.localhost":
    sys.exit("DITOLAK: komando-tests tidak boleh dijalankan terhadap produksi (osiun.localhost).")
BASE = os.environ.get("RN_BASE", "http://127.0.0.1:8000")
PW = "CmdTest123"
I = json.load(open("/tmp/flows_ids.json"))
S = I["sentinels"]
ok = fail = 0


def check(name, cond, extra=""):
    global ok, fail
    ok, fail = ok + bool(cond), fail + (not cond)
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else "  -> " + str(extra)[:300]))


class C:
    def __init__(self, email=None):
        self.jar = http.cookiejar.CookieJar()
        self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
        self.csrf = None
        self.login = self._req("POST", "/api/method/login", {"usr": email, "pwd": PW})[0] if email else None
        if email and self.login == 200:
            s, m = self._req("GET", "/api/method/rescue_net.api_auth.session_info")
            self.csrf = (m or {}).get("csrf_token") if isinstance(m, dict) else None

    def _req(self, method, path, body=None):
        h = {"Accept": "application/json", "Host": SITE}
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            h["Content-Type"] = "application/json"
        if self.csrf:
            h["X-Frappe-CSRF-Token"] = self.csrf
        try:
            r = self.op.open(urllib.request.Request(BASE + path, data=data, method=method, headers=h), timeout=90)
            t, s = r.read().decode(), r.status
        except urllib.error.HTTPError as e:
            t, s = e.read().decode(), e.code
        try:
            j = json.loads(t)
        except Exception:
            return s, t[:300]
        if s == 200:
            return s, j.get("message", j)
        msg = ""
        try:
            msg = " ".join(json.loads(m).get("message", "") for m in json.loads(j.get("_server_messages", "[]")))
        except Exception:
            pass
        return s, (msg or j.get("exception", "") or t[:200])

    def post(self, fn, **kw):
        return self._req("POST", "/api/method/rescue_net." + fn, kw)

    def get(self, fn, **kw):
        q = urllib.parse.urlencode({k: v for k, v in kw.items() if v is not None})
        return self._req("GET", "/api/method/rescue_net." + fn + ("?" + q if q else ""))


good = lambda r: r[0] == 200
denied = lambda r: r[0] == 403          # logged in but not allowed: must be a real PermissionError
gdenied = lambda r: r[0] in (401, 403)  # guest
dump = lambda r: json.dumps(r[1], ensure_ascii=False)
KEYS = ("sm", "opa", "opb", "ver", "ver2", "vsus", "plain", "reporter", "cc")
U = {k: C(f"{k}@flowtest.local") for k in KEYS}
guest = C()
check("login 9 akun uji", all(c.login == 200 for c in U.values()), {k: c.login for k, c in U.items()})
sm, opa, opb, ver, ver2, vsus, plain, reporter, cc = (U[k] for k in KEYS)
EV, PA, PB, ACC = I["event"], I["posko_a"], I["posko_b"], I["acc"]
SENT_ALL = [S["missing_name"], S["found_name"], S["claimant"], S["claimant_contact"], S["rep_phone"], S["rep_email"], S["rep_name"]]
leaks = lambda r, words=SENT_ALL: [w for w in words if w in dump(r)]

# ---------------------------------------------------------------- 1. Search & Found
print("--- 1. Search & Found")
SF = "api_search_found."
r = opa.post(SF + "create_claim", item_description="Koper hitam UJI", kind="barang", disaster_event=EV, posko=PA,
             claimant_name="Pengklaim Uji", claimant_contact="081200000001")
check("1. operator posko A membuat klaim di posko A", good(r) and r[1]["status"] == "menunggu_verifikasi", r)
new_claim = r[1]["claim"] if good(r) else None
check("1. operator posko B tidak bisa membuat klaim di posko A", denied(opb.post(SF + "create_claim", item_description="x", posko=PA, disaster_event=EV)))
check("1. user biasa tidak bisa membuat klaim di posko A", denied(plain.post(SF + "create_claim", item_description="x", posko=PA, disaster_event=EV)))
check("1. guest tidak bisa membuat klaim", gdenied(guest.post(SF + "create_claim", item_description="x", posko=PA, disaster_event=EV)))
r = opa.post(SF + "create_claim", item_description="  ", posko=PA, disaster_event=EV)
check("1. deskripsi kosong ditolak", not good(r), r)

C1 = I["claim"]
check("1. operator A: menunggu_verifikasi -> terverifikasi", good(opa.post(SF + "update_claim_status", claim=C1, new_status="terverifikasi")))
check("1. loncat status ditolak (terverifikasi -> selesai)", not good(opa.post(SF + "update_claim_status", claim=C1, new_status="selesai")))
check("1. operator B tidak bisa mengubah klaim posko A", denied(opb.post(SF + "update_claim_status", claim=C1, new_status="siap_diserahkan")))
check("1. user biasa tidak bisa mengubah status klaim", denied(plain.post(SF + "update_claim_status", claim=C1, new_status="siap_diserahkan")))
check("1. guest tidak bisa mengubah status klaim", gdenied(guest.post(SF + "update_claim_status", claim=C1, new_status="siap_diserahkan")))
check("1. System Manager boleh mengubah status klaim", good(sm.post(SF + "update_claim_status", claim=C1, new_status="siap_diserahkan")))

F1, M1 = I["found"], I["missing"]
check("1. operator A set_identification_status", good(opa.post(SF + "set_identification_status", found_report=F1, new_status="proses_identifikasi")))
check("1. status identifikasi tidak valid ditolak", not good(opa.post(SF + "set_identification_status", found_report=F1, new_status="ngawur")))
check("1. operator B ditolak set_identification_status", denied(opb.post(SF + "set_identification_status", found_report=F1, new_status="teridentifikasi")))
check("1. user biasa ditolak set_identification_status", denied(plain.post(SF + "set_identification_status", found_report=F1, new_status="teridentifikasi")))
check("1. guest ditolak set_identification_status", gdenied(guest.post(SF + "set_identification_status", found_report=F1, new_status="teridentifikasi")))
r = opa.post(SF + "restricted_record", doctype="RN Found Person Report", name=F1)
check("1. operator A membuka restricted_record (nama + kontak pelapor)", good(r) and r[1]["person_name"] == S["found_name"], r)
check("1. operator B ditolak restricted_record", denied(opb.post(SF + "restricted_record", doctype="RN Found Person Report", name=F1)))
check("1. user biasa ditolak restricted_record", denied(plain.post(SF + "restricted_record", doctype="RN Missing Person Report", name=M1)))
check("1. guest ditolak restricted_record", gdenied(guest.post(SF + "restricted_record", doctype="RN Missing Person Report", name=M1)))

for who, c in (("guest", guest), ("user biasa", plain), ("operator B", opb), ("verifikator", ver)):
    r = c.get(SF + "dashboard", disaster_event=EV)
    check(f"1. dashboard untuk {who}: 200 dan tanpa nama/telepon/email/kontak pengklaim", good(r) and not leaks(r), (r[0], leaks(r)))
r = opa.get(SF + "dashboard", disaster_event=EV)
check("1. dashboard untuk operator A tidak membawa nama orang (hanya restricted_record)",
      good(r) and not leaks(r, [S["missing_name"], S["found_name"]]), leaks(r, [S["missing_name"], S["found_name"]]))
check("1. control_centre_search_found: cc & SM boleh, user biasa/operator ditolak, guest ditolak",
      good(cc.get(SF + "control_centre_search_found")) and good(sm.get(SF + "control_centre_search_found"))
      and denied(plain.get(SF + "control_centre_search_found")) and denied(opb.get(SF + "control_centre_search_found"))
      and gdenied(guest.get(SF + "control_centre_search_found")))
r = cc.get(SF + "control_centre_search_found")
check("1. ringkasan Control Centre tanpa nama", good(r) and not leaks(r), leaks(r))

# ---------------------------------------------------------------- 2. Program Khusus plan
print("--- 2. Program Khusus Rencana Kerja")
DP = "api_donor_program."
PG, MS = I["program"], I["milestone"]
r = opa.post(DP + "save_plan_item", donor_program=PG, item_type="milestone", values={"title": "Tahap 2 uji", "milestone_status": "berjalan", "progress_percent": 20})
check("2. pemilik (operator posko A) menambah milestone", good(r), r)
ms2 = r[1]["name"] if good(r) else None
check("2. pemilik mengubah milestone", ms2 and good(opa.post(DP + "save_plan_item", donor_program=PG, item_type="milestone", name=ms2, values={"progress_percent": 60})))
check("2. pemilik menambah lokasi dan kebutuhan", good(opa.post(DP + "save_plan_item", donor_program=PG, item_type="location", values={"title": "Lokasi uji", "latitude": -6.2, "longitude": 106.8}))
      and good(opa.post(DP + "save_plan_item", donor_program=PG, item_type="need", values={"item": "Panel surya", "kind": "material", "qty_needed": 10, "qty_available": 2, "unit": "unit"})))
check("2. jenis item tak dikenal ditolak", not good(opa.post(DP + "save_plan_item", donor_program=PG, item_type="aneh", values={})))
check("2. milestone progres 100 saat belum selesai ditolak", not good(opa.post(DP + "save_plan_item", donor_program=PG, item_type="milestone", name=ms2, values={"milestone_status": "berjalan", "progress_percent": 100})))
for who, c in (("operator B", opb), ("user biasa", plain), ("verifikator", ver), ("pelapor", reporter)):
    check(f"2. {who} ditolak save_plan_item", denied(c.post(DP + "save_plan_item", donor_program=PG, item_type="milestone", values={"title": "x"})))
    check(f"2. {who} ditolak delete_plan_item", denied(c.post(DP + "delete_plan_item", donor_program=PG, item_type="milestone", name=MS)))
    check(f"2. {who} ditolak set_output_verification", denied(c.post(DP + "set_output_verification", donor_program=PG, status="terverifikasi", output_verified=3)))
check("2. guest ditolak save/delete/set_output", gdenied(guest.post(DP + "save_plan_item", donor_program=PG, item_type="milestone", values={"title": "x"}))
      and gdenied(guest.post(DP + "delete_plan_item", donor_program=PG, item_type="milestone", name=MS))
      and gdenied(guest.post(DP + "set_output_verification", donor_program=PG, status="terverifikasi")))
check("2. Control Centre dan System Manager boleh mengedit rencana",
      good(cc.post(DP + "save_plan_item", donor_program=PG, item_type="milestone", values={"title": "Oleh CC"}))
      and good(sm.post(DP + "save_plan_item", donor_program=PG, item_type="milestone", values={"title": "Oleh SM"})))
# cross-program: B owns its own program; A may not touch B's items through A's program id
r = opb.post(DP + "create_program", disaster_event=EV, program_name="[UJI-FLOW] Program B", owner_type="posko", owner_id=PB)
check("2. operator B membuat program miliknya", good(r), r)
pg_b = (r[1].get("program") or r[1].get("name")) if good(r) and isinstance(r[1], dict) else None
r = opb.post(DP + "save_plan_item", donor_program=pg_b, item_type="milestone", values={"title": "Milik B"}) if pg_b else (0, "no program")
ms_b = r[1]["name"] if good(r) else None
check("2. operator B menambah milestone di program B", bool(ms_b), r)
check("2. operator A tidak bisa mengubah item program B lewat id program A", ms_b and denied(opa.post(DP + "save_plan_item", donor_program=PG, item_type="milestone", name=ms_b, values={"title": "bajak"})))
check("2. operator A tidak bisa menghapus item program B lewat id program A", ms_b and denied(opa.post(DP + "delete_plan_item", donor_program=PG, item_type="milestone", name=ms_b)))
check("2. operator A tidak bisa mengedit program B", pg_b and denied(opa.post(DP + "save_plan_item", donor_program=pg_b, item_type="milestone", values={"title": "x"})))
check("2. hapus item: pemilik boleh", ms2 and good(opa.post(DP + "delete_plan_item", donor_program=PG, item_type="milestone", name=ms2)))
check("2. hapus item yang sudah hilang gagal", ms2 and not good(opa.post(DP + "delete_plan_item", donor_program=PG, item_type="milestone", name=ms2)))
r = opa.post(DP + "set_output_verification", donor_program=PG, status="dalam_proses", output_verified=6, output_target=12)
check("2. pemilik mencatat output 6 dari 12", good(r) and r[1]["output_verified"] == 6, r)
check("2. output terverifikasi > target ditolak", not good(opa.post(DP + "set_output_verification", donor_program=PG, output_verified=99)))
check("2. output negatif ditolak", not good(opa.post(DP + "set_output_verification", donor_program=PG, output_target=-1)))
check("2. status output tak valid ditolak", not good(opa.post(DP + "set_output_verification", donor_program=PG, status="ngawur")))

# ---------------------------------------------------------------- 3. Sistem Verifikasi
print("--- 3. Sistem Verifikasi")
VF = "api_verifier."
REP = ACC["reporter"]
STMT = "PERNYATAAN-SENTINEL kenal langsung sejak 2015"
check("3. verifikator aktif tanpa pernyataan ditolak", not good(ver.post(VF + "endorse_reporter", user_account=REP, statement="")))
check("3. pernyataan terlalu pendek ditolak", not good(ver.post(VF + "endorse_reporter", user_account=REP, statement="kenal")))
check("3. network_vouch tanpa 'via' ditolak", not good(ver.post(VF + "endorse_reporter", user_account=REP, method="network_vouch", statement=STMT)))
check("3. akun target tidak ada ditolak", not good(ver.post(VF + "endorse_reporter", user_account="TIDAK-ADA", statement=STMT)))
check("3. tidak bisa memverifikasi diri sendiri", denied(ver.post(VF + "endorse_reporter", user_account=ACC["ver"], statement=STMT)))
check("3. user biasa ditolak endorse_reporter", denied(plain.post(VF + "endorse_reporter", user_account=REP, statement=STMT)))
check("3. verifikator ditangguhkan ditolak", denied(vsus.post(VF + "endorse_reporter", user_account=REP, statement=STMT)))
check("3. System Manager (bukan verifikator) ditolak endorse_reporter", denied(sm.post(VF + "endorse_reporter", user_account=REP, statement=STMT)))
check("3. guest ditolak endorse_reporter", gdenied(guest.post(VF + "endorse_reporter", user_account=REP, statement=STMT)))
r = ver.post(VF + "endorse_reporter", user_account=REP, statement=STMT)
check("3. verifikator aktif 1 memverifikasi pelapor", good(r), r)
end1 = r[1]["endorsement"] if good(r) else None
check("3. sekali per verifikator (kedua kali ditolak)", not good(ver.post(VF + "endorse_reporter", user_account=REP, statement=STMT)))


def overview(c, **kw):
    r = c.get(VF + "endorsements_overview", target_type="reporter", **kw)
    return r, {x["endorsement"]: x for x in (r[1]["rows"] if good(r) else [])}


def rep_row(c):
    r = c.get("api_frontend_bridge.community_reports", disaster_event=EV)
    return r, next((x for x in (r[1] if good(r) else []) if x["name"] == I["rep_consent"]), None)


r, rows = overview(guest)
check("3. guest: ringkasan terbuka, pelapor anonim, tanpa pernyataan/ID target/can_revoke",
      good(r) and end1 in rows and rows[end1]["target"] == "Pelapor" and rows[end1]["statement"] is None
      and rows[end1]["target_id"] is None and not rows[end1]["can_revoke"] and not r[1]["privileged"], r)
check("3. guest: tidak ada kebocoran nama/HP/email/pernyataan", not leaks(r, SENT_ALL + ["PERNYATAAN-SENTINEL", REP]), leaks(r, SENT_ALL + ["PERNYATAAN-SENTINEL", REP]))
r, rows = overview(plain)
check("3. user biasa: pernyataan disembunyikan, tak bisa mencabut", good(r) and rows[end1]["statement"] is None and not rows[end1]["can_revoke"] and not r[1]["privileged"], r)
r, rows = overview(guest, q="PERNYATAAN-SENTINEL")
check("3. guest tidak bisa mencari lewat isi pernyataan (q)", good(r) and r[1]["total"] == 0, r)
r, rows = overview(ver)
check("3. verifikator pemilik: lihat pernyataan + can_revoke", good(r) and rows[end1]["statement"] == STMT and rows[end1]["can_revoke"] and r[1]["privileged"], r)
r, rows = overview(ver2)
check("3. verifikator lain: lihat pernyataan tapi tidak can_revoke", good(r) and rows[end1]["statement"] == STMT and not rows[end1]["can_revoke"], r)
r, rows = overview(sm)
check("3. System Manager: can_revoke", good(r) and rows[end1]["can_revoke"], r)
r, row = rep_row(guest)
check("3. daftar laporan publik: lencana pelapor community_verified (1 verifikator), nama anonim",
      good(r) and row and row["reporter_verification_status"] == "community_verified" and row["reporter_verified_count"] == 1
      and row["reporter_name"] == "Pelapor" and row["can_contact_reporter"] is False, row)
check("3. daftar laporan publik: tanpa pernyataan, HP, email, nama pelapor, akun pelapor",
      good(r) and not leaks(r, SENT_ALL + ["PERNYATAAN-SENTINEL", REP]), leaks(r, SENT_ALL + ["PERNYATAAN-SENTINEL", REP]))
check("3. daftar publik memuat nama verifikator (publik) tanpa field statement",
      row and row["reporter_verifiers"] and "statement" not in row["reporter_verifiers"][0]
      and any(v["verifier"] == "Verifikator ver" for v in row["reporter_verifiers"]), row and row["reporter_verifiers"])
r = ver2.post(VF + "endorse_reporter", user_account=REP, method="network_vouch", vouched_via="Pak RT", statement=STMT + " (2)")
end2 = r[1]["endorsement"] if good(r) else None
check("3. verifikator aktif 2 memverifikasi", good(r), r)
r, row = rep_row(guest)
check("3. dua verifikator -> official_verified", row and row["reporter_verification_status"] == "official_verified" and row["reporter_verified_count"] == 2, row)
check("3. user biasa ditolak revoke_endorsement", denied(plain.post(VF + "revoke_endorsement", endorsement=end1, reason="x")))
check("3. verifikator lain ditolak mencabut endorsement orang lain", denied(ver2.post(VF + "revoke_endorsement", endorsement=end1, reason="x")))
check("3. verifikator ditangguhkan ditolak mencabut", denied(vsus.post(VF + "revoke_endorsement", endorsement=end1, reason="x")))
check("3. guest ditolak revoke_endorsement", gdenied(guest.post(VF + "revoke_endorsement", endorsement=end1, reason="x")))
check("3. pelapor sendiri ditolak mencabut", denied(reporter.post(VF + "revoke_endorsement", endorsement=end1, reason="x")))
r, row = rep_row(guest)
check("3. percobaan cabut yang ditolak tidak mengubah lencana", row and row["reporter_verified_count"] == 2, row)
check("3. verifikator pemilik mencabut endorsement-nya", good(ver.post(VF + "revoke_endorsement", endorsement=end1, reason="salah orang")))
r, row = rep_row(guest)
check("3. setelah dicabut: community_verified (1 tersisa)", row and row["reporter_verification_status"] == "community_verified" and row["reporter_verified_count"] == 1, row)
r, rows = overview(sm, status="revoked")
check("3. System Manager melihat endorsement yang dicabut", good(r) and end1 in rows and rows[end1]["status"] == "revoked", r)
r2 = ver.post(VF + "revoke_endorsement", endorsement=end1, reason="dicabut lagi")
check("3. mencabut dua kali ditolak (jejak pencabutan tidak ditimpa)", not good(r2), r2)
check("3. System Manager mencabut endorsement verifikator lain", good(sm.post(VF + "revoke_endorsement", endorsement=end2, reason="admin")))
r, row = rep_row(guest)
check("3. semua dicabut -> self_reported", row and row["reporter_verification_status"] == "self_reported" and row["reporter_verified_count"] == 0, row)

# ---------------------------------------------------------------- 4. AI suggestions
print("--- 4. Saran AI")
AI = "api_ai."
names = lambda r: sorted(x["name"] for x in r[1]) if good(r) else None
SA, SR, SB, SB2 = I["sug_accept"], I["sug_reject"], I["sug_b"], I["sug_b2"]
check("4. operator A hanya melihat saran posko A", names(opa.get(AI + "list_ai_suggestions")) == sorted([SA, SR]), opa.get(AI + "list_ai_suggestions"))
check("4. operator B hanya melihat saran posko B", names(opb.get(AI + "list_ai_suggestions")) == sorted([SB, SB2]), names(opb.get(AI + "list_ai_suggestions")))
check("4. user biasa/verifikator/pelapor tidak melihat saran apa pun", all(names(c.get(AI + "list_ai_suggestions")) == [] for c in (plain, ver, reporter)))
check("4. guest ditolak list_ai_suggestions", gdenied(guest.get(AI + "list_ai_suggestions")))
check("4. Control Centre dan SM melihat keempatnya", all(set([SA, SR, SB, SB2]) <= set(names(c.get(AI + "list_ai_suggestions")) or []) for c in (cc, sm)))
for who, c in (("user biasa", plain), ("operator B", opb), ("pelapor", reporter), ("verifikator", ver)):
    check(f"4. {who} ditolak menerima saran posko A", denied(c.post(AI + "decide_ai_suggestion", suggestion=SA, decision="accepted")))
check("4. guest ditolak memutuskan saran", gdenied(guest.post(AI + "decide_ai_suggestion", suggestion=SA, decision="accepted")))
check("4. keputusan tak valid ditolak", not good(opa.post(AI + "decide_ai_suggestion", suggestion=SA, decision="mungkin")))
r, row = rep_row(opa)
check("4. sebelum diterima: jumlah terdampak 10", row and row["affected_people_count"] == 10, row)
r = opa.post(AI + "decide_ai_suggestion", suggestion=SA, decision="accepted")
check("4. operator A menerima saran -> field diterapkan", good(r) and r[1]["applied"].get("affected_people_count") == 55, r)
r, row = rep_row(opa)
check("4. laporan berubah (55, ai_applied)", row and row["affected_people_count"] == 55 and row["ai_status"] == "ai_applied", row)
check("4. saran hanya diputuskan sekali", not good(opa.post(AI + "decide_ai_suggestion", suggestion=SA, decision="rejected")))
r = opa.post(AI + "decide_ai_suggestion", suggestion=SR, decision="rejected")
check("4. operator A menolak saran -> tak ada field diterapkan", good(r) and r[1]["applied"] == {}, r)
check("4. operator A ditolak memutuskan saran posko B", denied(opa.post(AI + "decide_ai_suggestion", suggestion=SB, decision="accepted")))
check("4. Control Centre menerima saran posko B", good(cc.post(AI + "decide_ai_suggestion", suggestion=SB, decision="accepted")))
check("4. System Manager menolak saran lain", good(sm.post(AI + "decide_ai_suggestion", suggestion=SB2, decision="rejected")))

# ---------------------------------------------------------------- 5. Laporan Masyarakat queue + reporter_contact
print("--- 5. Laporan Masyarakat: antrian + Hubungi pelapor")
RC, RN_, RNP, RB = I["rep_consent"], I["rep_noconsent"], I["rep_noposko"], I["rep_b"]
rep_ids = (RC, RN_, RNP, RB)
for who, c, expect in (("operator A", opa, {RC: True, RN_: True, RNP: False, RB: False}),
                       ("operator B", opb, {RC: False, RN_: False, RNP: False, RB: True}),
                       ("user biasa", plain, dict.fromkeys(rep_ids, False)), ("guest", guest, dict.fromkeys(rep_ids, False)),
                       ("verifikator aktif", ver, dict.fromkeys(rep_ids, True)), ("verifikator ditangguhkan", vsus, dict.fromkeys(rep_ids, False)),
                       ("System Manager", sm, dict.fromkeys(rep_ids, True))):
    r = c.get("api_frontend_bridge.community_reports", disaster_event=EV)
    rows = {x["name"]: x for x in r[1]} if good(r) else {}
    got = {k: rows.get(k, {}).get("can_contact_reporter") for k in rep_ids}
    check(f"5. antrian untuk {who}: can_contact_reporter benar", good(r) and got == expect, got)
    check(f"5. antrian untuk {who}: tanpa HP/email pelapor dan nama sesuai hak",
          good(r) and not leaks(r, [S["rep_phone"], S["rep_email"]]) and all(
              "reporter_phone" not in x and "reporter_email" not in x for x in rows.values())
          and all((x["reporter_name"] == S["rep_name"]) == expect[k] for k, x in rows.items() if k in rep_ids),
          (leaks(r, [S["rep_phone"], S["rep_email"]]), {k: x["reporter_name"] for k, x in rows.items()}))


def n_audit(report):
    r = sm._req("GET", "/api/method/frappe.client.get_count?doctype=RN%20Verification%20Action&filters=" +
                urllib.parse.quote(json.dumps({"object_id": report, "action_type": "view_reporter_contact"})))
    return r[1] if good(r) else None


RCN = "api_reports.reporter_contact"
base = n_audit(RC)
check("5. bisa membaca log RN Verification Action sebagai SM", isinstance(base, int), base)
r = opa.post(RCN, report=RC)
check("5. operator A membuka kontak: telepon + email + WhatsApp + level verifikasi",
      good(r) and r[1]["phone"] == S["rep_phone"] and r[1]["email"] == S["rep_email"] and r[1]["whatsapp_url"].startswith("https://wa.me/62")
      and "status" in r[1]["verification"], r)
check("5. pembukaan oleh operator tercatat", n_audit(RC) == base + 1, (base, n_audit(RC)))
r = ver.post(RCN, report=RC)
check("5. verifikator aktif boleh membuka kontak", good(r) and r[1]["phone"] == S["rep_phone"] and r[1]["viewer_is_verifier"], r)
check("5. pembukaan verifikator tercatat", n_audit(RC) == base + 2, n_audit(RC))
check("5. System Manager boleh membuka kontak", good(sm.post(RCN, report=RC)))
check("5. 3 pembukaan sah -> 3 baris log", n_audit(RC) == base + 3, n_audit(RC))
before = n_audit(RC)
for who, c in (("operator B", opb), ("user biasa", plain), ("verifikator ditangguhkan", vsus), ("pelapor sendiri", reporter)):
    check(f"5. {who} ditolak membuka kontak", denied(c.post(RCN, report=RC)))
check("5. guest ditolak membuka kontak", gdenied(guest.post(RCN, report=RC)))
check("5. pembukaan yang ditolak tidak dicatat sebagai pembukaan", n_audit(RC) == before, (before, n_audit(RC)))
r = opa.post(RCN, report=RN_)
check("5. tanpa persetujuan pelapor: tak ada HP/email, alasan jelas",
      good(r) and r[1]["phone"] is None and r[1]["email"] is None and r[1]["whatsapp_url"] is None and "tidak bersedia" in (r[1]["reason_no_contact"] or ""), r)
check("5. laporan tanpa posko: operator A ditolak", denied(opa.post(RCN, report=RNP)))
check("5. laporan tanpa posko: verifikator & SM boleh", good(ver.post(RCN, report=RNP)) and good(sm.post(RCN, report=RNP)))
check("5. laporan posko B: operator A ditolak, operator B boleh", denied(opa.post(RCN, report=RB)) and good(opb.post(RCN, report=RB)))
check("5. laporan tidak ada -> bukan 200", not good(ver.post(RCN, report="TIDAK-ADA")))

# status / convert actions behind the queue's buttons
SC = "api_frontend_bridge.set_community_report_status"
for who, c in (("user biasa", plain), ("operator B (posko lain)", opb), ("pelapor", reporter)):
    check(f"5. {who} ditolak mengubah status laporan posko A", denied(c.post(SC, report=RC, status="verified")))
    check(f"5. {who} ditolak mengonversi laporan posko A", denied(c.post("api_frontend_bridge.convert_community_report", report=RC)))
check("5. guest ditolak mengubah status laporan", gdenied(guest.post(SC, report=RC, status="verified")))
check("5. operator A boleh mengubah status laporan posko A", good(opa.post(SC, report=RC, status="verified")))
check("5. System Manager boleh mengubah status laporan", good(sm.post(SC, report=RN_, status="verified")))

print(f"\n{ok} lulus, {fail} gagal")
sys.exit(1 if fail else 0)
