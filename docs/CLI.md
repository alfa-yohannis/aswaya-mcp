# Referensi CLI Aswaya

## Menjalankan

### 1. Pasang

Butuh Python 3.10+.

```bash
git clone https://github.com/alfa-yohannis/aswaya-mcp.git
cd aswaya-mcp
./aswaya uji            # jalankan pertama menyiapkan .venv + dependensi
```

Terpasang lewat pip, setiap sub-perintah tersedia sebagai perintah sendiri
berawalan `aswaya-` dengan argumen yang sama persis: `./aswaya kursus` dan
`aswaya-kursus` setara.

### 2. Isi kredensial

```bash
cp .env.contoh .env   # ASWAYA_USERNAME, lalu ASWAYA_PASSWORD atau ASWAYA_TOKEN
```

### 3. Cek, lalu lihat kursus Anda

```bash
./aswaya cek-login
./aswaya kursus
```

## Semua sub-perintah

Dijalankan dari akar proyek, yaitu direktori berisi `aswaya`.

```bash
./aswaya cek-login              # kredensial di .env bisa dipakai?
./aswaya publik                 # konfigurasi publik situs, tanpa login
./aswaya kursus ...             # kursus yang Anda ikuti
./aswaya isi ...                # section, modul, dan berkas satu kursus
./aswaya peserta ...            # peserta satu kursus
./aswaya tugas ...              # tugas satu kursus
./aswaya pengumpulan ...        # pengumpulan dan nilai per mahasiswa
./aswaya nilai ...              # buku nilai satu kursus
./aswaya forum ...              # forum satu kursus
./aswaya diskusi ...            # diskusi satu forum
./aswaya tenggat ...            # kegiatan yang menunggu tindakan
./aswaya section ...            # section satu kursus
./aswaya unduh ...              # unduh satu berkas
./aswaya fungsi ...             # fungsi web service yang tersedia
./aswaya panggil ...            # panggil wsfunction apa pun
./aswaya umumkan ...            # pengumuman baru (uji coba tanpa --kirim)
./aswaya beri-nilai ...         # nilai seorang mahasiswa (uji coba tanpa --kirim)
./aswaya pesan ...              # pesan pribadi (uji coba tanpa --kirim)
./aswaya tambah-section ...     # section baru (uji coba tanpa --kirim)
./aswaya ubah-nama-section ...  # ganti nama section (uji coba tanpa --kirim)
./aswaya ubah-ringkasan-section ...  # teks atau tautan di deskripsi section (uji coba tanpa --kirim)
./aswaya api                    # REST API
./aswaya mcp                    # MCP server
./aswaya uji                    # unit test
```

Setiap perintah baca dan tulis punya `--json` untuk keluaran yang bisa dipipa.
Kredensial selalu dibaca dari setelan (`.env`, environment) dan tidak pernah
dicetak. Kegagalan dilaporkan sebagai satu baris `Gagal: ...` di stderr dengan
kode keluar 1. Perintah yang menulis hanya mengirim kalau diberi `--kirim`.

Isian teks panjang (`--isi`, `--umpan-balik`, `--teks`, `--parameter`) boleh
diisi `-` untuk dibaca dari stdin:

```bash
./aswaya umumkan 5515 --subjek "Kuis minggu depan" --isi - < pengumuman.txt
```

## Perintah baca

### `./aswaya cek-login`

```bash
./aswaya cek-login
# Login Aswaya OK: Aswaya Pradita University E-Learning (https://aswaya.pradita.ac.id)
#   pemakai   Clark Kent (userid 7)
#   Moodle    4.1.9 (Build: 20240212)
#   fungsi    412 tersedia untuk token ini
#   token     dari cache, cache /home/anda/.cache/aswaya-mcp/token-....json
```

| Argumen         | Keterangan                                                           |
|-----------------|----------------------------------------------------------------------|
| `--login-ulang` | paksa login dengan password walaupun ada token di setelan atau cache |

Kalau `.env` belum diisi, pesannya menyebut kunci yang kurang tanpa menghubungi
Aswaya. Kalau login ditolak, ringkasan konfigurasi publik situs dicetak ke
stderr untuk membantu mencari sebabnya.

### `./aswaya publik`

Konfigurasi publik situs (`tool_mobile_get_public_config`) tanpa login: nama
situs, web service dan layanan mobile aktif atau tidak, status pemeliharaan,
dan jenis login.

### `./aswaya kursus`

```bash
./aswaya kursus
./aswaya kursus --cari web
./aswaya kursus --json | jq '.kursus[].id'
```

| Argumen  | Keterangan                                                  |
|----------|-------------------------------------------------------------|
| `--cari` | saring dengan potongan nama, nama pendek, atau kategori     |

### `./aswaya isi <kursus_id>`

Section, modul, tanggal penting, dan berkas (dengan url-nya) satu kursus.

### `./aswaya peserta <kursus_id>`

```bash
./aswaya peserta 5515 --peran student
./aswaya peserta 5515 --lengkap --json > peserta.json
```

| Argumen     | Keterangan                                                   |
|-------------|--------------------------------------------------------------|
| `--peran`   | shortname atau nama peran, mis. `student`, `editingteacher`  |
| `--lengkap` | sertakan email dan idnumber (NIM)                            |

Tanpa `--lengkap`, email dan NIM tidak diminta dari Aswaya sama sekali.

### `./aswaya tugas <kursus_id>`

Tugas beserta id, tenggat, batas akhir, nilai maksimum, dan url-nya. Id itulah
`tugas_id` untuk `pengumpulan` dan `beri-nilai`.

### `./aswaya pengumpulan <tugas_id>`

```
Tugas 77: 4 peserta, 1 dikumpulkan, 1 draf, 2 belum, 1 dinilai, 1 perlu dinilai

     103  Bruce Banner | belum mengumpulkan - | nilai -
     102  Diana Prince | draf, belum diserahkan 2026-09-15T20:00+07:00 | nilai -
     101  Peter Parker | sudah dikumpulkan 2026-09-14T21:30+07:00 | nilai 85  *perlu dinilai
          profil-peter.zip (10.0 KB)  https://aswaya.pradita.ac.id/webservice/pluginfile.php/...
```

### `./aswaya nilai <kursus_id>`

```bash
./aswaya nilai 5515
./aswaya nilai 5515 --csv > nilai.csv
```

| Argumen | Keterangan                                                                 |
|---------|----------------------------------------------------------------------------|
| `--csv` | CSV dengan kolom `user_id`, `nama`, lalu satu kolom per item nilai `Nama (#id)` |

### `./aswaya forum <kursus_id>` dan `./aswaya diskusi <forum_id>`

Forum kursus (forum pengumuman ditandai `[pengumuman]`) dan diskusi satu forum,
terbaru dulu.

### `./aswaya tenggat`

| Argumen    | Bawaan | Keterangan                       |
|------------|--------|----------------------------------|
| `--hari`   | `30`   | jangkauan ke depan, 1 sampai 366 |
| `--kursus` |        | batasi ke satu kursus            |

Mulai pukul 00.00 hari ini (WIB). Bagi dosen, isinya antara lain tugas yang
menunggu dinilai beserta jumlahnya.

### `./aswaya section <kursus_id>`

```
8 section di kursus 5026
https://aswaya.pradita.ac.id/course/view.php?id=5026

    0  id 8000     Umum (0 modul)
    1  id 8001     Session 01 (1 modul)
  ...
```

### `./aswaya unduh <url>`

```bash
./aswaya unduh "https://aswaya.pradita.ac.id/webservice/pluginfile.php/88/mod_resource/content/1/slide-html.pdf"
./aswaya unduh "<url>" --tujuan materi/minggu-1/
```

| Argumen    | Keterangan                                                                  |
|------------|-----------------------------------------------------------------------------|
| `url`      | url berkas dari `isi`, `pengumpulan`, atau `diskusi`                        |
| `--tujuan` | path berkas atau direktori (akhiri dengan `/`); bawaannya `data/unduhan/`   |
| `--timpa`  | timpa berkas yang sudah ada                                                 |

Path relatif dihitung dari akar proyek. Hanya berkas di host Aswaya yang bisa
diunduh.

### `./aswaya fungsi [teks]`

Fungsi web service yang boleh dipakai token, disaring dengan potongan nama.
Fungsi yang ditandai `(tulis: perlu --kirim)` hanya dipratinjau oleh
`./aswaya panggil` tanpa `--kirim`.

## Perintah tulis

Tanpa `--kirim` tidak ada yang dikirim; yang dicetak ringkasan, peringatan, dan
permintaan yang akan dikirim (tanpa token):

```
Uji coba: belum ada yang dikirim ke Aswaya. Periksa pratinjaunya, lalu ulangi dengan kirim=True (CLI: --kirim) setelah disetujui.

  kursus_id: 5515
  kursus: Pengembangan Aplikasi Web (Serpong)
  forum_id: 501
  forum: Pengumuman
  subjek: Kuis minggu depan
  isi: Kuis dimulai pukul 08.00.

POST https://aswaya.pradita.ac.id/webservice/rest/server.php  (wsfunction=mod_forum_add_discussion, wstoken disembunyikan)
  forumid  501
  subject  Kuis minggu depan
  message  <p>Kuis dimulai pukul 08.00.</p>

Tidak ada yang dikirim. Tambahkan --kirim untuk mengirim sungguhan.
```

Dengan `--kirim`, permintaannya dikirim sekali dan jawaban Aswaya dicetak. Kode
keluarnya 1 kalau kiriman tidak sepenuhnya berhasil, mis. pesan ke salah satu
penerima gagal.

### `./aswaya umumkan <kursus_id>`

```bash
./aswaya umumkan 5515 --subjek "Kuis minggu depan" --isi "Kuis dimulai pukul 08.00."
./aswaya umumkan 5515 --subjek "Kuis minggu depan" --isi "..." --kirim
```

| Argumen    | Wajib | Keterangan                                           |
|------------|-------|------------------------------------------------------|
| `--subjek` | ya    | subjek pengumuman (paling panjang 255 karakter)      |
| `--isi`    | ya    | isi; `-` dibaca dari stdin                           |
| `--html`   |       | isi sudah berupa HTML                                |
| `--kirim`  |       | benar-benar mengirim                                 |

### `./aswaya beri-nilai <tugas_id> <user_id>`

```bash
./aswaya beri-nilai 77 101 --nilai 90 --umpan-balik "Rapi. Tambahkan validasi form."
```

| Argumen          | Wajib | Keterangan                                              |
|------------------|-------|---------------------------------------------------------|
| `--nilai`        | ya    | tidak boleh negatif atau melebihi nilai maksimum tugas  |
| `--umpan-balik`  |       | umpan balik; `-` dibaca dari stdin                      |
| `--html`         |       | umpan balik sudah berupa HTML                           |
| `--kirim`        |       | benar-benar menyimpan                                   |

Rencananya menyebut nama mahasiswa, nilai lama, nilai baru, dan nilai maksimum.

### `./aswaya pesan`

```bash
./aswaya pesan --ke 101,102 --teks "Jangan lupa tugas 1."
./aswaya pesan --ke 101 --ke 102 --teks - --kirim < pesan.txt
```

| Argumen   | Wajib | Keterangan                                       |
|-----------|-------|--------------------------------------------------|
| `--ke`    | ya    | userid penerima; boleh diulang atau dipisah koma |
| `--teks`  | ya    | isi pesan; `-` dibaca dari stdin                 |
| `--html`  |       | teks sudah berupa HTML                           |
| `--kirim` |       | benar-benar mengirim                             |

### `./aswaya tambah-section <kursus_id>`

```bash
./aswaya tambah-section 5026 --nama "Session "{08..14}
./aswaya tambah-section 5026 --nama "Session "{08..14} --kirim
```

| Argumen   | Wajib | Keterangan                                                  |
|-----------|-------|-------------------------------------------------------------|
| `--nama`  | ya    | satu atau beberapa nama, berurutan; satu section per nama   |
| `--paksa` |       | tetap tambahkan walau namanya sudah terpakai di kursus itu  |
| `--kirim` |       | benar-benar menambahkan (login web, butuh ASWAYA_PASSWORD)  |

Bash menjabarkan `"Session "{08..14}` menjadi `Session 08` sampai `Session 14`.
Rencananya dicetak sebagai langkah sesi web:

```
Langkah lewat sesi web (sesskey dibaca dari halaman saat dikirim):
  1. GET https://aswaya.pradita.ac.id/course/changenumsections.php?courseid=5026&insertsection=0&numsections=7&sesskey=<sesskey dari sesi web>
  2. POST https://aswaya.pradita.ac.id/lib/ajax/service.php?sesskey=<sesskey dari sesi web>&info=core_update_inplace_editable
     core_update_inplace_editable {"component": "format_topics", "itemtype": "sectionname", "itemid": "<id section nomor 8>", "value": "Session 08"}
  ...
```

Sesudah `--kirim`, setiap section baru diperiksa ulang lewat
`core_course_get_contents` dan hasilnya dicetak per section.

### `./aswaya ubah-nama-section <kursus_id> <section_id>`

```bash
./aswaya ubah-nama-section 5026 8003 --nama "Session 03: Pewarisan"
```

`section_id` adalah id dari `./aswaya section`, bukan nomor urutnya. Butuh
`ASWAYA_PASSWORD` untuk `--kirim`.

### `./aswaya ubah-ringkasan-section <kursus_id> <section_id>`

```bash
./aswaya ubah-ringkasan-section 5519 62626 --awal --html --isi '<h3>Materi:</h3><p><a href="https://drive.google.com/...">Slides (PDF)</a></p>'
./aswaya ubah-ringkasan-section 5519 62626 --isi 'Slides: https://drive.google.com/...' --kirim
```

| Argumen       | Keterangan                                                              |
|---------------|-------------------------------------------------------------------------|
| `--isi`       | isi baru; `-` dibaca dari stdin                                         |
| `--html`      | isi sudah berupa HTML; tanpa ini teks biasa diubah ke HTML              |
| `--awal`      | taruh di bagian paling atas ringkasan (bawaannya di akhir)              |
| `--ganti`     | ganti seluruh ringkasan                                                 |
| `--tab-sama`  | biarkan tautan dibuka di tab yang sama (bawaannya tab baru)             |
| `--paksa`     | tetap tambahkan walau semua tautannya sudah ada                         |
| `--kirim`     | benar-benar menyimpan lewat login web; butuh `ASWAYA_PASSWORD`          |

### `./aswaya panggil <fungsi>`

```bash
./aswaya panggil core_course_get_contents --parameter '{"courseid": 5515}'
./aswaya panggil mod_forum_get_discussion_posts --parameter '{"discussionid": 301}' --maks 5000
./aswaya panggil core_course_view_course --parameter '{"courseid": 5515}'          # hanya pratinjau
```

| Argumen       | Keterangan                                                             |
|---------------|------------------------------------------------------------------------|
| `--parameter` | objek JSON; `-` dibaca dari stdin                                      |
| `--kirim`     | jalankan fungsi selain baca                                            |
| `--maks`      | potong hasil baca sepanjang N karakter; `0` (bawaan) berarti utuh      |

Keluarannya selalu JSON. Fungsi yang namanya memuat `_get_`, `_search_`, atau
`_list_` langsung dijalankan; fungsi lain hanya dipratinjau tanpa `--kirim`.

## Kredensial

Dibaca dari `.env` di akar proyek:

```
ASWAYA_URL=https://aswaya.pradita.ac.id
ASWAYA_USERNAME=...
ASWAYA_PASSWORD=...
ASWAYA_TOKEN=
```

Token hasil login disimpan di `~/.cache/aswaya-mcp/` (izin 0600), jadi perintah
berikutnya tidak memakai password lagi. REST API bisa menerima kredensial per
permintaan; MCP selalu memakai setelan ini.
