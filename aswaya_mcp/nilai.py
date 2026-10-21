"""Buku nilai satu kursus lewat gradereport_user_get_grade_items.

Dengan userid=0, Moodle mengembalikan item nilai semua mahasiswa yang bisa
dilihat akun ini. Hasilnya disusun ulang supaya ringkas: daftar item nilai
sekali saja, lalu satu baris per mahasiswa berisi nilai mentah tiap item,
berkunci id item. Untuk item berskala, nilai mentahnya adalah nomor butir skala.

idnumber (NIM) tidak ikut. Kalau perlu, cocokkan user_id dengan
peserta_kursus(lengkap=True).
"""

from __future__ import annotations

from aswaya_mcp.aswaya_client import KlienAswaya, periksa_id
from aswaya_mcp.teks import teks_dari_html

NAMA_ITEM_TOTAL = {"course": "Total kursus", "category": "Total kategori"}


def angka(nilai) -> float | None:
    """Nilai mentah sebagai float; kosong atau bukan angka menjadi None."""
    try:
        return float(nilai) if nilai is not None and nilai != "" else None
    except (TypeError, ValueError):
        return None


def bentuk_item(item: dict) -> dict:
    """Satu item nilai: tugas, kuis, item manual, atau total."""
    nama = teks_dari_html(item.get("itemname")) or NAMA_ITEM_TOTAL.get(item.get("itemtype"), "")
    return {
        "id": item.get("id"),
        "nama": nama,
        "jenis": item.get("itemtype"),
        "modul": item.get("itemmodule"),
        "cmid": item.get("cmid"),
        "maks": angka(item.get("grademax")),
    }


def nilai_kursus(klien: KlienAswaya, kursus_id: int) -> dict:
    """Item nilai dan nilai setiap mahasiswa di satu kursus.

    `item` berisi id, nama, jenis (mod, manual, category, course), modul, cmid,
    dan nilai maksimum. Tiap baris `mahasiswa` berisi user_id, nama, dan
    `nilai` berkunci id item (sebagai teks) dengan nilai mentah atau null.
    """
    kursus_id = periksa_id(kursus_id, "kursus_id")
    hasil = klien.panggil("gradereport_user_get_grade_items", {"courseid": kursus_id}) or {}
    item: dict[int, dict] = {}
    mahasiswa = []
    for pengguna in hasil.get("usergrades") or []:
        nilai = {}
        for satu in pengguna.get("gradeitems") or []:
            item.setdefault(satu.get("id"), bentuk_item(satu))
            nilai[str(satu.get("id"))] = angka(satu.get("graderaw"))
        mahasiswa.append({"user_id": pengguna.get("userid"), "nama": pengguna.get("userfullname"), "nilai": nilai})
    mahasiswa.sort(key=lambda satu: str(satu["nama"] or "").casefold())
    return {
        "kursus_id": kursus_id,
        "jumlah_item": len(item),
        "jumlah_mahasiswa": len(mahasiswa),
        "item": list(item.values()),
        "mahasiswa": mahasiswa,
        "peringatan": [str(satu.get("message") or satu) for satu in hasil.get("warnings") or []],
    }
