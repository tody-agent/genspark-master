from click.testing import CliRunner

import genspark_cli.auth as auth_mod
from genspark_cli.cli import main
from genspark_cli.profiles import ProfileManager


def _fake_login(session):
    session.save_storage_state({"cookies": [{"name": "ai_session", "value": f"c-{session.profile_name}"}]})
    session.save_recaptcha_token("tok")
    return True


def test_onboarding_adds_two_accounts(tmp_path, monkeypatch):
    monkeypatch.setattr(auth_mod, "run_login", _fake_login)
    env = {"GENSPARK_SESSION_DIR": str(tmp_path)}
    # step1 ok; add another? y, name acc2; add another? n
    res = CliRunner().invoke(main, ["setup"], input="y\nacc2\nn\n", env=env)
    assert res.exit_code == 0, res.output
    pm = ProfileManager(str(tmp_path))
    logged = {p["name"] for p in pm.list_profiles() if p["is_logged_in"]}
    assert logged == {"default", "acc2"}


def test_accounts_menu_logout_default_and_remove(tmp_path, monkeypatch):
    monkeypatch.setattr(auth_mod, "run_login", _fake_login)
    env = {"GENSPARK_SESSION_DIR": str(tmp_path)}
    runner = CliRunner()
    # add default, add acc2 (via menu 1), quit
    res = runner.invoke(main, ["accounts"], input="1\ndefault\n1\nacc2\n0\n", env=env)
    assert res.exit_code == 0, res.output
    # logout acc2 (#1 is acc2 alphabetically), confirm; then remove acc2 confirm; quit
    res = runner.invoke(main, ["accounts"], input="3\n1\ny\n4\n1\ny\n0\n", env=env)
    assert res.exit_code == 0, res.output
    names = {p["name"] for p in ProfileManager(str(tmp_path)).list_profiles()}
    assert names == {"default"}


def test_home_menu_quit(tmp_path, monkeypatch):
    monkeypatch.setattr(auth_mod, "run_login", _fake_login)
    env = {"GENSPARK_SESSION_DIR": str(tmp_path)}
    res = CliRunner().invoke(main, ["menu"], input="n\n6\n0\n", env=env)
    assert res.exit_code == 0, res.output
    assert "Hướng dẫn nhanh" in res.output
