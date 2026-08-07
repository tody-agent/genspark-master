"""Interactive REPL chat mode with smart session management.

Provides a live terminal chat experience with:
  - Multi-account profile display and switching
  - Conversation tracking with message history
  - Context health monitoring (turn counting)
  - Auto-compact suggestions at 7/12/20 turns
  - Session management (list, new, resume, compact)

Inspired by Claude Code's session management UX.

Usage:
    $ genspark chat
    🚀 Genspark AI Chat (claude-opus-4-6) [default]
    Type /help for commands, /quit to exit

    You: Hello!
    AI: Hello! How can I help you today?

    You: /compact
    🔄 Compacting conversation...

    You: /session list
    📝 Recent sessions...
"""

import asyncio
import sys
from typing import Optional

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from .client import GensparkClient
from .context_manager import ContextAdvice, ContextManager
from .conversations import ConversationStore
from .exceptions import GensparkError, RateLimitError, RecaptchaError, SessionExpiredError
from .log import log
from .models import DEFAULT_MODEL, MODELS, resolve_model
from .profiles import ProfileManager
from .session import SessionManager


console = Console()

HELP_TEXT = """
[bold cyan]Chat Commands:[/]
  [green]/model[/] <name>       Switch AI model (e.g. /model gpt-5.4)
  [green]/models[/]             List available models
  [green]/clear[/]              Clear screen
  [green]/raw[/]                Toggle raw/formatted output
  [green]/help[/]               Show this help
  [green]/quit[/] or [green]/q[/]        Exit chat

[bold cyan]Session Commands:[/]
  [green]/session list[/]       List recent conversations
  [green]/session new[/] [title] Start a new conversation
  [green]/session resume[/] <id> Resume a saved conversation
  [green]/session info[/]       Show current session stats
  [green]/rename[/] <name>      Name the current conversation
  [green]/history[/] [n]        Show last N messages (default 10)

[bold cyan]Context Commands:[/]
  [green]/compact[/] [focus]    Summarize & start fresh (like Claude Code)
  [green]/context[/]            Show turn count, tokens, health

[bold cyan]Account Commands:[/]
  [green]/accounts[/]           Show account pool status
  [green]/status[/]             Show session + account info
"""


async def interactive_chat(
    session: SessionManager,
    model: str = DEFAULT_MODEL,
    profile_manager: Optional[ProfileManager] = None,
    profile_name: Optional[str] = None,
) -> None:
    """Run the interactive REPL chat loop with smart session management."""

    current_model = model
    raw_mode = False
    pm = profile_manager or ProfileManager()
    current_profile = profile_name or session.profile_name

    # Initialize stores
    store = ConversationStore()
    ctx_mgr = ContextManager()

    try:
        model_info = resolve_model(current_model)
    except ValueError:
        model_info = resolve_model(DEFAULT_MODEL)
        current_model = DEFAULT_MODEL

    # Create a new conversation
    conversation = store.create(
        model=model_info.id,
        profile=current_profile,
    )
    current_conv_id = conversation.id

    profile_label = f" [{current_profile}]" if current_profile != "default" else ""
    console.print(Panel(
        f"[bold]🚀 Genspark AI Chat[/] — [cyan]{model_info.display_name}[/]{profile_label}\n"
        f"Type [green]/help[/] for commands, [green]/quit[/] to exit\n"
        f"[dim]Session: {conversation.id[:12]}... | /compact at 7+ turns[/]",
        border_style="blue",
    ))

    # Check cookie health
    health = session.check_cookie_health()
    if health == "missing":
        console.print("[red]⚠ No session found.[/] Run [cyan]genspark auth login[/] first.")
        return
    elif health == "expired":
        console.print("[yellow]⚠ Session may be expired.[/] Run [cyan]genspark auth login[/] to refresh.")
    elif health == "aging":
        console.print("[yellow]ℹ Session is aging.[/] Consider running [cyan]genspark auth login[/] soon.")

    # Show account pool status
    try:
        from .account_router import AccountRouter
        router = AccountRouter(pm)
        if router.pool_size > 1:
            console.print(f"[dim]Account pool: {router.available_count}/{router.pool_size} available[/]")
    except Exception:
        router = None

    async with GensparkClient(session, model=current_model) as client:
        while True:
            try:
                prompt = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: input("\n\033[1;32mYou:\033[0m "),
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

                elif cmd == "/help":
                    console.print(HELP_TEXT)
                    continue

                elif cmd == "/model" and len(cmd_parts) > 1:
                    new_model = cmd_parts[1].strip()
                    try:
                        model_info = resolve_model(new_model)
                        current_model = model_info.id
                        client.model = current_model
                        console.print(f"[green]✓[/] Switched to [cyan]{model_info.display_name}[/]")
                    except ValueError as e:
                        console.print(f"[red]✗[/] {e}")
                    continue

                elif cmd == "/models":
                    for mid, minfo in sorted(MODELS.items()):
                        marker = " ★" if mid == current_model else ""
                        console.print(f"  [green]{mid}[/] — {minfo.display_name}{marker}")
                    continue

                elif cmd == "/status":
                    console.print(f"  Model: [cyan]{model_info.display_name}[/]")
                    console.print(f"  Profile: [cyan]{current_profile}[/]")
                    console.print(f"  Session: {session}")
                    console.print(f"  Cookie health: {session.check_cookie_health()}")
                    conv = store.get(current_conv_id)
                    if conv:
                        console.print(f"  Turns: {conv.user_turn_count}")
                    continue

                elif cmd == "/clear":
                    console.clear()
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
                            for i, entry in enumerate(recent):
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
                        # Start new conversation (optionally with a title)
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
                        # Partial match
                        found = None
                        for entry in store.list_all():
                            if entry.get("id", "").startswith(target_id):
                                found = store.get(entry["id"])
                                break
                        if found:
                            conversation = found
                            current_conv_id = found.id
                            current_model = found.model or current_model
                            client.model = current_model
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
                    console.print("[dim]   Generating summary using AI...[/]")
                    try:
                        new_conv = await ctx_mgr.compact(
                            client, conv, store, instruction=instruction
                        )
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

                elif cmd == "/accounts":
                    if router:
                        statuses = router.get_status()
                        console.print("[bold]🔐 Account Pool:[/]")
                        for s in statuses:
                            health_icons = {
                                "healthy": "🟢",
                                "cooldown": "🟡",
                                "expired": "🔴",
                                "needs_login": "⚪",
                            }
                            icon = health_icons.get(s["health"], "⚪")
                            default = " ★" if s.get("is_default") else ""
                            extra = ""
                            if s.get("cooldown_remaining_s"):
                                extra = f" (cooldown {s['cooldown_remaining_s']}s)"
                            elif s.get("failure_reason"):
                                extra = f" ({s['failure_reason']})"
                            console.print(
                                f"  {icon} [bold]{s['name']}[/]{default} — "
                                f"{s['health']}{extra} "
                                f"[dim]({s['total_requests']} reqs)[/]"
                            )
                    else:
                        console.print("[dim]Single account mode.[/]")
                    continue

                else:
                    console.print(f"[yellow]Unknown command: {cmd}[/]. Type /help for commands.")
                    continue

            # ── Send Chat ──
            try:
                # Get conversation for multi-turn context
                conv = store.get(current_conv_id)
                conversation_messages = None
                project_id = None

                if conv and conv.messages:
                    conversation_messages = conv.get_messages_for_payload()
                    # If we have a project_id from Genspark, continue that thread
                    if session.last_project_id:
                        project_id = session.last_project_id

                # Record user message
                store.add_turn(current_conv_id, "user", prompt)

                console.print(f"[bold cyan]{model_info.display_name}:[/] ", end="")
                content_parts: list[str] = []

                async for chunk in client.chat_stream(
                    prompt,
                    model=current_model,
                    project_id=project_id,
                    messages=conversation_messages if conversation_messages else None,
                ):
                    if chunk.content:
                        if raw_mode:
                            print(chunk.content, end="", flush=True)
                        else:
                            print(chunk.content, end="", flush=True)
                        content_parts.append(chunk.content)

                    # Track project_id from Genspark
                    if chunk.project_id:
                        store.set_project_id(current_conv_id, chunk.project_id)

                print()  # newline after stream

                # Record assistant response
                full_response = "".join(content_parts)
                if full_response:
                    store.add_turn(current_conv_id, "assistant", full_response)

                # Mark account as successful
                if router:
                    router.mark_success(current_profile)

                # ── Context Health Check ──
                conv = store.get(current_conv_id)
                if conv:
                    health = ctx_mgr.check_health(conv)

                    if health.should_auto_compact:
                        # Auto-compact at 20+ turns
                        console.print(f"\n{health.message}")
                        try:
                            new_conv = await ctx_mgr.compact(client, conv, store)
                            current_conv_id = new_conv.id
                            console.print(
                                f"[green]✓[/] Auto-compacted → {new_conv.id[:12]}..."
                            )
                        except Exception as e:
                            console.print(f"[yellow]Auto-compact failed:[/] {e}")

                    elif health.advice != ContextAdvice.CONTINUE:
                        # Show suggestion/warning
                        console.print(f"\n{health.message}")

            except (SessionExpiredError, RecaptchaError) as e:
                console.print(f"\n[red]Error:[/] {e}")
                if router:
                    router.mark_unhealthy(current_profile, reason=type(e).__name__)
                    try:
                        new_session = router.get_session()
                        current_profile = new_session.profile_name
                        console.print(
                            f"[yellow]↻ Switched to account '[cyan]{current_profile}[/]'[/]"
                        )
                        # Recreate client with new session
                        await client.close()
                        client.session = new_session
                        client._http = None
                    except RuntimeError as re:
                        console.print(f"[red]No fallback accounts:[/] {re}")
                else:
                    log.error("REPL auth error: %s", e, exc_info=True)

            except RateLimitError as e:
                console.print(f"\n[yellow]Rate limited:[/] {e}")
                if router:
                    router.mark_unhealthy(current_profile, reason="rate_limit")
                    try:
                        new_session = router.get_session()
                        current_profile = new_session.profile_name
                        console.print(
                            f"[yellow]↻ Switched to account '[cyan]{current_profile}[/]'[/]"
                        )
                        await client.close()
                        client.session = new_session
                        client._http = None
                    except RuntimeError as re:
                        console.print(f"[red]No fallback accounts:[/] {re}")

            except GensparkError as e:
                console.print(f"\n[red]Error:[/] {e}")
                log.error("REPL chat error: %s", e, exc_info=True)
            except Exception as e:
                console.print(f"\n[red]Unexpected error:[/] {e}")
                log.error("REPL unexpected error: %s", e, exc_info=True)


def run_interactive(
    session: SessionManager,
    model: str = DEFAULT_MODEL,
    profile_manager: Optional[ProfileManager] = None,
    profile_name: Optional[str] = None,
) -> None:
    """Synchronous wrapper for the interactive REPL."""
    try:
        asyncio.run(interactive_chat(
            session,
            model=model,
            profile_manager=profile_manager,
            profile_name=profile_name,
        ))
    except KeyboardInterrupt:
        console.print("\n[dim]Goodbye![/]")
