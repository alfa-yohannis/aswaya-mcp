#!/usr/bin/env python3
"""Contoh memakai aswaya-mcp sebagai pustaka dari program Python sendiri.

Isi kredensial di .env pada akar proyek (salin dari .env.contoh), lalu:

    .venv/bin/python examples/pustaka.py

Hanya membaca: mencetak kursus Anda, lalu ringkasan pengumpulan tugas pertama
di kursus terbaru. Kredensial juga boleh diberikan dari kode lewat
atur_setelan(), seperti dicontohkan di bawah dalam keadaan dikomentari.
"""

from __future__ import annotations

import sys

from aswaya_mcp import AswayaError, KlienAswaya, KonfigurasiError, daftar_kursus, daftar_tugas, pengumpulan_tugas


def main() -> int:
    """Cetak kursus, lalu siapa yang sudah dan belum mengumpulkan tugas pertama di kursus terbaru."""
    # Setelan dari kode, untuk aplikasi yang menyimpan konfigurasinya sendiri:
    # from aswaya_mcp import atur_setelan
    # atur_setelan(ASWAYA_USERNAME="nama.anda@pradita.ac.id", ASWAYA_PASSWORD="...")

    try:
        klien = KlienAswaya()  # belum menghubungi Aswaya
        kursus = daftar_kursus(klien)["kursus"]  # token diambil di sini
        print(f"{len(kursus)} kursus:")
        for satu in kursus:
            print(f"  {satu['id']:>6}  {satu['fullname']}  ({satu['mulai']} s.d. {satu['selesai']})")
        if not kursus:
            return 0

        terbaru = kursus[0]
        tugas = daftar_tugas(klien, terbaru["id"])["tugas"]
        if not tugas:
            print(f"\nBelum ada tugas di {terbaru['fullname']}.")
            return 0
        status = pengumpulan_tugas(klien, tugas[0]["id"])
    except (AswayaError, KonfigurasiError) as galat:
        print(f"Gagal: {galat}", file=sys.stderr)
        return 1

    print(f"\n{tugas[0]['nama']} ({terbaru['fullname']}): {status['ringkasan']}")
    for mahasiswa in status["mahasiswa"]:
        print(f"  {mahasiswa['nama'] or mahasiswa['user_id']}: {mahasiswa['keterangan']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
