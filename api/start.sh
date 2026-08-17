#!/usr/bin/env bash
# Render start command. Run from the api/ directory (see render.yaml).
# Fresh deploy each boot: apply migrations, re-seed demo data (--force wipes
# and reloads so slots are always fresh), then serve on Render's $PORT.
set -euo pipefail

python -m app.migrate
python -m app.seed --force
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
