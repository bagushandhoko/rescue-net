"""Render aset dengan Chromium. Foto diambil dan diperiksa terpisah."""
import argparse
import os
from html import escape
from pathlib import Path

import qrcode
from PIL import Image, ImageDraw, ImageOps
from playwright.sync_api import sync_playwright

from cap_foto import font
from prog_a_data import LOCATIONS, programs

ROOT = Path(__file__).resolve().parent
WARNING = "SIMULASI RESCUE-NET. QR INI BUKAN QRIS PEMBAYARAN. JANGAN TRANSFER."
CSS = """
@page {size:A4; margin:0}
* {box-sizing:border-box}
body {margin:0; color:#142b37; background:#fff; font:15px Arial,sans-serif}
main {width:794px; padding:44px; border-top:13px solid #166657}
header {font-size:13px; letter-spacing:2px; color:#a33e16; font-weight:bold}
h1 {font-size:32px; margin:12px 0 8px}
h2 {font-size:21px}
p {line-height:1.48}
.meta {color:#476372}
table {width:100%; border-collapse:collapse; margin-top:24px}
th,td {padding:10px 8px; border-bottom:1px solid #ccd9db; text-align:left}
th {background:#166657; color:white}
.num {text-align:right; white-space:nowrap}
tr:nth-child(even) {background:#f1f6f5}
tfoot {font-weight:bold; background:#dceee8}
aside {margin-top:20px; background:#e7f3ef; padding:14px 18px}
small {display:block; margin-top:20px; line-height:1.5}
"""


def rp(number):
    return "Rp " + f"{number:,}".replace(",", ".")


def document(heading, program, body):
    return f"""<!DOCTYPE html><html lang=id><meta charset=utf-8><style>{CSS}</style>
    <main><header>SIMULASI · GEMPA ACEH BARAT · NOVEMBER 2026</header>
    <h1>{escape(heading)}</h1><p class=meta>{escape(program['title'])} · {program['id']}</p>
    {body}</main></html>"""


def table(headers, rows, numeric=(), footer=()):
    heading = "".join(f"<th>{escape(h)}</th>" for h in headers)

    def render(row):
        return "<tr>" + "".join(
            f'<td class="{"num" if i in numeric else ""}">{escape(str(value))}</td>'
            for i, value in enumerate(row)
        ) + "</tr>"

    foot = f"<tfoot>{render(footer)}</tfoot>" if footer else ""
    return f"<table><thead><tr>{heading}</tr></thead><tbody>{''.join(map(render, rows))}</tbody>{foot}</table>"


def render_pdf(page, html, path, png=False):
    page.set_content(html)
    paper = page.locator("main")
    if paper.bounding_box()["height"] > 1122:
        raise ValueError(f"Isi melebihi satu halaman A4: {path}")
    page.pdf(path=path, print_background=True, prefer_css_page_size=True)
    if png:
        paper.screenshot(path=path.with_name(f"{path.stem}-1.png"))


def statement(program):
    received, spent, _ = program["initial"]
    rows = [("21 Nov 2026", "Ringkasan dana masuk sebelum seed", received, 0),
            ("21 Nov 2026", "Ringkasan belanja sebelum seed", 0, spent)]
    rows.extend((date, donor, value, 0) for date, donor, value in program["donations"])
    rows.append(("24 Nov 2026", program["steps"][2], 0, program["spent"]))
    balance = 0
    lines = []
    for date, desc, credit, debit in rows:
        balance += credit - debit
        lines.append((date, desc, rp(credit), rp(debit), rp(balance)))
    cash_in, cash_out = program["terminal"]
    assert balance == cash_in - cash_out
    return document("Rekening koran contoh", program,
                    f"<p>Bank Simulasi · {program['bank']} · Periode 1–24 November 2026</p>"
                    + table(("Tanggal", "Uraian", "Masuk", "Keluar", "Saldo"), lines, (2, 3, 4),
                            ("", "Total / saldo akhir", rp(cash_in), rp(cash_out), rp(balance)))
                    + "<small>Data fiktif. Saldo awal periode Rp 0. Angka sebelum seed ditampilkan sebagai agregat.</small>")


def generate(page, program):
    folder = ROOT / program["key"]
    folder.mkdir(exist_ok=True)
    rows = [(item, f"{qty:,}".replace(",", ".") + " " + unit, rp(price), rp(qty * price))
            for item, qty, unit, price in program["lines"]]
    rab = document("Rencana Anggaran Biaya", program,
                   f"<p>Target layanan: {escape(program['target'])}</p>"
                   + table(("Komponen", "Volume", "Harga satuan", "Jumlah"), rows, (2, 3),
                           ("Total RAB", "", "", rp(program["total"])))
                   + "<small>Asumsi simulasi harga eceran, upah, dan angkutan Meulaboh 2026. "
                     "SSH Aceh Barat TA 2026 digunakan sebagai konteks perencanaan. "
                     "Angka ini merupakan estimasi latihan dan tidak dikutip dari tarif resmi.</small>")
    render_pdf(page, rab, folder / "rab.pdf", png=True)
    render_pdf(page, statement(program), folder / "rekening.pdf")
    guide = document("Panduan pelaksanaan", program,
                     f"<aside>{escape(program['guide'])}</aside><h2>Alur kegiatan</h2>"
                     + "<ol>" + "".join(f"<li>{escape(step)}</li>" for step in program["steps"]) + "</ol>"
                     + table(("Titik koordinat simulasi", "Lintang", "Bujur"),
                             [(role, lat, lon) for _, role, lat, lon in LOCATIONS])
                     + "<small>Titik fiktif di darat, Meulaboh, Aceh Barat. Tidak menandai fasilitas nyata.</small>")
    page.set_content(guide)
    page.locator("main").screenshot(path=folder / "panduan.png")

    code = qrcode.QRCode(box_size=10, border=4)
    code.add_data(WARNING)
    code.make()
    qr = code.make_image().convert("RGB")
    width, height = qr.size
    canvas = Image.new("RGB", (width + 80, height + 138), "white")
    canvas.paste(qr, (40, 47))
    draw = ImageDraw.Draw(canvas)
    label_font = font(24, bold=True)
    draw.text((canvas.width // 2, 22), "CONTOH QRIS · SIMULASI", anchor="mt", fill="#963916", font=label_font)
    draw.text((canvas.width // 2, height + 66), "JANGAN TRANSFER", anchor="mt", fill="#963916", font=label_font)
    canvas.save(folder / "qris.png")


def contact_sheet():
    items = list(programs())
    canvas = Image.new("RGB", (900, len(items) * 186 + 60), "#e7f3ef")
    draw = ImageDraw.Draw(canvas)
    bold = font(19, bold=True)
    regular = font(16)
    draw.text((20, 18), "Foto program A · SIMULASI", fill="#142b37", font=bold)
    for row, program in enumerate(items):
        top = 60 + row * 186
        draw.text((20, top + 14), program["key"], fill="#142b37", font=bold)
        for column, index in enumerate((0, 1)):
            x = 225 + column * 325
            path = ROOT / program["key"] / f"foto-{index}.jpg"
            draw.rectangle((x, top, x + 300, top + 168), fill="#d1e4df")
            if path.exists():
                with Image.open(path) as photo:
                    canvas.paste(ImageOps.contain(photo, (300, 168)), (x, top))
            else:
                draw.text((x + 20, top + 70), "Foto belum tersedia", fill="#142b37", font=regular)
    canvas.save(ROOT / "contact-sheet.png")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--contact-only", action="store_true")
    args = parser.parse_args()
    if not args.contact_only:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path=os.environ.get("RN_PROG_CHROMIUM"), timeout=120000)
            page = browser.new_page(viewport={"width": 794, "height": 1123}, device_scale_factor=1.6)
            for entry in programs():
                generate(page, entry)
            browser.close()
    contact_sheet()
