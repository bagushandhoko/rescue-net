import os
from playwright.sync_api import sync_playwright
OUT = os.path.dirname(os.path.abspath(__file__))
rp = lambda v: "{:,.0f}".format(v).replace(",", ".")
TX = [("02/11", "Setoran donasi - Slamet Riyadi (Warga Kalianda)", 10_000_000), ("02/11", "Setoran donasi - LD2 Landrover Logistik", 3_000_000),
      ("02/11", "Setoran donasi - Kompas TV Peduli (PIC Donasi)", 1_500_000), ("03/11", "Transfer masuk - Ikatan Alumni Teknik (SIM)", 100_000_000),
      ("05/11", "Transfer masuk - PT Sinar Nusantara Abadi CSR (SIM)", 75_000_000), ("05/11", "Pembersihan abu, bouwplank, K3 (kuitansi 001-003)", -21_500_000),
      ("06/11", "Transfer masuk - Gerakan Koin Kampus (SIM)", 18_750_000), ("08/11", "Transfer masuk - Donatur ***", 25_000_000),
      ("10/11", "Transfer masuk - Paguyuban Warga Lampung (SIM)", 7_500_000), ("12/11", "Uang muka 20% kontraktor CV Bangun Cepat (SPK 01)", -119_700_000),
      ("14/11", "Transfer masuk - R*** A***", 1_000_000), ("20/11", "Transfer masuk - B*** S***", 500_000),
      ("20/11", "DP 30% mebel 160 set + lemari (PO 004)", -30_333_000), ("22/11", "Transfer masuk - Komunitas Lari Pagi (SIM)", 3_250_000)]
rows, bal = [], 0
for d, t, v in TX:
    bal += v
    rows.append(f"<tr><td>{d}/2026</td><td>{t}</td><td class=n>{rp(-v) if v < 0 else ''}</td><td class=n>{rp(v) if v > 0 else ''}</td><td class=n>{rp(bal)}</td></tr>")
cr = sum(v for *_, v in TX if v > 0); db = -sum(v for *_, v in TX if v < 0)
html = f"""<html><head><meta charset=utf-8><style>body{{font-family:Arial;font-size:11px;color:#111}}h1{{font-size:16px;margin:0}}table{{width:100%;border-collapse:collapse;margin-top:10px}}
th,td{{border:1px solid #999;padding:4px 6px}}th{{background:#e9eef4}}.n{{text-align:right}}.sim{{position:fixed;top:38%;left:6%;font-size:58px;color:rgba(200,30,30,.12);transform:rotate(-22deg);font-weight:bold}}</style></head><body>
<div class=sim>SIMULASI — BUKAN DOKUMEN ASLI</div><h1>BANK SIMULASI — REKENING KORAN</h1>
<p>Nama rekening: <b>[SIM] UI PEDULI BENCANA</b> · No. rekening: 9001-2026-0711 · Periode: 01/11/2026 – 24/11/2026<br>Data pengirim perorangan disamarkan (***) sesuai aturan privasi Rescue-Net.</p>
<table><tr><th>Tanggal</th><th>Keterangan</th><th>Debet (Rp)</th><th>Kredit (Rp)</th><th>Saldo (Rp)</th></tr>{''.join(rows)}
<tr><td></td><td><b>Total</b></td><td class=n><b>{rp(db)}</b></td><td class=n><b>{rp(cr)}</b></td><td class=n><b>{rp(bal)}</b></td></tr></table>
<p style="margin-top:14px;color:#555">Dokumen ini dibuat untuk simulasi transparansi dana di Rescue-Net. Angka sesuai donasi terkonfirmasi & laporan penggunaan dana di halaman program.</p></body></html>"""
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(); pg.set_content(html)
    pg.pdf(path=os.path.join(OUT, "koran-nov-2026.pdf"), format="A4", margin={"top": "14mm", "bottom": "14mm", "left": "12mm", "right": "12mm"}, print_background=True); b.close()
print("kredit", cr, "debet", db, "saldo", bal)
