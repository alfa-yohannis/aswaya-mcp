"""Unduh berkas Aswaya (fileurl dari isi_kursus, pengumpulan_tugas, diskusi_forum) ke disk lokal.

Klien menambahkan token ke permintaannya sendiri, dan hanya ke host Aswaya.
Nama berkas diambil dari Content-Disposition, lalu dari ujung path URL, dan
dibersihkan dari pemisah direktori supaya server tidak bisa menulis ke luar
direktori tujuan. Berkas ditulis lewat berkas sementara di direktori yang sama,
lalu dipindah, jadi unduhan yang terputus tidak meninggalkan berkas setengah
jadi. Berkas yang sudah ada tidak ditimpa kecuali timpa=True.
"""

from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path
from urllib.parse import unquote, urlsplit

import requests

from aswaya_mcp.aswaya_client import AswayaError, IsianDitolak, KlienAswaya, samarkan
from aswaya_mcp.konfigurasi import akar_proyek, dir_data

DIR_UNDUHAN = "unduhan"
UKURAN_POTONGAN = 64 * 1024
POLA_NAMA_DISPOSISI = re.compile(r"filename\*?=(?:UTF-8''|\"?)([^\";]+)", re.IGNORECASE)


def nama_aman(nama: str) -> str:
    """Nama berkas tanpa direktori, karakter kendali, atau nama khusus seperti '..'."""
    nama = unquote(nama or "").replace("\\", "/").split("/")[-1]
    nama = "".join(huruf for huruf in nama if huruf.isprintable()).strip()
    return "" if nama in ("", ".", "..") else nama


def nama_dari_jawaban(jawaban, alamat: str) -> str:
    """Nama berkas dari Content-Disposition, lalu dari ujung path URL; 'berkas' kalau keduanya kosong."""
    cocok = POLA_NAMA_DISPOSISI.search(jawaban.headers.get("Content-Disposition", ""))
    if cocok:
        nama = nama_aman(cocok.group(1))
        if nama:
            return nama
    return nama_aman(urlsplit(alamat).path) or "berkas"


def path_tujuan(tujuan: str | Path, nama: str) -> Path:
    """Path berkas akhir. Kosong berarti data/unduhan/; path relatif dihitung dari akar proyek.

    Tujuan yang berakhir dengan / atau sudah berupa direktori dianggap direktori,
    dan nama berkasnya ditambahkan di belakang.
    """
    teks = str(tujuan or "")
    if not teks.strip():
        return dir_data() / DIR_UNDUHAN / nama
    path = Path(teks).expanduser()
    if not path.is_absolute():
        path = akar_proyek() / path
    if teks.endswith(("/", os.sep)) or path.is_dir():
        return path / nama
    return path


def unduh_berkas(klien: KlienAswaya, url: str, tujuan: str | Path = "", *, timpa: bool = False) -> dict:
    """Unduh satu berkas Aswaya ke `tujuan` dan kembalikan path, nama, ukuran, dan jenisnya."""
    jawaban = klien.buka_berkas(url)
    try:
        alamat = klien.alamat_berkas(url)
        nama = nama_dari_jawaban(jawaban, alamat)
        akhir = path_tujuan(tujuan, nama)
        if akhir.exists() and not timpa:
            raise IsianDitolak(f"{akhir} sudah ada; pakai timpa=True (CLI: --timpa) untuk menimpanya")
        akhir.parent.mkdir(parents=True, exist_ok=True)
        pegangan, sementara = tempfile.mkstemp(prefix=".unduhan-", dir=akhir.parent)
        ukuran = 0
        try:
            with os.fdopen(pegangan, "wb") as berkas:
                for potongan in jawaban.iter_content(chunk_size=UKURAN_POTONGAN):
                    if potongan:
                        berkas.write(potongan)
                        ukuran += len(potongan)
            os.replace(sementara, akhir)
        except requests.RequestException as galat:
            Path(sementara).unlink(missing_ok=True)
            raise AswayaError(f"Unduhan {nama} terputus: {samarkan(str(galat), klien.token)}") from None
        except BaseException:
            Path(sementara).unlink(missing_ok=True)
            raise
    finally:
        jawaban.close()
    return {
        "path": str(akhir),
        "nama_berkas": nama,
        "ukuran": ukuran,
        "jenis": jawaban.headers.get("Content-Type"),
    }
