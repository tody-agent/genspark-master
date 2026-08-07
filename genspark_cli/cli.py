"""Click CLI entrypoint for Genspark CLI.

Usage:
    genspark auth login          — Login via browser (one-time, default profile)
    genspark auth add <name>     — Add a new account profile
    genspark auth list           — List all account profiles
    genspark auth switch <name>  — Set default profile
    genspark auth refresh [name] — Re-login to refresh a profile's token
    genspark auth status         — Check session health (all profiles)
    genspark auth logout         — Clear session for a profile
    genspark chat ask "prompt"   — Send a message (fast httpx)
    genspark chat                — Interactive REPL mode
    genspark models list         — List available models
    genspark session list        — List recent conversations
    genspark session info <id>   — Show conversation details
    genspark session delete <id> — Delete a conversation
    genspark server start        — Start OpenAI-compatible proxy
    genspark integrate 9router   — Show 9Router configuration
"""

import json
import os
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown

from . import __version__
from .capabilities import capabilities_document
from .doctor import run_doctor
from .exceptions import GensparkError
from .log import log, set_level
from .models import DEFAULT_MODEL, list_models, resolve_model, MODELS
from .profiles import ProfileManager
from .session import SessionManager


console = Console()


def get_profile_manager() -> ProfileManager:
    """Get or create profile manager."""
    return ProfileManager()


def get_session(profile: str | None = None) -> SessionManager:
    """Get session for a specific or default profile."""
    pm = get_profile_manager()
    return pm.get_session(profile)


# ── Main Group ───────────────────────────────────────────────────────────

@click.group()
@click.version_option(version=__version__, prog_name="genspark")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging (DEBUG)")
@click.option("--quiet", "-q", is_flag=True, help="Suppress all non-error output")
def main(verbose, quiet):
    """🚀 Genspark CLI — Free AI Chat Gateway (Multi-Account)

    Access GPT-5.4, Claude Opus 4.6, Gemini 3.1 Pro, and more
    via Genspark's free AI Chat interface.

    \b
    Quick start:
      1. genspark auth login        # Login via browser (one-time)
      2. genspark auth add work     # Add another account (optional)
      3. genspark chat ask "hello"  # Chat with AI
      4. genspark chat              # Interactive chat mode
      5. genspark session list      # See conversation history
    """
    if verbose:
        set_level("DEBUG")
    elif quiet:
        set_level("ERROR")


@main.command()
@click.option("--json", "as_json", is_flag=True, help="Emit machine-readable JSON")
def capabilities(as_json):
    """List supported local interfaces and their authentication contract."""
    payload = capabilities_document()
    if as_json:
        click.echo(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return

    table = Table(title="Genspark capabilities")
    table.add_column("ID", style="cyan")
    table.add_column("Interface")
    table.add_column("Authentication")
    table.add_column("Command")
    for item in payload["capabilities"]:
        table.add_row(
            item["id"],
            item["interface"],
            item["authentication"],
            item["command"],
        )
    console.print(table)


@main.command()
@click.option("--json", "as_json", is_flag=True, help="Emit machine-readable JSON")
def doctor(as_json):
    """Check installation and browser-login state without network access."""
    try:
        payload = run_doctor()
    except Exception as exc:
        error = {
            "schema_version": 1,
            "status": "error",
            "error": {"type": type(exc).__name__, "message": str(exc)},
        }
        if as_json:
            click.echo(json.dumps(error, ensure_ascii=False, sort_keys=True))
            click.echo(f"Doctor failed: {exc}", err=True)
        else:
            console.print(f"[red]Doctor failed:[/] {exc}")
        raise click.exceptions.Exit(1) from exc

    if as_json:
        click.echo(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return

    color = {"ok": "green", "degraded": "yellow", "error": "red"}[payload["status"]]
    console.print(f"Doctor status: [{color}]{payload['status']}[/]")
    for name, check in payload["checks"].items():
        console.print(f"  {name}: {check['status']}")


# ── Auth Commands ────────────────────────────────────────────────────────

@main.group()
def auth():
    """🔐 Authentication & account management."""
    pass


@auth.command()
@click.option("--profile", "-p", default=None, help="Profile name to login (default profile if omitted)")
def login(profile):
    """Open browser to login to Genspark.

    Saves session cookies locally. All future chat uses fast HTTP.
    """
    from .auth import run_login

    pm = get_profile_manager()
    profile_name = profile or pm.default_profile

    try:
        session = pm.get_session(profile_name)
    except ValueError:
        # Profile doesn't exist, create it
        session = pm.add_profile(profile_name)

    if session.is_logged_in:
        health = session.check_cookie_health()
        if health == "fresh":
            if not click.confirm(
                f"Profile '{profile_name}' is already logged in (cookies fresh). Re-login?",
                default=False,
            ):
                console.print(f"[green]✓[/] Already logged in as [cyan]{profile_name}[/].")
                return
        else:
            console.print(f"[yellow]Profile '{profile_name}' cookie status: {health}[/] — refreshing...")

    console.print(Panel(
        f"[bold]🌐 Opening browser for login...[/]\n"
        f"Profile: [cyan]{profile_name}[/]\n\n"
        "1. Log in with your Google/email account\n"
        "2. Wait for the chat page to load\n"
        "3. Send ANY message in the chat\n"
        "4. Come back here and press Enter",
        title="Login",
        border_style="blue",
    ))

    try:
        success = run_login(session)
        if success:
            console.print(f"\n[bold green]✅ Session saved![/] Profile: [cyan]{profile_name}[/]")
            console.print("[dim]   All chat is via fast HTTP — no browser needed.[/]")
        else:
            console.print("\n[yellow]⚠️ Login may not have completed. Try again.[/]")
    except GensparkError as e:
        console.print(f"\n[red]Login failed:[/] {e}")
        sys.exit(1)


@auth.command()
@click.argument("name")
def add(name):
    """Add a new account profile and login.

    Creates a new named profile and opens browser for login.

    \b
    Examples:
      genspark auth add work
      genspark auth add backup-account
    """
    from .auth import run_login

    pm = get_profile_manager()

    try:
        session = pm.add_profile(name)
    except ValueError as e:
        console.print(f"[red]Error:[/] {e}")
        sys.exit(1)

    console.print(f"[green]✓[/] Created profile [cyan]{name}[/]")
    console.print(Panel(
        f"[bold]🌐 Opening browser to login profile '{name}'...[/]\n\n"
        "1. Log in with a DIFFERENT Google/email account\n"
        "2. Wait for the chat page to load\n"
        "3. Send ANY message in the chat\n"
        "4. Come back here and press Enter",
        title=f"Login — {name}",
        border_style="blue",
    ))

    try:
        success = run_login(session)
        if success:
            console.print(f"\n[bold green]✅ Profile '{name}' ready![/]")
            console.print(f"[dim]   Switch to it: genspark auth switch {name}[/]")
        else:
            console.print("\n[yellow]⚠️ Login may not have completed. Try again.[/]")
    except GensparkError as e:
        console.print(f"\n[red]Login failed:[/] {e}")
        sys.exit(1)


@auth.command(name="list")
def auth_list():
    """List all account profiles with health status."""
    pm = get_profile_manager()
    profiles = pm.list_profiles()

    if not profiles:
        console.print("[yellow]No profiles found.[/] Run [cyan]genspark auth login[/] to create one.")
        return

    table = Table(
        title="🔐 Account Profiles",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("Name", style="green")
    table.add_column("Default", style="yellow", justify="center")
    table.add_column("Logged In", justify="center")
    table.add_column("Cookie Health", justify="center")
    table.add_column("Age")

    for p in profiles:
        default_marker = "★" if p["is_default"] else ""
        logged_in = "[green]✓[/]" if p["is_logged_in"] else "[red]✗[/]"

        health = p["cookie_health"]
        health_colors = {"fresh": "green", "aging": "yellow", "expired": "red", "missing": "red"}
        color = health_colors.get(health, "white")
        health_str = f"[{color}]{health}[/]"

        age_str = ""
        if p["cookie_age"] is not None:
            days = int(p["cookie_age"] / 86400)
            if days > 0:
                age_str = f"{days}d"
            else:
                hours = int(p["cookie_age"] / 3600)
                age_str = f"{hours}h"

        table.add_row(p["name"], default_marker, logged_in, health_str, age_str)

    console.print(table)
    console.print(f"\n[dim]★ = default profile. Switch with: genspark auth switch <name>[/]")


@auth.command()
@click.argument("name")
def switch(name):
    """Set the default account profile.

    \b
    Example:
      genspark auth switch work
    """
    pm = get_profile_manager()
    try:
        pm.default_profile = name
        console.print(f"[green]✓[/] Default profile set to [cyan]{name}[/]")
    except ValueError as e:
        console.print(f"[red]Error:[/] {e}")
        sys.exit(1)


@auth.command()
@click.argument("name", required=False)
def refresh(name):
    """Re-login to refresh tokens for a profile.

    Without arguments, refreshes the default profile.
    """
    from .auth import run_login

    pm = get_profile_manager()
    profile_name = name or pm.default_profile

    try:
        session = pm.get_session(profile_name)
    except ValueError as e:
        console.print(f"[red]Error:[/] {e}")
        sys.exit(1)

    console.print(f"[bold]Refreshing profile [cyan]{profile_name}[/]...[/]")
    console.print(Panel(
        "🌐 Opening browser for re-login...\n\n"
        "1. Log in (if needed)\n"
        "2. Send ANY message in the chat\n"
        "3. Press Enter here when done",
        title=f"Refresh — {profile_name}",
        border_style="yellow",
    ))

    try:
        success = run_login(session)
        if success:
            console.print(f"\n[bold green]✅ Profile '{profile_name}' refreshed![/]")
        else:
            console.print("\n[yellow]⚠️ Refresh may not have completed.[/]")
    except GensparkError as e:
        console.print(f"\n[red]Refresh failed:[/] {e}")
        sys.exit(1)


@auth.command()
def status():
    """Check login status and cookie health for all profiles."""
    pm = get_profile_manager()
    profiles = pm.list_profiles()

    if not profiles:
        console.print("[yellow]No profiles.[/] Run [cyan]genspark auth login[/]")
        return

    for p in profiles:
        name = p["name"]
        is_default = p["is_default"]
        marker = " [yellow]★ default[/]" if is_default else ""

        if p["is_logged_in"]:
            health = p["cookie_health"]
            health_colors = {"fresh": "green", "aging": "yellow", "expired": "red"}
            color = health_colors.get(health, "white")

            age_str = ""
            if p["cookie_age"] is not None:
                days = int(p["cookie_age"] / 86400)
                age_str = f" ({days}d old)" if days > 0 else " (fresh)"

            console.print(f"[green]✓[/] [bold]{name}[/]{marker}")
            console.print(f"    Cookie health: [{color}]{health}{age_str}[/]")

            session = pm.get_session(name)
            cookies = session.get_cookies_dict()
            console.print(f"    Cookies: {len(cookies)}")

            token = session.get_recaptcha_token()
            if token:
                token_age = session.get_recaptcha_token_age()
                if token_age is not None:
                    hours = int(token_age / 3600)
                    age_label = f"{hours}h old" if hours > 0 else f"{int(token_age / 60)}m old"
                else:
                    age_label = "age unknown"
                console.print(f"    reCAPTCHA: [green]✓[/] ({age_label})")
            else:
                console.print(f"    reCAPTCHA: [red]✗ missing[/]")
        else:
            console.print(f"[red]✗[/] [bold]{name}[/]{marker} — not logged in")

        console.print()


@auth.command()
@click.argument("name", required=False)
@click.option("--force", "-f", is_flag=True, help="Skip confirmation")
def logout(name, force):
    """Clear saved session for a profile.

    Without arguments, clears the default profile.
    """
    pm = get_profile_manager()
    profile_name = name or pm.default_profile

    try:
        session = pm.get_session(profile_name)
    except ValueError as e:
        console.print(f"[red]Error:[/] {e}")
        sys.exit(1)

    if not force:
        if not click.confirm(f"Clear session for profile '{profile_name}'?", default=False):
            console.print("[dim]Cancelled.[/]")
            return

    session.clear()
    console.print(f"[green]✓[/] Session cleared for [cyan]{profile_name}[/].")


@auth.command()
@click.argument("name")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation")
def remove(name, force):
    """Delete an account profile completely."""
    pm = get_profile_manager()

    if not force:
        if not click.confirm(f"Delete profile '{name}' and all its data?", default=False):
            console.print("[dim]Cancelled.[/]")
            return

    try:
        pm.remove_profile(name)
        console.print(f"[green]✓[/] Profile [cyan]{name}[/] deleted.")
    except ValueError as e:
        console.print(f"[red]Error:[/] {e}")
        sys.exit(1)


# ── Chat Commands ────────────────────────────────────────────────────────

@main.group(invoke_without_command=True)
@click.option("--profile", "-p", default=None, help="Account profile to use")
@click.pass_context
def chat(ctx, profile):
    """💬 Chat with AI models.

    \b
    Run without a subcommand for interactive mode:
      genspark chat
      genspark chat -p work    # use 'work' profile

    \b
    Or use 'ask' for a single query:
      genspark chat ask "What is AI?"
    """
    ctx.ensure_object(dict)
    ctx.obj["profile"] = profile

    if ctx.invoked_subcommand is None:
        # Interactive mode
        from .interactive import run_interactive
        pm = get_profile_manager()

        try:
            from .account_router import AccountRouter
            router = AccountRouter(pm)
            session = router.get_session(preferred=profile)
            profile_name = session.profile_name
        except RuntimeError as e:
            console.print(f"[red]Error:[/] {e}")
            sys.exit(1)

        run_interactive(
            session,
            model=DEFAULT_MODEL,
            profile_manager=pm,
            profile_name=profile_name,
        )


@chat.command()
@click.argument("prompt")
@click.option("--model", "-m", default=DEFAULT_MODEL,
              help=f"Model to use (default: {DEFAULT_MODEL})")
@click.option("--stream", "-s", is_flag=True, default=False,
              help="Stream response in real-time")
@click.option("--json-output", "--json", "json_out", is_flag=True, default=False,
              help="Output as JSON (OpenAI-compatible format)")
@click.option("--raw", is_flag=True, default=False,
              help="Output raw text without formatting")
@click.option("--profile", "-p", default=None, help="Account profile to use")
@click.pass_context
def ask(ctx, prompt, model, stream, json_out, raw, profile):
    """Send a message to the AI and get a response.

    Uses fast HTTP (no browser). Requires prior login via 'genspark auth login'.

    \b
    Examples:
      genspark chat ask "What is quantum computing?"
      genspark chat ask "Write a Python function" --model gpt-5.4
      genspark chat ask "Explain AI" --stream -p work
      genspark chat ask "Hello" --json
    """
    from .client import run_chat

    # Use profile from parent group or this option
    profile = profile or (ctx.parent.obj or {}).get("profile")

    pm = get_profile_manager()
    try:
        from .account_router import AccountRouter
        router = AccountRouter(pm)
        session = router.get_session(preferred=profile)
    except RuntimeError as e:
        console.print(f"[red]Error:[/] {e}")
        sys.exit(1)

    # Resolve model name
    try:
        model_info = resolve_model(model)
    except ValueError as e:
        console.print(f"[red]Error:[/] {e}")
        sys.exit(1)

    if not json_out and not raw:
        profile_label = f" [dim]({session.profile_name})[/]" if session.profile_name != "default" else ""
        console.print(f"[dim]Using model: {model_info.display_name}{profile_label}[/]")
        # Show cookie health warning
        health = session.check_cookie_health()
        if health == "missing":
            console.print("[red]⚠ No session found.[/] Run [cyan]genspark auth login[/] first.")
            sys.exit(1)
        elif health == "expired":
            console.print("[yellow]⚠ Cookies may be expired.[/] Run [cyan]genspark auth login[/] to refresh.")
        console.print()

    try:
        result = run_chat(
            session=session,
            prompt=prompt,
            model=model_info.id,
            stream=stream,
        )

        if json_out:
            output = result.to_openai_format()
            click.echo(json.dumps(output, indent=2, ensure_ascii=False))
        elif raw:
            click.echo(result.content)
        else:
            if not stream:  # Stream already printed chunks
                if result.content:
                    console.print(Panel(
                        Markdown(result.content),
                        title=f"[bold]{model_info.display_name}[/]",
                        border_style="green",
                        padding=(1, 2),
                    ))
                else:
                    console.print("[yellow]No response received.[/]")
                    console.print("[dim]Try: genspark auth login  (to refresh session)[/]")

    except GensparkError as e:
        console.print(f"[red]Error:[/] {e}")
        log.error("Chat error: %s", e, exc_info=True)
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error:[/] {e}")
        log.error("Unexpected chat error: %s", e, exc_info=True)
        if not json_out:
            console.print("[dim]Check logs: ~/.genspark/genspark.log[/]")
        sys.exit(1)


# ── Session Commands ─────────────────────────────────────────────────────

@main.group()
def session():
    """📝 Manage conversation sessions."""
    pass


@session.command(name="list")
@click.option("--limit", "-n", default=10, help="Number of conversations to show")
def session_list(limit):
    """List recent conversations.

    \b
    Examples:
      genspark session list
      genspark session list -n 20
    """
    from .conversations import ConversationStore

    store = ConversationStore()
    conversations = store.list_recent(limit=limit)

    if not conversations:
        console.print("[dim]No conversations yet.[/] Start chatting with [cyan]genspark chat[/]")
        return

    table = Table(
        title="📝 Recent Conversations",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("ID", style="dim", max_width=12)
    table.add_column("Name", style="white", max_width=50)
    table.add_column("Model", style="blue")
    table.add_column("Turns", justify="right", style="yellow")
    table.add_column("Profile", style="green")
    table.add_column("Last Active", style="dim")

    import time as _time
    now = _time.time()

    for c in conversations:
        cid = c.get("id", "")[:12]
        display = c.get("display_name", c.get("name", "unnamed"))
        if len(display) > 50:
            display = display[:47] + "..."
        model_name = c.get("model", "")
        turns = str(c.get("turn_count", 0))
        profile_name = c.get("profile", "default")

        last_active = c.get("last_active", 0)
        if last_active:
            age = now - last_active
            if age < 3600:
                age_str = f"{int(age / 60)}m ago"
            elif age < 86400:
                age_str = f"{int(age / 3600)}h ago"
            else:
                age_str = f"{int(age / 86400)}d ago"
        else:
            age_str = ""

        has_summary = "📋" if c.get("has_summary") else ""
        table.add_row(cid, f"{display} {has_summary}", model_name, turns, profile_name, age_str)

    console.print(table)
    console.print(f"\n[dim]Total: {store.count} conversations. 📋 = has summary[/]")


@session.command()
@click.argument("conv_id")
def info(conv_id):
    """Show details about a conversation."""
    from .conversations import ConversationStore
    from .context_manager import ContextManager

    store = ConversationStore()

    # Support partial ID matching
    conv = store.get(conv_id)
    if not conv:
        # Try partial match from index
        for entry in store.list_all():
            if entry.get("id", "").startswith(conv_id):
                conv = store.get(entry["id"])
                break

    if not conv:
        console.print(f"[red]Conversation not found:[/] {conv_id}")
        sys.exit(1)

    ctx_mgr = ContextManager()
    console.print(Panel(
        ctx_mgr.format_context_info(conv),
        title=f"Session: {conv.display_name}",
        border_style="blue",
    ))

    # Show last few messages
    recent = conv.messages[-6:] if len(conv.messages) > 6 else conv.messages
    if recent:
        console.print("\n[bold]Recent messages:[/]")
        for msg in recent:
            role_color = "green" if msg.role == "user" else "cyan"
            preview = msg.content[:200]
            if len(msg.content) > 200:
                preview += "..."
            console.print(f"  [{role_color}]{msg.role}:[/] {preview}")


@session.command()
@click.argument("conv_id")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation")
def delete(conv_id, force):
    """Delete a conversation."""
    from .conversations import ConversationStore

    store = ConversationStore()

    if not force:
        if not click.confirm(f"Delete conversation {conv_id}?", default=False):
            console.print("[dim]Cancelled.[/]")
            return

    # Support partial ID matching
    full_id = conv_id
    for entry in store.list_all():
        if entry.get("id", "").startswith(conv_id):
            full_id = entry["id"]
            break

    if store.delete(full_id):
        console.print(f"[green]✓[/] Conversation deleted.")
    else:
        console.print(f"[red]Conversation not found:[/] {conv_id}")


# ── Models Commands ──────────────────────────────────────────────────────

@main.group()
def models():
    """📋 List and inspect available models."""
    pass


@models.command(name="list")
@click.option("--tier", type=click.Choice(["premium", "fast", "special"]),
              help="Filter by model tier")
@click.option("--provider", type=click.Choice(["openai", "anthropic", "google", "xai"]),
              help="Filter by provider")
@click.option("--json-output", "--json", "json_out", is_flag=True,
              help="Output as JSON")
def list_cmd(tier, provider, json_out):
    """List all available AI models.

    \b
    Examples:
      genspark models list
      genspark models list --tier premium
      genspark models list --provider anthropic --json
    """
    models_list = list_models(tier=tier, provider=provider)

    if json_out:
        output = [
            {
                "id": m.id,
                "name": m.display_name,
                "provider": m.provider,
                "tier": m.tier,
            }
            for m in models_list
        ]
        click.echo(json.dumps(output, indent=2))
        return

    table = Table(
        title="🤖 Available Genspark AI Models",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("ID", style="green")
    table.add_column("Name", style="white")
    table.add_column("Provider", style="blue")
    table.add_column("Tier", style="yellow")

    default_id = DEFAULT_MODEL
    for m in models_list:
        marker = " ★" if m.id == default_id else ""
        table.add_row(m.id, m.display_name + marker, m.provider, m.tier)

    console.print(table)
    console.print(f"\n[dim]★ = default model. Override with --model <id>[/]")
    console.print(f"[dim]Total: {len(models_list)} models available FREE[/]")


# ── Server Command ───────────────────────────────────────────────────────

@main.group()
def server():
    """🖥️ OpenAI-compatible API proxy server."""
    pass


@server.command()
@click.option("--port", "-p", default=8080, help="Port to listen on")
@click.option("--host", default="127.0.0.1", help="Host to bind to")
@click.option("--model", "-m", default=DEFAULT_MODEL, help="Default model")
def start(port, host, model):
    """Start the OpenAI-compatible proxy server.

    Exposes Genspark AI Chat as an OpenAI-compatible REST API
    at http://localhost:8080/v1/chat/completions

    Uses fast HTTP with multi-account failover.

    \b
    Use with any OpenAI-compatible client:
      export OPENAI_API_BASE=http://localhost:8080/v1
      export OPENAI_API_KEY=dummy
    """
    pm = get_profile_manager()
    healthy = pm.get_healthy_profiles()

    console.print(Panel(
        f"[bold]🖥️ Starting OpenAI-compatible proxy server[/]\n\n"
        f"  Endpoint: [cyan]http://{host}:{port}/v1/chat/completions[/]\n"
        f"  Default model: [green]{model}[/]\n"
        f"  Backend: [green]httpx (multi-account failover)[/]\n"
        f"  Accounts: [green]{len(healthy)}[/] healthy profiles\n\n"
        f"  [dim]Set OPENAI_API_BASE=http://{host}:{port}/v1 in your client[/]",
        title="Server",
        border_style="blue",
    ))

    from .server import run_server
    run_server(host=host, port=port, default_model=model)


# ── MCP Commands ─────────────────────────────────────────────────────────

@main.group()
def mcp():
    """🤖 MCP Server for AI agent integration."""
    pass


@mcp.command()
def info():
    """Show MCP configuration for various AI agents.

    Displays ready-to-use config for Claude Code, Gemini CLI,
    Cursor, OpenClaw, and other MCP-compatible agents.
    """
    import shutil

    # Find genspark-mcp binary
    mcp_bin = shutil.which("genspark-mcp")
    mcp_cmd = mcp_bin or "genspark-mcp"

    console.print(Panel(
        "[bold cyan]MCP Server Configuration[/]\n\n"
        "[bold]Claude Code:[/]\n"
        f"  [green]claude mcp add genspark -- {mcp_cmd}[/]\n\n"
        "[bold]Gemini CLI:[/]\n"
        f"  [green]gemini mcp add genspark {mcp_cmd}[/]\n\n"
        "[bold]Cursor / OpenClaw / Cline (JSON config):[/]\n"
        f'  [green]{{"mcpServers": {{"genspark": {{"command": "{mcp_cmd}"}}}}}}[/]\n\n'
        "[bold]Available MCP Tools:[/]\n"
        "  • [cyan]chat[/]             — Send message to any AI model\n"
        "  • [cyan]chat_with_context[/] — Chat with a system prompt\n"
        "  • [cyan]generate_image[/]   — Generate images with 7 free models\n"
        "  • [cyan]get_models[/]       — List 14+ free AI models\n"
        "  • [cyan]list_image_models[/] — List 7 free image models\n"
        "  • [cyan]check_status[/]     — Check session health",
        title="MCP Server",
        border_style="blue",
    ))


# ── Image Commands ───────────────────────────────────────────────────────

@main.group()
def image():
    """🎨 AI Image generation (FREE).

    Generate images using 7 free AI models including Flux 2, Nano Banana,
    GPT Image, and more. Supports 170+ art styles and 14 aspect ratios.

    \b
    Quick start:
      genspark image generate "a cyberpunk city at night"
      genspark image generate "portrait" --style "Oil Painting" --ratio 3:4
      genspark image models
      genspark image styles --search "cyber"
    """
    pass


@image.command()
@click.argument("prompt")
@click.option("--model", "-m", default=None,
              help="Image model to use (default: nano-banana-2)")
@click.option("--style", "-s", default="auto",
              help="Art style (e.g., 'Cyberpunk', 'Oil Painting', 'Anime 3D Game Look')")
@click.option("--ratio", "-r", default="auto",
              help="Aspect ratio (e.g., 16:9, 1:1, 3:4, 9:16)")
@click.option("--size", default="auto",
              help="Image size (auto, 0.5K, 1K, 2K, 4K)")
@click.option("--output", "-o", default=None,
              help="Output directory (default: current directory)")
@click.option("--no-download", is_flag=True, default=False,
              help="Don't download — just print URL")
@click.option("--no-enhance", is_flag=True, default=False,
              help="Don't auto-enhance the prompt")
@click.option("--profile", "-p", default=None, help="Account profile to use")
@click.option("--json-output", "--json", "json_out", is_flag=True, default=False,
              help="Output as JSON")
def generate(prompt, model, style, ratio, size, output, no_download, no_enhance, profile, json_out):
    """Generate an image from a text prompt.

    Uses the same authentication as chat — requires prior login.

    \b
    Examples:
      genspark image generate "a cat wearing a spacesuit"
      genspark image generate "sunset over ocean" --model flux-2-pro --size 4K
      genspark image generate "portrait" --style "Oil Painting" --ratio 3:4
      genspark image generate "logo" --no-download --json
    """
    from .image_client import run_image_generate
    from .image_models import DEFAULT_IMAGE_MODEL, resolve_image_model

    pm = get_profile_manager()
    try:
        from .account_router import AccountRouter
        router = AccountRouter(pm)
        session = router.get_session(preferred=profile)
    except RuntimeError as e:
        console.print(f"[red]Error:[/] {e}")
        sys.exit(1)

    # Resolve model
    model_id = model or DEFAULT_IMAGE_MODEL
    try:
        model_info = resolve_image_model(model_id)
    except ValueError as e:
        console.print(f"[red]Error:[/] {e}")
        sys.exit(1)

    if not json_out:
        profile_label = f" [dim]({session.profile_name})[/]" if session.profile_name != "default" else ""
        console.print(f"[dim]Model: {model_info.display_name}{profile_label}[/]")
        if style != "auto":
            console.print(f"[dim]Style: {style}[/]")
        if ratio != "auto":
            console.print(f"[dim]Ratio: {ratio}[/]")
        if size != "auto":
            console.print(f"[dim]Size:  {size}[/]")
        console.print()

        with console.status("[bold blue]🎨 Generating image...[/]", spinner="dots"):
            try:
                result = run_image_generate(
                    session=session,
                    prompt=prompt,
                    model=model_info.id,
                    style=style,
                    aspect_ratio=ratio,
                    image_size=size,
                    auto_prompt=not no_enhance,
                    output_dir=output,
                    download=not no_download,
                )
            except GensparkError as e:
                console.print(f"\n[red]Error:[/] {e}")
                sys.exit(1)
            except Exception as e:
                console.print(f"\n[red]Unexpected error:[/] {e}")
                sys.exit(1)

        # Display results
        if result.urls:
            console.print(f"[bold green]✅ Image generated![/]\n")
            for i, url in enumerate(result.urls):
                console.print(f"  [cyan]URL {i + 1}:[/] {url}")
            if result.local_paths:
                console.print()
                for path in result.local_paths:
                    console.print(f"  [green]📁 Saved:[/] {path}")
            if result.refined_prompt:
                console.print(f"\n  [dim]Enhanced prompt: {result.refined_prompt}[/]")
        else:
            console.print("[yellow]⚠️ No images generated.[/]")
    else:
        # JSON output mode
        try:
            result = run_image_generate(
                session=session,
                prompt=prompt,
                model=model_info.id,
                style=style,
                aspect_ratio=ratio,
                image_size=size,
                auto_prompt=not no_enhance,
                output_dir=output,
                download=not no_download,
            )
        except GensparkError as e:
            click.echo(json.dumps({"error": str(e)}, indent=2))
            sys.exit(1)

        output_data = {
            "urls": result.urls,
            "local_paths": result.local_paths,
            "model": result.model,
            "style": result.style,
            "refined_prompt": result.refined_prompt,
            "task_id": result.task_id,
        }
        click.echo(json.dumps(output_data, indent=2, ensure_ascii=False))


@image.command(name="models")
@click.option("--json-output", "--json", "json_out", is_flag=True,
              help="Output as JSON")
def image_models_cmd(json_out):
    """List available image generation models.

    \b
    Examples:
      genspark image models
      genspark image models --json
    """
    from .image_models import list_image_models, DEFAULT_IMAGE_MODEL

    models_list = list_image_models()

    if json_out:
        output = [
            {
                "id": m.id,
                "name": m.display_name,
                "provider": m.provider,
                "max_resolution": m.max_resolution,
                "description": m.description,
            }
            for m in models_list
        ]
        click.echo(json.dumps(output, indent=2))
        return

    table = Table(
        title="🎨 Available Image Generation Models",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("ID", style="green")
    table.add_column("Name", style="white")
    table.add_column("Provider", style="blue")
    table.add_column("Max Res", style="yellow", justify="center")
    table.add_column("Description", style="dim", max_width=50)

    for m in models_list:
        marker = " ★" if m.id == DEFAULT_IMAGE_MODEL else ""
        table.add_row(m.id, m.display_name + marker, m.provider, m.max_resolution, m.description)

    console.print(table)
    console.print(f"\n[dim]★ = default model. Override with --model <id>[/]")
    console.print(f"[dim]Total: {len(models_list)} image models available FREE[/]")


@image.command(name="styles")
@click.option("--search", "-s", default=None, help="Search for styles containing this text")
@click.option("--category", "-c", default=None, help="Filter by category name")
@click.option("--json-output", "--json", "json_out", is_flag=True,
              help="Output as JSON")
def image_styles_cmd(search, category, json_out):
    """List available art styles for image generation.

    Styles are organized by category: Cinema, Photography, Fine Art,
    Digital, 3D & Game Art, and more.

    \b
    Examples:
      genspark image styles
      genspark image styles --search "cyber"
      genspark image styles --category "Cinema"
      genspark image styles --json
    """
    from .image_models import list_styles, ALL_STYLES

    result = list_styles(search=search, category=category)

    if json_out:
        click.echo(json.dumps(result, indent=2, ensure_ascii=False))
        return

    if not result:
        if search:
            console.print(f"[yellow]No styles matching '{search}'[/]")
        elif category:
            console.print(f"[yellow]No category matching '{category}'[/]")
        return

    total = 0
    for cat_name, styles in result.items():
        console.print(f"\n[bold]{cat_name}[/]")
        # Display in columns
        row = []
        for s in styles:
            row.append(s)
            if len(row) == 3:
                console.print(f"  [green]{row[0]:<30}[/] [green]{row[1]:<30}[/] [green]{row[2]}[/]")
                row = []
        if row:
            formatted = "  " + "".join(f"[green]{s:<30}[/]" for s in row)
            console.print(formatted)
        total += len(styles)

    console.print(f"\n[dim]Total: {total} styles shown (of {len(ALL_STYLES)} total)[/]")
    if not search and not category:
        console.print("[dim]Tip: Use --search <term> to filter, e.g., genspark image styles -s cyber[/]")


# ── Integrations Commands ────────────────────────────────────────────────

@main.group()
def integrate():
    """🔗 Generate configs for 3rd party integrations."""
    pass

@integrate.command(name="9router")
def integrate_9router():
    """Print configuration for 9Router integration."""
    console.print(Panel(
        "[bold cyan]9Router Integration Guide[/]\n\n"
        "To set up Genspark CLI as a Free Tier fallback provider in 9Router,\n"
        "enter the following details in your 9Router dashboard:\n\n"
        "  [bold]Provider ID:[/]    [green]genspark-free[/]\n"
        "  [bold]Name:[/]           [green]Genspark CLI[/]\n"
        "  [bold]Base URL:[/]       [green]http://localhost:8080/v1[/]\n"
        "  [bold]API Key:[/]        [green]sk-dummy-token[/]\n\n"
        "[dim]Note: Make sure `genspark server start --port 8080` is running in another terminal![/]",
        title="9Router",
        border_style="green"
    ))

@integrate.command(name="openclaw")
@click.option("--port", "-p", default=8080, help="Genspark proxy port")
@click.option("--host", default="127.0.0.1", help="Genspark proxy host")
@click.option("--apply", "do_apply", is_flag=True, default=False,
              help="Auto-write to ~/.openclaw/openclaw.json")
@click.option("--set-default", "set_default", default=None,
              help="Set a default model (e.g., claude-opus-4-6)")
def integrate_openclaw(port, host, do_apply, set_default):
    """Generate OpenClaw provider configuration for Genspark.

    Creates a complete openclaw.json config that registers Genspark CLI
    as a free LLM provider with all 14 AI models.

    \b
    Prerequisites:
      1. genspark auth login        # Login first
      2. genspark server start      # Start proxy in another terminal

    \b
    Examples:
      genspark integrate openclaw                    # Show config
      genspark integrate openclaw --apply            # Write to ~/.openclaw/
      genspark integrate openclaw --apply --set-default claude-opus-4-6
    """
    from .models import MODELS, DEFAULT_MODEL, to_openclaw_models, to_openclaw_allowlist

    base_url = f"http://{host}:{port}/v1"
    default_model = set_default or DEFAULT_MODEL

    # Build OpenClaw config
    openclaw_config = {
        "models": {
            "mode": "merge",
            "providers": {
                "genspark": {
                    "baseUrl": base_url,
                    "apiKey": "sk-genspark-free",
                    "api": "openai-completions",
                    "models": to_openclaw_models(),
                }
            }
        },
        "agents": {
            "defaults": {
                "model": {
                    "primary": f"genspark/{default_model}",
                },
                "models": to_openclaw_allowlist(),
            }
        }
    }

    config_json = json.dumps(openclaw_config, indent=2, ensure_ascii=False)

    if do_apply:
        openclaw_dir = Path.home() / ".openclaw"
        openclaw_dir.mkdir(parents=True, exist_ok=True)
        config_path = openclaw_dir / "openclaw.json"

        # Merge with existing config if present
        if config_path.exists():
            try:
                existing = json.loads(config_path.read_text())
                # Merge providers
                existing_providers = existing.get("models", {}).get("providers", {})
                existing_providers["genspark"] = openclaw_config["models"]["providers"]["genspark"]
                existing.setdefault("models", {})["providers"] = existing_providers
                existing["models"]["mode"] = "merge"
                # Merge allowlist
                existing_models = existing.get("agents", {}).get("defaults", {}).get("models", {})
                existing_models.update(openclaw_config["agents"]["defaults"]["models"])
                existing.setdefault("agents", {}).setdefault("defaults", {})["models"] = existing_models
                # Set primary model
                existing["agents"]["defaults"]["model"] = openclaw_config["agents"]["defaults"]["model"]
                config_json = json.dumps(existing, indent=2, ensure_ascii=False)
            except (json.JSONDecodeError, OSError):
                pass  # Overwrite if corrupt

        config_path.write_text(config_json)
        console.print(f"[bold green]✅ OpenClaw config written to {config_path}[/]")
        console.print(f"[dim]Default model: genspark/{default_model}[/]")
        console.print()
        console.print("[bold]Next steps:[/]")
        console.print("  1. Start the proxy: [cyan]genspark server start[/]")
        console.print("  2. Apply config:    [cyan]openclaw gateway config.apply[/]")
        console.print(f"  3. Verify:          [cyan]openclaw models list[/]")
    else:
        console.print(Panel(
            f"[bold cyan]OpenClaw Provider Configuration[/]\n\n"
            f"[bold]Base URL:[/]  [green]{base_url}[/]\n"
            f"[bold]API Key:[/]   [green]sk-genspark-free[/] (dummy — auth via cookies)\n"
            f"[bold]Models:[/]    [green]{len(MODELS)}[/] free AI models\n"
            f"[bold]Default:[/]   [green]genspark/{default_model}[/]\n"
            f"[bold]Cost:[/]      [green]$0.00[/] (all models free)\n",
            title="Genspark → OpenClaw",
            border_style="green",
        ))
        console.print("[bold]Config JSON:[/]")
        console.print(config_json)
        console.print()
        console.print("[dim]Run with --apply to write to ~/.openclaw/openclaw.json[/]")
        console.print("[dim]Or copy the JSON above into your openclaw.json manually.[/]")


# ── Entry Point ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    main()
