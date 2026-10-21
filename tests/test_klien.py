"""Uji klien web service: perataan parameter, token, login ulang, galat Moodle, berkas, dan unggahan."""

from __future__ import annotations

import json

import pytest

from aswaya_mcp import konfigurasi
from aswaya_mcp.aswaya_client import (
    AlamatDitolak,
    AswayaError,
    FungsiTidakTersedia,
    HasilTidakPasti,
    IsianDitolak,
    KlienAswaya,
    LoginDitolak,
    MoodleError,
    periksa_id,
    ratakan,
)
from conftest import (
    KUNCI_PRIBADI_UJI,
    PASSWORD_UJI,
    PRIVATETOKEN_UJI,
    SITUS,
    TOKEN_LAIN,
    TOKEN_UJI,
    USERNAME_UJI,
    JawabanTiruan,
)


# --- perataan parameter ------------------------------------------------------


def test_ratakan_nilai_tunggal_bool_dan_none():
    assert ratakan({"courseid": 5515, "returnusercount": False, "lewati": None, "nama": "Kelas A"}) == [
        ("courseid", "5515"),
        ("returnusercount", "0"),
        ("nama", "Kelas A"),
    ]


def test_ratakan_daftar_dan_struktur_bersarang():
    parameter = {
        "courseids": [5515, 5026],
        "options": [{"name": "userfields", "value": "id,fullname"}, {"name": "onlyactive", "value": True}],
        "plugindata": {"assignfeedbackcomments_editor": {"text": "<p>Bagus</p>", "format": 1}},
    }

    assert ratakan(parameter) == [
        ("courseids[0]", "5515"),
        ("courseids[1]", "5026"),
        ("options[0][name]", "userfields"),
        ("options[0][value]", "id,fullname"),
        ("options[1][name]", "onlyactive"),
        ("options[1][value]", "1"),
        ("plugindata[assignfeedbackcomments_editor][text]", "<p>Bagus</p>"),
        ("plugindata[assignfeedbackcomments_editor][format]", "1"),
    ]


def test_ratakan_kosong():
    assert ratakan(None) == [] and ratakan({}) == []


@pytest.mark.parametrize("nilai", [0, -3, "abc", "05", 2.5, True, None])
def test_id_yang_tidak_sah_ditolak(nilai):
    with pytest.raises(IsianDitolak):
        periksa_id(nilai, "kursus_id")


# --- token ------------------------------------------------------------------


def test_membuat_klien_belum_menghubungi_situs(situs, kredensial_di_setelan):
    klien = KlienAswaya()

    assert situs.permintaan == []
    assert klien.token == ""


def test_login_meminta_token_layanan_mobile(situs, kredensial_di_setelan):
    klien = KlienAswaya().login()

    kiriman = [satu for satu in situs.permintaan if satu["path"] == "/login/token.php"]
    assert len(kiriman) == 1
    assert dict(kiriman[0]["isian"]) == {"username": USERNAME_UJI, "password": PASSWORD_UJI, "service": "moodle_mobile_app"}
    assert klien.token == TOKEN_UJI and klien.sumber_token == "login"


def test_privatetoken_tidak_disimpan_di_mana_pun(situs, kredensial_di_setelan, dir_cache):
    klien = KlienAswaya().login()

    assert PRIVATETOKEN_UJI not in json.dumps(vars(klien), default=str)
    assert PRIVATETOKEN_UJI not in "".join(berkas.read_text() for berkas in dir_cache.glob("*.json"))


def test_token_login_disimpan_ke_cache_dan_dipakai_ulang(situs, kredensial_di_setelan, dir_cache):
    KlienAswaya().info_situs()
    klien_kedua = KlienAswaya()
    klien_kedua.info_situs()

    assert situs.jumlah("POST", "/login/token.php") == 1
    assert klien_kedua.sumber_token == "cache"
    berkas = list(dir_cache.glob("token-*.json"))
    assert len(berkas) == 1 and PASSWORD_UJI not in berkas[0].read_text()


def test_cache_bisa_dimatikan(situs, kredensial_di_setelan, dir_cache):
    konfigurasi.atur_setelan(ASWAYA_USERNAME=USERNAME_UJI, ASWAYA_PASSWORD=PASSWORD_UJI, simpan_cache="tidak")
    KlienAswaya().info_situs()

    assert not dir_cache.exists() or not list(dir_cache.glob("*.json"))


def test_token_setelan_dipakai_lebih_dulu_walau_ada_password(situs):
    konfigurasi.atur_setelan(ASWAYA_USERNAME=USERNAME_UJI, ASWAYA_PASSWORD=PASSWORD_UJI, ASWAYA_TOKEN=TOKEN_UJI)
    klien = KlienAswaya()
    klien.info_situs()

    assert situs.jumlah("POST", "/login/token.php") == 0
    assert klien.sumber_token == "setelan"


def test_token_setelan_yang_ditolak_dipulihkan_dengan_login_sekali(situs):
    konfigurasi.atur_setelan(ASWAYA_USERNAME=USERNAME_UJI, ASWAYA_PASSWORD=PASSWORD_UJI, ASWAYA_TOKEN="token-basi")
    situs.token_berikutnya = TOKEN_LAIN
    klien = KlienAswaya()

    info = klien.info_situs()

    assert info["userid"] == 7
    assert situs.jumlah("POST", "/login/token.php") == 1
    assert klien.token == TOKEN_LAIN and klien.sumber_token == "login"


def test_token_ditolak_tanpa_password_dilaporkan_jelas(situs):
    konfigurasi.atur_setelan(ASWAYA_TOKEN="token-basi")

    with pytest.raises(LoginDitolak, match="ASWAYA_TOKEN atau isi ASWAYA_PASSWORD"):
        KlienAswaya().info_situs()
    assert situs.jumlah("POST", "/login/token.php") == 0


def test_token_cache_yang_ditolak_dihapus_lalu_diganti(situs, kredensial_di_setelan, dir_cache):
    konfigurasi.simpan_token(SITUS, USERNAME_UJI, "token-cache-basi")
    situs.token_berikutnya = TOKEN_LAIN
    klien = KlienAswaya()

    klien.info_situs()

    assert klien.token == TOKEN_LAIN
    assert konfigurasi.baca_token_tersimpan(SITUS, USERNAME_UJI) == TOKEN_LAIN


def test_token_yang_dicabut_di_tengah_jalan_dipulihkan(situs, kredensial_di_setelan):
    klien = KlienAswaya()
    klien.info_situs()
    situs.token_berlaku.clear()  # token dicabut admin atau kedaluwarsa
    situs.token_berikutnya = TOKEN_LAIN

    hasil = klien.panggil("core_course_get_contents", {"courseid": 5515})

    assert hasil[0]["name"] == "Umum"
    assert situs.jumlah("POST", "/login/token.php") == 2


def test_login_ulang_yang_juga_ditolak_tidak_diulang_lagi(situs, kredensial_di_setelan):
    klien = KlienAswaya()
    klien.info_situs()
    situs.token_berlaku.clear()
    situs.token_berikutnya = TOKEN_LAIN
    situs.token_login_berlaku = False

    with pytest.raises(LoginDitolak, match="juga ditolak"):
        klien.panggil("core_course_get_contents", {"courseid": 5515})
    assert situs.jumlah("POST", "/login/token.php") == 2


def test_password_salah_ditolak_tanpa_membocorkannya(situs):
    konfigurasi.atur_setelan(ASWAYA_USERNAME=USERNAME_UJI, ASWAYA_PASSWORD="sandi-yang-salah")

    with pytest.raises(LoginDitolak) as galat:
        KlienAswaya().info_situs()
    assert "Invalid login" in str(galat.value)
    assert "sandi-yang-salah" not in str(galat.value)
    assert situs.jumlah("POST", "/login/token.php") == 1


def test_pesan_situs_disamarkan_dari_kredensial(situs):
    konfigurasi.atur_setelan(ASWAYA_USERNAME=USERNAME_UJI, ASWAYA_PASSWORD="sandi-yang-salah")
    situs.pesan_gagal_login = f"Akun {USERNAME_UJI} dengan sandi sandi-yang-salah tidak cocok"

    with pytest.raises(LoginDitolak) as galat:
        KlienAswaya().login()
    assert USERNAME_UJI not in str(galat.value) and "sandi-yang-salah" not in str(galat.value)
    assert "***" in str(galat.value)


def test_kredensial_kosong_dilaporkan_sebelum_menghubungi_situs(situs):
    with pytest.raises(konfigurasi.KonfigurasiError, match="ASWAYA_USERNAME, ASWAYA_PASSWORD"):
        KlienAswaya().info_situs()
    assert situs.permintaan == []


def test_kredensial_argumen_tidak_memakai_token_setelan(situs):
    konfigurasi.atur_setelan(ASWAYA_TOKEN="token-milik-setelan")
    klien = KlienAswaya(USERNAME_UJI, PASSWORD_UJI)

    klien.info_situs()

    assert klien.sumber_token == "login"
    assert all("token-milik-setelan" not in json.dumps(satu["isian"]) for satu in situs.permintaan)


def test_token_dikirim_di_badan_bukan_di_url(klien, situs):
    klien.info_situs()

    for satu in situs.permintaan:
        assert TOKEN_UJI not in satu["url"]
    rest = [satu for satu in situs.permintaan if satu["path"] == "/webservice/rest/server.php"]
    assert ("wstoken", TOKEN_UJI) in rest[0]["isian"]
    assert ("moodlewsrestformat", "json") in rest[0]["isian"]


def test_repr_tanpa_rahasia(klien):
    klien.info_situs()

    assert TOKEN_UJI not in repr(klien) and PASSWORD_UJI not in repr(klien)


# --- fungsi dan galat ---------------------------------------------------------


def test_info_situs_membuang_kunci_akses_pribadi(klien):
    info = klien.info_situs()

    assert "userprivateaccesskey" not in info
    assert KUNCI_PRIBADI_UJI not in json.dumps(info)
    assert info["release"].startswith("4.1")


def test_info_situs_diingat(klien, situs):
    klien.info_situs()
    klien.info_situs()

    assert situs.jumlah("POST", "/webservice/rest/server.php", "core_webservice_get_site_info") == 1


def test_fungsi_yang_tidak_tersedia_ditolak_dengan_saran(klien, situs):
    with pytest.raises(FungsiTidakTersedia) as galat:
        klien.panggil("mod_assign_get_submission")
    assert "mod_assign_get_submissions" in str(galat.value)
    assert situs.jumlah("POST", "/webservice/rest/server.php", "mod_assign_get_submission") == 0


def test_nama_fungsi_tidak_sah_ditolak(klien):
    with pytest.raises(IsianDitolak):
        klien.panggil("core_course_get_contents&wstoken=lain")


def test_exception_moodle_menjadi_moodleerror(klien, situs):
    situs.galat_berikutnya["core_course_get_contents"] = {
        "exception": "moodle_exception", "errorcode": "nopermissions",
        "message": f"Sorry, but you do not currently have permissions (token {TOKEN_UJI})",
    }

    with pytest.raises(MoodleError) as galat:
        klien.panggil("core_course_get_contents", {"courseid": 5515})
    assert galat.value.kode == "nopermissions"
    assert TOKEN_UJI not in str(galat.value)


def test_jawaban_bukan_json_dilaporkan(klien, situs, monkeypatch):
    klien.info_situs()
    monkeypatch.setattr(situs, "server_php", lambda alamat, isian, catatan: JawabanTiruan(alamat, 502, teks="<h1>Bad gateway</h1>"))

    with pytest.raises(AswayaError, match="HTTP 502"):
        klien.panggil("core_course_get_contents", {"courseid": 5515})


def test_kegagalan_jaringan_saat_menulis_menjadi_hasil_tidak_pasti(klien, situs):
    klien.info_situs()
    situs.jaringan_putus.add("mod_forum_add_discussion")

    with pytest.raises(HasilTidakPasti, match="sebelum mengirim ulang"):
        klien.panggil("mod_forum_add_discussion", {"forumid": 501, "subject": "x", "message": "y"}, tulis=True)
    assert situs.jumlah("POST", "/webservice/rest/server.php", "mod_forum_add_discussion") == 1


def test_kegagalan_jaringan_saat_membaca_tetap_galat_biasa(klien, situs):
    klien.info_situs()
    situs.jaringan_putus.add("core_course_get_contents")

    with pytest.raises(AswayaError) as galat:
        klien.panggil("core_course_get_contents", {"courseid": 5515})
    assert not isinstance(galat.value, HasilTidakPasti)


def test_konfigurasi_publik_tanpa_login(situs):
    data = KlienAswaya().konfigurasi_publik()

    assert data["typeoflogin"] == 1
    assert situs.jumlah("POST", "/login/token.php") == 0
    assert situs.permintaan[0]["json"] == [{"index": 0, "methodname": "tool_mobile_get_public_config", "args": {}}]


# --- berkas -------------------------------------------------------------------


def test_alamat_berkas_di_host_lain_ditolak_tanpa_permintaan(klien, situs):
    with pytest.raises(AlamatDitolak, match="token hanya dikirim ke host Aswaya"):
        klien.buka_berkas("https://pencuri.contoh.id/webservice/pluginfile.php/1/a.pdf")
    assert situs.permintaan == []


def test_alamat_berkas_selain_pluginfile_ditolak(klien):
    with pytest.raises(AlamatDitolak, match="bukan alamat berkas"):
        klien.alamat_berkas(f"{SITUS}/course/view.php?id=5515")


def test_pluginfile_biasa_diubah_ke_versi_webservice_dan_token_lama_dibuang(klien):
    alamat = klien.alamat_berkas(f"{SITUS}/pluginfile.php/88/mod_resource/content/1/slide-html.pdf?token=lama&forcedownload=1")

    assert alamat == f"{SITUS}/webservice/pluginfile.php/88/mod_resource/content/1/slide-html.pdf?forcedownload=1"


def test_buka_berkas_menambahkan_token_sendiri(klien, situs):
    jawaban = klien.buka_berkas(f"{SITUS}/webservice/pluginfile.php/88/mod_resource/content/1/slide-html.pdf")

    assert jawaban.content.startswith(b"%PDF")
    unduhan = [satu for satu in situs.permintaan if satu["path"].startswith("/webservice/pluginfile.php/")]
    assert unduhan[0]["query"]["token"] == TOKEN_UJI


def test_pengalihan_berkas_ke_host_lain_tidak_diikuti(klien, situs):
    path = "/webservice/pluginfile.php/88/mod_resource/content/1/slide-html.pdf"
    situs.pengalihan_berkas[path] = "https://drive.contoh.id/berkas/123"

    with pytest.raises(AlamatDitolak, match="tidak diikuti supaya token tidak ikut terkirim"):
        klien.buka_berkas(SITUS + path)


def test_pengalihan_berkas_di_host_yang_sama_diikuti(klien, situs):
    path = "/webservice/pluginfile.php/99/lama/slide-lama.pdf"
    situs.pengalihan_berkas[path] = f"{SITUS}/webservice/pluginfile.php/88/mod_resource/content/1/slide-html.pdf"

    assert klien.buka_berkas(SITUS + path).content.startswith(b"%PDF")


def test_token_ditolak_saat_unduh_dipulihkan_sekali(klien, situs):
    klien.info_situs()
    situs.token_berlaku.clear()
    situs.token_berikutnya = TOKEN_LAIN

    jawaban = klien.buka_berkas(f"{SITUS}/webservice/pluginfile.php/88/mod_resource/content/1/slide-html.pdf")

    assert jawaban.content.startswith(b"%PDF")
    assert situs.jumlah("POST", "/login/token.php") == 2


def test_galat_jaringan_unduhan_tidak_membocorkan_token(klien, situs):
    klien.info_situs()
    situs.berkas_putus = True

    with pytest.raises(AswayaError) as galat:
        klien.buka_berkas(f"{SITUS}/webservice/pluginfile.php/88/mod_resource/content/1/slide-html.pdf")
    assert TOKEN_UJI not in str(galat.value)


def test_unggah_berkas_ke_draft_area(klien, situs, tmp_path):
    berkas = tmp_path / "materi.pdf"
    berkas.write_bytes(b"%PDF karangan")

    hasil = klien.unggah_berkas(berkas)

    assert hasil["itemid"] == 123456 and hasil["filename"] == "materi.pdf"
    kiriman = [satu for satu in situs.permintaan if satu["path"] == "/webservice/upload.php"][0]
    assert dict(kiriman["isian"])["filearea"] == "draft" and dict(kiriman["isian"])["itemid"] == "0"


def test_unggah_berkas_yang_tidak_ada_ditolak(klien, situs, tmp_path):
    with pytest.raises(IsianDitolak):
        klien.unggah_berkas(tmp_path / "tidak-ada.pdf")
    assert situs.permintaan == []
