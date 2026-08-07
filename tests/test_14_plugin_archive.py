import json
import subprocess
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = Path(
    "/Users/todyle/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py"
)


def test_mcp_uses_plugin_relative_launcher():
    payload = json.loads((ROOT / ".mcp.json").read_text(encoding="utf-8"))
    server = payload["mcpServers"]["genspark"]
    assert server["command"] == "./scripts/run-mcp.sh"
    assert server["cwd"] == "."


def test_build_plugin_archive_is_minimal_and_valid(tmp_path):
    output = tmp_path / "genspark-master.plugin"
    result = subprocess.run(
        [
            str(ROOT / ".venv" / "bin" / "python"),
            str(ROOT / "scripts" / "build_plugin.py"),
            "--output",
            str(output),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert output.is_file()

    with zipfile.ZipFile(output) as archive:
        names = set(archive.namelist())
        assert ".codex-plugin/plugin.json" in names
        assert ".mcp.json" in names
        assert "scripts/install.sh" in names
        assert "scripts/run-mcp.sh" in names
        assert "skills/gen-setup/SKILL.md" in names
        assert "genspark_cli/mcp.py" in names
        assert not any(
            forbidden in name.split("/")
            for name in names
            for forbidden in {".venv", "dist", "build", "tests", "__pycache__"}
        )
        assert not any(name.endswith((".pyc", "recaptcha_token.txt", "storage_state.json")) for name in names)
        assert (archive.getinfo("scripts/install.sh").external_attr >> 16) & 0o111
        archive.extractall(tmp_path / "extracted")

    validation = subprocess.run(
        [str(ROOT / ".venv" / "bin" / "python"), str(VALIDATOR), str(tmp_path / "extracted")],
        capture_output=True,
        text=True,
    )
    assert validation.returncode == 0, validation.stdout + validation.stderr
