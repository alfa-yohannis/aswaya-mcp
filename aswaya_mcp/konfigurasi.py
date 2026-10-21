"""Konfigurasi: akar proyek, setelan, kredensial, sesi HTTP, zona waktu, dan cache rahasia.

Paket ini dipakai dari dua arah, dan keduanya harus benar tanpa disetel apa pun:

    berdiri sendiri   repositori ini di-clone lalu dijalankan lewat ./aswaya.
                      Akar proyek = direktori repositori itu sendiri.

    sebagai pustaka   proyek lain memasangnya (`pip install aswaya-mcp`) dan
                      mengimpor `aswaya_mcp`. Akar proyek = direktori kerja
                      proyek itu, bukan site-packages tempat paket ini terpasang.

Akar proyek menentukan letak berkas-berkas ini:

    <akar>/.env          kredensial (ASWAYA_USERNAME, ASWAYA_PASSWORD, ASWAYA_TOKEN)
    <akar>/aswaya.yaml   setelan non-rahasia (alamat situs, batas waktu, zona waktu)
    <akar>/data/         tujuan bawaan berkas unduhan

Direktori di atasnya tidak pernah ikut ditelusuri, supaya hasilnya tidak berubah
hanya karena paket ini dipindah. Proyek yang memakainya sebagai pustaka bisa
menentukan sendiri lewat `atur_akar_proyek()`, `atur_setelan()`, atau
ASWAYA_AKAR_PROYEK.

Rahasia dipisah dari setelan dengan sengaja: `.env` memuat username, password,
dan token, dan tidak pernah ikut ter-commit, sedangkan `aswaya.yaml` aman
dibagikan. Karena itu kredensial tidak pernah dibaca dari `aswaya.yaml`.

Token hasil login dan cookie sesi web disimpan di luar repositori, di
$XDG_CACHE_HOME/aswaya-mcp/ (bawaannya ~/.cache/aswaya-mcp/), satu berkas per
jenis dan per pasangan situs dan username (token-*.json, sesi-*.json), berizin
0600 di direktori berizin 0700. Sistem berkas yang tidak menegakkan izin (NTFS,
FAT, sebagian mount jaringan) membuat berkas itu terbaca pemakai lain, jadi di
sana tidak ada yang disimpan dan rahasianya hanya hidup di memori.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
import tempfile
from datetime import datetime, timezone, tzinfo
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import requests
from dotenv import dotenv_values

AWALAN = "ASWAYA_"
NAMA_APLIKASI = "aswaya-mcp"
USER_AGENT_BAWAAN = NAMA_APLIKASI
ZONA_WAKTU_BAWAAN = "Asia/Jakarta"

# isian yang dibaca sebagai "ya" atau "tidak" pada setelan berjenis saklar
NILAI_YA = frozenset({"1", "true", "ya", "yes", "on", "benar"})
NILAI_TIDAK = frozenset({"0", "false", "tidak", "no", "off", "salah"})

IZIN_BERKAS_CACHE = 0o600
IZIN_DIR_CACHE = 0o700


class KonfigurasiError(RuntimeError):
    """Setelan atau kredensial yang tidak bisa dipakai.

    Sengaja bukan SystemExit: pustaka tidak boleh menghentikan program yang
    memakainya. Titik masuk CLI-lah yang menangkap ini dan keluar dengan rapi.
    """


# Ditetapkan dari kode lewat atur_akar_proyek()/atur_setelan(); dipakai proyek
# lain yang tidak mau bergantung pada berkas atau environment sama sekali.
_akar_ditetapkan: Path | None = None
_setelan_ditetapkan: dict[str, str] = {}
_konfigurasi_tersimpan: dict | None = None


def akar_bawaan() -> Path:
    """Akar proyek kalau tidak ada yang menentukan.

    Kalau paket ini berada di dalam checkout repositorinya sendiri, direktori
    repositori itulah akarnya (mode berdiri sendiri). Kalau sudah terpasang
    sebagai pustaka, site-packages jelas bukan tempat menaruh .env milik
    pemakai, jadi yang dipakai direktori kerja proyek pemanggil.
    """
    akar_repo = Path(__file__).resolve().parent.parent
    if (akar_repo / "pyproject.toml").is_file():
        return akar_repo
    return Path.cwd()


def akar_proyek() -> Path:
    """Direktori tempat .env, aswaya.yaml, dan data/ dicari."""
    if _akar_ditetapkan is not None:
        return _akar_ditetapkan
    ditetapkan = os.environ.get("ASWAYA_AKAR_PROYEK")
    if ditetapkan:
        return Path(ditetapkan).expanduser()
    return akar_bawaan()


def atur_akar_proyek(path: str | Path | None) -> None:
    """Tetapkan akar proyek dari kode. `None` mengembalikan ke perilaku bawaan."""
    global _akar_ditetapkan
    _akar_ditetapkan = Path(path).expanduser().resolve() if path is not None else None
    lupakan_konfigurasi()


def atur_setelan(**nilai: object) -> None:
    """Setelan dari kode, mis. `atur_setelan(url="https://lms.kampus-lain.ac.id")`.

    Kuncinya boleh gaya YAML (`url`) atau gaya environment (`ASWAYA_URL`). Ini
    kepastian tertinggi setelah argumen pemanggil: proyek yang menyetel sesuatu
    secara eksplisit tidak boleh berubah diam-diam karena environment mesin.
    Panggil tanpa argumen untuk mengosongkannya.
    """
    if not nilai:
        _setelan_ditetapkan.clear()
        return
    for kunci, isi in nilai.items():
        _setelan_ditetapkan[nama_di_yaml(kunci)] = str(isi)


def lupakan_konfigurasi() -> None:
    """Buang isi aswaya.yaml yang diingat, supaya dibaca ulang berikutnya."""
    global _konfigurasi_tersimpan
    _konfigurasi_tersimpan = None


def berkas_env() -> Path:
    """Letak .env yang dipakai."""
    return akar_proyek() / ".env"


def dir_data() -> Path:
    """Direktori hasil kerja lokal, termasuk tujuan bawaan unduhan."""
    return akar_proyek() / "data"


def berkas_konfigurasi() -> Path | None:
    """Berkas aswaya.yaml (atau .yml) yang dipakai, kalau memang ada."""
    akar = akar_proyek()
    for nama in ("aswaya.yaml", "aswaya.yml"):
        if (akar / nama).is_file():
            return akar / nama
    return None


def muat_konfigurasi() -> dict:
    """Isi aswaya.yaml sebagai dict datar. Dibaca sekali lalu diingat.

    PyYAML sengaja diimpor di sini, bukan di kepala modul: pemakai yang cukup
    dengan setelan bawaan tidak perlu punya berkas konfigurasi sama sekali.
    """
    global _konfigurasi_tersimpan
    if _konfigurasi_tersimpan is not None:
        return _konfigurasi_tersimpan

    berkas = berkas_konfigurasi()
    if berkas is None:
        _konfigurasi_tersimpan = {}
        return _konfigurasi_tersimpan

    try:
        import yaml
    except ImportError as galat:
        raise KonfigurasiError(
            f"{berkas} ada tapi PyYAML belum terpasang. Pasang dulu: pip install pyyaml"
        ) from galat

    isi = yaml.safe_load(berkas.read_text(encoding="utf-8")) or {}
    if not isinstance(isi, dict):
        raise KonfigurasiError(
            f"{berkas} harus berupa pemetaan kunci: nilai, bukan {type(isi).__name__}"
        )
    _konfigurasi_tersimpan = isi
    return _konfigurasi_tersimpan


def nama_di_yaml(kunci: str) -> str:
    """ASWAYA_URL -> url; kunci tanpa awalan dipakai apa adanya."""
    return kunci[len(AWALAN):].lower() if kunci.startswith(AWALAN) else kunci.lower()


def baca_pengaturan(kunci: str, bawaan: str = "", *, dari_yaml: bool = True) -> str:
    """Setelan opsional, dari yang paling khusus ke yang paling umum:

        atur_setelan()  ->  environment  ->  .env  ->  aswaya.yaml  ->  bawaan

    Argumen pemanggil (mis. `KlienAswaya(base_url=...)`) menang atas semuanya;
    yang itu ditangani pemanggilnya sendiri sebelum fungsi ini dipanggil.

    Isian kosong dianggap belum diisi, jadi `ASWAYA_PASSWORD=` di .env sama
    saja dengan tidak menulis barisnya. Kuncinya ditulis gaya environment
    (ASWAYA_URL); di aswaya.yaml nama yang sama dipakai tanpa awalan ASWAYA_
    dan huruf kecil (url). `dari_yaml=False` melewati aswaya.yaml, dipakai
    untuk kredensial.
    """
    dari_kode = _setelan_ditetapkan.get(nama_di_yaml(kunci), "").strip()
    if dari_kode:
        return dari_kode

    dari_lingkungan = (os.environ.get(kunci) or "").strip()
    if dari_lingkungan:
        return dari_lingkungan
    dari_env = (dotenv_values(berkas_env()).get(kunci) or "").strip()
    if dari_env:
        return dari_env

    if not dari_yaml:
        return bawaan
    dari_berkas = muat_konfigurasi().get(nama_di_yaml(kunci))
    return str(dari_berkas).strip() if dari_berkas not in (None, "") else bawaan


def baca_angka(kunci: str, bawaan: int) -> int:
    """Setelan berupa bilangan bulat; isian yang tidak masuk akal ditolak jelas."""
    nilai = baca_pengaturan(kunci, str(bawaan))
    try:
        return int(nilai)
    except ValueError as galat:
        raise KonfigurasiError(f"Setelan {kunci} harus berupa angka, bukan {nilai!r}") from galat


def baca_ya_tidak(kunci: str, bawaan: bool) -> bool:
    """Setelan saklar: ya/tidak, true/false, 1/0, on/off."""
    nilai = baca_pengaturan(kunci, "ya" if bawaan else "tidak").lower()
    if nilai in NILAI_YA:
        return True
    if nilai in NILAI_TIDAK:
        return False
    raise KonfigurasiError(f"Setelan {kunci} harus ya atau tidak, bukan {nilai!r}")


def baca_kredensial() -> dict[str, str]:
    """Username, password, dan token dari setelan; yang belum diisi bernilai "".

    Sumbernya atur_setelan(), environment, lalu .env. aswaya.yaml dilewati
    karena berkas itu dimaksudkan untuk dibagikan. Nilainya tidak pernah
    dicetak oleh paket ini.
    """
    return {
        kunci: baca_pengaturan(kunci, dari_yaml=False)
        for kunci in ("ASWAYA_USERNAME", "ASWAYA_PASSWORD", "ASWAYA_TOKEN")
    }


def buat_sesi_http() -> requests.Session:
    """Sesi HTTP untuk semua permintaan ke Aswaya.

    Verifikasi sertifikat TLS selalu aktif dan tidak ada setelan untuk
    mematikannya: sesi ini membawa kata sandi dan token.
    """
    sesi = requests.Session()
    sesi.verify = True
    sesi.headers.update({"User-Agent": baca_pengaturan("ASWAYA_USER_AGENT", USER_AGENT_BAWAAN)})
    return sesi


def zona_waktu() -> tzinfo:
    """Zona waktu untuk menampilkan tanggal; bawaannya Asia/Jakarta (WIB).

    Kalau basis data zona waktu tidak tersedia di mesin ini (sebagian Windows
    tanpa paket tzdata), yang dipakai zona waktu lokal mesin.
    """
    nama = baca_pengaturan("ASWAYA_ZONA_WAKTU", ZONA_WAKTU_BAWAAN)
    try:
        return ZoneInfo(nama)
    except (ZoneInfoNotFoundError, ValueError) as galat:
        if nama == ZONA_WAKTU_BAWAAN:
            return datetime.now(timezone.utc).astimezone().tzinfo
        raise KonfigurasiError(f"Zona waktu {nama!r} tidak dikenal; contoh yang benar: Asia/Jakarta") from galat


# --- cache token dan sesi web ---------------------------------------------------


def dir_cache() -> Path:
    """Direktori cache: $XDG_CACHE_HOME/aswaya-mcp, bawaannya ~/.cache/aswaya-mcp."""
    dasar = (os.environ.get("XDG_CACHE_HOME") or "").strip()
    akar = Path(dasar).expanduser() if dasar else Path.home() / ".cache"
    return akar / NAMA_APLIKASI


def berkas_cache(jenis: str, base_url: str, username: str) -> Path:
    """Berkas cache satu jenis (token atau sesi) untuk satu pasangan situs dan username.

    Namanya sidik SHA-256, jadi alamat situs dan username tidak terbaca dari
    daftar isi direktori.
    """
    sidik = hashlib.sha256(f"{base_url.rstrip('/')}\n{username.casefold()}".encode("utf-8")).hexdigest()
    return dir_cache() / f"{jenis}-{sidik[:24]}.json"


def berkas_token(base_url: str, username: str) -> Path:
    """Berkas cache token untuk satu pasangan situs dan username."""
    return berkas_cache("token", base_url, username)


def izin_terbatas(path: Path) -> bool:
    """Apakah berkas atau direktori tertutup bagi grup dan pemakai lain."""
    return stat.S_IMODE(path.stat().st_mode) & 0o077 == 0


def siapkan_dir_cache() -> Path:
    """Buat direktori cache berizin 0700, atau rapatkan izinnya kalau sudah ada."""
    direktori = dir_cache()
    direktori.mkdir(parents=True, exist_ok=True)
    os.chmod(direktori, IZIN_DIR_CACHE)
    return direktori


def baca_cache(jenis: str, base_url: str, username: str) -> dict | None:
    """Isi cache untuk situs dan username ini; None kalau tidak ada atau tidak bisa dipercaya.

    Berkas yang izinnya terbuka bagi pemakai lain dihapus dan tidak dipakai,
    karena isinya mungkin sudah terbaca orang lain. Berkas milik situs atau
    username lain (tabrakan sidik) juga diabaikan.
    """
    berkas = berkas_cache(jenis, base_url, username)
    try:
        if not berkas.is_file():
            return None
        if not izin_terbatas(berkas):
            berkas.unlink(missing_ok=True)
            return None
        isi = json.loads(berkas.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(isi, dict):
        return None
    if isi.get("base_url") != base_url.rstrip("/") or str(isi.get("username", "")).casefold() != username.casefold():
        return None
    return isi


def simpan_cache(jenis: str, base_url: str, username: str, isi: dict) -> Path | None:
    """Simpan isi cache dengan izin 0600; None kalau tidak bisa disimpan dengan aman.

    Berkas ditulis lewat berkas sementara berizin 0600 lalu dipindah, jadi tidak
    pernah ada saat isinya terbaca pemakai lain. Kalau sistem berkasnya tidak
    menegakkan izin itu, berkasnya dihapus lagi dan rahasianya hanya hidup di
    memori.
    """
    data = {
        **isi,
        "base_url": base_url.rstrip("/"),
        "username": username,
        "disimpan": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    try:
        direktori = siapkan_dir_cache()
        tujuan = berkas_cache(jenis, base_url, username)
        pegangan, sementara = tempfile.mkstemp(prefix=f".{jenis}-", dir=direktori)
        try:
            os.chmod(sementara, IZIN_BERKAS_CACHE)
            with os.fdopen(pegangan, "w", encoding="utf-8") as berkas:
                json.dump(data, berkas)
            os.replace(sementara, tujuan)
        except BaseException:
            Path(sementara).unlink(missing_ok=True)
            raise
        if not (izin_terbatas(tujuan) and izin_terbatas(direktori)):
            tujuan.unlink(missing_ok=True)
            return None
        return tujuan
    except OSError:
        return None


def hapus_cache(jenis: str, base_url: str, username: str) -> None:
    """Hapus cache satu jenis untuk situs dan username ini, kalau ada."""
    try:
        berkas_cache(jenis, base_url, username).unlink(missing_ok=True)
    except OSError:
        pass


def baca_token_tersimpan(base_url: str, username: str) -> str:
    """Token dari cache untuk situs dan username ini; "" kalau tidak ada atau tidak bisa dipercaya."""
    return str((baca_cache("token", base_url, username) or {}).get("token") or "")


def simpan_token(base_url: str, username: str, token: str) -> Path | None:
    """Simpan token ke cache dengan izin 0600; None kalau tidak bisa disimpan dengan aman."""
    return simpan_cache("token", base_url, username, {"token": token})


def hapus_token_tersimpan(base_url: str, username: str) -> None:
    """Hapus token di cache untuk situs dan username ini, kalau ada."""
    hapus_cache("token", base_url, username)
