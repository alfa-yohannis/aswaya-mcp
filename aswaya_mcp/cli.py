"""Perintah baris perintah Aswaya.

    aswaya-cek-login     cek kredensial di setelan (.env) bisa dipakai
    aswaya-publik        konfigurasi publik situs, tanpa login
    aswaya-kursus        kursus yang diikuti pemakai
    aswaya-isi           section, modul, dan berkas satu kursus
    aswaya-peserta       peserta satu kursus
    aswaya-tugas         tugas satu kursus
    aswaya-pengumpulan   pengumpulan dan nilai per mahasiswa untuk satu tugas
    aswaya-nilai         buku nilai satu kursus
    aswaya-forum         forum satu kursus
    aswaya-diskusi       diskusi satu forum
    aswaya-tenggat       kegiatan yang menunggu tindakan
    aswaya-unduh         unduh satu berkas Aswaya
    aswaya-fungsi        fungsi web service yang boleh dipakai token
    aswaya-panggil       panggil wsfunction apa pun (menulis hanya dengan --kirim)
    aswaya-umumkan       pengumuman baru (uji coba; --kirim untuk mengirim)
    aswaya-beri-nilai    nilai seorang mahasiswa (uji coba; --kirim untuk mengirim)
    aswaya-pesan         pesan pribadi (uji coba; --kirim untuk mengirim)
    aswaya-section       section satu kursus
    aswaya-tambah-section      section baru di akhir kursus (uji coba; --kirim, lewat login web)
    aswaya-ubah-nama-section   ganti nama satu section (uji coba; --kirim, lewat login web)

Dari klona repositori, semuanya dipanggil lewat peluncur: `./aswaya kursus`,
`./aswaya isi 5515`, dan seterusnya. Kredensial selalu dibaca dari setelan dan
tidak pernah dicetak. Perintah yang menulis hanya mengirim kalau diberi --kirim;
tanpa itu yang dicetak rencana permintaannya.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys

from aswaya_mcp import forum, fungsi, kalender, kursus, nilai, pesan, section, situs, tugas
from aswaya_mcp.aswaya_client import AswayaError, KlienAswaya
from aswaya_mcp.berkas import unduh_berkas
from aswaya_mcp.konfigurasi import KonfigurasiError
from aswaya_mcp.tulis import HasilTulis


def cetak_json(data) -> int:
    """Keluaran untuk dipipa ke perkakas lain."""
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0


def jalankan_aman(perintah) -> int:
    """Jalankan satu perintah CLI dengan penanganan kesalahan yang seragam.

    Kesalahan pustaka dicetak sebagai satu baris pesan di stderr dengan kode
    keluar 1, supaya pemakai CLI langsung tahu apa yang perlu dibetulkan.
    """
    try:
        return perintah()
    except (AswayaError, KonfigurasiError) as galat:
        print(f"Gagal: {galat}", file=sys.stderr)
        return 1


def pengurai(deskripsi: str) -> argparse.ArgumentParser:
    """Pengurai argumen dengan opsi --json yang dimiliki semua perintah."""
    hasil = argparse.ArgumentParser(description=deskripsi)
    hasil.add_argument("--json", action="store_true", help="Cetak JSON")
    return hasil


def baca_isian(nilai: str) -> str:
    """Isian teks dari argumen; '-' berarti dibaca dari stdin, untuk teks panjang."""
    return sys.stdin.read() if nilai == "-" else nilai


def ukuran_terbaca(ukuran) -> str:
    """1536 -> '1.5 KB'."""
    if not isinstance(ukuran, (int, float)):
        return "?"
    for satuan in ("B", "KB", "MB"):
        if ukuran < 1024:
            return f"{ukuran:.0f} {satuan}" if satuan == "B" else f"{ukuran:.1f} {satuan}"
        ukuran /= 1024
    return f"{ukuran:.1f} GB"


def nilai_atau_strip(nilai) -> str:
    """Nilai untuk tabel teks; None menjadi '-' dan angka bulat tanpa desimal."""
    if nilai is None or nilai == "":
        return "-"
    if isinstance(nilai, float):
        return f"{nilai:g}"
    return str(nilai)


# --- cetak hasil tulis ---------------------------------------------------------


def cetak_hasil_tulis(hasil: HasilTulis) -> None:
    """Ringkasan, peringatan, dan permintaan (uji coba) atau hasil kiriman sebagai teks."""
    print(hasil.pesan)
    print()
    for kunci, isi in hasil.ringkasan.items():
        if isinstance(isi, (list, dict)):
            isi = json.dumps(isi, ensure_ascii=False)
        teks = nilai_atau_strip(isi)
        if "\n" in teks:
            print(f"  {kunci}:")
            for baris in teks.splitlines():
                print(f"    {baris}")
        else:
            print(f"  {kunci}: {teks}")
    for satu in hasil.peringatan:
        print(f"  [peringatan] {satu}")
    cetak_permintaan(hasil.permintaan)
    if not hasil.kirim:
        print("\nTidak ada yang dikirim. Tambahkan --kirim untuk mengirim sungguhan.")
        return
    print("\nJawaban Aswaya:")
    print(json.dumps(hasil.hasil, ensure_ascii=False, indent=2))


def cetak_permintaan(permintaan: dict) -> None:
    """Permintaan web service (satu POST) atau rencana sesi web (beberapa langkah) sebagai teks."""
    if "langkah" in permintaan:
        print("\nLangkah lewat sesi web (sesskey dibaca dari halaman saat dikirim):")
        for nomor, langkah in enumerate(permintaan["langkah"], start=1):
            parameter = "&".join(f"{kunci}={isi}" for kunci, isi in langkah["parameter"].items())
            print(f"  {nomor}. {langkah['metode']} {langkah['url']}?{parameter}")
            if "args" in langkah:
                print(f"     {langkah['methodname']} {json.dumps(langkah['args'], ensure_ascii=False)}")
        return
    print(f"\n{permintaan['metode']} {permintaan['url']}  (wsfunction={permintaan['wsfunction']}, wstoken disembunyikan)")
    lebar = max((len(nama) for nama in permintaan["isian"]), default=0)
    for nama, isi in permintaan["isian"].items():
        tampil = isi if len(isi) <= 200 else isi[:197] + "..."
        print(f"  {nama:<{lebar}}  {tampil}")


def selesai_tulis(hasil: HasilTulis, sebagai_json: bool) -> int:
    """Cetak hasil tulis; kode keluar 1 kalau kiriman sungguhan tidak sepenuhnya berhasil."""
    if sebagai_json:
        cetak_json(hasil.sebagai_dict())
    else:
        cetak_hasil_tulis(hasil)
    return 0 if not hasil.kirim or hasil.berhasil else 1


# --- perintah baca -------------------------------------------------------------


def main_cek_login(argumen_baris: list[str] | None = None) -> int:
    """Pastikan token bisa dipakai, lalu cetak situs, pemakai, release, dan jumlah fungsi."""
    pengurai_cek = pengurai("Cek kredensial Aswaya di setelan (.env) bisa dipakai.")
    pengurai_cek.add_argument("--login-ulang", action="store_true",
                              help="Paksa login dengan password walaupun ada token di setelan atau cache")
    argumen = pengurai_cek.parse_args(argumen_baris)
    klien = KlienAswaya()
    try:
        hasil = situs.cek_login(klien, login_ulang=argumen.login_ulang)
    except AswayaError:
        keterangan = situs.diagnosis(klien)
        if keterangan is not None:
            print(f"Situs terjangkau: {json.dumps(keterangan, ensure_ascii=False)}", file=sys.stderr)
        raise
    if argumen.json:
        return cetak_json(hasil)
    print(f"Login Aswaya OK: {hasil['situs']} ({hasil['url']})")
    print(f"  pemakai   {hasil['nama']} (userid {hasil['userid']})")
    print(f"  Moodle    {hasil['release']}")
    print(f"  fungsi    {hasil['jumlah_fungsi']} tersedia untuk token ini")
    print(f"  token     dari {hasil['sumber_token']}" + (f", cache {hasil['cache_token']}" if hasil["cache_token"] else ""))
    return 0


def main_publik(argumen_baris: list[str] | None = None) -> int:
    """Cetak konfigurasi publik situs tanpa login."""
    argumen = pengurai("Konfigurasi publik Aswaya (tool_mobile_get_public_config), tanpa login.").parse_args(argumen_baris)
    hasil = situs.publik(KlienAswaya())
    if argumen.json:
        return cetak_json(hasil)
    for kunci, isi in hasil.items():
        if kunci != "mentah":
            print(f"  {kunci:<22} {nilai_atau_strip(isi)}")
    return 0


def main_kursus(argumen_baris: list[str] | None = None) -> int:
    """Cetak kursus yang diikuti pemakai."""
    pengurai_kursus = pengurai("Kursus yang Anda ikuti di Aswaya, terbaru dulu.")
    pengurai_kursus.add_argument("--cari", default="", help="Saring dengan potongan nama, nama pendek, atau kategori")
    argumen = pengurai_kursus.parse_args(argumen_baris)
    hasil = kursus.daftar_kursus(KlienAswaya(), argumen.cari)
    if argumen.json:
        return cetak_json(hasil)
    if not hasil["kursus"]:
        print("Tidak ada kursus" + (f" yang cocok dengan {argumen.cari!r}." if argumen.cari else "."))
        return 0
    print(f"{hasil['jumlah']} kursus:\n")
    for satu in hasil["kursus"]:
        tersembunyi = "" if satu["visible"] else "  [tersembunyi]"
        print(f"  {satu['id']:>6}  {satu['fullname']}  ({satu['shortname']}){tersembunyi}")
        print(f"          {nilai_atau_strip(satu['kategori'])}, {nilai_atau_strip(satu['mulai'])} s.d. "
              f"{nilai_atau_strip(satu['selesai'])}  {satu['url']}")
    return 0


def main_isi(argumen_baris: list[str] | None = None) -> int:
    """Cetak section, modul, dan berkas satu kursus."""
    pengurai_isi = pengurai("Section, modul, dan berkas satu kursus.")
    pengurai_isi.add_argument("kursus_id", type=int, help="id kursus dari ./aswaya kursus")
    argumen = pengurai_isi.parse_args(argumen_baris)
    hasil = kursus.isi_kursus(KlienAswaya(), argumen.kursus_id)
    if argumen.json:
        return cetak_json(hasil)
    print(f"Kursus {hasil['kursus_id']}: {hasil['jumlah_section']} section, {hasil['jumlah_modul']} modul\n{hasil['url']}")
    for bagian in hasil["section"]:
        print(f"\n[{bagian['nomor']}] {bagian['nama'] or '(tanpa nama)'}")
        for modul in bagian["modul"]:
            print(f"  - {modul['jenis']} {modul['id']}: {modul['nama']}")
            for tanggal in modul["tanggal"]:
                print(f"      {tanggal['label']} {nilai_atau_strip(tanggal['waktu'])}")
            for berkas in modul["berkas"]:
                print(f"      {berkas['nama']} ({ukuran_terbaca(berkas['ukuran'])})  {berkas['url']}")
    return 0


def main_peserta(argumen_baris: list[str] | None = None) -> int:
    """Cetak peserta satu kursus."""
    pengurai_peserta = pengurai("Peserta satu kursus. Email dan NIM hanya dengan --lengkap.")
    pengurai_peserta.add_argument("kursus_id", type=int, help="id kursus")
    pengurai_peserta.add_argument("--peran", default="", help="Saring per peran, mis. student atau editingteacher")
    pengurai_peserta.add_argument("--lengkap", action="store_true", help="Sertakan email dan idnumber (NIM)")
    argumen = pengurai_peserta.parse_args(argumen_baris)
    hasil = kursus.peserta_kursus(KlienAswaya(), argumen.kursus_id, argumen.peran, argumen.lengkap)
    if argumen.json:
        return cetak_json(hasil)
    peran = ", ".join(f"{satu['shortname']} ({satu['jumlah']})" for satu in hasil["peran_tersedia"])
    print(f"{hasil['jumlah']} peserta di kursus {hasil['kursus_id']}. Peran: {peran or '-'}\n")
    for satu in hasil["peserta"]:
        kolom = [str(satu["id"]), satu["nama"] or "-", ",".join(satu["peran"]) or "-", ",".join(satu["grup"]) or "-",
                 f"akses {nilai_atau_strip(satu['akses_terakhir'])}"]
        if argumen.lengkap:
            kolom += [nilai_atau_strip(satu.get("idnumber")), nilai_atau_strip(satu.get("email"))]
        print("  " + " | ".join(kolom))
    return 0


def main_tugas(argumen_baris: list[str] | None = None) -> int:
    """Cetak tugas satu kursus."""
    pengurai_tugas = pengurai("Tugas (assignment) satu kursus.")
    pengurai_tugas.add_argument("kursus_id", type=int, help="id kursus")
    argumen = pengurai_tugas.parse_args(argumen_baris)
    hasil = tugas.daftar_tugas(KlienAswaya(), argumen.kursus_id)
    if argumen.json:
        return cetak_json(hasil)
    print(f"{hasil['jumlah']} tugas di {hasil['kursus'] or 'kursus ' + str(hasil['kursus_id'])}\n")
    for satu in hasil["tugas"]:
        print(f"  {satu['id']:>6}  {satu['nama']}")
        print(f"          tenggat {nilai_atau_strip(satu['tenggat'])}, batas akhir {nilai_atau_strip(satu['batas_akhir'])}, "
              f"nilai maks {nilai_atau_strip(satu['nilai_maks'])}  {satu['url']}")
    for satu in hasil["peringatan"]:
        print(f"[peringatan] {satu}")
    return 0


def main_pengumpulan(argumen_baris: list[str] | None = None) -> int:
    """Cetak pengumpulan dan nilai setiap mahasiswa untuk satu tugas."""
    pengurai_kumpul = pengurai("Pengumpulan dan nilai per mahasiswa untuk satu tugas.")
    pengurai_kumpul.add_argument("tugas_id", type=int, help="id tugas dari ./aswaya tugas")
    argumen = pengurai_kumpul.parse_args(argumen_baris)
    hasil = tugas.pengumpulan_tugas(KlienAswaya(), argumen.tugas_id)
    if argumen.json:
        return cetak_json(hasil)
    ringkas = hasil["ringkasan"]
    print(f"Tugas {hasil['tugas_id']}: {ringkas['peserta']} peserta, {ringkas['dikumpulkan']} dikumpulkan, "
          f"{ringkas['draf']} draf, {ringkas['belum']} belum, {ringkas['dinilai']} dinilai, "
          f"{ringkas['perlu_dinilai']} perlu dinilai\n")
    for satu in hasil["mahasiswa"]:
        tanda = "  *perlu dinilai" if satu["perlu_dinilai"] else ""
        print(f"  {satu['user_id']:>6}  {satu['nama'] or '-'} | {satu['keterangan']} "
              f"{nilai_atau_strip(satu['waktu_kumpul'])} | nilai {nilai_atau_strip(satu['nilai'])}{tanda}")
        for berkas in satu["berkas"]:
            print(f"          {berkas['nama']} ({ukuran_terbaca(berkas['ukuran'])})  {berkas['url']}")
    for satu in hasil["peringatan"]:
        print(f"[peringatan] {satu}")
    return 0


def cetak_csv_nilai(hasil: dict) -> int:
    """Buku nilai sebagai CSV: user_id, nama, lalu satu kolom per item nilai."""
    penulis = csv.writer(sys.stdout)
    penulis.writerow(["user_id", "nama"] + [f"{item['nama']} (#{item['id']})" for item in hasil["item"]])
    for satu in hasil["mahasiswa"]:
        penulis.writerow(
            [satu["user_id"], satu["nama"]]
            + ["" if satu["nilai"].get(str(item["id"])) is None else f"{satu['nilai'][str(item['id'])]:g}" for item in hasil["item"]]
        )
    return 0


def main_nilai(argumen_baris: list[str] | None = None) -> int:
    """Cetak buku nilai satu kursus, sebagai teks, JSON, atau CSV."""
    pengurai_nilai = pengurai("Buku nilai satu kursus.")
    pengurai_nilai.add_argument("kursus_id", type=int, help="id kursus")
    pengurai_nilai.add_argument("--csv", action="store_true", help="Cetak CSV, mis. untuk dibuka di spreadsheet")
    argumen = pengurai_nilai.parse_args(argumen_baris)
    hasil = nilai.nilai_kursus(KlienAswaya(), argumen.kursus_id)
    if argumen.json:
        return cetak_json(hasil)
    if argumen.csv:
        return cetak_csv_nilai(hasil)
    print(f"{hasil['jumlah_mahasiswa']} mahasiswa, {hasil['jumlah_item']} item nilai\n")
    for item in hasil["item"]:
        print(f"  #{item['id']:<6} {item['nama']} (maks {nilai_atau_strip(item['maks'])})")
    print()
    for satu in hasil["mahasiswa"]:
        isi = ", ".join(f"#{kunci}={nilai_atau_strip(angka)}" for kunci, angka in satu["nilai"].items())
        print(f"  {satu['user_id']:>6}  {satu['nama']}: {isi}")
    return 0


def main_forum(argumen_baris: list[str] | None = None) -> int:
    """Cetak forum satu kursus."""
    pengurai_forum = pengurai("Forum satu kursus.")
    pengurai_forum.add_argument("kursus_id", type=int, help="id kursus")
    argumen = pengurai_forum.parse_args(argumen_baris)
    hasil = forum.daftar_forum(KlienAswaya(), argumen.kursus_id)
    if argumen.json:
        return cetak_json(hasil)
    print(f"{hasil['jumlah']} forum di kursus {hasil['kursus_id']}\n")
    for satu in hasil["forum"]:
        tanda = "  [pengumuman]" if satu["pengumuman"] else ""
        print(f"  {satu['id']:>6}  {satu['nama']} ({satu['jenis']}, {nilai_atau_strip(satu['jumlah_diskusi'])} diskusi){tanda}")
    return 0


def main_diskusi(argumen_baris: list[str] | None = None) -> int:
    """Cetak diskusi satu forum."""
    pengurai_diskusi = pengurai("Diskusi satu forum, terbaru dulu.")
    pengurai_diskusi.add_argument("forum_id", type=int, help="id forum dari ./aswaya forum")
    argumen = pengurai_diskusi.parse_args(argumen_baris)
    hasil = forum.diskusi_forum(KlienAswaya(), argumen.forum_id)
    if argumen.json:
        return cetak_json(hasil)
    print(f"{hasil['jumlah']} diskusi di forum {hasil['forum_id']}\n")
    for satu in hasil["diskusi"]:
        print(f"  {satu['id']:>6}  {satu['subjek']}  ({satu['penulis']}, {nilai_atau_strip(satu['dibuat'])}, "
              f"{nilai_atau_strip(satu['jumlah_balasan'])} balasan)")
    return 0


def main_tenggat(argumen_baris: list[str] | None = None) -> int:
    """Cetak kegiatan yang menunggu tindakan."""
    pengurai_tenggat = pengurai("Kegiatan yang menunggu tindakan, dari kalender Moodle.")
    pengurai_tenggat.add_argument("--hari", type=int, default=kalender.HARI_BAWAAN, help="Jangkauan ke depan (bawaan 30)")
    pengurai_tenggat.add_argument("--kursus", type=int, default=0, help="Batasi ke satu kursus")
    argumen = pengurai_tenggat.parse_args(argumen_baris)
    hasil = kalender.tenggat(KlienAswaya(), argumen.hari, argumen.kursus or None)
    if argumen.json:
        return cetak_json(hasil)
    print(f"{hasil['jumlah']} kegiatan, {hasil['dari']} s.d. {hasil['sampai']}\n")
    for satu in hasil["kegiatan"]:
        jumlah = f" ({satu['jumlah_item']})" if satu["jumlah_item"] else ""
        lewat = "  [lewat]" if satu["lewat"] else ""
        print(f"  {satu['waktu']}  {satu['nama']}  [{nilai_atau_strip(satu['kursus'])}] "
              f"{nilai_atau_strip(satu['tindakan'])}{jumlah}{lewat}")
    return 0


def main_unduh(argumen_baris: list[str] | None = None) -> int:
    """Unduh satu berkas Aswaya."""
    pengurai_unduh = pengurai("Unduh satu berkas Aswaya (fileurl dari isi, pengumpulan, atau diskusi).")
    pengurai_unduh.add_argument("url", help="fileurl berkas, .../webservice/pluginfile.php/...")
    pengurai_unduh.add_argument("--tujuan", default="",
                                help="Path berkas atau direktori (akhiri dengan /); bawaannya data/unduhan/")
    pengurai_unduh.add_argument("--timpa", action="store_true", help="Timpa berkas yang sudah ada")
    argumen = pengurai_unduh.parse_args(argumen_baris)
    hasil = unduh_berkas(KlienAswaya(), argumen.url, argumen.tujuan, timpa=argumen.timpa)
    if argumen.json:
        return cetak_json(hasil)
    print(f"Tersimpan: {hasil['path']} ({ukuran_terbaca(hasil['ukuran'])}, {hasil['jenis'] or 'jenis tidak diketahui'})")
    return 0


def main_fungsi(argumen_baris: list[str] | None = None) -> int:
    """Cetak fungsi web service yang boleh dipakai token."""
    pengurai_fungsi = pengurai("Fungsi web service yang boleh dipakai token ini.")
    pengurai_fungsi.add_argument("cari", nargs="?", default="", help="Potongan nama fungsi, mis. forum")
    argumen = pengurai_fungsi.parse_args(argumen_baris)
    hasil = fungsi.fungsi_tersedia(KlienAswaya(), argumen.cari)
    if argumen.json:
        return cetak_json(hasil)
    print(f"{hasil['jumlah']} dari {hasil['jumlah_semua']} fungsi" + (f" memuat {argumen.cari!r}" if argumen.cari else "") + "\n")
    for satu in hasil["fungsi"]:
        print(f"  {satu['nama']}" + ("" if satu["baca"] else "  (tulis: perlu --kirim)"))
    return 0


def main_section(argumen_baris: list[str] | None = None) -> int:
    """Cetak section satu kursus."""
    pengurai_section = pengurai("Section satu kursus: id, nomor, nama, dan jumlah modul.")
    pengurai_section.add_argument("kursus_id", type=int, help="id kursus")
    argumen = pengurai_section.parse_args(argumen_baris)
    hasil = section.daftar_section(KlienAswaya(), argumen.kursus_id)
    if argumen.json:
        return cetak_json(hasil)
    print(f"{hasil['jumlah']} section di kursus {hasil['kursus_id']}\n{hasil['url']}\n")
    for satu in hasil["section"]:
        tersembunyi = "" if satu["visible"] else "  [tersembunyi]"
        print(f"  {satu['nomor']:>3}  id {satu['id']:<8} {satu['nama']} ({satu['jumlah_modul']} modul){tersembunyi}")
    return 0


# --- perintah tulis ------------------------------------------------------------


def main_panggil(argumen_baris: list[str] | None = None) -> int:
    """Panggil satu wsfunction; fungsi selain baca hanya dipratinjau tanpa --kirim."""
    pengurai_panggil = argparse.ArgumentParser(
        description="Panggil wsfunction apa pun. Fungsi baca (_get_, _search_, _list_) langsung dijalankan; "
        "fungsi lain hanya dipratinjau kecuali diberi --kirim. Keluarannya selalu JSON."
    )
    pengurai_panggil.add_argument("nama", help="Nama wsfunction, mis. core_course_get_contents")
    pengurai_panggil.add_argument("--parameter", default="{}", help="Parameter sebagai objek JSON; '-' dibaca dari stdin")
    pengurai_panggil.add_argument("--kirim", action="store_true", help="Benar-benar menjalankan fungsi yang menulis")
    pengurai_panggil.add_argument("--maks", type=int, default=0, metavar="N",
                                  help="Potong hasil baca sepanjang N karakter; 0 berarti utuh")
    argumen = pengurai_panggil.parse_args(argumen_baris)
    try:
        parameter = json.loads(baca_isian(argumen.parameter))
    except ValueError as galat:
        raise AswayaError(f"--parameter bukan JSON yang sah: {galat}") from galat
    hasil = fungsi.panggil_fungsi(KlienAswaya(), argumen.nama, parameter, kirim=argumen.kirim, maks_karakter=argumen.maks)
    cetak_json(hasil)
    return 0


def main_umumkan(argumen_baris: list[str] | None = None) -> int:
    """Buat pengumuman di forum pengumuman satu kursus; tanpa --kirim hanya uji coba."""
    pengurai_umumkan = pengurai(
        "Pengumuman baru di forum pengumuman satu kursus. Tanpa --kirim hanya uji coba."
    )
    pengurai_umumkan.add_argument("kursus_id", type=int, help="id kursus")
    pengurai_umumkan.add_argument("--subjek", required=True, help="Subjek pengumuman")
    pengurai_umumkan.add_argument("--isi", required=True, help="Isi pengumuman; '-' dibaca dari stdin")
    pengurai_umumkan.add_argument("--html", action="store_true", help="Isi sudah berupa HTML")
    pengurai_umumkan.add_argument("--kirim", action="store_true", help="Benar-benar mengirim; tanpa ini hanya uji coba")
    argumen = pengurai_umumkan.parse_args(argumen_baris)
    hasil = forum.kirim_pengumuman(
        KlienAswaya(), argumen.kursus_id, argumen.subjek, baca_isian(argumen.isi),
        kirim=argumen.kirim, bentuk="html" if argumen.html else "teks",
    )
    return selesai_tulis(hasil, argumen.json)


def main_beri_nilai(argumen_baris: list[str] | None = None) -> int:
    """Simpan nilai seorang mahasiswa; tanpa --kirim hanya uji coba."""
    pengurai_nilai = pengurai("Nilai seorang mahasiswa untuk satu tugas. Tanpa --kirim hanya uji coba.")
    pengurai_nilai.add_argument("tugas_id", type=int, help="id tugas")
    pengurai_nilai.add_argument("user_id", type=int, help="userid mahasiswa")
    pengurai_nilai.add_argument("--nilai", required=True, type=float, help="Nilai baru")
    pengurai_nilai.add_argument("--umpan-balik", default="", help="Umpan balik; '-' dibaca dari stdin")
    pengurai_nilai.add_argument("--html", action="store_true", help="Umpan balik sudah berupa HTML")
    pengurai_nilai.add_argument("--kirim", action="store_true", help="Benar-benar menyimpan; tanpa ini hanya uji coba")
    argumen = pengurai_nilai.parse_args(argumen_baris)
    hasil = tugas.beri_nilai(
        KlienAswaya(), argumen.tugas_id, argumen.user_id, argumen.nilai, baca_isian(argumen.umpan_balik),
        kirim=argumen.kirim, bentuk="html" if argumen.html else "teks",
    )
    return selesai_tulis(hasil, argumen.json)


def daftar_id(nilai_ke: list[str]) -> list[str]:
    """['12,34', '56'] -> ['12', '34', '56']; id diperiksa oleh kirim_pesan."""
    return [bagian.strip() for satu in nilai_ke for bagian in satu.split(",") if bagian.strip()]


def main_pesan(argumen_baris: list[str] | None = None) -> int:
    """Kirim pesan pribadi ke beberapa pengguna; tanpa --kirim hanya uji coba."""
    pengurai_pesan = pengurai("Pesan pribadi Moodle ke satu atau beberapa pengguna. Tanpa --kirim hanya uji coba.")
    pengurai_pesan.add_argument("--ke", action="append", required=True, metavar="USER_ID",
                                help="userid penerima; boleh diulang atau dipisah koma")
    pengurai_pesan.add_argument("--teks", required=True, help="Isi pesan; '-' dibaca dari stdin")
    pengurai_pesan.add_argument("--html", action="store_true", help="Teks sudah berupa HTML")
    pengurai_pesan.add_argument("--kirim", action="store_true", help="Benar-benar mengirim; tanpa ini hanya uji coba")
    argumen = pengurai_pesan.parse_args(argumen_baris)
    hasil = pesan.kirim_pesan(
        KlienAswaya(), daftar_id(argumen.ke), baca_isian(argumen.teks),
        kirim=argumen.kirim, bentuk="html" if argumen.html else "teks",
    )
    return selesai_tulis(hasil, argumen.json)


def main_tambah_section(argumen_baris: list[str] | None = None) -> int:
    """Tambahkan section baru di akhir kursus; tanpa --kirim hanya uji coba."""
    pengurai_tambah = pengurai(
        "Tambahkan section di akhir kursus, satu per nama. Tanpa --kirim hanya uji coba. "
        "Pengiriman lewat login web, jadi butuh ASWAYA_PASSWORD."
    )
    pengurai_tambah.add_argument("kursus_id", type=int, help="id kursus")
    pengurai_tambah.add_argument("--nama", nargs="+", required=True, metavar="NAMA",
                                 help='Nama section baru, berurutan; mis. --nama "Session "{08..14}')
    pengurai_tambah.add_argument("--paksa", action="store_true", help="Tetap tambahkan walau namanya sudah terpakai")
    pengurai_tambah.add_argument("--kirim", action="store_true", help="Benar-benar menambahkan; tanpa ini hanya uji coba")
    argumen = pengurai_tambah.parse_args(argumen_baris)
    hasil = section.tambah_section(
        KlienAswaya(), argumen.kursus_id, argumen.nama, kirim=argumen.kirim, paksa=argumen.paksa
    )
    return selesai_tulis(hasil, argumen.json)


def main_ubah_nama_section(argumen_baris: list[str] | None = None) -> int:
    """Ganti nama satu section; tanpa --kirim hanya uji coba."""
    pengurai_ubah = pengurai(
        "Ganti nama satu section. Tanpa --kirim hanya uji coba. Pengiriman lewat login web, jadi butuh ASWAYA_PASSWORD."
    )
    pengurai_ubah.add_argument("kursus_id", type=int, help="id kursus")
    pengurai_ubah.add_argument("section_id", type=int, help="id section dari ./aswaya section (bukan nomornya)")
    pengurai_ubah.add_argument("--nama", required=True, help="Nama baru")
    pengurai_ubah.add_argument("--kirim", action="store_true", help="Benar-benar mengganti; tanpa ini hanya uji coba")
    argumen = pengurai_ubah.parse_args(argumen_baris)
    hasil = section.ubah_nama_section(
        KlienAswaya(), argumen.kursus_id, argumen.section_id, argumen.nama, kirim=argumen.kirim
    )
    return selesai_tulis(hasil, argumen.json)


# --- titik masuk ---------------------------------------------------------------


def jalankan_cek_login() -> int:
    """Titik masuk perintah `aswaya-cek-login`."""
    return jalankan_aman(main_cek_login)


def jalankan_publik() -> int:
    """Titik masuk perintah `aswaya-publik`."""
    return jalankan_aman(main_publik)


def jalankan_kursus() -> int:
    """Titik masuk perintah `aswaya-kursus`."""
    return jalankan_aman(main_kursus)


def jalankan_isi() -> int:
    """Titik masuk perintah `aswaya-isi`."""
    return jalankan_aman(main_isi)


def jalankan_peserta() -> int:
    """Titik masuk perintah `aswaya-peserta`."""
    return jalankan_aman(main_peserta)


def jalankan_tugas() -> int:
    """Titik masuk perintah `aswaya-tugas`."""
    return jalankan_aman(main_tugas)


def jalankan_pengumpulan() -> int:
    """Titik masuk perintah `aswaya-pengumpulan`."""
    return jalankan_aman(main_pengumpulan)


def jalankan_nilai() -> int:
    """Titik masuk perintah `aswaya-nilai`."""
    return jalankan_aman(main_nilai)


def jalankan_forum() -> int:
    """Titik masuk perintah `aswaya-forum`."""
    return jalankan_aman(main_forum)


def jalankan_diskusi() -> int:
    """Titik masuk perintah `aswaya-diskusi`."""
    return jalankan_aman(main_diskusi)


def jalankan_tenggat() -> int:
    """Titik masuk perintah `aswaya-tenggat`."""
    return jalankan_aman(main_tenggat)


def jalankan_unduh() -> int:
    """Titik masuk perintah `aswaya-unduh`."""
    return jalankan_aman(main_unduh)


def jalankan_fungsi() -> int:
    """Titik masuk perintah `aswaya-fungsi`."""
    return jalankan_aman(main_fungsi)


def jalankan_panggil() -> int:
    """Titik masuk perintah `aswaya-panggil`."""
    return jalankan_aman(main_panggil)


def jalankan_umumkan() -> int:
    """Titik masuk perintah `aswaya-umumkan`."""
    return jalankan_aman(main_umumkan)


def jalankan_beri_nilai() -> int:
    """Titik masuk perintah `aswaya-beri-nilai`."""
    return jalankan_aman(main_beri_nilai)


def jalankan_pesan() -> int:
    """Titik masuk perintah `aswaya-pesan`."""
    return jalankan_aman(main_pesan)


def jalankan_section() -> int:
    """Titik masuk perintah `aswaya-section`."""
    return jalankan_aman(main_section)


def jalankan_tambah_section() -> int:
    """Titik masuk perintah `aswaya-tambah-section`."""
    return jalankan_aman(main_tambah_section)


def jalankan_ubah_nama_section() -> int:
    """Titik masuk perintah `aswaya-ubah-nama-section`."""
    return jalankan_aman(main_ubah_nama_section)


if __name__ == "__main__":
    sys.exit(jalankan_kursus())
