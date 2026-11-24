# RAB Sekolah Darurat Kalianda (SIMULASI) - harga satuan perkiraan Lampung 2026
RAB = [
 ("I", "PEKERJAAN PERSIAPAN", [
  ("Pembersihan lahan & pengangkutan abu vulkanik", 620, "m2", 14_000),
  ("Pengukuran & pemasangan bouwplank", 110, "m'", 62_000),
  ("Gudang bahan & direksi keet (sewa kontainer)", 1, "ls", 6_000_000),
  ("Mobilisasi & demobilisasi alat", 1, "ls", 6_500_000),
  ("Papan nama proyek & K3 (APD, rambu, P3K)", 1, "ls", 6_750_000)]),
 ("II", "PEKERJAAN TANAH & PONDASI", [
  ("Galian tanah pondasi", 28, "m3", 98_000),
  ("Pondasi telapak/umpak beton K-225 40x40", 30, "titik", 865_000),
  ("Sloof beton bertulang 15/20", 138, "m'", 292_000),
  ("Urugan pasir bawah lantai t=10 cm", 26, "m3", 315_000)]),
 ("III", "PEKERJAAN LANTAI", [
  ("Rabat beton K-175 t=7 cm", 332, "m2", 148_000),
  ("Keramik 40x40 ruang kelas & ruang guru", 256, "m2", 165_000),
  ("Keramik anti-slip 20x20 toilet", 12, "m2", 195_000)]),
 ("IV", "STRUKTUR & DINDING", [
  ("Kolom baja hollow 100x100 t=3 mm + angkur", 24, "btg", 1_480_000),
  ("Rangka dinding baja ringan C75 + GRC 9 mm luar + kalsiboard dalam", 296, "m2", 205_000),
  ("Ring balok baja C100 keliling", 138, "m'", 150_000)]),
 ("V", "PEKERJAAN ATAP", [
  ("Rangka atap baja ringan C75/C100 (truss)", 410, "m2", 165_000),
  ("Penutup atap spandek pasir 0,35 + insulasi foil", 410, "m2", 98_000),
  ("Nok, listplank GRC & talang", 1, "ls", 11_500_000)]),
 ("VI", "PLAFON", [
  ("Plafon gypsum 9 mm rangka hollow", 256, "m2", 112_000)]),
 ("VII", "KUSEN, PINTU & JENDELA", [
  ("Pintu panil kayu + kusen aluminium", 6, "unit", 1_850_000),
  ("Jendela nako/aluminium kaca 5 mm", 22, "unit", 985_000),
  ("Kunci, engsel & penggantung", 1, "ls", 3_450_000)]),
 ("VIII", "SANITASI & AIR BERSIH", [
  ("Toilet 4 bilik (kloset jongkok, bak, kran)", 4, "bilik", 2_650_000),
  ("Sumur bor dalam 40 m + pompa", 1, "unit", 14_500_000),
  ("Tandon 2.200 L + menara besi 4 m", 1, "unit", 8_600_000),
  ("Septic tank biofilter 2 m3", 1, "unit", 8_900_000),
  ("Pipa air bersih & air kotor", 1, "ls", 7_350_000),
  ("Tempat cuci tangan 6 kran", 1, "unit", 3_600_000)]),
 ("IX", "INSTALASI LISTRIK", [
  ("Titik lampu + lampu LED 18 W", 40, "titik", 325_000),
  ("Stop kontak & kipas angin dinding", 14, "titik", 520_000),
  ("Panel MCB + penyambungan PLN 3.500 VA", 1, "ls", 7_200_000)]),
 ("X", "PENGECATAN", [
  ("Cat dinding dalam & luar (2 lapis)", 592, "m2", 28_000),
  ("Cat plafon", 256, "m2", 22_000)]),
 ("XI", "MEBEL & PERLENGKAPAN BELAJAR", [
  ("Meja + kursi siswa (tunggal)", 160, "set", 495_000),
  ("Meja + kursi guru", 6, "set", 1_450_000),
  ("Papan tulis whiteboard 120x240", 4, "unit", 865_000),
  ("Lemari arsip/buku", 5, "unit", 1_950_000),
  ("Buku bacaan & alat peraga", 1, "ls", 9_500_000),
  ("APAR 3 kg + kotak P3K", 5, "paket", 720_000)]),
]
def totals():
    sub = [(k, t, sum(q*h for _, q, _, h in items)) for k, t, items in RAB]
    s = sum(x[2] for x in sub)
    pend = round(s * 0.02, -3); adm = round(s * 0.005, -3); cad = round(s * 0.02, -3)
    tot = s + pend + adm + cad
    return sub, s, pend, adm, cad, tot
if __name__ == "__main__":
    sub, s, pend, adm, cad, tot = totals()
    for k,t,v in sub: print(k,t,f"{v:,}")
    print("sub",f"{s:,}","pend",pend,"adm",adm,"cad",cad,"TOTAL",f"{tot:,}")
