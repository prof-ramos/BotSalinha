#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="/root/BotSalinha"
LOG_FILE="${1:-/root/BotSalinha/data/ingest_supabase_bg.log}"
PID_FILE="${2:-/root/BotSalinha/data/ingest_supabase_bg.pid}"

mkdir -p "$(dirname "$LOG_FILE")" "$(dirname "$PID_FILE")"

cd "$ROOT_DIR"

required_envs=(
  OPENAI_API_KEY
  BOTSALINHA_RAG__SUPABASE__URL
  BOTSALINHA_RAG__SUPABASE__SERVICE_KEY
)

for env_name in "${required_envs[@]}"; do
  if [[ -z "${!env_name:-}" ]]; then
    echo "missing required env: $env_name" >&2
    exit 1
  fi
done

nohup env \
  PYTHONUNBUFFERED=1 \
  PYTHONPATH="$ROOT_DIR" \
  OPENAI_API_KEY="${OPENAI_API_KEY}" \
  BOTSALINHA_RAG__SUPABASE__URL="${BOTSALINHA_RAG__SUPABASE__URL}" \
  BOTSALINHA_RAG__SUPABASE__SERVICE_KEY="${BOTSALINHA_RAG__SUPABASE__SERVICE_KEY}" \
  BOTSALINHA_DATABASE__URL="${BOTSALINHA_DATABASE__URL:-sqlite:////root/BotSalinha/data/botsalinha.db}" \
  python3 "$ROOT_DIR/scripts/ingest_docs_to_supabase.py" \
  >> "$LOG_FILE" 2>&1 < /dev/null &

PID=$!
echo "$PID" > "$PID_FILE"
sleep 1
if ! kill -0 "$PID" 2>/dev/null; then
  echo "process failed to start; check log: $LOG_FILE" >&2
  tail -n 50 "$LOG_FILE" >&2 || true
  exit 1
fi

echo "started pid=$PID log=$LOG_FILE pid_file=$PID_FILE"
