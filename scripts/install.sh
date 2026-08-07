#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
VENV_DIR="$PLUGIN_ROOT/.venv"
PYTHON_BIN="${GENSPARK_INSTALL_PYTHON:-python3}"
INSTALL_BROWSER=1

usage() {
    echo "Usage: ./scripts/install.sh [--no-browser]"
    echo "  --no-browser  Install CLI, proxy, and MCP support without Playwright/Chromium."
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --no-browser)
            INSTALL_BROWSER=0
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
    shift
done

cd "$PLUGIN_ROOT"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    echo "Python 3.10+ is required but '$PYTHON_BIN' was not found." >&2
    exit 1
fi

if [ ! -x "$VENV_DIR/bin/python" ]; then
    "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

VENV_PYTHON="$VENV_DIR/bin/python"
"$VENV_PYTHON" -m pip install --upgrade pip

if [ "$INSTALL_BROWSER" -eq 1 ]; then
    "$VENV_PYTHON" -m pip install -e '.[all]'
    "$VENV_PYTHON" -m playwright install chromium
else
    "$VENV_PYTHON" -m pip install -e '.[server,mcp]'
fi

echo
echo "Installed executables:"
echo "  $VENV_DIR/bin/genspark"
echo "  $VENV_DIR/bin/gsk"
echo "  $VENV_DIR/bin/genspark-mcp"
echo
echo "Browser authentication:"
echo "  $VENV_DIR/bin/genspark auth login"
echo
echo "MCP registration examples (run only when you want to change that client):"
echo "  claude mcp add genspark -- $VENV_DIR/bin/genspark-mcp"
echo "  gemini mcp add genspark $VENV_DIR/bin/genspark-mcp"
echo "  JSON: {\"mcpServers\":{\"genspark\":{\"command\":\"$VENV_DIR/bin/genspark-mcp\"}}}"
echo
echo "Offline verification (equivalent to: genspark doctor --json):"
"$VENV_DIR/bin/genspark" doctor --json
