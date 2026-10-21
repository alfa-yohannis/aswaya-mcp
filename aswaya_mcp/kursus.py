"""Kursus: daftar kursus pemakai, isi satu kursus, dan pesertanya.

    daftar_kursus    core_enrol_get_users_courses, ditambah nama kategori dari
                     core_course_get_categories kalau fungsi itu tersedia
    isi_kursus       core_course_get_contents: section, modul, dan berkasnya
    peserta_kursus   core_enrol_get_enrolled_users

Data peserta sengaja diminta seperlunya lewat opsi userfields. Bawaannya hanya
id, nama lengkap, peran, grup, dan waktu akses terakhir. Email dan idnumber
(NIM) baru diminta dari Aswaya kalau lengkap=True, supaya data pribadi mahasiswa
tidak ikut tersimpan di riwayat percakapan asisten AI tanpa keperluan.
"""

from __future__ import annotations

from aswaya_mcp.aswaya_client import AswayaError, KlienAswaya, periksa_id
from aswaya_mcp.teks import ringkas_html, tanggal_iso, teks_dari_html, waktu_iso

BIDANG_PESERTA = ("id", "fullname", "roles", "groups", "lastaccess", "lastcourseaccess")
BIDANG_PESERTA_LENGKAP = ("email", "idnumber")
MAKS_RINGKASAN = 500
MAKS_DESKRIPSI = 300


# --- daftar kursus -------------------------------------------------------------


def nama_kategori(klien: KlienAswaya, ids: set[int]) -> dict[int, str]:
    """Nama kategori untuk id-id ini; kosong kalau fungsinya tidak tersedia atau ditolak."""
    if not ids or not klien.tersedia("core_course_get_categories"):
        return {}
    parameter = {
        "criteria": [{"key": "ids", "value": ",".join(str(nomor) for nomor in sorted(ids))}],
        "addsubcategories": False,
    }
    try:
        kategori = klien.panggil("core_course_get_categories", parameter)
    except AswayaError:
        return {}
    return {int(satu["id"]): teks_dari_html(satu.get("name")) for satu in kategori or [] if "id" in satu}


def bentuk_kursus(klien: KlienAswaya, kursus: dict, kategori: dict[int, str]) -> dict:
    """Satu kursus dalam bentuk ringkas."""
    id_kategori = kursus.get("category")
    return {
        "id": kursus["id"],
        "shortname": teks_dari_html(kursus.get("shortname")),
        "fullname": teks_dari_html(kursus.get("fullname")),
        "kategori": kategori.get(id_kategori) if id_kategori else None,
        "kategori_id": id_kategori,
        "mulai": tanggal_iso(kursus.get("startdate")),
        "selesai": tanggal_iso(kursus.get("enddate")),
        "visible": bool(kursus.get("visible", 1)),
        "url": klien.url_kursus(kursus["id"]),
    }


def cocok_dengan(kursus: dict, kata: str) -> bool:
    """Apakah potongan teks `kata` ada di nama, nama pendek, atau kategori kursus."""
    sasaran = " ".join(str(kursus.get(kunci) or "") for kunci in ("fullname", "shortname", "kategori"))
    return kata in sasaran.casefold()


def daftar_kursus(klien: KlienAswaya, cari: str = "") -> dict:
    """Kursus yang diikuti pemakai, terbaru dulu, disaring dengan potongan teks `cari`.

    Saringannya mencocokkan nama lengkap, nama pendek, dan nama kategori tanpa
    membedakan huruf besar dan kecil.
    """
    semua = klien.panggil(
        "core_enrol_get_users_courses", {"userid": klien.userid, "returnusercount": False}
    ) or []
    kategori = nama_kategori(klien, {int(satu["category"]) for satu in semua if satu.get("category")})
    kursus = [bentuk_kursus(klien, satu, kategori) for satu in semua]
    kata = (cari or "").strip().casefold()
    if kata:
        kursus = [satu for satu in kursus if cocok_dengan(satu, kata)]
    kursus.sort(key=lambda satu: satu["fullname"].casefold())
    kursus.sort(key=lambda satu: satu["mulai"] or "", reverse=True)
    return {"jumlah": len(kursus), "cari": cari or "", "kursus": kursus}


def nama_kursus(klien: KlienAswaya, kursus_id: int) -> str | None:
    """Nama lengkap kursus untuk pratinjau; None kalau tidak bisa dibaca."""
    if not klien.tersedia("core_course_get_courses_by_field"):
        return None
    try:
        hasil = klien.panggil("core_course_get_courses_by_field", {"field": "id", "value": kursus_id})
    except AswayaError:
        return None
    for kursus in (hasil or {}).get("courses", []):
        if kursus.get("id") == kursus_id:
            return teks_dari_html(kursus.get("fullname"))
    return None


# --- isi kursus ----------------------------------------------------------------


def bentuk_berkas(isi: dict) -> dict:
    """Satu entri `contents` modul: berkas, tautan luar, atau isi halaman."""
    return {
        "nama": isi.get("filename"),
        "tipe": isi.get("type"),
        "path": isi.get("filepath"),
        "ukuran": isi.get("filesize"),
        "jenis": isi.get("mimetype"),
        "url": isi.get("fileurl"),
        "diubah": waktu_iso(isi.get("timemodified")),
    }


def bentuk_modul(klien: KlienAswaya, modul: dict) -> dict:
    """Satu modul (aktivitas atau sumber belajar) di dalam section."""
    return {
        "id": modul.get("id"),
        "nama": teks_dari_html(modul.get("name")),
        "jenis": modul.get("modname"),
        "instance": modul.get("instance"),
        "visible": bool(modul.get("visible", 1)),
        "url": modul.get("url") or (klien.url_modul(modul["modname"], modul["id"]) if modul.get("modname") else None),
        "deskripsi": ringkas_html(modul.get("description"), MAKS_DESKRIPSI),
        "tanggal": [
            {"label": teks_dari_html(tanggal.get("label")), "waktu": waktu_iso(tanggal.get("timestamp"))}
            for tanggal in modul.get("dates") or []
        ],
        "berkas": [bentuk_berkas(isi) for isi in modul.get("contents") or []],
    }


def bentuk_section(klien: KlienAswaya, section: dict) -> dict:
    """Satu section kursus beserta modulnya."""
    return {
        "id": section.get("id"),
        "nomor": section.get("section"),
        "nama": teks_dari_html(section.get("name")),
        "visible": bool(section.get("visible", 1)),
        "ringkasan": ringkas_html(section.get("summary"), MAKS_RINGKASAN),
        "modul": [bentuk_modul(klien, modul) for modul in section.get("modules") or []],
    }


def isi_kursus(klien: KlienAswaya, kursus_id: int) -> dict:
    """Section dan modul satu kursus beserta berkasnya.

    `url` tiap berkas adalah fileurl Moodle (webservice/pluginfile.php/...) tanpa
    token; unduh lewat unduh_berkas, yang menambahkan tokennya sendiri.
    Deskripsi dan ringkasan diubah ke teks biasa lalu dipotong.
    """
    kursus_id = periksa_id(kursus_id, "kursus_id")
    sections = klien.panggil("core_course_get_contents", {"courseid": kursus_id}) or []
    hasil = [bentuk_section(klien, section) for section in sections]
    return {
        "kursus_id": kursus_id,
        "url": klien.url_kursus(kursus_id),
        "jumlah_section": len(hasil),
        "jumlah_modul": sum(len(section["modul"]) for section in hasil),
        "section": hasil,
    }


# --- peserta -------------------------------------------------------------------


def bentuk_peserta(pengguna: dict, lengkap: bool) -> dict:
    """Satu peserta; email dan idnumber hanya kalau `lengkap`."""
    hasil = {
        "id": pengguna.get("id"),
        "nama": pengguna.get("fullname"),
        "peran": [peran.get("shortname") for peran in pengguna.get("roles") or []],
        "grup": [teks_dari_html(grup.get("name")) for grup in pengguna.get("groups") or []],
        "akses_terakhir": waktu_iso(pengguna.get("lastcourseaccess")),
        "akses_terakhir_situs": waktu_iso(pengguna.get("lastaccess")),
    }
    if lengkap:
        hasil["email"] = pengguna.get("email")
        hasil["idnumber"] = pengguna.get("idnumber")
    return hasil


def punya_peran(pengguna: dict, peran: str) -> bool:
    """Apakah pengguna memegang peran dengan shortname atau nama `peran` (tanpa membedakan huruf)."""
    kata = peran.casefold()
    return any(
        kata in (str(satu.get("shortname") or "").casefold(), teks_dari_html(satu.get("name")).casefold())
        for satu in pengguna.get("roles") or []
    )


def hitung_peran(pengguna_semua: list[dict]) -> list[dict]:
    """Peran yang ada di kursus beserta jumlah pemegangnya, untuk menyaring ulang."""
    hitungan: dict[str, dict] = {}
    for pengguna in pengguna_semua:
        for peran in pengguna.get("roles") or []:
            kunci = str(peran.get("shortname") or "")
            entri = hitungan.setdefault(kunci, {"shortname": kunci, "nama": teks_dari_html(peran.get("name")), "jumlah": 0})
            entri["jumlah"] += 1
    return sorted(hitungan.values(), key=lambda entri: -entri["jumlah"])


def peserta_kursus(klien: KlienAswaya, kursus_id: int, peran: str = "", lengkap: bool = False) -> dict:
    """Peserta satu kursus, boleh disaring per peran (mis. student, editingteacher).

    `peran` dicocokkan dengan shortname atau nama peran tanpa membedakan huruf
    besar dan kecil. `peran_tersedia` menyebut peran yang ada di kursus itu.
    Email dan idnumber (NIM) hanya diminta dan dikembalikan kalau lengkap=True.
    """
    kursus_id = periksa_id(kursus_id, "kursus_id")
    bidang = BIDANG_PESERTA + (BIDANG_PESERTA_LENGKAP if lengkap else ())
    parameter = {"courseid": kursus_id, "options": [{"name": "userfields", "value": ",".join(bidang)}]}
    semua = klien.panggil("core_enrol_get_enrolled_users", parameter) or []
    terpilih = [pengguna for pengguna in semua if not peran or punya_peran(pengguna, peran.strip())]
    peserta = sorted((bentuk_peserta(pengguna, lengkap) for pengguna in terpilih), key=lambda satu: str(satu["nama"]).casefold())
    return {
        "kursus_id": kursus_id,
        "peran": peran or "",
        "lengkap": lengkap,
        "jumlah": len(peserta),
        "peran_tersedia": hitung_peran(semua),
        "peserta": peserta,
    }
