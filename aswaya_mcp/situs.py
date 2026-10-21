"""Cek akses dan konfigurasi publik situs, dipakai bersama CLI, REST API, dan MCP.

`cek_login()` memastikan token bisa dipakai lewat core_webservice_get_site_info
dan meringkas hasilnya. Kalau gagal, `diagnosis()` membaca konfigurasi publik
tanpa login (tool_mobile_get_public_config) supaya pesannya bisa membedakan
situs yang sedang dipelihara, layanan mobile yang dimatikan, dan kredensial
yang salah.
"""

from __future__ import annotations

from aswaya_mcp.aswaya_client import AswayaError, KlienAswaya
from aswaya_mcp.konfigurasi import berkas_token
from aswaya_mcp.teks import teks_dari_html

JENIS_LOGIN = {1: "di dalam aplikasi (username dan password)", 2: "lewat peramban", 3: "lewat peramban tertanam"}


def cek_login(klien: KlienAswaya, *, login_ulang: bool = False) -> dict:
    """Nama situs, pemakai, userid, release Moodle, dan jumlah fungsi yang boleh dipakai token.

    `login_ulang=True` memaksa login dengan password walaupun ada token di
    setelan atau cache, mis. setelah password diganti.
    """
    if login_ulang:
        klien.login()
    info = klien.info_situs(segarkan=True)
    # kunci cache memakai username yang dipakai login (bisa berupa email), bukan username Moodle
    username_login = klien.kredensial()[0]
    cache = berkas_token(klien.base_url, username_login) if klien.pakai_cache and username_login else None
    return {
        "situs": teks_dari_html(info.get("sitename")),
        "url": info.get("siteurl") or klien.base_url,
        "nama": info.get("fullname"),
        "username": info.get("username"),
        "userid": info.get("userid"),
        "release": info.get("release"),
        "versi": info.get("version"),
        "jumlah_fungsi": len(info.get("functions") or []),
        "sumber_token": klien.sumber_token,
        "cache_token": str(cache) if cache is not None and cache.is_file() else None,
    }


def ringkas_publik(konfigurasi: dict) -> dict:
    """Bagian konfigurasi publik yang berguna untuk diagnosis."""
    jenis = konfigurasi.get("typeoflogin")
    return {
        "situs": teks_dari_html(konfigurasi.get("sitename")),
        "url": konfigurasi.get("wwwroot"),
        "web_service_aktif": bool(konfigurasi.get("enablewebservices")),
        "layanan_mobile_aktif": bool(konfigurasi.get("enablemobilewebservice")),
        "pemeliharaan": bool(konfigurasi.get("maintenanceenabled")),
        "jenis_login": JENIS_LOGIN.get(jenis, jenis),
        "login_dengan_email": bool(konfigurasi.get("authloginviaemail")),
    }


def publik(klien: KlienAswaya) -> dict:
    """Konfigurasi publik situs tanpa login: ringkasannya dan isi mentahnya."""
    konfigurasi = klien.konfigurasi_publik()
    return {**ringkas_publik(konfigurasi), "mentah": konfigurasi}


def diagnosis(klien: KlienAswaya | None) -> dict | None:
    """Ringkasan konfigurasi publik untuk menjelaskan login yang gagal; None kalau situs pun tidak terjangkau."""
    if klien is None:
        return None
    try:
        return ringkas_publik(klien.konfigurasi_publik())
    except AswayaError:
        return None
