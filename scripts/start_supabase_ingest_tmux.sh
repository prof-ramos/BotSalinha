#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="/root/BotSalinha"
SESSION_NAME="${SESSION_NAME:-supabase_ingest}"
LOG_FILE="${LOG_FILE:-/root/BotSalinha/data/ingest_supabase_tmux.log}"
PID_FILE="${PID_FILE:-/root/BotSalinha/data/ingest_supabase_tmux.pid}"

mkdir -p "$(dirname "$LOG_FILE")" "$(dirname "$PID_FILE")"

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

if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
  echo "session already exists: $SESSION_NAME"
  tmux ls | grep "$SESSION_NAME" || true
  exit 0
fi

CMD="cd $ROOT_DIR && \
PYTHONUNBUFFERED=1 \
PYTHONPATH=$ROOT_DIR \
OPENAI_API_KEY='$OPENAI_API_KEY' \
BOTSALINHA_RAG__SUPABASE__URL='$BOTSALINHA_RAG__SUPABASE__URL' \
BOTSALINHA_RAG__SUPABASE__SERVICE_KEY='$BOTSALINHA_RAG__SUPABASE__SERVICE_KEY' \
BOTSALINHA_DATABASE__URL='${BOTSALINHA_DATABASE__URL:-sqlite:////root/BotSalinha/data/botsalinha.db}' \
MAX_DOCS='${MAX_DOCS:-0}' \
SUPABASE_BATCH_SIZE='${SUPABASE_BATCH_SIZE:-100}' \
INGEST_CHECKPOINT_FILE='${INGEST_CHECKPOINT_FILE:-/root/BotSalinha/data/ingest_supabase_checkpoint.jsonl}' \
INGEST_ERROR_LOG_FILE='${INGEST_ERROR_LOG_FILE:-/root/BotSalinha/data/ingest_supabase_errors.log}' \
python3 $ROOT_DIR/scripts/ingest_docs_to_supabase.py >> $LOG_FILE 2>&1"

tmux new-session -d -s "$SESSION_NAME" "bash -lc \"$CMD\""

sleep 1
if ! tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
  echo "failed to create tmux session: $SESSION_NAME" >&2
  exit 1
fi

# Try to capture process PID from pane
PANE_PID=$(tmux list-panes -t "$SESSION_NAME" -F '#{pane_pid}' | head -n1)
echo "$PANE_PID" > "$PID_FILE"

echo "started session=$SESSION_NAME pane_pid=$PANE_PID log=$LOG_FILE pid_file=$PID_FILE"
echo "monitor: tail -f $LOG_FILE"
echo "attach: tmux attach -t $SESSION_NAME"
echo "stop: tmux kill-session -t $SESSION_NAME"
