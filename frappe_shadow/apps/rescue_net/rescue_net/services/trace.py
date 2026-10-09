"""Kode lacak kiriman (QR). Token acak per Flow menggantikan potongan nama (yang dapat ditebak sebagian dan
dicari O(n)). Kode lama `RN-` + 8 karakter terakhir nama tetap diterima (label yang sudah tercetak)."""

import secrets

import frappe

ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"  # tanpa 0/O/1/I/L agar mudah dibaca dari label cetak
LENGTH = 8


def new_token():
    return "".join(secrets.choice(ALPHABET) for _ in range(LENGTH))


def unique_token():
    for _ in range(20):
        t = new_token()
        if not frappe.db.exists("RN Distribution Flow", {"trace_token": t}):
            return t
    frappe.throw("Gagal membuat kode lacak unik.")


def normalize(code):
    """`rn-ab23cdef` / `AB23CDEF` -> `AB23CDEF` (huruf besar, tanpa awalan)."""
    code = str(code or "").strip().upper()
    if code.startswith("RN-"):
        code = code[3:]
    return code.strip()
