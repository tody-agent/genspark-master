import asyncio
import pytest

from genspark_cli.account_router import AccountRouter, STRATEGY_ROUND_ROBIN
from genspark_cli.batch import BatchTask, MultiAccountBatchExecutor
from genspark_cli.exceptions import QuotaExhaustedError, RateLimitError
from genspark_cli.image_parser import ImageGenerationResult
from genspark_cli.parser import ChatResponse
from genspark_cli.profiles import ProfileManager


def _setup_pool(tmp_path, names=("acc1", "acc2", "acc3")):
    pm = ProfileManager(str(tmp_path))
    for idx, name in enumerate(names):
        if idx == 0 and name == "default":
            session = pm.get_session("default")
        else:
            session = pm.add_profile(name)
        session.save_storage_state({"cookies": [{"name": "ai_session", "value": f"c-{name}"}]})
        session.save_recaptcha_token(f"t-{name}")
    if names and "default" not in names:
        pm.default_profile = names[0]
    return pm, AccountRouter(pm, strategy=STRATEGY_ROUND_ROBIN)


@pytest.mark.asyncio
async def test_batch_chat_distributes_across_accounts_and_fails_over(tmp_path):
    _, router = _setup_pool(tmp_path, ("acc1", "acc2", "acc3"))
    used_profiles = []
    acc2_failed_once = False

    class FakeChatClient:
        def __init__(self, session, model="claude-opus-5.5"):
            self.session = session
            self.model = model

        async def chat(self, prompt, model=None, project_id=None, messages=None):
            nonlocal acc2_failed_once
            await asyncio.sleep(0.01)
            prof = self.session.profile_name
            used_profiles.append(prof)
            if prof == "acc2" and not acc2_failed_once:
                acc2_failed_once = True
                raise QuotaExhaustedError("acc2 out of credits")
            return ChatResponse(
                content=f"ans:{prompt}:{prof}",
                model=model or self.model,
                project_id=f"proj-{prof}",
            )

        async def close(self):
            pass

    tasks = [BatchTask(id=f"t{i}", prompt=f"prompt-{i}", model="claude-opus-5.5") for i in range(6)]
    executor = MultiAccountBatchExecutor(
        router=router,
        chat_client_factory=FakeChatClient,
    )
    results = await executor.execute_chat_batch(tasks, concurrency=3)

    assert len(results) == 6
    assert all(r.status == "ok" for r in results)
    assert all(r.model == "claude-opus-5.5" for r in results)
    # Verify multiple accounts participated and acc2 failed over cleanly
    assert len({r.profile for r in results}) >= 2
    assert any(r.attempts >= 2 for r in results)


@pytest.mark.asyncio
async def test_batch_image_generation_with_failover(tmp_path):
    _, router = _setup_pool(tmp_path, ("img1", "img2"))
    img1_failed = False

    class FakeImageClient:
        def __init__(self, session, model="nano-banana-2"):
            self.session = session
            self.model = model

        async def generate(self, prompt, model=None, style="auto", aspect_ratio="auto", image_size="auto", auto_prompt=True):
            nonlocal img1_failed
            await asyncio.sleep(0.01)
            if self.session.profile_name == "img1" and not img1_failed:
                img1_failed = True
                raise RateLimitError("img1 rate limited")
            return ImageGenerationResult(
                urls=[f"https://example.com/{self.session.profile_name}/{prompt}.png"],
                model=model or self.model,
                style=style,
                task_id="task-123",
            )

        async def download_images(self, result, output_dir=None):
            return []

        async def close(self):
            pass

    tasks = [BatchTask(id=f"img-{i}", prompt=f"scene-{i}") for i in range(4)]
    executor = MultiAccountBatchExecutor(
        router=router,
        image_client_factory=FakeImageClient,
    )
    results = await executor.execute_image_batch(tasks, concurrency=2, download=False)

    assert len(results) == 4
    assert all(r.status == "ok" for r in results)
    assert all(len(r.urls) == 1 for r in results)


@pytest.mark.asyncio
async def test_mcp_batch_chat_and_configure_pool(tmp_path):
    from genspark_cli.mcp import batch_chat, configure_pool

    _, router = _setup_pool(tmp_path, ("m1", "m2"))

    class FakeChatClient:
        def __init__(self, session, model="claude-opus-5.5"):
            self.session = session

        async def chat(self, prompt, model=None, project_id=None, messages=None):
            return ChatResponse(content=f"ok:{prompt}", model=model or "claude-opus-5.5")

        async def close(self):
            pass

    batch_out = await batch_chat(
        prompts=["p1", "p2", "p3"],
        model="claude-opus-5.5",
        max_concurrency=2,
        router=router,
        client_factory=FakeChatClient,
    )
    assert batch_out["total"] == 3
    assert batch_out["succeeded"] == 3
    assert len(batch_out["results"]) == 3

    cfg_out = configure_pool(
        strategy="least-used",
        max_concurrency=4,
        reset_cooldowns=True,
        router=router,
    )
    assert cfg_out["strategy"] == "least-used"
    assert cfg_out["max_concurrency_per_account"] == 4
