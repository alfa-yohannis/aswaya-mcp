"""MCP server LMS Aswaya Pradita.

Membuka kemampuan yang sama dengan CLI dan REST API lewat protokol MCP, sehingga
asisten AI bisa memakai sendiri Aswaya atas nama dosen: membaca kursus, peserta,
tugas, pengumpulan, nilai, forum, section, dan tenggat; mengunduh berkas; serta
membuat pengumuman, memberi nilai, mengirim pesan, dan menambah atau mengganti
nama section. Semua alat yang menulis, juga panggil_fungsi untuk fungsi selain
baca, bawaannya uji coba (kirim=False).

Kredensial tidak diterima lewat parameter tool. Semuanya dibaca dari setelan
(ASWAYA_USERNAME dan ASWAYA_PASSWORD, atau ASWAYA_TOKEN, di .env atau
environment), jadi asisten tidak pernah memegang kata sandi maupun token. Token
baru diambil saat tool pertama dipanggil, lalu dipakai ulang antar-pemanggilan.

Daftarkan ke Claude Code (perintah `aswaya-mcp` ikut terpasang bersama paketnya):
    claude mcp add aswaya-mcp -- aswaya-mcp
"""

from __future__ import annotations

from typing import Literal

from mcp.server.mcpserver import MCPServer

from aswaya_mcp import (
    __version__,
    berkas,
    forum,
    fungsi,
    kalender,
    kursus,
    nilai,
    pesan,
    section,
    situs,
    tugas,
)
from aswaya_mcp.aswaya_client import URL_BAWAAN, AswayaError, HasilTidakPasti, KlienAswaya, tentukan_alamat
from aswaya_mcp.konfigurasi import KonfigurasiError, baca_pengaturan
from aswaya_mcp.sesi_web import SesiWeb

GALAT = (AswayaError, KonfigurasiError)


def alamat_situs() -> str:
    """Alamat Aswaya untuk teks instruksi; setelan yang belum benar jatuh ke alamat bawaan."""
    try:
        return tentukan_alamat()
    except KonfigurasiError:
        return URL_BAWAAN


# instruksi menyebut instansi dan alamatnya supaya asisten tahu sistem mana yang
# sedang dipakai; keduanya ikut setelan, tidak ditanam di teks
NAMA_INSTANSI = baca_pengaturan("ASWAYA_NAMA_INSTANSI", "Pradita University")

server = MCPServer(
    name="aswaya-mcp",
    version=__version__,
    instructions=(
        f"Mengakses LMS Aswaya {NAMA_INSTANSI} ({alamat_situs()}), sebuah Moodle, atas nama dosen "
        "pemakai. Urutan yang disarankan: cek_login, lalu daftar_kursus untuk mendapatkan kursus_id, "
        "lalu isi_kursus, peserta_kursus, daftar_tugas, pengumpulan_tugas (dengan tugas_id dari "
        "daftar_tugas), nilai_kursus, daftar_forum, diskusi_forum, atau tenggat. unduh_berkas memakai "
        "url berkas dari hasil tool lain. daftar_section menampilkan section kursus beserta id-nya. "
        "Untuk fungsi Moodle yang tidak punya tool sendiri, cari namanya dengan fungsi_tersedia lalu "
        "pakai panggil_fungsi. "
        "Tool yang menulis ke Aswaya adalah kirim_pengumuman, beri_nilai, kirim_pesan, tambah_section, "
        "ubah_nama_section, dan panggil_fungsi untuk fungsi selain baca. Bawaannya uji coba "
        "(kirim=False) yang hanya mengembalikan pratinjau. Jalankan uji coba lebih dulu, tunjukkan "
        "pratinjaunya (ringkasan dan permintaan) ke pemakai, lalu panggil lagi dengan kirim=True hanya "
        "setelah pemakai menyetujuinya. tambah_section dan ubah_nama_section mengirim lewat login web "
        "dengan password dari .env; kalau login itu terhalang captcha atau MFA, sampaikan apa adanya "
        "dan jangan mencari jalan lain. Kalau balasannya terkirim=true dengan ok=false, jangan "
        "mengirim ulang; periksa dulu lewat tool baca dan laporkan ke pemakai. Email dan idnumber (NIM) mahasiswa "
        "hanya disertakan peserta_kursus dengan lengkap=True; minta hanya kalau pemakai "
        "membutuhkannya. Kredensial diambil dari setelan server (.env); jangan meminta kata sandi "
        "atau token ke pemakai."
    ),
)

# Satu klien untuk seluruh pemanggilan tool, supaya token tidak diminta ulang
# setiap kali. cek_login menggantinya dengan klien baru yang sudah teruji.
klien_tersimpan: KlienAswaya | None = None
# Sesi web (login lewat halaman) untuk menambah dan mengganti nama section,
# dipakai ulang selama kliennya sama.
sesi_web_tersimpan: SesiWeb | None = None


def klien_bersama() -> KlienAswaya:
    """Klien yang dipakai bersama tool; dibuat saat pertama dibutuhkan, belum menghubungi Aswaya."""
    global klien_tersimpan
    if klien_tersimpan is None:
        klien_tersimpan = KlienAswaya()
    return klien_tersimpan


def sesi_web_bersama() -> SesiWeb:
    """Sesi web milik klien bersama; dibuat saat pertama dibutuhkan, belum login."""
    global sesi_web_tersimpan
    klien = klien_bersama()
    if sesi_web_tersimpan is None or sesi_web_tersimpan.klien is not klien:
        sesi_web_tersimpan = SesiWeb(klien)
    return sesi_web_tersimpan


def gagal(galat: Exception) -> dict:
    """Balasan tool untuk kegagalan yang terjadi sebelum apa pun ditulis ke Aswaya."""
    return {"ok": False, "pesan": str(galat)}


def gagal_tulis(galat: Exception) -> dict:
    """Balasan tool tulis yang gagal; `terkirim` true kalau permintaannya mungkin sudah diproses."""
    return {"ok": False, "terkirim": isinstance(galat, HasilTidakPasti), "pesan": str(galat)}


@server.tool()
def cek_login(login_ulang: bool = False) -> dict:
    """Cek akses ke Aswaya dengan kredensial di setelan (.env).

    Mengembalikan nama situs, nama dan username pemakai, userid, release
    Moodle, jumlah fungsi web service yang boleh dipakai, dan asal tokennya
    (setelan, cache, atau login). Selalu membuat klien baru, jadi perubahan .env
    langsung terbaca. login_ulang=True memaksa login dengan password walaupun
    ada token di setelan atau cache. Kalau gagal, `diagnosis` berisi
    konfigurasi publik situs (pemeliharaan, layanan mobile) bila terjangkau.
    """
    global klien_tersimpan
    klien = None
    try:
        klien = KlienAswaya()
        hasil = situs.cek_login(klien, login_ulang=login_ulang)
    except GALAT as galat:
        return {"ok": False, "pesan": str(galat), "diagnosis": situs.diagnosis(klien)}
    klien_tersimpan = klien
    return {"ok": True, **hasil}


@server.tool()
def daftar_kursus(cari: str = "") -> dict:
    """Kursus yang diikuti pemakai di Aswaya, terbaru dulu.

    Tiap kursus berisi id, shortname, fullname, kategori, mulai, selesai,
    visible, dan url. `cari` menyaring dengan potongan teks dari nama, nama
    pendek, atau kategori, tanpa membedakan huruf besar dan kecil.
    """
    try:
        return {"ok": True, **kursus.daftar_kursus(klien_bersama(), cari)}
    except GALAT as galat:
        return gagal(galat)


@server.tool()
def isi_kursus(kursus_id: int) -> dict:
    """Section dan modul satu kursus beserta berkasnya (core_course_get_contents).

    Tiap modul berisi id (cmid), nama, jenis (assign, forum, resource, url,
    quiz, ...), url, deskripsi singkat, tanggal penting, dan berkas. `url`
    berkas bisa diteruskan ke unduh_berkas.
    """
    try:
        return {"ok": True, **kursus.isi_kursus(klien_bersama(), kursus_id)}
    except GALAT as galat:
        return gagal(galat)


@server.tool()
def peserta_kursus(kursus_id: int, peran: str = "", lengkap: bool = False) -> dict:
    """Peserta satu kursus: id, nama, peran, grup, dan waktu akses terakhir.

    `peran` menyaring per shortname atau nama peran Moodle, mis. student,
    editingteacher, atau teacher; `peran_tersedia` menyebut peran yang ada.
    Email dan idnumber (NIM) baru disertakan kalau lengkap=True. Pakai
    lengkap=True hanya kalau pemakai memang membutuhkannya.
    """
    try:
        return {"ok": True, **kursus.peserta_kursus(klien_bersama(), kursus_id, peran, lengkap)}
    except GALAT as galat:
        return gagal(galat)


@server.tool()
def daftar_tugas(kursus_id: int) -> dict:
    """Tugas (assignment) satu kursus: id, nama, dibuka, tenggat, batas akhir, nilai maksimum, url.

    `id` di sini adalah tugas_id untuk pengumpulan_tugas dan beri_nilai.
    """
    try:
        return {"ok": True, **tugas.daftar_tugas(klien_bersama(), kursus_id)}
    except GALAT as galat:
        return gagal(galat)


@server.tool()
def pengumpulan_tugas(tugas_id: int) -> dict:
    """Pengumpulan dan nilai setiap mahasiswa untuk satu tugas, termasuk yang belum mengumpulkan.

    Tiap baris berisi user_id, nama, grup, status (new, draft, submitted,
    reopened) dan keterangannya, perlu_dinilai, waktu_kumpul, berkas, teks
    daring yang dipotong, nilai (null kalau belum dinilai), dan dinilai_pada.
    `ringkasan` menghitung yang sudah mengumpulkan, belum, dan perlu dinilai.
    """
    try:
        return {"ok": True, **tugas.pengumpulan_tugas(klien_bersama(), tugas_id)}
    except GALAT as galat:
        return gagal(galat)


@server.tool()
def nilai_kursus(kursus_id: int) -> dict:
    """Buku nilai satu kursus (gradereport_user_get_grade_items).

    `item` berisi id, nama, jenis, dan nilai maksimum tiap item nilai. Tiap
    baris `mahasiswa` berisi user_id, nama, dan `nilai` berkunci id item
    (sebagai teks) dengan nilai mentah atau null.
    """
    try:
        return {"ok": True, **nilai.nilai_kursus(klien_bersama(), kursus_id)}
    except GALAT as galat:
        return gagal(galat)


@server.tool()
def daftar_forum(kursus_id: int) -> dict:
    """Forum di satu kursus: id, nama, jenis (news untuk pengumuman), jumlah diskusi, url."""
    try:
        return {"ok": True, **forum.daftar_forum(klien_bersama(), kursus_id)}
    except GALAT as galat:
        return gagal(galat)


@server.tool()
def diskusi_forum(forum_id: int) -> dict:
    """Diskusi satu forum, terbaru dulu: subjek, penulis, waktu, jumlah balasan, pesan pembuka, lampiran."""
    try:
        return {"ok": True, **forum.diskusi_forum(klien_bersama(), forum_id)}
    except GALAT as galat:
        return gagal(galat)


@server.tool()
def tenggat(hari: int = kalender.HARI_BAWAAN, kursus_id: int = 0) -> dict:
    """Kegiatan yang menunggu tindakan dari kalender Moodle, mulai hari ini sampai `hari` hari ke depan.

    Bagi dosen ini termasuk tugas yang menunggu dinilai (`jumlah_item`).
    kursus_id=0 berarti semua kursus.
    """
    try:
        return {"ok": True, **kalender.tenggat(klien_bersama(), hari, kursus_id or None)}
    except GALAT as galat:
        return gagal(galat)


@server.tool()
def unduh_berkas(url: str, tujuan: str = "", timpa: bool = False) -> dict:
    """Unduh satu berkas Aswaya ke disk lokal.

    `url` adalah url berkas dari isi_kursus, pengumpulan_tugas, atau
    diskusi_forum (webservice/pluginfile.php/...); tokennya ditambahkan sendiri
    dan hanya dikirim ke host Aswaya. `tujuan` boleh path berkas atau direktori
    (akhiri dengan /); kosong berarti data/unduhan/ di akar proyek, dan path
    relatif dihitung dari akar proyek. Berkas yang sudah ada tidak ditimpa
    kecuali timpa=True.
    """
    try:
        return {"ok": True, **berkas.unduh_berkas(klien_bersama(), url, tujuan, timpa=timpa)}
    except GALAT as galat:
        return gagal(galat)


@server.tool()
def daftar_section(kursus_id: int) -> dict:
    """Section satu kursus: id, nomor, nama, visible, dan jumlah modul.

    `id` adalah section_id untuk ubah_nama_section; `nomor` adalah urutan
    section di halaman kursus (0 untuk bagian umum di atas).
    """
    try:
        return {"ok": True, **section.daftar_section(klien_bersama(), kursus_id)}
    except GALAT as galat:
        return gagal(galat)


@server.tool()
def fungsi_tersedia(cari: str = "") -> dict:
    """Fungsi web service Moodle yang boleh dipakai token ini, disaring dengan potongan nama `cari`.

    `baca` bernilai true untuk fungsi yang langsung dijalankan panggil_fungsi;
    sisanya hanya dipratinjau tanpa kirim=True.
    """
    try:
        return {"ok": True, **fungsi.fungsi_tersedia(klien_bersama(), cari)}
    except GALAT as galat:
        return gagal(galat)


@server.tool()
def panggil_fungsi(nama: str, parameter: dict | None = None, kirim: bool = False, maks_karakter: int = 20000) -> dict:
    """Panggil satu fungsi web service Moodle apa pun (wsfunction) dengan parameter terstruktur.

    `parameter` berupa objek JSON sesuai dokumentasi fungsi Moodle-nya, mis.
    {"courseid": 5515} atau {"options": [{"name": "excludemodules", "value": 1}]};
    perataan ke bentuk form Moodle dikerjakan sendiri. Fungsi yang namanya
    memuat _get_, _search_, atau _list_ dianggap membaca dan langsung
    dijalankan. Fungsi lain hanya dikembalikan sebagai pratinjau permintaan
    kecuali kirim=True; jalankan uji coba dulu dan minta persetujuan pemakai.
    Hasil yang lebih panjang dari maks_karakter dikembalikan terpotong di
    `hasil_json` (0 berarti utuh).
    """
    try:
        hasil = fungsi.panggil_fungsi(klien_bersama(), nama, parameter, kirim=kirim, maks_karakter=maks_karakter)
    except GALAT as galat:
        return gagal_tulis(galat)
    return {"ok": True, **hasil}


@server.tool()
def kirim_pengumuman(
    kursus_id: int,
    subjek: str,
    isi: str,
    kirim: bool = False,
    bentuk: Literal["teks", "html"] = "teks",
) -> dict:
    """Buat pengumuman di forum pengumuman (jenis news) satu kursus. Bawaannya uji coba.

    Dengan kirim=False tidak ada yang dikirim; yang kembali adalah pratinjau:
    kursus, forum, subjek, isi, dan permintaan yang akan dikirim. Tunjukkan ke
    pemakai dan kirim dengan kirim=True hanya setelah pemakai menyetujuinya.
    `isi` berupa teks biasa (baris kosong memisahkan paragraf, alamat http(s)
    menjadi tautan) atau HTML dengan bentuk="html".
    """
    try:
        hasil = forum.kirim_pengumuman(klien_bersama(), kursus_id, subjek, isi, kirim=kirim, bentuk=bentuk)
    except GALAT as galat:
        return gagal_tulis(galat)
    return {"ok": True, **hasil.sebagai_dict()}


@server.tool()
def beri_nilai(
    tugas_id: int,
    user_id: int,
    nilai: float,
    umpan_balik: str = "",
    kirim: bool = False,
    bentuk: Literal["teks", "html"] = "teks",
) -> dict:
    """Simpan nilai seorang mahasiswa untuk satu tugas, dengan umpan balik opsional. Bawaannya uji coba.

    Pratinjau menyebut tugas, nama mahasiswa, nilai lama, nilai baru, dan nilai
    maksimum; nilai di atas maksimum ditolak. Tunjukkan ke pemakai dan kirim
    dengan kirim=True hanya setelah disetujui. umpan_balik kosong membiarkan
    umpan balik lama. Untuk tugas berkelompok, nilainya hanya untuk mahasiswa ini.
    """
    try:
        hasil = tugas.beri_nilai(
            klien_bersama(), tugas_id, user_id, nilai, umpan_balik, kirim=kirim, bentuk=bentuk
        )
    except GALAT as galat:
        return gagal_tulis(galat)
    return {"ok": True, **hasil.sebagai_dict()}


@server.tool()
def kirim_pesan(
    user_ids: list[int],
    teks: str,
    kirim: bool = False,
    bentuk: Literal["teks", "html"] = "teks",
) -> dict:
    """Kirim pesan pribadi Moodle yang sama ke satu atau beberapa pengguna. Bawaannya uji coba.

    Pratinjau menyebut nama setiap penerima; id yang tidak dikenal ditolak.
    Tunjukkan ke pemakai dan kirim dengan kirim=True hanya setelah disetujui.
    Sesudah kiriman, `hasil` berisi status per penerima dan ok bernilai false
    kalau ada yang gagal; jangan kirim ulang ke penerima yang sudah berhasil.
    """
    try:
        hasil = pesan.kirim_pesan(klien_bersama(), user_ids, teks, kirim=kirim, bentuk=bentuk)
    except GALAT as galat:
        return gagal_tulis(galat)
    return {"ok": hasil.berhasil, **hasil.sebagai_dict()}


@server.tool()
def tambah_section(kursus_id: int, nama: list[str], kirim: bool = False, paksa: bool = False) -> dict:
    """Tambahkan section baru di akhir kursus, satu per nama, lalu beri namanya. Bawaannya uji coba.

    Dengan kirim=False tidak ada yang dikirim; yang kembali rencananya: section
    yang ada, nama baru beserta nomor posisinya, dan langkah yang akan
    dijalankan. Tunjukkan ke pemakai dan kirim dengan kirim=True hanya setelah
    pemakai menyetujuinya. Pengirimannya lewat login web dengan password dari
    .env (changenumsections.php lalu core_update_inplace_editable), dan
    hasilnya diperiksa ulang. Nama yang sudah terpakai ditolak kecuali
    paksa=True, supaya perintah yang terulang tidak menggandakan section.
    """
    try:
        hasil = section.tambah_section(
            klien_bersama(), kursus_id, nama, kirim=kirim, paksa=paksa, sesi=sesi_web_bersama()
        )
    except GALAT as galat:
        return gagal_tulis(galat)
    return {"ok": hasil.berhasil, **hasil.sebagai_dict()}


@server.tool()
def ubah_nama_section(kursus_id: int, section_id: int, nama: str, kirim: bool = False) -> dict:
    """Ganti nama satu section. Bawaannya uji coba.

    `section_id` adalah id dari daftar_section, bukan nomor urutnya. Rencana
    menyebut nama lama dan nama baru. Tunjukkan ke pemakai dan kirim dengan
    kirim=True hanya setelah disetujui. Pengirimannya lewat login web dengan
    password dari .env, dan hasilnya diperiksa ulang.
    """
    try:
        hasil = section.ubah_nama_section(
            klien_bersama(), kursus_id, section_id, nama, kirim=kirim, sesi=sesi_web_bersama()
        )
    except GALAT as galat:
        return gagal_tulis(galat)
    return {"ok": hasil.berhasil, **hasil.sebagai_dict()}


def jalankan() -> None:
    """Titik masuk perintah `aswaya-mcp` (stdio)."""
    server.run()


if __name__ == "__main__":
    jalankan()
