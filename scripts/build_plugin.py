#!/usr/bin/env python3
"""Build a minimal, deterministic Codex .plugin archive."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROOT_FILES = (
    ".mcp.json",
    "README.md",
    "pyproject.toml",
    "requirements.txt",
)
TREE_FILES = (
    (Path(".codex-plugin"), {".json"}),
    (Path("skills"), {".md", ".yaml", ".yml", ".json"}),
    (Path("genspark_cli"), {".py"}),
)
SCRIPT_FILES = (
    Path("scripts/install.sh"),
    Path("scripts/run-mcp.sh"),
    Path("scripts/build_plugin.py"),
)
ARCHIVE_TIMESTAMP = (2026, 1, 1, 0, 0, 0)


def _manifest_version() -> str:
    manifest = json.loads(
        (ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
    )
    return manifest["version"]


def _iter_files() -> list[Path]:
    files = [Path(name) for name in ROOT_FILES]
    files.extend(SCRIPT_FILES)
    for tree, suffixes in TREE_FILES:
        files.extend(
            path.relative_to(ROOT)
            for path in (ROOT / tree).rglob("*")
            if path.is_file()
            and path.suffix in suffixes
            and "__pycache__" not in path.parts
        )
    unique = sorted(set(files), key=lambda path: path.as_posix())
    for relative in unique:
        source = ROOT / relative
        if not source.is_file() or source.is_symlink():
            raise RuntimeError(f"Unsafe or missing archive input: {relative}")
    return unique


def _write_entry(archive: zipfile.ZipFile, relative: Path) -> None:
    source = ROOT / relative
    info = zipfile.ZipInfo(relative.as_posix(), ARCHIVE_TIMESTAMP)
    info.create_system = 3
    mode = 0o755 if relative.suffix in {".sh", ".py"} and relative.parts[0] == "scripts" else 0o644
    info.external_attr = (0o100000 | mode) << 16
    info.compress_type = zipfile.ZIP_DEFLATED
    archive.writestr(info, source.read_bytes())


def build(output: Path) -> Path:
    output = output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{output.name}.", suffix=".tmp", dir=output.parent
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        with zipfile.ZipFile(temporary, "w") as archive:
            for relative in _iter_files():
                _write_entry(archive, relative)
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "dist" / f"genspark-master-{_manifest_version()}.plugin",
    )
    args = parser.parse_args()
    print(build(args.output))


if __name__ == "__main__":
    main()
