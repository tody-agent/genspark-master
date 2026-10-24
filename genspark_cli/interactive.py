"""Interactive Agentic Studio REPL mode (Claude Code / Hermes CLI style).

Provides a live terminal chat & multi-account studio experience with:
  - Status HUD displaying Active Model (with multiplier), Account Pool health,
    Routing Strategy (round-robin / least-used / failover), and Context turns
  - Readline history (~/.genspark/history) and Tab completion for slash commands
  - Automatic per-turn multi-account routing & transparent failover on errors
  - Built-in /pool, /strategy, /config, /reset, /image, /batch, /compact commands
"""

from __future__ import annotations

import asyncio
from pathlib import Path
import sys
from typing import Optional

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from .account_router import (
    AccountRouter,
    ROUTING_ERRORS,
    VALID_STRATEGIES,
)
from .batch import BatchTask, MultiAccountBatchExecutor
from .client import GensparkClient
from .context_manager import ContextAdvice, ContextManager
from .conversations import ConversationStore
from .exceptions import GensparkError
from .image_client import GensparkImageClient
from .image_models import DEFAULT_IMAGE_MODEL, resolve_image_model
from .log import log
from .models import DEFAULT_MODEL, MODELS, resolve_model
from .profiles import ProfileManager
from .session import SessionManager


console = Console()

SLASH_COMMANDS = [
    "/help",
    "/quit",
    "/q",
    "/exit",
    "/model",
    "/models",
    "/pool",
    "/accounts",
    "/login",
    "/logout",
    "/menu",
    "/strategy",
    "/reset",
    "/config",
    "/image",
    "/batch",
    "/session",
    "/rename",
    "/history",
    "/compact",
    "/context",
    "/status",
    "/clear",
    "/raw",
]

HELP_TEXT = """
[bold cyan]⚡ Studio & Chat Commands:[/]
  [green]/model[/] <name>           Switch AI chat model (e.g. /model gpt-6-sol)
  [green]/models[/]                 List available models & credit multipliers
  [green]/image[/] <prompt>         Generate an image inline using the account pool
  [green]/batch[/] <p1> | <p2> ...  Run multiple prompts concurrently across all accounts
  [green]/clear[/]                  Clear terminal screen
  [green]/raw[/]                    Toggle raw/formatted output
  [green]/help[/]                   Show this command reference
  [green]/quit[/] or [green]/q[/]            Exit studio

[bold cyan]🔐 Multi-Account Pool & Routing:[/]
  [green]/accounts[/]               Quản lý tài khoản: thêm / đăng nhập / đăng xuất / xoá  (/login, /logout)
  [green]/menu[/]                   Thoát khung chat, về menu chính
  [green]/pool[/]                   Show account pool dashboard, health & request stats
  [green]/pool reset[/]             Reset all cooldown / quota-exhausted states
  [green]/strategy[/] <mode>        Set routing strategy: [yellow]round-robin[/] | [yellow]least-used[/] | [yellow]failover[/]
  [green]/reset[/]                  Shortcut for /pool reset
  [green]/config[/] [key] [val]     View or update global CLI configuration

[bold cyan]📝 Session & Context Management:[/]
  [green]/session list[/]           List recent conversations
  [green]/session new[/] [title]    Start a fresh conversation thread
  [green]/session resume[/] <id>    Resume a saved conversation by ID prefix
  [green]/session info[/]           Show current session stats
  [green]/rename[/] <name>          Rename the current conversation
  [green]/history[/] [n]            Show last N messages (default 10)
  [green]/compact[/] [focus]        Summarize & compact context (like Claude Code)
  [green]/context[/]                Show turn count, estimated tokens & context health
  [green]/status[/]                 Show full session + account pool status
"""


def _setup_readline(base_dir: Path) -> None:
    """Configure readline history and slash-command tab completion if available."""
    try:
        import readline
    except ImportError:
        return

    history_file = base_dir / "history"
    try:
        if history_file.exists():
            readline.read_history_file(str(history_file))
        readline.set_history_length(500)
    except OSError:
        pass

    model_ids = sorted(MODELS.keys())

    def completer(text: str, state: int) -> Optional[str]:
        line = readline.get_line_buffer().lstrip()
        options: list[str] = []
        if line.startswith("/model "):
            prefix = line[len("/model "):].strip()
            options = [m for m in model_ids if m.startswith(prefix)]
        elif line.startswith("/strategy "):
            prefix = line[len("/strategy "):].strip()
            options = [s for s in sorted(VALID_STRATEGIES) if s.startswith(prefix)]
        elif line.startswith("/"):
            options = [cmd for cmd in SLASH_COMMANDS if cmd.startswith(line)]
        if state < len(options):
            return options[state]
        return None

    try:
        readline.set_completer(completer)
        if "libedit" in (getattr(readline, "__doc__", "") or ""):
            readline.parse_and_bind("bind ^I rl_complete")
        else:
            readline.parse_and_bind("tab: complete")
    except Exception:
        pass


def _save_readline_history(base_dir: Path) -> None:
    try:
        import readline
        history_file = base_dir / "history"
        readline.write_history_file(str(history_file))
    except Exception:
        pass


def _render_pool_table(router: AccountRouter) -> Table:
    statuses = router.get_status()
    table = Table(
        title=f"🔐 Multi-Account Pool (strategy: {router.strategy})",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("Profile", style="bold")
    table.add_column("Health", justify="center")
    table.add_column("In-Flight", justify="right")
    table.add_column("Requests", justify="right")
    table.add_column("Success/Fail", justify="right")
    table.add_column("Notes", style="dim")

    badges = {
        "healthy": "[green]● healthy[/]",
        "cooldown": "[yellow]◐ cooldown[/]",
        "quota_exhausted": "[red]⊘ quota_exhausted[/]",
        "expired": "[red]✗ expired[/]",
        "needs_login": "[dim]○ needs_login[/]",
    }
    for s in statuses:
        default_mark = " [yellow]★[/]" if s.get("is_default") else ""
        badge = badges.get(s["health"], s["health"])
        notes = []
        if s.get("cooldown_remaining_s"):
            notes.append(f"{s['cooldown_remaining_s']}s left")
        if s.get("failure_reason"):
            notes.append(str(s["failure_reason"])[:50])
        table.add_row(
            f"{s['name']}{default_mark}",
            badge,
            str(s.get("in_flight", 0)),
            str(s.get("total_requests", 0)),
            f"{s.get('success_count', 0)}/{s.get('failure_count', 0)}",
            " · ".join(notes) if notes else "ready",
        )
    return table


def _render_hud_header(
    model_info,
    router: AccountRouter,
    current_profile: str,
    conv_id: str,
    turns: int = 0,
) -> Panel:
    avail = router.available_count
    total = router.pool_size
    pool_color = "green" if avail > 0 else "red"
    mult_str = f"{model_info.multiplier}×"
    return Panel(
        f"[bold cyan]⚡ Genspark Agentic Studio[/]  [dim]│[/]  "
        f"Model: [bold white]{model_info.display_name}[/] [magenta]({mult_str})[/]  [dim]│[/]  "
        f"Pool: [{pool_color}]{avail}/{total} healthy[/] [dim]({router.strategy})[/]  [dim]│[/]  "
        f"Active: [cyan]{current_profile}[/]\n"
        f"[dim]Session {conv_id[:10]} · Turns: {turns} · "
        f"Commands: /pool  /strategy  /model  /image  /batch  /config  /compact  /help  /quit[/]",
        border_style="cyan",
        padding=(0, 1),
    )


async def interactive_chat(
    session: SessionManager,
    model: str = DEFAULT_MODEL,
    profile_manager: Optional[ProfileManager] = None,
    profile_name: Optional[str] = None,
) -> None:
    """Run the interactive Agentic Studio REPL loop with multi-account auto-routing."""
    pm = profile_manager or ProfileManager()
    router = AccountRouter(pm)
    current_model = model or pm.default_model
    raw_mode = False
    preferred_profile = profile_name
    current_profile = profile_name or session.profile_name

    _setup_readline(pm.base_dir)

    store = ConversationStore()
    ctx_mgr = ContextManager()

    try:
        model_info = resolve_model(current_model)
    except ValueError:
        model_info = resolve_model(DEFAULT_MODEL)
        current_model = DEFAULT_MODEL

    conversation = store.create(
        model=model_info.id,
        profile=current_profile,
    )
    current_conv_id = conversation.id

    console.print(_render_hud_header(model_info, router, current_profile, current_conv_id, 0))

    health = session.check_cookie_health()
    if health == "missing" and router.available_count == 0:
        console.print(
            "[red]⚠ No logged-in account found.[/] Run [cyan]gsk auth login[/] or [cyan]gsk pool add <name>[/] first."
        )
        return
    elif health == "expired":
        console.print("[yellow]⚠ Default session cookies may be expired.[/] Pool will auto-route to healthy accounts.")

    try:
        while True:
            avail = router.available_count
            total = router.pool_size
            prompt_prefix = f"\n\033[1;36m[{current_profile} · {avail}/{total}]\033[0m \033[1;32m❯\033[0m "
            try:
                prompt = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: input(prompt_prefix),
                )
            except (EOFError, KeyboardInterrupt):
                console.print("\n[dim]Goodbye![/]")
                break

            prompt = prompt.strip()
            if not prompt:
                continue

            # ── Slash Commands ──
            if prompt.startswith("/"):
                cmd_parts = prompt.split(maxsplit=2)
                cmd = cmd_parts[0].lower()

                if cmd in ("/quit", "/q", "/exit"):
                    console.print("[dim]Goodbye![/]")
                    break

                elif cmd == "/menu":
                    break

                elif cmd in ("/accounts", "/login", "/logout"):
                    from .menu import accounts_menu

                    accounts_menu(profile_manager or ProfileManager())
                    continue

                elif cmd == "/help":
                    console.print(HELP_TEXT)
                    continue

                elif cmd == "/model":
                    if len(cmd_parts) > 1:
                        new_model = cmd_parts[1].strip()
                        try:
                            model_info = resolve_model(new_model)
                            current_model = model_info.id
                            pm.update_config(default_model=current_model)
                            console.print(
                                f"[green]✓[/] Switched to [cyan]{model_info.display_name}[/] "
                                f"[magenta]({model_info.multiplier}×)[/]"
                            )
                        except ValueError as e:
                            console.print(f"[red]✗[/] {e}")
                    else:
                        console.print(
                            f"Current model: [cyan]{model_info.display_name}[/] ({current_model}, {model_info.multiplier}×)\n"
                            f"[dim]Usage: /model <model-id>[/]"
                        )
                    continue

                elif cmd == "/models":
                    table = Table(title="🤖 Available Chat Models", header_style="bold cyan")
                    table.add_column("ID", style="green")
                    table.add_column("Name")
                    table.add_column("Tier", style="yellow")
                    table.add_column("Cost", justify="right", style="magenta")
                    for mid, minfo in sorted(MODELS.items()):
                        marker = " ★" if mid == current_model else (" 🔥" if minfo.is_recommended else "")
                        table.add_row(mid, minfo.display_name + marker, minfo.tier, f"{minfo.multiplier}×")
                    console.print(table)
                    continue

                elif cmd == "/pool":
                    sub = cmd_parts[1].lower().strip() if len(cmd_parts) > 1 else "status"
                    if sub == "reset":
                        count = router.reset_cooldowns()
                        console.print(f"[green]✓[/] Reset cooldown state for {count} account(s).")
                    console.print(_render_pool_table(router))
                    continue

                elif cmd == "/reset":
                    count = router.reset_cooldowns()
                    console.print(f"[green]✓[/] Reset cooldown state for {count} account(s).")
                    continue

                elif cmd == "/strategy":
                    if len(cmd_parts) > 1:
                        new_strat = cmd_parts[1].strip().lower()
                        try:
                            router.strategy = new_strat
                            console.print(f"[green]✓[/] Routing strategy set to [cyan]{router.strategy}[/]")
                        except ValueError as e:
                            console.print(f"[red]✗[/] {e}")
                    else:
                        console.print(
                            f"Current strategy: [cyan]{router.strategy}[/]\n"
                            f"[dim]Options: round-robin | least-used | failover[/]"
                        )
                    continue

                elif cmd == "/config":
                    if len(cmd_parts) == 1:
                        cfg = pm.get_config()
                        table = Table(title="⚙️ Genspark Configuration", header_style="bold cyan")
                        table.add_column("Setting", style="green")
                        table.add_column("Value", style="white")
                        for k, v in cfg.items():
                            table.add_row(k, str(v))
                        console.print(table)
                        console.print("[dim]Update with: /config <strategy|concurrency|model|image_model> <value>[/]")
                    elif len(cmd_parts) >= 3:
                        key = cmd_parts[1].strip().lower()
                        val = cmd_parts[2].strip()
                        key_map = {
                            "strategy": "routing_strategy",
                            "routing_strategy": "routing_strategy",
                            "concurrency": "max_concurrency_per_account",
                            "max_concurrency": "max_concurrency_per_account",
                            "model": "default_model",
                            "default_model": "default_model",
                            "image_model": "default_image_model",
                            "default_image_model": "default_image_model",
                            "cooldown": "default_cooldown_s",
                        }
                        mapped = key_map.get(key)
                        if not mapped:
                            console.print(f"[red]Unknown config key:[/] {key}")
                        else:
                            try:
                                pm.update_config(**{mapped: val})
                                if mapped == "default_model":
                                    model_info = resolve_model(val)
                                    current_model = model_info.id
                                console.print(f"[green]✓[/] Updated [cyan]{mapped}[/] = [bold]{val}[/]")
                            except Exception as e:
                                console.print(f"[red]✗[/] {e}")
                    else:
                        console.print("[yellow]Usage:[/] /config [key] [value]")
                    continue

                elif cmd == "/image":
                    img_prompt = " ".join(cmd_parts[1:]).strip()
                    if not img_prompt:
                        console.print("[yellow]Usage:[/] /image <prompt>")
                        continue
                    img_model = resolve_image_model(pm.default_image_model)
                    console.print(f"[dim]🎨 Generating image with {img_model.display_name} via account pool...[/]")
                    try:
                        async def _gen_op(sess: SessionManager):
                            async with GensparkImageClient(sess, model=img_model.id) as iclient:
                                res = await iclient.generate(img_prompt, model=img_model.id)
                                if res.has_images:
                                    await iclient.download_images(res)
                                return res, sess.profile_name

                        img_res, used_prof = await router.execute_with_failover(_gen_op)
                        current_profile = used_prof
                        console.print(f"[green]✓ Image generated via [{used_prof}]![/]")
                        for u in img_res.urls:
                            console.print(f"  [cyan]URL:[/] {u}")
                        for p in img_res.local_paths:
                            console.print(f"  [green]Saved:[/] {p}")
                    except Exception as e:
                        console.print(f"[red]Image generation failed:[/] {e}")
                    continue

                elif cmd == "/batch":
                    raw_batch = " ".join(cmd_parts[1:]).strip()
                    if not raw_batch:
                        console.print("[yellow]Usage:[/] /batch <prompt 1> | <prompt 2> | <prompt 3>")
                        continue
                    prompts = [p.strip() for p in raw_batch.split("|") if p.strip()]
                    tasks = [BatchTask(id=f"b-{i}", prompt=p, model=current_model) for i, p in enumerate(prompts, 1)]
                    console.print(
                        f"[bold cyan]⚡ Running {len(tasks)} tasks in parallel across {router.available_count} account(s)...[/]"
                    )
                    executor = MultiAccountBatchExecutor(router=router)
                    results = await executor.execute_chat_batch(tasks)
                    for r in results:
                        if r.status == "ok":
                            console.print(Panel(
                                Markdown(r.content),
                                title=f"[green]✓ {r.id}[/] · [cyan]{r.profile}[/] · {r.elapsed_s}s",
                                border_style="green",
                            ))
                        else:
                            console.print(f"[red]✗ {r.id} ({r.profile}):[/] {r.error}")
                    continue

                elif cmd == "/status":
                    conv = store.get(current_conv_id)
                    turns = conv.user_turn_count if conv else 0
                    console.print(_render_hud_header(model_info, router, current_profile, current_conv_id, turns))
                    console.print(_render_pool_table(router))
                    continue

                elif cmd == "/clear":
                    console.clear()
                    conv = store.get(current_conv_id)
                    turns = conv.user_turn_count if conv else 0
                    console.print(_render_hud_header(model_info, router, current_profile, current_conv_id, turns))
                    continue

                elif cmd == "/raw":
                    raw_mode = not raw_mode
                    mode_str = "enabled" if raw_mode else "disabled"
                    console.print(f"[green]✓[/] Raw mode {mode_str}")
                    continue

                # ── Session Commands ──
                elif cmd == "/session":
                    subcmd = cmd_parts[1].lower() if len(cmd_parts) > 1 else "info"

                    if subcmd == "list":
                        recent = store.list_recent(limit=10)
                        if not recent:
                            console.print("[dim]No saved conversations.[/]")
                        else:
                            console.print("[bold]📝 Recent Sessions:[/]")
                            for entry in recent:
                                cid = entry.get("id", "")
                                display = entry.get("display_name", "unnamed")
                                turns = entry.get("turn_count", 0)
                                is_current = "→ " if cid == current_conv_id else "  "
                                summary_icon = "📋" if entry.get("has_summary") else ""
                                console.print(
                                    f"{is_current}[dim]{cid[:10]}[/] "
                                    f"{display[:50]} "
                                    f"[yellow]({turns}t)[/] {summary_icon}"
                                )
                        continue

                    elif subcmd == "new":
                        title = cmd_parts[2].strip() if len(cmd_parts) > 2 else None
                        conversation = store.create(
                            model=current_model,
                            profile=current_profile,
                            name=title,
                        )
                        current_conv_id = conversation.id
                        console.print(
                            f"[green]✓[/] New session started: {conversation.id[:12]}..."
                            f"{f' ({title})' if title else ''}"
                        )
                        continue

                    elif subcmd == "resume" and len(cmd_parts) > 2:
                        target_id = cmd_parts[2].strip()
                        found = None
                        for entry in store.list_all():
                            if entry.get("id", "").startswith(target_id):
                                found = store.get(entry["id"])
                                break
                        if found:
                            conversation = found
                            current_conv_id = found.id
                            current_model = found.model or current_model
                            try:
                                model_info = resolve_model(current_model)
                            except ValueError:
                                pass
                            console.print(
                                f"[green]✓[/] Resumed: {found.display_name}\n"
                                f"    [dim]{found.user_turn_count} turns, model: {current_model}[/]"
                            )
                        else:
                            console.print(f"[red]Session not found:[/] {target_id}")
                        continue

                    elif subcmd == "info":
                        conv = store.get(current_conv_id)
                        if conv:
                            console.print(ctx_mgr.format_context_info(conv))
                        else:
                            console.print("[dim]No active session.[/]")
                        continue

                    else:
                        console.print("[yellow]Usage:[/] /session list|new|resume|info")
                        continue

                elif cmd == "/rename" and len(cmd_parts) > 1:
                    new_name = " ".join(cmd_parts[1:]).strip()
                    conv = store.get(current_conv_id)
                    if conv:
                        conv.name = new_name
                        store.save(conv)
                        console.print(f"[green]✓[/] Session renamed to: {new_name}")
                    continue

                elif cmd == "/history":
                    n = 10
                    if len(cmd_parts) > 1:
                        try:
                            n = int(cmd_parts[1])
                        except ValueError:
                            pass

                    conv = store.get(current_conv_id)
                    if conv and conv.messages:
                        recent = conv.messages[-n:]
                        console.print(f"[bold]Last {len(recent)} messages:[/]")
                        for msg in recent:
                            role_color = "green" if msg.role == "user" else "cyan"
                            preview = msg.content[:300]
                            if len(msg.content) > 300:
                                preview += "..."
                            console.print(f"  [{role_color}]{msg.role}:[/] {preview}\n")
                    else:
                        console.print("[dim]No messages yet.[/]")
                    continue

                elif cmd == "/compact":
                    instruction = " ".join(cmd_parts[1:]).strip() if len(cmd_parts) > 1 else ""
                    conv = store.get(current_conv_id)
                    if not conv or conv.user_turn_count < 2:
                        console.print("[yellow]Not enough conversation to compact.[/]")
                        continue

                    console.print("[bold]🔄 Compacting conversation...[/]")
                    try:
                        active_sess = router.get_session(preferred=preferred_profile)
                        try:
                            async with GensparkClient(active_sess, model=current_model) as client:
                                new_conv = await ctx_mgr.compact(
                                    client, conv, store, instruction=instruction
                                )
                            router.mark_success(active_sess.profile_name)
                        except Exception:
                            router.release_session(active_sess.profile_name)
                            raise
                        current_conv_id = new_conv.id
                        console.print(
                            f"[green]✓[/] Compacted! New session: {new_conv.id[:12]}...\n"
                            f"   [dim]Summary saved. Previous session preserved.[/]"
                        )
                        if new_conv.summary:
                            console.print(f"\n[dim]Summary:[/]\n{new_conv.summary[:500]}")
                    except Exception as e:
                        console.print(f"[red]Compact failed:[/] {e}")
                        log.error("Compact error: %s", e, exc_info=True)
                    continue

                elif cmd == "/context":
                    conv = store.get(current_conv_id)
                    if conv:
                        console.print(ctx_mgr.format_context_info(conv))
                    else:
                        console.print("[dim]No active session.[/]")
                    continue

                else:
                    console.print(f"[yellow]Unknown command: {cmd}[/]. Type /help for commands.")
                    continue

            # ── Send Chat with Multi-Account Routing & Auto-Failover ──
            conv = store.get(current_conv_id)
            conversation_messages = None
            if conv and conv.messages:
                conversation_messages = conv.get_messages_for_payload()

            store.add_turn(current_conv_id, "user", prompt)

            statuses = router.get_status()
            max_attempts = max(1, len(statuses))
            tried_profiles: set[str] = set()
            succeeded = False

            for attempt in range(max_attempts):
                try:
                    turn_session = router.get_session(
                        preferred=preferred_profile if attempt == 0 else None,
                        exclude=tried_profiles if attempt > 0 else None,
                    )
                except RuntimeError as re_err:
                    console.print(f"\n[red]Pool exhausted:[/] {re_err}")
                    break

                turn_profile = turn_session.profile_name
                current_profile = turn_profile
                tried_profiles.add(turn_profile)
                project_id = turn_session.last_project_id if (conv and conv.messages) else None

                try:
                    console.print(
                        f"[bold cyan]{model_info.display_name}[/] [dim]({turn_profile})[/]: ",
                        end="",
                    )
                    content_parts: list[str] = []

                    async with GensparkClient(turn_session, model=current_model) as client:
                        async for chunk in client.chat_stream(
                            prompt,
                            model=current_model,
                            project_id=project_id,
                            messages=conversation_messages if conversation_messages else None,
                        ):
                            if chunk.content:
                                print(chunk.content, end="", flush=True)
                                content_parts.append(chunk.content)
                            if chunk.project_id:
                                store.set_project_id(current_conv_id, chunk.project_id)

                    print()
                    full_response = "".join(content_parts)
                    if full_response:
                        store.add_turn(current_conv_id, "assistant", full_response)

                    router.mark_success(turn_profile)
                    succeeded = True
                    break

                except ROUTING_ERRORS as e:
                    reason = f"{type(e).__name__}: {e}".splitlines()[0][:100]
                    router.mark_unhealthy(turn_profile, reason=reason)
                    console.print(
                        f"\n[yellow]↻ Account '{turn_profile}' hit {type(e).__name__} — failing over to next healthy account...[/]"
                    )
                except GensparkError as e:
                    router.release_session(turn_profile)
                    console.print(f"\n[red]Error:[/] {e}")
                    log.error("REPL chat error: %s", e, exc_info=True)
                    break
                except Exception as e:
                    router.release_session(turn_profile)
                    console.print(f"\n[red]Unexpected error:[/] {e}")
                    log.error("REPL unexpected error: %s", e, exc_info=True)
                    break

            if succeeded:
                conv = store.get(current_conv_id)
                if conv:
                    ctx_health = ctx_mgr.check_health(conv)
                    if ctx_health.should_auto_compact:
                        console.print(f"\n{ctx_health.message}")
                        try:
                            compact_sess = router.get_session(preferred=preferred_profile)
                            try:
                                async with GensparkClient(compact_sess, model=current_model) as client:
                                    new_conv = await ctx_mgr.compact(client, conv, store)
                                router.mark_success(compact_sess.profile_name)
                                current_conv_id = new_conv.id
                                console.print(f"[green]✓[/] Auto-compacted → {new_conv.id[:12]}...")
                            except Exception:
                                router.release_session(compact_sess.profile_name)
                                raise
                        except Exception as e:
                            console.print(f"[yellow]Auto-compact failed:[/] {e}")
                    elif ctx_health.advice != ContextAdvice.CONTINUE:
                        console.print(f"\n{ctx_health.message}")
    finally:
        _save_readline_history(pm.base_dir)


def run_interactive(
    session: SessionManager,
    model: str = DEFAULT_MODEL,
    profile_manager: Optional[ProfileManager] = None,
    profile_name: Optional[str] = None,
) -> None:
    """Synchronous wrapper for the interactive REPL."""
    try:
        asyncio.run(
            interactive_chat(
                session,
                model=model,
                profile_manager=profile_manager,
                profile_name=profile_name,
            )
        )
    except KeyboardInterrupt:
        console.print("\n[dim]Goodbye![/]")
