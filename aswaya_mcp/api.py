"""REST API LMS Aswaya Pradita.

Membuka kemampuan yang sama dengan CLI dan MCP lewat HTTP. Endpoint GET hanya
membaca. Endpoint POST yang menulis (pengumuman, nilai, pesan, section, dan
/panggil untuk fungsi selain baca) bawaannya uji coba: tanpa "kirim": true yang
kembali hanya pratinjau permintaannya. Menambah dan mengganti nama section
memakai login web, jadi hanya bisa dengan password, tidak dengan token saja.

Kredensial boleh dikirim per permintaan, jadi satu server bisa melayani
beberapa dosen: lewat header X-Aswaya-Token, atau X-Aswaya-Username dan
X-Aswaya-Password, pada GET; lewat token, atau username dan password, di badan
JSON pada POST. Kalau semuanya dikosongkan, dipakai setelan server (.env).
Token milik kredensial per permintaan tidak pernah ditulis ke cache disk server.

Jalankan:
    ./aswaya api              # http://localhost:8000

Contoh:
    curl localhost:8000/kursus?cari=web
    curl -X POST localhost:8000/kursus/5515/pengumuman -H "Content-Type: application/json" \
         -d '{"subjek": "Kuis", "isi": "Kuis minggu depan."}'
"""

from __future__ import annotations

import hashlib
import time
from typing import Any, Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from starlette.background import BackgroundTask

from aswaya_mcp import __version__, forum, fungsi, kalender, kursus, nilai, pesan, section, situs, tugas
from aswaya_mcp.aswaya_client import (
    AlamatDitolak,
    AswayaError,
    FungsiTidakTersedia,
    HasilTidakPasti,
    IsianDitolak,
    KlienAswaya,
    LoginDitolak,
    MoodleError,
)
from aswaya_mcp.berkas import nama_dari_jawaban
from aswaya_mcp.konfigurasi import KonfigurasiError, baca_angka, baca_pengaturan
from aswaya_mcp.sesi_web import SesiWeb

# nama perguruan tinggi hanya untuk label; tidak memengaruhi perilaku apa pun
NAMA_INSTANSI = baca_pengaturan("ASWAYA_NAMA_INSTANSI", "Pradita University")

# errorcode Moodle yang punya padanan status HTTP yang lebih tepat dari 502
KODE_TIDAK_DITEMUKAN = frozenset({"invalidrecord", "invalidrecordunknown", "invalidcourseid", "invalidcoursemodule"})
KODE_TERLARANG = frozenset({"nopermissions", "requireloginerror", "accessexception", "notingroup", "nopermission"})
KODE_ISIAN = frozenset({"invalidparameter", "invalidresponse", "missingparam"})

# Rute dikumpulkan di router supaya proyek lain bisa menempelkannya ke aplikasi
# FastAPI miliknya sendiri:
#     from aswaya_mcp.api import router
#     app_saya.include_router(router, prefix="/aswaya")
router = APIRouter()

# satu klien dipakai ulang selama masih segar; klien itu sendiri yang login
# ulang kalau tokennya ditolak di tengah jalan
UMUR_SESI_DETIK = baca_angka("ASWAYA_UMUR_SESI_DETIK", 900)
sesi_tersimpan: dict[str, tuple[float, KlienAswaya]] = {}
# sesi web (login lewat halaman) per klien, untuk menambah dan mengganti nama section
sesi_web_tersimpan: dict[str, SesiWeb] = {}


def buat_app() -> FastAPI:
    """Aplikasi FastAPI berdiri sendiri yang hanya berisi rute paket ini."""
    app = FastAPI(
        title=f"Aswaya {NAMA_INSTANSI} API",
        version=__version__,
        description=(
            "Pakai LMS Aswaya (Moodle) lewat HTTP: kursus, peserta, tugas, pengumpulan, nilai, forum, "
            "tenggat, berkas, dan fungsi web service apa pun. Endpoint POST yang menulis bawaannya uji "
            "coba; tambahkan \"kirim\": true untuk mengirim sungguhan."
        ),
    )
    app.include_router(router)
    return app


class Kredensial(BaseModel):
    """Kredensial Aswaya. Kosongkan semuanya untuk memakai setelan server."""

    username: str = Field(default="", description="Username atau email Aswaya; kosong berarti setelan server")
    password: str = Field(default="", description="Password Aswaya; kosong berarti setelan server")
    token: str = Field(default="", description="Token web service moodle_mobile_app; dipakai lebih dulu kalau diisi")


class PermintaanPanggil(Kredensial):
    """Satu panggilan wsfunction generik."""

    nama: str = Field(description="Nama wsfunction, mis. core_course_get_contents")
    parameter: dict[str, Any] = Field(default_factory=dict, description="Parameter fungsi sebagai objek JSON")
    kirim: bool = Field(default=False, description="Untuk fungsi selain baca: false hanya pratinjau, true mengirim")
    maks_karakter: int = Field(default=0, ge=0, description="Potong hasil baca sepanjang ini; 0 berarti utuh")


class PermintaanPengumuman(Kredensial):
    """Pengumuman baru di forum pengumuman kursus. Bawaannya uji coba."""

    subjek: str = Field(description="Subjek pengumuman")
    isi: str = Field(description="Isi pengumuman")
    bentuk: Literal["teks", "html"] = Field(default="teks", description="teks (diubah ke HTML) atau html")
    kirim: bool = Field(default=False, description="false: kembalikan pratinjau; true: kirim")


class PermintaanNilai(Kredensial):
    """Nilai seorang mahasiswa untuk satu tugas. Bawaannya uji coba."""

    user_id: int = Field(gt=0, description="userid Moodle mahasiswa")
    nilai: float = Field(ge=0, description="Nilai baru; tidak boleh melebihi nilai maksimum tugas")
    umpan_balik: str = Field(default="", description="Umpan balik; kosong berarti umpan balik lama tidak disentuh")
    bentuk: Literal["teks", "html"] = Field(default="teks", description="Bentuk umpan balik: teks atau html")
    kirim: bool = Field(default=False, description="false: kembalikan pratinjau; true: simpan nilai")


class PermintaanTambahSection(Kredensial):
    """Section baru di akhir kursus, satu per nama. Bawaannya uji coba."""

    nama: list[str] = Field(min_length=1, description="Nama section baru, berurutan")
    paksa: bool = Field(default=False, description="true: tetap tambahkan walau namanya sudah terpakai")
    kirim: bool = Field(default=False, description="false: kembalikan rencana; true: tambahkan lewat login web")


class PermintaanNamaSection(Kredensial):
    """Nama baru satu section. Bawaannya uji coba."""

    nama: str = Field(description="Nama baru")
    kirim: bool = Field(default=False, description="false: kembalikan rencana; true: ganti lewat login web")


class PermintaanRingkasanSection(Kredensial):
    """Isi baru untuk ringkasan (deskripsi) satu section."""

    isi: str = Field(description="Isi baru: teks biasa atau HTML")
    cara: Literal["tambah", "awal", "ganti"] = Field(
        default="tambah", description="tambah di akhir ringkasan, awal di bagian paling atas, atau ganti seluruhnya"
    )
    bentuk: Literal["teks", "html"] = Field(default="teks", description="teks (diubah ke HTML) atau html")
    tab_baru: bool = Field(default=True, description="true: setiap tautan di isi baru dibuka di tab baru")
    paksa: bool = Field(default=False, description="true: tetap tambahkan walau semua tautannya sudah ada")
    kirim: bool = Field(default=False, description="false: kembalikan rencana; true: simpan lewat login web")


class PermintaanPesan(Kredensial):
    """Pesan pribadi yang sama ke satu atau beberapa pengguna. Bawaannya uji coba."""

    user_ids: list[int] = Field(min_length=1, description="userid Moodle penerima")
    teks: str = Field(description="Isi pesan")
    bentuk: Literal["teks", "html"] = Field(default="teks", description="teks (diubah ke HTML) atau html")
    kirim: bool = Field(default=False, description="false: kembalikan pratinjau; true: kirim")


def kunci_sesi(kredensial: Kredensial) -> str:
    """Kunci penyimpanan klien. Password dan token hanya disimpan sebagai sidik SHA-256."""
    if not (kredensial.username or kredensial.password or kredensial.token):
        return "setelan"
    sidik = hashlib.sha256(f"{kredensial.password}\n{kredensial.token}".encode("utf-8")).hexdigest()
    return f"{kredensial.username}:{sidik}"


def galat_http(galat: Exception) -> HTTPException:
    """Terjemahkan kesalahan pustaka ke status HTTP yang sesuai."""
    if isinstance(galat, KonfigurasiError):
        return HTTPException(status_code=400, detail=str(galat))
    if isinstance(galat, (AlamatDitolak, IsianDitolak)):
        return HTTPException(status_code=422, detail=str(galat))
    if isinstance(galat, LoginDitolak):
        return HTTPException(status_code=401, detail=str(galat))
    if isinstance(galat, FungsiTidakTersedia):
        return HTTPException(status_code=403, detail=str(galat))
    if isinstance(galat, MoodleError):
        if galat.kode in KODE_TIDAK_DITEMUKAN:
            return HTTPException(status_code=404, detail=str(galat))
        if galat.kode in KODE_TERLARANG:
            return HTTPException(status_code=403, detail=str(galat))
        if galat.kode in KODE_ISIAN:
            return HTTPException(status_code=422, detail=str(galat))
    return HTTPException(status_code=502, detail=str(galat))


def ambil_klien(kredensial: Kredensial) -> KlienAswaya:
    """Klien untuk kredensial ini, dipakai ulang selama masih segar. Token diambil saat dibutuhkan."""
    if bool(kredensial.username) != bool(kredensial.password) and not kredensial.token:
        raise HTTPException(
            status_code=422, detail="Isi username dan password sekaligus, atau token, atau kosongkan semuanya"
        )
    kunci = kunci_sesi(kredensial)
    tersimpan = sesi_tersimpan.get(kunci)
    if tersimpan and time.monotonic() - tersimpan[0] < UMUR_SESI_DETIK:
        return tersimpan[1]
    try:
        if kunci == "setelan":
            klien = KlienAswaya()
        else:
            klien = KlienAswaya(
                kredensial.username or None, kredensial.password or None, kredensial.token or None, pakai_cache=False
            )
    except KonfigurasiError as galat:
        raise galat_http(galat) from galat
    sesi_tersimpan[kunci] = (time.monotonic(), klien)
    return klien


def ambil_sesi_web(kredensial: Kredensial, klien: KlienAswaya) -> SesiWeb:
    """Sesi web milik klien ini. Kredensial per permintaan tidak pernah menulis cookie ke cache server."""
    kunci = kunci_sesi(kredensial)
    sesi = sesi_web_tersimpan.get(kunci)
    if sesi is None or sesi.klien is not klien:
        sesi = SesiWeb(klien) if kunci == "setelan" else SesiWeb(klien, pakai_cache=False)
        sesi_web_tersimpan[kunci] = sesi
    return sesi


def kredensial_header(
    x_aswaya_username: str = Header(default="", description="Username atau email; kosong berarti setelan server"),
    x_aswaya_password: str = Header(default="", description="Password; kosong berarti setelan server"),
    x_aswaya_token: str = Header(default="", description="Token web service; dipakai lebih dulu kalau diisi"),
) -> Kredensial:
    """Kredensial GET dari header, karena GET tidak berbadan."""
    return Kredensial(username=x_aswaya_username, password=x_aswaya_password, token=x_aswaya_token)


def jalankan(fungsi_layanan, *argumen, **opsi):
    """Jalankan satu fungsi layanan dan terjemahkan kegagalannya ke HTTPException."""
    try:
        return fungsi_layanan(*argumen, **opsi)
    except (AswayaError, KonfigurasiError) as galat:
        raise galat_http(galat) from galat


# --- baca --------------------------------------------------------------------


@router.post("/sesi", summary="Cek akses ke Aswaya")
def cek_sesi(kredensial: Kredensial) -> dict:
    """Nama situs, pemakai, userid, release Moodle, dan jumlah fungsi yang boleh dipakai token."""
    klien = ambil_klien(kredensial)
    return {"ok": True, **jalankan(situs.cek_login, klien)}


@router.get("/publik", summary="Konfigurasi publik situs, tanpa login")
def konfigurasi_publik() -> dict:
    """tool_mobile_get_public_config: nama situs, jenis login, layanan mobile, pemeliharaan."""
    klien = jalankan(KlienAswaya)
    return jalankan(situs.publik, klien)


@router.get("/kursus", summary="Kursus yang diikuti pemakai")
def daftar_kursus(
    cari: str = Query(default="", description="Saring dengan potongan nama, nama pendek, atau kategori"),
    kredensial: Kredensial = Depends(kredensial_header),
) -> dict:
    """Kursus terbaru dulu: id, shortname, fullname, kategori, mulai, selesai, visible, url."""
    return jalankan(kursus.daftar_kursus, ambil_klien(kredensial), cari)


@router.get("/kursus/{kursus_id}/isi", summary="Section, modul, dan berkas satu kursus")
def isi_kursus(kursus_id: int, kredensial: Kredensial = Depends(kredensial_header)) -> dict:
    """core_course_get_contents dalam bentuk ringkas."""
    return jalankan(kursus.isi_kursus, ambil_klien(kredensial), kursus_id)


@router.get("/kursus/{kursus_id}/peserta", summary="Peserta satu kursus")
def peserta_kursus(
    kursus_id: int,
    peran: str = Query(default="", description="Shortname atau nama peran, mis. student"),
    lengkap: bool = Query(default=False, description="true: sertakan email dan idnumber (NIM)"),
    kredensial: Kredensial = Depends(kredensial_header),
) -> dict:
    """id, nama, peran, grup, dan akses terakhir; email dan idnumber hanya dengan lengkap=true."""
    return jalankan(kursus.peserta_kursus, ambil_klien(kredensial), kursus_id, peran, lengkap)


@router.get("/kursus/{kursus_id}/tugas", summary="Tugas satu kursus")
def daftar_tugas(kursus_id: int, kredensial: Kredensial = Depends(kredensial_header)) -> dict:
    """mod_assign_get_assignments dalam bentuk ringkas."""
    return jalankan(tugas.daftar_tugas, ambil_klien(kredensial), kursus_id)


@router.get("/kursus/{kursus_id}/nilai", summary="Buku nilai satu kursus")
def nilai_kursus(kursus_id: int, kredensial: Kredensial = Depends(kredensial_header)) -> dict:
    """Item nilai dan nilai mentah setiap mahasiswa."""
    return jalankan(nilai.nilai_kursus, ambil_klien(kredensial), kursus_id)


@router.get("/kursus/{kursus_id}/forum", summary="Forum satu kursus")
def daftar_forum(kursus_id: int, kredensial: Kredensial = Depends(kredensial_header)) -> dict:
    """mod_forum_get_forums_by_courses dalam bentuk ringkas."""
    return jalankan(forum.daftar_forum, ambil_klien(kredensial), kursus_id)


@router.get("/tugas/{tugas_id}/pengumpulan", summary="Pengumpulan dan nilai per mahasiswa")
def pengumpulan_tugas(tugas_id: int, kredensial: Kredensial = Depends(kredensial_header)) -> dict:
    """Status pengumpulan, berkas, dan nilai setiap peserta satu tugas."""
    return jalankan(tugas.pengumpulan_tugas, ambil_klien(kredensial), tugas_id)


@router.get("/forum/{forum_id}/diskusi", summary="Diskusi satu forum")
def diskusi_forum(forum_id: int, kredensial: Kredensial = Depends(kredensial_header)) -> dict:
    """Diskusi terbaru dulu beserta pesan pembukanya."""
    return jalankan(forum.diskusi_forum, ambil_klien(kredensial), forum_id)


@router.get("/tenggat", summary="Kegiatan yang menunggu tindakan")
def tenggat(
    hari: int = Query(default=kalender.HARI_BAWAAN, ge=1, le=kalender.MAKS_HARI, description="Jangkauan ke depan"),
    kursus_id: int = Query(default=0, ge=0, description="0 berarti semua kursus"),
    kredensial: Kredensial = Depends(kredensial_header),
) -> dict:
    """Action events kalender Moodle dari hari ini sampai `hari` hari ke depan."""
    return jalankan(kalender.tenggat, ambil_klien(kredensial), hari, kursus_id or None)


@router.get("/kursus/{kursus_id}/section", summary="Section satu kursus")
def daftar_section(kursus_id: int, kredensial: Kredensial = Depends(kredensial_header)) -> dict:
    """id, nomor, nama, visible, dan jumlah modul setiap section."""
    return jalankan(section.daftar_section, ambil_klien(kredensial), kursus_id)


@router.get("/fungsi", summary="Fungsi web service yang tersedia")
def fungsi_tersedia(
    cari: str = Query(default="", description="Potongan nama fungsi"),
    kredensial: Kredensial = Depends(kredensial_header),
) -> dict:
    """Daftar wsfunction dari site info, dengan tanda mana yang dianggap membaca."""
    return jalankan(fungsi.fungsi_tersedia, ambil_klien(kredensial), cari)


@router.get("/berkas", summary="Unduh satu berkas Aswaya")
def unduh_berkas(
    url: str = Query(description="fileurl dari isi kursus, pengumpulan, atau diskusi"),
    kredensial: Kredensial = Depends(kredensial_header),
) -> StreamingResponse:
    """Isi berkas dialirkan apa adanya; token hanya dikirim server ini ke host Aswaya."""
    klien = ambil_klien(kredensial)
    jawaban = jalankan(klien.buka_berkas, url)
    nama = nama_dari_jawaban(jawaban, jalankan(klien.alamat_berkas, url))
    return StreamingResponse(
        jawaban.iter_content(chunk_size=64 * 1024),
        media_type=jawaban.headers.get("Content-Type") or "application/octet-stream",
        headers={"Content-Disposition": disposisi(nama)},
        background=BackgroundTask(jawaban.close),
    )


def disposisi(nama: str) -> str:
    """Content-Disposition unduhan: filename ASCII untuk klien lama, filename* (RFC 5987) untuk nama utuh."""
    cadangan = "".join(huruf if huruf.isascii() and huruf.isprintable() and huruf not in '"\\' else "_" for huruf in nama)
    return f"attachment; filename=\"{cadangan}\"; filename*=UTF-8''{quote(nama, safe='')}"


# --- tulis (bawaannya uji coba) -------------------------------------------------


def hasil_tulis(fungsi_layanan, *argumen, **opsi) -> dict:
    """Jalankan satu fungsi tulis. Hasil yang tidak pasti dibalas 502 dengan pesan jangan mengirim ulang."""
    try:
        hasil = fungsi_layanan(*argumen, **opsi)
    except HasilTidakPasti as galat:
        raise HTTPException(status_code=502, detail=str(galat)) from galat
    except (AswayaError, KonfigurasiError) as galat:
        raise galat_http(galat) from galat
    return hasil if isinstance(hasil, dict) else hasil.sebagai_dict()


@router.post("/panggil", summary="Panggil wsfunction apa pun")
def panggil_fungsi(permintaan: PermintaanPanggil) -> dict:
    """Fungsi baca langsung dijalankan; fungsi lain hanya pratinjau kecuali kirim=true."""
    return hasil_tulis(
        fungsi.panggil_fungsi,
        ambil_klien(permintaan),
        permintaan.nama,
        permintaan.parameter,
        kirim=permintaan.kirim,
        maks_karakter=permintaan.maks_karakter,
    )


@router.post("/kursus/{kursus_id}/pengumuman", summary="Pengumuman baru (bawaannya uji coba)")
def kirim_pengumuman(kursus_id: int, permintaan: PermintaanPengumuman) -> dict:
    """Pengumuman di forum pengumuman kursus; tanpa kirim=true hanya pratinjau."""
    return hasil_tulis(
        forum.kirim_pengumuman,
        ambil_klien(permintaan),
        kursus_id,
        permintaan.subjek,
        permintaan.isi,
        kirim=permintaan.kirim,
        bentuk=permintaan.bentuk,
    )


@router.post("/tugas/{tugas_id}/nilai", summary="Beri nilai (bawaannya uji coba)")
def beri_nilai(tugas_id: int, permintaan: PermintaanNilai) -> dict:
    """Nilai dan umpan balik seorang mahasiswa; tanpa kirim=true hanya pratinjau."""
    return hasil_tulis(
        tugas.beri_nilai,
        ambil_klien(permintaan),
        tugas_id,
        permintaan.user_id,
        permintaan.nilai,
        permintaan.umpan_balik,
        kirim=permintaan.kirim,
        bentuk=permintaan.bentuk,
    )


@router.post("/pesan", summary="Kirim pesan pribadi (bawaannya uji coba)")
def kirim_pesan(permintaan: PermintaanPesan) -> dict:
    """Pesan yang sama ke beberapa pengguna; tanpa kirim=true hanya pratinjau."""
    return hasil_tulis(
        pesan.kirim_pesan,
        ambil_klien(permintaan),
        permintaan.user_ids,
        permintaan.teks,
        kirim=permintaan.kirim,
        bentuk=permintaan.bentuk,
    )


@router.post("/kursus/{kursus_id}/section", summary="Tambah section di akhir kursus (bawaannya uji coba)")
def tambah_section(kursus_id: int, permintaan: PermintaanTambahSection) -> dict:
    """Tanpa kirim=true hanya rencana; pengirimannya lewat login web, jadi butuh password."""
    klien = ambil_klien(permintaan)
    return hasil_tulis(
        section.tambah_section,
        klien,
        kursus_id,
        permintaan.nama,
        kirim=permintaan.kirim,
        paksa=permintaan.paksa,
        sesi=ambil_sesi_web(permintaan, klien),
    )


@router.post("/kursus/{kursus_id}/section/{section_id}/nama", summary="Ganti nama section (bawaannya uji coba)")
def ubah_nama_section(kursus_id: int, section_id: int, permintaan: PermintaanNamaSection) -> dict:
    """Tanpa kirim=true hanya rencana; pengirimannya lewat login web, jadi butuh password."""
    klien = ambil_klien(permintaan)
    return hasil_tulis(
        section.ubah_nama_section,
        klien,
        kursus_id,
        section_id,
        permintaan.nama,
        kirim=permintaan.kirim,
        sesi=ambil_sesi_web(permintaan, klien),
    )


@router.post("/kursus/{kursus_id}/section/{section_id}/ringkasan",
             summary="Tambah teks atau tautan ke ringkasan section (bawaannya uji coba)")
def ubah_ringkasan_section(kursus_id: int, section_id: int, permintaan: PermintaanRingkasanSection) -> dict:
    """Tanpa kirim=true hanya rencana; pengirimannya lewat login web, jadi butuh password."""
    klien = ambil_klien(permintaan)
    return hasil_tulis(
        section.ubah_ringkasan_section,
        klien,
        kursus_id,
        section_id,
        permintaan.isi,
        cara=permintaan.cara,
        bentuk=permintaan.bentuk,
        tab_baru=permintaan.tab_baru,
        kirim=permintaan.kirim,
        paksa=permintaan.paksa,
        sesi=ambil_sesi_web(permintaan, klien),
    )


app = buat_app()
