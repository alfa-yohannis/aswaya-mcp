"""Klien web service Moodle untuk LMS Aswaya Pradita University.

Aswaya (https://aswaya.pradita.ac.id) adalah Moodle yang membuka layanan web
service moodle_mobile_app, layanan yang juga dipakai aplikasi Moodle di ponsel.
Per Oktober 2026 konfigurasi publiknya menunjukkan enablewebservices=1,
enablemobilewebservice=1, dan typeoflogin=1 (login langsung dengan username dan
password). Klien ini memakai empat titik akhir:

    POST /login/token.php                username, password, service=moodle_mobile_app
                                         -> {"token", "privatetoken"} atau {"error", "errorcode"}
    POST /webservice/rest/server.php     wstoken, wsfunction, moodlewsrestformat=json,
                                         dan parameter fungsi yang diratakan ala Moodle
                                         -> JSON hasil, atau {"exception", "errorcode", "message"}
    GET  /webservice/pluginfile.php/...  fileurl dari jawaban API ditambah parameter token
    POST /webservice/upload.php          token, filearea=draft, itemid, berkasnya

Ditambah satu yang tidak butuh login, untuk diagnosis:

    POST /lib/ajax/service-nologin.php   [{"index": 0, "methodname":
                                         "tool_mobile_get_public_config", "args": {}}]

Token dicari berurutan: argumen, ASWAYA_TOKEN, cache token (lihat
konfigurasi.py), lalu login dengan password. Token hasil login disimpan ke cache
supaya password tidak perlu dipakai setiap kali. Kalau Moodle menjawab
invalidtoken dan password tersedia, klien login ulang sekali lalu mengulang
panggilan itu. Pengulangan ini aman juga untuk fungsi yang menulis, karena Moodle
memeriksa token sebelum menjalankan fungsinya. Login yang gagal tidak pernah
diulang otomatis, karena Moodle bisa mengunci akun setelah beberapa kali gagal.

`privatetoken` dari token.php dibuang. Token, password, dan kunci akses pribadi
tidak pernah muncul di repr(), pesan galat, maupun keluaran. Berkas hanya diunduh
dari host Aswaya, karena tokennya ikut terkirim, dan pengalihan ke host lain
tidak diikuti.
"""

from __future__ import annotations

import difflib
import re
import threading
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

import requests

from aswaya_mcp.konfigurasi import (
    KonfigurasiError,
    baca_angka,
    baca_kredensial,
    baca_pengaturan,
    baca_ya_tidak,
    berkas_env,
    buat_sesi_http,
    baca_token_tersimpan,
    hapus_token_tersimpan,
    simpan_token,
)

# alamat bawaan; situs lain diatur lewat ASWAYA_URL di .env atau url: di
# aswaya.yaml, tanpa menyentuh kode
URL_BAWAAN = "https://aswaya.pradita.ac.id"
LAYANAN_BAWAAN = "moodle_mobile_app"

PATH_TOKEN = "/login/token.php"
PATH_REST = "/webservice/rest/server.php"
PATH_UNGGAH = "/webservice/upload.php"
PATH_NOLOGIN = "/lib/ajax/service-nologin.php"
PATH_PLUGINFILE_WS = "/webservice/pluginfile.php/"
PATH_PLUGINFILE = "/pluginfile.php/"

FUNGSI_INFO_SITUS = "core_webservice_get_site_info"
FUNGSI_KONFIGURASI_PUBLIK = "tool_mobile_get_public_config"

BATAS_BAWAAN_DETIK = 60
BATAS_UNDUH_BAWAAN_DETIK = 300
MAKS_PENGALIHAN_BAWAAN = 5

# errorcode Moodle yang berarti tokennya sudah tidak berlaku; token.php dan
# server.php memakai kode yang sama
KODE_TOKEN_TIDAK_BERLAKU = frozenset({"invalidtoken", "invalidtimedtoken"})
POLA_NAMA_FUNGSI = re.compile(r"^[a-z][a-z0-9_]*$")

PESAN_TIDAK_PASTI = (
    "Permintaan {fungsi} sudah dikirim, tetapi hasilnya tidak bisa dipastikan ({sebab}). "
    "Periksa dulu di Aswaya, mis. lewat tool baca yang sesuai, sebelum mengirim ulang."
)


class AswayaError(RuntimeError):
    """Kegagalan yang berasal dari Aswaya atau jaringan menuju ke sana."""


class LoginDitolak(AswayaError):
    """Aswaya menolak kredensialnya, atau token yang ditolak tidak bisa dipulihkan dengan login ulang."""


class AlamatDitolak(AswayaError):
    """Alamat di luar Aswaya, bukan https, atau bukan berkas yang boleh diunduh dengan token."""


class FungsiTidakTersedia(AswayaError):
    """Fungsi web service yang diminta tidak dimuat layanan token ini."""


class IsianDitolak(AswayaError):
    """Isian ditolak sebelum apa pun dikirim ke Aswaya."""


class HasilTidakPasti(AswayaError):
    """Permintaan tulis sudah berangkat, tetapi diterima atau tidaknya tidak bisa dipastikan."""


class MoodleError(AswayaError):
    """Moodle menjawab sebuah fungsi dengan exception, mis. nopermissions atau invalidparameter."""

    def __init__(self, fungsi: str, kode: str, pesan: str, debuginfo: str = ""):
        """Simpan fungsi, errorcode, dan pesan Moodle; debuginfo ditambahkan seperlunya."""
        self.fungsi = fungsi
        self.kode = kode or ""
        self.pesan_moodle = pesan or ""
        self.debuginfo = debuginfo or ""
        teks = f"{fungsi} ditolak Aswaya ({self.kode or 'tanpa kode'}): {self.pesan_moodle}"
        if self.debuginfo:
            teks += f" [{self.debuginfo[:300]}]"
        super().__init__(teks)


def batas_detik() -> int:
    """Batas waktu login dan panggilan fungsi, dalam detik."""
    return baca_angka("ASWAYA_BATAS_DETIK", BATAS_BAWAAN_DETIK)


def batas_unduh_detik() -> int:
    """Batas waktu unduhan dan unggahan berkas, dalam detik."""
    return baca_angka("ASWAYA_BATAS_UNDUH_DETIK", BATAS_UNDUH_BAWAAN_DETIK)


def maks_pengalihan() -> int:
    """Banyaknya pengalihan yang diikuti saat mengunduh berkas."""
    return baca_angka("ASWAYA_MAKS_PENGALIHAN", MAKS_PENGALIHAN_BAWAAN)


def nama_layanan() -> str:
    """Nama pendek layanan web service yang dimintai token."""
    return baca_pengaturan("ASWAYA_LAYANAN", LAYANAN_BAWAAN)


def tentukan_alamat(base_url: str = "") -> str:
    """Alamat situs dari argumen, lalu ASWAYA_URL, lalu bawaan. Selain https ditolak.

    Moodle boleh terpasang di subdirektori (https://kampus.ac.id/lms), jadi path
    dipertahankan; garis miring di ujungnya dibuang.
    """
    alamat = (base_url or baca_pengaturan("ASWAYA_URL", URL_BAWAAN)).strip().rstrip("/")
    bagian = urlsplit(alamat)
    if bagian.scheme != "https" or not bagian.netloc or bagian.query or bagian.fragment:
        raise KonfigurasiError(f"Alamat Aswaya harus berbentuk https://host[/path], bukan {alamat!r}; periksa ASWAYA_URL")
    return alamat


def ratakan_nilai(nama: str, nilai: Any) -> list[tuple[str, str]]:
    """Satu nilai sebagai pasangan isian Moodle: list jadi nama[0], dict jadi nama[kunci].

    True/False menjadi 1/0 dan None dilewati, sehingga parameter opsional cukup
    diisi None untuk memakai nilai bawaan Moodle.
    """
    if nilai is None:
        return []
    if isinstance(nilai, bool):
        return [(nama, "1" if nilai else "0")]
    if isinstance(nilai, dict):
        hasil = []
        for kunci, isi in nilai.items():
            hasil.extend(ratakan_nilai(f"{nama}[{kunci}]", isi))
        return hasil
    if isinstance(nilai, (list, tuple)):
        hasil = []
        for nomor, isi in enumerate(nilai):
            hasil.extend(ratakan_nilai(f"{nama}[{nomor}]", isi))
        return hasil
    return [(nama, str(nilai))]


def ratakan(parameter: dict | None) -> list[tuple[str, str]]:
    """Parameter fungsi sebagai isian form ala Moodle.

        {"courseid": 5, "options": [{"name": "userfields", "value": "id"}]}
        -> [("courseid", "5"), ("options[0][name]", "userfields"), ("options[0][value]", "id")]
    """
    hasil = []
    for kunci, nilai in (parameter or {}).items():
        hasil.extend(ratakan_nilai(str(kunci), nilai))
    return hasil


def samarkan(teks: str, *rahasia: str) -> str:
    """Ganti setiap kemunculan nilai rahasia dengan ***, untuk pesan yang ditampilkan."""
    teks = str(teks or "")
    for nilai in rahasia:
        if nilai:
            teks = teks.replace(nilai, "***")
    return teks


def periksa_nama_fungsi(fungsi: str) -> str:
    """Nama wsfunction yang sah (huruf kecil, angka, garis bawah); selain itu ditolak."""
    fungsi = (fungsi or "").strip()
    if not POLA_NAMA_FUNGSI.match(fungsi):
        raise IsianDitolak(f"Nama fungsi {fungsi!r} tidak sah; contoh yang benar: core_course_get_contents")
    return fungsi


def periksa_id(nilai: Any, nama: str) -> int:
    """Id Moodle sebagai bilangan bulat positif; selain itu ditolak sebelum menghubungi Aswaya."""
    try:
        angka = int(nilai)
    except (TypeError, ValueError):
        raise IsianDitolak(f"{nama} harus berupa angka, bukan {nilai!r}") from None
    if isinstance(nilai, bool) or angka <= 0 or str(angka) != str(nilai).strip():
        raise IsianDitolak(f"{nama} harus bilangan bulat positif, bukan {nilai!r}")
    return angka


def baca_json(jawaban, keterangan: str) -> Any:
    """Isi jawaban sebagai JSON; jawaban yang bukan JSON dilaporkan dengan status HTTP-nya."""
    try:
        return jawaban.json()
    except ValueError as galat:
        raise AswayaError(f"{keterangan} bukan JSON (HTTP {jawaban.status_code})") from galat


def adalah_galat_moodle(hasil: Any) -> bool:
    """Apakah jawaban server.php berbentuk exception Moodle."""
    return isinstance(hasil, dict) and "exception" in hasil and "errorcode" in hasil


def buang_query(alamat: str, buang: tuple[str, ...]) -> str:
    """Alamat tanpa parameter query tertentu, mis. token yang terbawa dari tempat lain."""
    bagian = urlsplit(alamat)
    sisa = [(kunci, nilai) for kunci, nilai in parse_qsl(bagian.query, keep_blank_values=True) if kunci not in buang]
    return urlunsplit((bagian.scheme, bagian.netloc, bagian.path, urlencode(sisa), ""))


class KlienAswaya:
    """Sesi web service Aswaya milik satu pemakai.

    Kredensial boleh diberikan langsung. Kalau salah satu dari username,
    password, atau token diberikan, setelan tidak dipakai sama sekali, jadi
    token milik setelan tidak tercampur dengan akun lain. Kalau semuanya
    dikosongkan, kredensial dibaca dari setelan (atur_setelan, environment, atau
    .env) saat pertama dibutuhkan. Membuat objek ini belum menghubungi Aswaya.
    """

    def __init__(
        self,
        username: str | None = None,
        password: str | None = None,
        token: str | None = None,
        base_url: str = "",
        *,
        pakai_cache: bool | None = None,
    ):
        """Siapkan klien tanpa login. Alamat yang bukan https ditolak di sini."""
        self._username = (username or "").strip()
        self._password = password or ""
        self._token_argumen = (token or "").strip()
        self._dari_argumen = bool(self._username or self._password or self._token_argumen)
        self.base_url = tentukan_alamat(base_url)
        self.pakai_cache = baca_ya_tidak("ASWAYA_SIMPAN_CACHE", True) if pakai_cache is None else pakai_cache
        self.sesi_http = buat_sesi_http()
        self.token = ""
        self.sumber_token = ""
        self.jumlah_login = 0
        self.token_tersimpan_di: Path | None = None
        self._info_situs: dict | None = None
        # login ulang dan penggantian token tidak boleh bersilangan antar-thread
        self._kunci = threading.RLock()

    def __repr__(self) -> str:
        """Ringkasan tanpa kredensial, aman muncul di log atau traceback."""
        return f"KlienAswaya(base_url={self.base_url!r}, punya_token={bool(self.token)}, sumber={self.sumber_token!r})"

    # --- kredensial dan token ---------------------------------------------

    def kredensial(self) -> tuple[str, str]:
        """Username dan password: dari argumen kalau ada kredensial argumen, selain itu dari setelan."""
        if self._dari_argumen:
            return self._username, self._password
        setelan = baca_kredensial()
        return setelan["ASWAYA_USERNAME"], setelan["ASWAYA_PASSWORD"]

    def token_awal(self) -> tuple[str, str]:
        """Token yang dipakai sebelum login dan sumbernya: argumen, ASWAYA_TOKEN, lalu cache."""
        if self._token_argumen:
            return self._token_argumen, "argumen"
        if not self._dari_argumen:
            token = baca_kredensial()["ASWAYA_TOKEN"]
            if token:
                return token, "setelan"
        username = self.kredensial()[0]
        if self.pakai_cache and username:
            token = baca_token_tersimpan(self.base_url, username)
            if token:
                return token, "cache"
        return "", ""

    def pastikan_token(self) -> str:
        """Token yang siap dipakai; login berjalan di sini kalau belum ada token sama sekali."""
        with self._kunci:
            if self.token:
                return self.token
            token, sumber = self.token_awal()
            if token:
                self.token, self.sumber_token = token, sumber
                return token
            self.login()
            return self.token

    def login(self) -> "KlienAswaya":
        """Minta token baru dengan username dan password, lalu simpan ke cache kalau diizinkan."""
        with self._kunci:
            username, password = self.kredensial()
            kurang = [nama for nama, nilai in (("ASWAYA_USERNAME", username), ("ASWAYA_PASSWORD", password)) if not nilai]
            if kurang:
                raise KonfigurasiError(
                    f"Kredensial belum ada: {', '.join(kurang)}. Isi di {berkas_env()}, lewat environment, "
                    "atau atur_setelan(); ASWAYA_TOKEN bisa dipakai sebagai ganti password."
                )
            token = self.minta_token(username, password)
            self.token, self.sumber_token = token, "login"
            self.jumlah_login += 1
            self._info_situs = None
            if self.pakai_cache:
                self.token_tersimpan_di = simpan_token(self.base_url, username, token)
            return self

    def minta_token(self, username: str, password: str) -> str:
        """POST ke token.php sekali. Pesan galatnya disamarkan dari username dan password."""
        alamat = self.base_url + PATH_TOKEN
        isian = {"username": username, "password": password, "service": nama_layanan()}
        try:
            jawaban = self.sesi_http.request("POST", alamat, data=isian, timeout=batas_detik(), allow_redirects=False)
        except requests.RequestException as galat:
            raise AswayaError(f"Permintaan token ke {alamat} gagal: {samarkan(str(galat), username, password)}") from None
        if jawaban.is_redirect:
            raise AswayaError(
                f"{alamat} dialihkan ke {jawaban.headers.get('Location', '?')}; periksa ASWAYA_URL"
            )
        if jawaban.status_code >= 400:
            raise AswayaError(f"{alamat} membalas HTTP {jawaban.status_code}")
        data = baca_json(jawaban, "Jawaban token.php")
        if isinstance(data, dict) and data.get("token"):
            return str(data["token"])
        if not isinstance(data, dict):
            raise AswayaError("Jawaban token.php tidak berisi token maupun pesan galat")
        kode = str(data.get("errorcode") or "")
        pesan = samarkan(str(data.get("error") or ""), username, password)
        if kode == "invalidlogin":
            raise LoginDitolak(
                "Login Aswaya ditolak: username atau password salah; periksa ASWAYA_USERNAME dan "
                f"ASWAYA_PASSWORD. Pesan Aswaya: {pesan}"
            )
        raise LoginDitolak(f"Aswaya tidak memberi token ({kode or 'tanpa kode'}): {pesan}")

    def pulihkan_token(self, token_lama: str, galat: MoodleError) -> None:
        """Ganti token yang ditolak dengan login ulang sekali; tanpa password, laporkan dengan jelas."""
        with self._kunci:
            if self.token and self.token != token_lama:
                return
            sumber = self.sumber_token
            username, password = self.kredensial()
            if sumber == "cache" and username:
                hapus_token_tersimpan(self.base_url, username)
            self.token, self.sumber_token, self._info_situs = "", "", None
            if not (username and password):
                raise LoginDitolak(
                    f"Token Aswaya (dari {sumber or 'setelan'}) tidak berlaku lagi ({galat.kode}) dan password "
                    "tidak tersedia untuk login ulang. Perbarui ASWAYA_TOKEN atau isi ASWAYA_PASSWORD."
                )
            self.login()

    # --- memanggil fungsi -------------------------------------------------

    def panggil(self, fungsi: str, parameter: dict | None = None, *, tulis: bool = False, periksa: bool = True) -> Any:
        """Panggil satu fungsi web service dan kembalikan hasilnya yang sudah diurai dari JSON.

        Fungsi yang tidak dimuat layanan token ini ditolak sebelum dikirim, dengan
        pesan yang menyebut fungsi serupa yang tersedia. Token yang ditolak
        dipulihkan dengan login ulang sekali lalu panggilan diulang. Dengan
        `tulis=True`, kegagalan jaringan atau jawaban rusak sesudah permintaan
        berangkat menjadi HasilTidakPasti, karena fungsinya mungkin sudah berjalan.
        """
        fungsi = periksa_nama_fungsi(fungsi)
        isian = ratakan(parameter)
        if periksa and fungsi != FUNGSI_INFO_SITUS:
            self.periksa_fungsi(fungsi)
        token = self.pastikan_token()
        try:
            return self.kirim_ke_server(token, fungsi, isian, tulis=tulis)
        except MoodleError as galat:
            if galat.kode not in KODE_TOKEN_TIDAK_BERLAKU:
                raise
            self.pulihkan_token(token, galat)
        try:
            return self.kirim_ke_server(self.pastikan_token(), fungsi, isian, tulis=tulis)
        except MoodleError as galat:
            if galat.kode in KODE_TOKEN_TIDAK_BERLAKU:
                raise LoginDitolak(f"Token baru hasil login ulang juga ditolak Aswaya ({galat.kode})") from None
            raise

    def kirim_ke_server(self, token: str, fungsi: str, isian: list[tuple[str, str]], *, tulis: bool = False) -> Any:
        """Tepat satu POST ke server.php. Token dikirim di badan permintaan, tidak di URL."""
        alamat = self.base_url + PATH_REST
        data = [("wstoken", token), ("wsfunction", fungsi), ("moodlewsrestformat", "json"), *isian]
        try:
            jawaban = self.sesi_http.request("POST", alamat, data=data, timeout=batas_detik(), allow_redirects=False)
        except requests.RequestException as galat:
            sebab = samarkan(str(galat), token)
            if tulis:
                raise HasilTidakPasti(PESAN_TIDAK_PASTI.format(fungsi=fungsi, sebab=sebab)) from None
            raise AswayaError(f"Panggilan {fungsi} ke {alamat} gagal: {sebab}") from None
        try:
            if jawaban.is_redirect:
                raise AswayaError(f"{alamat} dialihkan ke {jawaban.headers.get('Location', '?')}; periksa ASWAYA_URL")
            if jawaban.status_code >= 400:
                raise AswayaError(f"{fungsi}: server.php membalas HTTP {jawaban.status_code}")
            hasil = baca_json(jawaban, f"Jawaban {fungsi}")
        except AswayaError as galat:
            if tulis:
                raise HasilTidakPasti(PESAN_TIDAK_PASTI.format(fungsi=fungsi, sebab=galat)) from None
            raise
        if adalah_galat_moodle(hasil):
            raise MoodleError(
                fungsi,
                str(hasil.get("errorcode") or ""),
                samarkan(str(hasil.get("message") or ""), token),
                samarkan(str(hasil.get("debuginfo") or ""), token),
            )
        return hasil

    # --- info situs dan daftar fungsi --------------------------------------

    def info_situs(self, *, segarkan: bool = False) -> dict:
        """core_webservice_get_site_info: situs, pemakai, release Moodle, dan fungsi yang boleh dipakai.

        Hasilnya diingat sampai token berganti. `userprivateaccesskey` dibuang
        karena kunci itu bisa dipakai membuka berkas pemakai tanpa token.
        """
        with self._kunci:
            if self._info_situs is not None and not segarkan:
                return self._info_situs
        info = self.panggil(FUNGSI_INFO_SITUS)
        if not isinstance(info, dict):
            raise AswayaError("Jawaban core_webservice_get_site_info tidak berbentuk objek")
        info.pop("userprivateaccesskey", None)
        with self._kunci:
            self._info_situs = info
        return info

    def daftar_fungsi(self) -> list[str]:
        """Nama semua wsfunction yang boleh dipakai token ini, urut abjad."""
        return sorted({satu.get("name", "") for satu in self.info_situs().get("functions", []) if satu.get("name")})

    def tersedia(self, fungsi: str) -> bool:
        """Apakah sebuah fungsi dimuat layanan token ini."""
        info = self.info_situs()
        if "functions" not in info:
            return True
        return fungsi in self.daftar_fungsi()

    def periksa_fungsi(self, fungsi: str) -> None:
        """Tolak fungsi yang tidak dimuat layanan token ini, dengan saran nama yang mirip."""
        if self.tersedia(fungsi):
            return
        mirip = difflib.get_close_matches(fungsi, self.daftar_fungsi(), n=3, cutoff=0.6)
        saran = f" Yang mirip: {', '.join(mirip)}." if mirip else ""
        raise FungsiTidakTersedia(
            f"Fungsi {fungsi} tidak tersedia untuk token ini; layanan {nama_layanan()} di Aswaya tidak "
            f"memuatnya.{saran} Daftar lengkapnya ada di fungsi_tersedia (CLI: ./aswaya fungsi)."
        )

    @property
    def userid(self) -> int:
        """userid Moodle pemilik token."""
        return int(self.info_situs()["userid"])

    # --- tanpa login -------------------------------------------------------

    def konfigurasi_publik(self) -> dict:
        """tool_mobile_get_public_config tanpa login: nama situs, jenis login, status pemeliharaan."""
        alamat = self.base_url + PATH_NOLOGIN
        badan = [{"index": 0, "methodname": FUNGSI_KONFIGURASI_PUBLIK, "args": {}}]
        try:
            jawaban = self.sesi_http.request("POST", alamat, json=badan, timeout=batas_detik(), allow_redirects=False)
        except requests.RequestException as galat:
            raise AswayaError(f"Permintaan ke {alamat} gagal: {galat}") from None
        if jawaban.status_code >= 400:
            raise AswayaError(f"{alamat} membalas HTTP {jawaban.status_code}")
        data = baca_json(jawaban, "Jawaban service-nologin.php")
        if not isinstance(data, list) or not data or not isinstance(data[0], dict):
            raise AswayaError("Jawaban service-nologin.php tidak berbentuk daftar hasil")
        pertama = data[0]
        if pertama.get("error"):
            galat_moodle = pertama.get("exception") or {}
            raise MoodleError(
                FUNGSI_KONFIGURASI_PUBLIK,
                str(galat_moodle.get("errorcode") or ""),
                str(galat_moodle.get("message") or ""),
            )
        return pertama.get("data") or {}

    # --- berkas ------------------------------------------------------------

    def alamat_berkas(self, url: str) -> str:
        """URL berkas yang boleh diunduh dengan token: di host Aswaya, lewat webservice/pluginfile.php.

        Alamat pluginfile.php biasa (mis. gambar di dalam HTML) diubah ke versi
        webservice-nya, seperti yang dilakukan aplikasi Moodle. Parameter token
        yang terbawa di URL dibuang; klien menambahkan tokennya sendiri.
        """
        alamat = urljoin(self.base_url + "/", (url or "").strip())
        bagian, dasar = urlsplit(alamat), urlsplit(self.base_url)
        if bagian.scheme != "https" or bagian.netloc.lower() != dasar.netloc.lower():
            raise AlamatDitolak(
                f"{url!r} berada di luar Aswaya ({self.base_url}); token hanya dikirim ke host Aswaya"
            )
        path = bagian.path
        awalan = dasar.path.rstrip("/")
        if not path.startswith(awalan + "/"):
            raise AlamatDitolak(f"{url!r} berada di luar {self.base_url}")
        sisa = path[len(awalan):]
        if sisa.startswith(PATH_PLUGINFILE):
            sisa = PATH_PLUGINFILE_WS + sisa[len(PATH_PLUGINFILE):]
        if not sisa.startswith(PATH_PLUGINFILE_WS):
            raise AlamatDitolak(
                f"{url!r} bukan alamat berkas Moodle (webservice/pluginfile.php/...); pakai fileurl dari isi_kursus, "
                "pengumpulan_tugas, atau diskusi_forum"
            )
        return buang_query(urlunsplit((bagian.scheme, bagian.netloc, awalan + sisa, bagian.query, "")), ("token",))

    def buka_berkas(self, url: str):
        """GET satu berkas Aswaya dengan token, sebagai jawaban streaming yang harus ditutup pemanggil.

        Pengalihan hanya diikuti kalau tujuannya berkas Aswaya juga. Jawaban JSON
        berisi errorcode dilaporkan sebagai MoodleError; token yang ditolak
        dipulihkan sekali seperti panggilan fungsi.
        """
        alamat = self.alamat_berkas(url)
        token = self.pastikan_token()
        jawaban = self.ambil_berkas(alamat, token)
        galat = self.galat_berkas(jawaban, token)
        if galat is not None and galat.kode in KODE_TOKEN_TIDAK_BERLAKU:
            self.pulihkan_token(token, galat)
            token = self.pastikan_token()
            jawaban = self.ambil_berkas(alamat, token)
            galat = self.galat_berkas(jawaban, token)
        if galat is not None:
            raise galat
        return jawaban

    def ambil_berkas(self, alamat: str, token: str):
        """GET berkas dan ikuti pengalihannya selama masih berkas Aswaya; token tidak pernah ikut ke host lain."""
        for _ in range(maks_pengalihan() + 1):
            try:
                jawaban = self.sesi_http.request(
                    "GET", alamat, params={"token": token}, stream=True,
                    timeout=batas_unduh_detik(), allow_redirects=False,
                )
            except requests.RequestException as galat:
                raise AswayaError(f"Unduhan {alamat} gagal: {samarkan(str(galat), token)}") from None
            if not jawaban.is_redirect:
                if jawaban.status_code >= 400:
                    jawaban.close()
                    raise AswayaError(f"Aswaya membalas HTTP {jawaban.status_code} untuk {alamat}")
                return jawaban
            tujuan = urljoin(alamat, jawaban.headers.get("Location", ""))
            jawaban.close()
            try:
                alamat = self.alamat_berkas(tujuan)
            except AlamatDitolak as galat:
                bagian = urlsplit(tujuan)
                raise AlamatDitolak(
                    f"Aswaya mengalihkan unduhan ke {bagian.scheme}://{bagian.netloc}{bagian.path}; pengalihan itu "
                    "tidak diikuti supaya token tidak ikut terkirim. Buka alamat itu sendiri di peramban."
                ) from galat
        raise AswayaError(f"Terlalu banyak pengalihan saat mengunduh {alamat}")

    def galat_berkas(self, jawaban, token: str) -> MoodleError | None:
        """MoodleError kalau Aswaya menjawab permintaan berkas dengan JSON galat; None kalau isinya berkas."""
        jenis = jawaban.headers.get("Content-Type", "").lower()
        if "json" not in jenis:
            return None
        try:
            data = jawaban.json()
        except ValueError:
            return None
        if not isinstance(data, dict) or not data.get("errorcode"):
            return None
        jawaban.close()
        return MoodleError(
            "webservice/pluginfile.php",
            str(data.get("errorcode")),
            samarkan(str(data.get("message") or data.get("error") or ""), token),
        )

    def unggah_berkas(self, path: str | Path, *, itemid: int = 0, filepath: str = "/") -> dict:
        """Unggah satu berkas lokal ke draft area pemakai lewat webservice/upload.php.

        Hasilnya keterangan berkas di draft area, termasuk `itemid` yang bisa
        diteruskan ke fungsi lain (mis. attachmentsid pada mod_forum_add_discussion).
        itemid=0 membuat draft area baru; isi itemid hasil unggahan sebelumnya
        untuk menaruh beberapa berkas di area yang sama. Draft area dibersihkan
        Moodle sendiri kalau tidak dipakai.
        """
        berkas = Path(path).expanduser()
        if not berkas.is_file():
            raise IsianDitolak(f"Berkas {berkas} tidak ada")
        alamat = self.base_url + PATH_UNGGAH
        token = self.pastikan_token()
        isian = {"token": token, "filearea": "draft", "itemid": str(int(itemid)), "filepath": filepath}
        try:
            with berkas.open("rb") as isi:
                jawaban = self.sesi_http.request(
                    "POST", alamat, data=isian, files={"file_1": (berkas.name, isi)},
                    timeout=batas_unduh_detik(), allow_redirects=False,
                )
        except requests.RequestException as galat:
            raise AswayaError(f"Unggahan {berkas.name} gagal: {samarkan(str(galat), token)}") from None
        if jawaban.status_code >= 400:
            raise AswayaError(f"{alamat} membalas HTTP {jawaban.status_code}")
        data = baca_json(jawaban, "Jawaban upload.php")
        if isinstance(data, dict) and (data.get("errorcode") or data.get("error")):
            kode = str(data.get("errorcode") or "")
            if kode in KODE_TOKEN_TIDAK_BERLAKU:
                raise LoginDitolak(f"Token ditolak upload.php ({kode}); jalankan cek_login lalu coba lagi")
            raise MoodleError("webservice/upload.php", kode, samarkan(str(data.get("error") or ""), token))
        if not isinstance(data, list) or not data:
            raise AswayaError("Jawaban upload.php tidak berisi keterangan berkas")
        return data[0]

    # --- alamat halaman ----------------------------------------------------

    def url_kursus(self, kursus_id: int) -> str:
        """Alamat halaman kursus di peramban."""
        return f"{self.base_url}/course/view.php?id={int(kursus_id)}"

    def url_modul(self, jenis: str, cmid: int) -> str:
        """Alamat halaman satu modul (aktivitas atau sumber belajar) di peramban."""
        return f"{self.base_url}/mod/{jenis}/view.php?id={int(cmid)}"
