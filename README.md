# Aswaya MCP

Aplikasi untuk memakai LMS Aswaya Pradita University
(<https://aswaya.pradita.ac.id>, sebuah Moodle) dari asisten AI, terminal, atau
program lain. Dibuat untuk dosen yang ingin mengotomasi pekerjaan mengajar:
melihat kursus dan pesertanya, memantau pengumpulan tugas, membaca buku nilai,
mengunduh berkas, membuat pengumuman, memberi nilai, mengirim pesan, serta
menambah dan mengganti nama section kursus.

Aplikasi ini memakai web service Moodle yang juga dipakai aplikasi Moodle di
ponsel (layanan `moodle_mobile_app`). Untuk section kursus, yang tidak dibuka
layanan itu, aplikasi login lewat halaman web seperti peramban. Proyek
saudaranya, dengan pola yang sama, adalah
[lppm-mcp](https://github.com/alfa-yohannis/lppm-mcp),
[siakad-mcp](https://github.com/alfa-yohannis/siakad-mcp), dan
[sister-mcp](https://github.com/alfa-yohannis/sister-mcp). Semuanya berdiri
sendiri: kode, dokumentasi, dan pengujiannya terpisah.

Tersedia dalam tiga bentuk, semuanya dari paket yang sama:

| Mode     | Untuk siapa                    | Referensi                    |
|----------|--------------------------------|------------------------------|
| MCP      | asisten AI (Claude Code, dsb.) | [docs/MCP.md](docs/MCP.md)   |
| REST API | aplikasi apa pun lewat HTTP    | [docs/API.md](docs/API.md)   |
| Pustaka  | program Python Anda sendiri    | [bagian Pustaka](#3-pustaka) |

Ada juga CLI (`./aswaya kursus`, `./aswaya pengumpulan`, `./aswaya umumkan`,
dan seterusnya) untuk pemakaian langsung dari terminal; lihat
[docs/CLI.md](docs/CLI.md).

## Memakainya lewat asisten AI

Untuk Claude Code, dari klona repositori ini:

```bash
claude mcp add aswaya-mcp -s user -- /path/ke/aswaya-mcp/aswaya mcp
```

Langkah untuk Codex dan Antigravity, serta pengaturan izin pemanggilan tool, ada
di [docs/MCP.md](docs/MCP.md).

## Prasyarat

- Python 3.10 atau lebih baru (diuji dengan 3.12)
- Akun Aswaya (username atau email kampus, dan password), atau token web service
  layanan `moodle_mobile_app`

## Pasang

Ada dua cara, pilih salah satu.

A. Berdiri sendiri. Klona lalu jalankan; cocok kalau Anda hanya mau memakai
aplikasinya:

```bash
git clone https://github.com/alfa-yohannis/aswaya-mcp.git
cd aswaya-mcp
./aswaya uji          # jalankan pertama menyiapkan .venv + dependensi sendiri
```

Virtualenv dibuat dengan `python3`. Untuk memakai interpreter lain:
`ASWAYA_PYTHON=python3.12 ./aswaya uji`.

B. Sebagai paket, kalau aplikasi Anda sendiri yang akan memakainya:

```bash
pip install "aswaya-mcp[api,mcp] @ git+https://github.com/alfa-yohannis/aswaya-mcp.git"
pip install "git+https://github.com/alfa-yohannis/aswaya-mcp.git"   # pustaka saja
```

## Kredensial

Salin contohnya lalu isi sendiri:

```bash
cp .env.contoh .env
```

```
ASWAYA_URL=https://aswaya.pradita.ac.id
ASWAYA_USERNAME=nama.anda@pradita.ac.id
ASWAYA_PASSWORD=...
ASWAYA_TOKEN=
```

Cukup isi password atau token. Kalau keduanya terisi, `ASWAYA_TOKEN` dipakai
lebih dulu, dan password hanya dipakai untuk login ulang saat token itu ditolak.
Isian kosong dianggap belum diisi. Login web untuk section selalu butuh
password, karena token web service tidak bisa dipakai untuk login lewat halaman.

`.env` tidak ikut ter-commit. Kredensial hanya dibaca dari `.env`, environment,
atau `atur_setelan()` di kode, tidak pernah dari `aswaya.yaml`, dan tidak pernah
dicetak ke layar maupun log. Tool MCP sengaja tidak menerima kata sandi atau
token lewat parameter, jadi asisten AI tidak pernah memegangnya.

### Cache token dan sesi web

Supaya password tidak dipakai setiap kali, token hasil login disimpan di luar
repositori:

```
$XDG_CACHE_HOME/aswaya-mcp/token-<sidik>.json    (bawaannya ~/.cache/aswaya-mcp/)
$XDG_CACHE_HOME/aswaya-mcp/sesi-<sidik>.json     cookie sesi web, untuk alat section
```

Berkasnya berizin 0600 di direktori berizin 0700, satu per pasangan situs dan
username; nama berkasnya sidik SHA-256, jadi alamat dan username tidak terbaca
dari daftar isi direktori. `privatetoken` dari Moodle dan `sesskey` tidak pernah
disimpan. Di sistem berkas yang tidak menegakkan izin (NTFS, FAT, sebagian mount
jaringan), berkasnya dihapus lagi dan token hanya hidup di memori; berkas cache
yang ternyata terbuka bagi pemakai lain juga dibuang. Untuk mematikan cache,
isi `simpan_cache: tidak` di `aswaya.yaml` (atau `ASWAYA_SIMPAN_CACHE=tidak`).
Hapus direktori itu untuk melupakan semua token dan sesi.

## Menjalankan

### 1. MCP

```bash
claude mcp add aswaya-mcp -- /path/ke/aswaya-mcp/aswaya mcp   # dari klona
claude mcp add aswaya-mcp -- aswaya-mcp                       # setelah pip install
```

Cek servernya hidup tanpa mendaftarkannya dulu:

```bash
./aswaya mcp        # bicara JSON-RPC lewat stdio; Ctrl-C untuk berhenti
```

Lalu minta asisten Anda, misalnya: *"Siapa saja yang belum mengumpulkan Tugas 1
di kelas Pengembangan Aplikasi Web?"* Ada 19 tool. Tiga belas hanya membaca:
`cek_login`, `daftar_kursus`, `isi_kursus`, `peserta_kursus`, `daftar_tugas`,
`pengumpulan_tugas`, `nilai_kursus`, `daftar_forum`, `diskusi_forum`, `tenggat`,
`daftar_section`, `fungsi_tersedia`, dan `unduh_berkas` (yang menulis ke disk
lokal, tidak ke Aswaya). Enam bisa menulis ke Aswaya dan bawaannya uji coba:
`kirim_pengumuman`, `beri_nilai`, `kirim_pesan`, `tambah_section`,
`ubah_nama_section`, dan `panggil_fungsi` untuk fungsi selain baca. Rinciannya
di [docs/MCP.md](docs/MCP.md).

### 2. REST API

```bash
./aswaya api                  # http://localhost:8000
PORT=9001 ./aswaya api        # ganti port
uvicorn aswaya_mcp.api:app --port 8000   # kalau terpasang sebagai paket
```

Dokumentasi interaktif ada di `/docs`. Coba:

```bash
curl localhost:8000/kursus?cari=web
curl localhost:8000/kursus/5515/peserta
curl -X POST localhost:8000/kursus/5515/pengumuman -H 'Content-Type: application/json' \
  -d '{"subjek": "Kuis", "isi": "Kuis dimulai pukul 08.00."}'      # uji coba
```

Untuk menempelkannya ke aplikasi FastAPI Anda sendiri:

```python
from aswaya_mcp.api import router
app.include_router(router, prefix="/aswaya")
```

Endpoint selengkapnya di [docs/API.md](docs/API.md).

### 3. Pustaka

```python
from aswaya_mcp import KlienAswaya, daftar_kursus, pengumpulan_tugas

klien = KlienAswaya()                       # kredensial dari .env; belum menghubungi Aswaya
for kursus in daftar_kursus(klien, "web")["kursus"]:    # token diambil di sini
    print(kursus["id"], kursus["fullname"])

status = pengumpulan_tugas(klien, 77)
print(status["ringkasan"])

# fungsi web service apa pun, dengan parameter terstruktur
isi = klien.panggil("core_course_get_contents", {"courseid": 5515})
```

Fungsi yang menulis mengembalikan `HasilTulis`. Bawaannya uji coba:

```python
from aswaya_mcp import KlienAswaya, kirim_pengumuman, tambah_section

klien = KlienAswaya()
rencana = kirim_pengumuman(klien, 5515, "Kuis minggu depan", "Kuis dimulai pukul 08.00.")
print(rencana.ringkasan, rencana.permintaan)
hasil = kirim_pengumuman(klien, 5515, "Kuis minggu depan", "Kuis dimulai pukul 08.00.", kirim=True)

rencana = tambah_section(klien, 5026, [f"Session {nomor:02d}" for nomor in range(8, 15)])
```

`KlienAswaya.unggah_berkas(path)` mengunggah berkas ke draft area pemakai dan
mengembalikan `itemid`-nya, untuk diteruskan ke fungsi lain lewat `panggil`.
Kredensial dan alamat situs boleh diberikan dari kode tanpa berkas apa pun:
`atur_setelan(ASWAYA_USERNAME="...", ASWAYA_PASSWORD="...")`. Semua kegagalan
berupa exception biasa (`AswayaError` dan turunannya: `LoginDitolak`,
`LoginWebTerhalang`, `MoodleError`, `FungsiTidakTersedia`, `IsianDitolak`,
`AlamatDitolak`, `HasilTidakPasti`; serta `KonfigurasiError`); pustaka tidak
pernah memanggil `sys.exit`. Contoh utuh: [examples/pustaka.py](examples/pustaka.py).

### CLI

```bash
./aswaya cek-login                      # kredensial di .env bisa dipakai?
./aswaya publik                         # konfigurasi publik situs, tanpa login
./aswaya kursus --cari web              # kursus yang Anda ikuti
./aswaya isi 5515                       # section, modul, dan berkas
./aswaya peserta 5515 --peran student   # peserta; --lengkap untuk email dan NIM
./aswaya pengumpulan 77                 # siapa sudah dan belum mengumpulkan
./aswaya nilai 5515 --csv > nilai.csv   # buku nilai untuk spreadsheet
./aswaya tenggat --hari 14              # kegiatan yang menunggu tindakan
./aswaya umumkan 5515 --subjek "Kuis" --isi "..."            # uji coba; --kirim untuk mengirim
./aswaya tambah-section 5026 --nama "Session "{08..14}       # uji coba; --kirim untuk mengirim
```

Terpasang sebagai paket, perintahnya `aswaya-cek-login`, `aswaya-kursus`, dan
seterusnya dengan argumen yang sama. Daftar lengkap di [docs/CLI.md](docs/CLI.md).

## Menulis ke Aswaya

Semua alat yang menulis mengikuti alur yang sama. Isian diperiksa dulu tanpa
menghubungi Aswaya, lalu data pendukung dibaca supaya pratinjaunya bisa
diperiksa: forum pengumuman kursus, nilai lama mahasiswa, nama penerima pesan,
section yang sudah ada. Dengan `kirim=False` (bawaan; di CLI tanpa `--kirim`)
yang kembali hanya pratinjau berisi `ringkasan` untuk dibaca manusia dan
`permintaan` yang akan dikirim apa adanya, tanpa token. Dengan `kirim=True`
permintaannya dikirim tepat sekali.

| Alat                | Yang dikirim                                             | Pemeriksaan sebelum kirim                                    |
|---------------------|----------------------------------------------------------|--------------------------------------------------------------|
| `kirim_pengumuman`  | `mod_forum_add_discussion` ke forum jenis news           | forum pengumuman ada dan akun ini boleh menulis              |
| `beri_nilai`        | `mod_assign_save_grade` (percobaan terakhir, `applytoall=0`) | nilai tidak negatif dan tidak melebihi nilai maksimum tugas |
| `kirim_pesan`       | `core_message_send_instant_messages`                     | setiap id penerima dikenal Aswaya                            |
| `tambah_section`    | `course/changenumsections.php`, lalu nama lewat AJAX     | nama belum terpakai di kursus itu (kecuali `paksa`)          |
| `ubah_nama_section` | `core_update_inplace_editable` lewat AJAX                | section milik kursus itu                                     |
| `panggil_fungsi`    | wsfunction apa pun selain fungsi baca                    | fungsinya dimuat layanan token ini                           |

Isi pengumuman, umpan balik, dan pesan berupa teks biasa: karakter HTML
di-escape, baris kosong memisahkan paragraf, dan alamat http(s) menjadi tautan.
Pakai `bentuk="html"` (CLI: `--html`) untuk mengirim HTML apa adanya.

Kiriman tidak pernah diulang otomatis, kecuali saat Aswaya menolak token atau
sesskey-nya; penolakan itu terjadi sebelum fungsinya dijalankan, jadi aman
diulang sekali setelah login. Kalau permintaan sudah berangkat tetapi jawabannya
tidak bisa dipastikan (jaringan putus, jawaban rusak), yang muncul
`HasilTidakPasti`; di MCP balasannya `terkirim: true` dengan `ok: false`.
Periksa dulu lewat alat baca sebelum mencoba lagi.

`panggil_fungsi` menebak jenis fungsi dari namanya, karena site info Moodle
tidak menyebutkannya: nama yang memuat `_get_`, `_search_`, atau `_list_`
dianggap membaca dan langsung dijalankan. Fungsi lain, termasuk fungsi `view`
yang mencatat log dan bisa menandai aktivitas selesai, hanya dipratinjau.
`tool_mobile_get_autologin_key` dan `tool_mobile_get_tokens_for_qr_login`
ditolak sama sekali karena menghasilkan kunci login.

## Section kursus

Layanan `moodle_mobile_app` tidak memuat fungsi pembuat section. Karena itu
`tambah_section` dan `ubah_nama_section` login lewat halaman, seperti peramban,
dengan username dan password dari `.env`:

1. `GET /login/index.php` untuk mengambil `logintoken` dari form `id="login"`,
   lalu `POST` berisi `anchor`, `logintoken`, `username`, dan `password`.
2. Halaman kursus dibuka untuk membaca `sesskey` dari `M.cfg`, sekaligus format
   kursusnya kalau web service tidak menyebutnya.
3. `GET /course/changenumsections.php?courseid=..&insertsection=0&numsections=N&sesskey=..`
   menambah N section di akhir kursus (parameter Moodle 4.1).
4. Setiap section baru diberi nama lewat
   `POST /lib/ajax/service.php?sesskey=..&info=core_update_inplace_editable`
   dengan component `format_<format kursus>`, itemtype `sectionname`, itemid id
   section, dan value namanya.
5. Hasilnya diperiksa ulang lewat `core_course_get_contents`. Section baru
   dikenali dari id yang belum ada sebelumnya, jadi nama tidak pernah terpasang
   ke section lama.

Contoh untuk menambah Session 08 sampai 14 di kursus 5026:

```bash
./aswaya section 5026                                  # lihat section yang ada
./aswaya tambah-section 5026 --nama "Session "{08..14}            # rencana
./aswaya tambah-section 5026 --nama "Session "{08..14} --kirim    # kirim
```

Bash menjabarkan `"Session "{08..14}` menjadi tujuh nama, `Session 08` sampai
`Session 14`. Rencananya menyebut section yang ada, nama baru beserta nomor
posisinya, dan langkah yang akan dijalankan. Nama yang sudah dipakai di kursus
itu ditolak supaya perintah yang tidak sengaja dijalankan dua kali tidak
menggandakan section; `--paksa` melewati pemeriksaan ini. Kalau kursus sudah
berakhir dengan section kosong, rencananya memperingatkan hal itu, karena
mungkin yang dimaksud adalah mengganti nama section kosong tersebut.

Kalau halaman login memuat captcha (reCAPTCHA, hCaptcha, Turnstile, dan
sejenisnya), login dihentikan dengan pesan jelas dan captcha-nya tidak dicoba
dijawab. Begitu juga kalau Aswaya meminta MFA, persetujuan kebijakan situs, atau
penggantian password. Langkah seperti itu diselesaikan pemakai lewat peramban.
Login web yang gagal tidak diulang otomatis.

## Privasi data mahasiswa

`peserta_kursus` hanya meminta id, nama, peran, grup, dan waktu akses terakhir
dari Aswaya, lewat opsi `userfields` milik `core_enrol_get_enrolled_users`.
Email dan idnumber (NIM) baru diminta dan dikembalikan kalau `lengkap=True`
(CLI: `--lengkap`), supaya data pribadi mahasiswa tidak ikut tersimpan di
riwayat percakapan asisten AI tanpa keperluan. `nilai_kursus` tidak menyertakan
NIM; cocokkan lewat `user_id` kalau perlu. `pengumpulan_tugas` membaca peserta
tugas dengan `onlyids`, jadi yang keluar hanya nama dan status.

## Setelan

Semua setelan opsional. Yang menang, dari yang paling khusus:

```
argumen pemanggil -> atur_setelan() -> environment -> .env -> aswaya.yaml -> nilai bawaan
```

Di environment dan `.env` namanya berawalan `ASWAYA_` dan huruf besar
(`ASWAYA_URL`); di `aswaya.yaml` tanpa awalan dan huruf kecil (`url`). Salin
`aswaya.yaml.contoh` menjadi `aswaya.yaml` kalau perlu mengubah sesuatu.

| `aswaya.yaml`        | Bawaan                          | Keterangan                                          |
|----------------------|---------------------------------|-----------------------------------------------------|
| `url`                | `https://aswaya.pradita.ac.id`  | alamat Moodle; harus https, boleh dengan subdirektori |
| `nama_instansi`      | `Pradita University`            | label pada judul REST API dan instruksi MCP         |
| `layanan`            | `moodle_mobile_app`             | layanan web service yang dimintai token             |
| `batas_detik`        | `60`                            | login dan panggilan fungsi                          |
| `batas_unduh_detik`  | `300`                           | unduhan dan unggahan berkas                         |
| `maks_pengalihan`    | `5`                             | pengalihan yang diikuti saat unduh dan di sesi web  |
| `simpan_cache`       | `ya`                            | simpan token dan cookie sesi di cache 0600          |
| `zona_waktu`         | `Asia/Jakarta`                  | zona waktu tanggal di keluaran                      |
| `umur_sesi_detik`    | `900`                           | lama klien per kredensial disimpan REST API         |
| `user_agent`         | `aswaya-mcp`                    | User-Agent permintaan HTTP                          |

`ASWAYA_USERNAME`, `ASWAYA_PASSWORD`, dan `ASWAYA_TOKEN` hanya dibaca dari
`atur_setelan()`, environment, dan `.env`.

## Akar proyek

Akar proyek menentukan letak `.env`, `aswaya.yaml`, dan `data/`, serta titik
hitung path relatif (termasuk tujuan unduhan):

- dijalankan dari klona repositori ini: direktori repositori itu sendiri
- dipasang sebagai paket: direktori kerja proyek pemakai

Direktori di atasnya tidak pernah ikut ditelusuri. Untuk menentukan sendiri,
setel `ASWAYA_AKAR_PROYEK` atau panggil `atur_akar_proyek()`.

## Rancangan

```
pyproject.toml              metadata paket, dependensi, dan perintah terpasang
aswaya                      peluncur untuk pemakaian berdiri sendiri
aswaya.yaml.contoh          contoh setelan non-rahasia
aswaya_mcp/__init__.py      API publik paket ini
aswaya_mcp/konfigurasi.py   akar proyek, setelan, kredensial, sesi HTTP, zona waktu, cache token dan sesi
aswaya_mcp/aswaya_client.py KlienAswaya: token, perataan parameter, server.php, galat Moodle, berkas, unggahan
aswaya_mcp/sesi_web.py      SesiWeb: login lewat halaman, cookie, sesskey, AJAX service.php
aswaya_mcp/kursus.py        daftar kursus, isi kursus, peserta
aswaya_mcp/tugas.py         tugas, pengumpulan, beri nilai
aswaya_mcp/nilai.py         buku nilai kursus
aswaya_mcp/forum.py         forum, diskusi, pengumuman
aswaya_mcp/kalender.py      tenggat dari action events kalender
aswaya_mcp/pesan.py         pesan pribadi
aswaya_mcp/section.py       daftar, tambah, dan ganti nama section
aswaya_mcp/berkas.py        unduh berkas ke disk
aswaya_mcp/fungsi.py        daftar fungsi dan pemanggil generik
aswaya_mcp/situs.py         cek login dan konfigurasi publik
aswaya_mcp/tulis.py         HasilTulis: uji coba, pratinjau permintaan, hasil kiriman
aswaya_mcp/teks.py          HTML ke teks dan sebaliknya, waktu Unix ke ISO 8601
aswaya_mcp/cli.py           CLI (aswaya-kursus, aswaya-umumkan, ...)
aswaya_mcp/api.py           REST API: router yang bisa ditempel + app siap pakai
aswaya_mcp/mcp_server.py    MCP server (perintah aswaya-mcp)
tests/                      unit test dengan Aswaya tiruan, tanpa jaringan
docs/                       referensi CLI, REST API, dan MCP
examples/                   contoh prompt, konfigurasi klien MCP, klien API, pustaka
```

## Catatan perilaku Aswaya

Diamati dari konfigurasi publik situs (`tool_mobile_get_public_config`, tanpa
login) pada 21 Oktober 2026:

- Nama situs "Aswaya Pradita University E-Learning", `wwwroot`
  `https://aswaya.pradita.ac.id`.
- `enablewebservices=1` dan `enablemobilewebservice=1`, jadi layanan
  `moodle_mobile_app` aktif dan `login/token.php` bisa dipakai.
- `typeoflogin=1`: login di dalam aplikasi dengan username dan password, tanpa
  peramban. `authloginviaemail=1`: email kampus bisa dipakai sebagai username.
- `guestlogin=0`, `maintenanceenabled=0`.

Menurut pemeriksaan pemakai, situsnya Moodle 4.1 dan halaman loginnya tidak
memuat captcha, dengan isian username, password, dan logintoken. Parameter
`changenumsections.php` dan nama itemtype `sectionname` dicocokkan dengan kode
`MOODLE_401_STABLE`. Parameter fungsi web service lainnya dicocokkan dengan kode
Moodle 4.1 yang sama (`enrol/externallib.php`, `mod/assign/externallib.php`,
`mod/forum/externallib.php`, `message/externallib.php`,
`calendar/externallib.php`, dan `gradereport_user`).

Yang belum bisa diverifikasi tanpa login, dan perlu dicek pada pemakaian
pertama:

- daftar fungsi yang benar-benar dimuat layanan `moodle_mobile_app` di Aswaya
  (`./aswaya fungsi`); alat yang butuh fungsi yang tidak ada memberi pesan jelas;
- bentuk jawaban `core_webservice_get_site_info`, `gradereport_user_get_grade_items`,
  dan fungsi lain untuk akun dosen sungguhan, termasuk peran dan nama grup;
- apakah idnumber pengguna di Aswaya memang berisi NIM;
- perilaku `webservice/pluginfile.php` untuk token yang ditolak, dan berkas
  yang tersimpan sebagai tautan ke layanan luar;
- login web, isi `M.cfg`, kelas body halaman kursus, dan jawaban AJAX
  `core_update_inplace_editable`; semuanya baru diuji dengan tiruan berdasarkan
  kode Moodle 4.1;
- batas section kursus 5026 dan format kursusnya.

## Keamanan dan batasan

- Verifikasi sertifikat TLS selalu aktif dan tidak ada setelan untuk
  mematikannya.
- Token dikirim di badan POST ke `server.php`, tidak di URL. Untuk unduhan,
  token ditambahkan ke query `webservice/pluginfile.php` dan hanya ke host
  Aswaya; pengalihan ke host lain tidak diikuti.
- Sesi web hanya membuka alamat di host Aswaya. Password hanya dikirim dalam
  POST ke `/login/index.php`, dan action form di host lain ditolak sebelum
  password ikut terkirim.
- Token, password, sesskey, `privatetoken`, dan `userprivateaccesskey` tidak
  muncul di `repr()`, pesan galat, maupun keluaran. Pesan galat dari Aswaya
  disamarkan kalau kebetulan menggemakan kredensial.
- Login yang gagal tidak diulang otomatis, karena Moodle bisa mengunci akun
  setelah beberapa kali gagal.
- Unduhan ditulis lewat berkas sementara lalu dipindah, nama berkas dari server
  dibersihkan dari pemisah direktori, dan berkas yang sudah ada tidak ditimpa
  kecuali `timpa=True`.

## Menambah kemampuan baru

```bash
./aswaya fungsi forum                              # 1. cari wsfunction yang tersedia
./aswaya panggil mod_forum_get_discussion_posts --parameter '{"discussionid": 301}'
                                                   # 2. lihat bentuk jawabannya
# 3. tulis fungsi layanan di modul areanya (mis. forum.py), dengan uji coba kalau menulis
# 4. daftarkan di cli.py, api.py, dan mcp_server.py
# 5. tambahkan uji di tests/ dengan jawaban karangan di SitusTiruan
```

Alat yang menulis memakai `tulis.jalankan_tulis()` (web service) atau
mengembalikan `HasilTulis` sendiri (sesi web), dengan `kirim=False` sebagai
bawaan, dan instruksi MCP-nya meminta asisten menjalankan uji coba lebih dulu
lalu meminta persetujuan pemakai.

## Konvensi penulisan skrip

- Satu modul untuk satu area; alur bersama tinggal di modul dasar
  (`aswaya_client.py`, `sesi_web.py`, `tulis.py`).
- Setiap kelas, method, dan fungsi punya docstring.
- Fungsi ditulis datar, tanpa fungsi bersarang di dalam fungsi.
- Nama variabel dan fungsi ditulis utuh dan deskriptif, tanpa singkatan
  satu-dua huruf.
- Komentar hanya untuk hal yang tidak terbaca dari kodenya.
- Nilai rahasia tidak pernah dicetak.

## Pengujian

```bash
./aswaya uji
```

237 unit test, semuanya berjalan tanpa jaringan dan tanpa kredensial: Aswaya
digantikan `SitusTiruan` di `tests/conftest.py`, yang menjawab seperti Moodle
4.1 untuk `token.php`, `server.php`, `webservice/pluginfile.php`, `upload.php`,
`service-nologin.php`, halaman login, `changenumsections.php`, dan AJAX
`service.php`. Selama uji, akar proyek dan cache dipindah ke direktori sementara
supaya `.env` asli dan `~/.cache/aswaya-mcp/` tidak tersentuh, dan sesi HTTP
sungguhan diblokir. Nama dosen, mahasiswa, NIM, email, token, dan kata sandi di
berkas uji dan dokumentasi seluruhnya dikarang.
