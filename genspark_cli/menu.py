"""Interactive home menu, account manager and first-run onboarding for `gsk`.

Everything is numbered-choice driven so users never have to memorise commands.
"""

from __future__ import annotations

import sys
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .exceptions import GensparkError
from .profiles import ProfileManager

console = Console()

QUICK_GUIDE = """[bold cyan]Hướng dẫn nhanh[/]

  [green]gsk[/]                      Mở menu này (lần đầu sẽ có hướng dẫn cài đặt)
  [green]gsk "câu hỏi"[/]            Hỏi nhanh 1 câu, tự chọn tài khoản còn quota
  [green]gsk -i "mô tả ảnh"[/]       Tạo ảnh nhanh
  [green]gsk accounts[/]             Quản lý tài khoản: thêm / đăng nhập / đăng xuất / xóa
  [green]gsk batch ...[/]            Chạy nhiều câu hỏi song song trên mọi tài khoản

[bold cyan]Trong khung chat[/]
  [green]/accounts[/]  Quản lý tài khoản     [green]/pool[/]   Xem tình trạng tài khoản
  [green]/menu[/]      Về menu chính         [green]/help[/]   Xem toàn bộ lệnh

[dim]Mẹo: thêm nhiều tài khoản để chạy song song nhanh hơn và tự chuyển khi hết quota.[/]"""


def _health_label(info: dict) -> str:
    if not info["is_logged_in"]:
        return "[dim]○ Chưa đăng nhập[/]"
    if info["cookie_health"] in ("expired", "stale"):
        return "[yellow]⚠ Hết hạn — cần đăng nhập lại[/]"
    return "[green]● Đã đăng nhập[/]"


def _accounts_table(pm: ProfileManager) -> list[dict]:
    profiles = pm.list_profiles()
    if not profiles:
        console.print("[yellow]Chưa có tài khoản nào.[/]")
        return profiles
    table = Table(title="👥 Tài khoản Genspark", header_style="bold cyan")
    table.add_column("#", justify="right", style="cyan")
    table.add_column("Tên")
    table.add_column("Trạng thái")
    table.add_column("Mặc định", justify="center")
    for idx, info in enumerate(profiles, 1):
        table.add_row(
            str(idx),
            info["name"],
            _health_label(info),
            "★" if info["is_default"] else "",
        )
    console.print(table)
    return profiles


def _next_free_name(pm: ProfileManager) -> str:
    existing = {p["name"] for p in pm.list_profiles()}
    if "default" not in existing:
        return "default"
    n = 2
    while f"acc{n}" in existing:
        n += 1
    return f"acc{n}"


def login_account(pm: ProfileManager, name: str) -> bool:
    """Create the profile if needed and run the browser login flow."""
    from .auth import run_login

    try:
        session = pm.get_session(name) if pm._profile_exists(name) else pm.add_profile(name)
    except ValueError as exc:
        console.print(f"[red]Lỗi:[/] {exc}")
        return False

    console.print(
        Panel(
            f"Sắp mở trình duyệt để đăng nhập tài khoản [bold cyan]{name}[/].\n\n"
            "  1. Đăng nhập bằng Google / email Genspark\n"
            "  2. Đợi trang chat tải xong\n"
            "  3. Gửi [bold]1 tin nhắn bất kỳ[/] trong khung chat\n"
            "  4. Quay lại đây và nhấn [bold]Enter[/]",
            title="Đăng nhập",
            border_style="blue",
        )
    )
    try:
        ok = run_login(session)
    except GensparkError as exc:
        console.print(f"[red]Đăng nhập thất bại:[/] {exc}")
        return False
    if ok:
        console.print(f"[bold green]✓ Đã lưu phiên đăng nhập cho '{name}'.[/]")
    else:
        console.print("[yellow]Chưa hoàn tất đăng nhập. Hãy thử lại.[/]")
    return bool(ok)


def _pick_account(profiles: list[dict], action: str) -> Optional[dict]:
    if not profiles:
        return None
    choice = click.prompt(
        f"Chọn số tài khoản để {action} (Enter để huỷ)",
        default="",
        show_default=False,
    ).strip()
    if not choice.isdigit() or not (1 <= int(choice) <= len(profiles)):
        return None
    return profiles[int(choice) - 1]


def accounts_menu(pm: Optional[ProfileManager] = None) -> None:
    """Add / re-login / logout / remove / set-default accounts."""
    pm = pm or ProfileManager()
    while True:
        console.print()
        profiles = _accounts_table(pm)
        console.print(
            "\n  [cyan]1[/] · Thêm tài khoản mới\n"
            "  [cyan]2[/] · Đăng nhập lại (làm mới phiên hết hạn)\n"
            "  [cyan]3[/] · Đăng xuất (xoá phiên, giữ tên tài khoản)\n"
            "  [cyan]4[/] · Xoá hẳn tài khoản\n"
            "  [cyan]5[/] · Đặt làm tài khoản mặc định\n"
            "  [cyan]0[/] · Quay lại"
        )
        choice = click.prompt("Chọn", default="0", show_default=False).strip()

        if choice == "0":
            return
        if choice == "1":
            name = click.prompt("Đặt tên cho tài khoản", default=_next_free_name(pm)).strip()
            login_account(pm, name)
        elif choice == "2":
            target = _pick_account(profiles, "đăng nhập lại")
            if target:
                login_account(pm, target["name"])
        elif choice == "3":
            target = _pick_account(profiles, "đăng xuất")
            if target and click.confirm(f"Đăng xuất '{target['name']}'?", default=False):
                pm.get_session(target["name"]).clear()
                console.print(f"[green]✓ Đã đăng xuất '{target['name']}'.[/] Có thể đăng nhập lại ở mục 2.")
        elif choice == "4":
            target = _pick_account(profiles, "xoá")
            if not target:
                continue
            if target["is_default"]:
                console.print("[yellow]Đây là tài khoản mặc định — hãy đặt tài khoản khác làm mặc định (mục 5) trước.[/]")
            elif click.confirm(f"Xoá vĩnh viễn '{target['name']}'?", default=False):
                try:
                    pm.remove_profile(target["name"])
                    console.print(f"[green]✓ Đã xoá '{target['name']}'.[/]")
                except ValueError as exc:
                    console.print(f"[red]Lỗi:[/] {exc}")
        elif choice == "5":
            target = _pick_account(profiles, "đặt mặc định")
            if target:
                pm.default_profile = target["name"]
                console.print(f"[green]✓ Mặc định: {target['name']}[/]")
        else:
            console.print("[yellow]Lựa chọn không hợp lệ.[/]")


def needs_onboarding(pm: ProfileManager) -> bool:
    return not any(p["is_logged_in"] for p in pm.list_profiles())


def onboarding(pm: Optional[ProfileManager] = None) -> bool:
    """First-run guided setup. Returns True when at least one account is ready."""
    pm = pm or ProfileManager()
    console.print(
        Panel(
            "[bold cyan]✨ Chào mừng đến với Genspark Studio[/]\n\n"
            "Công cụ này dùng chính tài khoản Genspark của bạn — [bold]không cần API key[/].\n"
            "Chỉ cần 3 bước, khoảng 1 phút:\n\n"
            "  [cyan]Bước 1[/]  Đăng nhập tài khoản đầu tiên (mở trình duyệt)\n"
            "  [cyan]Bước 2[/]  Thêm tài khoản phụ nếu có (tuỳ chọn — chạy nhanh hơn, tự chuyển khi hết quota)\n"
            "  [cyan]Bước 3[/]  Chọn cách dùng rồi bắt đầu chat",
            border_style="cyan",
        )
    )

    console.print("\n[bold]Bước 1/3 · Đăng nhập tài khoản đầu tiên[/]")
    while True:
        if login_account(pm, _next_free_name(pm) if not pm._profile_exists("default") else "default"):
            break
        if not click.confirm("Thử đăng nhập lại?", default=True):
            console.print("[dim]Bạn có thể đăng nhập sau bằng: gsk accounts[/]")
            return False

    console.print("\n[bold]Bước 2/3 · Thêm tài khoản phụ (tuỳ chọn)[/]")
    while click.confirm("Thêm một tài khoản nữa?", default=False):
        name = click.prompt("Đặt tên", default=_next_free_name(pm)).strip()
        login_account(pm, name)

    ready = [p for p in pm.list_profiles() if p["is_logged_in"]]
    console.print("\n[bold]Bước 3/3 · Chọn cách dùng[/]")
    if len(ready) > 1:
        console.print(f"  Bạn có [green]{len(ready)}[/] tài khoản → bật chế độ [bold]tự xoay vòng[/] (round-robin).")
        pm.update_config(routing_strategy="round-robin")
    else:
        console.print("  Có 1 tài khoản → dùng trực tiếp. Thêm tài khoản sau ở menu [bold]Tài khoản[/].")

    console.print(
        Panel(
            f"[bold green]✓ Sẵn sàng![/] {len(ready)} tài khoản đã đăng nhập.\n"
            "Lần sau chỉ cần gõ [bold cyan]gsk[/] để mở menu.",
            border_style="green",
        )
    )
    return bool(ready)


def _header(pm: ProfileManager) -> str:
    profiles = pm.list_profiles()
    ready = sum(1 for p in profiles if p["is_logged_in"])
    return (
        f"[bold cyan]⚡ Genspark Studio[/]   "
        f"Tài khoản sẵn sàng: [green]{ready}[/]/{len(profiles)} · "
        f"Chế độ: [cyan]{pm.routing_strategy}[/] · Model: [cyan]{pm.default_model}[/]"
    )


def _run_cli(*args: str) -> None:
    from .cli import main

    try:
        main.main(args=list(args), standalone_mode=False)
    except SystemExit:
        pass
    except click.ClickException as exc:
        exc.show()
    except click.exceptions.Abort:
        console.print("[dim]Đã huỷ.[/]")


def home_menu(pm: Optional[ProfileManager] = None) -> None:
    """Main interactive menu (shown by bare `gsk`)."""
    pm = pm or ProfileManager()
    if needs_onboarding(pm):
        onboarding(pm)

    while True:
        console.print()
        console.print(Panel(_header(pm), border_style="cyan"))
        console.print(
            "  [cyan]1[/] · 💬 Trò chuyện với AI\n"
            "  [cyan]2[/] · 👥 Tài khoản  [dim](thêm · đăng nhập · đăng xuất · xoá)[/]\n"
            "  [cyan]3[/] · 🎨 Tạo ảnh\n"
            "  [cyan]4[/] · ⚙️  Cài đặt  [dim](model mặc định, chế độ xoay vòng, số luồng)[/]\n"
            "  [cyan]5[/] · 📡 Kiểm tra tài khoản còn hoạt động không\n"
            "  [cyan]6[/] · ❓ Hướng dẫn nhanh\n"
            "  [cyan]0[/] · Thoát"
        )
        try:
            choice = click.prompt("Chọn", default="1", show_default=False).strip()
        except click.exceptions.Abort:
            return

        if choice in ("0", "q", "quit"):
            console.print("[dim]Hẹn gặp lại![/]")
            return
        if choice == "1":
            _run_cli("chat")
        elif choice == "2":
            accounts_menu(pm)
        elif choice == "3":
            prompt = click.prompt("Mô tả ảnh bạn muốn", default="", show_default=False).strip()
            if prompt:
                _run_cli("image", "generate", prompt)
        elif choice == "4":
            _run_cli("config", "wizard")
        elif choice == "5":
            _run_cli("pool", "ping")
        elif choice == "6":
            console.print(Panel(QUICK_GUIDE, border_style="blue"))
        else:
            console.print("[yellow]Lựa chọn không hợp lệ.[/]")


def is_interactive_terminal() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()
