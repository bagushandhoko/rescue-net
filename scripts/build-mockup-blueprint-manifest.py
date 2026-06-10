from pathlib import Path
import json
import urllib.parse

IMG_DIR = Path("assets/img/mockup")
OUT = Path("assets/js/mockup-manifest.js")

IMG_DIR.mkdir(parents=True, exist_ok=True)

def web_path(filename):
    # encode spasi, &, huruf, dll agar aman di browser
    return "../assets/img/mockup/" + urllib.parse.quote(filename)

files = {p.name.lower(): p.name for p in IMG_DIR.iterdir() if p.suffix.lower() in [".png", ".jpg", ".jpeg", ".webp"]}

def pick(*names):
    for name in names:
        found = files.get(name.lower())
        if found:
            return web_path(found), found
    return "../assets/img/mockup/placeholder-mockup.png", None

menus = [
    ("welcome", "01 Welcome / Landing", "Tampilan awal Rescue-Net sebelum masuk ke sistem.", ["welcome page rescue-net.png"]),
    ("active-disasters", "02 Active Disasters", "Daftar bencana aktif dan pintu masuk ke War Room.", ["bencana aktif.png"]),
    ("war-room", "03 War Room / Command Center", "Command center untuk satu bencana aktif.", ["war room.png"]),
    ("login", "04 Login & Registrasi", "Login, registrasi user, dan onboarding awal.", ["login & registrasi.png"]),
    ("organisasi-posko", "05 Organisasi & Posko", "Struktur organisasi, posko resmi, dan posko komunitas.", ["organisasi & posko.png"]),
    ("registrasi-verifikasi-posko", "06 Registrasi & Verifikasi Posko", "Alur registrasi dan validasi/verifikasi posko.", ["registrasi & verifikasi posko.png"]),
    ("posko-logistik", "07 Posko Logistik", "Kebutuhan, stok, supply-demand, dan ringkasan logistik posko.", ["posko logistik.png"]),
    ("distribusi", "08 Manajemen Distribusi", "Distribusi bantuan, transport, pickup, routing, dan delivery.", ["manajemen distribusi.png"]),
    ("dapur-umum", "09 Dapur Umum", "Produksi makanan, kebutuhan dapur, dan stok bahan.", ["dapur umum.png"]),
    ("shelter", "10 Shelter & Akomodasi", "Kapasitas shelter, akomodasi, pengungsi, dan kebutuhan.", ["shelter & akomodasi.png"]),
    ("search-found", "11 Search & Found", "Orang hilang, orang ditemukan, matching, dan reunifikasi.", ["search & found.png"]),
    ("program-khusus", "12 Program Khusus", "Program bantuan khusus: PLTS, air bersih, obat, dan infrastruktur darurat.", ["program khusus.png"]),
    ("relawan", "13 Manajemen Relawan", "Relawan, skill, penugasan, ketersediaan, dan koordinasi.", ["manajemen relawan.png"]),
    ("alat-kerja", "14 Manajemen Alat Kerja", "Alat berat, kendaraan, generator, pompa, operator, dan pemakaian.", ["manajemen alat kerja.png"]),
    ("sumber-daya", "15 Profil Sumber Daya", "Sumber daya organisasi/posko: asset, kapasitas, alat, dan fasilitas.", ["profil sumber daya.png"]),
    ("evidence-centre", "16 Evidence Centre", "Pusat bukti foto, dokumen, evidence, dan source tracking.", ["evidence centre.png"]),
    ("verification-approval", "17 Verification & Approval", "Approval, validasi, audit, dan verifikasi data penting.", ["verification & approval.png"]),
    ("komunikasi", "18 Alat Komunikasi", "Radio, kontak, channel komunikasi, PIC, dan directory.", ["alat komunikasi.png"]),
    ("mobile", "19 Tampilan HP / Mobile Field App", "Kompilasi tampilan mobile untuk petugas HP di lapangan.", ["kompilasi tampilan hp.png"]),
]

items = []
used = set()

for key, title, subtitle, candidates in menus:
    image, matched = pick(*candidates)
    if matched:
        used.add(matched.lower())
    items.append({
        "key": key,
        "title": title,
        "subtitle": subtitle,
        "image": image,
        "caption": f"File: {matched}" if matched else "Image belum ditemukan di assets/img/mockup.",
        "status": "matched" if matched else "missing",
        "matched_file": matched
    })

unused = [p.name for p in IMG_DIR.iterdir() if p.suffix.lower() in [".png", ".jpg", ".jpeg", ".webp"] and p.name.lower() not in used and p.name != "placeholder-mockup.png"]

OUT.write_text(
    "window.RN_MOCKUP_ITEMS = " + json.dumps(items, ensure_ascii=False, indent=2) + ";\n"
    "window.RN_MOCKUP_UNUSED_IMAGES = " + json.dumps(unused, ensure_ascii=False, indent=2) + ";\n"
)

print("OK manifest generated:", OUT)
for item in items:
    print(item["title"], "=>", item["matched_file"] or "NO MATCH")
if unused:
    print("UNUSED:", ", ".join(unused))
