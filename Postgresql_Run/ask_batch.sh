#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ "$#" -ne 1 ]; then
  echo "Usage: $0 questions.jsonl" >&2
  exit 2
fi

DB_WORKSPACE="$SCRIPT_DIR/DemoResult" \
  python3 -u "$SCRIPT_DIR/workflow.py" batch-answer --questions "$1"
