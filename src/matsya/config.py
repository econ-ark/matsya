"""Read the user's Matsya token and explicitly supplied service address.

Environment variables override the user's saved configuration. The client
has no default service address.
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

CONFIG_DIR = Path.home() / ".config" / "matsya"
CONFIG_FILE = CONFIG_DIR / "config.toml"


class ConfigurationError(ValueError):
    """The user has not supplied a Matsya token or a valid service address."""


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
    """Require a service address supplied in configuration or the environment."""
    server = value.strip().rstrip("/")
    if not server:
        raise ConfigurationError(
            "No Matsya service address configured. Set MATSYA_SERVER to the "
            "address supplied by AAS, or run matsya configure."
        )
    parsed = urlsplit(server)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ConfigurationError("The Matsya service address must be an HTTP or HTTPS URL.")
    return server


def load_config() -> dict[str, str]:
    """Return the Matsya token and required service address."""
    cfg = {"token": "", "server": ""}
    if CONFIG_FILE.exists():
        stored = _read_toml(CONFIG_FILE)
        for key in cfg:
            if key in stored:
                cfg[key] = str(stored[key])
    for key, variable in (("token", "MATSYA_TOKEN"), ("server", "MATSYA_SERVER")):
        if value := os.environ.get(variable):
            cfg[key] = value
    cfg["server"] = _server_url(cfg["server"])
    return cfg


def save_config(token: str, server: str | None = None) -> Path:
    """Save the Matsya token and explicit address in the user's private file."""
    if server is None:
        server = os.environ.get("MATSYA_SERVER")
        if not server and CONFIG_FILE.exists():
            server = str(_read_toml(CONFIG_FILE).get("server", ""))
    checked_server = _server_url(server or "")
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    contents = f"token = {json.dumps(token)}\nserver = {json.dumps(checked_server)}\n"
    descriptor = os.open(CONFIG_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        os.fchmod(stream.fileno(), 0o600)
        stream.write(contents)
    return CONFIG_FILE
