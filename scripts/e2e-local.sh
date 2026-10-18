#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE=(docker compose -f "$ROOT/docker-compose.dev.yml")
VIDEO="${E2E_VIDEO:-lecture-01.avi}"
MODEL="${E2E_MODEL:-tiny}"
LANGUAGE="${E2E_LANGUAGE:-ru}"
API_URL="${API_URL:-http://localhost:8000}"

if [[ ! -f "$ROOT/api/samples/$VIDEO" ]]; then
  echo "Missing api/samples/$VIDEO; set E2E_VIDEO to a sample file." >&2
  exit 1
fi

echo "Starting API..."
"${COMPOSE[@]}" --profile app up -d --build postgres rabbitmq api

for _ in $(seq 1 60); do
  if curl -fsS "$API_URL/healthz" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done
curl -fsS "$API_URL/healthz" >/dev/null

echo "Creating project and starting a run..."
project_id=$(curl -fsS -X POST "$API_URL/api/v1/projects" \
  -H 'content-type: application/json' \
  -d "{\"name\":\"E2E $(date +%s)\",\"defaults\":{\"model\":\"$MODEL\",\"language\":\"$LANGUAGE\"}}" \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')

curl -fsS -X POST "$API_URL/api/v1/projects/$project_id/items" \
  -H 'content-type: application/json' \
  -d "{\"items\":[{\"path\":\"$VIDEO\"}]}" >/dev/null

start=$(curl -fsS -X POST "$API_URL/api/v1/projects/$project_id/start")
task_id=$(printf '%s' "$start" | python3 -c 'import json,sys; print(json.load(sys.stdin)["task_ids"][0])')
run_id=$(printf '%s' "$start" | python3 -c 'import json,sys; print(json.load(sys.stdin)["run"]["id"])')
echo "project=$project_id run=$run_id task=$task_id"

echo "Building and running the worker..."
"${COMPOSE[@]}" --profile worker build --build-arg "WHISPER_MODEL=$MODEL" worker
"${COMPOSE[@]}" --profile worker run --rm worker

status=$(curl -fsS "$API_URL/api/v1/tasks/$task_id" \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["status"])')
echo "task status: $status"
if [[ "$status" != "succeeded" ]]; then
  exit 1
fi

echo "Transcript:"
curl -fsS "$API_URL/api/v1/tasks/$task_id/files/txt"
