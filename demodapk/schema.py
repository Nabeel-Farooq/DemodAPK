"""
JSON Schema configuration module.

Features:
- Interactive schema selection
- Safe config.json creation/update
- Local + remote schema support
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

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

CONFIG_FILE = Path("config.json")


SchemaSource = Literal["project", "netlify", "githubusercontent"]


SCHEMA_MAP: dict[SchemaSource, str] = {
    "project": str(SCHEMA_PATH),
    "netlify": SCHEMA_NETLIFY,
    "githubusercontent": SCHEMA_URL,
}


# =========================================================
# Models
# =========================================================

@dataclass(slots=True)
class Config:
    data: dict

    def set_schema(self, schema: str) -> None:
        self.data["$schema"] = schema


# =========================================================
# Config Handling
# =========================================================

def load_config(path: Path) -> Config:
    """
    Load config safely. If invalid JSON, returns empty config.
    """
    if not path.exists():
        return Config(data={})

    try:
        return Config(data=json.loads(path.read_text(encoding="utf-8")))
    except json.JSONDecodeError:
        msg.warning("Invalid config.json detected. Recreating it.")
        return Config(data={})


def save_config(path: Path, config: Config) -> None:
    """
    Save config safely to disk.
    """
    try:
        path.write_text(
            json.dumps(config.data, indent=4),
            encoding="utf-8",
        )
    except (OSError, TypeError) as e:
        raise RuntimeError(f"Failed to write config: {e}") from e


def ensure_config(schema_value: str) -> None:
    """
    Ensure config.json exists and contains schema reference.
    """
    config = load_config(CONFIG_FILE)
    config.set_schema(schema_value)
    save_config(CONFIG_FILE, config)

    msg.success("Schema added successfully to config.json")


# =========================================================
# Schema Selection
# =========================================================

def select_schema() -> SchemaSource | None:
    """
    Prompt user to select schema source.
    """
    question = [
        inquirer.List(
            "schema",
            message="Select JSON Schema source",
            choices=list(SCHEMA_MAP.keys()),
            default="netlify",
        )
    ]

    answer = inquirer.prompt(question)
    if not answer:
        return None

    return answer.get("schema")


def get_schema() -> None:
    """
    CLI entrypoint for schema selection.
    """
    choice = select_schema()

    if not choice:
        msg.error("No selection made")
        sys.exit(1)

    schema_link = SCHEMA_MAP[choice]

    msg.info(f"Selected: {choice} → {schema_link}")

    ensure_config(schema_link)

    sys.exit(0)


# =========================================================
# CLI
# =========================================================

if __name__ == "__main__":
    get_schema()
