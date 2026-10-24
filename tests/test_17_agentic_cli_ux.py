import json
from pathlib import Path
from click.testing import CliRunner
import pytest

from genspark_cli.account_router import AccountRouter
from genspark_cli.cli import main
from genspark_cli.exceptions import QuotaExhaustedError, RateLimitError
from genspark_cli.parser import ChatResponse
from genspark_cli.profiles import ProfileManager


def _seed_two_accounts(session_dir: Path) -> ProfileManager:
    pm = ProfileManager(str(session_dir))
    for name in ("default", "acc2"):
        s = pm.get_session("default") if name == "default" else pm.add_profile(name)
        s.save_storage_state({"cookies": [{"name": "ai_session", "value": f"c-{name}"}]})
        s.save_recaptcha_token(f"tok-{name}")
    return pm


def test_pool_status_strategy_reset_and_import_cli(tmp_path):
    env = {"GENSPARK_SESSION_DIR": str(tmp_path)}
    runner = CliRunner()

    # Import two accounts via CLI
    state_file = tmp_path / "exported_state.json"
    state_file.write_text(
        json.dumps({"cookies": [{"name": "ai_session", "value": "cookie-val"}]}),
        encoding="utf-8",
    )

    r_imp1 = runner.invoke(
        main,
        ["pool", "import", "default", str(state_file), "--token", "tok-1"],
        env=env,
    )
    assert r_imp1.exit_code == 0

    r_imp2 = runner.invoke(
        main,
        ["pool", "import", "work", str(state_file), "--token", "tok-2"],
        env=env,
    )
    assert r_imp2.exit_code == 0

    # Check pool status JSON
    r_status = runner.invoke(main, ["pool", "status", "--json"], env=env)
    assert r_status.exit_code == 0
    data = json.loads(r_status.stdout)
    assert data["pool_size"] == 2
    assert data["available_count"] == 2
    assert data["strategy"] == "round-robin"

    # Change strategy via CLI
    r_strat = runner.invoke(main, ["pool", "strategy", "least-used"], env=env)
    assert r_strat.exit_code == 0
    r_status2 = runner.invoke(main, ["pool", "status", "--json"], env=env)
    assert json.loads(r_status2.stdout)["strategy"] == "least-used"

    # Mark an account unhealthy, then reset via CLI
    router = AccountRouter(ProfileManager(str(tmp_path)))
    router.mark_unhealthy("default", reason="RateLimitError", cooldown=300)
    assert router.available_count == 1

    r_reset = runner.invoke(main, ["pool", "reset"], env=env)
    assert r_reset.exit_code == 0
    assert AccountRouter(ProfileManager(str(tmp_path))).available_count == 2


def test_config_show_and_set_cli(tmp_path):
    env = {"GENSPARK_SESSION_DIR": str(tmp_path)}
    runner = CliRunner()

    r_set = runner.invoke(
        main,
        ["config", "set", "concurrency", "5"],
        env=env,
    )
    assert r_set.exit_code == 0

    r_set_model = runner.invoke(
        main,
        ["config", "set", "model", "deepseek-v4.1-flash"],
        env=env,
    )
    assert r_set_model.exit_code == 0

    r_show = runner.invoke(main, ["config", "show", "--json"], env=env)
    assert r_show.exit_code == 0
    cfg = json.loads(r_show.stdout)
    assert cfg["max_concurrency_per_account"] == 5
    assert cfg["default_model"] == "deepseek-v4.1-flash"


def test_shorthand_prompt_and_chat_ask_auto_failover(tmp_path, monkeypatch):
    _seed_two_accounts(tmp_path)
    env = {"GENSPARK_SESSION_DIR": str(tmp_path)}
    runner = CliRunner()

    attempted_profiles = []

    def fake_run_chat(session, prompt, model, stream=False, **kwargs):
        attempted_profiles.append(session.profile_name)
        if len(attempted_profiles) == 1:
            raise QuotaExhaustedError("First account out of credits")
        return ChatResponse(
            content=f"Failover success on {session.profile_name}: {prompt}",
            model=model,
            project_id="p-1",
        )

    import genspark_cli.client as client_mod
    monkeypatch.setattr(client_mod, "run_chat", fake_run_chat)

    # 1. Test `genspark chat ask` auto-failover
    res1 = runner.invoke(main, ["chat", "ask", "Hello world", "--raw"], env=env)
    assert res1.exit_code == 0
    assert "Failover success on" in res1.stdout
    assert len(attempted_profiles) == 2

    # 2. Test shorthand `gsk "Direct prompt" --raw`
    AccountRouter(ProfileManager(str(tmp_path))).reset_cooldowns()
    attempted_profiles.clear()
    res2 = runner.invoke(main, ["Direct shorthand prompt", "--raw"], env=env)
    assert res2.exit_code == 0
    assert "Direct shorthand prompt" in res2.stdout
    assert len(attempted_profiles) == 2


def test_batch_cli_json_and_file_io(tmp_path, monkeypatch):
    _seed_two_accounts(tmp_path)
    env = {"GENSPARK_SESSION_DIR": str(tmp_path)}
    runner = CliRunner()

    class FakeBatchChatClient:
        def __init__(self, session, model="claude-opus-5.5"):
            self.session = session

        async def chat(self, prompt, model=None, project_id=None, messages=None):
            return ChatResponse(
                content=f"batch-reply:{prompt}:{self.session.profile_name}",
                model=model or "claude-opus-5.5",
            )

        async def close(self):
            pass

    import genspark_cli.batch as batch_mod
    monkeypatch.setattr(batch_mod, "GensparkClient", FakeBatchChatClient)

    tasks_file = tmp_path / "tasks.jsonl"
    tasks_file.write_text(
        '{"id": "1", "prompt": "Task one"}\n{"id": "2", "prompt": "Task two"}\n',
        encoding="utf-8",
    )
    out_file = tmp_path / "out.jsonl"

    res = runner.invoke(
        main,
        [
            "batch",
            "--input-file",
            str(tasks_file),
            "--output",
            str(out_file),
            "--concurrency",
            "2",
            "--json",
        ],
        env=env,
    )
    assert res.exit_code == 0
    payload = json.loads(res.stdout)
    assert payload["total"] == 2
    assert payload["succeeded"] == 2
    assert out_file.is_file()
    lines = [json.loads(line) for line in out_file.read_text().splitlines() if line.strip()]
    assert len(lines) == 2


def test_config_wizard_cli(tmp_path):
    env = {"GENSPARK_SESSION_DIR": str(tmp_path)}
    runner = CliRunner()

    # Select 2 (least-used), concurrency 4, model 5 (deepseek-v4.1-flash), image model 2 (flux-2-pro)
    res = runner.invoke(
        main,
        ["config", "-i"],
        input="2\n4\n5\n2\n",
        env=env,
    )
    assert res.exit_code == 0
    pm = ProfileManager(str(tmp_path))
    cfg = pm.get_config()
    assert cfg["routing_strategy"] == "least-used"
    assert cfg["max_concurrency_per_account"] == 4
    assert cfg["default_model"] == "deepseek-v4.1-flash"
    assert cfg["default_image_model"] == "flux-2-pro"

