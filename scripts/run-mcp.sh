#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
GENSPARK_PLUGIN_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
VENV_PYTHON="$GENSPARK_PLUGIN_ROOT/.venv/bin/python"

if [ -x "$VENV_PYTHON" ]; then
    cd "$GENSPARK_PLUGIN_ROOT"
    exec "$VENV_PYTHON" -m genspark_cli.mcp "$@"
fi

if command -v python3 >/dev/null 2>&1 && PYTHONPATH="$GENSPARK_PLUGIN_ROOT" python3 -c \
    'import httpx, mcp, genspark_cli' >/dev/null 2>&1; then
    cd "$GENSPARK_PLUGIN_ROOT"
    export PYTHONPATH="$GENSPARK_PLUGIN_ROOT${PYTHONPATH:+:$PYTHONPATH}"
    exec python3 -m genspark_cli.mcp "$@"
fi

echo "Genspark MCP runtime is not installed for this plugin." >&2
echo "Run: $GENSPARK_PLUGIN_ROOT/scripts/install.sh --no-browser" >&2
echo "Use the default installer without --no-browser when browser login is needed." >&2
exit 1
