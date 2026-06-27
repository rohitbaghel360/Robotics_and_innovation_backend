#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env from .env.example"
fi

export ENVIRONMENT="${ENVIRONMENT:-local}"
pip install -r requirements/dev.txt -q
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
