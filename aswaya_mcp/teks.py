"""Teks dari dan ke HTML Moodle, serta waktu Unix sebagai tanggal ISO 8601. Tanpa jaringan.

Moodle mengirim ringkasan kursus, deskripsi modul, dan isi forum sebagai HTML.
Asisten AI dan terminal lebih mudah membaca teks biasa, jadi `teks_dari_html()`
membuang tag, skrip, dan gaya, lalu menjaga batas paragraf dan butir daftar.

Arah sebaliknya dipakai saat menulis. mod_forum_add_discussion selalu menyimpan
pesannya sebagai HTML, jadi teks biasa dari pemakai diubah dulu oleh
`teks_ke_html()`: karakter HTML di-escape, baris kosong memisahkan paragraf, dan
alamat http(s) menjadi tautan yang bisa diklik.
"""

from __future__ import annotations

import html
import re
from datetime import datetime
from html.parser import HTMLParser

from aswaya_mcp.konfigurasi import zona_waktu

# tag yang mengawali baris baru di teks hasil
TAG_BLOK = frozenset({
    "p", "div", "br", "li", "tr", "table", "ul", "ol", "section", "article",
    "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "pre", "hr", "dt", "dd",
})
TAG_DIBUANG = frozenset({"script", "style", "template"})
POLA_URL = re.compile(r"https?://[^\s<>\"']+")
# tanda baca penutup kalimat yang tidak ikut menjadi bagian tautan
TANDA_AKHIR_URL = ".,;:!?)]}"


class PembacaTeks(HTMLParser):
    """Pengumpul teks dari HTML: tag blok menjadi baris baru, skrip dan gaya dibuang."""

    def __init__(self):
        """Pembaca kosong; entitas HTML seperti &amp; langsung diterjemahkan."""
        super().__init__(convert_charrefs=True)
        self.potongan: list[str] = []
        self.kedalaman_dibuang = 0

    def handle_starttag(self, tag, attrs):
        """Tandai awal blok, butir daftar, atau bagian yang dibuang."""
        if tag in TAG_DIBUANG:
            self.kedalaman_dibuang += 1
        elif tag == "li":
            self.potongan.append("\n- ")
        elif tag in TAG_BLOK:
            self.potongan.append("\n")

    def handle_startendtag(self, tag, attrs):
        """Tag tunggal seperti <br/> diperlakukan sama dengan pembukanya."""
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        """Tutup bagian yang dibuang, atau akhiri baris sebuah blok."""
        if tag in TAG_DIBUANG:
            self.kedalaman_dibuang = max(self.kedalaman_dibuang - 1, 0)
        elif tag in TAG_BLOK and tag != "li":
            self.potongan.append("\n")

    def handle_data(self, data):
        """Simpan teks yang terlihat."""
        if not self.kedalaman_dibuang:
            self.potongan.append(data)

    def hasil(self) -> str:
        """Teks terkumpul: spasi dirapikan per baris, baris kosong berturutan dipadatkan."""
        baris_semua = [" ".join(baris.split()) for baris in "".join(self.potongan).splitlines()]
        rapi: list[str] = []
        for baris in baris_semua:
            if baris or (rapi and rapi[-1]):
                rapi.append(baris)
        return "\n".join(rapi).strip()


def teks_dari_html(isi: str | None) -> str:
    """'<p>Halo &amp; <b>selamat</b></p><p>datang</p>' -> 'Halo & selamat\\n\\ndatang'."""
    if not isi:
        return ""
    pembaca = PembacaTeks()
    pembaca.feed(str(isi))
    pembaca.close()
    return pembaca.hasil()


def potong(teks: str, maks: int) -> str:
    """Teks paling panjang `maks` karakter, diakhiri "..." kalau terpotong; 0 berarti utuh."""
    if maks <= 0 or len(teks) <= maks:
        return teks
    return teks[: max(maks - 3, 0)].rstrip() + "..."


def ringkas_html(isi: str | None, maks: int) -> str:
    """HTML sebagai teks biasa yang dipotong sepanjang `maks` karakter."""
    return potong(teks_dari_html(isi), maks)


def tautkan(teks_aman: str) -> str:
    """Bungkus setiap alamat http(s) di teks yang sudah di-escape dengan <a href>."""
    hasil, posisi = [], 0
    for cocok in POLA_URL.finditer(teks_aman):
        alamat = cocok.group(0).rstrip(TANDA_AKHIR_URL)
        akhir = cocok.start() + len(alamat)
        hasil.append(teks_aman[posisi:cocok.start()])
        hasil.append(f'<a href="{alamat}">{alamat}</a>')
        posisi = akhir
    hasil.append(teks_aman[posisi:])
    return "".join(hasil)


def teks_ke_html(teks: str) -> str:
    """Teks biasa sebagai HTML: baris kosong memisahkan paragraf, baris tunggal menjadi <br>.

    Karakter seperti < dan & di-escape, jadi teks yang kebetulan mirip tag tetap
    tampil apa adanya. Alamat http(s) menjadi tautan.
    """
    paragraf = re.split(r"\n\s*\n", (teks or "").replace("\r\n", "\n").strip())
    hasil = []
    for satu in paragraf:
        if not satu.strip():
            continue
        baris = [tautkan(html.escape(isi.strip(), quote=False)) for isi in satu.split("\n")]
        hasil.append("<p>" + "<br>".join(baris) + "</p>")
    return "".join(hasil)


def waktu_iso(detik: int | float | None) -> str | None:
    """Waktu Unix sebagai ISO 8601 di zona waktu setelan; 0 atau None (belum diatur) menjadi None."""
    if not detik:
        return None
    return datetime.fromtimestamp(int(detik), zona_waktu()).isoformat(timespec="minutes")


def tanggal_iso(detik: int | float | None) -> str | None:
    """Tanggalnya saja ('2026-09-01'), untuk tanggal mulai dan selesai kursus."""
    if not detik:
        return None
    return datetime.fromtimestamp(int(detik), zona_waktu()).date().isoformat()
