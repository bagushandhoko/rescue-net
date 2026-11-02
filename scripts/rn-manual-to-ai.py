#!/usr/bin/env python3
"""Turn pages/manual.html (Manual Pengguna) into plain text for the AI assistant
(frappe_shadow/apps/rescue_net/rescue_net/ai/manual_pengguna.txt). Run after editing the manual:
    python3 scripts/rn-manual-to-ai.py
The backend cannot read pages/ (served by the web container), so the text ships with the app."""
import html, os, re

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
s = open(os.path.join(root, "pages/manual.html"), encoding="utf-8").read()
s = re.sub(r"(?s)<script.*?</script>|<style.*?</style>|<nav.*?</nav>|<header.*?</header>|<footer.*?</footer>", "", s)
s = re.sub(r"(?i)</(p|li|h[1-6]|tr|div|section)>", "\n", s)
t = html.unescape(re.sub(r"<[^>]+>", " ", s))
t = re.sub(r"[ \t]+", " ", t)
lines = [l.strip() for l in t.splitlines()]
t = "\n".join(l for l in lines if l and l not in ("← Kembali", "Kembali ke halaman sebelumnya", "Beranda"))
out = os.path.join(root, "frappe_shadow/apps/rescue_net/rescue_net/ai/manual_pengguna.txt")
open(out, "w", encoding="utf-8").write("SUMBER: pages/manual.html (Manual Pengguna Rescue-Net)\n" + t + "\n")
print(out, len(t), "huruf")
