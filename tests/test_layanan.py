"""Uji fungsi layanan per area di atas Aswaya tiruan: kursus, tugas, nilai, forum, tenggat, berkas, fungsi, pesan."""

from __future__ import annotations

import json

import pytest

from aswaya_mcp import berkas, forum, fungsi, kalender, kursus, nilai, pesan, tugas
from aswaya_mcp.aswaya_client import FungsiTidakTersedia, HasilTidakPasti, IsianDitolak
from aswaya_mcp.konfigurasi import akar_proyek
from conftest import (
    FORUM_PENGUMUMAN,
    FORUM_UMUM,
    KUNCI_PRIBADI_UJI,
    KURSUS_LAMA,
    KURSUS_SECTION,
    KURSUS_WEB,
    SITUS,
    TOKEN_UJI,
    TUGAS_1,
    TUGAS_REFLEKSI,
    detik,
)

URL_SLIDE = f"{SITUS}/webservice/pluginfile.php/88/mod_resource/content/1/slide-html.pdf"


# --- kursus -------------------------------------------------------------------


def test_daftar_kursus_terbaru_dulu_dengan_kategori(klien):
    hasil = kursus.daftar_kursus(klien)

    assert hasil["jumlah"] == 3
    assert [satu["id"] for satu in hasil["kursus"]] == [KURSUS_SECTION, KURSUS_WEB, KURSUS_LAMA]
    web = next(satu for satu in hasil["kursus"] if satu["id"] == KURSUS_WEB)
    assert web == {
        "id": KURSUS_WEB, "shortname": "IF140303-SRP", "fullname": "Pengembangan Aplikasi Web (Serpong)",
        "kategori": "Informatika", "kategori_id": 3, "mulai": "2026-09-01", "selesai": "2027-01-31",
        "visible": True, "url": f"{SITUS}/course/view.php?id={KURSUS_WEB}",
    }


def test_daftar_kursus_entitas_html_diterjemahkan_dan_tersembunyi_ditandai(klien):
    lama = next(satu for satu in kursus.daftar_kursus(klien)["kursus"] if satu["id"] == KURSUS_LAMA)

    assert lama["fullname"] == "Basis Data & SQL"
    assert lama["visible"] is False and lama["kategori"] == "Sistem Informasi"


@pytest.mark.parametrize("cari, harapan", [("web", [KURSUS_WEB]), ("if1402", [KURSUS_SECTION]), ("sistem informasi", [KURSUS_LAMA])])
def test_daftar_kursus_disaring(klien, cari, harapan):
    assert [satu["id"] for satu in kursus.daftar_kursus(klien, cari)["kursus"]] == harapan


def test_daftar_kursus_tanpa_fungsi_kategori(klien, situs):
    situs.fungsi.remove("core_course_get_categories")

    hasil = kursus.daftar_kursus(klien)

    assert all(satu["kategori"] is None for satu in hasil["kursus"])
    assert situs.panggilan("core_course_get_categories") == []


def test_isi_kursus_section_modul_dan_berkas(klien):
    hasil = kursus.isi_kursus(klien, KURSUS_WEB)

    assert hasil["jumlah_section"] == 2 and hasil["jumlah_modul"] == 3
    slide = hasil["section"][1]["modul"][0]
    assert slide["jenis"] == "resource" and slide["deskripsi"] == "Bacaan wajib sebelum kelas."
    assert slide["berkas"][0]["nama"] == "slide-html.pdf"
    assert slide["berkas"][0]["url"] == URL_SLIDE
    assert TOKEN_UJI not in json.dumps(hasil)
    tugas_modul = hasil["section"][1]["modul"][1]
    assert tugas_modul["tanggal"] == [{"label": "Due:", "waktu": "2026-09-15T23:59+07:00"}]
    assert hasil["section"][0]["ringkasan"] == "Selamat datang di kelas."


def test_isi_kursus_id_tidak_sah_ditolak_tanpa_permintaan(klien, situs):
    with pytest.raises(IsianDitolak):
        kursus.isi_kursus(klien, "lima")
    assert situs.permintaan == []


def test_peserta_bawaan_tanpa_email_dan_nim(klien, situs):
    hasil = kursus.peserta_kursus(klien, KURSUS_WEB)

    teks = json.dumps(hasil)
    assert "@contoh.ac.id" not in teks and "2026100001" not in teks
    bidang = situs.panggilan("core_enrol_get_enrolled_users")[0]["options"][0]
    assert bidang == {"name": "userfields", "value": "id,fullname,roles,groups,lastaccess,lastcourseaccess"}
    peter = next(satu for satu in hasil["peserta"] if satu["id"] == 101)
    assert peter == {
        "id": 101, "nama": "Peter Parker", "peran": ["student"], "grup": ["Kelas A"],
        "akses_terakhir": "2026-10-19T20:00+07:00", "akses_terakhir_situs": "2026-10-20T08:15+07:00",
    }


def test_peserta_lengkap_menyertakan_email_dan_nim(klien, situs):
    hasil = kursus.peserta_kursus(klien, KURSUS_WEB, lengkap=True)

    peter = next(satu for satu in hasil["peserta"] if satu["id"] == 101)
    assert peter["email"] == "peter.parker@contoh.ac.id" and peter["idnumber"] == "2026100001"
    assert situs.panggilan("core_enrol_get_enrolled_users")[0]["options"][0]["value"].endswith(",email,idnumber")


@pytest.mark.parametrize("peran", ["student", "Mahasiswa", "STUDENT"])
def test_peserta_disaring_per_peran(klien, peran):
    hasil = kursus.peserta_kursus(klien, KURSUS_WEB, peran=peran)

    assert hasil["jumlah"] == 4
    assert {"shortname": "student", "nama": "Mahasiswa", "jumlah": 4} in hasil["peran_tersedia"]


def test_peserta_belum_pernah_masuk_kursus(klien):
    natasha = next(satu for satu in kursus.peserta_kursus(klien, KURSUS_WEB)["peserta"] if satu["id"] == 104)

    assert natasha["akses_terakhir"] is None


# --- tugas --------------------------------------------------------------------


def test_daftar_tugas(klien):
    hasil = tugas.daftar_tugas(klien, KURSUS_WEB)

    assert hasil["kursus"] == "Pengembangan Aplikasi Web (Serpong)" and hasil["jumlah"] == 2
    pertama = hasil["tugas"][0]
    assert pertama["id"] == TUGAS_1 and pertama["nilai_maks"] == 100.0
    assert pertama["tenggat"] == "2026-09-15T23:59+07:00"
    assert pertama["url"] == f"{SITUS}/mod/assign/view.php?id=1234"
    assert hasil["tugas"][1]["nilai_maks"] is None


def test_daftar_tugas_kursus_tanpa_akses_memberi_peringatan(klien):
    hasil = tugas.daftar_tugas(klien, 9999)

    assert hasil["tugas"] == [] and hasil["peringatan"] == ["No access rights in course context"]


def test_pengumpulan_tugas_menggabungkan_peserta_pengumpulan_dan_nilai(klien):
    hasil = tugas.pengumpulan_tugas(klien, TUGAS_1)

    assert hasil["ringkasan"] == {"peserta": 4, "dikumpulkan": 1, "draf": 1, "belum": 2, "dinilai": 1, "perlu_dinilai": 1}
    per_nama = {satu["nama"]: satu for satu in hasil["mahasiswa"]}
    peter = per_nama["Peter Parker"]
    assert peter["status"] == "submitted" and peter["keterangan"] == "sudah dikumpulkan"
    assert peter["nilai"] == 85.0 and peter["dinilai_pada"] == "2026-09-18T09:00+07:00"
    assert peter["berkas"][0]["nama"] == "profil-peter.zip"
    assert peter["teks_daring"] == "Tautan repo saya ada di berkas."
    assert per_nama["Diana Prince"]["nilai"] is None  # -1 di Moodle berarti belum dinilai
    assert per_nama["Bruce Banner"]["keterangan"] == "belum mengumpulkan"
    assert per_nama["Natasha Romanoff"]["perpanjangan"] is True


def test_pengumpulan_tanpa_list_participants_tetap_jalan(klien, situs):
    situs.fungsi.remove("mod_assign_list_participants")

    hasil = tugas.pengumpulan_tugas(klien, TUGAS_1)

    assert {satu["user_id"] for satu in hasil["mahasiswa"]} == {101, 102}
    assert any("list_participants" in satu for satu in hasil["peringatan"])


def test_pengumpulan_berkelompok_dipasangkan_ke_anggota_grup(klien, situs):
    situs.data["pengumpulan"][TUGAS_1] = [
        {"id": 5, "userid": 0, "groupid": 70, "attemptnumber": 0, "status": "submitted",
         "timemodified": detik("2026-09-14 21:30"), "plugins": []},
    ]

    hasil = tugas.pengumpulan_tugas(klien, TUGAS_1)

    assert all(satu["status"] == "submitted" for satu in hasil["mahasiswa"])


# --- nilai --------------------------------------------------------------------


def test_nilai_kursus(klien):
    hasil = nilai.nilai_kursus(klien, KURSUS_WEB)

    assert [item["nama"] for item in hasil["item"]] == ["Tugas 1: Halaman Statis", "Kuis HTML", "Total kursus"]
    assert hasil["item"][1]["maks"] == 10.0
    diana = next(satu for satu in hasil["mahasiswa"] if satu["user_id"] == 102)
    assert diana["nilai"] == {"401": None, "402": 7.5, "400": 7.5}
    assert "2026100002" not in json.dumps(hasil)


# --- forum --------------------------------------------------------------------


def test_daftar_forum(klien):
    hasil = forum.daftar_forum(klien, KURSUS_WEB)

    assert [satu["nama"] for satu in hasil["forum"]] == ["Pengumuman", "Diskusi Umum"]
    assert hasil["forum"][0]["pengumuman"] is True and hasil["forum"][1]["deskripsi"] == "Tanya jawab materi."


def test_diskusi_forum(klien):
    hasil = forum.diskusi_forum(klien, FORUM_UMUM)

    assert hasil["jumlah"] == 2
    pertama = hasil["diskusi"][0]
    assert pertama["id"] == 301 and pertama["subjek"] == "Tanya soal CSS"
    assert pertama["pesan"] == "Bagaimana cara flexbox?"
    assert pertama["url"] == f"{SITUS}/mod/forum/discuss.php?d=301"
    assert hasil["diskusi"][1]["lampiran"][0]["nama"] == "kelompok.xlsx"


def test_diskusi_forum_dibaca_per_halaman(klien, situs):
    situs.data["diskusi"][FORUM_UMUM] = [
        {"id": 5000 + nomor, "discussion": 600 + nomor, "subject": f"Topik {nomor}", "message": ""} for nomor in range(150)
    ]

    hasil = forum.diskusi_forum(klien, FORUM_UMUM)

    assert hasil["jumlah"] == 150
    assert [panggilan["page"] for panggilan in situs.panggilan("mod_forum_get_forum_discussions")] == ["0", "1"]


def test_kirim_pengumuman_uji_coba_tidak_mengirim(klien, situs):
    hasil = forum.kirim_pengumuman(klien, KURSUS_WEB, "Kuis minggu depan", "Kuis dimulai pukul 08.00.\n\nMateri: https://contoh.ac.id/a.")

    assert hasil.kirim is False and hasil.terkirim is False
    assert hasil.ringkasan["forum"] == "Pengumuman" and hasil.ringkasan["kursus"] == "Pengembangan Aplikasi Web (Serpong)"
    assert hasil.permintaan["parameter"]["message"] == (
        '<p>Kuis dimulai pukul 08.00.</p><p>Materi: <a href="https://contoh.ac.id/a">https://contoh.ac.id/a</a>.</p>'
    )
    assert hasil.permintaan["isian"]["forumid"] == str(FORUM_PENGUMUMAN)
    assert situs.panggilan("mod_forum_add_discussion") == []


def test_kirim_pengumuman_sungguhan(klien, situs):
    hasil = forum.kirim_pengumuman(klien, KURSUS_WEB, "Kuis", "<b>Penting</b>", kirim=True, bentuk="html")

    assert hasil.terkirim is True and hasil.hasil["discussionid"] == 399
    assert hasil.ringkasan["url"] == f"{SITUS}/mod/forum/discuss.php?d=399"
    assert situs.panggilan("mod_forum_add_discussion") == [{"forumid": "501", "subject": "Kuis", "message": "<b>Penting</b>"}]


def test_pengumuman_ditolak_kalau_tidak_ada_forum_news(klien, situs):
    with pytest.raises(IsianDitolak, match="tidak punya forum pengumuman"):
        forum.kirim_pengumuman(klien, KURSUS_SECTION, "Kuis", "Isi")


def test_pengumuman_ditolak_kalau_tidak_boleh_menulis(klien, situs):
    situs.data["forum"][KURSUS_WEB][0]["cancreatediscussions"] = False

    with pytest.raises(IsianDitolak, match="tidak boleh membuat diskusi"):
        forum.kirim_pengumuman(klien, KURSUS_WEB, "Kuis", "Isi", kirim=True)
    assert situs.panggilan("mod_forum_add_discussion") == []


@pytest.mark.parametrize("subjek, isi", [("", "Isi"), ("Subjek", "   "), ("x" * 256, "Isi")])
def test_pengumuman_isian_tidak_sah_ditolak_sebelum_menghubungi(klien, situs, subjek, isi):
    with pytest.raises(IsianDitolak):
        forum.kirim_pengumuman(klien, KURSUS_WEB, subjek, isi)
    assert situs.permintaan == []


def test_pengumuman_yang_terputus_menjadi_hasil_tidak_pasti(klien, situs):
    situs.jaringan_putus.add("mod_forum_add_discussion")

    with pytest.raises(HasilTidakPasti):
        forum.kirim_pengumuman(klien, KURSUS_WEB, "Kuis", "Isi", kirim=True)


# --- beri nilai ---------------------------------------------------------------


def test_beri_nilai_uji_coba_menampilkan_nilai_lama_dan_baru(klien, situs):
    hasil = tugas.beri_nilai(klien, TUGAS_1, 101, 90, "Bagus.\nRapikan CSS-nya.")

    assert hasil.kirim is False
    assert hasil.ringkasan == {
        "tugas_id": TUGAS_1, "tugas": "Tugas 1: Halaman Statis", "kursus": "Pengembangan Aplikasi Web (Serpong)",
        "user_id": 101, "mahasiswa": "Peter Parker", "status_pengumpulan": "submitted",
        "nilai_lama": 85.0, "nilai_baru": 90.0, "nilai_maks": 100.0, "umpan_balik": "Bagus.\nRapikan CSS-nya.",
    }
    parameter = hasil.permintaan["parameter"]
    assert parameter["attemptnumber"] == -1 and parameter["applytoall"] is False and parameter["addattempt"] is False
    assert parameter["plugindata"]["assignfeedbackcomments_editor"] == {"text": "<p>Bagus.<br>Rapikan CSS-nya.</p>", "format": 1}
    assert situs.panggilan("mod_assign_save_grade") == []


def test_beri_nilai_sungguhan(klien, situs):
    hasil = tugas.beri_nilai(klien, TUGAS_1, 102, 78.5, kirim=True)

    assert hasil.terkirim is True and hasil.hasil is None
    terkirim = situs.panggilan("mod_assign_save_grade")[0]
    assert terkirim == {"assignmentid": "77", "userid": "102", "grade": "78.5", "attemptnumber": "-1",
                        "addattempt": "0", "workflowstate": "", "applytoall": "0"}


def test_beri_nilai_di_atas_maksimum_ditolak(klien, situs):
    with pytest.raises(IsianDitolak, match="melebihi nilai maksimum"):
        tugas.beri_nilai(klien, TUGAS_1, 101, 101, kirim=True)
    assert situs.panggilan("mod_assign_save_grade") == []


@pytest.mark.parametrize("nilai_baru", [-1, "sembilan puluh", float("nan")])
def test_beri_nilai_bukan_angka_atau_negatif_ditolak_sebelum_menghubungi(klien, situs, nilai_baru):
    with pytest.raises(IsianDitolak):
        tugas.beri_nilai(klien, TUGAS_1, 101, nilai_baru)
    assert situs.permintaan == []


def test_beri_nilai_tugas_tanpa_nilai_ditolak(klien):
    with pytest.raises(IsianDitolak, match="tidak memakai nilai"):
        tugas.beri_nilai(klien, TUGAS_REFLEKSI, 101, 10)


def test_beri_nilai_bukan_peserta_ditolak(klien):
    with pytest.raises(IsianDitolak, match="tidak bisa dinilai"):
        tugas.beri_nilai(klien, TUGAS_1, 7, 80)


def test_beri_nilai_peringatkan_umpan_balik_yang_tidak_aktif(klien, situs):
    situs.data["tugas"][KURSUS_WEB][0]["configs"][0]["value"] = "0"

    hasil = tugas.beri_nilai(klien, TUGAS_1, 101, 80, "Catatan")

    assert any("akan diabaikan" in satu for satu in hasil.peringatan)


# --- tenggat ------------------------------------------------------------------


def test_tenggat_mulai_tengah_malam_hari_ini(klien, situs):
    hasil = kalender.tenggat(klien, hari=30, sekarang=detik("2026-09-20 10:30"))

    assert hasil["dari"] == "2026-09-20T00:00+07:00"
    assert [satu["id"] for satu in hasil["kegiatan"]] == [601, 602]
    pertama = hasil["kegiatan"][0]
    assert pertama["tindakan"] == "Nilai" and pertama["jumlah_item"] == 1
    assert pertama["kursus"] == "Pengembangan Aplikasi Web (Serpong)"
    parameter = situs.panggilan("core_calendar_get_action_events_by_timesort")[0]
    assert parameter["timesortfrom"] == str(detik("2026-09-20 00:00")) and parameter["limitnum"] == "50"


def test_tenggat_satu_kursus(klien, situs):
    hasil = kalender.tenggat(klien, hari=30, kursus_id=KURSUS_SECTION, sekarang=detik("2026-09-20 10:30"))

    assert [satu["id"] for satu in hasil["kegiatan"]] == [602]
    assert situs.panggilan("core_calendar_get_action_events_by_course")[0]["courseid"] == str(KURSUS_SECTION)


def test_tenggat_dibaca_per_halaman(klien, situs):
    situs.data["kegiatan"] = [
        {**situs.data["kegiatan"][0], "id": 700 + nomor, "timesort": detik("2026-09-21 08:00") + nomor} for nomor in range(120)
    ]

    hasil = kalender.tenggat(klien, hari=7, sekarang=detik("2026-09-20 10:30"))

    assert hasil["jumlah"] == 120
    assert [p["aftereventid"] for p in situs.panggilan("core_calendar_get_action_events_by_timesort")] == ["0", "749", "799"]


@pytest.mark.parametrize("hari", [0, 400, "seminggu"])
def test_tenggat_hari_tidak_sah_ditolak(klien, hari):
    with pytest.raises(IsianDitolak):
        kalender.tenggat(klien, hari=hari)


# --- unduh berkas --------------------------------------------------------------


def test_unduh_ke_data_unduhan_secara_bawaan(klien, situs):
    hasil = berkas.unduh_berkas(klien, URL_SLIDE)

    tujuan = akar_proyek() / "data" / "unduhan" / "slide-html.pdf"
    assert hasil == {"path": str(tujuan), "nama_berkas": "slide-html.pdf", "ukuran": 23, "jenis": "application/pdf"}
    assert tujuan.read_bytes() == b"%PDF-1.4 slide karangan"
    assert TOKEN_UJI not in json.dumps(hasil)


def test_unduh_ke_direktori_dan_path_relatif(klien):
    hasil = berkas.unduh_berkas(klien, URL_SLIDE, "materi/")

    assert hasil["path"] == str(akar_proyek() / "materi" / "slide-html.pdf")


def test_unduh_tidak_menimpa_kecuali_diminta(klien, tmp_path):
    tujuan = tmp_path / "slide.pdf"
    tujuan.write_bytes(b"lama")

    with pytest.raises(IsianDitolak, match="sudah ada"):
        berkas.unduh_berkas(klien, URL_SLIDE, tujuan)
    assert tujuan.read_bytes() == b"lama"

    berkas.unduh_berkas(klien, URL_SLIDE, tujuan, timpa=True)
    assert tujuan.read_bytes().startswith(b"%PDF")


def test_nama_berkas_dari_server_dibersihkan():
    assert berkas.nama_aman("../../etc/passwd") == "passwd"
    assert berkas.nama_aman("..") == ""
    assert berkas.nama_aman("laporan%20akhir.pdf") == "laporan akhir.pdf"


def test_unduh_yang_terputus_tidak_meninggalkan_berkas(klien, situs, tmp_path):
    situs.berkas_putus = True

    with pytest.raises(Exception):
        berkas.unduh_berkas(klien, URL_SLIDE, tmp_path / "slide.pdf")
    assert not list(tmp_path.glob("*slide*")) and not list(tmp_path.glob(".unduhan-*"))


# --- fungsi generik -------------------------------------------------------------


def test_fungsi_tersedia_disaring_dan_ditandai(klien):
    hasil = fungsi.fungsi_tersedia(klien, "assign")

    nama = {satu["nama"]: satu["baca"] for satu in hasil["fungsi"]}
    assert nama["mod_assign_get_submissions"] is True and nama["mod_assign_list_participants"] is True
    assert nama["mod_assign_save_grade"] is False and nama["mod_assign_view_assign"] is False


@pytest.mark.parametrize("nama, baca", [
    ("core_course_get_contents", True),
    ("core_enrol_search_users", True),
    ("mod_assign_list_participants", True),
    ("mod_assign_view_assign", False),
    ("core_message_mark_message_read", False),
    ("tool_mobile_get_autologin_key", False),
])
def test_jenis_fungsi_ditebak_dari_nama(nama, baca):
    assert fungsi.adalah_fungsi_baca(nama) is baca


def test_panggil_fungsi_baca_langsung_dan_rahasia_disamarkan(klien):
    hasil = fungsi.panggil_fungsi(klien, "core_webservice_get_site_info")

    assert hasil["jenis"] == "baca" and hasil["hasil"]["userprivateaccesskey"] == "***"
    assert KUNCI_PRIBADI_UJI not in json.dumps(hasil)


def test_panggil_fungsi_hasil_panjang_dipotong(klien):
    hasil = fungsi.panggil_fungsi(klien, "core_course_get_contents", {"courseid": KURSUS_SECTION}, maks_karakter=100)

    assert hasil["terpotong"] is True and len(hasil["hasil_json"]) == 100 and hasil["panjang"] > 100


def test_panggil_fungsi_tulis_hanya_pratinjau(klien, situs):
    hasil = fungsi.panggil_fungsi(klien, "mod_assign_view_assign", {"assignid": TUGAS_1})

    assert hasil["jenis"] == "tulis" and hasil["kirim"] is False
    assert hasil["permintaan"]["isian"] == {"assignid": "77"}
    assert situs.panggilan("mod_assign_view_assign") == []


def test_panggil_fungsi_tulis_dengan_kirim(klien, situs):
    hasil = fungsi.panggil_fungsi(klien, "mod_assign_view_assign", {"assignid": TUGAS_1}, kirim=True)

    assert hasil["terkirim"] is True and hasil["hasil"] == {"status": True, "warnings": []}
    assert situs.panggilan("mod_assign_view_assign") == [{"assignid": "77"}]


def test_fungsi_penghasil_kunci_login_ditolak(klien, situs):
    with pytest.raises(IsianDitolak, match="kunci login"):
        fungsi.panggil_fungsi(klien, "tool_mobile_get_autologin_key", {"privatetoken": "x"}, kirim=True)


def test_panggil_fungsi_yang_tidak_tersedia(klien):
    with pytest.raises(FungsiTidakTersedia):
        fungsi.panggil_fungsi(klien, "core_course_create_courses", {}, kirim=True)


def test_parameter_harus_objek(klien):
    with pytest.raises(IsianDitolak, match="objek JSON"):
        fungsi.panggil_fungsi(klien, "core_course_get_contents", [5515])


# --- pesan --------------------------------------------------------------------


def test_kirim_pesan_uji_coba_menyebut_nama_penerima(klien, situs):
    hasil = pesan.kirim_pesan(klien, [101, "102", 101], "Jangan lupa tugas.")

    assert hasil.ringkasan["penerima"] == [{"user_id": 101, "nama": "Peter Parker"}, {"user_id": 102, "nama": "Diana Prince"}]
    assert hasil.permintaan["parameter"]["messages"][0] == {
        "touserid": 101, "text": "<p>Jangan lupa tugas.</p>", "textformat": 1, "clientmsgid": "aswaya-0"}
    assert situs.panggilan("core_message_send_instant_messages") == []


def test_kirim_pesan_penerima_tidak_dikenal_ditolak(klien, situs):
    with pytest.raises(IsianDitolak, match="tidak dikenal"):
        pesan.kirim_pesan(klien, [101, 999], "Halo", kirim=True)
    assert situs.panggilan("core_message_send_instant_messages") == []


def test_kirim_pesan_gagal_sebagian(klien):
    hasil = pesan.kirim_pesan(klien, [101, 104], "Halo", kirim=True)

    assert hasil.berhasil is False
    assert hasil.hasil == [
        {"user_id": 101, "terkirim": True, "msgid": 7000, "galat": None},
        {"user_id": 104, "terkirim": False, "msgid": -1, "galat": "The user is unable to be messaged"},
    ]
    assert "1 dari 2 penerima" in hasil.pesan


@pytest.mark.parametrize("user_ids", [[], [0], ["abc"]])
def test_kirim_pesan_penerima_tidak_sah(klien, user_ids):
    with pytest.raises(IsianDitolak):
        pesan.kirim_pesan(klien, user_ids, "Halo")
