#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ "$#" -eq 0 ]; then
  read -r -p "Question: " QUESTION
else
  QUESTION="$*"
fi

python3 "$SCRIPT_DIR/workflow.py" answer --question "$QUESTION"
