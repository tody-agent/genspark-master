import os
import stat
from pathlib import Path

import pytest

from genspark_cli.profiles import ProfileManager
from genspark_cli.session import SessionManager
from genspark_cli.storage import atomic_write_text, direct_child, validate_profile_name


def test_session_files_are_private(tmp_path):
    session = SessionManager(str(tmp_path))
    session.save_storage_state(
        {"cookies": [{"name": "ai_session", "value": "browser-cookie"}]}
    )
    session.save_recaptcha_token("browser-token")

    for filename in ("session.json", "storage_state.json", "recaptcha_token.txt"):
        path = tmp_path / filename
        assert path.is_file()
        if os.name == "posix":
            assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_atomic_write_preserves_old_file_when_replace_fails(tmp_path, monkeypatch):
    target = tmp_path / "session.json"
    atomic_write_text(target, "old")

    def fail_replace(source, destination):
        raise OSError("replace failed")

    monkeypatch.setattr(os, "replace", fail_replace)

    with pytest.raises(OSError, match="replace failed"):
        atomic_write_text(target, "new")

    assert target.read_text() == "old"
    assert not list(tmp_path.glob(".session.json.*.tmp"))


@pytest.mark.parametrize(
    "name",
    ["../escape", "a/b", ".", "..", "work account", "", "name\x00suffix"],
)
def test_profile_name_validation_rejects_unsafe_names(name):
    with pytest.raises(ValueError, match="Invalid profile name"):
        validate_profile_name(name)


@pytest.mark.parametrize(
    "name",
    ["../escape", "a/b", ".", "..", "work account", "", "name\x00suffix"],
)
def test_every_profile_operation_rejects_unsafe_names(tmp_path, name):
    manager = ProfileManager(str(tmp_path))

    with pytest.raises(ValueError, match="Invalid profile name"):
        manager.get_session(name)
    with pytest.raises(ValueError, match="Invalid profile name"):
        manager.remove_profile(name)


def test_direct_child_returns_only_a_valid_immediate_child(tmp_path):
    assert direct_child(tmp_path, "work_1") == tmp_path.resolve() / "work_1"


def test_remove_profile_rejects_symlink_without_touching_target(tmp_path):
    manager = ProfileManager(str(tmp_path / "sessions"))
    external = tmp_path / "outside"
    external.mkdir()
    marker = external / "keep.txt"
    marker.write_text("keep")

    link = manager._profiles_dir / "linked"
    link.symlink_to(external, target_is_directory=True)

    with pytest.raises(ValueError, match="Unsafe profile path"):
        manager.remove_profile("linked")

    assert marker.read_text() == "keep"


def test_profile_config_is_private(tmp_path):
    ProfileManager(str(tmp_path))
    config_path = tmp_path / "config.json"

    assert config_path.is_file()
    if os.name == "posix":
        assert stat.S_IMODE(config_path.stat().st_mode) == 0o600
