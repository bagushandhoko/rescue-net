import os
from playwright.sync_api import sync_playwright
OUT = os.path.dirname(os.path.abspath(__file__))
W, H = 1280, 760
def base(sky1, sky2, plume=True, ash="#9b9790"):
    return f'''<defs><linearGradient id="sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{sky1}"/><stop offset="1" stop-color="{sky2}"/></linearGradient>
<linearGradient id="sea" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#5f8fa8"/><stop offset="1" stop-color="#7fa9bd"/></linearGradient>
<linearGradient id="gnd" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{ash}"/><stop offset="1" stop-color="#6d6a64"/></linearGradient>
<radialGradient id="smk"><stop offset="0" stop-color="#5b5752" stop-opacity=".9"/><stop offset="1" stop-color="#7a756e" stop-opacity="0"/></radialGradient>
<filter id="blur"><feGaussianBlur stdDeviation="3"/></filter><filter id="sh"><feDropShadow dx="6" dy="8" stdDeviation="6" flood-opacity=".28"/></filter></defs>
<rect width="{W}" height="{H}" fill="url(#sky)"/>
<rect y="300" width="{W}" height="80" fill="url(#sea)"/>
<path d="M820 330 L905 238 Q920 226 935 238 L1030 330 Z" fill="#4a4641"/><path d="M890 252 L905 238 Q920 226 935 238 L948 252 Z" fill="#2f2c29"/>
{"".join(f'<circle cx="{915+i*14}" cy="{215-i*34}" r="{22+i*13}" fill="url(#smk)" filter="url(#blur)"/>' for i in range(7)) if plume else ""}
<path d="M0 330 Q200 300 420 322 T820 318 L820 330 L0 330Z" fill="#6f7f62"/>
<rect y="372" width="{W}" height="{H-372}" fill="url(#gnd)"/>'''
def stamp(t1, t2):
    return f'''<rect width="{W}" height="48" fill="rgba(178,30,30,.93)"/><text x="20" y="32" font-size="22" font-weight="bold" fill="#fff">ILUSTRASI — SIMULASI (bukan foto asli)</text>
<rect y="{H-78}" width="{W}" height="78" fill="rgba(0,0,0,.58)"/><text x="20" y="{H-44}" font-size="27" font-weight="bold" fill="#fff">{t1}</text><text x="20" y="{H-16}" font-size="18" fill="#eee">{t2}</text>'''
def person(x, y, s=1, helm="#f2c200", shirt="#1f5fa8", child=False):
    k = .72 if child else 1
    s *= k
    return f'''<g transform="translate({x},{y}) scale({s})"><ellipse cx="0" cy="2" rx="16" ry="5" fill="rgba(0,0,0,.25)"/>
<rect x="-9" y="-46" width="8" height="46" rx="3" fill="#2b3442"/><rect x="1" y="-46" width="8" height="46" rx="3" fill="#2b3442"/>
<rect x="-13" y="-86" width="26" height="44" rx="7" fill="{shirt}"/>{"" if child else '<rect x="-13" y="-70" width="26" height="5" fill="#d9ff3c"/>'}
<circle cx="0" cy="-98" r="11" fill="#c98f62"/>{f'<path d="M-13 -100 A13 13 0 0 1 13 -100 L15 -97 L-15 -97Z" fill="{helm}"/>' if helm else '<path d="M-11 -104 A11 9 0 0 1 11 -104Z" fill="#222"/>'}</g>'''
def bldg(x0, y0, L, stage):
    """Bangunan memanjang dalam perspektif ringan: depan (sisi panjang) + sisi kanan. stage 1..4"""
    h = 120; d = 60; dx = 70; dy = -34
    g = []
    # lantai/sloof
    g.append(f'<polygon points="{x0},{y0} {x0+L},{y0} {x0+L+dx},{y0+dy} {x0+dx},{y0+dy}" fill="#b9b5ad" stroke="#6a665f"/>')
    g.append(f'<rect x="{x0}" y="{y0}" width="{L}" height="14" fill="#9d9992" stroke="#6a665f"/>')
    cols = [x0 + i*L/9 for i in range(10)]
    if stage == 1:
        for c in cols:
            g.append(f'<rect x="{c-10}" y="{y0-6}" width="20" height="20" fill="#aaa59c" stroke="#555"/>'
                     f'<line x1="{c-4}" y1="{y0-6}" x2="{c-4}" y2="{y0-40}" stroke="#7b3f1d" stroke-width="2"/><line x1="{c+4}" y1="{y0-6}" x2="{c+4}" y2="{y0-40}" stroke="#7b3f1d" stroke-width="2"/>')
            g.append(f'<rect x="{c+dx-8}" y="{y0+dy-6}" width="16" height="16" fill="#aaa59c" stroke="#555"/>')
        return "".join(g)
    if stage >= 2:
        for c in cols:
            g.append(f'<rect x="{c+dx-5}" y="{y0+dy-h}" width="9" height="{h}" fill="#7d8690"/>')
    if stage >= 3:   # dinding belakang tampak lewat bukaan
        g.append(f'<rect x="{x0}" y="{y0-h}" width="{L}" height="{h}" fill="#efe7d6" stroke="#8a8172"/>')
        g.append(f'<polygon points="{x0+L},{y0} {x0+L+dx},{y0+dy} {x0+L+dx},{y0+dy-h} {x0+L},{y0-h}" fill="#d9cfba" stroke="#8a8172"/>')
        for i in range(9):
            cx = x0 + i*L/9
            if i in (2, 6):
                g.append(f'<rect x="{cx+L/18-14}" y="{y0-92}" width="28" height="92" fill="#8a5a33" stroke="#4a3020"/>')
            else:
                g.append(f'<rect x="{cx+10}" y="{y0-96}" width="{L/9-20}" height="54" fill="#9fc6dd" stroke="#4c5a63"/>' +
                         "".join(f'<line x1="{cx+10}" y1="{y0-96+t*9}" x2="{cx+L/9-10}" y2="{y0-96+t*9}" stroke="#7aa0b5"/>' for t in range(1, 6)))
        if stage == 3:
            g.append(f'<rect x="{x0+L*0.62}" y="{y0-h}" width="{L*0.38}" height="{h}" fill="#c7c0b2" opacity=".0"/>')
    for c in cols:
        if stage >= 2:
            g.append(f'<rect x="{c-5}" y="{y0-h}" width="10" height="{h}" fill="#8f98a3" stroke="#59616b"/>')
    if stage >= 2:
        g.append(f'<rect x="{x0-4}" y="{y0-h-8}" width="{L+8}" height="9" fill="#9aa3ad" stroke="#59616b"/>')
        g.append(f'<polygon points="{x0+L},{y0-h-8} {x0+L+dx},{y0+dy-h-8} {x0+L+dx},{y0+dy-h} {x0+L},{y0-h}" fill="#8b949e"/>')
        # truss di setiap kolom (segitiga ke belakang)
        rh = 70
        tr = cols if stage == 2 else cols[:]
        for c in tr:
            g.append(f'<polyline points="{c},{y0-h-8} {c+dx/2},{y0+dy/2-h-8-rh} {c+dx},{y0+dy-h-8}" fill="none" stroke="#b7bec6" stroke-width="3"/>'
                     f'<line x1="{c+dx/2}" y1="{y0+dy/2-h-8-rh}" x2="{c+dx/2}" y2="{y0+dy/2-h-8}" stroke="#b7bec6" stroke-width="2"/>')
        g.append(f'<line x1="{x0+dx/2}" y1="{y0+dy/2-h-8-rh}" x2="{x0+L+dx/2}" y2="{y0+dy/2-h-8-rh}" stroke="#b7bec6" stroke-width="3"/>')
    if stage >= 3:
        part = 1 if stage == 4 else 0.62
        rh = 70
        X2 = x0 + L*part
        g.append(f'<polygon filter="url(#sh)" points="{x0-24},{y0-h+6} {X2+(24 if part==1 else 0)},{y0-h+6} {X2+dx/2+(10 if part==1 else 0)},{y0+dy/2-h-8-rh} {x0+dx/2-10},{y0+dy/2-h-8-rh}" fill="#5d7f8f"/>')
        g.append("".join(f'<line x1="{x0-24+i}" y1="{y0-h+6}" x2="{x0+dx/2-10+i}" y2="{y0+dy/2-h-8-rh}" stroke="#4d6d7c" stroke-width="2"/>' for i in range(0, int(L*part)+20, 12)))
        if part == 1:
            g.append(f'<polygon points="{x0+L+24},{y0-h+6} {x0+L+dx/2+10},{y0+dy/2-h-8-rh} {x0+L+dx+20},{y0+dy-h+6}" fill="#4b6876"/>')
    return "".join(g)
def tents(x, y, n, col="#2f6db3", label="KELAS DARURAT"):
    out = []
    for i in range(n):
        tx = x + i*150
        out.append(f'<g filter="url(#sh)"><polygon points="{tx},{y} {tx+65},{y-70} {tx+130},{y}" fill="{col}"/><polygon points="{tx+50},{y} {tx+65},{y-40} {tx+80},{y}" fill="#173a63"/></g>')
    out.append(f'<text x="{x+n*75}" y="{y-80}" font-size="15" fill="#fff" text-anchor="middle" style="paint-order:stroke" stroke="#173a63" stroke-width="4">{label}</text>')
    return "".join(out)
def flag(x, y):
    return f'<line x1="{x}" y1="{y}" x2="{x}" y2="{y-170}" stroke="#ddd" stroke-width="4"/><rect x="{x+2}" y="{y-170}" width="70" height="22" fill="#d71f26"/><rect x="{x+2}" y="{y-148}" width="70" height="22" fill="#fff"/>'
def svg(body):
    return f'<html><body style="margin:0"><svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" font-family="Arial, Helvetica, sans-serif">{body}</svg></body></html>'
def mixer(x, y):
    return f'<g transform="translate({x},{y})"><ellipse cx="0" cy="-36" rx="30" ry="24" fill="#e66b1f" stroke="#7a3410"/><rect x="-24" y="-18" width="48" height="12" fill="#444"/><circle cx="-18" cy="0" r="9" fill="#222"/><circle cx="18" cy="0" r="9" fill="#222"/></g>'
def pile(x, y, col, n=6):
    return "".join(f'<rect x="{x+i*6}" y="{y-i*5}" width="120" height="6" fill="{col}" stroke="#555" stroke-width=".6" transform="skewX(-20)"/>' for i in range(n))
SCENES = {
 "kondisi": svg(base("#a9a59f", "#d6d0c7", True, "#8e8a84") +
   f'<g filter="url(#sh)"><rect x="120" y="420" width="520" height="140" fill="#d8cfbd" stroke="#6a665f"/>' +
   "".join(f'<rect x="{150+i*95}" y="455" width="60" height="55" fill="#55626b"/>' for i in range(5)) +
   '<polygon points="100,425 380,340 660,425" fill="#7a5c45"/><polygon points="380,340 520,382 470,440 330,410" fill="#8e8a84"/><polygon points="300,365 420,395 360,470 260,430" fill="#3a3632"/></g>' +
   '<path d="M100 425 Q380 395 660 425 L660 432 L100 432Z" fill="#b9b4ac"/>' + "".join(f'<ellipse cx="{150+i*55}" cy="{575+(i%3)*8}" rx="40" ry="9" fill="#a8a39b"/>' for i in range(9)) +
   tents(760, 560, 3) + person(700, 640, 1.1, None, "#7d5a9e", True) + person(735, 642, 1.1, None, "#c0392b", True) + person(960, 650, 1.15, "#f2c200", "#d35400") +
   stamp("Kondisi awal: gedung SD tertutup abu, atap runtuh — siswa belajar di tenda", "Kalianda, Lampung Selatan · 2 Nov 2026 (SIMULASI)")),
 "p1": svg(base("#9cc7e6", "#e6eef2", True) + bldg(160, 560, 820, 1) + mixer(1080, 610) + pile(1010, 680, "#a87b4f") +
   person(320, 640, 1.2) + person(520, 610, 1.15, "#ffffff", "#e67e22") + person(760, 650, 1.2) + person(900, 600, 1.1, "#f2c200", "#2e86c1") +
   stamp("Progres 1: pondasi umpak & sloof selesai (100%)", "18 Nov 2026 · 30 titik pondasi, sloof 138 m' · pengawas teknis memeriksa tulangan (SIMULASI)")),
 "p2": svg(base("#8fc3ea", "#eaf3f8", True) + bldg(160, 590, 820, 2) + pile(1020, 690, "#9aa3ad", 8) +
   person(300, 670, 1.2) + person(470, 660, 1.15, "#ffffff", "#e67e22") + person(1000, 650, 1.2, "#f2c200", "#2e86c1") +
   '<line x1="640" y1="460" x2="640" y2="590" stroke="#c49a4a" stroke-width="5"/><line x1="610" y1="590" x2="670" y2="460" stroke="#c49a4a" stroke-width="4"/>' + person(640, 470, 1.0) +
   stamp("Progres 2: kolom baja & rangka atap baja ringan terpasang", "24 Nov 2026 · 24 kolom hollow, kuda-kuda jarak 1,2 m · progres fisik 38% (SIMULASI)")),
 "p3": svg(base("#8fc3ea", "#eef6fa", True) + bldg(160, 590, 820, 3) + person(1040, 660, 1.2) + person(320, 680, 1.2, "#ffffff", "#e67e22") + pile(1050, 700, "#5d7f8f", 6) +
   stamp("Rencana tahap berikut: atap spandek + dinding GRC", "Target 8 Des 2026 · ruang kelas 1–2 dipakai lebih dulu (SIMULASI)")),
 "cover": svg(base("#f5b47c", "#fde7cf", True, "#a7a28f") + '<rect y="600" width="1280" height="160" fill="#7f9a5a"/>' + bldg(150, 600, 860, 4) + flag(1100, 640) +
   '<rect x="420" y="438" width="220" height="40" fill="#1f4e8c" stroke="#0c2a4f"/><text x="530" y="462" font-size="15" fill="#fff" font-weight="bold" text-anchor="middle">SEKOLAH DARURAT KALIANDA</text>' +
   "".join(person(260 + i*70, 690 + (i % 2)*12, 1.15, None, ["#c0392b", "#ffffff", "#c0392b", "#ffffff"][i % 4], True) for i in range(10)) + person(1000, 700, 1.15, None, "#2c3e50") +
   stamp("UI Peduli — Sekolah Darurat Krakatau", "4 ruang kelas + ruang guru + toilet untuk 160 siswa pengungsi · ilustrasi rencana (SIMULASI)")),
}
QRIS = '''<html><head><script src="https://cdnjs.cloudflare.com/ajax/libs/qrcode-generator/1.4.4/qrcode.min.js"></script></head>
<body style="margin:0;font-family:Arial,Helvetica,sans-serif"><div id="c" style="width:620px;padding:0 0 22px;background:#fff;border:1px solid #ddd">
<div style="background:#c62828;color:#fff;font-weight:bold;font-size:20px;padding:12px 18px">QRIS SIMULASI — JANGAN DIBAYAR</div>
<div style="display:flex;justify-content:space-between;align-items:center;padding:16px 22px 4px"><div style="font-size:34px;font-weight:900;letter-spacing:2px">QRIS</div>
<div style="text-align:right;font-size:12px;color:#444">QR Code Standar<br>Pembayaran Nasional (contoh)</div></div>
<div style="text-align:center;padding:6px 22px"><div style="font-size:21px;font-weight:bold">[SIM] UI PEDULI BENCANA</div>
<div style="font-size:13px;color:#555;margin-top:4px">NMID : ID-SIMULASI-0000-UIP · Donasi Sekolah Darurat Krakatau</div></div>
<div id="qr" style="display:flex;justify-content:center;padding:12px"></div>
<div style="text-align:center;font-size:12px;color:#555">Dicetak oleh: Bank Simulasi · Versi 1.0 (SIMULASI)<br>Kode ini hanya berisi teks peringatan, bukan tagihan pembayaran.</div></div>
<script>var q=qrcode(0,'M');q.addData('SIMULASI RESCUE-NET: ini bukan QRIS asli. Jangan transfer uang.');q.make();document.getElementById('qr').innerHTML=q.createSvgTag({cellSize:9,margin:2});</script></body></html>'''
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": W, "height": H})
    for k, html in SCENES.items():
        pg.set_content(html); pg.screenshot(path=os.path.join(OUT, f"il-{k}.png")); print(k)
    pg.set_content(QRIS, wait_until="networkidle"); pg.wait_for_timeout(500); pg.locator("#c").screenshot(path=os.path.join(OUT, "qris.png")); print("qris")
    b.close()
