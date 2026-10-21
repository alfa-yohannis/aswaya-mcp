#!/usr/bin/env python3
"""Contoh menempelkan REST API Aswaya ke aplikasi FastAPI milik sendiri.

Rute paket ini dikumpulkan di `router`, jadi tidak harus dijalankan sebagai
server terpisah dan bisa hidup berdampingan dengan rute Anda sendiri.

    pip install "aswaya-mcp[api] @ git+https://github.com/alfa-yohannis/aswaya-mcp.git"
    uvicorn examples.api_sendiri:app --port 8000

Lalu buka http://localhost:8000/docs; rute /aswaya/... muncul bersama /versi.
"""

from __future__ import annotations

from fastapi import FastAPI

from aswaya_mcp import __version__
from aswaya_mcp.api import router

# Kalau Moodle kampus Anda beralamat lain, tetapkan sekali di sini alih-alih
# menyediakan aswaya.yaml. Setelan dari kode mengalahkan environment dan berkas.
# from aswaya_mcp import atur_setelan
# atur_setelan(url="https://lms.kampuslain.ac.id")

app = FastAPI(title="Aplikasi Saya", version="0.1.0")

# Prefix bebas; endpoint jadi /aswaya/kursus, /aswaya/tugas/{id}/pengumpulan, dan seterusnya
app.include_router(router, prefix="/aswaya", tags=["aswaya"])


@app.get("/versi", summary="Rute milik aplikasi ini sendiri")
def versi() -> dict:
    """Versi aplikasi contoh dan versi aswaya-mcp yang terpasang."""
    return {"aplikasi": "0.1.0", "aswaya_mcp": __version__}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, port=8000)
