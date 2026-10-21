"""Uji ubah_ringkasan_section dan pembaca form web di atas Aswaya tiruan."""

from __future__ import annotations

import pytest

from aswaya_mcp import section
from aswaya_mcp.aswaya_client import IsianDitolak
from aswaya_mcp.sesi_web import cari_form, isian_form, sup_dari
from conftest import KURSUS_WEB, SESSKEY_UJI

SECTION_UMUM = 9000  # section 0 kursus web, ringkasannya "<p>Selamat datang di kelas.</p>"
RINGKASAN_AWAL = "<p>Selamat datang di kelas.</p>"
SLIDES = "https://drive.google.com/file/d/contoh-slides/view?usp=sharing"
ISI = f'<h3>Materi:</h3>\r\n<p><a href="{SLIDES}">Slides (PDF)</a></p>'


def ringkasan_di_situs(situs, section_id: int = SECTION_UMUM) -> str:
    """Ringkasan satu section di situs tiruan."""
    for daftar in situs.data["section"].values():
        for satu in daftar:
            if satu["id"] == section_id:
                return satu.get("summary") or ""
    raise AssertionError(f"section {section_id} tidak ada")


# --- pembaca form ------------------------------------------------------------------


def test_isian_form_seperti_peramban():
    html = (
        '<form action="/course/modedit.php" method="post">'
        '<input type="hidden" name="a" value="1"><input type="text" name="b" value="x">'
        '<input type="checkbox" name="c" value="1"><input type="checkbox" name="d" value="1" checked>'
        '<input type="radio" name="e" value="0" checked><input type="radio" name="e" value="1">'
        '<select name="f"><option value="0">A</option><option value="5" selected>B</option></select>'
        '<select name="g[]" multiple><option value="1" selected>1</option><option value="2" selected>2</option></select>'
        '<select name="h"></select>'
        "<textarea name=\"i\">&lt;p&gt;hai&lt;/p&gt;</textarea>"
        '<input type="text" name="j" value="tidak" disabled>'
        '<input type="submit" name="simpan" value="Simpan"></form>'
    )

    isian = isian_form(cari_form(html, "/course/modedit.php"))

    assert isian == [("a", "1"), ("b", "x"), ("d", "1"), ("e", "0"), ("f", "5"),
                     ("g[]", "1"), ("g[]", "2"), ("i", "<p>hai</p>")]


def test_cari_form_memilih_form_menurut_action():
    html = ('<form action="/login/index.php"><input name="x" value="y"></form>'
            '<form action="https://aswaya.example/course/editsection.php"><input name="k" value="v"></form>')

    assert isian_form(cari_form(html, "/course/editsection.php")) == [("k", "v")]
    assert cari_form(html, "/course/modedit.php") is None


def test_tautan_dibuka_di_tab_baru():
    hasil = section.buka_di_tab_baru(
        '<p><a href="https://a.example/x">A</a> dan <a href="https://b.example" rel="nofollow">B</a></p>'
    )

    tautan = sup_dari(hasil).find_all("a")
    assert [satu["target"] for satu in tautan] == ["_blank", "_blank"]
    assert tautan[0]["rel"] == ["noopener"]
    assert tautan[1]["rel"] == ["nofollow", "noopener"]


# --- uji coba -------------------------------------------------------------------------


def test_uji_coba_menampilkan_ringkasan_lama_dan_baru_tanpa_login_web(klien, situs):
    hasil = section.ubah_ringkasan_section(klien, KURSUS_WEB, SECTION_UMUM, ISI, bentuk="html")

    assert hasil.kirim is False and hasil.terkirim is False
    ringkasan = hasil.ringkasan
    assert ringkasan["nomor"] == 0 and ringkasan["cara"] == "tambah"
    assert ringkasan["ringkasan_lama"] == RINGKASAN_AWAL
    assert ringkasan["ringkasan_baru"].startswith(RINGKASAN_AWAL + "\r\n<h3>Materi:</h3>")
    assert 'target="_blank"' in ringkasan["isi_baru"] and ringkasan["tautan_baru"] == [SLIDES]
    assert situs.jumlah("GET", "/course/editsection.php") == 0
    assert situs.jumlah("GET", "/login/index.php") == 0


def test_teks_biasa_menjadi_paragraf_dengan_tautan_di_tab_baru(klien):
    hasil = section.ubah_ringkasan_section(klien, KURSUS_WEB, SECTION_UMUM, f"Slides: {SLIDES}")

    tautan = sup_dari(hasil.ringkasan["isi_baru"]).find("a")
    assert tautan["href"] == SLIDES and tautan["target"] == "_blank" and tautan["rel"] == ["noopener"]
    assert hasil.ringkasan["isi_baru"].startswith("<p>Slides: ")


def test_tab_baru_bisa_dimatikan(klien):
    hasil = section.ubah_ringkasan_section(klien, KURSUS_WEB, SECTION_UMUM, ISI, bentuk="html", tab_baru=False)

    assert "target=" not in hasil.ringkasan["isi_baru"]


def test_section_kursus_lain_ditolak(klien):
    with pytest.raises(IsianDitolak, match="bukan section kursus"):
        section.ubah_ringkasan_section(klien, KURSUS_WEB, 8000, ISI, bentuk="html")


def test_isi_kosong_dan_cara_asing_ditolak(klien):
    with pytest.raises(IsianDitolak, match="tidak boleh kosong"):
        section.ubah_ringkasan_section(klien, KURSUS_WEB, SECTION_UMUM, "   ")
    with pytest.raises(IsianDitolak, match="cara harus"):
        section.ubah_ringkasan_section(klien, KURSUS_WEB, SECTION_UMUM, ISI, cara="sisip")


# --- kirim ----------------------------------------------------------------------------


def test_kirim_menambah_di_akhir_dan_memeriksa_ulang(klien, situs):
    hasil = section.ubah_ringkasan_section(klien, KURSUS_WEB, SECTION_UMUM, ISI, bentuk="html", kirim=True)

    assert hasil.terkirim is True and hasil.berhasil is True
    ringkasan = ringkasan_di_situs(situs)
    assert ringkasan.startswith(RINGKASAN_AWAL + "\r\n<h3>Materi:</h3>")
    assert f'href="{SLIDES}"' in ringkasan and 'target="_blank"' in ringkasan
    assert hasil.hasil["sesuai"] is True and hasil.hasil["tautan_ada"] == [SLIDES]
    kiriman = [satu for satu in situs.permintaan if satu["path"] == "/course/editsection.php" and satu["metode"] == "POST"]
    assert len(kiriman) == 1
    isian = dict(kiriman[0]["isian"])
    assert isian["sesskey"] == SESSKEY_UJI and isian["submitbutton"] == "Save changes" and "cancel" not in isian
    assert isian["course"] == str(KURSUS_WEB) and isian["summary_editor[itemid]"] == "113051269"
    assert isian["availabilityconditionsjson"] == '{"op":"&","c":[],"showc":[]}'


def test_tautan_yang_sudah_ada_ditolak_kecuali_paksa(klien, situs):
    section.ubah_ringkasan_section(klien, KURSUS_WEB, SECTION_UMUM, ISI, bentuk="html", kirim=True)

    with pytest.raises(IsianDitolak, match="sudah ada"):
        section.ubah_ringkasan_section(klien, KURSUS_WEB, SECTION_UMUM, ISI, bentuk="html")
    hasil = section.ubah_ringkasan_section(klien, KURSUS_WEB, SECTION_UMUM, ISI, bentuk="html", paksa=True)
    assert any("sudah ada" in satu for satu in hasil.peringatan)


def test_ganti_mengganti_seluruh_ringkasan(klien, situs):
    hasil = section.ubah_ringkasan_section(klien, KURSUS_WEB, SECTION_UMUM, "Ringkasan baru", cara="ganti", kirim=True)

    assert hasil.berhasil is True
    assert ringkasan_di_situs(situs) == "<p>Ringkasan baru</p>"


def test_form_yang_ditolak_aswaya_tidak_mengubah_ringkasan(klien, situs):
    situs.galat_form_section = "Ringkasan terlalu panjang"

    with pytest.raises(IsianDitolak, match="Ringkasan terlalu panjang"):
        section.ubah_ringkasan_section(klien, KURSUS_WEB, SECTION_UMUM, ISI, bentuk="html", kirim=True)
    assert ringkasan_di_situs(situs) == RINGKASAN_AWAL


def test_awal_menaruh_isi_di_bagian_paling_atas(klien, situs):
    rencana = section.ubah_ringkasan_section(klien, KURSUS_WEB, SECTION_UMUM, ISI, bentuk="html", cara="awal")
    assert rencana.ringkasan["ringkasan_baru"].endswith("\r\n" + RINGKASAN_AWAL)

    hasil = section.ubah_ringkasan_section(klien, KURSUS_WEB, SECTION_UMUM, ISI, bentuk="html", cara="awal", kirim=True)

    assert hasil.berhasil is True
    ringkasan = ringkasan_di_situs(situs)
    assert ringkasan.startswith("<h3>Materi:</h3>") and ringkasan.endswith(RINGKASAN_AWAL)
    with pytest.raises(IsianDitolak, match="sudah ada"):
        section.ubah_ringkasan_section(klien, KURSUS_WEB, SECTION_UMUM, ISI, bentuk="html", cara="awal")
