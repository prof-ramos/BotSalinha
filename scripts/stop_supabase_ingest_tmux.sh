#!/usr/bin/env bash
set -euo pipefail
SESSION_NAME="${SESSION_NAME:-supabase_ingest}"

if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
  tmux kill-session -t "$SESSION_NAME"
  echo "stopped session=$SESSION_NAME"
else
  echo "session not found: $SESSION_NAME"
fi
