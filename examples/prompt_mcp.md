# Contoh prompt untuk MCP Aswaya

Permintaan siap salin untuk asisten AI setelah server `aswaya-mcp` didaftarkan
(lihat [../docs/MCP.md](../docs/MCP.md)). Kredensial diambil sendiri dari
`.env`; asisten tidak perlu dan tidak boleh menanyakan kata sandi.

## Memeriksa akses

```
Cek apakah akses Aswaya saya jalan, dan sebutkan versi Moodle-nya.
```

```
Tampilkan kursus saya yang dimulai semester ini, dengan id-nya.
```

## Memantau kelas

```
Di kelas Pengembangan Aplikasi Web, siapa saja yang belum mengumpulkan Tugas 1?
Pisahkan yang masih draf dan yang belum sama sekali.
```

```
Tugas apa saja yang menunggu saya nilai dalam dua minggu ke depan?
```

```
Mahasiswa mana di kursus 5515 yang belum pernah membuka kursusnya?
```

```
Rangkum diskusi di forum Diskusi Umum kursus 5515 minggu ini dan sebutkan
pertanyaan yang belum dijawab.
```

## Berkas

```
Unduh semua berkas pengumpulan Tugas 1 ke data/tugas-1/, satu folder per
mahasiswa.
```

## Menulis (selalu uji coba dulu)

```
Buat pengumuman di kursus 5515: kuis minggu depan dimulai pukul 08.00 di
ruang 3.02. Tunjukkan pratinjaunya dulu, jangan kirim sebelum saya setuju.
```

```
Beri Peter Parker nilai 90 untuk Tugas 1 dengan umpan balik "Rapi, tambahkan
validasi form." Tampilkan nilai lamanya dulu.
```

```
Kirim pesan ke mahasiswa yang belum mengumpulkan Tugas 1, ingatkan tenggatnya.
Tunjukkan daftar penerima sebelum mengirim.
```

```
Tambahkan Session 08 sampai Session 14 di kursus 5026. Tunjukkan section yang
sudah ada dan posisi section barunya dulu.
```

## Yang perlu diketahui

- Tool baca bisa dipanggil kapan saja. Alat yang menulis (`kirim_pengumuman`,
  `beri_nilai`, `kirim_pesan`, `tambah_section`, `ubah_nama_section`, dan
  `panggil_fungsi` untuk fungsi selain baca) bawaannya uji coba; asisten perlu
  persetujuan Anda sebelum memanggilnya dengan `kirim=True`.
- Email dan NIM mahasiswa hanya diambil kalau Anda memintanya.
- `tambah_section` dan `ubah_nama_section` login lewat halaman web dengan
  password dari `.env`. Kalau halaman login meminta captcha atau MFA, asisten
  akan menyampaikannya dan tidak mencoba jalan lain.
