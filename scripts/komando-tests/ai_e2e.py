"""Real-login AI checks (Fase 7): login over HTTP with CSRF, a fake OpenAI-compatible
model server in-process, and the 'local' provider pointing at it."""
import http.cookiejar, http.server, json, os, sys, threading, urllib.request, urllib.error
SITE = os.environ.get("RN_SITE", "rescuenet-test.localhost")
if SITE == "osiun.localhost":
    sys.exit("DITOLAK: komando-tests tidak boleh dijalankan terhadap produksi (osiun.localhost).")
BASE = os.environ.get("RN_BASE", "http://127.0.0.1:8000")
PW = "CmdTest123"
ORG, EVENT = os.environ["AI_ORG"], os.environ["AI_EVENT"]
ok = fail = 0
HITS = []


def check(name, cond, extra=""):
    global ok, fail
    ok, fail = ok + bool(cond), fail + (not cond)
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else "  -> " + str(extra)[:300]))


class Fake(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0); body = self.rfile.read(n)
        HITS.append((self.path, self.headers.get("Authorization"), json.loads(body or b"{}")))
        out = json.dumps({"choices": [{"message": {"content": "jawaban uji"}}],
                          "usage": {"prompt_tokens": 100, "completion_tokens": 0, "total_tokens": 100}}).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out))); self.end_headers(); self.wfile.write(out)

    def log_message(self, *a):
        pass


srv = http.server.ThreadingHTTPServer(("127.0.0.1", 9999), Fake)
threading.Thread(target=srv.serve_forever, daemon=True).start()


class C:
    def __init__(self, email=None):
        self.jar = http.cookiejar.CookieJar()
        self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar)); self.csrf = None
        self.login = self._req("POST", "/api/method/login", {"usr": email, "pwd": PW})[0] if email else None
        if email and self.login == 200:
            s, m = self._req("GET", "/api/method/rescue_net.api_auth.session_info")
            self.csrf = (m or {}).get("csrf_token") if isinstance(m, dict) else None

    def _req(self, method, path, body=None):
        h = {"Accept": "application/json", "Host": SITE}
        data = None
        if body is not None:
            data = json.dumps(body).encode(); h["Content-Type"] = "application/json"
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

    def call(self, fn, **kw):
        return self._req("POST", f"/api/method/rescue_net.api_ai.{fn}", kw)


def good(r):
    return r[0] == 200


owner, member, outsider, personal = (C(f"{k}@aitest.local") for k in ("owner", "member", "outsider", "personal"))
guest = C()
check("login 4 akun uji", all(c.login == 200 for c in (owner, member, outsider, personal)),
      [c.login for c in (owner, member, outsider, personal)])
U = {k: f"{k}@aitest.local" for k in ("owner", "member", "outsider", "personal")}
URL = "http://127.0.0.1:9999/v1"

# 1. who may set up the organisation's AI
check("1. anggota biasa tidak bisa mengatur profil AI organisasi",
      member.call("save_ai_profile", level="organization", owner_id=ORG, provider="local", base_url=URL)[0] in (403, 417),
      member.call("save_ai_profile", level="organization", owner_id=ORG, provider="local", base_url=URL))
r = owner.call("save_ai_profile", level="organization", owner_id=ORG, provider="local", base_url="http://169.254.169.254/v1")
check("1. alamat metadata cloud ditolak", not good(r), r)
r = owner.call("save_ai_profile", level="organization", owner_id=ORG, provider="local", base_url=URL, daily_budget_tokens=250)
check("1. pemilik organisasi mengatur profil model lokal + anggaran 250", good(r) and r[1]["profile"]["daily_budget_tokens"] == 250, r)
check("1. orang luar tidak bisa membaca profil organisasi", outsider.call("get_ai_profile", level="organization", owner_id=ORG)[0] in (403, 417))

# 2. contexts
check("2. anggota melihat konteks organisasi", [o["id"] for o in (member.call("ai_contexts")[1] or {}).get("organizations", [])] == [ORG], member.call("ai_contexts"))
check("2. orang luar tidak melihat organisasi itu", ORG not in [o["id"] for o in (outsider.call("ai_contexts")[1] or {}).get("organizations", [])])
check("2. guest ditolak", guest.call("ai_contexts")[0] in (401, 403), guest.call("ai_contexts"))

# 3. asking
ask = lambda c, who, **kw: c.call("ask", user_id=U[who], disaster_event_id=EVENT, question="Ringkas situasi", **kw)
r = ask(member, "member", organization_id=ORG)
check("3. anggota bertanya dengan konteks organisasi -> jawaban dari model lokal", good(r) and r[1]["answer"] == "jawaban uji", r)
check("3. permintaan sampai ke server model lokal tanpa header Authorization", HITS and HITS[-1][1] is None and HITS[-1][0].endswith("/chat/completions"), HITS[-1:] )
check("3. anggota tanpa key pribadi: konteks pribadi ditolak", not good(ask(member, "member")), ask(member, "member"))
check("3. orang luar tidak bisa memakai AI organisasi lain", ask(outsider, "outsider", organization_id=ORG)[0] in (403, 417))
check("3. tidak bisa bertanya atas nama orang lain", ask(member, "owner", organization_id=ORG)[0] in (403, 417))
check("3. guest tidak bisa bertanya", guest.call("ask", user_id=U["member"], disaster_event_id=EVENT, question="x")[0] in (401, 403))

# 4. budget
ask(member, "member", organization_id=ORG)  # 200
r = ask(owner, "owner", organization_id=ORG)  # 300 >= 250
check("4. panggilan ke-3 masih lewat (batas diperiksa sebelum panggilan)", good(r), r)
n = len(HITS)
r = ask(member, "member", organization_id=ORG)
check("4. anggaran harian habis -> ditolak dengan pesan jelas", not good(r) and "Anggaran" in str(r[1]), r)
check("4. panggilan yang ditolak tidak sampai ke model", len(HITS) == n)
s = owner.call("ai_usage_summary", organization_id=ORG)
check("4. admin melihat pemakaian 300 dari 250", good(s) and s[1]["budget"]["daily_used"] == 300 and s[1]["budget"]["daily_limit"] == 250, s)
check("4. anggota biasa tidak melihat ringkasan organisasi", member.call("ai_usage_summary", organization_id=ORG)[0] in (403, 417))

# 5. kill switch
owner.call("save_ai_profile", level="organization", owner_id=ORG, provider="local", base_url=URL, status="disabled")
r = ask(member, "member", organization_id=ORG)
check("5. profil dinonaktifkan -> AI organisasi mati", not good(r) and "dinonaktifkan" in str(r[1]), r)

print(f"\n{ok} lulus, {fail} gagal"); sys.exit(1 if fail else 0)
