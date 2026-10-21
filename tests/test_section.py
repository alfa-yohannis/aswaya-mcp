"""Uji sesi web (login lewat halaman, cookie, sesskey, AJAX) dan alat section di atas Aswaya tiruan."""

from __future__ import annotations

import json
import stat

import pytest

from aswaya_mcp import konfigurasi, section
from aswaya_mcp.aswaya_client import IsianDitolak, KlienAswaya, LoginDitolak
from aswaya_mcp.sesi_web import LoginWebTerhalang, SesiWeb, baca_form_login, format_dari_halaman, sesskey_dari
from conftest import (
    KURSUS_SECTION,
    KURSUS_WEB,
    LOGINTOKEN_UJI,
    PASSWORD_UJI,
    SESSKEY_UJI,
    SITUS,
    TOKEN_UJI,
    USERNAME_UJI,
)

NAMA_BARU = [f"Session {nomor:02d}" for nomor in range(8, 15)]


def nama_section(situs, kursus_id: int) -> list[str]:
    """Nama section kursus di situs tiruan, urut nomor."""
    return [satu["name"] for satu in sorted(situs.data["section"][kursus_id], key=lambda satu: satu["section"])]


# --- daftar section -------------------------------------------------------------


def test_daftar_section(klien, situs):
    hasil = section.daftar_section(klien, KURSUS_SECTION)

    assert hasil["jumlah"] == 8
    assert hasil["section"][0] == {"id": 8000, "nomor": 0, "nama": "Umum", "visible": True, "jumlah_modul": 0}
    assert hasil["section"][7] == {"id": 8007, "nomor": 7, "nama": "Session 07", "visible": True, "jumlah_modul": 1}
    opsi = situs.panggilan("core_course_get_contents")[0]["options"]
    assert opsi == [{"name": "excludecontents", "value": "1"}]


# --- tambah section: uji coba ------------------------------------------------------


def test_tambah_section_uji_coba_menampilkan_rencana_tanpa_login_web(klien, situs):
    hasil = section.tambah_section(klien, KURSUS_SECTION, NAMA_BARU)

    assert hasil.kirim is False and hasil.terkirim is False
    assert hasil.ringkasan["format"] == "topics"
    assert hasil.ringkasan["section_baru"][0] == {"nomor": 8, "nama": "Session 08"}
    assert hasil.ringkasan["section_baru"][-1] == {"nomor": 14, "nama": "Session 14"}
    assert len(hasil.ringkasan["section_sekarang"]) == 8
    langkah = hasil.permintaan["langkah"]
    assert langkah[0]["url"] == f"{SITUS}/course/changenumsections.php"
    assert langkah[0]["parameter"] == {"courseid": KURSUS_SECTION, "insertsection": 0, "numsections": 7,
                                       "sesskey": "<sesskey dari sesi web>"}
    assert langkah[1]["args"] == {"component": "format_topics", "itemtype": "sectionname",
                                  "itemid": "<id section nomor 8>", "value": "Session 08"}
    assert len(langkah) == 8
    assert situs.jumlah("GET", "/login/index.php") == 0 and situs.jumlah("GET", "/course/changenumsections.php") == 0


def test_uji_coba_mengingatkan_password_untuk_login_web(situs):
    konfigurasi.atur_setelan(ASWAYA_TOKEN=TOKEN_UJI)

    hasil = section.tambah_section(KlienAswaya(), KURSUS_SECTION, ["Session 08"])

    assert any("ASWAYA_PASSWORD" in satu for satu in hasil.peringatan)


def test_nama_yang_sudah_terpakai_ditolak_kecuali_dipaksa(klien, situs):
    with pytest.raises(IsianDitolak, match="'session 07' \\(sudah ada sebagai section 7\\)"):
        section.tambah_section(klien, KURSUS_SECTION, ["session  07", "Session 08"])

    hasil = section.tambah_section(klien, KURSUS_SECTION, ["Session 07"], paksa=True)
    assert any("paksa=True" in satu for satu in hasil.peringatan)


def test_nama_ganda_di_daftar_ditolak(klien):
    with pytest.raises(IsianDitolak, match="lebih dari sekali"):
        section.tambah_section(klien, KURSUS_SECTION, ["Session 08", "Session 08"])


@pytest.mark.parametrize("nama", [[], [""], ["   "], ["x" * 256], [8]])
def test_nama_tidak_sah_ditolak_sebelum_menghubungi(klien, situs, nama):
    with pytest.raises(IsianDitolak):
        section.tambah_section(klien, KURSUS_SECTION, nama)
    assert situs.permintaan == []


def test_peringatan_section_kosong_di_akhir(klien, situs):
    situs.data["section"][KURSUS_SECTION].append({"id": 8008, "section": 8, "name": "Topic 8", "visible": 1, "modules": []})

    hasil = section.tambah_section(klien, KURSUS_SECTION, ["Session 08"])

    assert hasil.ringkasan["section_baru"] == [{"nomor": 9, "nama": "Session 08"}]
    assert any("8 ('Topic 8', id 8008)" in satu and "ubah_nama_section" in satu for satu in hasil.peringatan)


def test_tanpa_section_kosong_tidak_ada_peringatan(klien):
    hasil = section.tambah_section(klien, KURSUS_SECTION, ["Session 08"])

    assert not any("section kosong" in satu for satu in hasil.peringatan)


def test_peringatan_batas_section(klien, situs):
    hasil = section.tambah_section(klien, KURSUS_SECTION, [f"Minggu {nomor}" for nomor in range(50)])

    assert any("batas bawaan Moodle 52" in satu for satu in hasil.peringatan)


# --- tambah section: kirim ----------------------------------------------------------


def test_tambah_section_sungguhan(klien, situs, dir_cache):
    hasil = section.tambah_section(klien, KURSUS_SECTION, NAMA_BARU, kirim=True)

    assert hasil.terkirim is True and hasil.berhasil is True
    assert nama_section(situs, KURSUS_SECTION)[8:] == NAMA_BARU
    assert [entri["nomor"] for entri in hasil.hasil["section_baru"]] == list(range(8, 15))
    assert all(entri["sesuai"] and entri["galat"] is None for entri in hasil.hasil["section_baru"])
    assert hasil.hasil["belum_ditambahkan"] == []

    login = [satu for satu in situs.permintaan if satu["path"] == "/login/index.php" and satu["metode"] == "POST"]
    assert len(login) == 1
    assert dict(login[0]["isian"]) == {"anchor": "", "logintoken": LOGINTOKEN_UJI, "username": USERNAME_UJI, "password": PASSWORD_UJI}
    tambah = [satu for satu in situs.permintaan if satu["path"] == "/course/changenumsections.php"]
    assert len(tambah) == 1
    assert tambah[0]["query"] == {"courseid": str(KURSUS_SECTION), "insertsection": "0", "numsections": "7", "sesskey": SESSKEY_UJI}
    ajax = [satu for satu in situs.permintaan if satu["path"] == "/lib/ajax/service.php"]
    assert len(ajax) == 7
    assert ajax[0]["query"] == {"sesskey": SESSKEY_UJI, "info": "core_update_inplace_editable"}
    assert ajax[0]["json"] == [{"index": 0, "methodname": "core_update_inplace_editable",
                                "args": {"component": "format_topics", "itemtype": "sectionname", "itemid": 8100, "value": "Session 08"}}]


def test_hasil_tambah_section_tidak_memuat_sesskey_maupun_password(klien):
    hasil = section.tambah_section(klien, KURSUS_SECTION, NAMA_BARU, kirim=True)

    teks = json.dumps(hasil.sebagai_dict())
    assert SESSKEY_UJI not in teks and PASSWORD_UJI not in teks


def test_cookie_sesi_disimpan_0600_tanpa_password(klien, dir_cache):
    section.tambah_section(klien, KURSUS_SECTION, ["Session 08"], kirim=True)

    berkas = list(dir_cache.glob("sesi-*.json"))
    assert len(berkas) == 1
    assert stat.S_IMODE(berkas[0].stat().st_mode) == 0o600
    isi = berkas[0].read_text()
    assert "MoodleSession" in isi and PASSWORD_UJI not in isi and SESSKEY_UJI not in isi


def test_sesi_dari_cache_dipakai_tanpa_login_ulang(klien, situs):
    section.tambah_section(klien, KURSUS_SECTION, ["Session 08"], kirim=True)
    situs.cookies.clear()  # proses baru: cookie di memori hilang, sesi di server masih hidup

    section.tambah_section(KlienAswaya(), KURSUS_SECTION, ["Session 09"], kirim=True)

    assert situs.jumlah("POST", "/login/index.php") == 1
    assert nama_section(situs, KURSUS_SECTION)[-2:] == ["Session 08", "Session 09"]


def test_sesi_yang_habis_dipulihkan_dengan_login_sekali(klien, situs):
    sesi = SesiWeb(klien)
    section.tambah_section(klien, KURSUS_SECTION, ["Session 08"], kirim=True, sesi=sesi)
    situs.sesi_web_aktif = None  # sesi kedaluwarsa di server

    hasil = section.tambah_section(klien, KURSUS_SECTION, ["Session 09"], kirim=True, sesi=sesi)

    assert hasil.berhasil is True
    assert situs.jumlah("POST", "/login/index.php") == 2


def test_sesskey_yang_ditolak_ajax_dipulihkan_sekali(klien, situs):
    situs.ajax_galat_berikutnya = ["invalidsesskey"]

    hasil = section.tambah_section(klien, KURSUS_SECTION, ["Session 08"], kirim=True)

    assert hasil.berhasil is True
    assert situs.jumlah("POST", "/lib/ajax/service.php") == 2


def test_batas_section_terlampaui_tidak_menambah_apa_pun(klien, situs):
    situs.maks_section = 10

    hasil = section.tambah_section(klien, KURSUS_SECTION, NAMA_BARU, kirim=True)

    assert hasil.terkirim is True and hasil.berhasil is False
    assert "Tidak ada section yang bertambah" in hasil.pesan
    assert hasil.hasil["belum_ditambahkan"] == NAMA_BARU
    assert situs.jumlah("POST", "/lib/ajax/service.php") == 0


def test_format_dibaca_dari_halaman_kalau_web_service_tidak_tersedia(klien, situs):
    situs.fungsi.remove("core_course_get_courses_by_field")

    rencana = section.tambah_section(klien, KURSUS_SECTION, ["Session 08"])
    hasil = section.tambah_section(klien, KURSUS_SECTION, ["Session 08"], kirim=True)

    assert any("Format kursus tidak terbaca" in satu for satu in rencana.peringatan)
    assert hasil.berhasil is True and hasil.ringkasan["format"] == "topics"


def test_tanpa_password_kirim_ditolak_sebelum_menambah(situs):
    konfigurasi.atur_setelan(ASWAYA_TOKEN=TOKEN_UJI)

    with pytest.raises(konfigurasi.KonfigurasiError, match="ASWAYA_USERNAME, ASWAYA_PASSWORD"):
        section.tambah_section(KlienAswaya(), KURSUS_SECTION, ["Session 08"], kirim=True)
    assert situs.jumlah("GET", "/course/changenumsections.php") == 0


# --- login web --------------------------------------------------------------------


def test_captcha_menghentikan_login_tanpa_mengirim_password(klien, situs):
    situs.captcha = True

    with pytest.raises(LoginWebTerhalang, match="captcha"):
        section.tambah_section(klien, KURSUS_SECTION, ["Session 08"], kirim=True)
    assert situs.jumlah("POST", "/login/index.php") == 0
    assert situs.jumlah("GET", "/course/changenumsections.php") == 0


def test_password_web_salah_ditolak_sekali_tanpa_membocorkannya(situs):
    konfigurasi.atur_setelan(ASWAYA_USERNAME=USERNAME_UJI, ASWAYA_PASSWORD=PASSWORD_UJI, ASWAYA_TOKEN=TOKEN_UJI)
    situs.password_benar = "sandi-lain"

    with pytest.raises(LoginDitolak) as galat:
        section.tambah_section(KlienAswaya(), KURSUS_SECTION, ["Session 08"], kirim=True)
    assert "Invalid login" in str(galat.value) and PASSWORD_UJI not in str(galat.value)
    assert situs.jumlah("POST", "/login/index.php") == 1


def test_mfa_menghentikan_login(klien, situs):
    situs.hambatan_login = "/admin/tool/mfa/auth.php"

    with pytest.raises(LoginWebTerhalang, match="multi-faktor"):
        section.tambah_section(klien, KURSUS_SECTION, ["Session 08"], kirim=True)
    assert situs.jumlah("GET", "/course/changenumsections.php") == 0


def test_sesi_web_tidak_mengikuti_pengalihan_ke_host_lain(klien, situs):
    sesi = SesiWeb(klien)

    with pytest.raises(Exception, match="di luar Aswaya"):
        sesi.minta("GET", "https://pencuri.contoh.id/login/index.php")
    assert situs.permintaan == []


def test_repr_sesi_web_tanpa_rahasia(klien):
    sesi = SesiWeb(klien)
    section.tambah_section(klien, KURSUS_SECTION, ["Session 08"], kirim=True, sesi=sesi)

    assert SESSKEY_UJI not in repr(sesi) and PASSWORD_UJI not in repr(sesi)


def test_pembaca_halaman():
    html = (
        '<html><head><script>M.cfg = {"wwwroot":"x","sesskey":"Abc123","x":1};</script></head>'
        '<body class="format-weeks course-12 pagelayout-course">'
        '<form id="guestlogin" method="post"><input name="username" value="guest"><input type="password" name="password"></form>'
        '<form id="login" method="post" action="/login/index.php"><input type="hidden" name="logintoken" value="t1">'
        '<input name="username"><input type="password" name="password">'
        '<input type="checkbox" name="rememberusername"></form></body></html>'
    )

    assert sesskey_dari(html) == "Abc123"
    assert format_dari_halaman(html) == "weeks"
    form = baca_form_login(html, f"{SITUS}/login/index.php")
    assert form.action == f"{SITUS}/login/index.php" and form.isian_bawaan == {"logintoken": "t1"}


# --- ganti nama ------------------------------------------------------------------


def test_ubah_nama_section_uji_coba(klien, situs):
    hasil = section.ubah_nama_section(klien, KURSUS_SECTION, 8003, "Session 03: OOP Dasar")

    assert hasil.ringkasan["nama_lama"] == "Session 03" and hasil.ringkasan["nama_baru"] == "Session 03: OOP Dasar"
    assert hasil.permintaan["langkah"][0]["args"] == {
        "component": "format_topics", "itemtype": "sectionname", "itemid": 8003, "value": "Session 03: OOP Dasar"}
    assert situs.jumlah("POST", "/lib/ajax/service.php") == 0


def test_ubah_nama_section_sungguhan(klien, situs):
    hasil = section.ubah_nama_section(klien, KURSUS_SECTION, 8003, "Session 03: OOP Dasar", kirim=True)

    assert hasil.berhasil is True and hasil.hasil["sesuai"] is True
    assert hasil.hasil["tampil"] == "Session 03: OOP Dasar"
    assert nama_section(situs, KURSUS_SECTION)[3] == "Session 03: OOP Dasar"


def test_section_kursus_lain_ditolak(klien, situs):
    with pytest.raises(IsianDitolak, match="bukan section kursus"):
        section.ubah_nama_section(klien, KURSUS_SECTION, 9001, "Nama", kirim=True)
    assert situs.jumlah("POST", "/lib/ajax/service.php") == 0


def test_nama_yang_sama_ditolak(klien):
    with pytest.raises(IsianDitolak, match="tidak ada yang perlu diubah"):
        section.ubah_nama_section(klien, KURSUS_SECTION, 8003, "Session 03")


def test_component_mengikuti_format_kursus(klien, situs):
    situs.data["kursus"][KURSUS_WEB]["format"] = "weeks"

    hasil = section.ubah_nama_section(klien, KURSUS_WEB, 9001, "Minggu 1", kirim=True)

    assert hasil.berhasil is True
    ajax = [satu for satu in situs.permintaan if satu["path"] == "/lib/ajax/service.php"]
    assert ajax[-1]["json"][0]["args"]["component"] == "format_weeks"
