"""Tugas (mod_assign): daftar tugas, pengumpulan per mahasiswa, dan pemberian nilai.

    daftar_tugas        mod_assign_get_assignments untuk satu kursus
    pengumpulan_tugas   mod_assign_list_participants (nama dan status semua
                        peserta, termasuk yang belum mengumpulkan) digabung dengan
                        mod_assign_get_submissions (berkas dan teks daring) dan
                        mod_assign_get_grades (nilai), per mahasiswa
    beri_nilai          mod_assign_save_grade, bawaannya uji coba

Kalau mod_assign_list_participants tidak tersedia, pengumpulan_tugas tetap jalan
dari data pengumpulan dan nilai saja, tanpa nama dan tanpa peserta yang belum
pernah membuka tugasnya.

Moodle menyimpan nilai -1 untuk "belum dinilai"; nilai itu dikembalikan sebagai
null. Tugas berkelompok menyimpan pengumpulannya dengan userid 0 dan groupid
kelompoknya, jadi pengumpulan seperti itu dipasangkan ke setiap anggota grup.
"""

from __future__ import annotations

from aswaya_mcp.aswaya_client import AswayaError, IsianDitolak, KlienAswaya, periksa_id
from aswaya_mcp.teks import potong, ringkas_html, teks_dari_html, waktu_iso
from aswaya_mcp.tulis import FORMAT_HTML_MOODLE, BentukIsi, HasilTulis, isi_sebagai_html, jalankan_tulis

MAKS_DESKRIPSI = 300
MAKS_TEKS_DARING = 2000

KETERANGAN_STATUS = {
    "new": "belum mengumpulkan",
    "draft": "draf, belum diserahkan",
    "submitted": "sudah dikumpulkan",
    "reopened": "dibuka ulang untuk percobaan baru",
}


# --- daftar tugas --------------------------------------------------------------


def bentuk_tugas(klien: KlienAswaya, tugas: dict) -> dict:
    """Satu tugas dalam bentuk ringkas. Nilai negatif di Moodle berarti skala, 0 berarti tanpa nilai."""
    nilai = tugas.get("grade") or 0
    return {
        "id": tugas.get("id"),
        "cmid": tugas.get("cmid"),
        "nama": teks_dari_html(tugas.get("name")),
        "dibuka": waktu_iso(tugas.get("allowsubmissionsfromdate")),
        "tenggat": waktu_iso(tugas.get("duedate")),
        "batas_akhir": waktu_iso(tugas.get("cutoffdate")),
        "tenggat_penilaian": waktu_iso(tugas.get("gradingduedate")),
        "nilai_maks": float(nilai) if nilai > 0 else None,
        "skala_id": -int(nilai) if nilai < 0 else None,
        "berkelompok": bool(tugas.get("teamsubmission")),
        "url": klien.url_modul("assign", tugas["cmid"]) if tugas.get("cmid") else None,
        "deskripsi": ringkas_html(tugas.get("intro"), MAKS_DESKRIPSI),
    }


def tugas_kursus(klien: KlienAswaya, kursus_id: int) -> tuple[dict | None, list[str]]:
    """Data mentah kursus dari mod_assign_get_assignments beserta peringatan Moodle-nya."""
    hasil = klien.panggil("mod_assign_get_assignments", {"courseids": [kursus_id]}) or {}
    peringatan = [str(satu.get("message") or satu) for satu in hasil.get("warnings") or []]
    for kursus in hasil.get("courses") or []:
        if kursus.get("id") == kursus_id:
            return kursus, peringatan
    return None, peringatan


def daftar_tugas(klien: KlienAswaya, kursus_id: int) -> dict:
    """Tugas (assignment) satu kursus: tenggat, batas akhir, nilai maksimum, dan tautannya.

    Kalau kursus itu tidak bisa dibuka akun ini, `tugas` kosong dan
    `peringatan` memuat pesan Moodle-nya.
    """
    kursus_id = periksa_id(kursus_id, "kursus_id")
    kursus, peringatan = tugas_kursus(klien, kursus_id)
    tugas = [bentuk_tugas(klien, satu) for satu in (kursus or {}).get("assignments") or []]
    return {
        "kursus_id": kursus_id,
        "kursus": teks_dari_html(kursus.get("fullname")) if kursus else None,
        "jumlah": len(tugas),
        "tugas": tugas,
        "peringatan": peringatan,
    }


# --- pengumpulan --------------------------------------------------------------


def berkas_pengumpulan(pengumpulan: dict) -> list[dict]:
    """Berkas dari plugin file pengumpulan."""
    hasil = []
    for plugin in pengumpulan.get("plugins") or []:
        for area in plugin.get("fileareas") or []:
            for berkas in area.get("files") or []:
                hasil.append({
                    "nama": berkas.get("filename"),
                    "ukuran": berkas.get("filesize"),
                    "jenis": berkas.get("mimetype"),
                    "url": berkas.get("fileurl"),
                    "diubah": waktu_iso(berkas.get("timemodified")),
                })
    return hasil


def teks_daring(pengumpulan: dict) -> str:
    """Teks daring (plugin onlinetext) sebagai teks biasa yang dipotong."""
    for plugin in pengumpulan.get("plugins") or []:
        for isian in plugin.get("editorfields") or []:
            if isian.get("name") == "onlinetext" and isian.get("text"):
                return potong(teks_dari_html(isian["text"]), MAKS_TEKS_DARING)
    return ""


def terbaru_per_kunci(baris: list[dict], kunci) -> dict:
    """Baris dengan attemptnumber terbesar untuk setiap kunci (userid atau groupid)."""
    hasil: dict = {}
    for satu in baris:
        nilai_kunci = kunci(satu)
        lama = hasil.get(nilai_kunci)
        if lama is None or (satu.get("attemptnumber") or 0) >= (lama.get("attemptnumber") or 0):
            hasil[nilai_kunci] = satu
    return hasil


def daftar_peserta_tugas(klien: KlienAswaya, tugas_id: int) -> list[dict] | None:
    """Peserta tugas dengan nama dan status; None kalau mod_assign_list_participants tidak tersedia."""
    if not klien.tersedia("mod_assign_list_participants"):
        return None
    parameter = {"assignid": tugas_id, "groupid": 0, "filter": "", "onlyids": True, "includeenrolments": False}
    return klien.panggil("mod_assign_list_participants", parameter) or []


def entri_kosong(user_id: int) -> dict:
    """Baris satu mahasiswa sebelum data pengumpulan dan nilai dipasang."""
    return {
        "user_id": user_id,
        "nama": None,
        "grup": None,
        "status": "new",
        "keterangan": KETERANGAN_STATUS["new"],
        "perlu_dinilai": False,
        "perpanjangan": False,
        "waktu_kumpul": None,
        "percobaan": None,
        "berkas": [],
        "teks_daring": "",
        "nilai": None,
        "dinilai_pada": None,
    }


def pasang_pengumpulan(entri: dict, pengumpulan: dict) -> None:
    """Isi status, waktu, berkas, dan teks daring satu pengumpulan ke baris mahasiswa."""
    status = pengumpulan.get("status") or "new"
    entri["status"] = status
    entri["keterangan"] = KETERANGAN_STATUS.get(status, status)
    entri["waktu_kumpul"] = waktu_iso(pengumpulan.get("timemodified")) if status != "new" else None
    entri["percobaan"] = pengumpulan.get("attemptnumber")
    entri["berkas"] = berkas_pengumpulan(pengumpulan)
    entri["teks_daring"] = teks_daring(pengumpulan)
    if pengumpulan.get("gradingstatus") == "notgraded" and status == "submitted":
        entri["perlu_dinilai"] = True


def angka_nilai(teks) -> float | None:
    """'85.00000' -> 85.0; nilai -1 (belum dinilai) dan isian kosong menjadi None."""
    try:
        angka = float(teks)
    except (TypeError, ValueError):
        return None
    return None if angka < 0 else angka


def gabungkan(peserta: list[dict] | None, pengumpulan: list[dict], nilai: list[dict]) -> list[dict]:
    """Satu baris per mahasiswa dari peserta, pengumpulan terbaru, dan nilai terbaru."""
    per_user: dict[int, dict] = {}
    anggota_grup: dict[int, list[int]] = {}
    for satu in peserta or []:
        entri = per_user.setdefault(satu["id"], entri_kosong(satu["id"]))
        entri["nama"] = satu.get("fullname")
        entri["grup"] = teks_dari_html(satu.get("groupname")) or None
        entri["perlu_dinilai"] = bool(satu.get("requiregrading"))
        entri["perpanjangan"] = bool(satu.get("grantedextension"))
        if satu.get("submissionstatus"):
            entri["status"] = satu["submissionstatus"]
            entri["keterangan"] = KETERANGAN_STATUS.get(satu["submissionstatus"], satu["submissionstatus"])
        if satu.get("groupid"):
            anggota_grup.setdefault(int(satu["groupid"]), []).append(satu["id"])

    perorangan = terbaru_per_kunci([s for s in pengumpulan if s.get("userid")], lambda s: s["userid"])
    kelompok = terbaru_per_kunci([s for s in pengumpulan if not s.get("userid") and s.get("groupid")], lambda s: s["groupid"])
    for groupid, satu in kelompok.items():
        for user_id in anggota_grup.get(int(groupid), []):
            pasang_pengumpulan(per_user[user_id], satu)
    for user_id, satu in perorangan.items():
        pasang_pengumpulan(per_user.setdefault(user_id, entri_kosong(user_id)), satu)

    for user_id, satu in terbaru_per_kunci(nilai, lambda g: g.get("userid")).items():
        entri = per_user.setdefault(user_id, entri_kosong(user_id))
        entri["nilai"] = angka_nilai(satu.get("grade"))
        entri["dinilai_pada"] = waktu_iso(satu.get("timemodified")) if entri["nilai"] is not None else None
    return sorted(per_user.values(), key=lambda entri: (str(entri["nama"] or "").casefold(), entri["user_id"]))


def ringkas_pengumpulan(mahasiswa: list[dict]) -> dict:
    """Hitungan per status untuk satu tugas."""
    return {
        "peserta": len(mahasiswa),
        "dikumpulkan": sum(1 for satu in mahasiswa if satu["status"] == "submitted"),
        "draf": sum(1 for satu in mahasiswa if satu["status"] == "draft"),
        "belum": sum(1 for satu in mahasiswa if satu["status"] in ("new", "reopened")),
        "dinilai": sum(1 for satu in mahasiswa if satu["nilai"] is not None),
        "perlu_dinilai": sum(1 for satu in mahasiswa if satu["perlu_dinilai"]),
    }


def pengumpulan_tugas(klien: KlienAswaya, tugas_id: int) -> dict:
    """Status pengumpulan dan nilai setiap mahasiswa untuk satu tugas.

    Tiap baris berisi user_id, nama, grup, status Moodle (new, draft, submitted,
    reopened) beserta keterangannya, perlu_dinilai, waktu_kumpul, berkas (fileurl
    tanpa token), teks_daring (dipotong), nilai (null kalau belum dinilai), dan
    dinilai_pada.
    """
    tugas_id = periksa_id(tugas_id, "tugas_id")
    hasil_kumpul = klien.panggil("mod_assign_get_submissions", {"assignmentids": [tugas_id]}) or {}
    hasil_nilai = klien.panggil("mod_assign_get_grades", {"assignmentids": [tugas_id]}) or {}
    peserta = daftar_peserta_tugas(klien, tugas_id)
    pengumpulan = [
        kumpulan
        for tugas in hasil_kumpul.get("assignments") or []
        if tugas.get("assignmentid") == tugas_id
        for kumpulan in tugas.get("submissions") or []
    ]
    nilai = [
        satu
        for tugas in hasil_nilai.get("assignments") or []
        if tugas.get("assignmentid") == tugas_id
        for satu in tugas.get("grades") or []
    ]
    mahasiswa = gabungkan(peserta, pengumpulan, nilai)
    peringatan = [
        str(satu.get("message") or satu)
        for satu in (hasil_kumpul.get("warnings") or []) + (hasil_nilai.get("warnings") or [])
    ]
    if peserta is None:
        peringatan.append(
            "mod_assign_list_participants tidak tersedia; peserta yang belum pernah mengumpulkan tidak terlihat"
        )
    return {
        "tugas_id": tugas_id,
        "ringkasan": ringkas_pengumpulan(mahasiswa),
        "mahasiswa": mahasiswa,
        "peringatan": peringatan,
    }


# --- beri nilai ----------------------------------------------------------------


def keterangan_tugas(klien: KlienAswaya, tugas_id: int) -> dict | None:
    """Nama, kursus, nilai maksimum, dan konfigurasi plugin satu tugas; None kalau tidak terbaca."""
    if not klien.tersedia("core_course_get_course_module_by_instance"):
        return None
    try:
        modul = klien.panggil("core_course_get_course_module_by_instance", {"module": "assign", "instance": tugas_id})
    except AswayaError:
        return None
    kursus_id = (modul or {}).get("cm", {}).get("course")
    if not kursus_id:
        return None
    kursus, _ = tugas_kursus(klien, int(kursus_id))
    for tugas in (kursus or {}).get("assignments") or []:
        if tugas.get("id") == tugas_id:
            return {"tugas": tugas, "kursus_id": int(kursus_id), "kursus": teks_dari_html((kursus or {}).get("fullname"))}
    return None


def komentar_aktif(tugas: dict) -> bool | None:
    """Apakah umpan balik komentar aktif di tugas ini; None kalau konfigurasinya tidak terbaca."""
    for konfigurasi in tugas.get("configs") or []:
        if (
            konfigurasi.get("subtype") == "assignfeedback"
            and konfigurasi.get("plugin") == "comments"
            and konfigurasi.get("name") == "enabled"
        ):
            return str(konfigurasi.get("value")) == "1"
    return None


def nilai_sekarang(klien: KlienAswaya, tugas_id: int, user_id: int) -> float | None:
    """Nilai terakhir seorang mahasiswa untuk tugas ini; None kalau belum ada atau tidak terbaca."""
    try:
        hasil = klien.panggil("mod_assign_get_grades", {"assignmentids": [tugas_id]}) or {}
    except AswayaError:
        return None
    nilai = [
        satu
        for tugas in hasil.get("assignments") or []
        if tugas.get("assignmentid") == tugas_id
        for satu in tugas.get("grades") or []
        if satu.get("userid") == user_id
    ]
    terbaru = terbaru_per_kunci(nilai, lambda g: g.get("userid")).get(user_id)
    return angka_nilai(terbaru.get("grade")) if terbaru else None


def periksa_nilai(nilai, tugas: dict | None) -> float:
    """Nilai sebagai angka yang sah untuk tugas ini; nilai negatif atau di atas maksimum ditolak."""
    try:
        angka = float(nilai)
    except (TypeError, ValueError):
        raise IsianDitolak(f"nilai harus berupa angka, bukan {nilai!r}") from None
    if angka != angka or angka < 0:
        raise IsianDitolak(f"nilai tidak boleh negatif atau kosong, bukan {nilai!r}")
    if tugas is None:
        return angka
    maks = tugas.get("grade") or 0
    if maks == 0:
        raise IsianDitolak(f"Tugas {teks_dari_html(tugas.get('name'))!r} tidak memakai nilai (grade 0 di Moodle)")
    if maks > 0 and angka > maks:
        raise IsianDitolak(f"nilai {angka:g} melebihi nilai maksimum tugas ini ({float(maks):g})")
    if maks < 0 and angka != int(angka):
        raise IsianDitolak("Tugas ini memakai skala; nilai harus nomor butir skala (bilangan bulat)")
    return angka


def peserta_tugas(klien: KlienAswaya, tugas_id: int, user_id: int) -> dict | None:
    """Keterangan satu peserta tugas (nama, status); None kalau fungsinya tidak tersedia.

    Pengguna yang bukan peserta tugas ini ditolak dengan pesan Moodle-nya.
    """
    if not klien.tersedia("mod_assign_get_participant"):
        return None
    try:
        return klien.panggil("mod_assign_get_participant", {"assignid": tugas_id, "userid": user_id, "embeduser": False})
    except AswayaError as galat:
        raise IsianDitolak(f"user_id {user_id} tidak bisa dinilai di tugas {tugas_id}: {galat}") from galat


def beri_nilai(
    klien: KlienAswaya,
    tugas_id: int,
    user_id: int,
    nilai,
    umpan_balik: str = "",
    *,
    kirim: bool = False,
    bentuk: BentukIsi = "teks",
) -> HasilTulis:
    """Simpan nilai (dan umpan balik) seorang mahasiswa untuk satu tugas. Bawaannya uji coba.

    Sebelum apa pun dikirim, nilai diperiksa terhadap nilai maksimum tugas dan
    pratinjau menyebut nama mahasiswa, nilai lama, dan nilai baru. Umpan balik
    berupa teks biasa (bentuk="teks") atau HTML (bentuk="html"); kosong berarti
    umpan balik lama tidak disentuh. Percobaan yang dinilai selalu yang terakhir,
    dan untuk tugas berkelompok nilainya hanya untuk mahasiswa ini
    (applytoall=0). Kalau tugas memakai panduan penilaian lanjutan (rubrik),
    Moodle mengabaikan nilai ini.
    """
    tugas_id = periksa_id(tugas_id, "tugas_id")
    user_id = periksa_id(user_id, "user_id")
    if not isinstance(umpan_balik, str):
        raise IsianDitolak("umpan_balik harus berupa teks")
    periksa_nilai(nilai, None)
    keterangan = keterangan_tugas(klien, tugas_id)
    tugas = keterangan["tugas"] if keterangan else None
    angka = periksa_nilai(nilai, tugas)
    peserta = peserta_tugas(klien, tugas_id, user_id)

    parameter = {
        "assignmentid": tugas_id,
        "userid": user_id,
        "grade": angka,
        "attemptnumber": -1,
        "addattempt": False,
        "workflowstate": "",
        "applytoall": False,
    }
    peringatan = []
    if umpan_balik.strip():
        parameter["plugindata"] = {
            "assignfeedbackcomments_editor": {
                "text": isi_sebagai_html(umpan_balik, bentuk, "umpan_balik"),
                "format": FORMAT_HTML_MOODLE,
            }
        }
        if tugas is not None and komentar_aktif(tugas) is False:
            peringatan.append("Umpan balik komentar tidak aktif di tugas ini, jadi teks umpan baliknya akan diabaikan Moodle")
    if tugas is None:
        peringatan.append("Keterangan tugas tidak terbaca, jadi nilai maksimumnya tidak diperiksa")

    maks = (tugas or {}).get("grade") or 0
    ringkasan = {
        "tugas_id": tugas_id,
        "tugas": teks_dari_html(tugas.get("name")) if tugas else None,
        "kursus": keterangan["kursus"] if keterangan else None,
        "user_id": user_id,
        "mahasiswa": (peserta or {}).get("fullname"),
        "status_pengumpulan": (peserta or {}).get("submissionstatus"),
        "nilai_lama": nilai_sekarang(klien, tugas_id, user_id),
        "nilai_baru": angka,
        "nilai_maks": float(maks) if maks > 0 else None,
        "umpan_balik": umpan_balik.strip() or None,
    }
    return jalankan_tulis(
        klien, "mod_assign_save_grade", parameter, ringkasan,
        kirim=kirim, peringatan=peringatan, pesan_terkirim="Nilai tersimpan di Aswaya.",
    )
