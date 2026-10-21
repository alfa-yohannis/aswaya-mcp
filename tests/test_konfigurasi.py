"""Uji akar proyek, urutan setelan, kunci kredensial, alamat situs, zona waktu, dan cache rahasia."""

from __future__ import annotations

import stat
from pathlib import Path

import pytest
from dotenv import dotenv_values

from aswaya_mcp import konfigurasi
from aswaya_mcp.aswaya_client import KlienAswaya, tentukan_alamat

AKAR_REPO = Path(__file__).resolve().parent.parent
KUNCI_ENV = {"ASWAYA_URL", "ASWAYA_USERNAME", "ASWAYA_PASSWORD", "ASWAYA_TOKEN"}


def mode(path: Path) -> int:
    """Bit izin sebuah berkas atau direktori."""
    return stat.S_IMODE(path.stat().st_mode)


# --- akar proyek -----------------------------------------------------------


def test_berdiri_sendiri_berakar_di_repositori_ini():
    """Mode pertama: repositori di-clone lalu dijalankan apa adanya."""
    konfigurasi.atur_akar_proyek(None)
    akar = konfigurasi.akar_bawaan()

    assert (akar / "pyproject.toml").is_file()
    assert konfigurasi.akar_proyek() == akar


def test_env_proyek_induk_tidak_ikut_terpungut(tmp_path):
    """Direktori di atas akar tidak pernah ditelusuri, jadi kredensial proyek lain tidak terbawa."""
    induk = tmp_path / "induk"
    aplikasi = induk / "app"
    aplikasi.mkdir(parents=True)
    (induk / ".env").write_text("ASWAYA_USERNAME=induk\nASWAYA_PASSWORD=induk\n")
    konfigurasi.atur_akar_proyek(aplikasi)

    assert konfigurasi.berkas_env() == aplikasi / ".env"
    assert konfigurasi.baca_kredensial()["ASWAYA_PASSWORD"] == ""


def test_akar_lewat_environment(tmp_path, monkeypatch):
    konfigurasi.atur_akar_proyek(None)
    monkeypatch.setenv("ASWAYA_AKAR_PROYEK", str(tmp_path))

    assert konfigurasi.akar_proyek() == tmp_path
    assert konfigurasi.dir_data() == tmp_path / "data"


# --- urutan setelan --------------------------------------------------------


def test_setelan_yaml_dibaca():
    akar = konfigurasi.akar_proyek()
    (akar / "aswaya.yaml").write_text("nama_instansi: Kampus Karangan\nbatas_detik: 30\n")

    assert konfigurasi.baca_pengaturan("ASWAYA_NAMA_INSTANSI", "Pradita") == "Kampus Karangan"
    assert konfigurasi.baca_angka("ASWAYA_BATAS_DETIK", 60) == 30


def test_berkas_env_menang_atas_yaml():
    akar = konfigurasi.akar_proyek()
    (akar / "aswaya.yaml").write_text("nama_instansi: Dari YAML\n")
    (akar / ".env").write_text("ASWAYA_NAMA_INSTANSI=Dari ENV\n")

    assert konfigurasi.baca_pengaturan("ASWAYA_NAMA_INSTANSI") == "Dari ENV"


def test_environment_menang_atas_berkas_env(monkeypatch):
    (konfigurasi.akar_proyek() / ".env").write_text("ASWAYA_NAMA_INSTANSI=Dari ENV\n")
    monkeypatch.setenv("ASWAYA_NAMA_INSTANSI", "Dari environment")

    assert konfigurasi.baca_pengaturan("ASWAYA_NAMA_INSTANSI") == "Dari environment"


def test_setelan_dari_kode_menang_atas_environment(monkeypatch):
    monkeypatch.setenv("ASWAYA_NAMA_INSTANSI", "Dari environment")
    konfigurasi.atur_setelan(nama_instansi="Dari kode")

    assert konfigurasi.baca_pengaturan("ASWAYA_NAMA_INSTANSI") == "Dari kode"


def test_setelan_dari_kode_menerima_kedua_gaya_nama():
    konfigurasi.atur_setelan(ASWAYA_URL="https://a.ac.id")
    assert konfigurasi.baca_pengaturan("ASWAYA_URL") == "https://a.ac.id"

    konfigurasi.atur_setelan(url="https://b.ac.id")
    assert konfigurasi.baca_pengaturan("ASWAYA_URL") == "https://b.ac.id"


def test_angka_tidak_masuk_akal_ditolak_jelas(monkeypatch):
    monkeypatch.setenv("ASWAYA_BATAS_DETIK", "selama mungkin")

    with pytest.raises(konfigurasi.KonfigurasiError, match="harus berupa angka"):
        konfigurasi.baca_angka("ASWAYA_BATAS_DETIK", 60)


def test_saklar_ya_tidak(monkeypatch):
    monkeypatch.setenv("ASWAYA_SIMPAN_CACHE", "tidak")
    assert konfigurasi.baca_ya_tidak("ASWAYA_SIMPAN_CACHE", True) is False

    monkeypatch.setenv("ASWAYA_SIMPAN_CACHE", "mungkin")
    with pytest.raises(konfigurasi.KonfigurasiError, match="ya atau tidak"):
        konfigurasi.baca_ya_tidak("ASWAYA_SIMPAN_CACHE", True)


# --- kredensial ------------------------------------------------------------


def test_kredensial_dibaca_dengan_kunci_persis_dari_env():
    (konfigurasi.akar_proyek() / ".env").write_text(
        "ASWAYA_URL=https://aswaya.pradita.ac.id\n"
        "ASWAYA_USERNAME=dosen@contoh.ac.id\n"
        "ASWAYA_PASSWORD=sandi-karangan\n"
        "ASWAYA_TOKEN=token-karangan\n"
    )

    assert konfigurasi.baca_kredensial() == {
        "ASWAYA_USERNAME": "dosen@contoh.ac.id",
        "ASWAYA_PASSWORD": "sandi-karangan",
        "ASWAYA_TOKEN": "token-karangan",
    }


def test_isian_kosong_dianggap_belum_diisi(monkeypatch):
    """`ASWAYA_PASSWORD=` sama dengan tidak menulis barisnya, dan environment kosong tidak menutupi .env."""
    (konfigurasi.akar_proyek() / ".env").write_text(
        "ASWAYA_USERNAME=dosen@contoh.ac.id\nASWAYA_PASSWORD=\nASWAYA_TOKEN=  # diisi pemakai\n"
    )
    monkeypatch.setenv("ASWAYA_USERNAME", "")

    kredensial = konfigurasi.baca_kredensial()
    assert kredensial["ASWAYA_PASSWORD"] == ""
    assert kredensial["ASWAYA_TOKEN"] == ""
    assert kredensial["ASWAYA_USERNAME"] == "dosen@contoh.ac.id"


def test_kredensial_tidak_pernah_dibaca_dari_yaml():
    """aswaya.yaml dimaksudkan untuk dibagikan, jadi kredensial di sana diabaikan."""
    (konfigurasi.akar_proyek() / "aswaya.yaml").write_text("username: dosen\npassword: bocor\ntoken: bocor\n")

    assert konfigurasi.baca_kredensial() == {"ASWAYA_USERNAME": "", "ASWAYA_PASSWORD": "", "ASWAYA_TOKEN": ""}


def test_env_contoh_memuat_kunci_yang_sama_tanpa_rahasia():
    """.env.contoh memakai empat kunci yang dibaca paket ini; password dan token dibiarkan kosong."""
    contoh = dotenv_values(AKAR_REPO / ".env.contoh")

    assert set(contoh) == KUNCI_ENV
    assert contoh["ASWAYA_URL"] == "https://aswaya.pradita.ac.id"
    assert not contoh["ASWAYA_PASSWORD"]
    assert not contoh["ASWAYA_TOKEN"]


def test_gitignore_mengabaikan_rahasia_dan_hasil_kerja():
    isi = (AKAR_REPO / ".gitignore").read_text().splitlines()

    for pola in (".env", ".venv", "data/", "token-*.json", "sesi-*.json", ".cache/"):
        assert pola in isi
    assert "!.env.contoh" in isi


def test_kesalahan_setelan_bukan_systemexit():
    """Pustaka tidak boleh menghentikan program yang memakainya."""
    konfigurasi.atur_setelan(batas_detik="sebentar")

    with pytest.raises(Exception) as galat:
        konfigurasi.baca_angka("ASWAYA_BATAS_DETIK", 60)
    assert isinstance(galat.value, konfigurasi.KonfigurasiError)


# --- sesi HTTP, alamat, zona waktu ------------------------------------------


def test_sesi_http_selalu_memverifikasi_tls():
    assert konfigurasi.buat_sesi_http().verify is True


def test_uji_tidak_bisa_menyentuh_jaringan():
    """Pagar di conftest: sesi HTTP sungguhan diblokir selama uji (.invalid tidak pernah ada)."""
    with pytest.raises(AssertionError, match="jaringan sungguhan"):
        konfigurasi.buat_sesi_http().get("https://contoh.invalid/")


def test_tidak_ada_kode_yang_mematikan_verifikasi_tls():
    sumber = "".join(berkas.read_text(encoding="utf-8") for berkas in Path(konfigurasi.__file__).parent.glob("*.py"))
    assert "verify=False" not in sumber.replace(" ", "")


def test_alamat_bawaan_aswaya():
    assert tentukan_alamat() == "https://aswaya.pradita.ac.id"


def test_alamat_dari_env_dan_subdirektori_dipertahankan(monkeypatch):
    monkeypatch.setenv("ASWAYA_URL", "https://kampus-karangan.ac.id/lms/")

    assert tentukan_alamat() == "https://kampus-karangan.ac.id/lms"


def test_alamat_harus_https():
    with pytest.raises(konfigurasi.KonfigurasiError, match="https"):
        KlienAswaya(base_url="http://aswaya.pradita.ac.id")


def test_zona_waktu_bawaan_wib():
    assert str(konfigurasi.zona_waktu()) == "Asia/Jakarta"


def test_zona_waktu_tidak_dikenal_ditolak(monkeypatch):
    monkeypatch.setenv("ASWAYA_ZONA_WAKTU", "Mars/Olympus")

    with pytest.raises(konfigurasi.KonfigurasiError, match="Zona waktu"):
        konfigurasi.zona_waktu()


# --- cache token dan sesi -----------------------------------------------------


def test_dir_cache_mengikuti_xdg_cache_home(tmp_path):
    assert konfigurasi.dir_cache() == tmp_path / "cache" / "aswaya-mcp"


def test_dir_cache_bawaan_di_home(tmp_path, monkeypatch):
    monkeypatch.delenv("XDG_CACHE_HOME")
    monkeypatch.setenv("HOME", str(tmp_path / "rumah"))

    assert konfigurasi.dir_cache() == tmp_path / "rumah" / ".cache" / "aswaya-mcp"


def test_token_disimpan_berizin_0600_di_direktori_0700(dir_cache):
    berkas = konfigurasi.simpan_token("https://aswaya.pradita.ac.id", "dosen@contoh.ac.id", "token-karangan")

    assert berkas is not None and berkas.parent == dir_cache
    assert mode(berkas) == 0o600
    assert mode(dir_cache) == 0o700
    assert konfigurasi.baca_token_tersimpan("https://aswaya.pradita.ac.id", "Dosen@Contoh.ac.id") == "token-karangan"


def test_nama_berkas_cache_tidak_membocorkan_situs_atau_username(dir_cache):
    berkas = konfigurasi.simpan_token("https://aswaya.pradita.ac.id", "dosen@contoh.ac.id", "token-karangan")

    assert "dosen" not in berkas.name and "aswaya" not in berkas.name
    assert berkas.name.startswith("token-")


def test_token_milik_username_lain_tidak_terbaca():
    konfigurasi.simpan_token("https://aswaya.pradita.ac.id", "dosen@contoh.ac.id", "token-karangan")

    assert konfigurasi.baca_token_tersimpan("https://aswaya.pradita.ac.id", "lain@contoh.ac.id") == ""
    assert konfigurasi.baca_token_tersimpan("https://lms.lain.ac.id", "dosen@contoh.ac.id") == ""


def test_cache_yang_terbuka_bagi_pemakai_lain_dibuang():
    berkas = konfigurasi.simpan_token("https://aswaya.pradita.ac.id", "dosen@contoh.ac.id", "token-karangan")
    berkas.chmod(0o644)

    assert konfigurasi.baca_token_tersimpan("https://aswaya.pradita.ac.id", "dosen@contoh.ac.id") == ""
    assert not berkas.exists()


def test_cache_tidak_disimpan_di_sistem_berkas_tanpa_izin(monkeypatch, dir_cache):
    """Di NTFS dan sejenisnya chmod tidak berlaku, jadi rahasia hanya hidup di memori."""
    monkeypatch.setattr(konfigurasi, "izin_terbatas", lambda path: False)

    assert konfigurasi.simpan_token("https://aswaya.pradita.ac.id", "dosen@contoh.ac.id", "token-karangan") is None
    assert not list(dir_cache.glob("token-*.json"))


def test_hapus_token_tersimpan():
    konfigurasi.simpan_token("https://aswaya.pradita.ac.id", "dosen@contoh.ac.id", "token-karangan")
    konfigurasi.hapus_token_tersimpan("https://aswaya.pradita.ac.id", "dosen@contoh.ac.id")

    assert konfigurasi.baca_token_tersimpan("https://aswaya.pradita.ac.id", "dosen@contoh.ac.id") == ""
