#!/usr/bin/env bash
# Universal Installer for Genspark Master AI Suite Plugin & MCP
# Compatible with Google Antigravity / Gemini CLI, Claude Code, and OpenAI Codex
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
VENV_DIR="$PLUGIN_ROOT/.venv"
PYTHON_BIN="${GENSPARK_INSTALL_PYTHON:-python3}"
INSTALL_BROWSER=1
USE_SYMLINK=0
TARGET_PLATFORM="all"

usage() {
    cat <<EOF
Usage: ./install.sh [OPTIONS]

Options:
  --gemini, --antigravity   Install plugin to Google Antigravity / Gemini CLI (~/.gemini/config/plugins/genspark)
  --claude                  Install plugin to Claude Code (~/.claude/plugins/genspark)
  --codex                   Install plugin to OpenAI Codex (~/.codex/plugins/genspark)
  --all                     Install to all detected platforms (default)
  --link                    Use symlinks instead of copying (recommended for local development)
  --no-browser              Skip Playwright/Chromium installation (CLI & MCP only, no browser automation)
  -h, --help                Show this help message
EOF
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --gemini|--antigravity)
            TARGET_PLATFORM="gemini"
            ;;
        --claude)
            TARGET_PLATFORM="claude"
            ;;
        --codex)
            TARGET_PLATFORM="codex"
            ;;
        --all)
            TARGET_PLATFORM="all"
            ;;
        --link)
            USE_SYMLINK=1
            ;;
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

echo "=========================================================="
echo "⚡ Genspark Master AI Suite — Universal Plugin Installer"
echo "=========================================================="

cd "$PLUGIN_ROOT"

# 1. Check Python version
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    echo "❌ Error: Python 3.10+ is required but '$PYTHON_BIN' was not found." >&2
    exit 1
fi

PY_VERSION=$("$PYTHON_BIN" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "✓ Python runtime: $PYTHON_BIN (v$PY_VERSION)"

# 2. Setup Virtual Environment
if [ ! -x "$VENV_DIR/bin/python" ]; then
    echo "📦 Creating virtual environment at $VENV_DIR..."
    "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

VENV_PYTHON="$VENV_DIR/bin/python"
echo "📦 Upgrading pip & installing dependencies..."
"$VENV_PYTHON" -m pip install --upgrade pip --quiet

if [ "$INSTALL_BROWSER" -eq 1 ]; then
    "$VENV_PYTHON" -m pip install -e '.[all]' --quiet
    echo "🌐 Ensuring Playwright Chromium is installed..."
    "$VENV_PYTHON" -m playwright install chromium || true
else
    "$VENV_PYTHON" -m pip install -e '.[server,mcp]' --quiet
fi

# Ensure bin wrappers are executable
chmod +x "$PLUGIN_ROOT/bin/"* || true
chmod +x "$PLUGIN_ROOT/scripts/"* || true

echo
echo "Installed executables:"
echo "  $VENV_DIR/bin/genspark"
echo "  $VENV_DIR/bin/gsk"
echo "  $VENV_DIR/bin/genspark-mcp"
echo

# Helper function to install to destination
install_to_dest() {
    local dest_dir="$1"
    local name="$2"

    # Don't install over itself if we are already running from destination
    if [ "$PLUGIN_ROOT" = "$dest_dir" ]; then
        echo "  ℹ️ Already running from inside $name directory ($dest_dir)."
        return 0
    fi

    mkdir -p "$(dirname "$dest_dir")"
    if [ "$USE_SYMLINK" -eq 1 ]; then
        echo "  🔗 Linking $name plugin -> $dest_dir"
        rm -rf "$dest_dir"
        ln -s "$PLUGIN_ROOT" "$dest_dir"
    else
        echo "  📋 Copying files to $name plugin -> $dest_dir"
        mkdir -p "$dest_dir"
        # Copy core files excluding dev/cache
        rsync -a --exclude='.git' \
                 --exclude='.venv' \
                 --exclude='__pycache__' \
                 --exclude='*.pyc' \
                 --exclude='.pytest_cache' \
                 --exclude='.DS_Store' \
                 "$PLUGIN_ROOT/" "$dest_dir/"
    fi
}

# 4. Target Platforms Installation
case "$TARGET_PLATFORM" in
    gemini)
        echo "📦 Installing to Google Antigravity / Gemini CLI..."
        install_to_dest "$HOME/.gemini/config/plugins/genspark" "Antigravity/Gemini"
        ;;
    claude)
        echo "📦 Installing to Claude Code..."
        install_to_dest "$HOME/.claude/plugins/genspark" "Claude Code"
        # Also copy skills to ~/.claude/skills if directory exists
        if [ -d "$HOME/.claude/skills" ]; then
            cp -r "$PLUGIN_ROOT/skills/"* "$HOME/.claude/skills/" 2>/dev/null || true
        fi
        ;;
    codex)
        echo "📦 Installing to OpenAI Codex..."
        install_to_dest "$HOME/.codex/plugins/genspark" "OpenAI Codex"
        if [ -d "$HOME/.codex/skills" ]; then
            cp -r "$PLUGIN_ROOT/skills/"* "$HOME/.codex/skills/" 2>/dev/null || true
        fi
        ;;
    all)
        # Antigravity / Gemini CLI
        if [ -d "$HOME/.gemini" ] || [ ! -d "$HOME/.claude" ]; then
            echo "📦 Installing to Google Antigravity / Gemini CLI..."
            install_to_dest "$HOME/.gemini/config/plugins/genspark" "Antigravity/Gemini"
        fi
        # Claude Code
        if [ -d "$HOME/.claude" ]; then
            echo "📦 Installing to Claude Code..."
            install_to_dest "$HOME/.claude/plugins/genspark" "Claude Code"
        fi
        # OpenAI Codex
        if [ -d "$HOME/.codex" ]; then
            echo "📦 Installing to OpenAI Codex..."
            install_to_dest "$HOME/.codex/plugins/genspark" "OpenAI Codex"
        fi
        ;;
esac

echo ""
echo "Offline verification (equivalent to: genspark doctor --json):"
"$VENV_DIR/bin/genspark" doctor --json

echo ""
echo "=========================================================="
echo "🎉 Installation Succeeded! Ready to use Genspark."
echo "=========================================================="
echo "Next steps:"
echo "  1. 🔑 Browser Login (one-time):"
echo "     genspark auth login"
echo "  2. 💬 Quick Test:"
echo "     genspark chat ask \"Hello!\""
echo "  3. 🎨 Image Generation:"
echo "     genspark image create \"Cyberpunk neon street\" --model flux-2-pro"
echo "  4. 🤖 Agent Integration:"
echo "     Restart Antigravity / Gemini CLI to activate the newly installed plugin."
echo "=========================================================="
