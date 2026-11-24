"""Buat PDF/PNG RAB, gambar kerja, QR peringatan, dan rekening koran contoh."""
from io import BytesIO
from datetime import datetime
from pathlib import Path


from baduy_data import (
    ACCOUNT, DONATIONS, HOLDER, HOUSE, LEUIT, LOCATION, MARKER, OPENING,
    PENDING, QR_TEXT, RECEIVED, SPENT, SUPPORT, TOTAL, UPDATES, subtotal,
)
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


def page(title, subtitle, content, footer):
    return f"""<section class="sheet"><header>
<strong class="warning">SIMULASI RESCUE-NET</strong><h1>{title}</h1>
<p>Bangun Kembali 21 Rumah Warga Baduy Luar<br>{LOCATION}<br>{subtitle}</p>
</header>{content}<footer>{footer}</footer></section>"""


def html(*pages):
    return '<!doctype html><meta charset="utf-8"><style>' + CSS + '</style>' + "".join(pages)


def cost_table(items):
    rows = "".join(
        f'<tr><td>{i}</td><td>{name}</td><td class="num">{qty}</td><td>{unit}</td>'
        f'<td class="num">{rp(rate)}</td><td class="num">{rp(qty * rate)}</td></tr>'
        for i, (name, qty, unit, rate) in enumerate(items, 1)
    )
    return (f'<table><tr><th>No.</th><th>Uraian</th><th>Vol.</th><th>Sat.</th>'
            f'<th>Harga satuan (Rp)</th><th>Jumlah (Rp)</th></tr>{rows}'
            f'<tr class="total"><td colspan="5">Subtotal</td><td class="num">{rp(subtotal(items))}</td></tr></table>')


def rab_pages():
    subtitle = f"{MARKER} · Rev. 0 · 24 November 2026"
    house = '<h2>A · Biaya satu rumah panggung 6 × 6 m</h2>' + cost_table(HOUSE)
    house += ("<h2>Dasar volume</h2><p>Palupuh 6 × 6 m. Atap 7,2 × 7,2 m dalam proyeksi, "
              "kemiringan 40°, ditambah susut sekitar 12%. Bilik bersih setelah bukaan. "
              "12 umpak menopang 12 tiang. Ikatan dan pasak menggantikan paku. OH = orang-hari, "
              "rit = satu perjalanan pikul.</p>")
    recap = '<h2>B · Biaya satu leuit 2,4 × 2,4 m</h2>' + cost_table(LEUIT)
    recap += '<h2>C · Pendampingan, administrasi dan cadangan program</h2>' + cost_table(SUPPORT)
    recap += f"""<h2>Rekapitulasi program</h2><table>
<tr><td>21 rumah × Rp {rp(subtotal(HOUSE))}</td><td class="num">{rp(21*subtotal(HOUSE))}</td></tr>
<tr><td>2 leuit × Rp {rp(subtotal(LEUIT))}</td><td class="num">{rp(2*subtotal(LEUIT))}</td></tr>
<tr><td>Pendampingan, administrasi dan cadangan</td><td class="num">{rp(subtotal(SUPPORT))}</td></tr>
<tr class="total"><td>TOTAL ANGGARAN</td><td class="num">Rp {rp(TOTAL)}</td></tr></table>
<p>Harga adalah asumsi simulasi Lebak TA 2026. Rujukan konteks harga: Perbup Lebak 7/2025
(JDIH dokumen 1254). Harga bahan khusus adat dan angkut pikul perlu penawaran lokal.</p>"""
    return (page("Rencana Anggaran Biaya", subtitle, house, "RAB simulasi · Halaman 1/2"),
            page("Rencana Anggaran Biaya", subtitle, recap, "RAB simulasi · Halaman 2/2"))


def statement_html():
    def day(timestamp):
        return datetime.fromisoformat(timestamp).strftime("%d/%m/%Y")

    transactions = list(OPENING)
    transactions += [(day(ts), "Donasi — " + ("Anonim ***" if anon else donor), amount)
                     for ts, donor, amount, anon, confirmed in DONATIONS if confirmed]
    transactions += [(day(ts), title, -spent) for ts, title, _, spent, _ in UPDATES if spent]
    balance = 0
    rows = ['<tr><td>Awal</td><td>Saldo awal</td><td></td><td></td><td class="num">0</td></tr>']
    for date, title, change in transactions:
        balance += change
        debit = rp(-change) if change < 0 else ""
        credit = rp(change) if change > 0 else ""
        rows.append(f'<tr><td>{date}</td><td>{title}</td>'
                    f'<td class="num">{debit}</td><td class="num">{credit}</td><td class="num">{rp(balance)}</td></tr>')
    content = f"""<p>Rekening fiktif {ACCOUNT} · Periode skenario 22 November–12 Desember 2026</p>
<table><tr><th>Tanggal</th><th>Keterangan</th><th>Debet (Rp)</th><th>Kredit (Rp)</th><th>Saldo (Rp)</th></tr>
{''.join(rows)}<tr class="total"><td></td><td>Total mutasi / saldo akhir</td>
<td class="num">{rp(SPENT)}</td><td class="num">{rp(RECEIVED)}</td><td class="num">{rp(balance)}</td></tr></table>
<p>Dua donasi menunggu konfirmasi (Rp {rp(PENDING)}) berada di luar mutasi rekening.
Keterangan transaksi lama diringkas dari skenario program.</p>"""
    return html(page("Rekening koran simulasi", "Bank Simulasi · " + HOLDER,
                     content, "Dokumen fiktif untuk latihan transparansi dana · Jangan transfer"))


def generate():
    import qrcode
    from playwright.sync_api import sync_playwright
    sections = rab_pages()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        tab = browser.new_page(viewport={"width": 1400, "height": 1150}, device_scale_factor=2)
        tab.set_content(html(*sections))
        tab.pdf(path=OUT / "baduy-rab.pdf", prefer_css_page_size=True, print_background=True)
        for i, section in enumerate(sections, 1):
            tab.set_content(html(section))
            tab.locator(".sheet").screenshot(path=OUT / f"baduy-rab-{i}.png")
        for code, drawing in (("gk01", plan()), ("gk02", elevation())):
            tab.set_content(drawing)
            tab.locator("svg").screenshot(path=OUT / f"baduy-{code}.png")
        tab.set_content(statement_html())
        tab.pdf(path=OUT / "baduy-koran.pdf", prefer_css_page_size=True, print_background=True)
        payload = BytesIO()
        qrcode.make(QR_TEXT).save(payload, format="PNG")
        from base64 import b64encode
        encoded = b64encode(payload.getvalue()).decode("ascii")
        tab.set_content(f"""<meta charset="utf-8"><div id="q" style="width:500px;text-align:center;
        padding:24px;background:white;color:#8a291e;font: bold 22px Arial">
        QRIS CONTOH · SIMULASI<br><img alt="" src="data:image/png;base64,{encoded}">
        <br>JANGAN TRANSFER<br>QR ini berisi teks peringatan</div>""")
        tab.locator("#q").screenshot(path=OUT / "baduy-qris.png")
        browser.close()


if __name__ == "__main__":
    generate()
