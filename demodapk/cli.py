"""
DemodAPK CLI module.

Provides the main command-line interface for DemodAPK,
including APK decoding, rebuilding, package renaming,
configuration management, and APKEditor updates.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import rich_click as click
from auto_click_auto import enable_click_shell_completion_option

from demodapk import __version__
from demodapk.baseconf import load_config
from demodapk.mods import dowhat, runsteps
from demodapk.utils import show_logo


@click.command()
@click.help_option("-h", "--help")
@click.argument(
    "apk_dir",
    required=False,
    type=click.Path(
        exists=True,
        file_okay=True,
        dir_okay=True,
        path_type=str,
    ),
    metavar="<apk>",
)
@click.option(
    "-i",
    "--id",
    "index",
    type=int,
    default=None,
    metavar="<int>",
    help="Index of configured package.",
)
@click.option(
    "-c",
    "--config",
    default="config.json",
    show_default=True,
    metavar="<json>",
    type=click.Path(
        exists=False,
        file_okay=True,
        dir_okay=True,
        path_type=str,
    ),
    help="Path to the configuration file.",
)
@click.option(
    "-sc",
    "--schema",
    is_flag=True,
    help="Apply schema to the configuration.",
)
@click.option(
    "-S",
    "--single-apk",
    is_flag=True,
    default=False,
    help="Keep only the rebuilt APK.",
)
@click.option(
    "-s",
    "--skip",
    "skip_list",
    multiple=True,
    metavar="<key>",
    type=click.Choice(
        [
            "fb",
            "rename",
        ]
    ),
    help="Skip specific configuration actions.",
)
@click.option(
    "-f",
    "--force",
    is_flag=True,
    default=False,
    help="Overwrite existing files without prompting.",
)
@click.option(
    "-o",
    "--output",
    metavar="<path>",
    type=click.Path(
        exists=False,
        file_okay=True,
        dir_okay=True,
        path_type=str,
    ),
    help="Output directory for decoded and rebuilt APK files.",
)
@click.option(
    "-ua",
    "--getup",
    "update_apkeditor",
    is_flag=True,
    help="Update APKEditor to the latest version.",
)
@click.option(
    "-dex",
    "--raw-dex",
    is_flag=True,
    default=False,
    help="Decode APK using raw DEX files.",
)
@click.option(
    "-sm",
    "--xsmali",
    is_flag=True,
    help="Rename package references inside smali files and directories.",
)
@enable_click_shell_completion_option(
    "--completion",
    "-ac",
    program_name="demodapk",
)
@click.version_option(
    __version__,
    "-v",
    "--version",
)
def main(**kwargs: Any) -> None:
    """
    DemodAPK command-line entry point.
    """
    args = SimpleNamespace(**kwargs)

    try:
        config = load_config(args.config)
        packer = config.get("DemodAPK", {})
    except Exception as exc:
        raise click.ClickException(
            f"Failed to load configuration '{args.config}': {exc}"
        ) from exc

    show_logo("DemodAPK")

    try:
        dowhat(args, click)
        runsteps(args, packer)
    except click.ClickException:
        raise
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc


if __name__ == "__main__":
    main()
