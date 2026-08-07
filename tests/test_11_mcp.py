import importlib
import sys

import pytest

from genspark_cli.exceptions import RateLimitError
from genspark_cli.parser import ChatResponse


class FakeSession:
    def __init__(self, profile_name):
        self.profile_name = profile_name


class FakeRouter:
    def __init__(self, names=("default",)):
        self.sessions = [FakeSession(name) for name in names]
        self.unhealthy = []
        self.successful = []

    def get_session(self, preferred=None):
        available = [s for s in self.sessions if s.profile_name not in self.unhealthy]
        if preferred:
            for session in available:
                if session.profile_name == preferred:
                    return session
        if not available:
            raise RuntimeError("no profiles")
        return available[0]

    def mark_unhealthy(self, name, reason="unknown"):
        self.unhealthy.append(name)

    def mark_success(self, name):
        self.successful.append(name)

    def get_status(self):
        return [{"profile": s.profile_name, "health": "healthy"} for s in self.sessions]


@pytest.mark.asyncio
async def test_chat_tool_uses_router_session_and_shared_client():
    from genspark_cli.mcp import chat

    calls = []

    class FakeChatClient:
        def __init__(self, session):
            calls.append(session.profile_name)

        async def chat(self, prompt, model=None, project_id=None):
            assert prompt == "hello"
            assert model == "claude-opus-4-6"
            return ChatResponse(content="reply", model=model, project_id="project-1")

        async def close(self):
            pass

    result = await chat(
        "hello",
        model="claude-opus-4-6",
        router=FakeRouter(),
        client_factory=FakeChatClient,
    )

    assert result["content"] == "reply"
    assert result["profile"] == "default"
    assert calls == ["default"]


@pytest.mark.asyncio
async def test_chat_failover_is_bounded_and_marks_only_routing_errors():
    from genspark_cli.mcp import chat

    attempts = []
    router = FakeRouter(("first", "second"))

    class FailoverClient:
        def __init__(self, session):
            self.profile = session.profile_name

        async def chat(self, prompt, model=None, project_id=None):
            attempts.append(self.profile)
            if self.profile == "first":
                raise RateLimitError()
            return ChatResponse(content="second reply", model=model)

        async def close(self):
            pass

    result = await chat("hello", router=router, client_factory=FailoverClient)

    assert result["content"] == "second reply"
    assert result["profile"] == "second"
    assert attempts == ["first", "second"]
    assert router.unhealthy == ["first"]


@pytest.mark.asyncio
async def test_programming_errors_are_not_swallowed_or_failed_over():
    from genspark_cli.mcp import chat

    router = FakeRouter(("first", "second"))

    class BrokenClient:
        def __init__(self, session):
            pass

        async def chat(self, prompt, model=None, project_id=None):
            raise ValueError("programming bug")

        async def close(self):
            pass

    with pytest.raises(ValueError, match="programming bug"):
        await chat("hello", router=router, client_factory=BrokenClient)
    assert router.unhealthy == []


def test_model_and_status_services_are_structured():
    from genspark_cli.mcp import check_status, get_models, list_image_models

    models = get_models()
    images = list_image_models()
    status = check_status(router=FakeRouter(("default", "backup")))

    assert any(model["id"] == "claude-opus-4-6" for model in models["models"])
    assert images["models"]
    assert len(status["profiles"]) == 2


def test_importing_mcp_module_does_not_require_mcp_extra(monkeypatch):
    monkeypatch.setitem(sys.modules, "mcp", None)
    module = importlib.reload(importlib.import_module("genspark_cli.mcp"))
    assert callable(module.run_mcp_server)
    assert callable(module.create_mcp_server)


def test_create_mcp_server_supports_installed_mcp_major():
    pytest.importorskip("mcp")
    from genspark_cli.mcp import create_mcp_server

    server = create_mcp_server()
    assert callable(server.run)


def test_mcp_help_does_not_start_stdio(monkeypatch, capsys):
    import genspark_cli.mcp as mcp_module

    monkeypatch.setattr(sys, "argv", ["genspark-mcp", "--help"])
    monkeypatch.setattr(
        mcp_module,
        "create_mcp_server",
        lambda: pytest.fail("--help must not start the server"),
    )

    mcp_module.run_mcp_server()
    assert "stdio" in capsys.readouterr().out
