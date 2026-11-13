#!/usr/bin/env bash
# Cetakan - jalankan: ./jalankan.sh
set -e
cd "$(dirname "$0")"
PY=$(command -v python3 || command -v python) || { echo "Python 3 belum terpasang."; exit 1; }
if [ ! -d .venv ]; then
  echo "Menyiapkan Cetakan untuk pertama kali, mohon tunggu..."
  "$PY" -m venv .venv
  .venv/bin/python -m pip install --disable-pip-version-check -q -r requirements.txt
fi
exec .venv/bin/python -m cetakan --port "${PORT:-8000}" --buka
