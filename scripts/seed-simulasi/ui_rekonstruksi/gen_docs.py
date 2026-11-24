"""Buat PDF/PNG RAB, gambar kerja, QR peringatan, dan rekening koran contoh."""
from io import BytesIO
from pathlib import Path


from rek_data import ACCOUNT, DONATIONS, HOLDER, LOCATION, QR_TEXT, RAB, TOTAL, UPDATES
from drawings import elevation, plan

OUT = Path(__file__).resolve().parent
CSS = """
@page { size: A4; margin: 0; }
* { box-sizing: border-box; }
body { margin:0; font: 12px Arial,sans-serif; color:#183244; }
.sheet { width:210mm; height:296.5mm; padding:13mm 12mm; position:relative; }
.sheet + .sheet { break-before:page; }
header { border-bottom:2px solid #284d63; padding-bottom:10px; margin-bottom:12px; }
h1 { font-size:24px; margin:8px 0 4px; } h2 { font-size:15px; margin:12px 0 6px; }
p { margin:6px 0; line-height:1.5; }
strong.warning { color:#972a22; }
table { width:100%; border-collapse:collapse; font-size:12px; }
th,td { padding:5px 7px; border:1px solid #a7bac4; }
th,.group { background:#e8f0f4; text-align:left; } .group,.total { font-weight:bold; }
.num { text-align:right; white-space:nowrap; font-variant-numeric:tabular-nums; }
footer { position:absolute; bottom:12mm; left:12mm; right:12mm; border-top:1px solid #a7bac4; padding-top:7px; }
"""


def rp(n):
    return f"{n:,}".replace(",", ".")


def group_total(items):
    return sum(q * h for _, q, _, h in items)


def page(title, subtitle, content, footer):
    return f"""<section class="sheet"><header>
<strong class="warning">SIMULASI RESCUE-NET</strong><h1>{title}</h1>
<p>UI Peduli — Rekonstruksi Fasilitas Belajar<br>{LOCATION}<br>{subtitle}</p>
</header>{content}<footer>{footer}</footer></section>"""


def html(*pages):
    return '<!doctype html><meta charset="utf-8"><style>' + CSS + '</style>' + "".join(pages)


def rab_page(groups, number):
    rows = []
    for code, title, items in groups:
        rows.append(f'<tr class="group"><td colspan="5">{code} · {title}</td>'
                    f'<td class="num">{rp(group_total(items))}</td></tr>')
        for i, (name, qty, unit, rate) in enumerate(items, 1):
            rows.append(f'<tr><td>{code}.{i}</td><td>{name}</td><td class="num">{rp(qty)}</td>'
                        f'<td>{unit}</td><td class="num">{rp(rate)}</td><td class="num">{rp(qty*rate)}</td></tr>')
    content = ('<table><tr><th>No.</th><th>Uraian pekerjaan</th><th>Vol.</th><th>Sat.</th>'
               '<th>Harga satuan (Rp)</th><th>Jumlah (Rp)</th></tr>' + "".join(rows) + '</table>')
    if number == 1:
        content += ('<h2>Dasar volume</h2><p>Blok eksisting 21 × 8 m dan selasar 21 × 2 m. '
                    'Atap: proyeksi 22 × 10,45 m ÷ cos 26°, dibulatkan ke 256 m². Volume perkuatan adalah asumsi dari '
                    'asesmen simulasi, termasuk delapan kolom dan pekerjaan balok/sloof.</p>')
    if number == 2:
        recap = "".join(f'<tr><td>{k} · {title}</td><td class="num">{rp(group_total(items))}</td></tr>'
                        for k, title, items in RAB)
        content += (f'<h2>Rekapitulasi seluruh kelompok</h2><table>{recap}<tr class="total">'
                    f'<td>TOTAL ANGGARAN PROGRAM</td><td class="num">Rp {rp(TOTAL)}</td></tr></table>'
                    '<p>Harga satuan terpasang adalah estimasi simulasi Meulaboh 2026 (bahan, upah dan alat), '
                    'dengan SSH Aceh Barat TA 2026, Keputusan Bupati 419/2025, sebagai acuan tingkat harga. '
                    'Tidak ada baris pajak terpisah dalam simulasi ini.</p>')
    return page("Rencana Anggaran Biaya", "SIM/UIP/REB/02 · Rev. 0 · 24 November 2026",
                content, f"RAB rehabilitasi dua kelas dan perpustakaan · Halaman {number}/2")


def statement_html(open_received=0, open_spent=0):
    transactions = [(ts, "Donasi — " + ("Anonim ***" if anon else donor), amt)
                    for ts, donor, amt, anon, confirmed in DONATIONS if confirmed]
    transactions += [(ts, title, -amt) for ts, title, _, amt, _ in UPDATES if amt]
    opening = open_received - open_spent
    balance = opening
    rows = [f'<tr><td>Awal</td><td>Saldo catatan awal program</td><td></td><td></td><td class="num">{rp(opening)}</td></tr>']
    for ts, title, change in sorted(transactions):
        balance += change
        debit = rp(-change) if change < 0 else ""
        credit = rp(change) if change > 0 else ""
        rows.append(f'<tr><td>{ts[8:10]}/11/2026</td><td>{title}</td>'
                    f'<td class="num">{debit}</td><td class="num">{credit}</td><td class="num">{rp(balance)}</td></tr>')
    received = sum(v for _, _, v in transactions if v > 0)
    spent = -sum(v for _, _, v in transactions if v < 0)
    content = f"""<p>Rekening fiktif {ACCOUNT} · Periode skenario 4–24 November 2026</p>
<table><tr><th>Tanggal</th><th>Keterangan</th><th>Debet (Rp)</th><th>Kredit (Rp)</th><th>Saldo (Rp)</th></tr>
{''.join(rows)}<tr class="total"><td></td><td>Mutasi skenario / saldo akhir</td>
<td class="num">{rp(spent)}</td><td class="num">{rp(received)}</td><td class="num">{rp(balance)}</td></tr></table>
<h2>Rekonsiliasi</h2><p>Catatan awal sebelum seed: dana masuk Rp {rp(open_received)}, dana terpakai Rp {rp(open_spent)}.
Setelah mutasi skenario: dana masuk Rp {rp(open_received + received)}, dana terpakai Rp {rp(open_spent + spent)}.</p>
<p>Saldo awal merangkum catatan program yang sudah ada sebelum seed. Komitmen Rp 2.000.000
yang masih menunggu konfirmasi tidak masuk mutasi. Data perorangan disamarkan.</p>"""
    return html(page("Rekening koran simulasi", "Bank Simulasi · " + HOLDER,
                     content, "Dokumen fiktif untuk latihan transparansi dana · Jangan transfer"))


def generate():
    import qrcode
    from playwright.sync_api import sync_playwright
    sections = (rab_page(RAB[:3], 1), rab_page(RAB[3:], 2))
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        tab = browser.new_page(viewport={"width": 1400, "height": 1150}, device_scale_factor=2)
        tab.set_content(html(*sections))
        tab.pdf(path=OUT / "rek-rab.pdf", prefer_css_page_size=True, print_background=True)
        for i, section in enumerate(sections, 1):
            tab.set_content(html(section))
            tab.locator(".sheet").screenshot(path=OUT / f"rek-rab-{i}.png")
        for code, drawing in (("gk01", plan()), ("gk02", elevation())):
            tab.set_content(drawing)
            tab.locator("svg").screenshot(path=OUT / f"rek-{code}.png")
        tab.set_content(statement_html())
        tab.pdf(path=OUT / "rek-koran.pdf", prefer_css_page_size=True, print_background=True)
        payload = BytesIO()
        qrcode.make(QR_TEXT).save(payload, format="PNG")
        from base64 import b64encode
        encoded = b64encode(payload.getvalue()).decode("ascii")
        tab.set_content(f"""<meta charset="utf-8"><div id="q" style="width:500px;text-align:center;
        padding:24px;background:white;color:#8a291e;font: bold 22px Arial">
        QRIS CONTOH · SIMULASI<br><img alt="" src="data:image/png;base64,{encoded}">
        <br>JANGAN TRANSFER<br>QR ini berisi teks peringatan</div>""")
        tab.locator("#q").screenshot(path=OUT / "rek-qris.png")
        browser.close()


if __name__ == "__main__":
    generate()
