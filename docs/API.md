# Referensi REST API Aswaya

## Menjalankan

### 1. Pasang

Butuh Python 3.10+.

```bash
pip install "aswaya-mcp[api] @ git+https://github.com/alfa-yohannis/aswaya-mcp.git"
```

### 2. Hidupkan servernya

```bash
uvicorn aswaya_mcp.api:app --port 8000     # setelah pip install
./aswaya api                               # dari klona; PORT=9001 untuk ganti port
```

### 3. Pastikan hidup

```bash
curl -s localhost:8000/publik
```

`/publik` membaca konfigurasi publik Aswaya tanpa login. Dokumentasi interaktif
ada di <http://localhost:8000/docs>, skema mesin di `/openapi.json`.

### 4. Permintaan pertama

```bash
curl -X POST localhost:8000/sesi -H 'Content-Type: application/json' -d '{}'
```

Contoh lengkap yang bisa dijalankan: [../examples/klien_api.sh](../examples/klien_api.sh).

### Menempel ke aplikasi FastAPI sendiri

```python
from fastapi import FastAPI
from aswaya_mcp.api import router

app = FastAPI()
app.include_router(router, prefix="/aswaya")
```

Contoh utuh: [../examples/api_sendiri.py](../examples/api_sendiri.py).

## Kredensial

Endpoint GET menerima kredensial lewat header: `X-Aswaya-Token`, atau
`X-Aswaya-Username` dan `X-Aswaya-Password`. Endpoint POST menerimanya di badan
JSON: `token`, atau `username` dan `password`. Kosongkan semuanya supaya server
memakai `ASWAYA_USERNAME`, `ASWAYA_PASSWORD`, dan `ASWAYA_TOKEN` dari setelannya
sendiri (`.env`). Mengisi username tanpa password, atau sebaliknya, tanpa token,
dibalas `422`. Kalau token dan password sama-sama dikirim, token dipakai lebih
dulu dan password untuk login ulang.

Klien per kredensial disimpan di memori server selama 15 menit
(`umur_sesi_detik`). Password dan token tidak disimpan apa adanya sebagai kunci;
yang dipakai sidik SHA-256-nya. Token dan cookie milik kredensial per permintaan
tidak pernah ditulis ke cache disk server; hanya kredensial setelan server yang
memakai `~/.cache/aswaya-mcp/`.

Endpoint section (`POST /kursus/{id}/section`,
`POST /kursus/{id}/section/{section_id}/nama`, dan
`POST /kursus/{id}/section/{section_id}/ringkasan`) login lewat halaman web, jadi
butuh password. Dengan token saja, uji cobanya tetap jalan tetapi kiriman
sungguhannya dibalas `400`.

## Endpoint baca

Semua endpoint GET hanya membaca Aswaya. Bentuk balasannya sama dengan tool MCP
bernama serupa, tanpa field `ok`; contoh lengkapnya di [MCP.md](MCP.md).

| Endpoint                              | Tool MCP padanannya   | Parameter query                        |
|---------------------------------------|-----------------------|----------------------------------------|
| `POST /sesi`                          | `cek_login`           | (badan: kredensial)                    |
| `GET /publik`                         | (tanpa login)         |                                        |
| `GET /kursus`                         | `daftar_kursus`       | `cari`                                 |
| `GET /kursus/{kursus_id}/isi`         | `isi_kursus`          |                                        |
| `GET /kursus/{kursus_id}/peserta`     | `peserta_kursus`      | `peran`, `lengkap` (bawaan `false`)    |
| `GET /kursus/{kursus_id}/tugas`       | `daftar_tugas`        |                                        |
| `GET /kursus/{kursus_id}/nilai`       | `nilai_kursus`        |                                        |
| `GET /kursus/{kursus_id}/forum`       | `daftar_forum`        |                                        |
| `GET /kursus/{kursus_id}/section`     | `daftar_section`      |                                        |
| `GET /tugas/{tugas_id}/pengumpulan`   | `pengumpulan_tugas`   |                                        |
| `GET /forum/{forum_id}/diskusi`       | `diskusi_forum`       |                                        |
| `GET /tenggat`                        | `tenggat`             | `hari` (1 sampai 366), `kursus_id`     |
| `GET /fungsi`                         | `fungsi_tersedia`     | `cari`                                 |
| `GET /berkas`                         | `unduh_berkas`        | `url`                                  |

```bash
curl localhost:8000/kursus?cari=web
curl localhost:8000/kursus/5515/peserta?peran=student
curl localhost:8000/kursus/5515/peserta?lengkap=true      # dengan email dan NIM
curl localhost:8000/tugas/77/pengumpulan -H 'X-Aswaya-Token: ...'
```

`GET /berkas` mengalirkan isi berkas apa adanya, alih-alih menyimpannya di disk
server. Nama berkasnya ada di `Content-Disposition`, sebagai `filename` ASCII
untuk klien lama dan `filename*` (RFC 5987) untuk nama utuh. Tokennya hanya
dikirim server ini ke host Aswaya.

```bash
curl -OJ "localhost:8000/berkas?url=https://aswaya.pradita.ac.id/webservice/pluginfile.php/88/mod_resource/content/1/slide-html.pdf"
```

## Endpoint tulis

Bawaannya uji coba: tanpa `"kirim": true`, balasannya pratinjau dan tidak ada
yang dikirim ke Aswaya. Bentuk balasannya `HasilTulis` (`kirim`, `terkirim`,
`fungsi`, `ringkasan`, `permintaan`, `hasil`, `berhasil`, `peringatan`, `pesan`),
sama dengan tool MCP; uraiannya di [MCP.md](MCP.md#alat-yang-menulis).

### `POST /kursus/{kursus_id}/pengumuman`

```json
{ "subjek": "Kuis minggu depan", "isi": "Kuis dimulai pukul 08.00.", "bentuk": "teks", "kirim": false }
```

| Field    | Bawaan  | Keterangan                                             |
|----------|---------|--------------------------------------------------------|
| `subjek` | wajib   | paling panjang 255 karakter                            |
| `isi`    | wajib   | teks biasa (diubah ke HTML) atau HTML                  |
| `bentuk` | `teks`  | `teks` atau `html`                                     |
| `kirim`  | `false` | `true` membuat diskusi di forum pengumuman kursus      |

### `POST /tugas/{tugas_id}/nilai`

```json
{ "user_id": 101, "nilai": 90, "umpan_balik": "Rapi.", "kirim": false }
```

| Field         | Bawaan  | Keterangan                                                 |
|---------------|---------|------------------------------------------------------------|
| `user_id`     | wajib   | userid Moodle mahasiswa                                    |
| `nilai`       | wajib   | tidak boleh negatif atau melebihi nilai maksimum tugas     |
| `umpan_balik` | `""`    | kosong berarti umpan balik lama tidak disentuh             |
| `bentuk`      | `teks`  | bentuk umpan balik: `teks` atau `html`                     |
| `kirim`       | `false` | `true` menyimpan nilai lewat `mod_assign_save_grade`       |

### `POST /pesan`

```json
{ "user_ids": [101, 102], "teks": "Jangan lupa tugas 1.", "kirim": false }
```

Sesudah kiriman, `hasil` berisi status per penerima, dan `berhasil` bernilai
`false` kalau ada yang gagal (balasan tetap `200`).

### `POST /kursus/{kursus_id}/section`

```json
{ "nama": ["Session 08", "Session 09"], "paksa": false, "kirim": false }
```

Menambah section di akhir kursus, satu per nama, lalu memberi namanya. Nama yang
sudah terpakai di kursus itu dibalas `422` kecuali `"paksa": true`.

### `POST /kursus/{kursus_id}/section/{section_id}/nama`

```json
{ "nama": "Session 03: Pewarisan", "kirim": false }
```

### `POST /kursus/{kursus_id}/section/{section_id}/ringkasan`

```json
{ "isi": "<p><a href=\"https://drive.google.com/...\">Slides (PDF)</a></p>", "bentuk": "html",
  "cara": "awal", "tab_baru": true, "paksa": false, "kirim": false }
```

`cara` bernilai `tambah` (di akhir, bawaan), `awal` (paling atas), atau `ganti`.
Tautan yang semuanya sudah ada dibalas `422` kecuali `"paksa": true`.

### `POST /panggil`

```json
{ "nama": "core_course_get_contents", "parameter": {"courseid": 5515}, "kirim": false, "maks_karakter": 0 }
```

Fungsi yang namanya memuat `_get_`, `_search_`, atau `_list_` langsung
dijalankan; fungsi lain hanya dipratinjau kecuali `"kirim": true`.
`maks_karakter` memotong hasil baca (0 berarti utuh).

## Status galat

| Status | Sebab                                                                                   |
|--------|-----------------------------------------------------------------------------------------|
| `400`  | kredensial tidak dikirim dan setelan server juga belum punya; atau login web tanpa password |
| `401`  | login ditolak Aswaya, atau token yang ditolak tidak bisa dipulihkan                     |
| `403`  | fungsi tidak dimuat layanan token ini, atau Aswaya menolak karena hak akses             |
| `404`  | Aswaya tidak menemukan datanya (`invalidrecord` dan sejenisnya)                         |
| `422`  | badan tidak sah, isian yang ditolak sebelum dikirim, atau alamat berkas di luar Aswaya  |
| `502`  | galat lain dari Aswaya atau jaringan, termasuk hasil kiriman yang tidak pasti           |

Galat sesudah kiriman berangkat dibalas `502` dengan `detail` yang menyebut
bahwa permintaannya sudah dikirim. Periksa dulu lewat endpoint baca sebelum
mencoba lagi, karena kiriman tidak pernah diulang otomatis.
