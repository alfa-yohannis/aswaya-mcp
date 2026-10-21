"""Dasar bersama semua penulisan ke Aswaya: uji coba, pratinjau permintaan, dan hasil kiriman.

Setiap alat yang menulis (kirim_pengumuman, beri_nilai, kirim_pesan, dan
panggil_fungsi untuk fungsi selain baca) mengikuti alur yang sama:

    1. isian diperiksa tanpa menghubungi Aswaya;
    2. data pendukung dibaca (forum pengumuman, nilai lama, nama penerima) supaya
       pratinjaunya bisa diperiksa pemakai;
    3. dengan kirim=False (bawaan) yang kembali hanya HasilTulis berisi
       pratinjau permintaan, tanpa mengirim apa pun;
    4. dengan kirim=True permintaannya dikirim tepat sekali.

Pratinjau memuat fungsi, parameter, dan isian form yang akan dikirim, tanpa
token. Kalau permintaan sudah berangkat tetapi jawabannya tidak bisa dipastikan,
yang muncul HasilTidakPasti dan permintaan itu tidak diulang otomatis.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from aswaya_mcp.aswaya_client import PATH_REST, IsianDitolak, KlienAswaya, ratakan
from aswaya_mcp.teks import teks_ke_html

FORMAT_HTML_MOODLE = 1

PESAN_UJI_COBA = (
    "Uji coba: belum ada yang dikirim ke Aswaya. Periksa pratinjaunya, lalu ulangi dengan "
    "kirim=True (CLI: --kirim) setelah disetujui."
)

BentukIsi = Literal["teks", "html"]


@dataclass
class HasilTulis:
    """Pratinjau (kirim=False) atau hasil (kirim=True) satu permintaan tulis.

    `ringkasan` adalah keterangan untuk dibaca manusia: kursus, forum, nama
    penerima, nilai lama dan baru. `permintaan` adalah yang dikirim apa adanya:
    metode, URL, wsfunction, parameter, dan isian form ratanya, tanpa token.
    `berhasil` bernilai False kalau Aswaya menerima permintaannya tetapi
    sebagian isinya gagal, mis. pesan ke salah satu penerima.
    """

    kirim: bool
    terkirim: bool
    fungsi: str
    ringkasan: dict
    permintaan: dict
    hasil: Any = None
    berhasil: bool = True
    peringatan: list[str] = field(default_factory=list)
    pesan: str = ""

    def sebagai_dict(self) -> dict:
        """Bentuk JSON untuk CLI, REST API, dan MCP."""
        return asdict(self)


def pratinjau_permintaan(klien: KlienAswaya, fungsi: str, parameter: dict) -> dict:
    """Permintaan POST yang akan dikirim ke server.php, tanpa wstoken."""
    return {
        "metode": "POST",
        "url": klien.base_url + PATH_REST,
        "wsfunction": fungsi,
        "parameter": parameter,
        "isian": dict(ratakan(parameter)),
    }


def jalankan_tulis(
    klien: KlienAswaya,
    fungsi: str,
    parameter: dict,
    ringkasan: dict,
    *,
    kirim: bool,
    peringatan: list[str] | None = None,
    pesan_terkirim: str = "Terkirim.",
) -> HasilTulis:
    """Kembalikan pratinjau, atau kirim permintaannya sekali kalau `kirim` bernilai True.

    Ketersediaan fungsinya diperiksa juga pada uji coba, supaya pratinjau tidak
    menjanjikan sesuatu yang pasti ditolak.
    """
    klien.periksa_fungsi(fungsi)
    permintaan = pratinjau_permintaan(klien, fungsi, parameter)
    if not kirim:
        return HasilTulis(
            kirim=False,
            terkirim=False,
            fungsi=fungsi,
            ringkasan=ringkasan,
            permintaan=permintaan,
            peringatan=list(peringatan or []),
            pesan=PESAN_UJI_COBA,
        )
    hasil = klien.panggil(fungsi, parameter, tulis=True)
    return HasilTulis(
        kirim=True,
        terkirim=True,
        fungsi=fungsi,
        ringkasan=ringkasan,
        permintaan=permintaan,
        hasil=hasil,
        peringatan=list(peringatan or []),
        pesan=pesan_terkirim,
    )


def isi_sebagai_html(isi: str, bentuk: BentukIsi, nama_isian: str) -> str:
    """Isi tulisan sebagai HTML: teks biasa diubah, HTML dipakai apa adanya. Isi kosong ditolak."""
    if not (isi or "").strip():
        raise IsianDitolak(f"{nama_isian} tidak boleh kosong")
    if bentuk == "html":
        return isi.strip()
    if bentuk == "teks":
        return teks_ke_html(isi)
    raise IsianDitolak(f"Bentuk {nama_isian} harus 'teks' atau 'html', bukan {bentuk!r}")

