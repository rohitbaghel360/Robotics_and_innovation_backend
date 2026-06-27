#!/usr/bin/env bash
# Manual deploy helper (same steps CI runs on the server)
set -euo pipefail

ENV="${1:?Usage: deploy-remote.sh <testing|production>}"
COMPOSE_FILE="docker-compose.${ENV}.yml"

if [[ ! -f "$COMPOSE_FILE" ]]; then
  echo "Unknown environment: $ENV"
  exit 1
fi

docker compose -f "$COMPOSE_FILE" pull
docker compose -f "$COMPOSE_FILE" up -d
docker compose -f "$COMPOSE_FILE" ps
