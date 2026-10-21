"""Tenggat: kegiatan yang menunggu tindakan dari kalender Moodle (action events).

Dipakai core_calendar_get_action_events_by_timesort, atau
core_calendar_get_action_events_by_course kalau kursusnya disebut. Isinya
kegiatan yang menunggu tindakan akun ini: bagi mahasiswa tenggat pengumpulan,
bagi dosen antara lain tugas yang menunggu dinilai beserta jumlahnya.

Jendela waktunya mulai pukul 00.00 hari ini (zona waktu setelan) sampai `hari`
hari ke depan. Moodle membatasi 50 kegiatan per permintaan, jadi dibaca per
halaman lewat aftereventid.
"""

from __future__ import annotations

import time
from datetime import datetime

from aswaya_mcp.aswaya_client import IsianDitolak, KlienAswaya, periksa_id
from aswaya_mcp.konfigurasi import zona_waktu
from aswaya_mcp.teks import teks_dari_html, waktu_iso

BATAS_PER_PERMINTAAN = 50
MAKS_HALAMAN = 10
HARI_BAWAAN = 30
MAKS_HARI = 366


def awal_hari_ini(sekarang: float) -> int:
    """Waktu Unix pukul 00.00 hari ini di zona waktu setelan."""
    hari_ini = datetime.fromtimestamp(sekarang, zona_waktu()).replace(hour=0, minute=0, second=0, microsecond=0)
    return int(hari_ini.timestamp())


def bentuk_kegiatan(kegiatan: dict) -> dict:
    """Satu kegiatan kalender dalam bentuk ringkas."""
    kursus = kegiatan.get("course") or {}
    tindakan = kegiatan.get("action") or {}
    return {
        "id": kegiatan.get("id"),
        "nama": teks_dari_html(kegiatan.get("name")),
        "waktu": waktu_iso(kegiatan.get("timesort") or kegiatan.get("timestart")),
        "kursus_id": kursus.get("id"),
        "kursus": teks_dari_html(kursus.get("fullname")) or None,
        "modul": kegiatan.get("modulename"),
        "aktivitas": teks_dari_html(kegiatan.get("activityname")) or None,
        "jenis": kegiatan.get("eventtype"),
        "tindakan": teks_dari_html(tindakan.get("name")) or None,
        "jumlah_item": tindakan.get("itemcount"),
        "bisa_ditindak": tindakan.get("actionable"),
        "lewat": bool(kegiatan.get("overdue")),
        "url": kegiatan.get("url") or tindakan.get("url"),
    }


def tenggat(klien: KlienAswaya, hari: int = HARI_BAWAAN, kursus_id: int | None = None, *, sekarang: float | None = None) -> dict:
    """Kegiatan yang menunggu tindakan dari hari ini sampai `hari` hari ke depan, terdekat dulu.

    `kursus_id` membatasi ke satu kursus. `jumlah_item` berisi banyaknya hal
    yang menunggu, mis. pengumpulan yang belum dinilai.
    """
    try:
        hari = int(hari)
    except (TypeError, ValueError):
        raise IsianDitolak(f"hari harus berupa angka, bukan {hari!r}") from None
    if not 1 <= hari <= MAKS_HARI:
        raise IsianDitolak(f"hari harus antara 1 dan {MAKS_HARI}, bukan {hari}")
    detik_sekarang = time.time() if sekarang is None else sekarang
    dari = awal_hari_ini(detik_sekarang)
    sampai = int(detik_sekarang + hari * 86400)

    if kursus_id:
        fungsi = "core_calendar_get_action_events_by_course"
        dasar = {"courseid": periksa_id(kursus_id, "kursus_id")}
    else:
        fungsi = "core_calendar_get_action_events_by_timesort"
        dasar = {"limittononsuspendedevents": True}

    kegiatan: list[dict] = []
    setelah = 0
    for _ in range(MAKS_HALAMAN):
        parameter = {**dasar, "timesortfrom": dari, "timesortto": sampai, "aftereventid": setelah, "limitnum": BATAS_PER_PERMINTAAN}
        hasil = klien.panggil(fungsi, parameter) or {}
        baris = hasil.get("events") or []
        kegiatan.extend(baris)
        if len(baris) < BATAS_PER_PERMINTAAN:
            break
        setelah = hasil.get("lastid") or baris[-1].get("id") or 0
        if not setelah:
            break
    return {
        "dari": waktu_iso(dari),
        "sampai": waktu_iso(sampai),
        "kursus_id": int(kursus_id) if kursus_id else None,
        "jumlah": len(kegiatan),
        "kegiatan": [bentuk_kegiatan(satu) for satu in kegiatan],
    }
