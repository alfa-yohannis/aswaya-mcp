# Referensi MCP Aswaya

Server MCP membuka kemampuan yang sama dengan REST API dan CLI, sehingga asisten
AI bisa memakai sendiri LMS Aswaya atas nama dosen. Tiga belas dari sembilan
belas tool-nya hanya membaca Aswaya. Enam sisanya bisa menulis, dengan uji coba
sebagai bawaannya.

## Menjalankan

### 1. Pasang

Butuh Python 3.10+.

```bash
git clone https://github.com/alfa-yohannis/aswaya-mcp.git
cd aswaya-mcp
./aswaya uji              # jalankan pertama menyiapkan .venv + dependensi
```

Atau sebagai paket:
`pip install "aswaya-mcp[mcp] @ git+https://github.com/alfa-yohannis/aswaya-mcp.git"`.

### 2. Isi kredensial

Isi `.env` pada akar proyek, disalin dari `.env.contoh`:

```
ASWAYA_URL=https://aswaya.pradita.ac.id
ASWAYA_USERNAME=nama.anda@pradita.ac.id
ASWAYA_PASSWORD=...
ASWAYA_TOKEN=
```

Cukup password atau token; kalau keduanya ada, token dipakai lebih dulu.
`tambah_section`, `ubah_nama_section`, dan `ubah_ringkasan_section` login lewat
halaman web, jadi ketiganya butuh password. Tool MCP tidak menerima username, password, maupun token lewat
parameter, jadi asisten tidak pernah memegangnya. Token hasil login disimpan di
`~/.cache/aswaya-mcp/` (izin 0600); lihat README bagian Kredensial.

### 3. Cek servernya hidup

```bash
./aswaya mcp        # atau aswaya-mcp kalau terpasang sebagai paket
```

Server bicara JSON-RPC lewat stdio, jadi terminal akan tampak diam menunggu
masukan. Itu memang benar. Ctrl-C untuk berhenti.

### 4. Daftarkan

Untuk Claude Code:

```bash
claude mcp add aswaya-mcp -s user -- /path/ke/aswaya-mcp/aswaya mcp
claude mcp list                      # pastikan muncul "✔ Connected"
```

`-s user` membuatnya tersedia dari direktori mana pun. Kalau terpasang sebagai
paket, perintahnya cukup `claude mcp add aswaya-mcp -s user -- aswaya-mcp`.

Untuk Codex, formatnya TOML di `~/.codex/config.toml`:

```toml
[mcp_servers.aswaya-mcp]
command = "/path/ke/aswaya-mcp/aswaya"
args = ["mcp"]
```

Untuk Antigravity, sunting `~/.gemini/config/mcp_config.json` (global) atau
`.agents/mcp_config.json` (per ruang kerja):

```json
{
  "mcpServers": {
    "aswaya-mcp": {
      "command": "/path/ke/aswaya-mcp/aswaya",
      "args": ["mcp"]
    }
  }
}
```

Untuk klien MCP lain, pakai [../examples/mcp_klien.json](../examples/mcp_klien.json).

### 5. Coba

Minta asisten Anda:

```
Cek apakah akses Aswaya saya jalan, lalu tampilkan kursus semester ini.
```

```
Siapa saja yang belum mengumpulkan Tugas 1 di kelas Pengembangan Aplikasi Web?
```

Contoh prompt lain di [../examples/prompt_mcp.md](../examples/prompt_mcp.md).

## Mengaktifkan setelah didaftarkan

Daftar server dibaca saat klien dijalankan, jadi entri baru tidak muncul di sesi
yang sedang berlangsung:

| Klien       | Cara memuat                                          | Cara memeriksa                     |
|-------------|------------------------------------------------------|------------------------------------|
| Claude Code | mulai sesi baru                                      | `claude mcp list` → `✔ Connected`  |
| Codex       | jalankan ulang Codex                                 | `codex mcp list` → `enabled`       |
| Antigravity | tombol refresh di Manage MCP Servers, atau jalankan ulang | panel yang sama; di CLI ketik `/mcp` |

Tool yang hanya membaca aman diizinkan otomatis: `cek_login`, `daftar_kursus`,
`isi_kursus`, `peserta_kursus`, `daftar_tugas`, `pengumpulan_tugas`,
`nilai_kursus`, `daftar_forum`, `diskusi_forum`, `tenggat`, `daftar_section`,
dan `fungsi_tersedia`. `unduh_berkas` menulis ke disk lokal; izinkan kalau Anda
nyaman asisten menyimpan berkas di sana. Biarkan `kirim_pengumuman`,
`beri_nilai`, `kirim_pesan`, `tambah_section`, `ubah_nama_section`,
`ubah_ringkasan_section`, dan `panggil_fungsi` tetap meminta persetujuan setiap kali dipanggil. Di Claude Code
nama izinnya berbentuk `mcp__aswaya-mcp__daftar_kursus`.

## Tool

| Tool                | Parameter                                                   | Hasil                                           |
|---------------------|-------------------------------------------------------------|-------------------------------------------------|
| `cek_login`         | `login_ulang?`                                              | situs, pemakai, userid, release, jumlah fungsi  |
| `daftar_kursus`     | `cari?`                                                     | kursus yang diikuti pemakai                     |
| `isi_kursus`        | `kursus_id`                                                 | section, modul, dan berkas                      |
| `peserta_kursus`    | `kursus_id`, `peran?`, `lengkap?` (bawaan `false`)          | peserta; email dan NIM hanya dengan `lengkap`   |
| `daftar_tugas`      | `kursus_id`                                                 | tugas beserta tenggat dan nilai maksimum        |
| `pengumpulan_tugas` | `tugas_id`                                                  | status, berkas, dan nilai per mahasiswa         |
| `nilai_kursus`      | `kursus_id`                                                 | item nilai dan nilai setiap mahasiswa           |
| `daftar_forum`      | `kursus_id`                                                 | forum kursus, termasuk forum pengumuman         |
| `diskusi_forum`     | `forum_id`                                                  | diskusi beserta pesan pembukanya                |
| `tenggat`           | `hari?` (bawaan 30), `kursus_id?`                           | kegiatan yang menunggu tindakan                 |
| `unduh_berkas`      | `url`, `tujuan?`, `timpa?`                                  | path berkas lokal                               |
| `daftar_section`    | `kursus_id`                                                 | section: id, nomor, nama, jumlah modul          |
| `fungsi_tersedia`   | `cari?`                                                     | wsfunction yang boleh dipakai token             |
| `panggil_fungsi`    | `nama`, `parameter?`, `kirim?` (bawaan `false`), `maks_karakter?` | hasil fungsi baca, atau pratinjau          |
| `kirim_pengumuman`  | `kursus_id`, `subjek`, `isi`, `kirim?`, `bentuk?`           | pratinjau, atau id diskusi baru                 |
| `beri_nilai`        | `tugas_id`, `user_id`, `nilai`, `umpan_balik?`, `kirim?`, `bentuk?` | pratinjau nilai lama dan baru           |
| `kirim_pesan`       | `user_ids`, `teks`, `kirim?`, `bentuk?`                     | pratinjau penerima, atau status per penerima    |
| `tambah_section`    | `kursus_id`, `nama` (daftar), `kirim?`, `paksa?`            | rencana posisi, atau hasil yang sudah diperiksa |
| `ubah_nama_section` | `kursus_id`, `section_id`, `nama`, `kirim?`                 | nama lama dan baru, atau hasil yang diperiksa   |
| `ubah_ringkasan_section` | `kursus_id`, `section_id`, `isi`, `cara?`, `bentuk?`, `tab_baru?`, `kirim?`, `paksa?` | ringkasan lama dan baru, atau hasil yang diperiksa |

Setiap tool membalas `ok`. Kalau `ok` bernilai `false`, `pesan` menjelaskan
sebabnya: kredensial belum diisi, login ditolak, fungsi tidak tersedia untuk
token ini, isian yang ditolak, atau galat dari Aswaya. Tool yang menulis juga
membawa `terkirim`; artinya ada di bagian [Alat yang menulis](#alat-yang-menulis).

Contoh di bawah memakai data karangan.

### `cek_login`

Membuat klien baru (jadi perubahan `.env` langsung terbaca), memastikan tokennya
bisa dipakai, lalu memakai klien itu untuk tool berikutnya. `login_ulang=true`
memaksa login dengan password walaupun ada token di setelan atau cache.

```json
{ "ok": true, "situs": "Aswaya Pradita University E-Learning", "url": "https://aswaya.pradita.ac.id",
  "nama": "Clark Kent", "username": "clark.kent", "userid": 7,
  "release": "4.1.9 (Build: 20240212)", "versi": "2022112809", "jumlah_fungsi": 412,
  "sumber_token": "cache", "cache_token": "/home/anda/.cache/aswaya-mcp/token-0a6b17fc35870f15e040345e.json" }
```

`sumber_token` bernilai `setelan` (ASWAYA_TOKEN), `cache`, atau `login`. Kalau
gagal, balasannya membawa `diagnosis` dari konfigurasi publik situs (layanan
mobile aktif atau tidak, sedang dipelihara atau tidak), kalau situsnya
terjangkau.

### `daftar_kursus`

Kursus yang diikuti pemakai (`core_enrol_get_users_courses`), terbaru dulu.
`cari` mencocokkan nama lengkap, nama pendek, dan nama kategori tanpa
membedakan huruf besar dan kecil.

```json
{ "ok": true, "jumlah": 1, "cari": "web",
  "kursus": [{ "id": 5515, "shortname": "IF140303-SRP", "fullname": "Pengembangan Aplikasi Web (Serpong)",
               "kategori": "Informatika", "kategori_id": 3, "mulai": "2026-09-01", "selesai": "2027-01-31",
               "visible": true, "url": "https://aswaya.pradita.ac.id/course/view.php?id=5515" }] }
```

Nama kategori dibaca lewat `core_course_get_categories`; kalau fungsi itu tidak
tersedia, `kategori` bernilai `null` dan `kategori_id` tetap ada.

### `isi_kursus`

Section dan modul satu kursus (`core_course_get_contents`). Ringkasan section
dan deskripsi modul diubah ke teks biasa lalu dipotong.

```json
{ "ok": true, "kursus_id": 5515, "jumlah_section": 2, "jumlah_modul": 3,
  "section": [{ "id": 9001, "nomor": 1, "nama": "Pertemuan 1", "visible": true, "ringkasan": "",
    "modul": [{ "id": 1233, "nama": "Slide HTML Dasar", "jenis": "resource", "instance": 61, "visible": true,
                "url": "https://aswaya.pradita.ac.id/mod/resource/view.php?id=1233",
                "deskripsi": "Bacaan wajib sebelum kelas.", "tanggal": [],
                "berkas": [{ "nama": "slide-html.pdf", "tipe": "file", "path": "/", "ukuran": 245760,
                             "jenis": "application/pdf", "diubah": "2026-09-02T10:00+07:00",
                             "url": "https://aswaya.pradita.ac.id/webservice/pluginfile.php/88/mod_resource/content/1/slide-html.pdf" }] }] }] }
```

`url` berkas tidak membawa token. Teruskan ke `unduh_berkas`, yang menambahkan
tokennya sendiri. Modul berjenis `url` membawa tautan luar dengan `tipe`
`url`; tautan seperti itu tidak bisa diunduh lewat `unduh_berkas`.

### `peserta_kursus`

`core_enrol_get_enrolled_users` dengan opsi `userfields`, jadi Aswaya hanya
mengirim bidang yang diminta. `peran` mencocokkan shortname atau nama peran,
mis. `student`, `editingteacher`, atau `teacher`.

```json
{ "ok": true, "kursus_id": 5515, "peran": "student", "lengkap": false, "jumlah": 4,
  "peran_tersedia": [{ "shortname": "student", "nama": "Mahasiswa", "jumlah": 4 },
                     { "shortname": "editingteacher", "nama": "Dosen", "jumlah": 1 }],
  "peserta": [{ "id": 101, "nama": "Peter Parker", "peran": ["student"], "grup": ["Kelas A"],
                "akses_terakhir": "2026-10-19T20:00+07:00", "akses_terakhir_situs": "2026-10-20T08:15+07:00" }] }
```

`akses_terakhir` adalah akses terakhir ke kursus itu (`null` kalau belum
pernah), `akses_terakhir_situs` ke Aswaya secara umum. Dengan `lengkap=true`,
tiap peserta juga membawa `email` dan `idnumber` (NIM). Pakai hanya kalau
pemakai memang membutuhkannya.

### `daftar_tugas`

```json
{ "ok": true, "kursus_id": 5515, "kursus": "Pengembangan Aplikasi Web (Serpong)", "jumlah": 1,
  "tugas": [{ "id": 77, "cmid": 1234, "nama": "Tugas 1: Halaman Statis",
              "dibuka": "2026-09-01T08:00+07:00", "tenggat": "2026-09-15T23:59+07:00",
              "batas_akhir": "2026-09-17T23:59+07:00", "tenggat_penilaian": "2026-09-22T23:59+07:00",
              "nilai_maks": 100.0, "skala_id": null, "berkelompok": false,
              "url": "https://aswaya.pradita.ac.id/mod/assign/view.php?id=1234",
              "deskripsi": "Buat halaman profil dengan HTML." }],
  "peringatan": [] }
```

`id` adalah `tugas_id` untuk `pengumpulan_tugas` dan `beri_nilai`. `nilai_maks`
bernilai `null` untuk tugas tanpa nilai atau berskala (`skala_id` terisi).
Kursus yang tidak bisa dibuka akun ini menghasilkan `tugas` kosong dan pesan
Moodle di `peringatan`.

### `pengumpulan_tugas`

Gabungan `mod_assign_list_participants` (semua peserta, termasuk yang belum
mengumpulkan), `mod_assign_get_submissions`, dan `mod_assign_get_grades`.

```json
{ "ok": true, "tugas_id": 77,
  "ringkasan": { "peserta": 4, "dikumpulkan": 1, "draf": 1, "belum": 2, "dinilai": 1, "perlu_dinilai": 1 },
  "mahasiswa": [{ "user_id": 101, "nama": "Peter Parker", "grup": "Kelas A", "status": "submitted",
                  "keterangan": "sudah dikumpulkan", "perlu_dinilai": true, "perpanjangan": false,
                  "waktu_kumpul": "2026-09-14T21:30+07:00", "percobaan": 0,
                  "berkas": [{ "nama": "profil-peter.zip", "ukuran": 10240, "jenis": "application/zip",
                               "url": "https://aswaya.pradita.ac.id/webservice/pluginfile.php/90/assignsubmission_file/submission_files/1/profil-peter.zip",
                               "diubah": "2026-09-02T10:00+07:00" }],
                  "teks_daring": "Tautan repo saya ada di berkas.", "nilai": 85.0,
                  "dinilai_pada": "2026-09-18T09:00+07:00" }],
  "peringatan": [] }
```

`status` memakai nilai Moodle: `new` (belum mengumpulkan), `draft`,
`submitted`, dan `reopened`. `nilai` bernilai `null` kalau belum dinilai (Moodle
menyimpan -1). Teks daring dipotong 2000 karakter. Pengumpulan tugas
berkelompok dipasangkan ke setiap anggota grupnya. Kalau
`mod_assign_list_participants` tidak tersedia, yang muncul hanya mahasiswa yang
pernah membuka tugasnya, dengan catatan di `peringatan`.

### `nilai_kursus`

`gradereport_user_get_grade_items` untuk semua mahasiswa.

```json
{ "ok": true, "kursus_id": 5515, "jumlah_item": 3, "jumlah_mahasiswa": 1,
  "item": [{ "id": 401, "nama": "Tugas 1: Halaman Statis", "jenis": "mod", "modul": "assign", "cmid": 1234, "maks": 100.0 },
           { "id": 402, "nama": "Kuis HTML", "jenis": "mod", "modul": "quiz", "cmid": 1240, "maks": 10.0 },
           { "id": 400, "nama": "Total kursus", "jenis": "course", "modul": null, "cmid": null, "maks": 100.0 }],
  "mahasiswa": [{ "user_id": 101, "nama": "Peter Parker", "nilai": { "401": 85.0, "402": 9.0, "400": 47.0 } }],
  "peringatan": [] }
```

`nilai` berkunci id item (sebagai teks) dan berisi nilai mentah; untuk item
berskala, nilainya nomor butir skala. NIM tidak ikut; cocokkan lewat `user_id`
dengan `peserta_kursus(lengkap=true)` kalau perlu.

### `daftar_forum` dan `diskusi_forum`

```json
{ "ok": true, "kursus_id": 5515, "jumlah": 2,
  "forum": [{ "id": 501, "cmid": 1200, "nama": "Pengumuman", "jenis": "news", "pengumuman": true,
              "jumlah_diskusi": 1, "bisa_membuat_diskusi": true,
              "url": "https://aswaya.pradita.ac.id/mod/forum/view.php?id=1200", "deskripsi": "" }] }
```

```json
{ "ok": true, "forum_id": 502, "jumlah": 1,
  "diskusi": [{ "id": 301, "subjek": "Tanya soal CSS", "penulis": "Peter Parker",
                "dibuat": "2026-09-10T10:00+07:00", "diubah": "2026-09-11T08:00+07:00",
                "jumlah_balasan": 2, "belum_dibaca": 1, "disematkan": false, "dikunci": false,
                "pesan": "Bagaimana cara flexbox?", "lampiran": [],
                "url": "https://aswaya.pradita.ac.id/mod/forum/discuss.php?d=301" }] }
```

Diskusi dibaca per halaman sampai habis (paling banyak 2000). Pesan pembukanya
dipotong 1000 karakter. Balasan sebuah diskusi bisa dibaca dengan
`panggil_fungsi("mod_forum_get_discussion_posts", {"discussionid": 301})`.

### `tenggat`

Action events kalender Moodle mulai pukul 00.00 hari ini (WIB) sampai `hari`
hari ke depan, terdekat dulu. Bagi dosen, isinya antara lain tugas yang
menunggu dinilai beserta jumlahnya.

```json
{ "ok": true, "dari": "2026-09-20T00:00+07:00", "sampai": "2026-10-20T10:30+07:00", "kursus_id": null, "jumlah": 1,
  "kegiatan": [{ "id": 601, "nama": "Tugas 1: Halaman Statis perlu dinilai", "waktu": "2026-09-22T23:59+07:00",
                 "kursus_id": 5515, "kursus": "Pengembangan Aplikasi Web (Serpong)", "modul": "assign",
                 "aktivitas": "Tugas 1: Halaman Statis", "jenis": "gradingdue", "tindakan": "Nilai",
                 "jumlah_item": 1, "bisa_ditindak": true, "lewat": false,
                 "url": "https://aswaya.pradita.ac.id/mod/assign/view.php?id=1234" }] }
```

`hari` antara 1 dan 366. `kursus_id` membatasi ke satu kursus
(`core_calendar_get_action_events_by_course`).

### `unduh_berkas`

`url` adalah url berkas dari `isi_kursus`, `pengumpulan_tugas`, atau
`diskusi_forum`. Alamat `pluginfile.php` biasa diubah ke versi webservice-nya.
`tujuan` boleh path berkas atau direktori (akhiri dengan `/`); kosong berarti
`data/unduhan/` di akar proyek, dan path relatif dihitung dari akar proyek.

```json
{ "ok": true, "path": "/path/ke/aswaya-mcp/data/unduhan/slide-html.pdf", "nama_berkas": "slide-html.pdf",
  "ukuran": 245760, "jenis": "application/pdf" }
```

Berkas yang sudah ada tidak ditimpa kecuali `timpa=true`. Alamat di host lain
ditolak, dan pengalihan ke host lain (berkas yang tersimpan sebagai tautan ke
layanan luar) tidak diikuti supaya token tidak ikut terkirim.

### `daftar_section`

```json
{ "ok": true, "kursus_id": 5026, "url": "https://aswaya.pradita.ac.id/course/view.php?id=5026", "jumlah": 8,
  "section": [{ "id": 8000, "nomor": 0, "nama": "Umum", "visible": true, "jumlah_modul": 0 },
              { "id": 8007, "nomor": 7, "nama": "Session 07", "visible": true, "jumlah_modul": 1 }] }
```

`id` adalah `section_id` untuk `ubah_nama_section`; `nomor` adalah urutannya di
halaman kursus.

### `fungsi_tersedia`

```json
{ "ok": true, "jumlah": 3, "jumlah_semua": 412, "cari": "forum",
  "fungsi": [{ "nama": "mod_forum_add_discussion", "baca": false },
             { "nama": "mod_forum_get_forum_discussions", "baca": true },
             { "nama": "mod_forum_get_forums_by_courses", "baca": true }] }
```

`baca` bernilai true untuk fungsi yang langsung dijalankan `panggil_fungsi`.

### `panggil_fungsi`

`parameter` berupa objek JSON sesuai dokumentasi fungsi Moodle-nya; perataannya
ke bentuk form Moodle (`options[0][name]` dan seterusnya) dikerjakan sendiri.
Fungsi baca langsung dijalankan:

```json
{ "ok": true, "fungsi": "core_course_get_contents", "jenis": "baca", "terpotong": false, "panjang": 1320,
  "hasil": [ ... ] }
```

Hasil yang JSON-nya lebih panjang dari `maks_karakter` (bawaan 20000; 0 berarti
utuh) dikembalikan sebagai potongan teks di `hasil_json` dengan
`terpotong: true`. Nilai berkunci `token`, `privatetoken`, `wstoken`, dan
`userprivateaccesskey` diganti `***`. Fungsi lain dikembalikan sebagai pratinjau
dengan `jenis: "tulis"`, berbentuk sama dengan alat tulis lainnya.

## Alat yang menulis

`kirim_pengumuman`, `beri_nilai`, `kirim_pesan`, `tambah_section`,
`ubah_nama_section`, `ubah_ringkasan_section`, dan `panggil_fungsi` untuk fungsi
selain baca. Semuanya
bawaannya `kirim=false`, dan balasannya berbentuk sama:

| Field        | Isi                                                                     |
|--------------|-------------------------------------------------------------------------|
| `kirim`      | `false` untuk uji coba                                                  |
| `terkirim`   | permintaan sudah sampai ke Aswaya                                       |
| `fungsi`     | wsfunction, atau langkah sesi web untuk section                         |
| `ringkasan`  | keterangan untuk dibaca pemakai sebelum menyetujui                      |
| `permintaan` | yang dikirim apa adanya, tanpa token dan tanpa sesskey                  |
| `hasil`      | jawaban Aswaya sesudah kiriman                                          |
| `berhasil`   | `false` kalau sebagian gagal (mis. pesan ke salah satu penerima)        |
| `peringatan` | hal yang perlu diketahui sebelum mengirim                               |
| `pesan`      | ringkasan satu kalimat                                                  |

Kalau gagal, balasannya `{ "ok": false, "terkirim": ..., "pesan": "..." }`.
`terkirim: false` berarti tidak ada yang berubah di Aswaya: isian ditolak,
fungsi tidak tersedia, atau Aswaya menolak permintaannya. `terkirim: true`
berarti permintaannya sudah berangkat tetapi hasilnya tidak bisa dipastikan.
Jangan mengirim ulang sebelum memeriksa lewat tool baca.

### `kirim_pengumuman`

Mencari forum berjenis `news` di kursus itu, lalu `mod_forum_add_discussion`.
Pratinjaunya:

```json
{ "ok": true, "kirim": false, "terkirim": false, "fungsi": "mod_forum_add_discussion",
  "ringkasan": { "kursus_id": 5515, "kursus": "Pengembangan Aplikasi Web (Serpong)", "forum_id": 501,
                 "forum": "Pengumuman", "subjek": "Kuis minggu depan",
                 "isi": "Kuis dimulai pukul 08.00.\n\nMateri: https://contoh.ac.id/kuis" },
  "permintaan": { "metode": "POST", "url": "https://aswaya.pradita.ac.id/webservice/rest/server.php",
                  "wsfunction": "mod_forum_add_discussion",
                  "parameter": { "forumid": 501, "subject": "Kuis minggu depan",
                                 "message": "<p>Kuis dimulai pukul 08.00.</p><p>Materi: <a href=\"https://contoh.ac.id/kuis\">https://contoh.ac.id/kuis</a></p>" },
                  "isian": { "forumid": "501", "subject": "Kuis minggu depan", "message": "..." } },
  "hasil": null, "berhasil": true, "peringatan": [],
  "pesan": "Uji coba: belum ada yang dikirim ke Aswaya. ..." }
```

Sesudah `kirim=true`, `hasil` berisi `discussionid` dan `ringkasan.url`
menunjuk diskusi barunya. Moodle selalu menyimpan pesan forum sebagai HTML, jadi
`isi` berbentuk teks diubah dulu; `bentuk="html"` mengirimnya apa adanya.
Kursus tanpa forum pengumuman, atau akun yang tidak boleh menulis di sana,
ditolak sebelum apa pun dikirim.

### `beri_nilai`

`mod_assign_save_grade` untuk percobaan terakhir (`attemptnumber=-1`), tanpa
membuka percobaan baru, dan untuk tugas berkelompok hanya bagi mahasiswa itu
(`applytoall=0`). Pratinjau menyebut nilai lama dan nilai maksimumnya:

```json
{ "ringkasan": { "tugas_id": 77, "tugas": "Tugas 1: Halaman Statis", "kursus": "Pengembangan Aplikasi Web (Serpong)",
                 "user_id": 101, "mahasiswa": "Peter Parker", "status_pengumpulan": "submitted",
                 "nilai_lama": 85.0, "nilai_baru": 90.0, "nilai_maks": 100.0,
                 "umpan_balik": "Rapi. Tambahkan validasi form." } }
```

Nilai negatif, di atas nilai maksimum, atau untuk tugas tanpa nilai ditolak.
`umpan_balik` kosong membiarkan umpan balik lama; kalau diisi, dikirim lewat
`plugindata[assignfeedbackcomments_editor]`. Kalau umpan balik komentar tidak
aktif di tugas itu, `peringatan` menyebutnya. Jawaban Moodle untuk fungsi ini
`null`, jadi periksa hasilnya dengan `pengumpulan_tugas`. Tugas yang memakai
panduan penilaian lanjutan (rubrik) mengabaikan nilai ini.

### `kirim_pesan`

`core_message_send_instant_messages`, satu pesan yang sama untuk setiap id di
`user_ids`. Pratinjau menyebut nama setiap penerima, dan id yang tidak dikenal
ditolak. Sesudah kiriman, `hasil` berisi status per penerima:

```json
{ "ok": false, "terkirim": true, "berhasil": false,
  "hasil": [{ "user_id": 101, "terkirim": true, "msgid": 7000, "galat": null },
            { "user_id": 104, "terkirim": false, "msgid": -1, "galat": "The user is unable to be messaged" }],
  "pesan": "Pesan terkirim ke 1 dari 2 penerima; ..." }
```

Jangan kirim ulang ke penerima yang sudah berhasil.

### `tambah_section`

Menambah section di akhir kursus, satu per nama, lewat login web dengan password
dari `.env`. Pratinjaunya menyebut section yang ada, posisi section baru, dan
langkah yang akan dijalankan:

```json
{ "ok": true, "kirim": false, "terkirim": false,
  "fungsi": "course/changenumsections.php + core_update_inplace_editable",
  "ringkasan": { "kursus_id": 5026, "kursus": "Pemrograman Berorientasi Objek", "format": "topics",
                 "section_sekarang": [{ "id": 8007, "nomor": 7, "nama": "Session 07" }],
                 "section_baru": [{ "nomor": 8, "nama": "Session 08" }, { "nomor": 9, "nama": "Session 09" }],
                 "jumlah_baru": 2 },
  "permintaan": { "langkah": [
      { "metode": "GET", "url": "https://aswaya.pradita.ac.id/course/changenumsections.php",
        "parameter": { "courseid": 5026, "insertsection": 0, "numsections": 2, "sesskey": "<sesskey dari sesi web>" } },
      { "metode": "POST", "url": "https://aswaya.pradita.ac.id/lib/ajax/service.php",
        "parameter": { "sesskey": "<sesskey dari sesi web>", "info": "core_update_inplace_editable" },
        "methodname": "core_update_inplace_editable",
        "args": { "component": "format_topics", "itemtype": "sectionname",
                  "itemid": "<id section nomor 8>", "value": "Session 08" } } ] } }
```

Contoh di atas dipendekkan. Sesudah `kirim=true`, setiap section baru diperiksa
ulang:

```json
{ "hasil": { "section_baru": [{ "id": 8100, "nomor": 8, "nama_diminta": "Session 08", "galat": null,
                                "nama_sekarang": "Session 08", "sesuai": true }],
             "belum_ditambahkan": [], "section_lain_tanpa_nama": [] } }
```

`ok` bernilai `berhasil`: semua section bertambah dan bernama sesuai
permintaan. Kalau tidak ada yang bertambah, biasanya karena batas section
kursus (bawaan Moodle 52) atau hak akses, `belum_ditambahkan` memuat semua nama
dan tidak ada yang perlu dibatalkan. Nama yang sudah terpakai di kursus itu
ditolak kecuali `paksa=true`. Kalau halaman login memuat captcha atau Aswaya
meminta MFA, balasannya `ok: false` dengan pesan yang menyebut hal itu.

### `ubah_nama_section`

Satu `core_update_inplace_editable` lewat sesi web. `section_id` adalah id dari
`daftar_section`, bukan nomornya; section milik kursus lain ditolak.

```json
{ "ringkasan": { "kursus_id": 5026, "kursus": "Pemrograman Berorientasi Objek", "format": "topics",
                 "section_id": 8003, "nomor": 3, "nama_lama": "Session 03", "nama_baru": "Session 03: Pewarisan" } }
```

Sesudah kiriman, `hasil` berisi `nama_sekarang`, `sesuai`, dan `tampil` (nama
yang dikembalikan Moodle).

### `ubah_ringkasan_section`

Form `course/editsection.php` lewat sesi web: isian form dibaca utuh, hanya
`summary_editor[text]` yang diganti. Cocok untuk menaruh teks atau tautan di
section General (nomor 0). `cara` bernilai `tambah` (di akhir, bawaan), `awal`
(di bagian paling atas), atau `ganti` (seluruh ringkasan). `isi` berupa teks
biasa atau HTML dengan `bentuk="html"`; `tab_baru=true` (bawaan) membuat setiap
tautan di isi baru dibuka di tab baru. Kalau semua tautannya sudah ada,
`tambah` dan `awal` ditolak kecuali `paksa=true`.

```json
{ "ringkasan": { "kursus_id": 5519, "section_id": 62626, "nomor": 0, "nama": "General", "cara": "awal",
                 "tautan_baru": ["https://drive.google.com/file/d/.../view?usp=sharing"],
                 "ringkasan_lama": "<h3>Kuesioner Penelitian:</h3>...", "ringkasan_baru": "<h3>Materi:</h3>..." } }
```

Sesudah kiriman, `hasil` berisi `ringkasan_sekarang`, `sesuai`, `tautan_ada`,
dan `url_kursus`.

## Catatan untuk agen

- Jangan meminta kata sandi atau token ke pemakai. Kalau `pesan` menyebut
  kredensial belum ada, minta pemakai mengisi `.env` sendiri.
- Urutan yang disarankan: `cek_login`, lalu `daftar_kursus` untuk mendapatkan
  `kursus_id`, lalu tool per kursus. `tugas_id` datang dari `daftar_tugas`,
  `forum_id` dari `daftar_forum`, dan `section_id` dari `daftar_section`.
- Jalankan setiap alat tulis dengan `kirim=false` lebih dulu, tunjukkan
  `ringkasan`, `peringatan`, dan `permintaan` ke pemakai, lalu kirim dengan
  `kirim=true` hanya setelah pemakai menyetujuinya.
- Kalau balasannya `terkirim: true` dengan `ok: false`, jangan mengirim ulang.
  Periksa dulu lewat tool baca dan laporkan hasilnya ke pemakai.
- Minta `lengkap=true` di `peserta_kursus` hanya kalau email atau NIM memang
  dibutuhkan untuk pekerjaan yang diminta.
- Kalau login web terhalang captcha atau MFA, sampaikan apa adanya ke pemakai
  dan jangan mencari jalan lain.
- Untuk fungsi Moodle yang tidak punya tool sendiri, cari namanya dengan
  `fungsi_tersedia`, lalu pakai `panggil_fungsi`.
