"""
Module for applying hex patches to binary files.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Final

from demodapk.utils import msg

WHITESPACE_RE: Final[re.Pattern[str]] = re.compile(r"\s+")


def _clean_hex(value: str) -> str:
    """Remove all whitespace from a hex string."""
    return WHITESPACE_RE.sub("", value)


def _hex_to_regex(hex_string: str) -> re.Pattern[bytes] | None:
    """
    Convert a hex string containing '??' wildcards into a compiled regex.
    """
    hex_string = _clean_hex(hex_string)

    if len(hex_string) % 2:
        msg.error(f"Odd-length hex string: {hex_string}")
        return None

    pattern = bytearray()

    try:
        for i in range(0, len(hex_string), 2):
            chunk = hex_string[i : i + 2]

            if chunk == "??":
                pattern.extend(b".")
            else:
                pattern.extend(re.escape(bytes.fromhex(chunk)))

    except ValueError:
        msg.error(f"Invalid hex characters in search pattern: {hex_string}")
        return None

    return re.compile(bytes(pattern), re.DOTALL)


def _parse_replace_pattern(
    hex_replace_str: str,
    original_bytes: bytearray,
    offset: int,
) -> bytes | None:
    """
    Parse a replacement pattern.

    Supports '??' wildcards which preserve original bytes.
    """
    clean_hex = _clean_hex(hex_replace_str)

    if len(clean_hex) % 2:
        msg.error(f"Odd-length hex replace string: {hex_replace_str}")
        return None

    result = bytearray()

    try:
        for i in range(0, len(clean_hex), 2):
            chunk = clean_hex[i : i + 2]

            if chunk == "??":
                pos = offset + len(result)

                if pos >= len(original_bytes):
                    msg.error(
                        "Replace pattern '??' goes out of bounds at offset "
                        f"{hex(pos)}."
                    )
                    return None

                result.append(original_bytes[pos])
            else:
                result.append(int(chunk, 16))

    except ValueError:
        msg.error(f"Invalid hex characters in replace pattern: {hex_replace_str}")
        return None

    return bytes(result)


def _apply_offset_patch(
    hex_search_or_offset: str,
    hex_replace_str: str,
    patched_data: bytearray,
    verbose: bool,
) -> tuple[int, bytearray]:
    """
    Apply a patch directly at a file offset.
    """
    try:
        target_offset = int(hex_search_or_offset, 16)
    except ValueError:
        msg.error(f"Invalid hex offset: {hex_search_or_offset}")
        return 0, patched_data

    replace_bytes = _parse_replace_pattern(
        hex_replace_str,
        patched_data,
        target_offset,
    )

    if replace_bytes is None:
        return 0, patched_data

    if target_offset + len(replace_bytes) > len(patched_data):
        msg.error(
            f"Offset patch out of bounds: {hex(target_offset)} "
            f"with replace length {len(replace_bytes)}."
        )
        return 0, patched_data

    patched_data[target_offset : target_offset + len(replace_bytes)] = replace_bytes

    if verbose:
        msg.done(f"Replace: [b magenta]{hex_replace_str}")

    msg.info(
        f"  -> Offset: [u green]0x{target_offset:X}[/u green]",
        prefix="?",
    )

    return 1, patched_data


def _apply_search_replace_patch(
    hex_search_or_offset: str,
    hex_replace_str: str,
    patched_data: bytearray,
    verbose: bool,
) -> tuple[int, bytearray]:
    """
    Apply a search-and-replace hex patch.
    """
    regex = _hex_to_regex(hex_search_or_offset)

    if regex is None:
        return 0, patched_data

    try:
        replace_bytes = bytes.fromhex(_clean_hex(hex_replace_str))
    except ValueError:
        msg.error(f"Invalid hex characters in replace pattern: {hex_replace_str}")
        return 0, patched_data

    patches_applied = 0
    current_offset = 0

    while current_offset < len(patched_data):
        match = regex.search(patched_data, current_offset)

        if match is None:
            break

        found_offset = match.start()

        if verbose:
            msg.done(f"Found: [b blue]{hex_search_or_offset}")
            msg.done(f"Replace: [b magenta]{hex_replace_str}")

        msg.info(
            f"  -> Offset: [u green]0x{found_offset:X}[/u green]",
            prefix="?",
        )

        end_offset = found_offset + len(replace_bytes)

        if end_offset > len(patched_data):
            msg.error(
                f"Patch out of bounds for pattern: {hex_search_or_offset}"
            )
            break

        patched_data[found_offset:end_offset] = replace_bytes

        patches_applied += 1
        current_offset = end_offset

    if patches_applied == 0:
        msg.warning(f"Not found: [b blue]{hex_search_or_offset}")

    return patches_applied, patched_data


def update_bin_with_patch(attr: dict, decoded_dir: str) -> None:
    """
    Apply configured hex patches to binary files.
    """
    for hex_patch in attr.get("hex", []):
        rel_path = hex_patch.get("path")
        output_path = hex_patch.get("output")
        patches = hex_patch.get("patch", [])
        verbose = hex_patch.get("verbose", False)

        if not rel_path or not patches:
            msg.error(
                "Invalid hex patch format: requires 'path' and 'patch'."
            )
            continue

        src = Path(decoded_dir) / rel_path
        dst = Path(decoded_dir) / output_path if output_path else None

        patch_codes(
            src=src,
            codes=patches,
            output=dst,
            verbose=verbose,
        )


def patch_codes(
    src: Path | str,
    codes: list[str],
    output: Path | str | None = None,
    verbose: bool = False,
) -> None:
    """
    Patch a binary file using hex patch instructions.

    Format:

        SEARCH | REPLACE
        OFFSET | REPLACE

    Examples:

        AABBCCDD | 11223344
        AA ?? CC | FF EE DD
        0x1234 | 90 90 90
    """
    src = Path(src)

    if not src.is_file():
        msg.error(f"File not found: {src}")
        return

    try:
        patched_data = bytearray(src.read_bytes())
    except OSError as exc:
        msg.error(f"Failed to read file {src}: {exc}")
        return

    total_patches_applied = 0

    msg.info(f"Analyze [b cyan]{src.name}[/] for hex patches.")

    for code in codes:
        parts = [part.strip() for part in code.split("|", 1)]

        if len(parts) != 2:
            msg.error(f"Invalid patch format: {code}")
            continue

        hex_search, hex_replace = parts

        if hex_search.lower().startswith("0x"):
            applied, patched_data = _apply_offset_patch(
                hex_search,
                hex_replace,
                patched_data,
                verbose,
            )
        else:
            applied, patched_data = _apply_search_replace_patch(
                hex_search,
                hex_replace,
                patched_data,
                verbose,
            )

        total_patches_applied += applied

    if total_patches_applied == 0:
        msg.info(f"No patches applied to [b cyan]{src.name}[/].")
        return

    output_path = Path(output) if output else src

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(patched_data)

        msg.done(
            f"Updated {total_patches_applied} hex patch(es) in "
            f"[b cyan]{output_path.name}[/]."
        )

    except OSError as exc:
        msg.error(f"Failed to write file {output_path}: {exc}")
