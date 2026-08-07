"""Static, machine-readable capability discovery for agents and installers."""

from __future__ import annotations

from typing import Any

from . import __version__


def list_capabilities() -> list[dict[str, Any]]:
    """Return local capabilities without inspecting credentials or the network."""
    return [
        {
            "id": "chat",
            "description": "Stream or collect Genspark chat responses.",
            "authentication": "browser_session",
            "interface": "cli",
            "command": "genspark chat ask",
        },
        {
            "id": "image",
            "description": "Generate and download images through Genspark.",
            "authentication": "browser_session",
            "interface": "cli",
            "command": "genspark image generate",
        },
        {
            "id": "mcp",
            "description": "Expose six browser-session tools over MCP stdio.",
            "authentication": "browser_session",
            "interface": "mcp",
            "command": "genspark-mcp",
        },
        {
            "id": "openai-proxy",
            "description": "Serve an OpenAI-compatible local HTTP endpoint.",
            "authentication": "browser_session",
            "interface": "http",
            "command": "genspark server start",
        },
        {
            "id": "doctor",
            "description": "Inspect the local installation and login state offline.",
            "authentication": "none",
            "interface": "cli",
            "command": "genspark doctor --json",
        },
    ]


def capabilities_document() -> dict[str, Any]:
    """Return the versioned capabilities document."""
    return {
        "schema_version": 1,
        "plugin": "genspark-master",
        "version": __version__,
        "authentication": "browser_session",
        "capabilities": list_capabilities(),
    }
