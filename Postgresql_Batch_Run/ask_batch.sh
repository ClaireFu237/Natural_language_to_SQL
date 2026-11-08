#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ "$#" -eq 0 ]; then
  echo "Usage: $0 questions.jsonl [additional workflow options]" >&2
  exit 2
fi

QUESTIONS_FILE="$1"
shift
python3 "$SCRIPT_DIR/workflow.py" batch-answer --questions "$QUESTIONS_FILE" "$@"
