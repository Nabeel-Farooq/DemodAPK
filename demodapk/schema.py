"""
JSON Schema configuration module.

Features:
- Interactive schema selection
- Safe config.json creation/update
- Local and remote schema support
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

import inquirer

import demodapk
from demodapk.utils import msg


# =========================================================
# Paths & Constants
# =========================================================

SCHEMA_PATH = Path(demodapk.__file__).resolve().parent / "schema.json"

SCHEMA_URL = (
    "https://raw.githubusercontent.com/Veha0001/DemodAPK/"
    "refs/heads/main/demodapk/schema.json"
)

SCHEMA_NETLIFY = "https://demodapk.netlify.app/schema.json"

DEFAULT_CONFIG_FILE = Path("config.json")


# =========================================================
# Schema Sources
# =========================================================


class SchemaSource(StrEnum):
    PROJECT = "project"
    NETLIFY = "netlify"
    GITHUB = "githubusercontent"


SCHEMA_MAP: dict[SchemaSource, str] = {
    SchemaSource.PROJECT: str(SCHEMA_PATH),
    SchemaSource.NETLIFY: SCHEMA_NETLIFY,
    SchemaSource.GITHUB: SCHEMA_URL,
}

SCHEMA_CHOICES: dict[str, SchemaSource] = {
    "Local Project Schema": SchemaSource.PROJECT,
    "Netlify (Recommended)": SchemaSource.NETLIFY,
    "GitHub Raw": SchemaSource.GITHUB,
}


# =========================================================
# Models
# =========================================================


@dataclass(slots=True)
class Config:
    data: dict[str, Any]

    def set_schema(self, schema: str) -> None:
        self.data["$schema"] = schema

    def to_json(self) -> str:
        return json.dumps(
            self.data,
            indent=4,
            ensure_ascii=False,
        )


# =========================================================
# Config Handling
# =========================================================


def load_config(path: Path) -> Config:
    """
    Load config safely.

    Returns an empty config if:
    - file does not exist
    - JSON is invalid
    - root object is not a dictionary
    """
    if not path.exists():
        return Config({})

    try:
        data = json.loads(path.read_text(encoding="utf-8"))

        if not isinstance(data, dict):
            raise ValueError("Config root must be a JSON object")

        return Config(data)

    except (json.JSONDecodeError, ValueError):
        msg.warning("Invalid config.json detected. Recreating it.")
        return Config({})


def save_config(path: Path, config: Config) -> None:
    """
    Save config to disk.
    """
    try:
        path.write_text(
            config.to_json(),
            encoding="utf-8",
        )
    except OSError as exc:
        raise RuntimeError(
            f"Failed to write config file: {path}"
        ) from exc


def ensure_config(
    schema_value: str,
    config_path: Path = DEFAULT_CONFIG_FILE,
) -> None:
    """
    Ensure config exists and contains the selected schema.
    """
    config = load_config(config_path)
    config.set_schema(schema_value)

    save_config(config_path, config)

    msg.success(f"Schema added successfully to {config_path}")


# =========================================================
# Schema Selection
# =========================================================


def select_schema() -> SchemaSource | None:
    """
    Prompt the user to select a schema source.
    """
    questions = [
        inquirer.List(
            "schema",
            message="Select JSON Schema source",
            choices=list(SCHEMA_CHOICES.keys()),
            default="Netlify (Recommended)",
        )
    ]

    answer = inquirer.prompt(questions) or {}

    selected = answer.get("schema")
    if selected is None:
        return None

    return SCHEMA_CHOICES[selected]


# =========================================================
# CLI
# =========================================================


def main() -> int:
    """
    CLI entrypoint.
    """
    schema_source = select_schema()

    if schema_source is None:
        msg.error("No schema source selected.")
        return 1

    schema_link = SCHEMA_MAP[schema_source]

    msg.info(f"Selected: {schema_source.value}")
    msg.info(f"Schema: {schema_link}")

    ensure_config(schema_link)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
