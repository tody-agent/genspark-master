import re
import subprocess
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_skills_use_canonical_plugin_layout():
    expected = {"gen-setup", "gen-chat", "gen-imagegen"}
    found = {path.parent.name for path in (ROOT / "skills").glob("*/SKILL.md")}
    assert found == expected
    assert not list((ROOT / "skills").glob("gen-*.md"))


def test_skill_frontmatter_has_only_required_discovery_keys():
    for path in (ROOT / "skills").glob("*/SKILL.md"):
        text = path.read_text(encoding="utf-8")
        match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
        assert match, f"missing YAML frontmatter: {path}"
        keys = {
            line.split(":", 1)[0].strip()
            for line in match.group(1).splitlines()
            if line and not line.startswith(" ") and ":" in line
        }
        assert keys == {"name", "description"}
        assert f"name: {path.parent.name}" in match.group(1)


def test_installer_is_non_destructive_and_uses_supported_extra():
    script = (ROOT / "scripts" / "install.sh").read_text(encoding="utf-8")
    assert "set -euo pipefail" in script
    assert "'.[all]'" in script or '".[all]"' in script
    assert "--no-browser" in script
    assert ".zshrc" not in script
    assert ".bashrc" not in script
    assert ".bash_profile" not in script
    assert "$HOME/.local/bin" not in script
    assert "genspark doctor --json" in script


def test_installer_has_valid_bash_syntax():
    result = subprocess.run(
        ["bash", "-n", str(ROOT / "scripts" / "install.sh")],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_readme_local_links_resolve():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    for target in re.findall(r"\[[^]]+\]\(([^)]+)\)", text):
        if target.startswith(("http://", "https://", "#", "mailto:")):
            continue
        local_target = target.split("#", 1)[0]
        assert (ROOT / local_target).exists(), f"broken README link: {target}"


def test_requirements_matches_core_project_dependencies():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    requirements = {
        line.strip()
        for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }
    assert requirements == set(project["project"]["dependencies"])


def test_gate_covers_every_test_module():
    script = (ROOT / "scripts" / "test_gate.sh").read_text(encoding="utf-8")
    assert "-m pytest tests -q" in script
    assert "-m compileall -q genspark_cli" in script
    assert "validate_plugin.py" in script
    assert "test_06_image_models.py" not in script
