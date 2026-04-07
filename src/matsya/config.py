"""Configuration loading for the Matsya client.

Reads token and server URL from:
  1. Environment variables (MATSYA_TOKEN, MATSYA_SERVER) — highest priority
  2. Config file (~/.config/matsya/config.toml)
  3. Built-in defaults
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path

DEFAULT_SERVER = "http://45.55.225.169:8700"
CONFIG_DIR = Path.home() / ".config" / "matsya"
CONFIG_FILE = CONFIG_DIR / "config.toml"


def load_config() -> dict[str, str]:
    """Return ``{"token": ..., "server": ...}`` merged from file + env."""
    cfg: dict[str, str] = {"token": "", "server": DEFAULT_SERVER}

    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "rb") as f:
            file_cfg = tomllib.load(f)
        if "token" in file_cfg:
            cfg["token"] = str(file_cfg["token"])
        if "server" in file_cfg:
            cfg["server"] = str(file_cfg["server"])

    if env_token := os.environ.get("MATSYA_TOKEN"):
        cfg["token"] = env_token
    if env_server := os.environ.get("MATSYA_SERVER"):
        cfg["server"] = env_server

    return cfg


def save_config(token: str, server: str | None = None) -> Path:
    """Write *token* (and optional *server*) to the config TOML file.

    Returns the path written to.
    """
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    lines = [f'token = "{token}"']
    if server and server != DEFAULT_SERVER:
        lines.append(f'server = "{server}"')
    else:
        lines.append(f"# server = \"{DEFAULT_SERVER}\"")

    CONFIG_FILE.write_text("\n".join(lines) + "\n")
    CONFIG_FILE.chmod(0o600)
    return CONFIG_FILE
