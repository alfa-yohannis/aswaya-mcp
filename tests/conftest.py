"""Perkakas bersama untuk unit test Aswaya.

Seluruh test berjalan tanpa jaringan: Aswaya digantikan SitusTiruan yang menjawab
seperti Moodle 4.1 (token.php, server.php, pluginfile, upload.php,
service-nologin.php, halaman login, changenumsections.php, dan AJAX
service.php), sehingga bisa dijalankan kapan saja tanpa kredensial. Nama dosen,
mahasiswa, kursus, NIM, email, token, dan kata sandi di seluruh berkas uji
sengaja dikarang.
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from zoneinfo import ZoneInfo

import pytest
import requests

AKAR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AKAR))

from aswaya_mcp import aswaya_client, konfigurasi, sesi_web  # noqa: E402

SITUS = "https://aswaya.pradita.ac.id"
HOST = "aswaya.pradita.ac.id"
USERNAME_UJI = "dosen.karangan@pradita.ac.id"
PASSWORD_UJI = "sandi-karangan-123"
TOKEN_UJI = "0123456789abcdef0123456789abcdef"
TOKEN_LAIN = "fedcba9876543210fedcba9876543210"
PRIVATETOKEN_UJI = "privat-karangan-jangan-disimpan"
KUNCI_PRIBADI_UJI = "kunci-akses-pribadi-karangan"
SESSKEY_UJI = "SesKarangan01"
LOGINTOKEN_UJI = "logintokenkarangan"
USERID_DOSEN = 7
KURSUS_WEB = 5515
KURSUS_SECTION = 5026
KURSUS_LAMA = 4001
TUGAS_1 = 77
TUGAS_REFLEKSI = 78
FORUM_PENGUMUMAN = 501
FORUM_UMUM = 502
WIB = ZoneInfo("Asia/Jakarta")


def detik(teks: str) -> int:
    """'2026-09-01 08:00' (WIB) sebagai waktu Unix."""
    return int(datetime.strptime(teks, "%Y-%m-%d %H:%M").replace(tzinfo=WIB).timestamp())


# --- data Moodle karangan ------------------------------------------------------

FUNGSI_DASAR = [
    "core_webservice_get_site_info",
    "core_enrol_get_users_courses",
    "core_course_get_categories",
    "core_course_get_contents",
    "core_course_get_courses_by_field",
    "core_course_get_course_module_by_instance",
    "core_enrol_get_enrolled_users",
    "core_user_get_users_by_field",
    "mod_assign_get_assignments",
    "mod_assign_get_submissions",
    "mod_assign_get_grades",
    "mod_assign_list_participants",
    "mod_assign_get_participant",
    "mod_assign_save_grade",
    "mod_assign_view_assign",
    "gradereport_user_get_grade_items",
    "mod_forum_get_forums_by_courses",
    "mod_forum_get_forum_discussions",
    "mod_forum_add_discussion",
    "core_calendar_get_action_events_by_timesort",
    "core_calendar_get_action_events_by_course",
    "core_message_send_instant_messages",
    "tool_mobile_get_autologin_key",
]


def berkas_moodle(nama: str, ukuran: int, jenis: str, path_area: str) -> dict:
    """Satu entri berkas seperti di jawaban Moodle, dengan fileurl webservice tanpa token."""
    return {
        "type": "file",
        "filename": nama,
        "filepath": "/",
        "filesize": ukuran,
        "fileurl": f"{SITUS}/webservice/pluginfile.php/{path_area}/{nama}",
        "timemodified": detik("2026-09-02 10:00"),
        "mimetype": jenis,
    }


def data_awal() -> dict:
    """Isi Moodle karangan; setiap uji mendapat salinan segar."""
    return {
        "kursus": {
            KURSUS_WEB: {
                "id": KURSUS_WEB, "shortname": "IF140303-SRP", "fullname": "Pengembangan Aplikasi Web (Serpong)",
                "displayname": "Pengembangan Aplikasi Web (Serpong)", "category": 3, "visible": 1,
                "startdate": detik("2026-09-01 00:00"), "enddate": detik("2027-01-31 00:00"), "format": "topics",
            },
            KURSUS_SECTION: {
                "id": KURSUS_SECTION, "shortname": "IF140201", "fullname": "Pemrograman Berorientasi Objek",
                "displayname": "Pemrograman Berorientasi Objek", "category": 3, "visible": 1,
                "startdate": detik("2026-09-01 00:00"), "enddate": 0, "format": "topics",
            },
            KURSUS_LAMA: {
                "id": KURSUS_LAMA, "shortname": "SI120101", "fullname": "Basis Data &amp; SQL",
                "displayname": "Basis Data & SQL", "category": 4, "visible": 0,
                "startdate": detik("2025-02-01 00:00"), "enddate": detik("2025-06-30 00:00"), "format": "weeks",
            },
        },
        "kategori": {3: "Informatika", 4: "Sistem Informasi"},
        "section": {
            KURSUS_WEB: [
                {"id": 9000, "section": 0, "name": "Umum", "visible": 1, "summary": "<p>Selamat datang di kelas.</p>",
                 "modules": [
                     {"id": 1200, "name": "Pengumuman", "modname": "forum", "instance": FORUM_PENGUMUMAN, "visible": 1,
                      "url": f"{SITUS}/mod/forum/view.php?id=1200"},
                 ]},
                {"id": 9001, "section": 1, "name": "Pertemuan 1", "visible": 1, "summary": "",
                 "modules": [
                     {"id": 1233, "name": "Slide HTML Dasar", "modname": "resource", "instance": 61, "visible": 1,
                      "url": f"{SITUS}/mod/resource/view.php?id=1233",
                      "description": "<p>Bacaan <b>wajib</b> sebelum kelas.</p>",
                      "contents": [berkas_moodle("slide-html.pdf", 245760, "application/pdf", "88/mod_resource/content/1")]},
                     {"id": 1234, "name": "Tugas 1: Halaman Statis", "modname": "assign", "instance": TUGAS_1, "visible": 1,
                      "url": f"{SITUS}/mod/assign/view.php?id=1234",
                      "dates": [{"label": "Due:", "timestamp": detik("2026-09-15 23:59")}]},
                 ]},
            ],
            KURSUS_SECTION: [
                {"id": 8000 + nomor, "section": nomor, "name": "Umum" if nomor == 0 else f"Session {nomor:02d}",
                 "visible": 1, "summary": "", "modules": [{"id": 3000 + nomor, "name": f"Materi {nomor}", "modname": "page",
                                                           "instance": 900 + nomor, "visible": 1}] if nomor else []}
                for nomor in range(0, 8)
            ],
            KURSUS_LAMA: [{"id": 7000, "section": 0, "name": "General", "visible": 1, "summary": "", "modules": []}],
        },
        "pengguna": {
            USERID_DOSEN: {"id": USERID_DOSEN, "fullname": "Clark Kent", "email": "clark.kent@contoh.ac.id", "idnumber": "D-001"},
            101: {"id": 101, "fullname": "Peter Parker", "email": "peter.parker@contoh.ac.id", "idnumber": "2026100001"},
            102: {"id": 102, "fullname": "Diana Prince", "email": "diana.prince@contoh.ac.id", "idnumber": "2026100002"},
            103: {"id": 103, "fullname": "Bruce Banner", "email": "bruce.banner@contoh.ac.id", "idnumber": "2026100003"},
            104: {"id": 104, "fullname": "Natasha Romanoff", "email": "natasha.r@contoh.ac.id", "idnumber": "2026100004"},
        },
        "peserta": {
            KURSUS_WEB: [
                (USERID_DOSEN, "editingteacher", "Dosen", []),
                (101, "student", "Mahasiswa", ["Kelas A"]),
                (102, "student", "Mahasiswa", ["Kelas A"]),
                (103, "student", "Mahasiswa", ["Kelas B"]),
                (104, "student", "Mahasiswa", ["Kelas B"]),
            ],
        },
        "tugas": {
            KURSUS_WEB: [
                {"id": TUGAS_1, "cmid": 1234, "course": KURSUS_WEB, "name": "Tugas 1: Halaman Statis", "grade": 100,
                 "duedate": detik("2026-09-15 23:59"), "allowsubmissionsfromdate": detik("2026-09-01 08:00"),
                 "cutoffdate": detik("2026-09-17 23:59"), "gradingduedate": detik("2026-09-22 23:59"),
                 "teamsubmission": 0, "intro": "<p>Buat halaman profil dengan HTML.</p>",
                 "configs": [{"plugin": "comments", "subtype": "assignfeedback", "name": "enabled", "value": "1"}]},
                {"id": TUGAS_REFLEKSI, "cmid": 1235, "course": KURSUS_WEB, "name": "Refleksi Mingguan", "grade": 0,
                 "duedate": 0, "allowsubmissionsfromdate": 0, "cutoffdate": 0, "gradingduedate": 0,
                 "teamsubmission": 0, "intro": "", "configs": []},
            ],
        },
        "pengumpulan": {
            TUGAS_1: [
                {"id": 1, "userid": 101, "attemptnumber": 0, "status": "submitted", "timemodified": detik("2026-09-14 21:30"),
                 "gradingstatus": "graded",
                 "plugins": [
                     {"type": "file", "name": "File submissions", "fileareas": [{"area": "submission_files", "files": [
                         berkas_moodle("profil-peter.zip", 10240, "application/zip", "90/assignsubmission_file/submission_files/1")]}]},
                     {"type": "onlinetext", "name": "Online text", "editorfields": [
                         {"name": "onlinetext", "description": "Online text", "text": "<p>Tautan repo saya ada di berkas.</p>", "format": 1}]},
                 ]},
                {"id": 2, "userid": 102, "attemptnumber": 0, "status": "draft", "timemodified": detik("2026-09-15 20:00"),
                 "gradingstatus": "notgraded", "plugins": []},
            ],
        },
        "nilai_tugas": {
            TUGAS_1: [
                {"id": 11, "userid": 101, "attemptnumber": 0, "grade": "85.00000", "timemodified": detik("2026-09-18 09:00"), "grader": USERID_DOSEN},
                {"id": 12, "userid": 102, "attemptnumber": 0, "grade": "-1.00000", "timemodified": detik("2026-09-18 09:05"), "grader": USERID_DOSEN},
            ],
        },
        "forum": {
            KURSUS_WEB: [
                {"id": FORUM_PENGUMUMAN, "course": KURSUS_WEB, "type": "news", "name": "Pengumuman", "intro": "",
                 "cmid": 1200, "numdiscussions": 1, "cancreatediscussions": True},
                {"id": FORUM_UMUM, "course": KURSUS_WEB, "type": "general", "name": "Diskusi Umum",
                 "intro": "<p>Tanya jawab materi.</p>", "cmid": 1201, "numdiscussions": 2, "cancreatediscussions": True},
            ],
            KURSUS_SECTION: [],
        },
        "diskusi": {
            FORUM_UMUM: [
                {"id": 3101, "discussion": 301, "name": "Tanya soal CSS", "subject": "Tanya soal CSS", "userid": 101,
                 "userfullname": "Peter Parker", "created": detik("2026-09-10 10:00"), "timemodified": detik("2026-09-11 08:00"),
                 "numreplies": 2, "numunread": 1, "pinned": False, "locked": False,
                 "message": "<p>Bagaimana cara <code>flexbox</code>?</p>", "attachments": []},
                {"id": 3102, "discussion": 302, "name": "Kelompok proyek", "subject": "Kelompok proyek", "userid": 102,
                 "userfullname": "Diana Prince", "created": detik("2026-09-09 10:00"), "timemodified": detik("2026-09-09 10:00"),
                 "numreplies": 0, "numunread": 0, "pinned": True, "locked": False, "message": "<p>Daftar kelompok.</p>",
                 "attachments": [{"filename": "kelompok.xlsx", "filesize": 2048,
                                  "fileurl": f"{SITUS}/webservice/pluginfile.php/91/mod_forum/attachment/3102/kelompok.xlsx"}]},
            ],
        },
        "kegiatan": [
            {"id": 601, "name": "Tugas 1: Halaman Statis perlu dinilai", "timesort": detik("2026-09-22 23:59"),
             "course": {"id": KURSUS_WEB, "fullname": "Pengembangan Aplikasi Web (Serpong)"}, "modulename": "assign",
             "activityname": "Tugas 1: Halaman Statis", "eventtype": "gradingdue", "overdue": False,
             "url": f"{SITUS}/mod/assign/view.php?id=1234",
             "action": {"name": "Nilai", "url": f"{SITUS}/mod/assign/view.php?id=1234&action=grading", "itemcount": 1, "actionable": True}},
            {"id": 602, "name": "Kuis 1 ditutup", "timesort": detik("2026-09-25 12:00"),
             "course": {"id": KURSUS_SECTION, "fullname": "Pemrograman Berorientasi Objek"}, "modulename": "quiz",
             "activityname": "Kuis 1", "eventtype": "close", "overdue": False, "url": f"{SITUS}/mod/quiz/view.php?id=4000",
             "action": {"name": "Lihat", "url": f"{SITUS}/mod/quiz/view.php?id=4000", "itemcount": 0, "actionable": True}},
        ],
        "item_nilai": {
            KURSUS_WEB: [
                {"id": 401, "itemname": "Tugas 1: Halaman Statis", "itemtype": "mod", "itemmodule": "assign", "cmid": 1234, "grademax": 100},
                {"id": 402, "itemname": "Kuis HTML", "itemtype": "mod", "itemmodule": "quiz", "cmid": 1240, "grademax": 10},
                {"id": 400, "itemname": None, "itemtype": "course", "itemmodule": None, "cmid": None, "grademax": 100},
            ],
        },
        "nilai_kursus": {
            KURSUS_WEB: {101: {401: 85.0, 402: 9.0, 400: 47.0}, 102: {401: None, 402: 7.5, 400: 7.5}},
        },
    }


# --- jawaban dan situs tiruan --------------------------------------------------


class JawabanTiruan:
    """Pengganti requests.Response seperlunya saja."""

    def __init__(self, url, status_code=200, teks="", lokasi="", jenis="text/html; charset=utf-8", isi=None, header=None):
        """Jawaban dengan alamat, status, isi teks atau biner, dan (kalau pengalihan) Location."""
        self.url = url
        self.status_code = status_code
        self.text = teks
        self.content = isi if isi is not None else teks.encode("utf-8")
        self.headers = {"Content-Type": jenis, **(header or {})}
        if lokasi:
            self.headers["Location"] = lokasi
        self.ditutup = False

    @property
    def is_redirect(self) -> bool:
        """Sama dengan requests: ada Location dan statusnya kode pengalihan."""
        return "Location" in self.headers and self.status_code in (301, 302, 303, 307, 308)

    def json(self):
        """Isi sebagai JSON; ValueError kalau bukan JSON, seperti requests."""
        return json.loads(self.text)

    def iter_content(self, chunk_size=1):
        """Isi biner per potongan."""
        for awal in range(0, len(self.content), chunk_size):
            yield self.content[awal:awal + chunk_size]

    def close(self):
        """Tandai jawaban sudah ditutup."""
        self.ditutup = True


def jawaban_json(url: str, data, status_code: int = 200) -> JawabanTiruan:
    """Jawaban JSON seperti server.php dan token.php."""
    return JawabanTiruan(url, status_code, teks=json.dumps(data), jenis="application/json; charset=utf-8")


def susun_parameter(pasangan) -> dict:
    """Isian form ala Moodle kembali ke bentuk bersarang: options[0][name] -> {"options": [{"name": ...}]}."""
    hasil: dict = {}
    for kunci, nilai in (pasangan.items() if isinstance(pasangan, dict) else pasangan):
        bagian = re.findall(r"[^\[\]]+", kunci)
        sasaran = hasil
        for nama in bagian[:-1]:
            sasaran = sasaran.setdefault(nama, {})
        sasaran[bagian[-1]] = nilai
    return jadikan_daftar(hasil)


def jadikan_daftar(nilai):
    """Dict yang semua kuncinya angka menjadi list, seperti PHP membaca isian form."""
    if isinstance(nilai, dict):
        nilai = {kunci: jadikan_daftar(isi) for kunci, isi in nilai.items()}
        if nilai and all(kunci.isdigit() for kunci in nilai):
            return [nilai[kunci] for kunci in sorted(nilai, key=int)]
    return nilai


def galat_moodle(kode: str, pesan: str, jenis: str = "moodle_exception") -> dict:
    """Bentuk exception Moodle di jawaban server.php."""
    return {"exception": jenis, "errorcode": kode, "message": pesan}


class SitusTiruan:
    """Aswaya tiruan yang menjawab seperti Moodle 4.1, tanpa jaringan.

    Dipasang menggantikan sesi HTTP klien dan sesi web. Setiap permintaan
    dicatat di `permintaan`, dan permintaan ke host lain langsung menggagalkan uji.
    """

    def __init__(self):
        """Situs dalam keadaan belum ada token maupun sesi web, dengan data karangan segar."""
        self.verify = True
        self.headers = {}
        self.cookies = requests.cookies.RequestsCookieJar()
        self.data = data_awal()
        self.username_benar = USERNAME_UJI
        self.password_benar = PASSWORD_UJI
        self.token_berlaku = {TOKEN_UJI}
        self.token_berikutnya = TOKEN_UJI
        self.token_login_berlaku = True  # False: token baru dari token.php langsung ditolak server.php
        self.fungsi = list(FUNGSI_DASAR)
        self.permintaan: list[dict] = []
        self.galat_berikutnya: dict[str, dict] = {}  # wsfunction -> exception sekali pakai
        self.jaringan_putus: set[str] = set()  # wsfunction yang permintaannya gagal di jaringan
        self.pesan_gagal_login = "Invalid login, please try again"
        # sesi web
        self.sesi_web_aktif: str | None = None
        self.nomor_sesi = 0
        self.sesskey = SESSKEY_UJI
        self.captcha = False
        self.hambatan_login = ""
        self.maks_section = 52
        self.ajax_galat_berikutnya: list[str] = []
        self.id_section_berikutnya = 8100
        self.berkas = {
            "/webservice/pluginfile.php/88/mod_resource/content/1/slide-html.pdf": (b"%PDF-1.4 slide karangan", "application/pdf"),
            "/webservice/pluginfile.php/90/assignsubmission_file/submission_files/1/profil-peter.zip": (b"PK zip karangan", "application/zip"),
        }
        self.pengalihan_berkas: dict[str, str] = {}
        self.berkas_putus = False  # True: unduhan berkas gagal di jaringan

    def sebagai_pabrik(self) -> "SitusTiruan":
        """Pengganti buat_sesi_http(): selalu mengembalikan situs ini sendiri."""
        return self

    # --- pencatatan --------------------------------------------------------

    def jumlah(self, metode: str, path: str, fungsi: str = "") -> int:
        """Berapa kali sebuah path (dan wsfunction, kalau disebut) diminta dengan metode tertentu."""
        return sum(
            1 for satu in self.permintaan
            if satu["metode"] == metode and satu["path"] == path and (not fungsi or satu["fungsi"] == fungsi)
        )

    def panggilan(self, fungsi: str) -> list[dict]:
        """Parameter (sudah disusun ulang) setiap panggilan server.php untuk wsfunction ini."""
        return [satu["parameter"] for satu in self.permintaan if satu["fungsi"] == fungsi]

    # --- pintu masuk -------------------------------------------------------

    def request(self, method, url, params=None, data=None, json=None, files=None, headers=None,
                timeout=None, allow_redirects=True, stream=False):
        """Jawab satu permintaan seperti Aswaya."""
        bagian = urlsplit(url)
        assert bagian.netloc == HOST, f"permintaan keluar Aswaya: {url}"
        assert bagian.scheme == "https", f"permintaan tanpa https: {url}"
        assert allow_redirects is False, "pengalihan harus diikuti klien sendiri"
        query = dict(parse_qsl(bagian.query))
        query.update({kunci: str(nilai) for kunci, nilai in (params or {}).items()})
        alamat = urlunsplit((bagian.scheme, bagian.netloc, bagian.path, urlencode(query), ""))
        isian = list(data.items()) if isinstance(data, dict) else list(data or [])
        catatan = {"metode": method, "path": bagian.path, "url": url, "query": query, "isian": isian,
                   "json": json, "files": files, "fungsi": "", "parameter": {}}
        self.permintaan.append(catatan)

        path = bagian.path
        if path == "/login/token.php" and method == "POST":
            return self.token_php(alamat, dict(isian))
        if path == "/webservice/rest/server.php" and method == "POST":
            return self.server_php(alamat, isian, catatan)
        if path.startswith("/webservice/pluginfile.php/"):
            return self.pluginfile(alamat, path, query)
        if path == "/webservice/upload.php" and method == "POST":
            return self.upload_php(alamat, dict(isian), files)
        if path == "/lib/ajax/service-nologin.php":
            return jawaban_json(alamat, [{"error": False, "data": {
                "wwwroot": SITUS, "sitename": "Aswaya Contoh", "enablewebservices": 1, "enablemobilewebservice": 1,
                "maintenanceenabled": 0, "typeoflogin": 1, "authloginviaemail": 1}}])
        return self.halaman_web(method, alamat, path, query, dict(isian), json)

    # --- web service -------------------------------------------------------

    def token_php(self, alamat: str, isian: dict):
        """token.php: kredensial benar dibalas token dan privatetoken, salah dibalas invalidlogin."""
        if isian.get("service") != "moodle_mobile_app":
            return jawaban_json(alamat, {"error": "Web service is not available", "errorcode": "servicenotavailable"})
        if isian.get("username") == self.username_benar and isian.get("password") == self.password_benar:
            if self.token_login_berlaku:
                self.token_berlaku.add(self.token_berikutnya)
            return jawaban_json(alamat, {"token": self.token_berikutnya, "privatetoken": PRIVATETOKEN_UJI})
        return jawaban_json(alamat, {"error": self.pesan_gagal_login, "errorcode": "invalidlogin",
                                     "stacktrace": None, "debuginfo": None, "reproductionlink": None})

    def server_php(self, alamat: str, isian: list, catatan: dict):
        """server.php: periksa token, lalu jalankan wsfunction tiruan."""
        isi = dict(isian)
        fungsi = isi.get("wsfunction", "")
        parameter = susun_parameter([(k, v) for k, v in isian if k not in ("wstoken", "wsfunction", "moodlewsrestformat")])
        catatan["fungsi"], catatan["parameter"] = fungsi, parameter
        if fungsi in self.jaringan_putus:
            raise requests.ConnectionError(f"Connection aborted while sending to {alamat}")
        if isi.get("wstoken") not in self.token_berlaku:
            return jawaban_json(alamat, galat_moodle("invalidtoken", "Invalid token - token not found"))
        if isi.get("moodlewsrestformat") != "json":
            return JawabanTiruan(alamat, teks="<xml/>", jenis="application/xml")
        if fungsi in self.galat_berikutnya:
            return jawaban_json(alamat, self.galat_berikutnya.pop(fungsi))
        if fungsi not in self.fungsi:
            return jawaban_json(alamat, galat_moodle("accessexception", "Access control exception", "webservice_access_exception"))
        penangan = getattr(self, "ws_" + fungsi, None)
        if penangan is None:
            return jawaban_json(alamat, galat_moodle("invalidrecord", "Can't find data record in database table external_functions."))
        return jawaban_json(alamat, penangan(parameter))

    def ws_core_webservice_get_site_info(self, parameter):
        """Info situs, termasuk kunci akses pribadi yang tidak boleh ikut keluar."""
        return {
            "sitename": "Aswaya Contoh", "siteurl": SITUS, "username": "dosen.karangan", "fullname": "Clark Kent",
            "userid": USERID_DOSEN, "release": "4.1.9 (Build: 20240212)", "version": "2022112809",
            "userprivateaccesskey": KUNCI_PRIBADI_UJI,
            "functions": [{"name": nama, "version": "2022112809"} for nama in self.fungsi],
        }

    def ws_core_enrol_get_users_courses(self, parameter):
        """Kursus yang diikuti userid itu."""
        assert int(parameter["userid"]) == USERID_DOSEN
        return [dict(kursus) for kursus in self.data["kursus"].values()]

    def ws_core_course_get_categories(self, parameter):
        """Kategori untuk kriteria ids."""
        ids = [int(nomor) for nomor in parameter["criteria"][0]["value"].split(",")]
        return [{"id": nomor, "name": self.data["kategori"][nomor]} for nomor in ids if nomor in self.data["kategori"]]

    def ws_core_course_get_contents(self, parameter):
        """Section dan modul kursus; excludecontents membuang isi berkas modul."""
        tanpa_isi = any(opsi["name"] == "excludecontents" and opsi["value"] == "1" for opsi in parameter.get("options", []))
        hasil = []
        for section in self.data["section"].get(int(parameter["courseid"]), []):
            salinan = {**section, "modules": [dict(modul) for modul in section["modules"]]}
            if tanpa_isi:
                for modul in salinan["modules"]:
                    modul.pop("contents", None)
            hasil.append(salinan)
        return hasil

    def ws_core_course_get_courses_by_field(self, parameter):
        """Kursus berdasarkan id, termasuk format dan opsi formatnya."""
        kursus = self.data["kursus"].get(int(parameter["value"]))
        if kursus is None:
            return {"courses": [], "warnings": []}
        return {"courses": [{**kursus, "courseformatoptions": [{"name": "hiddensections", "value": 0}]}], "warnings": []}

    def ws_core_course_get_course_module_by_instance(self, parameter):
        """Modul kursus dari instance tugas."""
        for kursus_id, daftar in self.data["tugas"].items():
            for tugas in daftar:
                if tugas["id"] == int(parameter["instance"]):
                    return {"cm": {"id": tugas["cmid"], "course": kursus_id, "modname": "assign", "instance": tugas["id"]}, "warnings": []}
        return galat_moodle("invalidrecord", "Can't find data record in database table course_modules.")

    def ws_core_enrol_get_enrolled_users(self, parameter):
        """Peserta kursus, hanya dengan bidang yang diminta lewat userfields."""
        bidang = {"id", "fullname"}
        for opsi in parameter.get("options", []):
            if opsi["name"] == "userfields":
                bidang |= set(opsi["value"].split(","))
        hasil = []
        for user_id, peran, nama_peran, grup in self.data["peserta"].get(int(parameter["courseid"]), []):
            lengkap = {**self.data["pengguna"][user_id],
                       "roles": [{"roleid": 5, "name": nama_peran, "shortname": peran, "sortorder": 0}],
                       "groups": [{"id": 70 + nomor, "name": nama} for nomor, nama in enumerate(grup)],
                       "lastaccess": detik("2026-10-20 08:15"), "lastcourseaccess": detik("2026-10-19 20:00") if user_id != 104 else 0}
            hasil.append({kunci: nilai for kunci, nilai in lengkap.items() if kunci in bidang})
        return hasil

    def ws_core_user_get_users_by_field(self, parameter):
        """Pengguna berdasarkan id."""
        assert parameter["field"] == "id"
        return [dict(self.data["pengguna"][int(nomor)]) for nomor in parameter["values"] if int(nomor) in self.data["pengguna"]]

    def ws_mod_assign_get_assignments(self, parameter):
        """Tugas per kursus; kursus yang tidak diikuti menjadi peringatan."""
        kursus, peringatan = [], []
        for nomor in parameter.get("courseids", []):
            nomor = int(nomor)
            if nomor in self.data["tugas"]:
                kursus.append({"id": nomor, "fullname": self.data["kursus"][nomor]["fullname"],
                               "assignments": [dict(tugas) for tugas in self.data["tugas"][nomor]]})
            else:
                peringatan.append({"item": "course", "itemid": nomor, "warningcode": "1",
                                   "message": "No access rights in course context"})
        return {"courses": kursus, "warnings": peringatan}

    def ws_mod_assign_get_submissions(self, parameter):
        """Pengumpulan per tugas."""
        return {"assignments": [{"assignmentid": int(nomor), "submissions": self.data["pengumpulan"].get(int(nomor), [])}
                                for nomor in parameter["assignmentids"]], "warnings": []}

    def ws_mod_assign_get_grades(self, parameter):
        """Nilai per tugas."""
        return {"assignments": [{"assignmentid": int(nomor), "grades": self.data["nilai_tugas"].get(int(nomor), [])}
                                for nomor in parameter["assignmentids"]], "warnings": []}

    def ws_mod_assign_list_participants(self, parameter):
        """Peserta tugas dengan status pengumpulannya (onlyids: tanpa data pribadi)."""
        assert parameter["onlyids"] == "1"
        status = {101: ("submitted", 1, 0), 102: ("draft", 0, 0), 103: ("new", 0, 0), 104: ("new", 0, 1)}
        return [
            {"id": user_id, "fullname": self.data["pengguna"][user_id]["fullname"], "submitted": status[user_id][0] == "submitted",
             "requiregrading": bool(status[user_id][1]), "grantedextension": bool(status[user_id][2]),
             "submissionstatus": status[user_id][0], "groupid": 70, "groupname": "Kelas A" if user_id < 103 else "Kelas B"}
            for user_id in (101, 102, 103, 104)
        ]

    def ws_mod_assign_get_participant(self, parameter):
        """Satu peserta tugas; pengguna yang bukan mahasiswa kursus ditolak."""
        user_id = int(parameter["userid"])
        if user_id not in (101, 102, 103, 104):
            return galat_moodle("usernotincourse", "User is not enrolled in this course")
        return {"id": user_id, "fullname": self.data["pengguna"][user_id]["fullname"], "submitted": user_id == 101,
                "requiregrading": user_id == 101, "grantedextension": False, "blindmarking": False,
                "submissionstatus": "submitted" if user_id == 101 else "new"}

    def ws_mod_assign_save_grade(self, parameter):
        """Simpan nilai; jawabannya null seperti Moodle."""
        tugas_id, user_id = int(parameter["assignmentid"]), int(parameter["userid"])
        daftar = self.data["nilai_tugas"].setdefault(tugas_id, [])
        daftar.append({"id": 99, "userid": user_id, "attemptnumber": 1, "grade": f"{float(parameter['grade']):.5f}",
                       "timemodified": detik("2026-10-21 09:00"), "grader": USERID_DOSEN})
        return None

    def ws_gradereport_user_get_grade_items(self, parameter):
        """Buku nilai semua mahasiswa kursus."""
        kursus_id = int(parameter["courseid"])
        item = self.data["item_nilai"].get(kursus_id, [])
        return {"usergrades": [
            {"courseid": kursus_id, "userid": user_id, "userfullname": self.data["pengguna"][user_id]["fullname"],
             "useridnumber": self.data["pengguna"][user_id]["idnumber"],
             "gradeitems": [{**satu, "graderaw": nilai.get(satu["id"])} for satu in item]}
            for user_id, nilai in self.data["nilai_kursus"].get(kursus_id, {}).items()
        ], "warnings": []}

    def ws_mod_forum_get_forums_by_courses(self, parameter):
        """Forum kursus."""
        return [dict(forum) for nomor in parameter.get("courseids", []) for forum in self.data["forum"].get(int(nomor), [])]

    def ws_mod_forum_get_forum_discussions(self, parameter):
        """Diskusi satu forum, per halaman."""
        semua = self.data["diskusi"].get(int(parameter["forumid"]), [])
        halaman, per_halaman = int(parameter.get("page", 0)), int(parameter.get("perpage", 0))
        if per_halaman:
            semua = semua[halaman * per_halaman:(halaman + 1) * per_halaman]
        return {"discussions": semua, "warnings": []}

    def ws_mod_forum_add_discussion(self, parameter):
        """Diskusi baru di forum; dicatat supaya bisa diperiksa."""
        forum_id = int(parameter["forumid"])
        self.data["diskusi"].setdefault(forum_id, []).append(
            {"id": 3999, "discussion": 399, "subject": parameter["subject"], "message": parameter["message"]})
        return {"discussionid": 399, "warnings": []}

    def ws_core_calendar_get_action_events_by_timesort(self, parameter):
        """Kegiatan dalam jendela waktu, setelah aftereventid, paling banyak limitnum."""
        return self.kegiatan_dalam(parameter, self.data["kegiatan"])

    def ws_core_calendar_get_action_events_by_course(self, parameter):
        """Kegiatan satu kursus."""
        kursus_id = int(parameter["courseid"])
        return self.kegiatan_dalam(parameter, [satu for satu in self.data["kegiatan"] if satu["course"]["id"] == kursus_id])

    def kegiatan_dalam(self, parameter, kegiatan):
        """Saring kegiatan seperti calendar local_api: rentang waktu, aftereventid, limitnum (maks 50)."""
        batas = int(parameter.get("limitnum", 20))
        assert 1 <= batas <= 50
        dari, sampai = int(parameter.get("timesortfrom", 0)), int(parameter.get("timesortto", 2**31))
        setelah = int(parameter.get("aftereventid", 0))
        cocok = sorted((satu for satu in kegiatan if dari <= satu["timesort"] <= sampai), key=lambda satu: (satu["timesort"], satu["id"]))
        if setelah:
            posisi = next((nomor for nomor, satu in enumerate(cocok) if satu["id"] == setelah), -1)
            cocok = cocok[posisi + 1:]
        hasil = cocok[:batas]
        return {"events": hasil, "firstid": hasil[0]["id"] if hasil else 0, "lastid": hasil[-1]["id"] if hasil else 0}

    def ws_core_message_send_instant_messages(self, parameter):
        """Pesan per penerima; pengguna 104 menolak pesan dari bukan kontak."""
        hasil = []
        for nomor, pesan in enumerate(parameter["messages"]):
            user_id = int(pesan["touserid"])
            if user_id == 104:
                hasil.append({"msgid": -1, "clientmsgid": pesan.get("clientmsgid"),
                              "errormessage": "The user is unable to be messaged"})
            else:
                hasil.append({"msgid": 7000 + nomor, "clientmsgid": pesan.get("clientmsgid"), "text": pesan["text"],
                              "timecreated": detik("2026-10-21 09:00"), "conversationid": 50 + nomor, "useridfrom": USERID_DOSEN})
        return hasil

    def ws_mod_assign_view_assign(self, parameter):
        """Fungsi view: mencatat log di Moodle sungguhan."""
        return {"status": True, "warnings": []}

    def ws_tool_mobile_get_autologin_key(self, parameter):
        """Kunci autologin; uji memastikan fungsi ini tidak pernah dipanggil."""
        raise AssertionError("tool_mobile_get_autologin_key tidak boleh dipanggil")

    # --- berkas ------------------------------------------------------------

    def pluginfile(self, alamat: str, path: str, query: dict):
        """webservice/pluginfile.php: butuh token di query."""
        if self.berkas_putus:
            raise requests.ConnectionError(f"Connection reset while reading {alamat}")
        if query.get("token") not in self.token_berlaku:
            return jawaban_json(alamat, {"error": "Invalid token - token not found", "errorcode": "invalidtoken"})
        if path in self.pengalihan_berkas:
            return JawabanTiruan(alamat, 303, lokasi=self.pengalihan_berkas[path])
        if path not in self.berkas:
            return JawabanTiruan(alamat, 404, teks="Not found")
        isi, jenis = self.berkas[path]
        nama = path.rsplit("/", 1)[-1]
        return JawabanTiruan(alamat, isi=isi, teks="", jenis=jenis,
                             header={"Content-Disposition": f'attachment; filename="{nama}"'})

    def upload_php(self, alamat: str, isian: dict, files):
        """webservice/upload.php: berkas masuk draft area dengan itemid baru."""
        if isian.get("token") not in self.token_berlaku:
            return jawaban_json(alamat, {"error": "Invalid token - token not found", "errorcode": "invalidtoken"})
        nama, _ = files["file_1"]
        return jawaban_json(alamat, [{"component": "user", "contextid": 5, "userid": USERID_DOSEN, "filearea": "draft",
                                      "filename": nama, "filepath": isian.get("filepath", "/"),
                                      "itemid": 123456 if isian.get("itemid") == "0" else int(isian["itemid"])}])

    # --- sesi web ----------------------------------------------------------

    def sudah_masuk(self) -> bool:
        """Apakah cookie MoodleSession yang dibawa permintaan masih berlaku di server."""
        return bool(self.sesi_web_aktif) and self.cookies.get("MoodleSession") == self.sesi_web_aktif

    def halaman_moodle(self, alamat: str, isi: str, kelas: str = "", sesskey: bool = True):
        """Halaman HTML Moodle dengan M.cfg dan kelas body."""
        kelas_body = kelas if self.sudah_masuk() else f"{kelas} notloggedin"
        cfg = f'"sesskey":"{self.sesskey}",' if sesskey and self.sudah_masuk() else ""
        html = (
            f'<!DOCTYPE html><html><head><script>M.cfg = {{"wwwroot":"{SITUS}",{cfg}"sessiontimeout":"28800"}};</script>'
            f'</head><body id="page" class="{kelas_body.strip()}">{isi}</body></html>'
        )
        return JawabanTiruan(alamat, teks=html)

    def form_login(self, galat: str = "") -> str:
        """Form login Moodle 4.1 (lib/templates/loginform.mustache), dengan captcha kalau diminta."""
        captcha = '<div class="g-recaptcha" data-sitekey="kunci-situs-karangan"></div>' if self.captcha else ""
        skrip = '<script src="https://www.google.com/recaptcha/api.js"></script>' if self.captcha else ""
        blok_galat = (
            f'<div class="loginerrors"><a href="#" id="loginerrormessage" class="sr-only">{galat}</a>'
            f'<div class="alert alert-danger" role="alert">{galat}</div></div>' if galat else ""
        )
        return (
            f"{skrip}{blok_galat}"
            f'<form class="login-form" action="{SITUS}/login/index.php" method="post" id="login">'
            '<input id="anchor" type="hidden" name="anchor" value="">'
            f'<input type="hidden" name="logintoken" value="{LOGINTOKEN_UJI}">'
            '<input type="text" name="username" id="username" value="">'
            '<input type="password" name="password" id="password" value="">'
            f"{captcha}<button type=\"submit\" id=\"loginbtn\">Log in</button></form>"
            '<form action="/login/index.php" method="post" id="guestlogin">'
            '<input type="hidden" name="username" value="guest"><input type="hidden" name="password" value="guest"></form>'
        )

    def alihkan_ke_login(self, alamat: str):
        """require_login(): tamu dialihkan ke halaman login."""
        return JawabanTiruan(alamat, 303, lokasi=f"{SITUS}/login/index.php")

    def halaman_web(self, metode: str, alamat: str, path: str, query: dict, isian: dict, badan_json):
        """Halaman web: login, beranda, kursus, changenumsections.php, dan AJAX service.php."""
        if path == "/login/index.php":
            return self.login_php(metode, alamat, query, isian)
        if path == "/lib/ajax/service.php" and metode == "POST":
            return self.ajax_php(alamat, query, badan_json)
        if not self.sudah_masuk():
            return self.alihkan_ke_login(alamat)
        if self.hambatan_login and path != self.hambatan_login:
            return JawabanTiruan(alamat, 303, lokasi=SITUS + self.hambatan_login)
        if path == "/my/":
            return self.halaman_moodle(alamat, "<h1>Dasbor</h1>", "page-my-index")
        if path == "/course/view.php":
            kursus = self.data["kursus"].get(int(query.get("id", 0)))
            if kursus is None:
                return JawabanTiruan(alamat, 404, teks="Can't find data record in database table course.")
            return self.halaman_moodle(alamat, f"<h1>{kursus['fullname']}</h1>", f"format-{kursus['format']} course-{kursus['id']}")
        if path == "/course/changenumsections.php":
            return self.changenumsections(alamat, query)
        if path == self.hambatan_login:
            return self.halaman_moodle(alamat, "<h1>Langkah tambahan</h1>")
        return JawabanTiruan(alamat, 404, teks="Not found")

    def login_php(self, metode: str, alamat: str, query: dict, isian: dict):
        """login/index.php seperti Moodle 4.1: form, POST kredensial, lalu testsession."""
        if metode == "GET" and "testsession" in query:
            return JawabanTiruan(alamat, 303, lokasi=f"{SITUS}/my/")
        if metode == "GET":
            if self.sudah_masuk():
                return self.halaman_moodle(alamat, "<p>You are already logged in as Clark Kent</p>", "page-login-index")
            return self.halaman_moodle(alamat, self.form_login(), "page-login-index")
        if (
            isian.get("logintoken") == LOGINTOKEN_UJI
            and isian.get("username") == self.username_benar
            and isian.get("password") == self.password_benar
        ):
            self.nomor_sesi += 1
            self.sesi_web_aktif = f"sesi-karangan-{self.nomor_sesi}"
            self.cookies.set("MoodleSession", self.sesi_web_aktif, domain=HOST, path="/")
            if self.hambatan_login:
                return JawabanTiruan(alamat, 303, lokasi=SITUS + self.hambatan_login)
            return JawabanTiruan(alamat, 303, lokasi=f"{SITUS}/login/index.php?testsession={USERID_DOSEN}")
        return self.halaman_moodle(alamat, self.form_login(self.pesan_gagal_login), "page-login-index")

    def changenumsections(self, alamat: str, query: dict):
        """course/changenumsections.php Moodle 4.1: insertsection=0 menambah numsections section di akhir."""
        if query.get("sesskey") != self.sesskey:
            return self.halaman_moodle(alamat, "<p>Incorrect sesskey submitted, form not accepted!</p>")
        kursus_id = int(query["courseid"])
        daftar = self.data["section"][kursus_id]
        jumlah = int(query.get("numsections", 1))
        terakhir = max(section["section"] for section in daftar)
        if query.get("insertsection") == "0" and terakhir + jumlah <= self.maks_section:
            for nomor in range(terakhir + 1, terakhir + jumlah + 1):
                daftar.append({"id": self.id_section_berikutnya, "section": nomor, "name": f"Topic {nomor}",
                               "visible": 1, "summary": "", "modules": [], "_tanpa_nama": True})
                self.id_section_berikutnya += 1
        return JawabanTiruan(alamat, 303, lokasi=f"{SITUS}/course/view.php?id={kursus_id}#section-{terakhir + 1}")

    def ajax_php(self, alamat: str, query: dict, badan):
        """lib/ajax/service.php: periksa login dan sesskey, lalu jalankan core_update_inplace_editable."""
        permintaan = badan[0]
        if self.ajax_galat_berikutnya:
            kode = self.ajax_galat_berikutnya.pop(0)
            return jawaban_json(alamat, [{"error": True, "exception": {"errorcode": kode, "message": f"galat {kode}"}}])
        if not self.sudah_masuk():
            return jawaban_json(alamat, [{"error": True, "exception": {"errorcode": "servicerequireslogin",
                                                                        "message": "Web service requires login"}}])
        if query.get("sesskey") != self.sesskey:
            return jawaban_json(alamat, [{"error": True, "exception": {"errorcode": "invalidsesskey",
                                                                        "message": "Incorrect sesskey submitted"}}])
        if permintaan["methodname"] != "core_update_inplace_editable":
            return jawaban_json(alamat, [{"error": True, "exception": {"errorcode": "servicenotavailable", "message": "?"}}])
        args = permintaan["args"]
        for kursus_id, daftar in self.data["section"].items():
            for section in daftar:
                if section["id"] == int(args["itemid"]):
                    format_kursus = self.data["kursus"][kursus_id]["format"]
                    if args["component"] != f"format_{format_kursus}" or args["itemtype"] != "sectionname":
                        break
                    section["name"] = args["value"]
                    section.pop("_tanpa_nama", None)
                    return jawaban_json(alamat, [{"error": False, "data": {
                        "displayvalue": args["value"], "itemid": str(section["id"]), "component": args["component"],
                        "itemtype": "sectionname", "value": args["value"]}}])
        return jawaban_json(alamat, [{"error": True, "exception": {"errorcode": "invalidrecord",
                                                                    "message": "Can't find data record in database."}}])


def tolak_jaringan(*argumen, **opsi):
    """Pengganti requests.Session.request selama uji: jaringan sungguhan tidak boleh tersentuh."""
    raise AssertionError("uji mencoba menghubungi jaringan sungguhan; pakai fixture `situs`")


@pytest.fixture(autouse=True)
def setelan_terpisah(tmp_path, monkeypatch):
    """Setelan, .env, aswaya.yaml, dan cache mesin pengembang tidak boleh ikut menentukan hasil uji.

    Kredensial asli di .env proyek tidak terbaca karena akar proyek dipindah ke
    direktori sementara, cache dialihkan ke direktori sementara lewat
    XDG_CACHE_HOME, dan sesi HTTP sungguhan diblokir sama sekali.
    """
    monkeypatch.setattr(requests.Session, "request", tolak_jaringan)
    for kunci in list(os.environ):
        if kunci.startswith("ASWAYA_"):
            monkeypatch.delenv(kunci)
    akar = tmp_path / "proyek"
    akar.mkdir()
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    konfigurasi.atur_akar_proyek(akar)
    konfigurasi.atur_setelan()
    yield
    konfigurasi.atur_akar_proyek(None)
    konfigurasi.atur_setelan()


@pytest.fixture
def situs(monkeypatch) -> SitusTiruan:
    """Aswaya tiruan yang dipakai setiap KlienAswaya dan SesiWeb yang dibuat selama uji."""
    tiruan = SitusTiruan()
    monkeypatch.setattr(aswaya_client, "buat_sesi_http", tiruan.sebagai_pabrik)
    monkeypatch.setattr(sesi_web, "buat_sesi_http", tiruan.sebagai_pabrik)
    return tiruan


@pytest.fixture
def kredensial_di_setelan():
    """Username dan password karangan, diberikan lewat atur_setelan seperti dari .env."""
    konfigurasi.atur_setelan(ASWAYA_USERNAME=USERNAME_UJI, ASWAYA_PASSWORD=PASSWORD_UJI)


@pytest.fixture
def klien(situs, kredensial_di_setelan):
    """KlienAswaya dengan kredensial karangan di setelan."""
    return aswaya_client.KlienAswaya()


@pytest.fixture
def dir_cache(tmp_path) -> Path:
    """Direktori cache token dan sesi selama uji."""
    return tmp_path / "cache" / "aswaya-mcp"
