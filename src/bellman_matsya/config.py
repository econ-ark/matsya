"""Read the user's Matsya token and Bellman service address, and the personal
Anthropic key the user may add after the Matsya token.

An environment setting overrides a saved address, which overrides the
built-in Bellman address. `token_file` answers whether a token is saved,
without returning it, and `first_use` identifies a new installation.

A registered holder of a Matsya token may also select a personal Anthropic
API key, whose Anthropic account is then charged for the language-model
calls of the jobs, questions and replies the holder starts (AMD-MAT-021
§2.2). The key is never required and never replaces the Matsya token. A
nonempty BELLMAN_MATSYA_ANTHROPIC_KEY takes precedence over the key saved in
the owner-only file `anthropic-key` beside `config.toml`;
`selected_anthropic_key` applies that precedence, `check_anthropic_key`
refuses a key that an HTTP header cannot carry, and `save_anthropic_key` and
`clear_anthropic_key` write and delete the file.
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
# the environment variable that supplies a personal Anthropic key without
# saving it, and the name of the file in CONFIG_DIR that holds a saved one
# (AMD-MAT-021 §2.2)
ANTHROPIC_KEY_VARIABLE = "BELLMAN_MATSYA_ANTHROPIC_KEY"
ANTHROPIC_KEY_FILE_NAME = "anthropic-key"
# the sentence with which a personal Anthropic key is refused, which names
# no part of the key (AMD-MAT-021 §2.2)
ANTHROPIC_KEY_REFUSAL = (
    "The personal Anthropic key is empty or contains a space, a line break or a character "
    "outside printable ASCII"
)


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


def anthropic_key_file() -> Path:
    """The file that holds a saved personal Anthropic key,
    `~/.config/bellman-matsya/anthropic-key`, beside `config.toml`; its
    path is formed from CONFIG_DIR when it is asked for (AMD-MAT-021
    §2.2)."""
    return CONFIG_DIR / ANTHROPIC_KEY_FILE_NAME


def check_anthropic_key(key: object) -> str:
    """The key without its surrounding whitespace. A key that is then
    empty, or that holds a character other than the visible ASCII
    characters `!` to `~`, the characters an HTTP header carries
    unchanged, is refused with `ValueError` and the sentence
    `ANTHROPIC_KEY_REFUSAL`, which shows no part of the key (AMD-MAT-021
    §2.2)."""
    held = key.strip() if isinstance(key, str) else ""
    if not held or not all("!" <= character <= "~" for character in held):
        raise ValueError(ANTHROPIC_KEY_REFUSAL)
    return held


def save_anthropic_key(key: str) -> Path:
    """Check a personal Anthropic key (`check_anthropic_key`) and save it
    in its own owner-only file (mode 0600), the key followed by one line
    feed, replacing a key saved before; return the file's path. The file
    `config.toml` is not touched, so that saving the Matsya token again
    leaves the key in place (AMD-MAT-021 §2.2)."""
    checked = check_anthropic_key(key)
    path = anthropic_key_file()
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        os.fchmod(stream.fileno(), 0o600)
        stream.write(checked + "\n")
    return path


def clear_anthropic_key() -> bool:
    """Delete the file of a saved personal Anthropic key, and answer whether
    one was removed. With BELLMAN_MATSYA_ANTHROPIC_KEY unset or empty,
    later work then uses the service's key (AMD-MAT-021 §2.2)."""
    try:
        anthropic_key_file().unlink()
    except FileNotFoundError:
        return False
    return True


def selected_anthropic_key() -> tuple[str | None, str | None]:
    """The personal Anthropic key that the command line and the
    package-level functions select, unchecked, with its source
    (AMD-MAT-021 §2.2): a nonempty BELLMAN_MATSYA_ANTHROPIC_KEY, with the
    source `"environment"`, in place of any saved key; else the text of the
    saved file, with the file's path as the source; else `(None, None)`,
    and the service's key is used. The caller checks the value
    (`check_anthropic_key`), so that a refusal can name the source."""
    value = os.environ.get(ANTHROPIC_KEY_VARIABLE)
    if value:
        return value, "environment"
    path = anthropic_key_file()
    if path.is_file():
        return path.read_bytes().decode("utf-8", "replace"), str(path)
    return None, None
