import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from rab import RAB, totals
from playwright.sync_api import sync_playwright
OUT = os.path.dirname(os.path.abspath(__file__))
rp = lambda v: "{:,.0f}".format(v).replace(",", ".")
CSS = """body{margin:0;font-family:Arial,Helvetica,sans-serif;color:#111}
.kop{display:flex;justify-content:space-between;align-items:flex-end;border-bottom:3px double #111;padding-bottom:8px;margin-bottom:10px}
.kop h1{font-size:15px;margin:0}.kop small{font-size:10.5px;display:block;line-height:1.35}
.sim{position:fixed;top:40%;left:8%;font-size:64px;color:rgba(200,30,30,.10);transform:rotate(-24deg);font-weight:bold;white-space:nowrap}
table{width:100%;border-collapse:collapse;font-size:10.5px}th,td{border:1px solid #444;padding:3px 5px}th{background:#e6ecf3}
td.n{text-align:right;white-space:nowrap}tr.g td{background:#f3f3f3;font-weight:bold}tr.t td{font-weight:bold;background:#fff7d6}
.ttd{display:flex;justify-content:space-between;margin-top:18px;font-size:11px}.ttd div{width:30%;text-align:center}.ttd b{display:block;margin-top:46px;text-decoration:underline}
.note{font-size:10px;color:#444;margin-top:8px}"""
def rab_html(part=0):
    sub, s, pend, adm, cad, tot = totals()
    rows = []
    for gi, ((k, t, items), (_, _, st)) in enumerate(zip(RAB, sub)):
        if part == 1 and gi > 5: continue
        if part == 2 and gi <= 5: continue
        rows.append(f'<tr class="g"><td>{k}</td><td colspan="4">{t}</td><td class="n">{rp(st)}</td></tr>')
        for i, (n, q, u, h) in enumerate(items, 1):
            rows.append(f'<tr><td>{i}</td><td>{n}</td><td class="n">{rp(q)}</td><td>{u}</td><td class="n">{rp(h)}</td><td class="n">{rp(q*h)}</td></tr>')
    rek = "".join(f'<tr><td>{k}</td><td>{t}</td><td class="n">{rp(v)}</td></tr>' for k, t, v in sub)
    fis = sum(v for k, t, v in sub if k != "XI")
    return f"""<html><head><meta charset=utf-8><style>{CSS} @page{{size:A4;margin:14mm 12mm}}</style></head><body><div class=sim>SIMULASI — BUKAN DOKUMEN ASLI</div>
<div class=kop><div><h1>RENCANA ANGGARAN BIAYA (RAB)</h1><small>Pembangunan Sekolah Darurat Semi-Permanen — 4 Ruang Kelas, 1 Ruang Guru, Toilet 4 Bilik</small>
<small>Lokasi: Lahan SDN 1 Way Urang (pinjam pakai), Kalianda, Lampung Selatan · Penerima manfaat: 160 siswa SD/SMP pengungsi</small></div>
<div style="text-align:right"><small><b>[SIMULASI] UI Peduli Bencana</b></small><small>Pendamping teknis: Tim Teknik Sipil (simulasi)</small><small>No. RAB: SIM/UIP/KRK/011/2026 · Rev. 1 · 18 Nov 2026</small></div></div>
<table><tr><th style="width:4%">No</th><th>Uraian Pekerjaan</th><th style="width:8%">Volume</th><th style="width:6%">Sat.</th><th style="width:13%">Harga Satuan (Rp)</th><th style="width:15%">Jumlah (Rp)</th></tr>{''.join(rows)}</table>
{"" if part == 1 else ""}<div style="display:{'none' if part == 1 else 'block'}"><h3 style="font-size:13px;margin:16px 0 6px">REKAPITULASI</h3>
<table><tr><th style="width:6%">No</th><th>Uraian</th><th style="width:22%">Jumlah (Rp)</th></tr>{rek}
<tr class="t"><td></td><td>JUMLAH PEKERJAAN (I–XI)</td><td class="n">{rp(s)}</td></tr>
<tr><td></td><td>Pendampingan teknis &amp; pengawasan (2%)</td><td class="n">{rp(pend)}</td></tr>
<tr><td></td><td>Administrasi, dokumentasi &amp; laporan publik (0,5%)</td><td class="n">{rp(adm)}</td></tr>
<tr><td></td><td>Cadangan kenaikan harga bahan (2%)</td><td class="n">{rp(cad)}</td></tr>
<tr class="t"><td></td><td>TOTAL ANGGARAN PROGRAM</td><td class="n">{rp(tot)}</td></tr>
<tr><td></td><td><i>Pekerjaan fisik I–X (ditenderkan)</i></td><td class="n"><i>{rp(fis)}</i></td></tr></table>
</div><p class=note>{"Halaman 1 dari 2 — lanjut ke halaman 2 (pekerjaan VII–XI dan rekapitulasi). " if part == 1 else ("Halaman 2 dari 2. " if part == 2 else "")}Harga satuan: perkiraan harga pasar Lampung Selatan Nov 2026 (asumsi simulasi), belum termasuk PPN karena pengadaan melalui program donasi. Volume dihitung dari gambar kerja GK-01 dan GK-02. Spesifikasi: kolom baja hollow 100x100x3, rangka atap baja ringan, penutup spandek pasir + foil (redam panas &amp; bising hujan), dinding GRC 9 mm.</p>
<div class=ttd><div>Disusun oleh,<b>[SIM] Perencana Teknis</b>Tim Pendamping</div><div>Diperiksa oleh,<b>[SIM] Koordinator Program</b>UI Peduli Bencana</div><div>Disetujui oleh,<b>[SIM] Kepala Sekolah</b>SDN 1 Way Urang</div></div></body></html>""", tot, fis

DRAW_CSS = """body{margin:0;background:#fff;font-family:Arial,Helvetica,sans-serif}svg text{font-family:Arial,Helvetica,sans-serif}"""
def frame(title, no, body, w=1600, h=1100):
    return f"""<html><head><meta charset=utf-8><style>{DRAW_CSS}</style></head><body><svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">
<rect x="10" y="10" width="{w-20}" height="{h-20}" fill="#fff" stroke="#111" stroke-width="3"/><rect x="22" y="22" width="{w-44}" height="{h-44}" fill="none" stroke="#111"/>
{body}
<g transform="translate({w-452},{h-182})"><rect width="430" height="160" fill="#fff" stroke="#111" stroke-width="2"/>
<line x1="0" y1="40" x2="430" y2="40" stroke="#111"/><line x1="0" y1="90" x2="430" y2="90" stroke="#111"/><line x1="0" y1="125" x2="430" y2="125" stroke="#111"/><line x1="300" y1="90" x2="300" y2="160" stroke="#111"/>
<text x="10" y="27" font-size="15" font-weight="bold">[SIMULASI] UI PEDULI BENCANA</text>
<text x="10" y="60" font-size="12">Proyek: Sekolah Darurat Semi-Permanen Kalianda</text><text x="10" y="79" font-size="12">Lokasi: SDN 1 Way Urang, Kalianda, Lampung Selatan</text>
<text x="10" y="113" font-size="15" font-weight="bold">{title}</text><text x="310" y="113" font-size="12">Skala 1 : 100</text>
<text x="10" y="148" font-size="11">Digambar: Tim Teknik (SIM) · 17-11-2026</text><text x="310" y="148" font-size="15" font-weight="bold">{no}</text></g>
<g transform="translate(40,{h-70})"><rect width="520" height="34" fill="none" stroke="#c0392b" stroke-width="2.5"/><text x="12" y="23" font-size="16" fill="#c0392b" font-weight="bold">GAMBAR KERJA SIMULASI — BUKAN DOKUMEN ASLI</text></g>
</svg></body></html>"""

def dim(x1, y1, x2, y2, label, off=0, vertical=False):
    if vertical:
        return (f'<line x1="{x1+off}" y1="{y1}" x2="{x2+off}" y2="{y2}" stroke="#333"/><line x1="{x1+off-6}" y1="{y1+6}" x2="{x1+off+6}" y2="{y1-6}" stroke="#333" stroke-width="2"/>'
                f'<line x1="{x2+off-6}" y1="{y2+6}" x2="{x2+off+6}" y2="{y2-6}" stroke="#333" stroke-width="2"/>'
                f'<text x="{x1+off-8}" y="{(y1+y2)/2}" font-size="13" text-anchor="middle" transform="rotate(-90 {x1+off-8} {(y1+y2)/2})">{label}</text>')
    return (f'<line x1="{x1}" y1="{y1+off}" x2="{x2}" y2="{y2+off}" stroke="#333"/><line x1="{x1-6}" y1="{y1+off+6}" x2="{x1+6}" y2="{y1+off-6}" stroke="#333" stroke-width="2"/>'
            f'<line x1="{x2-6}" y1="{y2+off+6}" x2="{x2+6}" y2="{y2+off-6}" stroke="#333" stroke-width="2"/><text x="{(x1+x2)/2}" y="{y1+off-6}" font-size="13" text-anchor="middle">{label}</text>')

def denah():
    S = 30  # px per m ; bangunan 32 x 8 m + selasar 2 m depan; toilet 4x3 terpisah
    ox, oy = 110, 250
    b = []
    rooms = [("RUANG KELAS 1", 7), ("RUANG KELAS 2", 7), ("RUANG GURU", 4), ("RUANG KELAS 3", 7), ("RUANG KELAS 4", 7)]
    x = ox
    b.append(f'<rect x="{ox}" y="{oy}" width="{32*S}" height="{8*S}" fill="#f7f4ee" stroke="#111" stroke-width="6"/>')
    for i, (n, wm) in enumerate(rooms):
        if i: b.append(f'<line x1="{x}" y1="{oy}" x2="{x}" y2="{oy+8*S}" stroke="#111" stroke-width="5"/>')
        cx = x + wm*S/2
        b.append(f'<text x="{cx}" y="{oy+4*S-8}" font-size="15" font-weight="bold" text-anchor="middle">{n}</text>')
        b.append(f'<text x="{cx}" y="{oy+4*S+12}" font-size="12" text-anchor="middle">{wm} x 8 m · {"40 siswa" if wm==7 else "6 guru"}</text>')
        b.append(f'<text x="{cx}" y="{oy+4*S+30}" font-size="11" text-anchor="middle" fill="#555">+0,45</text>')
        if wm == 7:  # meja siswa grid
            for r in range(4):
                for c in range(5):
                    b.append(f'<rect x="{x+28+c*36}" y="{oy+40+r*30}" width="18" height="12" fill="none" stroke="#777"/>' if r in (0, 3) else "")
            b.append(f'<line x1="{x+30}" y1="{oy+12}" x2="{x+wm*S-30}" y2="{oy+12}" stroke="#2c7" stroke-width="4"/>')
        # pintu (depan/bawah) dengan busur
        dx = x + wm*S - 70
        b.append(f'<rect x="{dx}" y="{oy+8*S-4}" width="30" height="8" fill="#fff"/><path d="M{dx} {oy+8*S} A30 30 0 0 0 {dx+30} {oy+8*S-30}" fill="none" stroke="#333"/><line x1="{dx+30}" y1="{oy+8*S}" x2="{dx+30}" y2="{oy+8*S-30}" stroke="#333"/>')
        # jendela belakang & depan
        for jx in (x+20, x+wm*S/2-15) if wm == 7 else (x+30,):
            b.append(f'<rect x="{jx}" y="{oy-3}" width="40" height="6" fill="#bfe3ff" stroke="#111"/>')
        x += wm*S
    # selasar
    b.append(f'<rect x="{ox}" y="{oy+8*S}" width="{32*S}" height="{2*S}" fill="#eee" stroke="#111" stroke-dasharray="8 5"/>')
    b.append(f'<text x="{ox+16*S}" y="{oy+9*S+5}" font-size="13" text-anchor="middle">SELASAR / TERAS ± 0,30 (lebar 2 m)</text>')
    # kolom grid
    xs = [0, 3.5, 7, 10.5, 14, 18, 21.5, 25, 28.5, 32]
    for i, xm in enumerate(xs):
        for ym in (0, 8, 10):
            b.append(f'<rect x="{ox+xm*S-5}" y="{oy+ym*S-5}" width="10" height="10" fill="#111"/>')
    for i, xm in enumerate([0, 7, 14, 18, 25, 32]):
        X = ox + xm*S
        b.append(f'<line x1="{X}" y1="{oy-70}" x2="{X}" y2="{oy-20}" stroke="#999" stroke-dasharray="10 4 2 4"/><circle cx="{X}" cy="{oy-86}" r="15" fill="#fff" stroke="#111"/><text x="{X}" y="{oy-81}" font-size="14" text-anchor="middle">{i+1}</text>')
    for j, (ym, L) in enumerate([(0, "A"), (8, "B"), (10, "C")]):
        Y = oy + ym*S
        b.append(f'<circle cx="{ox-56}" cy="{Y}" r="15" fill="#fff" stroke="#111"/><text x="{ox-56}" y="{Y+5}" font-size="14" text-anchor="middle">{L}</text>')
    # dimensi
    x = ox
    for n, wm in rooms:
        b.append(dim(x, oy+10*S+30, x+wm*S, oy+10*S+30, f"{wm*1000:,}".replace(",", "."), 0)); x += wm*S
    b.append(dim(ox, oy+10*S+70, ox+32*S, oy+10*S+70, "32.000", 0))
    b.append(dim(ox+32*S+40, oy, ox+32*S+40, oy+8*S, "8.000", 0, True))
    b.append(dim(ox+32*S+40, oy+8*S, ox+32*S+40, oy+10*S, "2.000", 0, True))
    # toilet & tandon & cuci tangan
    tx, ty = ox+32*S+110, oy
    b.append(f'<rect x="{tx}" y="{ty}" width="{4*S}" height="{3*S*2}" fill="#eef6fb" stroke="#111" stroke-width="5"/>')
    for k in range(1, 4):
        b.append(f'<line x1="{tx}" y1="{ty+k*45}" x2="{tx+4*S}" y2="{ty+k*45}" stroke="#111" stroke-width="3"/>')
    for k in range(4):
        b.append(f'<ellipse cx="{tx+75}" cy="{ty+22+k*45}" rx="12" ry="8" fill="none" stroke="#333"/><text x="{tx+10}" y="{ty+28+k*45}" font-size="11">WC {k+1}</text>')
    b.append(f'<text x="{tx+2*S}" y="{ty+6*S+22}" font-size="13" font-weight="bold" text-anchor="middle">TOILET 4 BILIK</text><text x="{tx+2*S}" y="{ty+6*S+38}" font-size="11" text-anchor="middle">(2 pa / 2 pi) 4 x 6 m</text>')
    b.append(f'<circle cx="{tx+60}" cy="{ty+6*S+90}" r="26" fill="#d6ecff" stroke="#111"/><text x="{tx+60}" y="{ty+6*S+94}" font-size="10" text-anchor="middle">TANDON</text><text x="{tx+60}" y="{ty+6*S+135}" font-size="11" text-anchor="middle">2.200 L / menara 4 m</text>')
    b.append(f'<rect x="{ox+2*S}" y="{oy+10*S+110}" width="{5*S}" height="22" fill="#d6ecff" stroke="#111"/><text x="{ox+2*S+5*S/2}" y="{oy+10*S+150}" font-size="11" text-anchor="middle">Tempat cuci tangan 6 kran</text>')
    b.append(f'<rect x="{ox+10*S}" y="{oy+10*S+110}" width="{12*S}" height="60" fill="#eaf6e5" stroke="#5a5" stroke-dasharray="6 4"/><text x="{ox+16*S}" y="{oy+10*S+145}" font-size="12" text-anchor="middle">Halaman upacara / bermain (paving eksisting)</text>')
    # arah utara
    b.append('<g transform="translate(1480,110)"><circle r="34" fill="none" stroke="#111"/><path d="M0 -30 L12 18 L0 8 L-12 18 Z" fill="#111"/><text y="-40" font-size="16" text-anchor="middle" font-weight="bold">U</text></g>')
    b.append(f'<text x="{ox}" y="80" font-size="26" font-weight="bold">DENAH SEKOLAH DARURAT — LUAS BANGUNAN 256 m² + SELASAR 64 m² + TOILET 24 m²</text>')
    b.append(f'<text x="{ox}" y="108" font-size="15" fill="#333">4 ruang kelas (@ 40 siswa) + 1 ruang guru · Kolom baja hollow 100x100 jarak 3,5 m · Lantai +0,45 dari tanah (antisipasi lahar dingin/genangan)</text>')
    return frame("DENAH LANTAI", "GK-01", "".join(b))

def tampak():
    S = 26; ox, gy = 120, 440
    b = [f'<text x="{ox}" y="80" font-size="26" font-weight="bold">TAMPAK DEPAN &amp; POTONGAN A-A</text>',
         f'<text x="{ox}" y="108" font-size="15" fill="#333">Rangka atap baja ringan kemiringan 25°, penutup spandek pasir + foil, tinggi plafon 3,2 m, lantai +0,45</text>']
    L = 32*S
    # tanah
    b.append(f'<line x1="{ox-40}" y1="{gy}" x2="{ox+L+40}" y2="{gy}" stroke="#111" stroke-width="3"/>')
    for i in range(0, L+80, 18): b.append(f'<line x1="{ox-40+i}" y1="{gy}" x2="{ox-52+i}" y2="{gy+12}" stroke="#777"/>')
    fl = gy - 0.45*S; pl = fl - 3.2*S
    b.append(f'<rect x="{ox}" y="{fl}" width="{L}" height="{0.45*S}" fill="#ccc" stroke="#111"/>')
    b.append(f'<rect x="{ox}" y="{pl}" width="{L}" height="{3.2*S}" fill="#f4efe4" stroke="#111" stroke-width="2"/>')
    # jendela & pintu tiap ruang
    x = ox
    for wm in (7, 7, 4, 7, 7):
        if wm == 7:
            for k in range(3):
                jx = x + 15 + k*48
                b.append(f'<rect x="{jx}" y="{pl+22}" width="34" height="46" fill="#bfe3ff" stroke="#111"/>' + "".join(f'<line x1="{jx}" y1="{pl+22+t*6}" x2="{jx+34}" y2="{pl+22+t*6}" stroke="#7aa"/>' for t in range(1, 8)))
        b.append(f'<rect x="{x+wm*S-48}" y="{pl+14}" width="28" height="{3.2*S-14}" fill="#8a5a33" stroke="#111"/>')
        x += wm*S
    # atap (overhang 1 m), tinggi atap
    oh = 1*S; ridge = pl - 4.6*S*0.47
    b.append(f'<polygon points="{ox-oh},{pl} {ox+L+oh},{pl} {ox+L+oh-2.2*S},{ridge} {ox-oh+2.2*S},{ridge}" fill="#9aa7b5" stroke="#111" stroke-width="2"/>')
    for i in range(0, int(L+2*oh), 10): b.append(f'<line x1="{ox-oh+i}" y1="{pl}" x2="{ox-oh+i + (2.2*S if i < (L+2*oh)/2 else -2.2*S)*0}" y2="{ridge if (ox-oh+i) > ox-oh+2.2*S and (ox-oh+i) < ox+L+oh-2.2*S else pl}" stroke="#7d8a98" stroke-width="1"/>')
    b.append(f'<rect x="{ox-oh}" y="{pl-6}" width="{L+2*oh}" height="8" fill="#e8e8e8" stroke="#111"/>')
    b.append(f'<text x="{ox+L/2}" y="{ridge-14}" font-size="13" text-anchor="middle">Penutup spandek pasir 0,35 + insulasi foil · talang PVC</text>')
    # papan nama
    b.append(f'<rect x="{ox+14*S-30}" y="{pl-58}" width="{4*S+60}" height="44" fill="#1f4e8c" stroke="#111"/><text x="{ox+16*S}" y="{pl-38}" font-size="12" fill="#fff" text-anchor="middle" font-weight="bold">SEKOLAH DARURAT</text><text x="{ox+16*S}" y="{pl-22}" font-size="10" fill="#fff" text-anchor="middle">KALIANDA (SIMULASI)</text>')
    # elevasi
    for y, t in ((pl-1, "+3,65 plafon"), (fl, "+0,45 lantai"), (gy, "±0,00 tanah")):
        b.append(f'<line x1="{ox+L+50}" y1="{y}" x2="{ox+L+90}" y2="{y}" stroke="#111"/><path d="M{ox+L+60} {y} l-8 -12 h16 z" fill="#111"/><text x="{ox+L+96}" y="{y+4}" font-size="13">{t}</text>')
    b.append(f'<text x="{ox+L/2}" y="{gy+46}" font-size="18" font-weight="bold" text-anchor="middle">TAMPAK DEPAN  1 : 100</text>')
    # POTONGAN A-A
    px, py, W = 260, 1010, 8*45
    S2 = 45
    pfl = py - 0.45*S2; ppl = pfl - 3.2*S2; top = ppl - (4.0+1)*S2*0.47
    b.append(f'<line x1="{px-120}" y1="{py}" x2="{px+W+2*S2+120}" y2="{py}" stroke="#111" stroke-width="3"/>')
    for i in range(0, W+2*S2+240, 18): b.append(f'<line x1="{px-120+i}" y1="{py}" x2="{px-132+i}" y2="{py+12}" stroke="#777"/>')
    # pondasi umpak
    for xx in (px, px+W, px+W+2*S2):
        b.append(f'<rect x="{xx-18}" y="{py}" width="36" height="34" fill="#bbb" stroke="#111"/><rect x="{xx-8}" y="{py-0.45*S2}" width="16" height="{0.45*S2}" fill="#999" stroke="#111"/>')
    b.append(f'<rect x="{px}" y="{pfl}" width="{W}" height="{0.45*S2}" fill="#d8d8d8" stroke="#111"/><rect x="{px+W}" y="{py-0.3*S2}" width="{2*S2}" height="{0.3*S2}" fill="#e5e5e5" stroke="#111"/>')
    b.append(f'<rect x="{px-6}" y="{ppl}" width="12" height="{3.2*S2}" fill="#555"/><rect x="{px+W-6}" y="{ppl}" width="12" height="{3.2*S2}" fill="#555"/><rect x="{px+W+2*S2-5}" y="{ppl+10}" width="10" height="{3.2*S2-10+0.45*S2-0.3*S2}" fill="#555"/>')
    b.append(f'<line x1="{px}" y1="{ppl}" x2="{px+W}" y2="{ppl}" stroke="#111" stroke-width="2" stroke-dasharray="6 3"/>')
    # truss
    mid = px + W/2; L0, R0 = px - S2, px + W + 2*S2 + 20
    b.append(f'<polyline points="{L0},{ppl+8} {mid},{top} {R0},{ppl+30}" fill="none" stroke="#c0392b" stroke-width="4"/><line x1="{px}" y1="{ppl}" x2="{px+W}" y2="{ppl}" stroke="#c0392b" stroke-width="3"/>')
    for k in range(1, 8):
        xk = px + k*W/8; yk = top + abs(xk-mid)/(W/2)*(ppl-top)
        b.append(f'<line x1="{xk}" y1="{ppl}" x2="{xk}" y2="{yk}" stroke="#c0392b" stroke-width="1.5"/>')
        if k < 7: b.append(f'<line x1="{xk}" y1="{ppl}" x2="{xk+W/8}" y2="{top + abs(xk+W/8-mid)/(W/2)*(ppl-top)}" stroke="#c0392b" stroke-width="1.5"/>')
    LX = px + W + 2*S2 + 160
    for t, ax, ay, ly in (("Penutup spandek pasir 0,35 + foil, kemiringan 25°", mid+60, top+28, top-6),
                          ("Rangka atap baja ringan C75 (kuda-kuda jarak 1,2 m)", mid+110, ppl-40, top+30),
                          ("Plafon gypsum 9 mm, rangka hollow (+3,65)", px+W-40, ppl, ppl-6),
                          ("Kolom baja hollow 100x100x3", px+W, ppl+50, ppl+40),
                          ("Dinding GRC 9 mm luar / kalsiboard dalam", px+W-4, ppl+100, ppl+80),
                          ("Lantai keramik 40x40 di atas rabat beton K-175", px+W-60, pfl+6, pfl-14),
                          ("Pondasi umpak beton 40x40 + sloof 15/20", px+W+2, py+20, py+24)):
        b.append(f'<line x1="{ax}" y1="{ay}" x2="{LX-8}" y2="{ly-4}" stroke="#555"/><circle cx="{ax}" cy="{ay}" r="3" fill="#555"/><text x="{LX}" y="{ly}" font-size="14">{t}</text>')
    b.append(f'<text x="{px+W/2}" y="{ppl+70}" font-size="15" text-anchor="middle" fill="#666">RUANG KELAS</text><text x="{px+W+S2}" y="{ppl+70}" font-size="12" text-anchor="middle" fill="#666">SELASAR</text>')
    b.append(dim(px, py+60, px+W, py+60, "8.000") + dim(px+W, py+60, px+W+2*S2, py+60, "2.000"))
    b.append(dim(px-60, ppl, px-60, pfl, "3.200", 0, True))
    b.append(f'<text x="{px+W/2+60}" y="{py+110}" font-size="18" font-weight="bold" text-anchor="middle">POTONGAN A-A  1 : 100</text>')
    return frame("TAMPAK &amp; POTONGAN", "GK-02", "".join(b), 1600, 1200)

if __name__ == "__main__":
    html, tot, fis = rab_html()
    open(os.path.join(OUT, "rab.html"), "w").write(html)
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(); pg.set_content(html); pg.pdf(path=os.path.join(OUT, "rab-sekolah-darurat-kalianda.pdf"), format="A4", margin={"top": "14mm", "bottom": "14mm", "left": "12mm", "right": "12mm"}, print_background=True,
              display_header_footer=True, header_template="<span></span>", footer_template='<div style="font-size:8px;width:100%;text-align:center;color:#666">RAB SIMULASI — Sekolah Darurat Kalianda · hal. <span class="pageNumber"></span>/<span class="totalPages"></span></div>')
        pg = b.new_page(viewport={"width": 1100, "height": 1400}, device_scale_factor=1); pg.set_content(html.replace("<body>", "<body style=\"padding:28px;background:#fff\">")); pg.wait_for_timeout(300)
        H = pg.evaluate("document.body.scrollHeight"); print("rab tinggi", H)
        pg.set_viewport_size({"width": 1100, "height": H}); pg.screenshot(path=os.path.join(OUT, "rab-full.png"), full_page=True)
        for part in (1, 2):
            h2 = rab_html(part)[0].replace("<body>", "<body style=\"padding:28px;background:#fff\">")
            pg = b.new_page(viewport={"width": 1100, "height": 900}); pg.set_content(h2); pg.wait_for_timeout(200)
            pg.screenshot(path=os.path.join(OUT, f"rab-hal-{part}.png"), full_page=True); print("rab hal", part)
        for name, fn, (w, h) in (("denah", denah, (1600, 1100)), ("tampak", tampak, (1600, 1200))):
            pg = b.new_page(viewport={"width": w, "height": h}); pg.set_content(fn()); pg.screenshot(path=os.path.join(OUT, f"{name}.png")); print(name)
        b.close()
    print("TOTAL", tot, "FISIK", fis)
