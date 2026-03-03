#!/usr/bin/env bash
set -euo pipefail
SESSION_NAME="${SESSION_NAME:-supabase_ingest}"
LOG_FILE="${LOG_FILE:-/root/BotSalinha/data/ingest_supabase_tmux.log}"

if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
  echo "running session=$SESSION_NAME"
  tmux ls | grep "$SESSION_NAME" || true
  echo "--- last log lines ---"
  tail -n 30 "$LOG_FILE" || true
else
  echo "not running session=$SESSION_NAME"
fi
