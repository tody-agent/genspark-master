import json

from click.testing import CliRunner

from genspark_cli.cli import main


def test_capabilities_json_is_clean_stdout():
    result = CliRunner().invoke(main, ["capabilities", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert {item["id"] for item in payload["capabilities"]} >= {
        "chat",
        "image",
        "mcp",
        "openai-proxy",
    }
    assert "browser_session" in {
        item["authentication"] for item in payload["capabilities"]
    }
    assert result.stderr == ""


def test_doctor_reports_missing_login_without_failing_json(tmp_path):
    result = CliRunner().invoke(
        main,
        ["doctor", "--json"],
        env={"GENSPARK_SESSION_DIR": str(tmp_path)},
    )

    payload = json.loads(result.stdout)
    assert result.exit_code == 0
    assert payload["status"] == "degraded"
    assert payload["checks"]["browser_session"]["status"] == "missing"
    assert payload["checks"]["network"]["status"] == "not_checked"


def test_doctor_json_error_keeps_stdout_machine_readable(monkeypatch):
    import genspark_cli.cli as cli_module

    def fail_doctor(*args, **kwargs):
        raise OSError("diagnostic exploded")

    monkeypatch.setattr(cli_module, "run_doctor", fail_doctor, raising=False)
    result = CliRunner().invoke(main, ["doctor", "--json"])

    payload = json.loads(result.stdout)
    assert result.exit_code != 0
    assert payload["status"] == "error"
    assert payload["error"]["type"] == "OSError"
    assert "diagnostic exploded" in result.stderr
