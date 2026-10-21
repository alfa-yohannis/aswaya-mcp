# Contoh Aswaya

Contoh siap jalan untuk ketiga mode. Semuanya butuh Python 3.10+ dan kredensial
Aswaya di `.env` (salin dari `.env.contoh`).

| Berkas           | Mode     | Isi                                              |
|------------------|----------|--------------------------------------------------|
| `prompt_mcp.md`  | MCP      | prompt siap salin untuk asisten AI               |
| `mcp_klien.json` | MCP      | konfigurasi server untuk klien MCP selain Claude |
| `klien_api.sh`   | REST API | memakai REST API dari `curl`                     |
| `api_sendiri.py` | REST API | menempel router ke aplikasi FastAPI sendiri      |
| `pustaka.py`     | Pustaka  | memakai `aswaya_mcp` dari program Python sendiri |

## 1. MCP

```bash
claude mcp add aswaya-mcp -- /path/ke/aswaya-mcp/aswaya mcp
```

Lalu minta asisten Anda:

> Tampilkan kursus saya semester ini, lalu siapa saja yang belum mengumpulkan
> tugas terakhir di tiap kursus.

Prompt lain di [prompt_mcp.md](prompt_mcp.md). Untuk klien MCP selain Claude
Code, pakai [mcp_klien.json](mcp_klien.json).

## 2. REST API

```bash
./aswaya api                 # terminal pertama
examples/klien_api.sh 5515   # terminal kedua; kredensial dari .env server
```

Untuk menempelkan rutenya ke aplikasi FastAPI Anda sendiri:

```bash
.venv/bin/uvicorn examples.api_sendiri:app --port 8000
```

Buka <http://localhost:8000/docs>; rute `/aswaya/...` muncul berdampingan dengan
rute milik aplikasi contoh itu sendiri.

## 3. Pustaka

```bash
.venv/bin/python examples/pustaka.py
```

Mencetak kursus Anda, lalu ringkasan pengumpulan tugas pertama di kursus
terbaru. Hanya membaca.

## Lewat CLI

```bash
./aswaya cek-login
./aswaya kursus
./aswaya tugas 5515
./aswaya pengumpulan 77
```
