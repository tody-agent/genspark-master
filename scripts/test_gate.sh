#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
PLUGIN_VALIDATOR="${GENSPARK_PLUGIN_VALIDATOR:-/Users/todyle/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py}"

cd "$PLUGIN_ROOT"

if [ -x ".venv/bin/python" ]; then
    PYTHON=".venv/bin/python"
else
    PYTHON="${GENSPARK_TEST_PYTHON:-python3}"
fi

if [ ! -f "$PLUGIN_VALIDATOR" ]; then
    echo "Plugin validator not found: $PLUGIN_VALIDATOR" >&2
    echo "Set GENSPARK_PLUGIN_VALIDATOR to plugin-creator/scripts/validate_plugin.py" >&2
    exit 1
fi

echo "[1/3] Full pytest suite"
"$PYTHON" -m pytest tests -q

echo "[2/3] Python bytecode compilation"
"$PYTHON" -m compileall -q genspark_cli

echo "[3/3] Codex plugin validation"
"$PYTHON" "$PLUGIN_VALIDATOR" "$PLUGIN_ROOT"

echo "Genspark Master quality gate passed."
