"""Forum: daftar forum satu kursus, diskusi satu forum, dan pengumuman baru.

    daftar_forum       mod_forum_get_forums_by_courses
    diskusi_forum      mod_forum_get_forum_discussions, dibaca per halaman
    kirim_pengumuman   cari forum bertipe news (Announcements/Pengumuman) di
                       kursus itu, lalu mod_forum_add_discussion; bawaannya uji coba

mod_forum_add_discussion selalu menyimpan pesannya sebagai HTML, jadi isi
berbentuk teks biasa diubah dulu ke HTML (lihat teks.py). Balasan sebuah diskusi
bisa dibaca lewat panggil_fungsi("mod_forum_get_discussion_posts",
{"discussionid": ...}).
"""

from __future__ import annotations

from aswaya_mcp.aswaya_client import IsianDitolak, KlienAswaya, periksa_id
from aswaya_mcp.kursus import nama_kursus
from aswaya_mcp.teks import ringkas_html, teks_dari_html, waktu_iso
from aswaya_mcp.tulis import BentukIsi, HasilTulis, isi_sebagai_html, jalankan_tulis

JENIS_PENGUMUMAN = "news"
MAKS_DESKRIPSI = 300
MAKS_PESAN = 1000
MAKS_SUBJEK = 255
DISKUSI_PER_HALAMAN = 100
MAKS_HALAMAN_DISKUSI = 20


def bentuk_forum(klien: KlienAswaya, forum: dict) -> dict:
    """Satu forum dalam bentuk ringkas."""
    return {
        "id": forum.get("id"),
        "cmid": forum.get("cmid"),
        "nama": teks_dari_html(forum.get("name")),
        "jenis": forum.get("type"),
        "pengumuman": forum.get("type") == JENIS_PENGUMUMAN,
        "jumlah_diskusi": forum.get("numdiscussions"),
        "bisa_membuat_diskusi": forum.get("cancreatediscussions"),
        "url": klien.url_modul("forum", forum["cmid"]) if forum.get("cmid") else None,
        "deskripsi": ringkas_html(forum.get("intro"), MAKS_DESKRIPSI),
    }


def forum_kursus(klien: KlienAswaya, kursus_id: int) -> list[dict]:
    """Data mentah forum satu kursus."""
    forum = klien.panggil("mod_forum_get_forums_by_courses", {"courseids": [kursus_id]}) or []
    return [satu for satu in forum if satu.get("course") in (None, kursus_id)]


def daftar_forum(klien: KlienAswaya, kursus_id: int) -> dict:
    """Forum di satu kursus, termasuk forum pengumuman (jenis news)."""
    kursus_id = periksa_id(kursus_id, "kursus_id")
    forum = [bentuk_forum(klien, satu) for satu in forum_kursus(klien, kursus_id)]
    return {"kursus_id": kursus_id, "jumlah": len(forum), "forum": forum}


def bentuk_diskusi(klien: KlienAswaya, diskusi: dict) -> dict:
    """Satu diskusi beserta pesan pembukanya sebagai teks yang dipotong."""
    nomor = diskusi.get("discussion") or diskusi.get("id")
    return {
        "id": nomor,
        "subjek": teks_dari_html(diskusi.get("subject") or diskusi.get("name")),
        "penulis": diskusi.get("userfullname"),
        "dibuat": waktu_iso(diskusi.get("created")),
        "diubah": waktu_iso(diskusi.get("timemodified")),
        "jumlah_balasan": diskusi.get("numreplies"),
        "belum_dibaca": diskusi.get("numunread"),
        "disematkan": bool(diskusi.get("pinned")),
        "dikunci": bool(diskusi.get("locked")),
        "pesan": ringkas_html(diskusi.get("message"), MAKS_PESAN),
        "lampiran": [
            {"nama": berkas.get("filename"), "ukuran": berkas.get("filesize"), "url": berkas.get("fileurl")}
            for berkas in diskusi.get("attachments") or []
        ],
        "url": f"{klien.base_url}/mod/forum/discuss.php?d={nomor}",
    }


def diskusi_forum(klien: KlienAswaya, forum_id: int) -> dict:
    """Diskusi satu forum, terbaru dulu (urutan bawaan Moodle: posting terakhir).

    Dibaca per halaman sampai habis atau sampai 2000 diskusi.
    """
    forum_id = periksa_id(forum_id, "forum_id")
    diskusi: list[dict] = []
    for halaman in range(MAKS_HALAMAN_DISKUSI):
        hasil = klien.panggil(
            "mod_forum_get_forum_discussions",
            {"forumid": forum_id, "page": halaman, "perpage": DISKUSI_PER_HALAMAN},
        ) or {}
        baris = hasil.get("discussions") or []
        diskusi.extend(baris)
        if len(baris) < DISKUSI_PER_HALAMAN:
            break
    return {
        "forum_id": forum_id,
        "jumlah": len(diskusi),
        "diskusi": [bentuk_diskusi(klien, satu) for satu in diskusi],
    }


def forum_pengumuman(klien: KlienAswaya, kursus_id: int) -> dict:
    """Forum pengumuman (jenis news) di kursus ini; ditolak kalau tidak ada atau akun ini tidak boleh menulis."""
    calon = [satu for satu in forum_kursus(klien, kursus_id) if satu.get("type") == JENIS_PENGUMUMAN]
    if not calon:
        raise IsianDitolak(
            f"Kursus {kursus_id} tidak punya forum pengumuman (forum berjenis news) yang terlihat oleh akun ini"
        )
    forum = calon[0]
    if forum.get("cancreatediscussions") is False:
        raise IsianDitolak(
            f"Akun ini tidak boleh membuat diskusi di forum {teks_dari_html(forum.get('name'))!r} "
            f"(kursus {kursus_id}); biasanya hanya dosen pengampu yang boleh"
        )
    return forum


def kirim_pengumuman(
    klien: KlienAswaya,
    kursus_id: int,
    subjek: str,
    isi: str,
    *,
    kirim: bool = False,
    bentuk: BentukIsi = "teks",
) -> HasilTulis:
    """Buat pengumuman baru di forum pengumuman satu kursus. Bawaannya uji coba.

    Isi berupa teks biasa (bentuk="teks"): baris kosong memisahkan paragraf dan
    alamat http(s) menjadi tautan. bentuk="html" mengirim isinya apa adanya.
    Grupnya selalu bawaan Moodle (groupid 0), yaitu semua peserta kalau forum
    tidak memakai mode grup.
    """
    kursus_id = periksa_id(kursus_id, "kursus_id")
    subjek = " ".join((subjek or "").split())
    if not subjek:
        raise IsianDitolak("subjek tidak boleh kosong")
    if len(subjek) > MAKS_SUBJEK:
        raise IsianDitolak(f"subjek paling panjang {MAKS_SUBJEK} karakter, bukan {len(subjek)}")
    pesan_html = isi_sebagai_html(isi, bentuk, "isi")
    forum = forum_pengumuman(klien, kursus_id)
    parameter = {"forumid": forum["id"], "subject": subjek, "message": pesan_html}
    ringkasan = {
        "kursus_id": kursus_id,
        "kursus": nama_kursus(klien, kursus_id),
        "forum_id": forum["id"],
        "forum": teks_dari_html(forum.get("name")),
        "subjek": subjek,
        "isi": teks_dari_html(pesan_html),
    }
    hasil = jalankan_tulis(
        klien, "mod_forum_add_discussion", parameter, ringkasan,
        kirim=kirim, pesan_terkirim="Pengumuman terkirim.",
    )
    if hasil.terkirim and isinstance(hasil.hasil, dict) and hasil.hasil.get("discussionid"):
        hasil.ringkasan["url"] = f"{klien.base_url}/mod/forum/discuss.php?d={hasil.hasil['discussionid']}"
    return hasil
