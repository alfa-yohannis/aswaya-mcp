#!/usr/bin/env bash
# Contoh memakai REST API Aswaya dari baris perintah.
# Jalankan API-nya lebih dulu: ./aswaya api
#
# Permintaan di sini tidak membawa kredensial, jadi server memakai
# ASWAYA_USERNAME/ASWAYA_PASSWORD (atau ASWAYA_TOKEN) dari .env-nya sendiri.
# Untuk mengirimnya per permintaan, tambahkan header X-Aswaya-Token, atau
# X-Aswaya-Username dan X-Aswaya-Password.
#
#   examples/klien_api.sh [kursus_id]

set -euo pipefail

API="${ASWAYA_API:-http://localhost:8000}"
KURSUS="${1:-}"

echo "== cek akses"
curl -s -X POST "$API/sesi" -H 'Content-Type: application/json' -d '{}'

echo -e "\n\n== kursus saya"
curl -s "$API/kursus" |
	python3 -c '
import json, sys
for satu in json.load(sys.stdin)["kursus"]:
    print("  ", satu["id"], satu["fullname"])
'

if [[ -z "$KURSUS" ]]; then
	echo -e "\nBeri id kursus sebagai argumen untuk melihat tugas dan pengumuman."
	exit 0
fi

echo -e "\n== tugas di kursus $KURSUS"
curl -s "$API/kursus/$KURSUS/tugas" |
	python3 -c '
import json, sys
for satu in json.load(sys.stdin)["tugas"]:
    print("  ", satu["id"], satu["nama"], "tenggat", satu["tenggat"])
'

echo -e "\n== pratinjau pengumuman (uji coba, tidak dikirim)"
curl -s -X POST "$API/kursus/$KURSUS/pengumuman" -H 'Content-Type: application/json' \
	-d '{"subjek": "Contoh pengumuman", "isi": "Ini hanya uji coba dari examples/klien_api.sh."}' |
	python3 -c 'import json, sys; isi = json.load(sys.stdin); print("  ", isi.get("pesan") or isi.get("detail")); print("  ", isi.get("ringkasan", ""))'
