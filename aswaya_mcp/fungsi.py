"""Daftar fungsi web service yang boleh dipakai token, dan pemanggil generik untuk fungsi apa pun.

Alat khusus di paket ini hanya mencakup sebagian kecil fungsi layanan
moodle_mobile_app. Sisanya bisa dipakai lewat `panggil_fungsi()`, dengan satu
pagar: hanya fungsi yang tampak membaca yang langsung dijalankan.

Moodle mencatat jenis read/write setiap fungsi, tetapi core_webservice_get_site_info
tidak menyampaikannya. Jadi jenisnya ditebak dari nama: fungsi yang namanya
memuat _get_, _search_, atau _list_ dianggap membaca. Fungsi lain, termasuk
fungsi view (yang mencatat log dan bisa menandai aktivitas selesai), hanya
dikembalikan sebagai pratinjau permintaan kecuali kirim=True.

Dua fungsi yang menghasilkan kunci login ditolak sama sekali, karena asisten AI
tidak boleh memegang kredensial pemakai.
"""

from __future__ import annotations

import json
from typing import Any

from aswaya_mcp.aswaya_client import IsianDitolak, KlienAswaya, periksa_nama_fungsi
from aswaya_mcp.tulis import jalankan_tulis

POLA_BACA = ("_get_", "_search_", "_list_")
FUNGSI_TERLARANG = frozenset({
    "tool_mobile_get_autologin_key",
    "tool_mobile_get_tokens_for_qr_login",
})
# kunci yang nilainya kredensial; disamarkan dari setiap hasil panggil_fungsi
KUNCI_RAHASIA = frozenset({"token", "wstoken", "privatetoken", "userprivateaccesskey"})
MAKS_KARAKTER_BAWAAN = 20000


def adalah_fungsi_baca(nama: str) -> bool:
    """Apakah fungsi ini dianggap membaca dari namanya (memuat _get_, _search_, atau _list_)."""
    return nama not in FUNGSI_TERLARANG and any(pola in f"{nama}_" for pola in POLA_BACA)


def samarkan_rahasia(data: Any) -> Any:
    """Salinan data dengan nilai berkunci token, privatetoken, dan sejenisnya diganti '***'."""
    if isinstance(data, dict):
        return {
            kunci: ("***" if kunci in KUNCI_RAHASIA and data[kunci] else samarkan_rahasia(isi))
            for kunci, isi in data.items()
        }
    if isinstance(data, list):
        return [samarkan_rahasia(isi) for isi in data]
    return data


def fungsi_tersedia(klien: KlienAswaya, cari: str = "") -> dict:
    """Fungsi web service yang boleh dipakai token ini, disaring dengan potongan nama `cari`.

    Tiap entri menyebut apakah panggil_fungsi akan langsung menjalankannya
    (`baca`) atau hanya mengembalikan pratinjau tanpa kirim=True.
    """
    semua = klien.daftar_fungsi()
    kata = (cari or "").strip().casefold()
    cocok = [nama for nama in semua if kata in nama.casefold()]
    return {
        "jumlah": len(cocok),
        "jumlah_semua": len(semua),
        "cari": cari or "",
        "fungsi": [{"nama": nama, "baca": adalah_fungsi_baca(nama)} for nama in cocok],
    }


def bentuk_hasil(hasil: Any, maks_karakter: int) -> dict:
    """Hasil panggilan baca, utuh atau sebagai potongan JSON kalau melebihi `maks_karakter`."""
    hasil = samarkan_rahasia(hasil)
    teks = json.dumps(hasil, ensure_ascii=False)
    if maks_karakter > 0 and len(teks) > maks_karakter:
        return {"terpotong": True, "panjang": len(teks), "hasil_json": teks[:maks_karakter]}
    return {"terpotong": False, "panjang": len(teks), "hasil": hasil}


def panggil_fungsi(
    klien: KlienAswaya,
    nama: str,
    parameter: dict | None = None,
    *,
    kirim: bool = False,
    maks_karakter: int = MAKS_KARAKTER_BAWAAN,
) -> dict:
    """Panggil satu wsfunction apa pun dengan parameter terstruktur.

    Fungsi baca langsung dijalankan. Fungsi lain hanya dikembalikan sebagai
    pratinjau permintaan, kecuali kirim=True; uraiannya di tulis.py. Hasil baca
    yang JSON-nya lebih panjang dari `maks_karakter` dikembalikan sebagai
    potongan teks di `hasil_json` (0 berarti utuh).
    """
    nama = periksa_nama_fungsi(nama)
    if nama in FUNGSI_TERLARANG:
        raise IsianDitolak(f"{nama} menghasilkan kunci login, jadi tidak dibuka lewat alat ini")
    if parameter is not None and not isinstance(parameter, dict):
        raise IsianDitolak("parameter harus berupa objek JSON, mis. {\"courseid\": 5515}")
    parameter = parameter or {}
    if adalah_fungsi_baca(nama):
        hasil = klien.panggil(nama, parameter)
        return {"fungsi": nama, "jenis": "baca", **bentuk_hasil(hasil, maks_karakter)}
    tulis = jalankan_tulis(
        klien, nama, parameter, {"fungsi": nama}, kirim=kirim, pesan_terkirim=f"{nama} sudah dijalankan."
    )
    data = tulis.sebagai_dict()
    data["hasil"] = samarkan_rahasia(data["hasil"])
    return {"jenis": "tulis", **data}
