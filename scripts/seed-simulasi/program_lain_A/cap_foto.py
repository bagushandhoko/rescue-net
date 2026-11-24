"""Pasang cap pada file JPG yang sudah diperiksa. Masukkan direktori pilihan."""
import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

from prog_a_data import programs

ROOT = Path(__file__).resolve().parent
CAPTIONS = {
    "24ea13d2e0a8": ("Kit untuk sesi bermain anak", "Persiapan kartu kegiatan bermain"),
    "2e3020faa479": ("Gambaran kondisi awal atap posko", "Rincian peralatan PLTS posko"),
    "6e945dc35c1e": ("Contoh buah untuk dapur layanan", "Persiapan bahan di dapur PMT"),
    "83d25e5a39f5": ("Ruang penyiapan paket kebersihan keluarga", "Penyiapan paket kebersihan"),
    "d346ff392f8e": ("Area penampungan wadah logistik", "Penyortiran isi paket posko"),
    "d743d5d52ba8": ("Ruang penyiapan titik layanan air", "Rincian wadah dan perpipaan air"),
    "e065907513c7": ("Gambaran perlengkapan klinik bergerak", "Kendaraan untuk layanan keliling"),
    "eb590551280a": ("Gambaran ruang belajar bergilir", "Penataan meja untuk kegiatan siswa"),
    "ed5431a4c682": ("Contoh persediaan pangan posko", "Gambaran pengemasan sembako"),
}


def font(size, bold=False):
    filename = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    try:
        return ImageFont.truetype(filename, size)
    except OSError:
        return ImageFont.load_default(size=size)


def stamp(source, destination, caption):
    with Image.open(source) as raw:
        photo = ImageOps.fit(ImageOps.exif_transpose(raw).convert("RGB"), (1280, 760))
    draw = ImageDraw.Draw(photo)
    bold = font(23, bold=True)
    regular = font(17)
    draw.rounded_rectangle((16, 16, 283, 60), radius=6, fill="#a51e22")
    draw.text((28, 24), "FOTO AI · SIMULASI", font=bold, fill="white")
    draw.rectangle((0, 670, 1280, 760), fill="#152630")
    draw.text((20, 683), caption, font=bold, fill="white")
    draw.text((20, 720), "Gambar buatan AI untuk latihan Rescue-Net", font=regular, fill="#e8f1f5")
    destination.parent.mkdir(exist_ok=True)
    photo.save(destination, quality=88, optimize=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("approved", type=Path)
    args = parser.parse_args()
    for p in programs():
        key = p["key"]
        for index, caption in enumerate(CAPTIONS[key]):
            source = args.approved / f"{key}-{index}.jpg"
            if source.is_file():
                stamp(source, ROOT / key / f"foto-{index}.jpg", caption)
