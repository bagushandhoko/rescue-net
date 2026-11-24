"""Skema arsitektur simulasi dalam SVG, dirender menjadi PNG oleh gen_docs.py."""


def label(x, y, text, size=18, anchor="start"):
    return f'<text x="{x}" y="{y}" font-size="{size}" text-anchor="{anchor}">{text}</text>'


def rect(x, y, w, h, fill="#fff"):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}" stroke="#284457" stroke-width="2"/>'


def line(x1, y1, x2, y2, style=""):
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#284457" {style}/>'


def horizontal(x1, x2, y, text):
    return (line(x1, y, x2, y) + line(x1, y-8, x1, y+8)
            + line(x2, y-8, x2, y+8) + label((x1+x2)/2, y-7, text, 16, "middle"))


def vertical(x, y1, y2, text):
    return (line(x, y1, x, y2) + line(x-8, y1, x+8, y1)
            + line(x-8, y2, x+8, y2) + label(x+12, (y1+y2)/2+6, text, 16))


def frame(code, title, content):
    return f"""<!doctype html><meta charset="utf-8">
<style>body{{margin:0}}text{{font-family:Arial;fill:#193247}}</style>
<svg xmlns="http://www.w3.org/2000/svg" width="1400" height="980">
{rect(16,16,1368,948)}{label(55,72,title,32)}
{content}
{rect(810,837,550,104,"#ecf4f6")}{label(828,864,"UI PEDULI — REKONSTRUKSI FASILITAS BELAJAR",19)}
{label(828,891,"SD Tunas Pesisir (fiktif) · Johan Pahlawan, Aceh Barat",16)}
{label(828,922,f"{code}  •  Rev. 0 · 24 Nov 2026  •  Dimensi dalam mm",16)}
{rect(55,866,690,48,"#fceae7")}
<text x="72" y="897" font-size="21" style="fill:#9a271d">GAMBAR KERJA SIMULASI · JANGAN DIGUNAKAN MEMBANGUN</text>
</svg>"""


def plan():
    content = [label(55, 107, "Blok rehabilitasi 168 m² + selasar 42 m². Empat garis grid dengan delapan kolom beton eksisting.")]
    for i, title in enumerate(("KELAS 1", "KELAS 2", "PERPUSTAKAAN")):
        x = 180 + i*294
        content.extend([
            rect(x, 260, 294, 336, "#eef5fa"), rect(x, 596, 294, 84, "#e9eae4"),
            label(x+147, 414, title, 24, "middle"),
            label(x+147, 448, "7 × 8 m · 32 siswa" if i < 2 else "7 × 8 m · ruang baca", 17, "middle"),
            horizontal(x, x+294, 215, "7.000"),
            rect(x+207, 593, 42, 6), line(x+249, 596, x+249, 554),
            f'<path d="M{x+207},596 a42,42 0 0,1 42,-42" stroke="#284457" fill="none"/>',
        ])
        for wx, wy in ((44, 257), (150, 257), (33, 593), (119, 593)):
            content.append(rect(x+wx, wy, 63, 6, "#71b6cc"))
    for x in (180, 474, 768, 1062):
        for y in (260, 596):
            content.append(rect(x-8, y-8, 16, 16, "#345e79"))
    content += [
        horizontal(180, 1062, 166, "21.000"), vertical(1100, 260, 596, "8.000"),
        vertical(1100, 596, 680, "2.000"), label(620, 648, "SELASAR · +0,35 m", 19, "middle"),
        line(684, 232, 684, 711, 'stroke-dasharray="9 6"'), label(696, 246, "A"),
        label(696, 716, "A"), rect(116, 626, 64, 54, "#e9eae4"), label(69, 710, "Ramp masuk", 16),
        label(1230, 205, "UTARA", 16, "middle"), label(1230, 241, "↑", 32, "middle"),
        rect(442, 764, 16, 16, "#345e79"), label(472, 778, "Kolom dijaket"),
        rect(658, 767, 32, 8, "#71b6cc"), label(705, 778, "Jendela 1.500 × 1.200"),
    ]
    return frame("GK-01", "Denah blok kelas dan perpustakaan", "".join(content))


def elevation():
    content = [
        label(55, 111, "TAMPAK DEPAN · Dua kelas dan perpustakaan"),
        rect(155, 210, 882, 141, "#eef5fa"), rect(155, 351, 882, 19, "#ddd"),
        '<path d="M134 210 L189 139 H1003 L1058 210 Z" fill="#b6cbd1" stroke="#284457" stroke-width="2"/>',
        horizontal(155, 1037, 408, "21.000"), label(1090, 356, "+0,45 lantai"),
        label(1090, 372, "±0,00 halaman", 16), label(1090, 218, "+3,80 ring balok"),
    ]
    for i in range(3):
        x = 155 + i*294
        for offset in (33, 119):
            content.append(rect(x+offset, 252, 63, 50, "#a9d5e3"))
        content.append(rect(x+207, 263, 42, 88, "#fff"))
    for x in (155, 449, 743, 1037):
        content.append(rect(x-6, 210, 12, 141, "#345e79"))
    content += [
        label(55, 466, "POTONGAN A–A · Rangka beton bertulang eksisting diperkuat"),
        line(134, 748, 690, 748), rect(180, 729, 336, 19, "#ddd"),
        rect(516, 733, 84, 15, "#e9eae4"), rect(172, 588, 16, 141, "#345e79"),
        rect(508, 588, 16, 141, "#345e79"), rect(180, 581, 336, 14, "#345e79"),
        rect(157, 751, 46, 25, "#ccc"), rect(493, 751, 46, 25, "#ccc"),
        '<path d="M169 603 L389 496 L608 603" fill="none" stroke="#284457" stroke-width="5"/>',
        line(180, 603, 516, 603, 'stroke-dasharray="8 5"'),
        horizontal(180, 516, 815, "8.000"), horizontal(516, 600, 815, "2.000"),
        vertical(650, 588, 729, "3.350"),
        line(485, 536, 775, 529), label(788, 534, "Atap metal berinsulasi · kemiringan sekitar 26°"),
        line(470, 586, 775, 581), label(788, 586, "Ring balok beton · +3,80 m"),
        line(515, 660, 775, 652), label(788, 657, "Jaket kolom beton bertulang"),
        line(517, 763, 775, 768), label(788, 773, "Fondasi eksisting dipertahankan setelah asesmen"),
        label(788, 804, "Ukuran perkuatan ditentukan lewat desain struktur proyek nyata.", 15),
    ]
    return frame("GK-02", "Tampak depan dan potongan A–A", "".join(content))
