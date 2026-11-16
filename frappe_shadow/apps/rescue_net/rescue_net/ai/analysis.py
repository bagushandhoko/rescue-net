"""Analisis AI lanjutan (Suri 2026-11-16, owner: "perkaya menu AI Analysis dengan kemampuan yang susah tanpa AI").

Fondasi bersama untuk semua fitur:
- _kunci(): login + kunci AI (pribadi / organisasi) persis seperti ai.chat.ask.
- _simpan(): simpan hasil ke RN AI Report (riwayat + ekspor).
- daftar_laporan_ai / baca_laporan_ai: riwayat dengan kontrol akses.
Fitur: 1 sitrep_ai, 8 tanya_berujukan (Suri); 2,3,5,7 (Nala) ; 4 foto, 6 rencana kirim (Suri, menyusul).
Semua fitur HANYA menulis RN AI Report (saran). Tidak ada data operasional yang diubah AI.
"""

import json

import frappe
from frappe.utils import cint, now_datetime

from rescue_net.access_policy import is_system_manager, rn_actor
from rescue_net.ai.chat import _llm_chat
from rescue_net.ai.common import _assert_self, _prov
from rescue_net.ai.keys import _resolve_ai_key

DOCTYPE = "RN AI Report"
JENIS = ("sitrep", "triase_laporan", "prakiraan_stok", "tanya_jawab", "gempa", "kejanggalan", "foto", "rencana_kirim")

ATURAN_UMUM = """
Kamu adalah analis Rescue-Net (sistem koordinasi bencana Indonesia).
Tulis dalam Bahasa Indonesia yang sederhana dan jelas.
HANYA gunakan fakta dari data JSON yang diberikan; jangan mengarang angka, nama, atau lokasi.
Bila data tidak cukup, katakan terus terang apa yang kurang.
Jangan menampilkan nomor telepon, alamat pribadi, atau identitas pasien/korban.
Data bertanda [SIMULASI] adalah latihan; sebutkan itu bila relevan.
"""


def _kunci(user_id, provider="auto", organization_id=None):
    """Login + kunci AI. Kembalikan dict yang dipakai _tanya/_simpan."""
    _actor, user_id = _assert_self(user_id)
    provider = _prov(provider, allow_auto=True)
    api_key, model_name, key_source, owner_type, owner_id, provider = _resolve_ai_key(
        user_id, provider, organization_id)
    if not api_key and provider != "local":
        frappe.throw("Belum ada kunci AI aktif untuk konteks ini (pribadi atau organisasi yang dipilih). "
                     "Tambahkan di AI Settings.")
    return {"user_id": user_id, "api_key": api_key, "model_name": model_name, "key_source": key_source,
            "owner_type": owner_type, "owner_id": owner_id, "provider": provider}


def _tanya(k, system, isi, disaster_event=None, feature=None, json_mode=False, images=None, temperature=0.2):
    """Satu panggilan AI lewat _llm_chat (anggaran, batas, log biaya ikut)."""
    if isinstance(isi, str):
        isi = [isi]
    return _llm_chat(k["api_key"], k["model_name"], ATURAN_UMUM + "\n" + system, isi,
                     k["user_id"], k["key_source"], k["owner_type"], k["owner_id"], k["provider"],
                     disaster_event=disaster_event, q_chars=sum(len(x) for x in isi), temperature=temperature,
                     json_mode=json_mode, feature=feature, images=images)


def _simpan(k, jenis, judul, isi_md, disaster_event=None, question=None, structured=None, sources=None):
    assert jenis in JENIS, jenis
    doc = frappe.get_doc({
        "doctype": DOCTYPE, "report_type": jenis, "title": (judul or jenis)[:140],
        "disaster_event": disaster_event or "", "question": (question or "")[:2000],
        "content": isi_md or "", "structured": json.dumps(structured, default=str, ensure_ascii=False) if structured is not None else "",
        "sources": json.dumps(sources, default=str, ensure_ascii=False) if sources is not None else "",
        "user_id": k["user_id"], "owner_type": k["owner_type"] or "", "owner_id": k["owner_id"] or "",
        "provider": k["provider"] or "", "model_name": k["model_name"] or "",
    })
    doc.insert(ignore_permissions=True)
    return doc.name


def _boleh_lihat(row, user_id, actor):
    if is_system_manager():
        return True
    if row.get("user_id") == user_id:
        return True
    org = getattr(actor, "organization", None) or (actor.get("organization") if hasattr(actor, "get") else None)
    return row.get("owner_type") == "organization" and org and row.get("owner_id") == org


def _ringkas(row, isi=False):
    out = {k: row.get(k) for k in ("name", "report_type", "title", "disaster_event", "question", "provider",
                                    "model_name", "owner_type")}
    out["dibuat"] = str(row.get("creation") or "")[:16]
    if isi:
        for k in ("content", "structured", "sources"):
            v = row.get(k) or ""
            if k != "content" and v:
                try:
                    v = json.loads(v)
                except Exception:
                    pass
            out[k] = v
    return out


@frappe.whitelist()
def daftar_laporan_ai(user_id, disaster_event_id=None, report_type=None, limit=30):
    actor, user_id = _assert_self(user_id)
    filters = {}
    if disaster_event_id:
        filters["disaster_event"] = disaster_event_id
    if report_type:
        filters["report_type"] = report_type
    rows = frappe.get_all(DOCTYPE, filters=filters, order_by="creation desc", limit_page_length=200,
                          fields=["name", "report_type", "title", "disaster_event", "question", "provider",
                                  "model_name", "owner_type", "owner_id", "user_id", "creation"])
    rows = [r for r in rows if _boleh_lihat(r, user_id, actor)][: max(1, min(cint(limit) or 30, 100))]
    return [_ringkas(r) for r in rows]


@frappe.whitelist()
def baca_laporan_ai(user_id, name):
    actor, user_id = _assert_self(user_id)
    if not frappe.db.exists(DOCTYPE, name):
        frappe.throw("Laporan AI tidak ditemukan.", frappe.DoesNotExistError)
    row = frappe.get_doc(DOCTYPE, name).as_dict()
    if not _boleh_lihat(row, user_id, actor):
        frappe.throw("Tidak boleh membuka laporan AI ini.", frappe.PermissionError)
    return _ringkas(row, isi=True)


# ---------------------------------------------------------------- Fitur 1: SITREP AI
SISTEM_SITREP = """
Tugas: tulis SITREP naratif (gaya OCHA) dari data SITREP Rescue-Net.
Format markdown dengan judul bagian persis:
## Ringkasan Eksekutif  (3-5 kalimat: skala, jiwa terdampak, hal paling mendesak)
## Situasi Terkini
## Perubahan Sejak Laporan Sebelumnya
## Kebutuhan Mendesak dan Kesenjangan  (tabel: kebutuhan | posko | kekurangan | prioritas)
## Logistik dan Distribusi
## Layanan (Kesehatan, Shelter, Dapur Umum)
## Kelompok Rentan
## Risiko 24-72 Jam ke Depan  (perkiraan berdasarkan tren data; tandai sebagai perkiraan)
## Rekomendasi Tindakan  (daftar bernomor, urut prioritas, sebut siapa yang sebaiknya bertindak)
## Catatan Data  (data yang kurang / perlu diverifikasi)
Setiap angka penting diberi rujukan bagian data dalam kurung siku, misal [situasi.jiwa_terdampak].
"""


@frappe.whitelist()
def sitrep_ai(user_id, disaster_event_id, hours=24, provider="auto", organization_id=None):
    from rescue_net.api_sitrep import sitrep
    k = _kunci(user_id, provider, organization_id)
    hours = max(1, min(cint(hours) or 24, 168))
    data = sitrep(disaster_event_id, hours)
    md = _tanya(k, SISTEM_SITREP, ["Data SITREP Rescue-Net (JSON):\n" + json.dumps(data, default=str, ensure_ascii=False),
                                   f"Tulis SITREP naratif untuk periode {hours} jam terakhir."],
                disaster_event=disaster_event_id, feature="ai_sitrep", temperature=0.2)
    judul = "SITREP AI %s - %s" % ((data.get("bencana") or {}).get("title") or disaster_event_id, str(now_datetime())[:16])
    name = _simpan(k, "sitrep", judul, md, disaster_event_id, question=f"{hours} jam",
                   sources={"nomor": data.get("nomor"), "periode": data.get("periode")})
    return {"name": name, "title": judul, "content": md, "provider": k["provider"], "model_name": k["model_name"]}


# ---------------------------------------------------------------- Fitur 8: tanya jawab berujukan
SISTEM_TANYA = """
Tugas: jawab pertanyaan pengguna dari data konteks Rescue-Net.
Setiap fakta WAJIB diberi rujukan ID data sumber dalam kurung siku, misal [RN-NEED-0012] atau
[posko: SIM-LR-POSKO-LD3]. Gunakan nilai field name/id persis dari data.
Format markdown: jawaban singkat dulu, lalu rincian, lalu "Langkah yang disarankan".
Akhiri dengan bagian "Rujukan" berisi daftar ID yang dipakai.
"""


@frappe.whitelist()
def tanya_berujukan(user_id, disaster_event_id, question, provider="auto", organization_id=None):
    from rescue_net.ai.context import context
    question = (question or "").strip()
    if not question:
        frappe.throw("Pertanyaan wajib diisi.")
    k = _kunci(user_id, provider, organization_id)
    ctx = context(disaster_event_id)
    batas = {"summary": None, "alerts": 30, "recommendations": 30, "stock_summary": 80, "logistic_needs": 80,
             "aid_offers": 60, "distribution_flows": 60, "kitchen_meal_productions": 40, "medical_cases": 40,
             "shelter_occupancies": 40, "shelter_needs": 40, "resource_profiles": 60, "recovery_projects": 40,
             "community_reports_predicted_needs": 40}
    compact = {kk: (ctx.get(kk) if n is None else (ctx.get(kk) or [])[:n]) for kk, n in batas.items()}
    md = _tanya(k, SISTEM_TANYA, ["Data konteks Rescue-Net (JSON):\n" + json.dumps(compact, default=str, ensure_ascii=False),
                                  "Pertanyaan: " + question],
                disaster_event=disaster_event_id, feature="ai_tanya_berujukan")
    name = _simpan(k, "tanya_jawab", question[:120], md, disaster_event_id, question=question)
    return {"name": name, "title": question[:120], "content": md, "provider": k["provider"], "model_name": k["model_name"]}


# ---------------------------------------------------------------- Fitur 4: analisis foto bukti (vision)
SISTEM_FOTO = """
Tugas: nilai SATU foto dari lokasi bencana untuk petugas posko.
Balas HANYA JSON valid dengan kunci:
{"jenis_bencana": str, "tingkat_kerusakan": "tidak_tampak|ringan|sedang|berat",
 "perkiraan_tinggi_air_cm": int atau null, "bahaya": [str], "kebutuhan_terlihat": [str],
 "orang_butuh_bantuan_terlihat": true/false, "label": [str],
 "perlu_dicek": [str],  // mis. foto tampak lama, hasil edit, tidak relevan, bukan lokasi bencana
 "ringkasan": str}
Jangan mengenali atau menyebut identitas orang di foto. Bila ragu, katakan ragu.
"""
_MIME_FOTO = ("image/jpeg", "image/png", "image/webp")


@frappe.whitelist(methods=["POST"])
def analisis_foto(user_id, disaster_event_id, image_b64, mime="image/jpeg", note="", provider="auto", organization_id=None):
    from rescue_net.services import llm as _llm
    mime = (mime or "image/jpeg").lower()
    if mime not in _MIME_FOTO:
        frappe.throw("Format foto harus JPG, PNG, atau WEBP.")
    image_b64 = (image_b64 or "").strip()
    if not image_b64 or len(image_b64) > 5_600_000:
        frappe.throw("Foto kosong atau lebih dari 4 MB.")
    k = _kunci(user_id, provider, organization_id)
    teks = "Catatan petugas: " + (note or "-")[:500]
    raw = _tanya(k, SISTEM_FOTO, [teks], disaster_event=disaster_event_id, feature="ai_foto",
                 json_mode=k["provider"] != "anthropic", images=[{"mime": mime, "b64": image_b64}], temperature=0.1)
    try:
        hasil = _llm.parse_json(raw) or {}
    except Exception:
        hasil = {"ringkasan": raw}
    daftar = lambda xs: "\n".join("- " + str(x) for x in (xs or [])) or "- (tidak ada)"
    md = "\n".join([
        "## Ringkasan", str(hasil.get("ringkasan") or "-"),
        "## Penilaian",
        f"- Jenis bencana: **{hasil.get('jenis_bencana') or '-'}**",
        f"- Tingkat kerusakan: **{hasil.get('tingkat_kerusakan') or '-'}**",
        f"- Perkiraan tinggi air: **{hasil.get('perkiraan_tinggi_air_cm') if hasil.get('perkiraan_tinggi_air_cm') is not None else '-'} cm**",
        f"- Orang butuh bantuan terlihat: **{'ya' if hasil.get('orang_butuh_bantuan_terlihat') else 'tidak'}**",
        "## Bahaya", daftar(hasil.get("bahaya")),
        "## Kebutuhan yang terlihat", daftar(hasil.get("kebutuhan_terlihat")),
        "## Label", ", ".join(map(str, hasil.get("label") or [])) or "-",
        "## Perlu dicek", daftar(hasil.get("perlu_dicek")),
    ])
    judul = "Analisis foto - " + ((note or "").strip()[:60] or str(now_datetime())[:16])
    name = _simpan(k, "foto", judul, md, disaster_event_id, question=note, structured=hasil,
                   sources={"mime": mime, "ukuran_kb": int(len(image_b64) * 3 / 4 / 1024), "foto_disimpan": False})
    return {"name": name, "title": judul, "content": md, "structured": hasil,
            "provider": k["provider"], "model_name": k["model_name"]}


# ---------------------------------------------------------------- Fitur 6: rencana pengiriman
import math as _math


def _jarak_km(a, b):
    """Haversine; a,b = (lat, lon). None bila koordinat tidak lengkap."""
    try:
        la1, lo1, la2, lo2 = map(float, (a[0], a[1], b[0], b[1]))
    except (TypeError, ValueError):
        return None
    if not (la1 or lo1) or not (la2 or lo2):
        return None
    r = _math.radians
    h = _math.sin(r(la2 - la1) / 2) ** 2 + _math.cos(r(la1)) * _math.cos(r(la2)) * _math.sin(r(lo2 - lo1) / 2) ** 2
    return round(6371 * 2 * _math.asin(min(1, _math.sqrt(h))), 1)


def _kunci_barang(row):
    return (row.get("canonical_item") or row.get("item_name") or "").strip().lower()


def kandidat_kirim(disaster_event_id, maks_kebutuhan=40):
    """DETERMINISTIK: kebutuhan terbuka x stok tersedia di posko lain x armada tersedia."""
    from rescue_net.reference_resolver import resolve_disaster_event
    ev = resolve_disaster_event(disaster_event_id) or disaster_event_id
    posko = {p.name: p for p in frappe.get_all("RN Posko", filters={"disaster_event": ev},
                                               fields=["name", "title", "latitude", "longitude", "organization"])}
    needs = frappe.get_all("RN Logistic Need", filters={"disaster_event": ev, "need_status": "open"},
                           fields=["name", "posko", "item_name", "canonical_item", "quantity", "unit", "urgency", "needed_before"],
                           order_by="creation desc", limit_page_length=300)
    stok = frappe.get_all("RN Stock Observation", filters={"disaster_event": ev, "stock_state": "available"},
                          fields=["name", "posko", "item_name", "canonical_item", "quantity", "unit", "observed_at"],
                          order_by="observed_at desc", limit_page_length=1000)
    terbaru = {}
    for s in stok:  # stok terbaru per (posko, barang)
        terbaru.setdefault((s.posko, _kunci_barang(s)), s)
    armada = frappe.get_all("RN Transport Space", filters={"disaster_event": ev, "transport_status": ["in", ["available", "reserved"]]},
                            fields=["name", "title", "coordination_posko", "transport_type", "capacity_weight_kg",
                                    "capacity_committed_kg", "route_origin", "route_destination", "departure_at",
                                    "position_lat", "position_lng"], limit_page_length=200)
    hasil = []
    for n in needs[: int(maks_kebutuhan)]:
        tujuan = posko.get(n.posko)
        if not tujuan:
            continue
        kb = _kunci_barang(n)
        sumber = []
        for (pk, barang), s in terbaru.items():
            if barang != kb or pk == n.posko or not s.quantity or pk not in posko:
                continue
            asal = posko[pk]
            sumber.append({"posko_asal": pk, "nama_asal": asal.title, "stok": s.quantity, "unit": s.unit,
                           "jarak_km": _jarak_km((asal.latitude, asal.longitude), (tujuan.latitude, tujuan.longitude))})
        sumber.sort(key=lambda x: (x["jarak_km"] is None, x["jarak_km"] or 0))
        sumber = sumber[:3]
        calon_armada = []
        for a in armada:
            sisa = (a.capacity_weight_kg or 0) - (a.capacity_committed_kg or 0)
            if a.capacity_weight_kg and sisa <= 0:
                continue  # armada sudah penuh
            dekat = None
            for s in sumber:
                asal = posko[s["posko_asal"]]
                d = 0 if a.coordination_posko == s["posko_asal"] else _jarak_km((a.position_lat, a.position_lng), (asal.latitude, asal.longitude))
                if d is not None and (dekat is None or d < dekat):
                    dekat = d
            calon_armada.append({"armada": a.name, "judul": a.title, "jenis": a.transport_type, "sisa_kg": sisa,
                                 "dari": a.route_origin, "ke": a.route_destination,
                                 "berangkat": str(a.departure_at or "")[:16], "jarak_ke_sumber_km": dekat})
        calon_armada.sort(key=lambda x: (x["jarak_ke_sumber_km"] is None, x["jarak_ke_sumber_km"] or 0))
        hasil.append({"kebutuhan": n.name, "posko_tujuan": n.posko, "nama_tujuan": tujuan.title,
                      "barang": n.item_name, "jumlah": n.quantity, "unit": n.unit, "urgensi": n.urgency,
                      "batas_waktu": str(n.needed_before or "")[:16], "sumber": sumber, "armada": calon_armada[:3]})
    return hasil


SISTEM_KIRIM = """
Tugas: susun USULAN rencana pengiriman dari kandidat hitungan sistem (kebutuhan terbuka, posko sumber
yang punya stok barang sama + jarak, armada tersedia). Jangan menambah sumber/armada di luar data.
Format markdown:
## Ringkasan
## Rencana Pengiriman  (tabel: No | Barang | Jumlah | Dari posko | Ke posko | Armada | Alasan)
## Kebutuhan Tanpa Sumber  (kebutuhan yang tidak ada stoknya di posko lain -> sarankan cari donor)
## Catatan  (risiko, urutan prioritas, hal yang perlu dikonfirmasi pengelola posko)
Utamakan urgensi tinggi dan batas waktu terdekat; jangan kosongkan stok posko sumber (sisakan cadangan).
Tegaskan: rencana ini perlu disetujui pengelola posko sebelum dijalankan.
"""


@frappe.whitelist()
def rencana_kirim(user_id, disaster_event_id, provider="auto", organization_id=None):
    k = _kunci(user_id, provider, organization_id)
    kandidat = kandidat_kirim(disaster_event_id)
    if not kandidat:
        md = "## Ringkasan\nTidak ada kebutuhan terbuka yang bisa dicocokkan saat ini."
    else:
        md = _tanya(k, SISTEM_KIRIM, ["Kandidat hitungan sistem (JSON):\n" + json.dumps(kandidat, default=str, ensure_ascii=False),
                                       "Susun usulan rencana pengiriman."],
                    disaster_event=disaster_event_id, feature="ai_rencana_kirim")
    judul = "Rencana pengiriman - " + str(now_datetime())[:16]
    name = _simpan(k, "rencana_kirim", judul, md, disaster_event_id, structured=kandidat)
    return {"name": name, "title": judul, "content": md, "structured": kandidat,
            "provider": k["provider"], "model_name": k["model_name"]}


# Endpoint Nala tetap tersedia melalui rescue_net.ai.analysis untuk frontend.
from rescue_net.ai.analysis_nala import (  # noqa: E402,F401
    triase_laporan, prakiraan_stok, dampak_gempa, cek_kejanggalan,
)
