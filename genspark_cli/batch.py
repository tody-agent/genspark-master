"""Multi-account parallel batch execution engine for Genspark CLI & MCP.

Distributes N chat or image generation tasks concurrently across M accounts
in the pool with per-account concurrency limits and automatic failover.
"""

from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
import time
from typing import Any, Callable, Optional

from .account_router import AccountRouter, ROUTING_ERRORS
from .client import GensparkClient
from .image_client import GensparkImageClient
from .image_models import DEFAULT_IMAGE_MODEL, resolve_image_model
from .models import DEFAULT_MODEL, resolve_model
from .profiles import ProfileManager


@dataclass
class BatchTask:
    """A single unit of work for parallel batch execution."""

    id: str
    prompt: str
    model: Optional[str] = None
    system_prompt: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class BatchResult:
    """Outcome of a single BatchTask execution."""

    id: str
    prompt: str
    status: str = "ok"
    content: str = ""
    urls: list[str] = field(default_factory=list)
    local_paths: list[str] = field(default_factory=list)
    profile: str = ""
    model: str = ""
    project_id: Optional[str] = None
    elapsed_s: float = 0.0
    error: str = ""
    attempts: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_tasks_from_file(
    file_path: Path,
    default_model: Optional[str] = None,
    system_prompt: Optional[str] = None,
) -> list[BatchTask]:
    """Load batch tasks from a .jsonl, .json, or plain text file (one prompt per line)."""
    raw = file_path.read_text(encoding="utf-8", errors="replace").strip()
    if not raw:
        return []

    tasks: list[BatchTask] = []
    suffix = file_path.suffix.lower()

    if suffix == ".json":
        data = json.loads(raw)
        if isinstance(data, list):
            for idx, item in enumerate(data, 1):
                if isinstance(item, str):
                    tasks.append(
                        BatchTask(
                            id=f"task-{idx}",
                            prompt=item,
                            model=default_model,
                            system_prompt=system_prompt,
                        )
                    )
                elif isinstance(item, dict) and item.get("prompt"):
                    tasks.append(
                        BatchTask(
                            id=str(item.get("id") or f"task-{idx}"),
                            prompt=str(item["prompt"]),
                            model=item.get("model") or default_model,
                            system_prompt=item.get("system_prompt") or system_prompt,
                            metadata={k: v for k, v in item.items() if k not in {"id", "prompt", "model", "system_prompt"}},
                        )
                    )
        return tasks

    if suffix == ".jsonl":
        for idx, line in enumerate(raw.splitlines(), 1):
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
                if isinstance(item, dict) and item.get("prompt"):
                    tasks.append(
                        BatchTask(
                            id=str(item.get("id") or f"task-{idx}"),
                            prompt=str(item["prompt"]),
                            model=item.get("model") or default_model,
                            system_prompt=item.get("system_prompt") or system_prompt,
                            metadata={k: v for k, v in item.items() if k not in {"id", "prompt", "model", "system_prompt"}},
                        )
                    )
                    continue
            except json.JSONDecodeError:
                pass
            tasks.append(
                BatchTask(
                    id=f"task-{idx}",
                    prompt=line,
                    model=default_model,
                    system_prompt=system_prompt,
                )
            )
        return tasks

    # Default: plain text (one prompt per non-empty line)
    for idx, line in enumerate(raw.splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        tasks.append(
            BatchTask(
                id=f"task-{idx}",
                prompt=line,
                model=default_model,
                system_prompt=system_prompt,
            )
        )
    return tasks


class MultiAccountBatchExecutor:
    """Executes chat or image tasks concurrently across all accounts in AccountRouter."""

    def __init__(
        self,
        router: Optional[AccountRouter] = None,
        *,
        chat_client_factory: Optional[Callable[..., Any]] = None,
        image_client_factory: Optional[Callable[..., Any]] = None,
    ):
        self.router = router or AccountRouter(ProfileManager())
        self.chat_client_factory = chat_client_factory or GensparkClient
        self.image_client_factory = image_client_factory or GensparkImageClient
        self._account_semaphores: dict[str, asyncio.Semaphore] = {}

    def _get_account_semaphore(self, profile_name: str) -> asyncio.Semaphore:
        if profile_name not in self._account_semaphores:
            limit = max(1, self.router.max_concurrency_per_account)
            self._account_semaphores[profile_name] = asyncio.Semaphore(limit)
        return self._account_semaphores[profile_name]

    def _default_concurrency(self, task_count: int) -> int:
        avail = max(1, self.router.available_count)
        per_acc = max(1, self.router.max_concurrency_per_account)
        return max(1, min(task_count, avail * per_acc))

    async def execute_chat_batch(
        self,
        tasks: list[BatchTask],
        *,
        concurrency: Optional[int] = None,
        on_progress: Optional[Callable[[BatchResult, int, int], None]] = None,
    ) -> list[BatchResult]:
        """Run a batch of chat tasks in parallel across the multi-account pool."""
        if not tasks:
            return []

        max_workers = max(1, concurrency or self._default_concurrency(len(tasks)))
        global_sem = asyncio.Semaphore(max_workers)
        completed_count = 0
        total_count = len(tasks)

        async def _run_one(task: BatchTask) -> BatchResult:
            nonlocal completed_count
            async with global_sem:
                t0 = time.monotonic()
                attempts = 0
                used_profile = ""
                model_name = task.model or getattr(self.router.profiles, "default_model", DEFAULT_MODEL)
                try:
                    resolved_model = resolve_model(model_name).id
                except ValueError:
                    resolved_model = model_name

                full_prompt = (
                    f"[System Instruction]\n{task.system_prompt}\n\n{task.prompt}"
                    if task.system_prompt
                    else task.prompt
                )

                statuses = self.router.get_status()
                max_attempts = max(1, len(statuses))
                tried: set[str] = set()
                last_error: Optional[Exception] = None

                for attempt in range(max_attempts):
                    attempts = attempt + 1
                    try:
                        session = self.router.get_session(
                            exclude=tried if attempt > 0 else None
                        )
                    except RuntimeError as exc:
                        last_error = exc
                        break

                    prof = getattr(session, "profile_name", "default")
                    used_profile = prof
                    tried.add(prof)
                    acc_sem = self._get_account_semaphore(prof)

                    try:
                        async with acc_sem:
                            client = self.chat_client_factory(session)
                            try:
                                response = await client.chat(
                                    full_prompt,
                                    model=resolved_model,
                                )
                            finally:
                                close_fn = getattr(client, "close", None)
                                if close_fn is not None:
                                    await close_fn()

                        self.router.mark_success(prof)
                        res = BatchResult(
                            id=task.id,
                            prompt=task.prompt,
                            status="ok",
                            content=response.content,
                            profile=prof,
                            model=response.model or resolved_model,
                            project_id=getattr(response, "project_id", None),
                            elapsed_s=round(time.monotonic() - t0, 3),
                            attempts=attempts,
                            metadata=task.metadata,
                        )
                        completed_count += 1
                        if on_progress:
                            on_progress(res, completed_count, total_count)
                        return res

                    except ROUTING_ERRORS as exc:
                        last_error = exc
                        reason = f"{type(exc).__name__}: {exc}".splitlines()[0][:120]
                        self.router.mark_unhealthy(prof, reason=reason)
                    except Exception as exc:
                        self.router.release_session(prof)
                        last_error = exc
                        break

                err_res = BatchResult(
                    id=task.id,
                    prompt=task.prompt,
                    status="error",
                    profile=used_profile,
                    model=resolved_model,
                    elapsed_s=round(time.monotonic() - t0, 3),
                    error=str(last_error) if last_error else "All accounts failed",
                    attempts=max(1, attempts),
                    metadata=task.metadata,
                )
                completed_count += 1
                if on_progress:
                    on_progress(err_res, completed_count, total_count)
                return err_res

        return list(await asyncio.gather(*(_run_one(t) for t in tasks)))

    async def execute_image_batch(
        self,
        tasks: list[BatchTask],
        *,
        concurrency: Optional[int] = None,
        style: str = "auto",
        aspect_ratio: str = "auto",
        image_size: str = "auto",
        auto_prompt: bool = True,
        output_dir: Optional[str] = None,
        download: bool = True,
        on_progress: Optional[Callable[[BatchResult, int, int], None]] = None,
    ) -> list[BatchResult]:
        """Run a batch of image generation tasks in parallel across the multi-account pool."""
        if not tasks:
            return []

        max_workers = max(1, concurrency or self._default_concurrency(len(tasks)))
        global_sem = asyncio.Semaphore(max_workers)
        completed_count = 0
        total_count = len(tasks)

        async def _run_one(task: BatchTask) -> BatchResult:
            nonlocal completed_count
            async with global_sem:
                t0 = time.monotonic()
                attempts = 0
                used_profile = ""
                model_name = task.model or getattr(self.router.profiles, "default_image_model", DEFAULT_IMAGE_MODEL)
                try:
                    resolved_model = resolve_image_model(model_name).id
                except ValueError:
                    resolved_model = model_name

                statuses = self.router.get_status()
                max_attempts = max(1, len(statuses))
                tried: set[str] = set()
                last_error: Optional[Exception] = None

                for attempt in range(max_attempts):
                    attempts = attempt + 1
                    try:
                        session = self.router.get_session(
                            exclude=tried if attempt > 0 else None
                        )
                    except RuntimeError as exc:
                        last_error = exc
                        break

                    prof = getattr(session, "profile_name", "default")
                    used_profile = prof
                    tried.add(prof)
                    acc_sem = self._get_account_semaphore(prof)

                    try:
                        async with acc_sem:
                            client = self.image_client_factory(session)
                            try:
                                img_result = await client.generate(
                                    task.prompt,
                                    model=resolved_model,
                                    style=style,
                                    aspect_ratio=aspect_ratio,
                                    image_size=image_size,
                                )
                                if download and getattr(img_result, "urls", None):
                                    dl_fn = getattr(client, "download_images", None)
                                    if dl_fn is not None:
                                        await dl_fn(img_result, output_dir=output_dir)
                            finally:
                                close_fn = getattr(client, "close", None)
                                if close_fn is not None:
                                    await close_fn()

                        self.router.mark_success(prof)
                        res = BatchResult(
                            id=task.id,
                            prompt=task.prompt,
                            status="ok",
                            urls=list(getattr(img_result, "urls", []) or []),
                            local_paths=list(getattr(img_result, "local_paths", []) or []),
                            profile=prof,
                            model=resolved_model,
                            elapsed_s=round(time.monotonic() - t0, 3),
                            attempts=attempts,
                            metadata=task.metadata,
                        )
                        completed_count += 1
                        if on_progress:
                            on_progress(res, completed_count, total_count)
                        return res

                    except ROUTING_ERRORS as exc:
                        last_error = exc
                        reason = f"{type(exc).__name__}: {exc}".splitlines()[0][:120]
                        self.router.mark_unhealthy(prof, reason=reason)
                    except Exception as exc:
                        self.router.release_session(prof)
                        last_error = exc
                        break

                err_res = BatchResult(
                    id=task.id,
                    prompt=task.prompt,
                    status="error",
                    profile=used_profile,
                    model=resolved_model,
                    elapsed_s=round(time.monotonic() - t0, 3),
                    error=str(last_error) if last_error else "All accounts failed",
                    attempts=max(1, attempts),
                    metadata=task.metadata,
                )
                completed_count += 1
                if on_progress:
                    on_progress(err_res, completed_count, total_count)
                return err_res

        return list(await asyncio.gather(*(_run_one(t) for t in tasks)))
