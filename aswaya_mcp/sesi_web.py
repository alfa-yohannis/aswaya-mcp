"""Sesi web Moodle: login lewat halaman, cookie MoodleSession, sesskey, dan AJAX.

Layanan moodle_mobile_app tidak memuat fungsi untuk membuat section. Untuk aksi
seperti itu paket ini juga bisa masuk lewat halaman login, seperti peramban:

    GET  /login/index.php            logintoken dari form id="login"
    POST /login/index.php            anchor, logintoken, username, password
                                     -> dialihkan ke ?testsession=<userid>, lalu ke beranda
    GET  halaman mana pun            M.cfg.sesskey dibaca dari halaman itu
    POST /lib/ajax/service.php?sesskey=..&info=<methodname>
                                     [{"index": 0, "methodname": ..., "args": {...}}]
                                     -> [{"error": false, "data": ...}] atau
                                        [{"error": true, "exception": {"errorcode", "message"}}]

Menurut pemeriksaan pemakai pada Oktober 2026, halaman login Aswaya tidak memuat
captcha dan isiannya username, password, dan logintoken. Kalau suatu saat ada
captcha (reCAPTCHA, hCaptcha, Turnstile, dan sejenisnya), login dihentikan
dengan pesan jelas dan captcha-nya tidak pernah dicoba dijawab. Hal yang sama
berlaku untuk autentikasi multi-faktor, persetujuan kebijakan situs, dan
paksaan ganti password; semuanya diselesaikan pemakai sendiri lewat peramban.

Password hanya dikirim dalam POST ke /login/index.php di host Aswaya, tidak
pernah dicetak, dan disamarkan dari setiap pesan galat. Cookie sesinya disimpan
di cache (sesi-*.json, izin 0600; lihat konfigurasi.py) supaya login tidak
diulang setiap kali. sesskey tidak disimpan, selalu dibaca ulang dari halaman.
Login yang gagal tidak pernah diulang otomatis, karena Moodle bisa mengunci akun
setelah beberapa kali gagal. Pengalihan ke host lain tidak diikuti.
"""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from aswaya_mcp.aswaya_client import (
    PESAN_TIDAK_PASTI,
    AlamatDitolak,
    AswayaError,
    HasilTidakPasti,
    KlienAswaya,
    LoginDitolak,
    MoodleError,
    baca_json,
    batas_detik,
    maks_pengalihan,
    samarkan,
)
from aswaya_mcp.konfigurasi import KonfigurasiError, baca_cache, buat_sesi_http, hapus_cache, simpan_cache

PATH_LOGIN = "/login/index.php"
PATH_AJAX = "/lib/ajax/service.php"
PATH_PEMANASAN = "/my/"
JENIS_CACHE = "sesi"

POLA_SESSKEY = re.compile(r'"sesskey"\s*:\s*"([A-Za-z0-9]+)"')
POLA_SESSKEY_INPUT = re.compile(r'name="sesskey"[^>]*value="([A-Za-z0-9]+)"')
# potongan nama yang menandai captcha: recaptcha, g-recaptcha, hcaptcha, h-captcha, cf-turnstile
KATA_CAPTCHA = ("captcha", "turnstile")
JENIS_TANPA_NILAI = frozenset({"submit", "button", "reset", "image", "file"})

# halaman tempat Moodle mendaratkan pemakai yang harus menyelesaikan sesuatu dulu
HAMBATAN_LOGIN = {
    "/admin/tool/mfa/": "Akun ini memakai autentikasi multi-faktor; login web otomatis tidak didukung",
    "/login/change_password.php": "Aswaya meminta password diganti dulu; lakukan lewat peramban",
    "/user/policy.php": "Ada kebijakan situs yang harus disetujui dulu lewat peramban",
    "/admin/tool/policy/": "Ada kebijakan situs yang harus disetujui dulu lewat peramban",
    "/user/edit.php": "Aswaya meminta profil dilengkapi dulu; lakukan lewat peramban",
}
# errorcode AJAX yang berarti sesi web atau sesskey-nya tidak berlaku; dilempar
# sebelum fungsinya dijalankan, jadi aman diulang sesudah login ulang
KODE_SESI_HABIS = frozenset({"invalidsesskey", "servicerequireslogin", "requireloginerror"})


class LoginWebTerhalang(AswayaError):
    """Login lewat halaman terhalang captcha, MFA, kebijakan situs, atau paksaan ganti password."""


@dataclass
class FormLoginWeb:
    """Form login Moodle yang dibaca dari halamannya. Tidak pernah memuat kredensial."""

    action: str
    isian_bawaan: dict[str, str] = field(default_factory=dict)


def sup_dari(html: str) -> BeautifulSoup:
    """HTML sebagai BeautifulSoup dengan pengurai bawaan Python."""
    return BeautifulSoup(html or "", "html.parser")


def cari_form_login(sup: BeautifulSoup):
    """Form login utama (id="login"); form tamu (id="guestlogin") dilewati."""
    form = sup.find("form", id="login")
    if form is not None:
        return form
    for calon in sup.find_all("form"):
        if calon.get("id") != "guestlogin" and calon.find("input", attrs={"type": "password"}) is not None:
            return calon
    return None


def teks_atribut(nilai) -> str:
    """Nilai atribut sebagai teks huruf kecil; atribut class berupa daftar digabung."""
    return (" ".join(nilai) if isinstance(nilai, list) else str(nilai or "")).lower()


def tanda_captcha(sup: BeautifulSoup, form) -> str:
    """Penanda captcha di form login atau skrip halaman; "" kalau tidak ada."""
    for elemen in form.find_all(True):
        if elemen.has_attr("data-sitekey"):
            return "data-sitekey"
        for atribut in ("class", "id", "name"):
            teks = teks_atribut(elemen.get(atribut))
            if any(kata in teks for kata in KATA_CAPTCHA):
                return teks
    for elemen in sup.find_all(["script", "iframe"], src=True):
        if any(kata in elemen["src"].lower() for kata in KATA_CAPTCHA):
            return elemen["src"]
    return ""


def baca_form_login(html: str, url_halaman: str) -> FormLoginWeb:
    """Action dan isian bawaan form login. Captcha dan form yang berubah ditolak sebelum apa pun dikirim."""
    sup = sup_dari(html)
    form = cari_form_login(sup)
    if form is None:
        raise AswayaError(f"Form login tidak ditemukan di {url_halaman}")
    captcha = tanda_captcha(sup, form)
    if captcha:
        raise LoginWebTerhalang(
            f"Halaman login Aswaya memuat captcha ({captcha}). Login otomatis dihentikan dan captcha tidak "
            "dicoba dijawab; lakukan langkah ini lewat peramban."
        )
    if (form.get("method") or "get").lower() != "post":
        raise AswayaError("Form login tidak memakai POST, jadi kredensial tidak dikirim")
    nama_isian = {masukan.get("name") for masukan in form.find_all("input") if masukan.get("name")}
    if not {"username", "password"} <= nama_isian:
        raise AswayaError("Form login Aswaya tidak lagi memuat isian username dan password; tidak ada yang dikirim")
    isian = {}
    for masukan in form.find_all("input"):
        nama = masukan.get("name")
        jenis = (masukan.get("type") or "text").lower()
        if not nama or nama in ("username", "password") or jenis in JENIS_TANPA_NILAI:
            continue
        if jenis in ("checkbox", "radio") and not masukan.has_attr("checked"):
            continue
        isian[nama] = masukan.get("value", "")
    return FormLoginWeb(action=urljoin(url_halaman, form.get("action") or url_halaman), isian_bawaan=isian)


def sesskey_dari(html: str) -> str:
    """sesskey dari M.cfg di halaman, atau dari isian tersembunyi; "" kalau tidak ada."""
    cocok = POLA_SESSKEY.search(html or "") or POLA_SESSKEY_INPUT.search(html or "")
    return cocok.group(1) if cocok else ""


def kelas_body(html: str) -> list[str]:
    """Kelas CSS elemen <body>, mis. ['format-topics', 'course-5026', 'notloggedin']."""
    body = sup_dari(html).find("body")
    kelas = body.get("class") if body is not None else None
    return list(kelas or [])


def format_dari_halaman(html: str) -> str:
    """Format kursus dari kelas body halaman kursus ('format-topics' -> 'topics'); "" kalau tidak ada."""
    for kelas in kelas_body(html):
        if kelas.startswith("format-") and len(kelas) > len("format-"):
            return kelas[len("format-"):]
    return ""


def pesan_galat_login(html: str) -> str:
    """Pesan galat di halaman login (.alert-danger, #loginerrormessage), digabung jadi satu baris."""
    sup = sup_dari(html)
    hasil = []
    for elemen in sup.select(".alert-danger, #loginerrormessage, .loginerrors"):
        teks = " ".join(elemen.get_text(" ").split())[:200]
        if teks and teks not in hasil:
            hasil.append(teks)
    return "; ".join(hasil)


class SesiWeb:
    """Sesi web Aswaya milik pemakai klien `klien`, untuk aksi yang tidak dibuka layanan web service.

    Username dan password diambil dari klien itu (argumen atau setelan); token
    web service tidak bisa dipakai untuk login lewat halaman. Membuat objek ini
    belum menghubungi Aswaya.
    """

    def __init__(self, klien: KlienAswaya, *, pakai_cache: bool | None = None):
        """Siapkan sesi tanpa login; cookie dari cache baru dimuat saat halaman pertama diminta."""
        self.klien = klien
        self.base_url = klien.base_url
        self.pakai_cache = klien.pakai_cache if pakai_cache is None else pakai_cache
        self.sesi_http = buat_sesi_http()
        self.sesskey = ""
        self.sudah_masuk = False
        self.jumlah_login = 0
        self._cookie_dimuat = False
        # login ulang dan permintaan tidak boleh bersilangan antar-thread
        self._kunci = threading.RLock()

    def __repr__(self) -> str:
        """Ringkasan tanpa kredensial, cookie, maupun sesskey."""
        return f"SesiWeb(base_url={self.base_url!r}, sudah_masuk={self.sudah_masuk})"

    # --- kredensial, alamat, dan permintaan ---------------------------------

    def kredensial(self) -> tuple[str, str]:
        """Username dan password untuk login web; KonfigurasiError kalau salah satunya kosong."""
        username, password = self.klien.kredensial()
        kurang = [nama for nama, nilai in (("ASWAYA_USERNAME", username), ("ASWAYA_PASSWORD", password)) if not nilai]
        if kurang:
            raise KonfigurasiError(
                f"Sesi web Aswaya butuh {', '.join(kurang)}; token web service tidak bisa dipakai untuk login "
                "lewat halaman. Isi di .env, lalu coba lagi."
            )
        return username, password

    def rahasia(self) -> tuple[str, ...]:
        """Nilai yang harus disamarkan dari pesan galat."""
        return (self.klien.kredensial()[1], self.sesskey)

    def alamat_lengkap(self, path_atau_url: str) -> str:
        """URL penuh di bawah Aswaya. Path diawali / ditambahkan ke alamat situs; host lain ditolak."""
        teks = (path_atau_url or "").strip()
        alamat = self.base_url + teks if teks.startswith("/") else urljoin(self.base_url + "/", teks)
        bagian, dasar = urlsplit(alamat), urlsplit(self.base_url)
        if (
            bagian.scheme != "https"
            or bagian.netloc.lower() != dasar.netloc.lower()
            or not (bagian.path + "/").startswith(dasar.path.rstrip("/") + "/")
        ):
            raise AlamatDitolak(f"{path_atau_url!r} berada di luar Aswaya ({self.base_url}); tidak diikuti")
        return alamat

    def minta(
        self,
        metode: str,
        path_atau_url: str,
        *,
        params: dict | None = None,
        data: dict | None = None,
        json_badan: Any = None,
        headers: dict | None = None,
    ):
        """Kirim satu permintaan dan ikuti pengalihannya selama masih di Aswaya, sebagai GET seperti peramban."""
        alamat = self.alamat_lengkap(path_atau_url)
        for _ in range(maks_pengalihan() + 1):
            try:
                jawaban = self.sesi_http.request(
                    metode, alamat, params=params, data=data, json=json_badan, headers=headers,
                    timeout=batas_detik(), allow_redirects=False,
                )
            except requests.RequestException as galat:
                raise AswayaError(f"Permintaan ke {alamat} gagal: {samarkan(str(galat), *self.rahasia())}") from None
            if not jawaban.is_redirect:
                return jawaban
            if jawaban.status_code not in (301, 302, 303):
                raise AswayaError(f"Pengalihan HTTP {jawaban.status_code} dari {alamat} tidak diikuti")
            alamat = self.alamat_lengkap(urljoin(alamat, jawaban.headers.get("Location", "")))
            metode, params, data, json_badan = "GET", None, None, None
        raise AswayaError(f"Terlalu banyak pengalihan dari {path_atau_url}")

    # --- cookie --------------------------------------------------------------

    def muat_cookie(self) -> None:
        """Pasang cookie sesi dari cache, sekali saja per objek."""
        if self._cookie_dimuat:
            return
        self._cookie_dimuat = True
        username = self.klien.kredensial()[0]
        if not (self.pakai_cache and username):
            return
        host = urlsplit(self.base_url).hostname or ""
        for cookie in (baca_cache(JENIS_CACHE, self.base_url, username) or {}).get("cookies", []):
            if cookie.get("name") and cookie.get("value"):
                self.sesi_http.cookies.set(
                    cookie["name"], cookie["value"], domain=cookie.get("domain") or host, path=cookie.get("path") or "/"
                )

    def simpan_cookie(self) -> None:
        """Simpan cookie host Aswaya ke cache berizin 0600, kalau diizinkan."""
        username = self.klien.kredensial()[0]
        if not (self.pakai_cache and username):
            return
        host = (urlsplit(self.base_url).hostname or "").lower()
        cookies = [
            {"name": cookie.name, "value": cookie.value, "domain": cookie.domain, "path": cookie.path}
            for cookie in self.sesi_http.cookies
            if host == cookie.domain.lstrip(".").lower() or host.endswith("." + cookie.domain.lstrip(".").lower())
        ]
        if cookies:
            simpan_cache(JENIS_CACHE, self.base_url, username, {"cookies": cookies})

    def lupakan(self) -> None:
        """Buang cookie dan sesskey di memori maupun di cache."""
        with self._kunci:
            self.sesi_http.cookies.clear()
            self.sesskey, self.sudah_masuk = "", False
            username = self.klien.kredensial()[0]
            if username:
                hapus_cache(JENIS_CACHE, self.base_url, username)

    # --- login dan halaman ---------------------------------------------------

    def di_halaman_login(self, jawaban) -> bool:
        """Apakah jawaban ini berakhir di halaman login."""
        return urlsplit(jawaban.url).path.endswith(PATH_LOGIN)

    def belum_masuk(self, jawaban) -> bool:
        """Tanda sesi tidak berlaku: mendarat di halaman login, atau body berkelas notloggedin."""
        return self.di_halaman_login(jawaban) or "notloggedin" in kelas_body(jawaban.text)

    def periksa_hambatan(self, jawaban) -> None:
        """Tolak halaman yang menuntut pemakai menyelesaikan sesuatu lewat peramban (MFA, kebijakan)."""
        path = urlsplit(jawaban.url).path
        for awalan, pesan in HAMBATAN_LOGIN.items():
            if awalan in path:
                raise LoginWebTerhalang(f"{pesan} ({path}).")

    def login(self) -> "SesiWeb":
        """Login lewat form halaman login, sekali. Kegagalan tidak diulang."""
        with self._kunci:
            username, password = self.kredensial()
            halaman = self.minta("GET", PATH_LOGIN)
            if halaman.status_code >= 400:
                raise AswayaError(f"Halaman login Aswaya membalas HTTP {halaman.status_code}")
            if "notloggedin" not in kelas_body(halaman.text) and cari_form_login(sup_dari(halaman.text)) is None:
                # cookie lama masih berlaku: Moodle menampilkan "sudah masuk" tanpa form login
                self.tandai_masuk(halaman)
                return self
            form = baca_form_login(halaman.text, halaman.url)
            # action di luar Aswaya ditolak di sini, sebelum password ikut terkirim
            self.alamat_lengkap(form.action)
            isian = {**form.isian_bawaan, "username": username, "password": password}
            jawaban = self.minta("POST", form.action, data=isian, headers={"Referer": halaman.url})
            self.periksa_hambatan(jawaban)
            if jawaban.status_code >= 400:
                raise AswayaError(f"Login web Aswaya gagal: HTTP {jawaban.status_code}")
            if self.belum_masuk(jawaban):
                pesan = samarkan(pesan_galat_login(jawaban.text), username, password)
                raise LoginDitolak(
                    "Login web Aswaya ditolak; periksa ASWAYA_USERNAME dan ASWAYA_PASSWORD"
                    + (f". Pesan Aswaya: {pesan}" if pesan else "")
                )
            self.jumlah_login += 1
            self.tandai_masuk(jawaban)
            return self

    def tandai_masuk(self, jawaban) -> None:
        """Catat sesi yang sudah masuk, sesskey dari halamannya, lalu simpan cookie-nya."""
        self.sudah_masuk = True
        self.sesskey = sesskey_dari(jawaban.text) or self.sesskey
        self.simpan_cookie()

    def halaman(self, path_atau_url: str, params: dict | None = None):
        """GET satu halaman setelah masuk; sesi yang habis dipulihkan dengan login sekali."""
        with self._kunci:
            self.muat_cookie()
            jawaban = self.minta("GET", path_atau_url, params=params)
            if self.belum_masuk(jawaban):
                self.login()
                jawaban = self.minta("GET", path_atau_url, params=params)
                if self.belum_masuk(jawaban):
                    raise LoginDitolak("Sesi web Aswaya tidak pulih setelah login ulang")
            self.periksa_hambatan(jawaban)
            if jawaban.status_code >= 400:
                raise AswayaError(f"{path_atau_url} membalas HTTP {jawaban.status_code}")
            self.tandai_masuk(jawaban)
            return jawaban

    def pastikan_sesskey(self) -> str:
        """sesskey sesi ini; halaman beranda dibuka dulu kalau belum ada."""
        with self._kunci:
            if not self.sesskey:
                self.halaman(PATH_PEMANASAN)
            if not self.sesskey:
                raise AswayaError("sesskey tidak ditemukan di halaman Aswaya; susunan halamannya mungkin berubah")
            return self.sesskey

    # --- aksi yang mengubah data --------------------------------------------

    def aksi_get(self, path: str, params: dict):
        """GET yang mengubah data (dilindungi sesskey), mis. course/changenumsections.php.

        Kalau sesinya ternyata habis, Moodle mengalihkan ke halaman login
        sebelum aksinya dijalankan, jadi aksi diulang sekali sesudah login.
        Kegagalan jaringan sesudah permintaan berangkat menjadi HasilTidakPasti.
        """
        with self._kunci:
            for percobaan in range(2):
                sesskey = self.pastikan_sesskey()
                try:
                    jawaban = self.minta("GET", path, params={**params, "sesskey": sesskey})
                except AswayaError as galat:
                    raise HasilTidakPasti(PESAN_TIDAK_PASTI.format(fungsi=path, sebab=galat)) from None
                if not self.belum_masuk(jawaban) or percobaan:
                    break
                self.sesskey, self.sudah_masuk = "", False
                self.login()
            if self.belum_masuk(jawaban):
                raise LoginDitolak("Sesi web Aswaya habis dan login ulang tidak memulihkannya; aksi tidak dijalankan")
            self.tandai_masuk(jawaban)
            return jawaban

    def ajax(self, methodname: str, args: dict, *, tulis: bool = False) -> Any:
        """Panggil satu fungsi lewat lib/ajax/service.php dengan sesskey sesi ini.

        Sesi atau sesskey yang ditolak (invalidsesskey, servicerequireslogin)
        dipulihkan dengan login sekali lalu permintaannya diulang; Moodle
        menolak keduanya sebelum fungsinya dijalankan. Dengan `tulis=True`,
        kegagalan jaringan sesudah permintaan berangkat menjadi HasilTidakPasti.
        """
        with self._kunci:
            try:
                return self.kirim_ajax(methodname, args, tulis=tulis)
            except MoodleError as galat:
                if galat.kode not in KODE_SESI_HABIS:
                    raise
            self.sesskey, self.sudah_masuk = "", False
            self.login()
            try:
                return self.kirim_ajax(methodname, args, tulis=tulis)
            except MoodleError as galat:
                if galat.kode in KODE_SESI_HABIS:
                    raise LoginDitolak(f"Sesi web Aswaya tetap ditolak setelah login ulang ({galat.kode})") from None
                raise

    def kirim_ajax(self, methodname: str, args: dict, *, tulis: bool = False) -> Any:
        """Tepat satu POST ke lib/ajax/service.php; exception Moodle menjadi MoodleError."""
        sesskey = self.pastikan_sesskey()
        badan = [{"index": 0, "methodname": methodname, "args": args}]
        try:
            jawaban = self.minta("POST", PATH_AJAX, params={"sesskey": sesskey, "info": methodname}, json_badan=badan)
            if jawaban.status_code >= 400:
                raise AswayaError(f"{methodname}: service.php membalas HTTP {jawaban.status_code}")
            data = baca_json(jawaban, f"Jawaban AJAX {methodname}")
        except AswayaError as galat:
            if tulis:
                raise HasilTidakPasti(PESAN_TIDAK_PASTI.format(fungsi=methodname, sebab=galat)) from None
            raise
        if not isinstance(data, list) or not data or not isinstance(data[0], dict):
            if isinstance(data, dict) and data.get("errorcode"):
                raise MoodleError(methodname, str(data["errorcode"]), samarkan(str(data.get("error") or ""), *self.rahasia()))
            raise AswayaError(f"Jawaban AJAX {methodname} tidak berbentuk daftar hasil")
        pertama = data[0]
        if pertama.get("error"):
            galat_moodle = pertama.get("exception") or {}
            raise MoodleError(
                methodname,
                str(galat_moodle.get("errorcode") or ""),
                samarkan(str(galat_moodle.get("message") or ""), *self.rahasia()),
            )
        return pertama.get("data")
