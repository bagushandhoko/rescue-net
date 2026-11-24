"""Render Chromium. Opsional: --photos menunjuk direktori foto mentah yang sudah diperiksa."""
import argparse
from html import escape
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

from data_b import AREAS, PENDING, PROGRAMS, RECEIPT_DAYS, UPDATE_DAYS, account

ROOT = Path(__file__).resolve().parent
CSS = """
@page { size:A4; margin:14mm; }
* { box-sizing:border-box; }
body { margin:0; color:#182a3c; background:white; font:16px Arial,sans-serif; }
article { padding:22px; border-top:7px solid #286572; }
header { display:flex; justify-content:space-between; color:#286572; font-size:14px; }
strong.stamp { background:#9c251d; color:white; padding:6px 10px; }
h1 { font-size:28px; margin:18px 0 6px; }
h2 { font-size:19px; margin:12px 0; }
p, li { line-height:1.45; }
table { width:100%; border-collapse:collapse; font-size:14px; }
td, th { padding:8px 7px; border-bottom:1px solid #cbd6dc; text-align:left; }
th { background:#e8f1f4; }
td.num { text-align:right; white-space:nowrap; }
tfoot td { font-weight:bold; background:#e8f1f4; }
footer { margin-top:16px; padding-top:10px; border-top:1px solid #cbd6dc; font-size:13px; }
a { color:#17515b; }
"""


def rp(amount):
    return f"{amount:,}".replace(",", ".")


def page(program, title, content, footer):
    return f"""<!doctype html><html lang="id"><meta charset="utf-8"><style>{CSS}</style>
<article><header><span>Rescue-Net · 24 November 2026</span><strong class="stamp">SIMULASI</strong></header>
<h1>{title}</h1><h2>{escape(program.title)}</h2>{content}<footer>{footer}</footer></article></html>"""


def rab(program):
    lines = "".join(
        f'<tr><td>{escape(label)}</td><td>{qty:g} {escape(unit)}</td>'
        f'<td class="num">{rp(price)}</td><td class="num">{rp(qty * price)}</td></tr>'
        for label, qty, unit, price in program.rows
    )
    locations = " / ".join(place for place, *_ in AREAS[program.area][1])
    return page(program, "Rencana Anggaran Biaya", f"""<p>{escape(program.scope)}</p>
<table><thead><tr><th>Komponen</th><th>Volume</th><th>Satuan (Rp)</th><th>Jumlah (Rp)</th></tr></thead>
<tbody>{lines}</tbody><tfoot><tr><td colspan="3">Total RAB</td><td class="num">{rp(program.target)}</td></tr></tfoot></table>
<p>Sumber harga: asumsi simulasi harga bahan, upah, dan logistik 2026 di {locations}.
Harga per baris adalah perkiraan paket atau biaya terpasang sesuai uraian.</p>""",
                "Dokumen latihan · Semua volume dan harga adalah perkiraan skenario.")


def statement(key, program):
    received, spent = program.opening
    balance = received - spent
    rows = [f'<tr><td>Awal</td><td>Saldo sebelum seed</td><td></td><td></td><td class="num">{rp(balance)}</td></tr>']
    items = [(day, "Donasi masuk · identitas disamarkan", amount)
             for day, amount in zip(RECEIPT_DAYS, program.receipts)]
    items += [(day, title, -amount)
              for day, title, amount in zip(UPDATE_DAYS, program.stages[:2], program.spending)]
    for day, title, amount in sorted(items):
        balance += amount
        debit = rp(-amount) if amount < 0 else ""
        credit = rp(amount) if amount > 0 else ""
        rows.append(f'<tr><td>{day:02d}/11/2026</td><td>{escape(title)}</td>'
                    f'<td class="num">{debit}</td><td class="num">{credit}</td><td class="num">{rp(balance)}</td></tr>')
    final_received, final_spent = program.final
    number = account(key, program)
    return page(program, "Rekening Koran Simulasi", f"""<p>Rekening ••••{number[-4:]} · Periode 9–24 November 2026</p>
<table><tr><th>Tanggal</th><th>Uraian</th><th>Debet (Rp)</th><th>Kredit (Rp)</th><th>Saldo (Rp)</th></tr>
{''.join(rows)}<tfoot><tr><td colspan="4">Saldo akhir</td><td class="num">{rp(balance)}</td></tr></tfoot></table>
<p>Catatan awal: masuk Rp {rp(received)}, terpakai Rp {rp(spent)}.</p>
<p>Dana masuk akhir Rp {rp(final_received)} · Dana terpakai akhir Rp {rp(final_spent)}.</p>
<p>Donasi menunggu konfirmasi Rp {rp(PENDING)} belum masuk mutasi.</p>""",
                "Rekening koran latihan · Jangan transfer.")


def support(program):
    locations = "".join(f'<li><a href="{url}">{escape(place)}</a> ({lat}, {lon})</li>'
                        for place, lat, lon, url in AREAS[program.area][1])
    specifications = "".join(f"<li>{qty:g} {escape(unit)} · {escape(label)}</li>"
                             for label, qty, unit, _ in program.rows[:5])
    titles = {
        "wildlife": "Daftar perlengkapan klinik dan karantina",
        "education": "Daftar perlengkapan ruang belajar",
        "health": "Susunan tim dan persediaan kendaraan",
        "special_program": "Spesifikasi ruang aman asap",
        "infrastructure": "Spesifikasi konsep jembatan pejalan kaki",
        "psychosocial": "Susunan fasilitator dan isi kit kegiatan",
        "general_relief": "Daftar isi paket pangan",
    }
    workflow = " → ".join(map(escape, program.stages))
    return page(program, titles[program.kind], f"""<p>{escape(program.scope)}</p>
<h2>Komponen utama</h2><ul>{specifications}</ul><h2>Urutan kegiatan</h2><p>{workflow}</p>
<h2>Area skenario</h2><ul>{locations}</ul>""",
                "Titik darat referensi OpenStreetMap © kontributor · Lokasi fasilitas dalam skenario bersifat ilustratif.")


def render_documents():
    import qrcode
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        tab = browser.new_page(viewport={"width": 794, "height": 1123}, device_scale_factor=2)
        for key, program in PROGRAMS.items():
            assert 0 <= program.final[1] <= program.final[0] <= program.target
            tab.set_content(rab(program))
            tab.pdf(path=ROOT / f"{key}-rab.pdf", prefer_css_page_size=True, print_background=True)
            tab.locator("article").screenshot(path=ROOT / f"{key}-rab-1.png")
            tab.set_content(support(program))
            tab.locator("article").screenshot(path=ROOT / f"{key}-gambar.png")
            tab.set_content(statement(key, program))
            tab.pdf(path=ROOT / f"{key}-koran.pdf", prefer_css_page_size=True, print_background=True)
            qr = qrcode.make(f"SIMULASI RESCUE-NET {key}. JANGAN TRANSFER. QR INI BUKAN UNTUK PEMBAYARAN.")
            qr_path = ROOT / f"{key}-qris.png"
            from io import BytesIO
            from base64 import b64encode
            encoded = BytesIO()
            qr.save(encoded, format="PNG")
            data = b64encode(encoded.getvalue()).decode("ascii")
            tab.set_content(f'<meta charset="utf-8"><div id="qr" style="width:470px;text-align:center;'
                            'padding:20px;background:white;color:#8c231b;font:bold 22px Arial">'
                            f'QRIS CONTOH · SIMULASI<br><img src="data:image/png;base64,{data}">'
                            '<br>JANGAN TRANSFER<br>QR berisi teks peringatan</div>')
            tab.locator("#qr").screenshot(path=qr_path)
        browser.close()


def font(size):
    return ImageFont.load_default(size=size)


def render_photos(source):
    width, height = 420, 250
    sheet = Image.new("RGB", (width * 2, height * len(PROGRAMS)), "#e8edf2")
    for row, (key, program) in enumerate(PROGRAMS.items()):
        for index, label in enumerate(program.photos, 1):
            image_name = f"{key}-foto-{index}.jpg"
            src = source / image_name
            x, y = (index - 1) * width, row * height
            if src.is_file():
                with Image.open(src) as original:
                    photo = ImageOps.fit(ImageOps.exif_transpose(original).convert("RGB"), (1280, 760))
                draw = ImageDraw.Draw(photo)
                draw.rounded_rectangle((18, 18, 328, 65), radius=7, fill="#9c251d")
                draw.text((30, 26), "FOTO AI · SIMULASI", fill="white", font=font(25))
                draw.rectangle((0, 687, 1280, 760), fill="#182a3c")
                draw.text((20, 706), label, fill="white", font=font(27))
                photo.save(ROOT / image_name, quality=88)
            if (ROOT / image_name).is_file():
                with Image.open(ROOT / image_name) as stamped:
                    preview = stamped.resize((width, height - 23), Image.Resampling.LANCZOS)
                sheet.paste(preview, (x, y))
            else:
                ImageDraw.Draw(sheet).text((x + 20, y + 95), "Foto belum tersedia", fill="#182a3c", font=font(21))
            ImageDraw.Draw(sheet).text((x + 12, y + height - 21), f"{key} · {index}", fill="#182a3c", font=font(14))
    sheet.save(ROOT / "contact-sheet.png")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--photos", type=Path)
    parser.add_argument("--photos-only", action="store_true")
    args = parser.parse_args()
    if not args.photos_only:
        render_documents()
    if args.photos:
        render_photos(args.photos)
