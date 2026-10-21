"""Section kursus: daftar, tambah, ganti nama, dan ubah ringkasan.

    daftar_section          core_course_get_contents lewat token web service
    tambah_section          GET /course/changenumsections.php?courseid=..&insertsection=0
                            &numsections=N&sesskey=.. lewat sesi web, lalu setiap section
                            baru diberi nama lewat core_update_inplace_editable
    ubah_nama_section       core_update_inplace_editable lewat sesi web
    ubah_ringkasan_section  GET /course/editsection.php?id=<section_id>, lalu POST form-nya
                            dengan summary_editor[text] yang baru lewat sesi web

Layanan moodle_mobile_app tidak memuat fungsi pembuat atau pengubah section,
jadi tiga alat terakhir memakai sesi web (sesi_web.py) seperti peramban dosen.
Parameternya dicocokkan dengan kode Moodle 4.1 (MOODLE_401_STABLE):

    changenumsections.php   courseid wajib; insertsection=0 berarti section baru
                            ditaruh di akhir; numsections adalah banyaknya; butuh
                            hak moodle/course:update dan sesskey. Kalau jumlah
                            akhirnya melampaui batas section kursus (bawaan Moodle
                            52), tidak ada section yang dibuat.
    inplace editable        component "format_<format kursus>" (mis. format_topics),
                            itemtype "sectionname", itemid id section (bukan
                            nomornya), value nama baru. format_topics hanya
                            menerima itemid milik kursus berformat topics, jadi
                            component harus cocok dengan format kursusnya.
    editsection.php         form editsection_form (_qf__editsection_form=1) dengan
                            id, course, sesskey, name, summary_editor[text|format|itemid],
                            dan availabilityconditionsjson. Isiannya dibaca utuh dari
                            form, hanya summary_editor[text] yang diganti, lalu dikirim
                            dengan tombol submitbutton. Berhasil berarti dialihkan ke
                            halaman kursus; form yang tampil lagi berarti ditolak.

Keduanya bawaannya uji coba: rencananya menyebut section yang ada, nama baru,
dan nomor posisinya. Sesudah dikirim, hasilnya diperiksa ulang lewat
core_course_get_contents. Section baru dikenali dari id yang belum ada sebelum
kiriman, jadi nama tidak pernah dipasang ke section lama.
"""

from __future__ import annotations

from collections import Counter
from urllib.parse import urljoin, urlsplit

from aswaya_mcp.aswaya_client import AswayaError, HasilTidakPasti, IsianDitolak, KlienAswaya, periksa_id
from aswaya_mcp.sesi_web import (
    PATH_AJAX,
    SesiWeb,
    cari_form,
    format_dari_halaman,
    isian_form,
    pesan_galat_form,
    sup_dari,
    tombol_form,
)
from aswaya_mcp.teks import teks_dari_html, teks_ke_html
from aswaya_mcp.tulis import FORMAT_HTML_MOODLE, PESAN_UJI_COBA, HasilTulis

PATH_CHANGENUMSECTIONS = "/course/changenumsections.php"
PATH_EDITSECTION = "/course/editsection.php"
ISIAN_RINGKASAN = "summary_editor[text]"
ISIAN_FORMAT_RINGKASAN = "summary_editor[format]"
PENANDA_FORM_SECTION = "_qf__editsection_form"
TOMBOL_SIMPAN = "submitbutton"
CARA_RINGKASAN = ("tambah", "awal", "ganti")
FUNGSI_INPLACE = "core_update_inplace_editable"
ITEMTYPE_NAMA_SECTION = "sectionname"
MAKS_NAMA = 255
MAKS_SECTION_BAWAAN = 52
SESSKEY_DISEMBUNYIKAN = "<sesskey dari sesi web>"


# --- membaca -------------------------------------------------------------------


def bentuk_section(section: dict) -> dict:
    """Satu section: id, nomor, nama, visible, dan jumlah modulnya."""
    return {
        "id": section.get("id"),
        "nomor": section.get("section"),
        "nama": teks_dari_html(section.get("name")),
        "visible": bool(section.get("visible", 1)),
        "jumlah_modul": len(section.get("modules") or []),
    }


def baca_section(klien: KlienAswaya, kursus_id: int) -> list[dict]:
    """Section kursus dari core_course_get_contents, tanpa isi berkas modul supaya ringan."""
    parameter = {"courseid": kursus_id, "options": [{"name": "excludecontents", "value": True}]}
    return [bentuk_section(section) for section in klien.panggil("core_course_get_contents", parameter) or []]


def daftar_section(klien: KlienAswaya, kursus_id: int) -> dict:
    """Section satu kursus: id, nomor, nama, visible, dan jumlah modul.

    `id` adalah section_id untuk ubah_nama_section; `nomor` adalah urutan
    section di halaman kursus (0 untuk bagian umum di atas).
    """
    kursus_id = periksa_id(kursus_id, "kursus_id")
    section = baca_section(klien, kursus_id)
    return {"kursus_id": kursus_id, "url": klien.url_kursus(kursus_id), "jumlah": len(section), "section": section}


def keterangan_kursus(klien: KlienAswaya, kursus_id: int) -> dict:
    """Nama, format, dan opsi format kursus dari core_course_get_courses_by_field; kosong kalau tidak terbaca."""
    if not klien.tersedia("core_course_get_courses_by_field"):
        return {}
    try:
        hasil = klien.panggil("core_course_get_courses_by_field", {"field": "id", "value": kursus_id}) or {}
    except AswayaError:
        return {}
    for kursus in hasil.get("courses") or []:
        if kursus.get("id") == kursus_id:
            return {
                "nama": teks_dari_html(kursus.get("fullname")),
                "format": kursus.get("format") or "",
                "opsi_format": {opsi.get("name"): opsi.get("value") for opsi in kursus.get("courseformatoptions") or []},
            }
    return {}


# --- isian dan rencana ---------------------------------------------------------


def periksa_nama(nama) -> str:
    """Nama section yang spasinya dirapikan; kosong atau lebih dari 255 karakter ditolak."""
    if not isinstance(nama, str):
        raise IsianDitolak(f"Nama section harus berupa teks, bukan {nama!r}")
    nama = " ".join(nama.split())
    if not nama:
        raise IsianDitolak("Nama section tidak boleh kosong")
    if len(nama) > MAKS_NAMA:
        raise IsianDitolak(f"Nama section paling panjang {MAKS_NAMA} karakter, bukan {len(nama)}")
    return nama


def kunci_nama(nama: str | None) -> str:
    """Bentuk pembanding nama: spasi dirapikan, huruf besar dan kecil disamakan."""
    return " ".join((nama or "").split()).casefold()


def periksa_daftar_nama(nama) -> list[str]:
    """Daftar nama section baru; satu teks dianggap satu nama, daftar kosong ditolak."""
    if isinstance(nama, str):
        nama = [nama]
    if not nama:
        raise IsianDitolak("Berikan minimal satu nama, satu nama untuk setiap section baru")
    return [periksa_nama(satu) for satu in nama]


def section_kosong_di_akhir(sections: list[dict]) -> list[dict]:
    """Section tanpa modul yang berderet di ujung kursus (selain section 0), urut nomor."""
    hasil = []
    for satu in sorted(sections, key=lambda s: s["nomor"] or 0, reverse=True):
        if not satu["nomor"] or satu["jumlah_modul"]:
            break
        hasil.append(satu)
    return list(reversed(hasil))


def komponen_format(format_kursus: str) -> str:
    """Nama component inplace editable untuk format kursus ini, mis. 'format_topics'."""
    return f"format_{format_kursus}" if format_kursus else "format_<format kursus>"


def langkah_tambah(klien: KlienAswaya, kursus_id: int, jumlah: int) -> dict:
    """Rencana GET changenumsections.php, dengan sesskey disembunyikan."""
    return {
        "metode": "GET",
        "url": klien.base_url + PATH_CHANGENUMSECTIONS,
        "parameter": {"courseid": kursus_id, "insertsection": 0, "numsections": jumlah, "sesskey": SESSKEY_DISEMBUNYIKAN},
    }


def langkah_ganti_nama(klien: KlienAswaya, komponen: str, itemid, nama: str) -> dict:
    """Rencana POST AJAX core_update_inplace_editable untuk satu section."""
    return {
        "metode": "POST",
        "url": klien.base_url + PATH_AJAX,
        "parameter": {"sesskey": SESSKEY_DISEMBUNYIKAN, "info": FUNGSI_INPLACE},
        "methodname": FUNGSI_INPLACE,
        "args": {"component": komponen, "itemtype": ITEMTYPE_NAMA_SECTION, "itemid": itemid, "value": nama},
    }


def ganti_nama(sesi: SesiWeb, komponen: str, section_id: int, nama: str):
    """Satu panggilan core_update_inplace_editable lewat sesi web."""
    args = {"component": komponen, "itemtype": ITEMTYPE_NAMA_SECTION, "itemid": section_id, "value": nama}
    return sesi.ajax(FUNGSI_INPLACE, args, tulis=True)


def buka_kursus(sesi: SesiWeb, kursus_id: int, format_kursus: str) -> str:
    """Buka halaman kursus lewat sesi web (login dan sesskey), lalu kembalikan format kursusnya.

    Format dari web service didahulukan; kalau kosong, dibaca dari kelas body
    halaman kursus. Tanpa format, component inplace editable tidak bisa
    ditentukan, jadi tidak ada yang dikirim.
    """
    halaman = sesi.halaman("/course/view.php", params={"id": kursus_id})
    format_kursus = format_kursus or format_dari_halaman(halaman.text)
    if not format_kursus:
        raise AswayaError(f"Format kursus {kursus_id} tidak terbaca dari web service maupun halaman kursus; tidak ada yang dikirim")
    return format_kursus


def periksa_ulang(klien: KlienAswaya, kursus_id: int) -> dict[int, dict] | None:
    """Section kursus sesudah kiriman, berkunci id; None kalau tidak bisa dibaca."""
    try:
        return {section["id"]: section for section in baca_section(klien, kursus_id)}
    except AswayaError:
        return None


# --- tambah section --------------------------------------------------------------


def tambah_section(
    klien: KlienAswaya,
    kursus_id: int,
    nama,
    *,
    kirim: bool = False,
    paksa: bool = False,
    sesi: SesiWeb | None = None,
) -> HasilTulis:
    """Tambahkan section baru di akhir kursus, satu per nama, lalu beri namanya. Bawaannya uji coba.

    Nama yang sudah dipakai section lain di kursus itu, atau yang muncul dua
    kali di daftar, ditolak supaya perintah yang tidak sengaja dijalankan dua
    kali tidak menggandakan section; paksa=True melewati pemeriksaan ini.
    Dengan kirim=True dibutuhkan ASWAYA_PASSWORD untuk login web.
    """
    kursus_id = periksa_id(kursus_id, "kursus_id")
    nama_baru = periksa_daftar_nama(nama)
    sekarang = baca_section(klien, kursus_id)
    keterangan = keterangan_kursus(klien, kursus_id)
    format_kursus = keterangan.get("format", "")

    terpakai = {kunci_nama(section["nama"]): section for section in sekarang}
    kembar = [satu for satu in nama_baru if kunci_nama(satu) in terpakai]
    ganda = [satu for satu, jumlah in Counter(kunci_nama(satu) for satu in nama_baru).items() if jumlah > 1]
    peringatan = []
    if (kembar or ganda) and not paksa:
        keterangan_kembar = [f"{satu!r} (sudah ada sebagai section {terpakai[kunci_nama(satu)]['nomor']})" for satu in kembar]
        keterangan_kembar += [f"{satu!r} (muncul lebih dari sekali di daftar)" for satu in ganda]
        raise IsianDitolak(
            "Nama berikut sudah terpakai: " + "; ".join(keterangan_kembar)
            + ". Tidak ada yang dikirim. Ulangi dengan paksa=True (CLI: --paksa) kalau memang ingin menambahkannya."
        )
    if kembar or ganda:
        peringatan.append("Sebagian nama sudah terpakai; section bernama sama tetap ditambahkan karena paksa=True")

    nomor_akhir = max((section["nomor"] or 0 for section in sekarang), default=0)
    rencana = [{"nomor": nomor_akhir + urutan, "nama": satu} for urutan, satu in enumerate(nama_baru, start=1)]
    kosong = section_kosong_di_akhir(sekarang)
    if kosong:
        daftar_kosong = ", ".join(f"{s['nomor']} ({s['nama']!r}, id {s['id']})" for s in kosong)
        peringatan.append(
            f"Kursus sudah berakhir dengan section kosong: {daftar_kosong}. Section baru ditaruh sesudahnya; "
            "kalau section kosong itu yang dimaksud, ganti saja namanya dengan ubah_nama_section"
        )
    if nomor_akhir + len(nama_baru) > MAKS_SECTION_BAWAAN:
        peringatan.append(
            f"Kursus akan berisi {nomor_akhir + len(nama_baru)} section; batas bawaan Moodle {MAKS_SECTION_BAWAAN}. "
            "Kalau batas kursus ini juga segitu, Moodle tidak menambahkan satu pun"
        )
    if "numsections" in keterangan.get("opsi_format", {}):
        peringatan.append(
            "Format kursus ini memakai opsi numsections; section tambahan bisa tidak tampil bagi mahasiswa "
            "sampai jumlahnya disesuaikan di pengaturan kursus"
        )
    if not format_kursus:
        peringatan.append("Format kursus tidak terbaca lewat web service; saat dikirim dibaca dari halaman kursus")

    komponen = komponen_format(format_kursus)
    ringkasan = {
        "kursus_id": kursus_id,
        "kursus": keterangan.get("nama"),
        "format": format_kursus or None,
        "section_sekarang": [{"id": s["id"], "nomor": s["nomor"], "nama": s["nama"]} for s in sekarang],
        "section_baru": rencana,
        "jumlah_baru": len(rencana),
    }
    permintaan = {
        "langkah": [langkah_tambah(klien, kursus_id, len(nama_baru))]
        + [langkah_ganti_nama(klien, komponen, f"<id section nomor {satu['nomor']}>", satu["nama"]) for satu in rencana],
    }
    fungsi = f"{PATH_CHANGENUMSECTIONS.lstrip('/')} + {FUNGSI_INPLACE}"
    if not kirim:
        if not klien.kredensial()[1]:
            peringatan.append("kirim=True butuh ASWAYA_PASSWORD untuk login web; token web service saja tidak cukup")
        return HasilTulis(
            kirim=False, terkirim=False, fungsi=fungsi, ringkasan=ringkasan, permintaan=permintaan,
            peringatan=peringatan, pesan=PESAN_UJI_COBA,
        )

    sesi = sesi or SesiWeb(klien)
    format_kursus = buka_kursus(sesi, kursus_id, format_kursus)
    komponen = komponen_format(format_kursus)
    id_sebelum = {section["id"] for section in sekarang}
    sesi.aksi_get(PATH_CHANGENUMSECTIONS, {"courseid": kursus_id, "insertsection": 0, "numsections": len(nama_baru)})

    sesudah = periksa_ulang(klien, kursus_id)
    if sesudah is None:
        raise HasilTidakPasti(
            "changenumsections.php sudah dijalankan, tetapi daftar section tidak bisa dibaca ulang. Periksa dengan "
            "daftar_section sebelum mencoba lagi."
        )
    baru = sorted((s for s in sesudah.values() if s["id"] not in id_sebelum), key=lambda s: s["nomor"] or 0)
    hasil_nama = []
    for section, satu in zip(baru, nama_baru):
        galat = None
        try:
            ganti_nama(sesi, komponen, section["id"], satu)
        except AswayaError as kegagalan:
            galat = str(kegagalan)
        hasil_nama.append({"id": section["id"], "nomor": section["nomor"], "nama_diminta": satu, "galat": galat})

    akhir = periksa_ulang(klien, kursus_id) or {}
    for entri in hasil_nama:
        entri["nama_sekarang"] = (akhir.get(entri["id"]) or {}).get("nama")
        entri["sesuai"] = kunci_nama(entri["nama_sekarang"]) == kunci_nama(entri["nama_diminta"])
    belum = nama_baru[len(baru):]
    lebih = [s["id"] for s in baru[len(nama_baru):]]
    berhasil = not belum and not lebih and all(entri["sesuai"] for entri in hasil_nama)
    if berhasil:
        pesan = f"{len(baru)} section ditambahkan dan diberi nama; sudah diperiksa ulang lewat core_course_get_contents."
    elif not baru:
        pesan = (
            "Tidak ada section yang bertambah. Kemungkinan jumlahnya melampaui batas section kursus, atau akun ini "
            "tidak boleh mengubah kursus. Tidak ada yang perlu dibatalkan."
        )
    else:
        pesan = (
            f"{len(baru)} dari {len(nama_baru)} section bertambah; lihat `hasil` untuk nama yang belum terpasang. "
            "Periksa dengan daftar_section sebelum mencoba lagi."
        )
    return HasilTulis(
        kirim=True, terkirim=True, fungsi=fungsi, ringkasan={**ringkasan, "format": format_kursus},
        permintaan=permintaan,
        hasil={"section_baru": hasil_nama, "belum_ditambahkan": belum, "section_lain_tanpa_nama": lebih},
        berhasil=berhasil, peringatan=peringatan, pesan=pesan,
    )


# --- ganti nama ----------------------------------------------------------------


def ubah_nama_section(
    klien: KlienAswaya,
    kursus_id: int,
    section_id: int,
    nama: str,
    *,
    kirim: bool = False,
    sesi: SesiWeb | None = None,
) -> HasilTulis:
    """Ganti nama satu section lewat core_update_inplace_editable. Bawaannya uji coba.

    `section_id` adalah id section dari daftar_section, bukan nomor urutnya.
    Section milik kursus lain ditolak sebelum apa pun dikirim. Dengan kirim=True
    dibutuhkan ASWAYA_PASSWORD untuk login web.
    """
    kursus_id = periksa_id(kursus_id, "kursus_id")
    section_id = periksa_id(section_id, "section_id")
    nama = periksa_nama(nama)
    sekarang = baca_section(klien, kursus_id)
    sasaran = next((section for section in sekarang if section["id"] == section_id), None)
    if sasaran is None:
        raise IsianDitolak(
            f"section_id {section_id} bukan section kursus {kursus_id}; lihat daftar_section untuk id yang benar"
        )
    if sasaran["nama"] == nama:
        raise IsianDitolak(f"Section {sasaran['nomor']} sudah bernama {nama!r}; tidak ada yang perlu diubah")
    keterangan = keterangan_kursus(klien, kursus_id)
    format_kursus = keterangan.get("format", "")
    peringatan = []
    if not format_kursus:
        peringatan.append("Format kursus tidak terbaca lewat web service; saat dikirim dibaca dari halaman kursus")
    ringkasan = {
        "kursus_id": kursus_id,
        "kursus": keterangan.get("nama"),
        "format": format_kursus or None,
        "section_id": section_id,
        "nomor": sasaran["nomor"],
        "nama_lama": sasaran["nama"],
        "nama_baru": nama,
    }
    permintaan = {"langkah": [langkah_ganti_nama(klien, komponen_format(format_kursus), section_id, nama)]}
    if not kirim:
        if not klien.kredensial()[1]:
            peringatan.append("kirim=True butuh ASWAYA_PASSWORD untuk login web; token web service saja tidak cukup")
        return HasilTulis(
            kirim=False, terkirim=False, fungsi=FUNGSI_INPLACE, ringkasan=ringkasan, permintaan=permintaan,
            peringatan=peringatan, pesan=PESAN_UJI_COBA,
        )

    sesi = sesi or SesiWeb(klien)
    format_kursus = buka_kursus(sesi, kursus_id, format_kursus)
    jawaban = ganti_nama(sesi, komponen_format(format_kursus), section_id, nama)
    akhir = periksa_ulang(klien, kursus_id)
    nama_sekarang = (akhir or {}).get(section_id, {}).get("nama")
    sesuai = kunci_nama(nama_sekarang) == kunci_nama(nama)
    if akhir is None:
        pesan = "Nama dikirim, tetapi daftar section tidak bisa dibaca ulang; periksa dengan daftar_section."
    elif sesuai:
        pesan = "Nama section sudah diganti; sudah diperiksa ulang lewat core_course_get_contents."
    else:
        pesan = f"Nama dikirim, tetapi section itu sekarang bernama {nama_sekarang!r}; periksa di Aswaya."
    return HasilTulis(
        kirim=True, terkirim=True, fungsi=FUNGSI_INPLACE, ringkasan={**ringkasan, "format": format_kursus},
        permintaan=permintaan,
        hasil={
            "section_id": section_id,
            "nama_sekarang": nama_sekarang,
            "sesuai": sesuai,
            "tampil": teks_dari_html((jawaban or {}).get("displayvalue")) if isinstance(jawaban, dict) else None,
        },
        berhasil=sesuai, peringatan=peringatan, pesan=pesan,
    )


# --- ringkasan section ---------------------------------------------------------


def baca_ringkasan(klien: KlienAswaya, kursus_id: int) -> dict[int, dict]:
    """Section kursus berkunci id, dengan ringkasan HTML (summary) dan formatnya, tanpa modul."""
    parameter = {"courseid": kursus_id, "options": [{"name": "excludemodules", "value": True}]}
    hasil = {}
    for section in klien.panggil("core_course_get_contents", parameter) or []:
        hasil[section.get("id")] = {
            "id": section.get("id"),
            "nomor": section.get("section"),
            "nama": teks_dari_html(section.get("name")),
            "ringkasan": section.get("summary") or "",
            "format_ringkasan": section.get("summaryformat"),
        }
    return hasil


def buka_di_tab_baru(isi_html: str) -> str:
    """Setiap tautan <a href> di isi_html dibuka di tab baru: target="_blank" dan rel="noopener"."""
    sup = sup_dari(isi_html)
    for tautan in sup.find_all("a", href=True):
        tautan["target"] = "_blank"
        rel = list(tautan.get("rel") or [])
        if "noopener" not in rel:
            rel.append("noopener")
        tautan["rel"] = rel
    return str(sup)


def tautan_di(isi_html: str) -> list[str]:
    """Alamat semua tautan <a href> di isi_html, berurutan."""
    return [tautan["href"] for tautan in sup_dari(isi_html).find_all("a", href=True)]


def gabung_ringkasan(lama: str, tambahan: str, *, di_awal: bool = False) -> str:
    """Ringkasan lama dengan tambahan di akhir (atau di awal), dipisah satu baris baru seperti editor Moodle."""
    lama = (lama or "").strip()
    if not lama:
        return tambahan
    return f"{tambahan}\r\n{lama}" if di_awal else f"{lama}\r\n{tambahan}"


def kunci_html(isi: str | None) -> str:
    """Bentuk pembanding HTML: akhir baris dan spasi di ujung disamakan."""
    return (isi or "").replace("\r\n", "\n").strip()


def ubah_ringkasan_section(
    klien: KlienAswaya,
    kursus_id: int,
    section_id: int,
    isi: str,
    *,
    cara: str = "tambah",
    bentuk: str = "teks",
    tab_baru: bool = True,
    kirim: bool = False,
    paksa: bool = False,
    sesi: SesiWeb | None = None,
) -> HasilTulis:
    """Tambahkan isi ke ringkasan (deskripsi) satu section, atau ganti seluruhnya. Bawaannya uji coba.

    `isi` berupa teks biasa (baris kosong memisahkan paragraf, alamat http(s)
    menjadi tautan) atau HTML dengan bentuk="html". cara="tambah" menaruhnya di
    akhir ringkasan yang ada, cara="awal" di bagian paling atasnya, dan
    cara="ganti" menggantikan seluruh ringkasan. Dengan tab_baru=True setiap
    tautan di isi baru dibuka di tab baru. Kalau semua tautan di isi baru sudah
    ada di ringkasan, cara="tambah" dan cara="awal" ditolak kecuali
    paksa=True, supaya perintah yang terulang tidak menggandakan tautan. Dengan
    kirim=True dibutuhkan ASWAYA_PASSWORD untuk login web.
    """
    kursus_id = periksa_id(kursus_id, "kursus_id")
    section_id = periksa_id(section_id, "section_id")
    if cara not in CARA_RINGKASAN:
        raise IsianDitolak(f"cara harus 'tambah', 'awal', atau 'ganti', bukan {cara!r}")
    if bentuk not in ("teks", "html"):
        raise IsianDitolak(f"bentuk harus 'teks' atau 'html', bukan {bentuk!r}")
    if not isinstance(isi, str) or not isi.strip():
        raise IsianDitolak("Isi ringkasan tidak boleh kosong")
    isi_html = teks_ke_html(isi) if bentuk == "teks" else isi.strip()
    if tab_baru:
        isi_html = buka_di_tab_baru(isi_html)

    sekarang = baca_ringkasan(klien, kursus_id)
    sasaran = sekarang.get(section_id)
    if sasaran is None:
        raise IsianDitolak(
            f"section_id {section_id} bukan section kursus {kursus_id}; lihat daftar_section untuk id yang benar"
        )
    lama = sasaran["ringkasan"]
    tautan_baru = tautan_di(isi_html)
    sudah_ada = [alamat for alamat in tautan_baru if alamat in lama]
    peringatan = []
    if cara != "ganti" and tautan_baru and len(sudah_ada) == len(tautan_baru) and not paksa:
        raise IsianDitolak(
            "Semua tautan di isi baru sudah ada di ringkasan section ini: " + ", ".join(sudah_ada)
            + ". Tidak ada yang dikirim. Ulangi dengan paksa=True (CLI: --paksa) kalau memang ingin menambahkannya lagi."
        )
    if sudah_ada:
        peringatan.append("Sebagian tautan sudah ada di ringkasan: " + ", ".join(sudah_ada))
    if sasaran["format_ringkasan"] not in (None, FORMAT_HTML_MOODLE):
        peringatan.append(
            f"Ringkasan lama berformat {sasaran['format_ringkasan']}, bukan HTML; editor Aswaya menyimpannya sebagai HTML"
        )
    baru = gabung_ringkasan(lama, isi_html, di_awal=cara == "awal") if cara != "ganti" else isi_html
    keterangan = keterangan_kursus(klien, kursus_id)
    ringkasan = {
        "kursus_id": kursus_id,
        "kursus": keterangan.get("nama"),
        "section_id": section_id,
        "nomor": sasaran["nomor"],
        "nama": sasaran["nama"],
        "cara": cara,
        "isi_baru": isi_html,
        "tautan_baru": tautan_baru,
        "ringkasan_lama": lama,
        "ringkasan_baru": baru,
    }
    permintaan = {
        "langkah": [
            {"metode": "GET", "url": klien.base_url + PATH_EDITSECTION, "parameter": {"id": section_id, "sr": 0}},
            {
                "metode": "POST",
                "url": klien.base_url + PATH_EDITSECTION,
                "isian_diubah": {ISIAN_RINGKASAN: baru, ISIAN_FORMAT_RINGKASAN: FORMAT_HTML_MOODLE},
                "isian_lain": "dibaca apa adanya dari form editsection (id, course, sesskey, name, "
                "summary_editor[itemid], availabilityconditionsjson), lalu dikirim dengan tombol submitbutton",
            },
        ],
    }
    fungsi = PATH_EDITSECTION.lstrip("/")
    if not kirim:
        if not klien.kredensial()[1]:
            peringatan.append("kirim=True butuh ASWAYA_PASSWORD untuk login web; token web service saja tidak cukup")
        return HasilTulis(
            kirim=False, terkirim=False, fungsi=fungsi, ringkasan=ringkasan, permintaan=permintaan,
            peringatan=peringatan, pesan=PESAN_UJI_COBA,
        )

    sesi = sesi or SesiWeb(klien)
    halaman = sesi.halaman(PATH_EDITSECTION, params={"id": section_id, "sr": 0})
    form = cari_form(halaman.text, PATH_EDITSECTION)
    if form is None:
        raise AswayaError(f"Form edit section {section_id} tidak ditemukan; tidak ada yang dikirim")
    isian = isian_form(form)
    nilai = dict(isian)
    if nilai.get(PENANDA_FORM_SECTION) != "1" or nilai.get("course") != str(kursus_id) or ISIAN_RINGKASAN not in nilai:
        raise AswayaError(
            f"Form di {PATH_EDITSECTION} bukan form edit section {section_id} kursus {kursus_id}; tidak ada yang dikirim"
        )
    if cara != "ganti" and kunci_html(nilai[ISIAN_RINGKASAN]) != kunci_html(lama):
        # ringkasan berubah sejak dibaca; tambahan ditempel ke isi form yang paling baru
        peringatan.append("Ringkasan berubah sejak uji coba; tambahan ditempel ke ringkasan terbaru")
        baru = gabung_ringkasan(nilai[ISIAN_RINGKASAN], isi_html, di_awal=cara == "awal")
    ganti = {ISIAN_RINGKASAN: baru, ISIAN_FORMAT_RINGKASAN: str(FORMAT_HTML_MOODLE)}
    isian = [(kunci, ganti.get(kunci, isi_lama)) for kunci, isi_lama in isian]
    tombol = tombol_form(form, TOMBOL_SIMPAN)
    if tombol is not None:
        isian.append(tombol)
    jawaban = sesi.kirim_form(urljoin(halaman.url, form.get("action") or PATH_EDITSECTION), isian, referer=halaman.url)
    if urlsplit(jawaban.url).path.endswith(PATH_EDITSECTION):
        galat = pesan_galat_form(jawaban.text)
        raise IsianDitolak(
            f"Aswaya menampilkan lagi form edit section{f' dengan pesan: {galat}' if galat else ''}; ringkasan tidak berubah."
        )

    try:
        akhir = baca_ringkasan(klien, kursus_id).get(section_id)
    except AswayaError:
        akhir = None
    ringkasan_sekarang = (akhir or {}).get("ringkasan")
    sesuai = akhir is not None and kunci_html(ringkasan_sekarang) == kunci_html(baru)
    if akhir is None:
        pesan = "Form tersimpan, tetapi ringkasan tidak bisa dibaca ulang; periksa di Aswaya sebelum mencoba lagi."
    elif sesuai:
        pesan = "Ringkasan section sudah diperbarui; sudah diperiksa ulang lewat core_course_get_contents."
    else:
        pesan = "Form tersimpan, tetapi ringkasan yang terbaca berbeda dari yang dikirim; periksa di Aswaya."
    return HasilTulis(
        kirim=True, terkirim=True, fungsi=fungsi, ringkasan={**ringkasan, "ringkasan_baru": baru},
        permintaan=permintaan,
        hasil={
            "section_id": section_id,
            "ringkasan_sekarang": ringkasan_sekarang,
            "sesuai": sesuai,
            "tautan_ada": [alamat for alamat in tautan_baru if alamat in (ringkasan_sekarang or "")],
            "url_kursus": klien.url_kursus(kursus_id),
        },
        berhasil=sesuai, peringatan=peringatan, pesan=pesan,
    )
