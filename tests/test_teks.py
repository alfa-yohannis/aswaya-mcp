"""Uji pengubah teks dan HTML serta penulisan waktu, tanpa jaringan."""

from __future__ import annotations

from aswaya_mcp.teks import potong, tanggal_iso, teks_dari_html, teks_ke_html, waktu_iso
from conftest import detik


def test_teks_dari_html_menjaga_paragraf_dan_butir():
    html = "<p>Halo &amp; <b>selamat</b> datang</p><ul><li>Satu</li><li>Dua</li></ul><script>var x = 1;</script>"

    assert teks_dari_html(html) == "Halo & selamat datang\n\n- Satu\n- Dua"


def test_teks_dari_html_kosong():
    assert teks_dari_html(None) == "" and teks_dari_html("") == ""


def test_teks_ke_html_escape_paragraf_dan_tautan():
    teks = "Nilai <80 & hadir.\nMateri: https://contoh.ac.id/a?b=1&c=2.\n\nTerima kasih"

    assert teks_ke_html(teks) == (
        "<p>Nilai &lt;80 &amp; hadir.<br>Materi: "
        '<a href="https://contoh.ac.id/a?b=1&amp;c=2">https://contoh.ac.id/a?b=1&amp;c=2</a>.</p>'
        "<p>Terima kasih</p>"
    )


def test_potong():
    assert potong("abcdef", 0) == "abcdef"
    assert potong("abcdefghij", 6) == "abc..."


def test_waktu_dalam_wib_dan_nol_berarti_kosong():
    assert waktu_iso(detik("2026-09-15 23:59")) == "2026-09-15T23:59+07:00"
    assert tanggal_iso(detik("2026-09-01 00:00")) == "2026-09-01"
    assert waktu_iso(0) is None and tanggal_iso(None) is None
