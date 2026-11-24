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
{rect(810,837,550,104,"#ecf4f6")}{label(828,864,"BANGUN KEMBALI 21 RUMAH BADUY LUAR",19)}
{label(828,891,"Cihulu, Desa Kanekes · Leuwidamar, Lebak",16)}
{label(828,922,f"{code}  •  Rev. 0 · 24 Nov 2026  •  Dimensi dalam meter",16)}
{rect(55,866,690,48,"#fceae7")}
<text x="72" y="897" font-size="21" style="fill:#9a271d">GAMBAR KERJA SIMULASI · BUKAN UNTUK KONSTRUKSI</text>
</svg>"""


def plan():
    # 9 px/m. Tepi atap berjarak 6 m pada susunan dasar 13,2 m.
    content = [
        label(55, 110, "Tapak konseptual · 21 rumah dalam 3 baris mengikuti kontur · Utara di atas"),
        '<path d="M1200 160 Q1080 320 1180 420 T1160 742" fill="none" stroke="#a8d6e5" stroke-width="48"/>',
        label(1210, 500, "Sungai"),
        label(1280, 205, "U", 19, "middle"), label(1280, 245, "↑", 34, "middle"),
        '<rect x="135" y="209" width="880" height="409" rx="20" fill="#f4f6ec" stroke="#70856b" stroke-dasharray="10 6"/>',
        label(155, 240, "BATAS PERMUKIMAN SKENARIO", 16),
    ]
    for row in range(3):
        y = 289 + 119 * row
        content += [
            f'<path d="M75 {y+99} Q550 {y+61} 1077 {y+99}" fill="none" stroke="#c0a075" stroke-width="7"/>',
            f'<path d="M87 {y+112} Q550 {y+74} 1077 {y+112}" fill="none" stroke="#9eb08a" stroke-dasharray="7 6"/>',
        ]
        for col, offset in enumerate((19, 13, 7, 0, 7, 13, 19)):
            x = 181 + 119 * col
            top = y + offset
            content += [rect(x, top, 65, 65, "#e6ceab"),
                        label(x+32.5, top+38, f"R{row*7+col+1:02}", 17, "middle")]
    for x, name in ((229, "L1"), (312, "L2")):
        content += [rect(x, 685, 33, 33, "#c0ad7a"), label(x+16.5, 708, name, 16, "middle")]
    content += [
        horizontal(246, 300, 284, "6 m"),
        label(371, 707, "Dua leuit di luar batas rumah · badan 2,4 × 2,4 m"),
        label(920, 662, "Jalan setapak", 17),
        label(475, 748, "Kontur ilustratif (garis putus-putus) · 6 m bersih antartepi atap", 17),
        horizontal(78, 168, 756, "10 m"),
        label(56, 794, "Skema konseptual. Posisi leuit, garis sungai dan jarak akhir perlu musyawarah adat dan ukur lapangan.", 17),
    ]
    return frame("GK-01", "Denah tapak kampung", "".join(content))


def elevation():
    content = [
        label(55, 110, "TAMPAK DEPAN", 21),
        label(55, 473, "POTONGAN A–A MELINTANG", 21),
        label(785, 166, "Ukuran tipikal rumah 6 × 6 m"),
        label(785, 196, "12 titik umpak, grid 3 × 4"),
        label(785, 226, "Teras dan tangga kayu di sisi masuk"),
        label(785, 256, "Pasak kayu dan pengikat rotan / ijuk tanpa paku"),
        label(785, 286, "Tinggi umpak dan tiang menyesuaikan kontur"),
    ]
    for floor in (345, 724):
        left, right, eave = 235, 631, floor - 139
        # The upper view uses the long face; the lower view shows roof pitch.
        if floor == 345:
            ridge = 142
            content += [
                f'<path d="M195 {eave} L236 {ridge} H630 L671 {eave} Z" fill="#b88f57" stroke="#284457" stroke-width="2"/>',
                rect(left, eave, right-left, floor-eave, "#e9d6ac"),
                rect(412, floor-109, 62, 109, "#b68d60"),
                '<path d="M432 352 h30 v9 h10 v9 h10 v9 h10 v9 h-60 Z" fill="#b68d60" stroke="#284457"/>',
            ]
            for y in range(eave+10, floor, 12):
                content += [line(left, y, 411, y, 'opacity=".33"'),
                            line(475, y, right, y, 'opacity=".33"')]
        else:
            ridge = 419
            content += [
                f'<path d="M195 {eave+32} L433 {ridge} L671 {eave+32}" fill="none" stroke="#a78452" stroke-width="8"/>',
                line(left, eave, right, eave),
                line(433, ridge, 433, eave),
                rect(537, floor-79, 8, 79, "#e9d6ac"),
                line(570, 519, 762, 519), label(778, 524, "Kiray ±40° · bubungan ijuk"),
                line(right, eave, 762, eave), label(778, eave+5, "Rangka bambu terikat"),
                line(545, 662, 762, 662), label(778, 668, "Dinding bilik"),
                line(right, floor, 762, floor), label(778, floor+5, "Palupuh di atas gelagar kayu"),
                line(right, floor+39, 762, floor+39), label(778, floor+44, "Umpak batu di atas tanah asli"),
                vertical(152, eave, floor, "2,10"),
                vertical(1110, floor, floor+53, "0,80 tipikal"),
            ]
        content += [rect(left, floor-5, right-left, 12, "#aa8058"),
                    f'<path d="M172 {floor+48} L693 {floor+58}" fill="none" stroke="#647c55" stroke-width="2"/>',
                    horizontal(left, right, floor + (67 if floor == 345 else 82), "6,00")]
        for x in (left, 433, right):
            content += [rect(x-5, eave if floor == 724 else floor, 10,
                             (floor-eave if floor == 724 else 0)+36, "#ac815a"),
                        rect(x-14, floor+36, 28, 14, "#b9c1c2")]
    return frame("GK-02", "Tampak dan potongan rumah panggung", "".join(content))
