#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

export ENVIRONMENT=testing
export DEBUG=true

pip install -r requirements/dev.txt -q
pytest -v "$@"
