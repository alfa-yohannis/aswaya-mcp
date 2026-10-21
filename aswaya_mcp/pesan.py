"""Pesan pribadi Moodle lewat core_message_send_instant_messages. Bawaannya uji coba.

Pratinjau menyebut nama setiap penerima (core_user_get_users_by_field, kalau
tersedia), supaya pemakai bisa memastikan id-nya benar sebelum mengirim.
Moodle melaporkan hasil per penerima: msgid -1 berarti pesan ke penerima itu
gagal, mis. karena pengaturan privasi penerima. Kegagalan sebagian membuat
`berhasil` bernilai False tanpa membatalkan pesan yang sudah terkirim.
"""

from __future__ import annotations

from aswaya_mcp.aswaya_client import AswayaError, IsianDitolak, KlienAswaya, periksa_id
from aswaya_mcp.teks import teks_dari_html
from aswaya_mcp.tulis import FORMAT_HTML_MOODLE, BentukIsi, HasilTulis, isi_sebagai_html, jalankan_tulis


def periksa_penerima(user_ids) -> list[int]:
    """Daftar id penerima tanpa duplikat, urut seperti diberikan; daftar kosong ditolak."""
    if isinstance(user_ids, (int, str)):
        user_ids = [user_ids]
    if not user_ids:
        raise IsianDitolak("user_ids tidak boleh kosong")
    hasil: list[int] = []
    for nilai in user_ids:
        nomor = periksa_id(nilai, "user_id")
        if nomor not in hasil:
            hasil.append(nomor)
    return hasil


def nama_penerima(klien: KlienAswaya, user_ids: list[int]) -> dict[int, str] | None:
    """Nama lengkap tiap id penerima; None kalau fungsi pencariannya tidak tersedia."""
    if not klien.tersedia("core_user_get_users_by_field"):
        return None
    try:
        pengguna = klien.panggil("core_user_get_users_by_field", {"field": "id", "values": user_ids}) or []
    except AswayaError:
        return None
    return {int(satu["id"]): satu.get("fullname") for satu in pengguna if "id" in satu}


def hasil_per_penerima(hasil, user_ids: list[int]) -> list[dict]:
    """Status kiriman tiap penerima dari jawaban Moodle, urut seperti permintaannya."""
    baris = []
    for nomor, user_id in enumerate(user_ids):
        satu = hasil[nomor] if isinstance(hasil, list) and nomor < len(hasil) else {}
        msgid = satu.get("msgid", -1)
        baris.append({
            "user_id": user_id,
            "terkirim": isinstance(msgid, int) and msgid > 0,
            "msgid": msgid,
            "galat": satu.get("errormessage") or None,
        })
    return baris


def kirim_pesan(
    klien: KlienAswaya,
    user_ids,
    teks: str,
    *,
    kirim: bool = False,
    bentuk: BentukIsi = "teks",
) -> HasilTulis:
    """Kirim satu pesan pribadi yang sama ke beberapa pengguna. Bawaannya uji coba.

    Penerima yang tidak dikenal Moodle ditolak sebelum apa pun dikirim. Sesudah
    kiriman, `hasil` berisi status per penerima.
    """
    penerima = periksa_penerima(user_ids)
    teks_html = isi_sebagai_html(teks, bentuk, "teks")
    nama = nama_penerima(klien, penerima)
    peringatan = []
    if nama is not None:
        tidak_dikenal = [user_id for user_id in penerima if user_id not in nama]
        if tidak_dikenal:
            raise IsianDitolak(f"user_id tidak dikenal Aswaya: {', '.join(map(str, tidak_dikenal))}")
    else:
        peringatan.append("Nama penerima tidak bisa diperiksa karena core_user_get_users_by_field tidak tersedia")

    parameter = {
        "messages": [
            {"touserid": user_id, "text": teks_html, "textformat": FORMAT_HTML_MOODLE, "clientmsgid": f"aswaya-{nomor}"}
            for nomor, user_id in enumerate(penerima)
        ]
    }
    ringkasan = {
        "penerima": [{"user_id": user_id, "nama": (nama or {}).get(user_id)} for user_id in penerima],
        "jumlah_penerima": len(penerima),
        "teks": teks_dari_html(teks_html),
    }
    hasil = jalankan_tulis(
        klien, "core_message_send_instant_messages", parameter, ringkasan,
        kirim=kirim, peringatan=peringatan, pesan_terkirim="Pesan terkirim ke semua penerima.",
    )
    if hasil.terkirim:
        per_penerima = hasil_per_penerima(hasil.hasil, penerima)
        hasil.hasil = per_penerima
        gagal = [baris for baris in per_penerima if not baris["terkirim"]]
        if gagal:
            hasil.berhasil = False
            hasil.pesan = (
                f"Pesan terkirim ke {len(per_penerima) - len(gagal)} dari {len(per_penerima)} penerima; "
                "lihat `hasil` untuk yang gagal. Jangan kirim ulang ke penerima yang sudah berhasil."
            )
    return hasil
