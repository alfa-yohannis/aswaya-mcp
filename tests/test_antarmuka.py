"""Uji ketiga antarmuka (CLI, MCP, REST API) di atas Aswaya tiruan.

Yang diperiksa terutama hal yang tidak boleh bocor atau terkirim diam-diam:
kredensial dan token tidak tercetak, tool MCP tidak menerima kata sandi lewat
parameter, semua alat tulis bawaannya uji coba, dan galat dilaporkan rapi.
"""

from __future__ import annotations

import asyncio
import io
import json

import pytest

from aswaya_mcp import cli, kalender
from conftest import (
    FORUM_UMUM,
    KUNCI_PRIBADI_UJI,
    KURSUS_SECTION,
    KURSUS_WEB,
    PASSWORD_UJI,
    SESSKEY_UJI,
    SITUS,
    TOKEN_UJI,
    TUGAS_1,
    USERNAME_UJI,
    detik,
)

URL_SLIDE = f"{SITUS}/webservice/pluginfile.php/88/mod_resource/content/1/slide-html.pdf"
TOOL_BACA = {
    "cek_login", "daftar_kursus", "isi_kursus", "peserta_kursus", "daftar_tugas", "pengumpulan_tugas",
    "nilai_kursus", "daftar_forum", "diskusi_forum", "tenggat", "unduh_berkas", "daftar_section", "fungsi_tersedia",
}
TOOL_TULIS = {"panggil_fungsi", "kirim_pengumuman", "beri_nilai", "kirim_pesan", "tambah_section", "ubah_nama_section"}


# --- CLI -------------------------------------------------------------------


def test_cli_cek_login_tanpa_mencetak_rahasia(situs, kredensial_di_setelan, capsys, monkeypatch):
    monkeypatch.setattr("sys.argv", ["aswaya-cek-login"])

    assert cli.jalankan_cek_login() == 0
    keluaran = capsys.readouterr()
    assert "Login Aswaya OK: Aswaya Contoh" in keluaran.out
    assert "4.1.9" in keluaran.out and "userid 7" in keluaran.out
    for rahasia in (PASSWORD_UJI, TOKEN_UJI, KUNCI_PRIBADI_UJI):
        assert rahasia not in keluaran.out + keluaran.err


def test_cli_cek_login_tanpa_kredensial_keluar_dengan_kode_1(situs, capsys, monkeypatch):
    monkeypatch.setattr("sys.argv", ["aswaya-cek-login"])

    assert cli.jalankan_cek_login() == 1
    assert "Gagal: Kredensial belum ada" in capsys.readouterr().err


def test_cli_cek_login_gagal_menampilkan_diagnosis(situs, capsys, monkeypatch):
    from aswaya_mcp import konfigurasi

    konfigurasi.atur_setelan(ASWAYA_USERNAME=USERNAME_UJI, ASWAYA_PASSWORD="sandi-yang-salah")
    monkeypatch.setattr("sys.argv", ["aswaya-cek-login"])

    assert cli.jalankan_cek_login() == 1
    galat = capsys.readouterr().err
    assert "Situs terjangkau" in galat and "layanan_mobile_aktif" in galat
    assert "sandi-yang-salah" not in galat


def test_cli_publik(situs, capsys):
    assert cli.main_publik([]) == 0
    assert "layanan_mobile_aktif" in capsys.readouterr().out


def test_cli_kursus_teks_dan_json(situs, kredensial_di_setelan, capsys):
    assert cli.main_kursus(["--cari", "web"]) == 0
    assert "5515  Pengembangan Aplikasi Web (Serpong)  (IF140303-SRP)" in capsys.readouterr().out

    assert cli.main_kursus(["--json"]) == 0
    assert json.loads(capsys.readouterr().out)["jumlah"] == 3


def test_cli_isi(situs, kredensial_di_setelan, capsys):
    assert cli.main_isi([str(KURSUS_WEB)]) == 0
    keluaran = capsys.readouterr().out
    assert "[1] Pertemuan 1" in keluaran and "slide-html.pdf (240.0 KB)" in keluaran


def test_cli_peserta_nim_hanya_dengan_lengkap(situs, kredensial_di_setelan, capsys):
    assert cli.main_peserta([str(KURSUS_WEB), "--peran", "student"]) == 0
    assert "2026100001" not in capsys.readouterr().out

    assert cli.main_peserta([str(KURSUS_WEB), "--lengkap"]) == 0
    keluaran = capsys.readouterr().out
    assert "2026100001" in keluaran and "peter.parker@contoh.ac.id" in keluaran


def test_cli_tugas_dan_pengumpulan(situs, kredensial_di_setelan, capsys):
    assert cli.main_tugas([str(KURSUS_WEB)]) == 0
    assert "Tugas 1: Halaman Statis" in capsys.readouterr().out

    assert cli.main_pengumpulan([str(TUGAS_1)]) == 0
    keluaran = capsys.readouterr().out
    assert "4 peserta, 1 dikumpulkan, 1 draf, 2 belum" in keluaran
    assert "Peter Parker | sudah dikumpulkan" in keluaran and "nilai 85" in keluaran


def test_cli_nilai_csv(situs, kredensial_di_setelan, capsys):
    assert cli.main_nilai([str(KURSUS_WEB), "--csv"]) == 0
    baris = capsys.readouterr().out.strip().splitlines()
    assert baris[0] == "user_id,nama,Tugas 1: Halaman Statis (#401),Kuis HTML (#402),Total kursus (#400)"
    assert "102,Diana Prince,,7.5,7.5" in baris


def test_cli_forum_dan_diskusi(situs, kredensial_di_setelan, capsys):
    assert cli.main_forum([str(KURSUS_WEB)]) == 0
    assert "[pengumuman]" in capsys.readouterr().out

    assert cli.main_diskusi([str(FORUM_UMUM)]) == 0
    assert "Tanya soal CSS" in capsys.readouterr().out


def test_cli_tenggat(situs, kredensial_di_setelan, capsys, monkeypatch):
    monkeypatch.setattr(kalender.time, "time", lambda: detik("2026-09-20 10:30"))

    assert cli.main_tenggat(["--hari", "30"]) == 0
    assert "Tugas 1: Halaman Statis perlu dinilai" in capsys.readouterr().out


def test_cli_unduh(situs, kredensial_di_setelan, capsys, tmp_path):
    assert cli.main_unduh([URL_SLIDE, "--tujuan", str(tmp_path) + "/"]) == 0
    assert f"Tersimpan: {tmp_path}/slide-html.pdf" in capsys.readouterr().out


def test_cli_fungsi(situs, kredensial_di_setelan, capsys):
    assert cli.main_fungsi(["forum"]) == 0
    keluaran = capsys.readouterr().out
    assert "mod_forum_add_discussion  (tulis: perlu --kirim)" in keluaran


def test_cli_panggil_json_dan_parameter_tidak_sah(situs, kredensial_di_setelan, capsys, monkeypatch):
    assert cli.main_panggil(["core_course_get_contents", "--parameter", '{"courseid": 5026}']) == 0
    assert json.loads(capsys.readouterr().out)["jenis"] == "baca"

    monkeypatch.setattr("sys.argv", ["aswaya-panggil", "core_course_get_contents", "--parameter", "{courseid: 1}"])
    assert cli.jalankan_panggil() == 1
    assert "bukan JSON yang sah" in capsys.readouterr().err


def test_cli_umumkan_tanpa_kirim_hanya_uji_coba(situs, kredensial_di_setelan, capsys, monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO("Kuis besok.\nBawa laptop."))

    assert cli.main_umumkan([str(KURSUS_WEB), "--subjek", "Kuis", "--isi", "-"]) == 0
    keluaran = capsys.readouterr().out
    assert keluaran.startswith("Uji coba: belum ada yang dikirim")
    assert "wsfunction=mod_forum_add_discussion, wstoken disembunyikan" in keluaran
    assert "<p>Kuis besok.<br>Bawa laptop.</p>" in keluaran
    assert "Tidak ada yang dikirim. Tambahkan --kirim" in keluaran
    assert TOKEN_UJI not in keluaran
    assert situs.panggilan("mod_forum_add_discussion") == []


def test_cli_umumkan_kirim(situs, kredensial_di_setelan, capsys):
    assert cli.main_umumkan([str(KURSUS_WEB), "--subjek", "Kuis", "--isi", "Besok", "--kirim"]) == 0
    assert "Pengumuman terkirim." in capsys.readouterr().out
    assert len(situs.panggilan("mod_forum_add_discussion")) == 1


def test_cli_beri_nilai_uji_coba(situs, kredensial_di_setelan, capsys):
    assert cli.main_beri_nilai([str(TUGAS_1), "101", "--nilai", "90", "--umpan-balik", "Bagus"]) == 0
    keluaran = capsys.readouterr().out
    assert "nilai_lama: 85" in keluaran and "nilai_baru: 90" in keluaran
    assert situs.panggilan("mod_assign_save_grade") == []


def test_cli_pesan_gagal_sebagian_keluar_dengan_kode_1(situs, kredensial_di_setelan, capsys):
    assert cli.main_pesan(["--ke", "101,104", "--teks", "Halo"]) == 0
    assert "Natasha Romanoff" in capsys.readouterr().out

    assert cli.main_pesan(["--ke", "101", "--ke", "104", "--teks", "Halo", "--kirim", "--json"]) == 1
    assert json.loads(capsys.readouterr().out)["berhasil"] is False


def test_cli_section_dan_tambah_section(situs, kredensial_di_setelan, capsys):
    assert cli.main_section([str(KURSUS_SECTION)]) == 0
    assert "7  id 8007     Session 07 (1 modul)" in capsys.readouterr().out

    assert cli.main_tambah_section([str(KURSUS_SECTION), "--nama", "Session 08", "Session 09"]) == 0
    keluaran = capsys.readouterr().out
    assert "Langkah lewat sesi web" in keluaran
    assert "courseid=5026&insertsection=0&numsections=2&sesskey=<sesskey dari sesi web>" in keluaran
    assert situs.jumlah("GET", "/course/changenumsections.php") == 0

    assert cli.main_tambah_section([str(KURSUS_SECTION), "--nama", "Session 08", "Session 09", "--kirim"]) == 0
    keluaran = capsys.readouterr().out
    assert "2 section ditambahkan dan diberi nama" in keluaran
    assert SESSKEY_UJI not in keluaran and PASSWORD_UJI not in keluaran


def test_cli_ubah_nama_section(situs, kredensial_di_setelan, capsys):
    assert cli.main_ubah_nama_section([str(KURSUS_SECTION), "8003", "--nama", "Session 03: Kelas"]) == 0
    assert "nama_lama: Session 03" in capsys.readouterr().out


# --- MCP -------------------------------------------------------------------


@pytest.fixture
def server_mcp(monkeypatch):
    """Modul server MCP dengan klien dan sesi web bersama yang dikosongkan sebelum dan sesudah uji."""
    pytest.importorskip("mcp")
    from aswaya_mcp import mcp_server

    monkeypatch.setattr(mcp_server, "klien_tersimpan", None)
    monkeypatch.setattr(mcp_server, "sesi_web_tersimpan", None)
    return mcp_server


def daftar_alat(server_mcp) -> dict:
    """Tool MCP berkunci nama."""
    return {satu.name: satu for satu in asyncio.run(server_mcp.server.list_tools())}


def test_mcp_daftar_tool(server_mcp):
    assert set(daftar_alat(server_mcp)) == TOOL_BACA | TOOL_TULIS


def test_mcp_tool_tanpa_parameter_kredensial(server_mcp):
    for satu in daftar_alat(server_mcp).values():
        assert not set(satu.input_schema.get("properties", {})) & {"username", "password", "token", "wstoken"}


def test_mcp_alat_tulis_bawaannya_uji_coba(server_mcp):
    alat = daftar_alat(server_mcp)

    for nama in TOOL_TULIS:
        assert alat[nama].input_schema["properties"]["kirim"]["default"] is False
    assert alat["kirim_pengumuman"].input_schema["properties"]["bentuk"]["enum"] == ["teks", "html"]
    assert set(alat["tambah_section"].input_schema["required"]) == {"kursus_id", "nama"}


def test_mcp_instruksi_meminta_uji_coba_dan_persetujuan(server_mcp):
    instruksi = server_mcp.server.instructions

    assert "Jalankan uji coba lebih dulu" in instruksi
    assert "kirim=True hanya setelah pemakai menyetujuinya" in instruksi
    assert "jangan meminta kata sandi" in instruksi
    assert "https://aswaya.pradita.ac.id" in instruksi


def test_mcp_cek_login(server_mcp, situs, kredensial_di_setelan):
    hasil = server_mcp.cek_login()

    assert hasil["ok"] is True and hasil["userid"] == 7 and hasil["release"].startswith("4.1")
    assert hasil["jumlah_fungsi"] == len(situs.fungsi) and hasil["sumber_token"] == "login"
    assert server_mcp.klien_tersimpan is not None


def test_mcp_cek_login_gagal_dengan_diagnosis(server_mcp, situs):
    from aswaya_mcp import konfigurasi

    konfigurasi.atur_setelan(ASWAYA_USERNAME=USERNAME_UJI, ASWAYA_PASSWORD="sandi-yang-salah")

    hasil = server_mcp.cek_login()

    assert hasil["ok"] is False and "Invalid login" in hasil["pesan"]
    assert hasil["diagnosis"]["layanan_mobile_aktif"] is True


def test_mcp_tanpa_kredensial_memberi_pesan_bukan_galat(server_mcp, situs):
    hasil = server_mcp.daftar_kursus()

    assert hasil["ok"] is False and "ASWAYA_USERNAME" in hasil["pesan"]


def test_mcp_satu_token_untuk_banyak_tool(server_mcp, situs, kredensial_di_setelan):
    assert server_mcp.daftar_kursus("web")["jumlah"] == 1
    assert server_mcp.isi_kursus(KURSUS_WEB)["ok"] is True
    assert server_mcp.peserta_kursus(KURSUS_WEB)["jumlah"] == 5
    assert situs.jumlah("POST", "/login/token.php") == 1


def test_mcp_id_tidak_sah(server_mcp, situs, kredensial_di_setelan):
    hasil = server_mcp.daftar_tugas(-5)

    assert hasil["ok"] is False and "bilangan bulat positif" in hasil["pesan"]


def test_mcp_kirim_pengumuman_bawaannya_uji_coba(server_mcp, situs, kredensial_di_setelan):
    hasil = server_mcp.kirim_pengumuman(KURSUS_WEB, "Kuis", "Besok")

    assert hasil["ok"] is True and hasil["kirim"] is False and hasil["terkirim"] is False
    assert situs.panggilan("mod_forum_add_discussion") == []

    hasil = server_mcp.kirim_pengumuman(KURSUS_WEB, "Kuis", "Besok", kirim=True)
    assert hasil["terkirim"] is True and hasil["hasil"]["discussionid"] == 399


def test_mcp_hasil_tidak_pasti_ditandai_terkirim(server_mcp, situs, kredensial_di_setelan):
    situs.jaringan_putus.add("mod_assign_save_grade")

    hasil = server_mcp.beri_nilai(TUGAS_1, 101, 90, kirim=True)

    assert hasil["ok"] is False and hasil["terkirim"] is True
    assert "sebelum mengirim ulang" in hasil["pesan"]


def test_mcp_penolakan_sebelum_kirim_ditandai_belum_terkirim(server_mcp, situs, kredensial_di_setelan):
    hasil = server_mcp.beri_nilai(TUGAS_1, 101, 150, kirim=True)

    assert hasil == {"ok": False, "terkirim": False, "pesan": hasil["pesan"]}
    assert "melebihi nilai maksimum" in hasil["pesan"]


def test_mcp_kirim_pesan_gagal_sebagian(server_mcp, situs, kredensial_di_setelan):
    hasil = server_mcp.kirim_pesan([101, 104], "Halo", kirim=True)

    assert hasil["ok"] is False and hasil["terkirim"] is True and hasil["berhasil"] is False


def test_mcp_panggil_fungsi(server_mcp, situs, kredensial_di_setelan):
    baca = server_mcp.panggil_fungsi("core_course_get_contents", {"courseid": KURSUS_SECTION})
    terlarang = server_mcp.panggil_fungsi("tool_mobile_get_autologin_key", {"privatetoken": "x"}, kirim=True)

    assert baca["ok"] is True and baca["jenis"] == "baca"
    assert terlarang["ok"] is False and terlarang["terkirim"] is False


def test_mcp_section(server_mcp, situs, kredensial_di_setelan):
    assert server_mcp.daftar_section(KURSUS_SECTION)["jumlah"] == 8

    rencana = server_mcp.tambah_section(KURSUS_SECTION, ["Session 08"])
    assert rencana["ok"] is True and rencana["kirim"] is False
    assert situs.jumlah("POST", "/login/index.php") == 0

    hasil = server_mcp.tambah_section(KURSUS_SECTION, ["Session 08"], kirim=True)
    assert hasil["ok"] is True and hasil["hasil"]["section_baru"][0]["nama_sekarang"] == "Session 08"

    ganti = server_mcp.ubah_nama_section(KURSUS_SECTION, 8001, "Session 01: Pengantar", kirim=True)
    assert ganti["ok"] is True
    assert situs.jumlah("POST", "/login/index.php") == 1


def test_mcp_unduh_dan_tenggat(server_mcp, situs, kredensial_di_setelan, tmp_path):
    unduhan = server_mcp.unduh_berkas(URL_SLIDE, str(tmp_path) + "/")
    tenggat = server_mcp.tenggat(hari=400)

    assert unduhan["ok"] is True and unduhan["path"].endswith("slide-html.pdf")
    assert tenggat["ok"] is False and "antara 1 dan 366" in tenggat["pesan"]


# --- REST API --------------------------------------------------------------


@pytest.fixture
def api(monkeypatch):
    """TestClient REST API dengan simpanan klien dan sesi web yang kosong."""
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx2")
    from fastapi.testclient import TestClient

    from aswaya_mcp import api as modul_api

    monkeypatch.setattr(modul_api, "sesi_tersimpan", {})
    monkeypatch.setattr(modul_api, "sesi_web_tersimpan", {})
    return TestClient(modul_api.app)


def test_api_sesi_dengan_kredensial_per_permintaan_tanpa_cache(api, situs, dir_cache):
    jawaban = api.post("/sesi", json={"username": USERNAME_UJI, "password": PASSWORD_UJI})

    assert jawaban.status_code == 200 and jawaban.json()["userid"] == 7
    assert not dir_cache.exists() or not list(dir_cache.glob("*.json"))


def test_api_password_salah_dibalas_401(api, situs):
    jawaban = api.post("/sesi", json={"username": USERNAME_UJI, "password": "sandi-yang-salah"})

    assert jawaban.status_code == 401 and "sandi-yang-salah" not in jawaban.text


def test_api_kredensial_setengah_dibalas_422(api, situs):
    assert api.post("/sesi", json={"username": USERNAME_UJI}).status_code == 422


def test_api_tanpa_kredensial_dibalas_400(api, situs):
    jawaban = api.get("/kursus")

    assert jawaban.status_code == 400 and "ASWAYA_USERNAME" in jawaban.json()["detail"]


def test_api_kursus_dengan_setelan_header_dan_token(api, situs, kredensial_di_setelan):
    assert api.get("/kursus", params={"cari": "web"}).json()["jumlah"] == 1
    lewat_header = api.get("/kursus", headers={"X-Aswaya-Username": USERNAME_UJI, "X-Aswaya-Password": PASSWORD_UJI})
    lewat_token = api.get("/kursus", headers={"X-Aswaya-Token": TOKEN_UJI})

    assert lewat_header.status_code == 200 and lewat_token.status_code == 200


def test_api_peserta_lengkap(api, situs, kredensial_di_setelan):
    bawaan = api.get(f"/kursus/{KURSUS_WEB}/peserta").json()
    lengkap = api.get(f"/kursus/{KURSUS_WEB}/peserta", params={"lengkap": "true", "peran": "student"}).json()

    assert "email" not in bawaan["peserta"][0]
    assert lengkap["jumlah"] == 4 and lengkap["peserta"][0]["email"].endswith("@contoh.ac.id")


def test_api_baca_lainnya(api, situs, kredensial_di_setelan):
    assert api.get(f"/kursus/{KURSUS_WEB}/isi").json()["jumlah_modul"] == 3
    assert api.get(f"/kursus/{KURSUS_WEB}/tugas").json()["jumlah"] == 2
    assert api.get(f"/kursus/{KURSUS_WEB}/nilai").json()["jumlah_mahasiswa"] == 2
    assert api.get(f"/kursus/{KURSUS_WEB}/forum").json()["jumlah"] == 2
    assert api.get(f"/kursus/{KURSUS_SECTION}/section").json()["jumlah"] == 8
    assert api.get(f"/tugas/{TUGAS_1}/pengumpulan").json()["ringkasan"]["peserta"] == 4
    assert api.get(f"/forum/{FORUM_UMUM}/diskusi").json()["jumlah"] == 2
    assert api.get("/fungsi", params={"cari": "message"}).json()["jumlah"] == 1
    assert api.get("/tenggat", params={"hari": 7}).status_code == 200
    assert api.get("/publik").json()["layanan_mobile_aktif"] is True


def test_api_berkas_dialirkan(api, situs, kredensial_di_setelan):
    jawaban = api.get("/berkas", params={"url": URL_SLIDE})

    assert jawaban.status_code == 200 and jawaban.content.startswith(b"%PDF")
    assert jawaban.headers["content-disposition"] == "attachment; filename=\"slide-html.pdf\"; filename*=UTF-8''slide-html.pdf"


def test_api_nama_berkas_non_ascii():
    pytest.importorskip("fastapi")
    from aswaya_mcp.api import disposisi

    assert disposisi('Materi "Ké-2".pdf') == "attachment; filename=\"Materi _K_-2_.pdf\"; filename*=UTF-8''Materi%20%22K%C3%A9-2%22.pdf"


def test_api_berkas_di_host_lain_dibalas_422(api, situs, kredensial_di_setelan):
    assert api.get("/berkas", params={"url": "https://contoh.id/webservice/pluginfile.php/1/a.pdf"}).status_code == 422


def test_api_pengumuman_bawaannya_uji_coba(api, situs, kredensial_di_setelan):
    jawaban = api.post(f"/kursus/{KURSUS_WEB}/pengumuman", json={"subjek": "Kuis", "isi": "Besok"})

    assert jawaban.status_code == 200 and jawaban.json()["kirim"] is False
    assert TOKEN_UJI not in jawaban.text
    assert situs.panggilan("mod_forum_add_discussion") == []

    terkirim = api.post(f"/kursus/{KURSUS_WEB}/pengumuman", json={"subjek": "Kuis", "isi": "Besok", "kirim": True})
    assert terkirim.json()["terkirim"] is True


def test_api_penolakan_dan_status_http(api, situs, kredensial_di_setelan):
    tanpa_forum = api.post(f"/kursus/{KURSUS_SECTION}/pengumuman", json={"subjek": "Kuis", "isi": "Besok"})
    tidak_tersedia = api.post("/panggil", json={"nama": "core_course_create_courses", "parameter": {}})
    tidak_ada = api.post("/panggil", json={"nama": "core_course_get_course_module_by_instance",
                                           "parameter": {"module": "assign", "instance": 999}})
    nilai_lebih = api.post(f"/tugas/{TUGAS_1}/nilai", json={"user_id": 101, "nilai": 150})

    assert tanpa_forum.status_code == 422
    assert tidak_tersedia.status_code == 403
    assert tidak_ada.status_code == 404
    assert nilai_lebih.status_code == 422
    assert situs.panggilan("mod_assign_save_grade") == []


def test_api_hasil_tidak_pasti_dibalas_502(api, situs, kredensial_di_setelan):
    situs.jaringan_putus.add("core_message_send_instant_messages")

    jawaban = api.post("/pesan", json={"user_ids": [101], "teks": "Halo", "kirim": True})

    assert jawaban.status_code == 502 and "sebelum mengirim ulang" in jawaban.json()["detail"]


def test_api_section(api, situs, kredensial_di_setelan):
    rencana = api.post(f"/kursus/{KURSUS_SECTION}/section", json={"nama": ["Session 08", "Session 09"]})

    assert rencana.status_code == 200 and rencana.json()["kirim"] is False
    assert len(rencana.json()["permintaan"]["langkah"]) == 3

    hasil = api.post(f"/kursus/{KURSUS_SECTION}/section", json={"nama": ["Session 08"], "kirim": True})
    assert hasil.json()["berhasil"] is True

    ganti = api.post(f"/kursus/{KURSUS_SECTION}/section/8002/nama", json={"nama": "Session 02: Kelas", "kirim": True})
    assert ganti.status_code == 200 and ganti.json()["hasil"]["sesuai"] is True
    assert SESSKEY_UJI not in hasil.text + ganti.text
