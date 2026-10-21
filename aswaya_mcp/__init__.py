"""Aswaya MCP: pakai LMS Aswaya Pradita (Moodle) sebagai pustaka, CLI, REST API, atau MCP.

Tiga cara memakainya, semuanya dari paket yang sama:

    pustaka   from aswaya_mcp import KlienAswaya, daftar_kursus
              klien = KlienAswaya()                    # kredensial dari .env
              print(daftar_kursus(klien))              # token diambil di sini
              print(klien.panggil("core_course_get_contents", {"courseid": 5515}))

    REST API  from aswaya_mcp.api import router
              app_saya.include_router(router, prefix="/aswaya")

    MCP       from aswaya_mcp.mcp_server import server
              server.run()                             # atau lewat perintah `aswaya-mcp`

Fungsi yang menulis ke Aswaya (kirim_pengumuman, beri_nilai, kirim_pesan,
tambah_section, ubah_nama_section, dan panggil_fungsi untuk fungsi selain baca)
bawaannya uji coba: yang kembali pratinjau permintaannya, dan baru dikirim
dengan kirim=True. Dua yang menyangkut section memakai SesiWeb (login lewat
halaman), karena layanan moodle_mobile_app tidak memuat fungsi pembuat section.

    from aswaya_mcp import KlienAswaya, kirim_pengumuman
    rencana = kirim_pengumuman(KlienAswaya(), 5515, "Kuis minggu depan", "...")   # uji coba

Setelan bisa diberikan tanpa berkas apa pun, berguna buat proyek yang menyimpan
konfigurasinya sendiri:

    from aswaya_mcp import atur_setelan
    atur_setelan(ASWAYA_USERNAME="...", ASWAYA_TOKEN="...")

Impor di sini sengaja hanya menyentuh modul inti. `aswaya_mcp.api` butuh FastAPI
dan `aswaya_mcp.mcp_server` butuh paket mcp, jadi keduanya diimpor sendiri oleh
yang memerlukan. Pemakai pustaka tidak dipaksa memasang keduanya.
"""

from __future__ import annotations

__version__ = "0.1.0"

from aswaya_mcp.aswaya_client import (
    AlamatDitolak,
    AswayaError,
    FungsiTidakTersedia,
    HasilTidakPasti,
    IsianDitolak,
    KlienAswaya,
    LoginDitolak,
    MoodleError,
    ratakan,
)
from aswaya_mcp.berkas import unduh_berkas
from aswaya_mcp.forum import daftar_forum, diskusi_forum, kirim_pengumuman
from aswaya_mcp.fungsi import adalah_fungsi_baca, fungsi_tersedia, panggil_fungsi
from aswaya_mcp.kalender import tenggat
from aswaya_mcp.konfigurasi import (
    KonfigurasiError,
    akar_proyek,
    atur_akar_proyek,
    atur_setelan,
    baca_pengaturan,
    dir_cache,
)
from aswaya_mcp.kursus import daftar_kursus, isi_kursus, peserta_kursus
from aswaya_mcp.nilai import nilai_kursus
from aswaya_mcp.pesan import kirim_pesan
from aswaya_mcp.section import daftar_section, tambah_section, ubah_nama_section
from aswaya_mcp.sesi_web import LoginWebTerhalang, SesiWeb
from aswaya_mcp.tugas import beri_nilai, daftar_tugas, pengumpulan_tugas
from aswaya_mcp.tulis import HasilTulis

__all__ = [
    # klien
    "KlienAswaya",
    "SesiWeb",
    "ratakan",
    # baca
    "daftar_kursus",
    "isi_kursus",
    "peserta_kursus",
    "daftar_tugas",
    "pengumpulan_tugas",
    "nilai_kursus",
    "daftar_forum",
    "diskusi_forum",
    "daftar_section",
    "tenggat",
    "unduh_berkas",
    "fungsi_tersedia",
    "adalah_fungsi_baca",
    # tulis (bawaannya uji coba)
    "panggil_fungsi",
    "kirim_pengumuman",
    "beri_nilai",
    "kirim_pesan",
    "tambah_section",
    "ubah_nama_section",
    "HasilTulis",
    # setelan
    "atur_setelan",
    "atur_akar_proyek",
    "baca_pengaturan",
    "akar_proyek",
    "dir_cache",
    # kesalahan
    "AswayaError",
    "LoginDitolak",
    "AlamatDitolak",
    "FungsiTidakTersedia",
    "IsianDitolak",
    "HasilTidakPasti",
    "MoodleError",
    "LoginWebTerhalang",
    "KonfigurasiError",
    "__version__",
]
