"""
Utility helpers for DemodAPK.

Features:
- Rich terminal output
- Gradient ASCII logos
- Shell command execution
- Package table rendering
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from art import text2art
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.traceback import install
from rich_gradient import Gradient
from rich_color_ext.patch import uninstall as restore_rich_colors

# ---------------------------------------------------------------------------
# Rich setup
# ---------------------------------------------------------------------------

restore_rich_colors()
install(show_locals=True)

console = Console(log_path=False)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

CONFIG_PATH = Path.home() / ".config" / "demodapk"
LIBEXEC_PATH = Path.home() / ".local" / "libexec" / "demodapk"

for path in (CONFIG_PATH, LIBEXEC_PATH):
    path.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class Command:
    """Command execution definition."""

    run: str
    title: str = ""
    quiet: bool | None = None


# ---------------------------------------------------------------------------
# Logo
# ---------------------------------------------------------------------------


def show_logo(
    text: str,
    *,
    font: str = "small",
    gradient: bool = True,
    style: str = "bold",
    panel: bool = True,
    padding_lines: int = 1,
) -> None:
    """
    Render an ASCII-art logo.

    Args:
        text: Logo text.
        font: pyfiglet/art font.
        gradient: Enable rainbow gradient.
        style: Rich style.
        panel: Wrap output in a panel.
        padding_lines: Blank lines after logo.
    """

    logo = text2art(text, font=font)

    renderable = (
        Panel.fit(logo, border_style="cyan")
        if panel
        else logo
    )

    if gradient:
        renderable = Gradient(renderable, console=console)

    console.print(renderable, style=style)
    console.line(padding_lines)


# ---------------------------------------------------------------------------
# Terminal Messages
# ---------------------------------------------------------------------------


class CLIPrinter:
    """Rich terminal message helper."""

    LEVELS = {
        "info": ("!", "bold cyan"),
        "error": ("✖", "bold red"),
        "warning": ("⚠", "bold yellow"),
        "progress": ("➜", "bold magenta"),
        "success": ("✓", "bold green"),
    }

    def print(
        self,
        message: object,
        *,
        style: str = "bold",
        prefix: str = "?",
    ) -> None:
        console.print(
            f"[{style}]{prefix}[/] {message}",
            markup=True,
            soft_wrap=True,
        )

    def _emit(self, level: str, message: object) -> None:
        prefix, style = self.LEVELS[level]
        self.print(message, style=style, prefix=prefix)

    def info(self, message: object) -> None:
        self._emit("info", message)

    def error(self, message: object) -> None:
        self._emit("error", message)

    def warning(self, message: object) -> None:
        self._emit("warning", message)

    def progress(self, message: object) -> None:
        self._emit("progress", message)

    def success(self, message: object) -> None:
        self._emit("success", message)

    # aliases
    warn = warning
    done = success
    prog = progress


msg = CLIPrinter()

# ---------------------------------------------------------------------------
# Command Execution
# ---------------------------------------------------------------------------


class CommandExecutionError(RuntimeError):
    """Raised when a command fails."""


def run_command(
    command: str,
    *,
    quiet: bool = False,
    title: str = "",
) -> None:
    """
    Execute a shell command.

    Raises:
        CommandExecutionError
    """

    if quiet and title:
        msg.progress(title)

    kwargs = {
        "shell": True,
        "check": True,
        "env": os.environ.copy(),
    }

    if quiet:
        kwargs.update(
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    try:
        subprocess.run(command, **kwargs)

    except KeyboardInterrupt as exc:
        raise CommandExecutionError(
            "Execution cancelled by user."
        ) from exc

    except subprocess.CalledProcessError as exc:
        raise CommandExecutionError(
            f"Command failed ({exc.returncode}): {command}"
        ) from exc


def run_commands(
    commands: Iterable[str | Command],
    *,
    quiet: bool = False,
    tasker: bool = False,
) -> None:
    """
    Execute multiple commands.
    """

    for item in commands:

        if isinstance(item, str):
            run_command(item, quiet=quiet)

        elif isinstance(item, Command):

            run_command(
                item.run,
                quiet=item.quiet
                if item.quiet is not None
                else quiet,
                title="" if tasker else item.title,
            )


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------


def show_packages(
    packages: list[str],
    selected_index: int | None = None,
) -> None:
    """
    Display package list.
    """

    table = Table(
        title="Available Packages",
        box=box.ROUNDED,
        show_lines=True,
    )

    table.add_column("Index", justify="right", style="cyan")
    table.add_column("Package", style="magenta")

    for index, package in enumerate(packages):

        if index == selected_index:
            package = f"[bold green]{package}[/]"

        table.add_row(str(index), package)

    console.print(table)
