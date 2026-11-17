#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r backend/requirements.txt
if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env. Set HTTP_USER_AGENT to include a real operator contact before using public OSM services."
fi
export PYTHONPATH=backend
exec uvicorn app.main:app --app-dir backend --env-file .env --host 127.0.0.1 --port 8000 --reload
