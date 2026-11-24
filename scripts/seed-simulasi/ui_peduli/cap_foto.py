"""Beri cap 'FOTO AI · SIMULASI' + keterangan pada foto AI (pollinations FLUX). python cap_foto.py <dir_foto> <dir_keluar>"""
import base64, os, sys
from playwright.sync_api import sync_playwright
SRC, OUT = sys.argv[1], sys.argv[2]
CAP = {"cover": "Rencana: sekolah darurat semi-permanen Kalianda", "kondisi": "Kondisi awal: gedung tertutup abu, siswa di tenda",
       "pondasi": "Progres 18 Nov: pondasi & sloof", "rangka": "Progres 24 Nov: kolom & rangka atap baja"}
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 1280, "height": 760})
    for k, cap in CAP.items():
        img = base64.b64encode(open(os.path.join(SRC, k + ".jpg"), "rb").read()).decode()
        pg.set_content(f"""<body style="margin:0;font-family:Arial"><div style="position:relative;width:1280px;height:760px;overflow:hidden">
<img src="data:image/jpeg;base64,{img}" style="width:1280px;height:760px;object-fit:cover;display:block">
<div style="position:absolute;top:16px;left:16px;background:#c62828;color:#fff;font-weight:bold;font-size:22px;padding:7px 14px;border-radius:6px">FOTO AI · SIMULASI</div>
<div style="position:absolute;left:0;right:0;bottom:0;background:linear-gradient(transparent,rgba(0,0,0,.7));color:#fff;font-size:24px;font-weight:bold;padding:40px 18px 16px">{cap}<div style="font-size:15px;font-weight:normal;opacity:.9">Gambar buatan AI untuk simulasi Rescue-Net — bukan foto lapangan asli</div></div></div></body>""")
        pg.wait_for_timeout(200); pg.screenshot(path=os.path.join(OUT, f"foto-ai-{k}.jpg"), type="jpeg", quality=86); print(k)
    b.close()
