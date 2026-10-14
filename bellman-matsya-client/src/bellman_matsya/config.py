"""Read the user's Matsya token and Bellman service address.

An environment setting overrides a saved address, which overrides the
built-in Bellman address. `token_file` answers whether a token is saved,
without returning it, and `first_use` identifies a new installation.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.parse import urlsplit

try:
    import tomllib
except ModuleNotFoundError:
    tomllib = None  # type: ignore[assignment]

CONFIG_DIR = Path.home() / ".config" / "bellman-matsya"
CONFIG_FILE = CONFIG_DIR / "config.toml"
DEFAULT_SERVER_URL = "http://45.55.225.169:8710"


class ConfigurationError(ValueError):
    """The user supplied an invalid service address."""


def _read_toml(path: Path) -> dict:
    """Read the two string settings, including on Python 3.10."""
    if tomllib is not None:
        with open(path, "rb") as stream:
            return tomllib.load(stream)
    result = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            try:
                result[key.strip()] = json.loads(value.strip())
            except json.JSONDecodeError:
                result[key.strip()] = value.strip().strip("'")
    return result


def _server_url(value: str) -> str:
    """Check a service address supplied in configuration or the environment."""
    server = value.strip().rstrip("/")
    if not server:
        raise ConfigurationError("The Matsya service address cannot be empty.")
    parsed = urlsplit(server)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ConfigurationError("The Matsya service address must be an HTTP or HTTPS URL.")
    return server


def load_config() -> dict[str, str]:
    """Return the Matsya token and selected service address."""
    cfg = {"token": "", "server": DEFAULT_SERVER_URL}
    if CONFIG_FILE.exists():
        stored = _read_toml(CONFIG_FILE)
        for key in cfg:
            if key in stored:
                cfg[key] = str(stored[key])
    for key, variable in (("token", "BELLMAN_MATSYA_TOKEN"), ("server", "BELLMAN_MATSYA_SERVER")):
        if value := os.environ.get(variable):
            cfg[key] = value
    cfg["server"] = _server_url(cfg["server"])
    return cfg


def save_config(token: str, server: str | None = None) -> Path:
    """Save the token and any explicit address in the user's private file."""
    if server is None and CONFIG_FILE.exists():
        server = str(_read_toml(CONFIG_FILE).get("server", "")).strip() or None
    checked_server = _server_url(server) if server is not None else DEFAULT_SERVER_URL
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    contents = f"token = {json.dumps(token)}\n"
    if server is not None:
        contents += f"server = {json.dumps(checked_server)}\n"
    descriptor = os.open(CONFIG_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        os.fchmod(stream.fileno(), 0o600)
        stream.write(contents)
    return CONFIG_FILE


def token_file() -> Path | None:
    """The configuration file, when it holds a Matsya token; None when the
    file does not exist, cannot be read or holds no Matsya token. The Matsya
    token itself is not returned."""
    if not CONFIG_FILE.exists():
        return None
    try:
        token = _read_toml(CONFIG_FILE).get("token", "")
    except (OSError, ValueError):
        return None
    return CONFIG_FILE if str(token).strip() else None


def first_use() -> bool:
    """Whether this is the first use of the client on this machine: no
    configuration file exists and BELLMAN_MATSYA_TOKEN is unset."""
    return not CONFIG_FILE.exists() and not os.environ.get("BELLMAN_MATSYA_TOKEN")
