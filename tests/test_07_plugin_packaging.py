import importlib.util
import json
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_plugin_manifest_matches_root_and_components():
    manifest = json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text())

    assert manifest["name"] == "genspark-master"
    assert manifest["version"] == "0.5.0"
    assert manifest["skills"] == "./skills/"
    assert manifest["mcpServers"] == "./.mcp.json"
    assert isinstance(manifest["interface"]["defaultPrompt"], list)
    assert 1 <= len(manifest["interface"]["defaultPrompt"]) <= 3
    assert (ROOT / ".mcp.json").is_file()


def test_mcp_manifest_declares_installed_stdio_entrypoint():
    manifest = json.loads((ROOT / ".mcp.json").read_text())

    assert manifest == {
        "mcpServers": {
            "genspark": {
                "command": "./scripts/run-mcp.sh",
                "args": [],
                "cwd": ".",
            }
        }
    }


def test_python_entrypoints_include_short_alias_and_mcp():
    payload = tomllib.loads((ROOT / "pyproject.toml").read_text())
    scripts = payload["project"]["scripts"]

    assert payload["project"]["version"] == "0.5.0"
    assert scripts == {
        "genspark": "genspark_cli.cli:main",
        "gsk": "genspark_cli.cli:main",
        "genspark-mcp": "genspark_cli.mcp:run_mcp_server",
    }
    assert {"browser", "stealth", "server", "mcp", "dev", "all"} <= set(
        payload["project"]["optional-dependencies"]
    )


def test_all_declared_entrypoint_modules_are_importable():
    assert importlib.util.find_spec("genspark_cli.cli") is not None
    assert importlib.util.find_spec("genspark_cli.mcp") is not None
