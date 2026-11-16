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


# Endpoint Nala tetap tersedia melalui rescue_net.ai.analysis untuk frontend.
from rescue_net.ai.analysis_nala import (  # noqa: E402,F401
    triase_laporan, prakiraan_stok, dampak_gempa, cek_kejanggalan,
)
