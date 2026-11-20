#!/usr/bin/env bash
set -eu
cd -- "$(dirname -- "$0")/.."
if [[ ! -x .venv/bin/python ]]; then
    echo "Instale primeiro com python3 scripts/install.py." >&2
    exit 1
fi
exec .venv/bin/python -m app.serve "${1:-dev}"
