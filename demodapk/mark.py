"""
APK modification utilities using APKEditor.

This module provides functions for managing and executing APKEditor operations,
including updating, decoding, building, and merging APK files.
"""

from __future__ import annotations

import os
import re
import shutil
import sys
from contextlib import nullcontext
from pathlib import Path

from rich.panel import Panel

from demodapk.baseconf import Apkeditor
from demodapk.tool import (
    download_apkeditor,
    get_file_sha256,
    get_latest_apkeditor_info,
)
from demodapk.utils import (
    LIBEXEC_PATH,
    console,
    msg,
    run_commands,
)

APKEDITOR_PATTERN = re.compile(r"APKEditor-(.+?)\.jar$")


def update_apkeditor() -> str | None:
    """
    Ensure the latest APKEditor JAR is installed.

    Returns:
        Path to latest APKEditor JAR or None on failure.
    """
    apkeditor_info = get_latest_apkeditor_info()

    if not apkeditor_info or not apkeditor_info.get("version"):
        msg.error("Could not get latest APKEditor version information.")
        return None

    latest_version = apkeditor_info["version"]
    latest_jar_name = f"APKEditor-{latest_version}.jar"
    latest_jar_path = Path(LIBEXEC_PATH) / latest_jar_name
    remote_sha = apkeditor_info.get("sha256")

    libexec = Path(LIBEXEC_PATH)
    libexec.mkdir(parents=True, exist_ok=True)

    # Remove old versions
    for jar in libexec.glob("APKEditor-*.jar"):
        if jar.name == latest_jar_name:
            continue

        try:
            jar.unlink()
            console.print(
                Panel(
                    jar.name,
                    title="Deleted old version",
                ),
                justify="left",
                style="bold yellow",
            )
        except OSError:
            pass

    # Existing jar validation
    if latest_jar_path.exists():
        if remote_sha:
            local_sha = get_file_sha256(str(latest_jar_path))

            if local_sha == remote_sha:
                console.print(
                    Panel.fit(
                        f"APKEditor [bold blue]v{latest_version}[/bold blue] is up to date.",
                        border_style="bold green",
                    )
                )
                return str(latest_jar_path)

            console.print(
                "Local APKEditor JAR hash mismatch. Redownloading...",
                style="yellow",
            )

        elif latest_jar_path.stat().st_size > 0:
            console.print(
                f"APKEditor v{latest_version} is up to date.",
                style="green",
            )
            return str(latest_jar_path)

    # Download latest
    download_apkeditor(LIBEXEC_PATH)

    if not latest_jar_path.exists():
        msg.error("Failed to download APKEditor.")
        return None

    if remote_sha:
        local_sha = get_file_sha256(str(latest_jar_path))

        if local_sha != remote_sha:
            msg.error(
                "Downloaded APKEditor JAR failed SHA256 verification."
            )
            return None

    return str(latest_jar_path)


def _discover_latest_jar() -> str | None:
    """
    Find the newest APKEditor JAR in LIBEXEC_PATH.
    """
    jars: list[tuple[tuple[int, ...], str]] = []

    for jar in Path(LIBEXEC_PATH).glob("APKEditor-*.jar"):
        match = APKEDITOR_PATTERN.match(jar.name)

        if not match:
            continue

        version = tuple(
            int(v)
            for v in re.findall(r"\d+", match.group(1))
        )

        if version:
            jars.append((version, str(jar)))

    if not jars:
        return None

    jars.sort(reverse=True)
    return jars[0][1]


def get_apkeditor_cmd(cfg: Apkeditor) -> str:
    """
    Return APKEditor execution command.
    """
    javaopts = cfg.javaopts.strip()

    editor_jar: str | None = None

    env_jar = os.environ.get("APKEDITOR_JAR")

    if env_jar and Path(env_jar).is_file():
        editor_jar = env_jar

    elif cfg.editor_jar:
        editor_jar = cfg.editor_jar

        if not Path(editor_jar).is_file():
            msg.error(f"Specified APKEditor JAR not found: {editor_jar}")
            sys.exit(1)

    else:
        editor_jar = _discover_latest_jar()

    if not editor_jar or not Path(editor_jar).is_file():
        msg.info("APKEditor not found. Downloading latest version...")
        editor_jar = update_apkeditor()

        if not editor_jar:
            sys.exit(1)

    if Path(editor_jar).stat().st_size == 0:
        msg.error("APKEditor JAR is empty or corrupted.")
        editor_jar = update_apkeditor()

        if not editor_jar:
            sys.exit(1)

    return f"java {javaopts} -jar \"{editor_jar}\"".strip()


def _status_context(quietly: bool, text: str):
    """
    Shared status context helper.
    """
    if quietly:
        return console.status(
            text,
            spinner="point",
            spinner_style="blue",
        )
    return nullcontext()


def apkeditor_merge(
    cfg: Apkeditor,
    apk_file: str,
    merge_base_apk: str,
    quietly: bool,
    force: bool = False,
) -> None:
    """
    Merge split APKs into a single APK.
    """
    command = (
        f'{get_apkeditor_cmd(cfg)} '
        f'm -i "{Path(apk_file).resolve()}" '
        f'-o "{Path(merge_base_apk).resolve()}"'
    )

    if force:
        command += " -f"

    msg.info(f"Merging: {Path(apk_file).name}", prefix="-")

    with _status_context(quietly, "[bold blue]Processing..."):
        run_commands([command], quietly, tasker=True)

    msg.success(
        f"Merged into: {Path(merge_base_apk).name}",
        prefix="+",
    )


def apkeditor_decode(
    cfg: Apkeditor,
    apk_file: str,
    output_dir: str,
    quietly: bool,
    force: bool,
) -> None:
    """
    Decode an APK using APKEditor.
    """
    apk_path = Path(apk_file).resolve()
    output_path = Path(output_dir).resolve()

    if not apk_path.name.lower().endswith(".apk"):
        merged_apk = apk_path.with_suffix(".apk")

        if not merged_apk.exists():
            apkeditor_merge(
                cfg,
                str(apk_path),
                str(merged_apk),
                quietly,
            )

        apk_path = merged_apk

    command = (
        f'{get_apkeditor_cmd(cfg)} '
        f'd -i "{apk_path}" '
        f'-o "{output_path}"'
    )

    if cfg.dex_option:
        command += " -dex"

    if force:
        command += " -f"

    msg.info(
        f"Decoding: [magenta underline]{apk_path.name}",
        prefix="-",
    )

    with _status_context(quietly, "[bold green]Processing..."):
        run_commands([command], quietly, tasker=True)

    msg.success(
        f"Decoded into: {output_path}",
        prefix="+",
    )


def apkeditor_build(
    cfg: Apkeditor,
    input_dir: str,
    output_apk: str,
    quietly: bool,
    force: bool,
) -> str:
    """
    Build an APK from decoded files.
    """
    input_path = Path(input_dir).resolve()
    output_path = Path(output_apk).resolve()

    command = (
        f'{get_apkeditor_cmd(cfg)} '
        f'b -i "{input_path}" '
        f'-o "{output_path}"'
    )

    if force:
        command += " -f"

    msg.info(f"Building: {input_path.name}", prefix="-")

    with _status_context(
        quietly,
        "[bold green]Finishing Build...",
    ):
        run_commands([command], quietly, tasker=True)

    final_output = str(output_path)

    if cfg.clean:
        final_output = cleanup_apk_build(
            str(input_path),
            str(output_path),
        )

    msg.success(
        f"Built into: {Path(final_output).name}",
        prefix="+",
    )

    return final_output


def cleanup_apk_build(
    input_dir: str,
    output_apk: str,
) -> str:
    """
    Cleanup decoded directory after build.
    """
    input_path = Path(input_dir)
    output_path = Path(output_apk)

    final_apk = input_path.with_suffix(".apk")

    shutil.move(str(output_path), str(final_apk))

    msg.info(
        f"Clean: {input_path.name}",
        prefix="-",
    )

    shutil.rmtree(input_path, ignore_errors=True)

    return str(final_apk)
