"""The acceptance file of AMD-MAT-021 on the side of the client: a registered
holder's personal Anthropic API key, an addition to the Matsya token and never
a substitute for it.

Against no service (`new_machine`): `configure --set-anthropic-key`, which
requires a configured Matsya token and otherwise asks for nothing and writes
nothing (§2.1), and which saves and replaces the key in its owner-only file,
as `configure --clear-anthropic-key` removes it, without showing it (§2.2);
the orientation's line in each of its three states (§2.5); and the literal
test of the addresses that may receive a key (§2.4). Against the stand-in of
the service: the precedence of the environment over the saved file, and the
constructor, which reads neither; the refusal of a key with an internal
space, line break or other character that an HTTP header does not allow, in
the sentence that names its source and with no traceback, and the acceptance
of a key whose only fault is surrounding whitespace (§2.2); the three
requests that carry the key and the many that do not, and the Matsya token
that always travels with it (§2.3); the refusal, before the first request,
of every command and function that would send the key to a plain-HTTP
address that is not a loopback host, while a command that sends no key
proceeds there; the bypass of any proxy at a loopback address; the
verification of an HTTPS certificate and the zero debug level, whatever the
calling process has set; and the refusal of a redirect that would move a
secret to another origin (§2.4); the credential line, the report of work the
service accepted under its own key, and the remedy added to the service's
refusal of a reply without a key (§2.5); and the masking of the key in every
message, with its absence from every file, output and request other than the
header of those three requests (§5 item 6). Every key is a distinctive fake
value, and no assertion shows one: a leak is reported by `_no_key_in`, which
names where it was found, and a key in a text that is compared is replaced
by its name (`_named`)."""

from __future__ import annotations

import http.client
import io
import json
import logging
import re
import shutil
import ssl
import subprocess
import threading
import traceback
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

import bellman_matsya
from conftest import ANSWER, KEY_HEADER, TOKEN, _user
from bellman_matsya import cli, config, project
from bellman_matsya.client import (
    MatsyaClient,
    MatsyaError,
    _SameHostRedirects,
    key_destination_allowed,
)

# two distinctive fake keys; neither is a real Anthropic key
KEY = "sk-ant-test-AMD021-client-first-7f3a9c"
OTHER_KEY = "sk-ant-test-AMD021-client-second-2b8e41"
VARIABLE = "BELLMAN_MATSYA_ANTHROPIC_KEY"
# a plain-HTTP address that is not a loopback host; `at_remote` sends what
# is addressed to it to the stand-in, so that no request leaves the machine
REMOTE = "http://matsya.example.invalid:8710"
HTTPS_ADDRESS = "https://matsya.example.invalid"
TIME = re.compile(r"^\d\d:\d\d:\d\d  ")

# the sentences of the amendment, as it quotes them
NO_TOKEN = (
    "Error: no Matsya token is configured. A personal Anthropic key is an addition to a Matsya "
    "token, not a substitute for it: save the Matsya token the service's administrator gave you "
    "with bellman-matsya configure, or set BELLMAN_MATSYA_TOKEN.\n"
)
CONSTRUCTOR_REFUSAL = (
    "The personal Anthropic key is empty or contains a space, a line break or a character "
    "outside printable ASCII"
)
VARIABLE_REFUSAL = (
    "Error: the personal Anthropic key in BELLMAN_MATSYA_ANTHROPIC_KEY is empty or contains a "
    "space, a line break or another character that an HTTP header does not allow; set the "
    "variable to the key alone, or unset it to use the service's key.\n"
)
ENTERED_REFUSAL = (
    "Error: the key you entered is empty or contains a space, a line break or another character "
    "that an HTTP header does not allow; nothing was saved.\n"
)
FROM_VARIABLE = (
    "The environment variable `BELLMAN_MATSYA_ANTHROPIC_KEY` is set; new jobs, questions and "
    "replies that continue a job use its value in place of any saved key, and the Anthropic "
    "account of that key is charged."
)
NONE_SELECTED = (
    "No personal Anthropic key is selected; new jobs and questions use the service's key, and a "
    "reply that would continue a job run with a personal key is refused until one is selected."
)
CREDENTIAL = "Credential: your Anthropic API key"
# what replaces the personal key in every message the client composes (§2.5)
MASK = "<Anthropic API key>"
REPLY_REFUSAL = (
    "Error: The service refused the request (422): The job awaiting this reply ran under a "
    "personal Anthropic key; send the reply with a personal Anthropic key. Supply one with "
    "bellman-matsya configure --set-anthropic-key, BELLMAN_MATSYA_ANTHROPIC_KEY, or "
    "MatsyaClient(..., anthropic_api_key=...).\n"
)

# keys refused for a character that an HTTP header does not allow, after
# their surrounding whitespace is removed, and keys whose only fault is that
# whitespace; the names serve as the tests' identifiers, so that none shows
# a key
INVALID = {
    "internal line feed": KEY[:12] + "\n" + KEY[12:],
    "internal carriage return": KEY[:12] + "\r" + KEY[12:],
    "internal space": KEY[:12] + " " + KEY[12:],
    "internal tab": KEY[:12] + "\t" + KEY[12:],
    "trailing control character": KEY + "\x07",
    "character outside ASCII": KEY + "é",
    "whitespace alone": " \n\t ",
}
SURROUNDED = {
    "trailing line feed": KEY + "\n",
    "trailing carriage return": KEY + "\r",
    "trailing carriage return and line feed": KEY + "\r\n",
    "spaces and a tab around it": " \t" + KEY + "  ",
}


def _no_key_in(text: str | bytes, where: str) -> None:
    """Fail, without showing the text, when a test key appears in it."""
    data = text if isinstance(text, bytes) else text.encode("utf-8", "surrogatepass")
    if any(key.encode() in data for key in (KEY, OTHER_KEY)):
        pytest.fail(f"a test key appears in {where}", pytrace=False)


def _named(text: str) -> str:
    """The text with each test key replaced by its name."""
    return text.replace(KEY, "<KEY>").replace(OTHER_KEY, "<OTHER_KEY>")


def _key_sent(request: dict) -> str:
    """The key a request the stand-in recorded carried, by its name: `KEY`,
    `OTHER_KEY`, `none` or `another value`."""
    values = [value for name, value in request["headers"].items() if name.lower() == KEY_HEADER]
    if not values:
        return "none"
    return {KEY: "KEY", OTHER_KEY: "OTHER_KEY"}.get(values[0], "another value")


def _route(request: dict) -> str:
    """A recorded request as its method and route, identifiers replaced."""
    path = urllib.parse.urlsplit(request["path"]).path
    return f"{request['method']} " + re.sub(r"[0-9a-f]{32}", "<id>", path)


def _sent(stand_in) -> list[tuple[str, str]]:
    """The requests the stand-in received since the last call, each as its
    route and the key it carried."""
    sent = [(_route(request), _key_sent(request)) for request in stand_in.requests]
    stand_in.requests.clear()
    return sent


def _identifier(pattern: str, text: str) -> str:
    found = re.search(pattern, text, re.MULTILINE)
    assert found, _named(text)
    return found.group(1)


def _final(out: str) -> list[str]:
    """The lines a command printed, without the lines of progress."""
    return [line for line in out.splitlines() if not TIME.match(line)]


def _destination_refusal(address: str) -> str:
    return (
        "A personal Anthropic key is sent only over HTTPS or to localhost, 127.0.0.1 or ::1, and "
        f"the service address is {address}; use an HTTPS address, or stop selecting the key: unset "
        "BELLMAN_MATSYA_ANTHROPIC_KEY, run bellman-matsya configure --clear-anthropic-key, or omit "
        "anthropic_api_key."
    )


def _file_refusal(path: Path) -> str:
    return (
        f"Error: the personal Anthropic key in the saved file {path} is empty or contains a space, "
        "a line break or another character that an HTTP header does not allow; set it again with "
        "bellman-matsya configure --set-anthropic-key, or remove it with bellman-matsya configure "
        "--clear-anthropic-key.\n"
    )


def _saved(path: Path) -> str:
    return (
        f"A personal Anthropic key is saved on this machine, in `{path}`; new jobs, questions and "
        "replies that continue a job use it, and the Anthropic account of that key is charged."
    )


def _plain_http(address: str) -> str:
    return (
        f"The service address {address} uses plain HTTP, so the client refuses to send a job, a "
        "question or a reply with this key."
    )


def _own_key(url: str, kind: str, work_id: str) -> str:
    return f"Error: the service at {url} accepted {kind} {work_id} under its own Anthropic key, not yours.\n"


def _key_file() -> Path:
    return config.CONFIG_DIR / "anthropic-key"


def _write_key_file(content: bytes) -> Path:
    """A saved key file holding `content`, owner-only."""
    path = _key_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    path.chmod(0o600)
    return path


def _text(folder: Path, name: str, text: str) -> Path:
    path = folder / name
    path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture
def entered(monkeypatch: pytest.MonkeyPatch) -> list:
    """The answers the prompt of `configure --set-anthropic-key` receives, in
    order, and the prompts it showed, kept under `entered.prompts`; the
    prompt is `getpass.getpass`, which does not show what is typed."""

    class Answers(list):
        prompts: list[str]

    answers = Answers()
    answers.prompts = []

    def prompt(text: str = "") -> str:
        answers.prompts.append(text)
        held = answers.pop(0)
        if isinstance(held, BaseException):
            raise held
        return held

    monkeypatch.setattr("getpass.getpass", prompt)
    return answers


# ---------------------------------------------------------------------------
# §§2.1 and 2.2: configure


def test_set_anthropic_key_requires_a_configured_matsya_token(new_machine, run, monkeypatch, entered) -> None:
    """Without a Matsya token the option prints the sentence of §2.1 on
    standard error, exits with status 1, prompts for nothing and writes
    nothing; an address the client cannot read is reported as `configure`
    reports it; a Matsya token saved by `configure` or set in
    BELLMAN_MATSYA_TOKEN suffices. `--clear-anthropic-key` needs none."""
    entered += [KEY, KEY]
    status, out, err = run("configure", "--set-anthropic-key")
    assert (status, out, err) == (1, cli.FIRST_USE + "\n", NO_TOKEN)
    assert entered.prompts == [] and not config.CONFIG_DIR.exists()
    status, out, err = run("configure", "--clear-anthropic-key")
    assert (status, err) == (0, "") and not config.CONFIG_DIR.exists()

    # a saved address the client cannot read: the sentence of `configure`,
    # with no traceback, and no prompt
    config.CONFIG_DIR.mkdir(parents=True)
    new_machine.write_text(f'token = "{TOKEN}"\nserver = "ftp://matsya.example.invalid"\n')
    status, out, err = run("configure", "--set-anthropic-key")
    assert (status, out) == (1, "") and entered.prompts == [] and not _key_file().exists()
    assert err == "Error: The Matsya service address must be an HTTP or HTTPS URL.\n"
    monkeypatch.setattr("builtins.input", lambda prompt="": TOKEN)
    assert run("configure")[::2] == (1, err)

    # a Matsya token saved by configure
    new_machine.unlink()
    config.save_config(TOKEN)
    status, out, err = run("configure", "--set-anthropic-key")
    assert (status, err) == (0, "") and _key_file().is_file()
    # a Matsya token set in BELLMAN_MATSYA_TOKEN alone
    new_machine.unlink()
    _key_file().unlink()
    monkeypatch.setenv("BELLMAN_MATSYA_TOKEN", TOKEN)
    status, out, err = run("configure", "--set-anthropic-key")
    assert (status, err) == (0, "") and _key_file().is_file() and not new_machine.exists()
    assert entered.prompts == ["Enter your Anthropic API key (it is not shown): "] * 2
    _no_key_in(out + err, "the output of configure --set-anthropic-key")


def test_a_key_is_saved_replaced_and_removed_in_an_owner_only_file_without_being_shown(
    new_machine, run, monkeypatch, entered
) -> None:
    """The key, asked for without echo and never as an argument, is saved
    without its surrounding whitespace in `anthropic-key` beside
    `config.toml`, mode 0600, followed by one line feed; plain `configure`
    leaves it in place; a second key replaces it, the mode made 0600 again;
    `--clear-anthropic-key` removes it and says whether one was removed. No
    output shows the key, and neither option asks for the Matsya token."""
    monkeypatch.setenv("BELLMAN_MATSYA_TOKEN", TOKEN)
    monkeypatch.setattr("builtins.input", lambda prompt="": pytest.fail("the Matsya token was asked for"))
    path = _key_file()
    entered += ["  " + KEY + "  "]
    status, out, err = run("configure", "--set-anthropic-key")
    _no_key_in(out + err, "the output of configure --set-anthropic-key")
    assert (status, err) == (0, "")
    assert out.splitlines() == [
        "Matsya: save a personal Anthropic API key",
        "",
        f"Personal Anthropic key saved to {path}",
        "New jobs, questions and replies that continue a job use this key, and the Anthropic "
        "account of this key is charged.",
        _plain_http(config.DEFAULT_SERVER_URL),
        "Remove it with: bellman-matsya configure --clear-anthropic-key",
    ]
    assert path == config.CONFIG_DIR / "anthropic-key" and path.parent == new_machine.parent
    assert _named(path.read_text(encoding="ascii")) == "<KEY>\n"
    assert path.stat().st_mode & 0o777 == 0o600

    # configure, which rewrites config.toml, leaves the key in place
    monkeypatch.setattr("builtins.input", lambda prompt="": TOKEN)
    assert run("configure")[0] == 0 and new_machine.is_file()
    assert _named(path.read_text(encoding="ascii")) == "<KEY>\n"

    # a second key replaces the first, and the file is made owner-only again;
    # at an HTTPS address no sentence on plain HTTP is printed
    path.chmod(0o644)
    monkeypatch.setenv("BELLMAN_MATSYA_SERVER", HTTPS_ADDRESS)
    entered += [OTHER_KEY]
    status, out, err = run("configure", "--set-anthropic-key")
    _no_key_in(out + err, "the output of configure --set-anthropic-key")
    assert (status, err) == (0, "")
    assert out.splitlines()[3:] == [
        "New jobs, questions and replies that continue a job use this key, and the Anthropic "
        "account of this key is charged.",
        "Remove it with: bellman-matsya configure --clear-anthropic-key",
    ]
    assert _named(path.read_text(encoding="ascii")) == "<OTHER_KEY>\n"
    assert path.stat().st_mode & 0o777 == 0o600

    # with BELLMAN_MATSYA_ANTHROPIC_KEY set, its value is used in place of
    # the saved key, and the output says so
    monkeypatch.setenv(VARIABLE, KEY)
    entered += [OTHER_KEY]
    status, out, err = run("configure", "--set-anthropic-key")
    _no_key_in(out + err, "the output of configure --set-anthropic-key")
    assert out.splitlines()[3] == (
        "The environment variable BELLMAN_MATSYA_ANTHROPIC_KEY is set, and new jobs, questions and "
        "replies that continue a job use its value in place of this key until it is unset."
    )

    # removal, which needs no Matsya token
    monkeypatch.delenv("BELLMAN_MATSYA_TOKEN")
    new_machine.unlink()
    status, out, err = run("configure", "--clear-anthropic-key")
    assert (status, err) == (0, "") and not path.exists()
    assert out.splitlines()[-2:] == [
        f"Removed the saved personal Anthropic key, {path}.",
        "The environment variable BELLMAN_MATSYA_ANTHROPIC_KEY is set, and new jobs, questions and "
        "replies that continue a job use its value until it is unset.",
    ]
    monkeypatch.delenv(VARIABLE)
    status, out, err = run("configure", "--clear-anthropic-key")
    assert (status, err) == (0, "")
    assert out.splitlines()[-2:] == [
        f"No personal Anthropic key was saved on this machine, in {path}; nothing was removed.",
        "New jobs and questions use the service's key.",
    ]
    _no_key_in(out, "the output of configure --clear-anthropic-key")
    assert entered == [] and len(entered.prompts) == 3


@pytest.mark.parametrize("name", sorted(INVALID))
def test_a_key_entered_with_a_character_a_header_does_not_allow_is_not_saved(
    new_machine, run, monkeypatch, entered, name
) -> None:
    monkeypatch.setenv("BELLMAN_MATSYA_TOKEN", TOKEN)
    path = _write_key_file(KEY.encode() + b"\n")
    entered += [INVALID[name]]
    status, out, err = run("configure", "--set-anthropic-key")
    _no_key_in(out + err, "the refusal of an entered key")
    assert (status, err) == (1, ENTERED_REFUSAL)
    assert _named(path.read_text(encoding="ascii")) == "<KEY>\n"


def test_the_end_of_the_input_at_the_prompt_saves_nothing(new_machine, run, monkeypatch, entered) -> None:
    monkeypatch.setenv("BELLMAN_MATSYA_TOKEN", TOKEN)
    entered += [EOFError()]
    assert run("configure", "--set-anthropic-key")[::2] == (1, ENTERED_REFUSAL)
    assert not _key_file().exists()
    entered += [KeyboardInterrupt()]
    status, _, err = run("configure", "--set-anthropic-key")
    assert (status, err) == (130, "\nStopped; nothing was saved.\n") and not _key_file().exists()


def test_the_options_are_exclusive_and_the_help_names_them_as_optional_additions(new_machine, run) -> None:
    status, out, err = run("configure", "--set-anthropic-key", "--clear-anthropic-key")
    assert (status, out) == (2, "") and "not allowed with argument" in err
    status, out, _ = run("--help")
    setup = out[out.index("Set up once:") : out.index("Examples:")]
    assert setup.index("bellman-matsya configure  ") < setup.index("once the Matsya token is configured")
    for name in ("--set-anthropic-key", "--clear-anthropic-key", "BELLMAN_MATSYA_ANTHROPIC_KEY"):
        assert setup.index("once the Matsya token is configured") < setup.index(name), name
    status, out, _ = run("configure", "--help")
    text = " ".join(out.split())
    assert status == 0 and "Once the Matsya token is configured, you may add a personal Anthropic API key" in text
    for name in ("--set-anthropic-key", "--clear-anthropic-key", "BELLMAN_MATSYA_ANTHROPIC_KEY"):
        assert name in text, name


# ---------------------------------------------------------------------------
# §2.5: the orientation


def test_the_orientation_names_the_credential_of_the_next_job_and_never_a_key(
    new_machine, run, monkeypatch
) -> None:
    """One line after the Matsya token's line, in exactly one of three
    states, checked in order: the variable, a saved key, no key; with a key
    selected and an address that fails the test of §2.4, the line adds the
    sentence on plain HTTP."""

    def line() -> str:
        status, out, err = run()
        _no_key_in(out + err, "the orientation")
        assert (status, err) == (0, "")
        lines = out.splitlines()
        assert lines[6].startswith(("A Matsya token", "No Matsya token"))
        return lines[7]

    assert line() == NONE_SELECTED
    path = _write_key_file(KEY.encode() + b"\n")
    # the built-in Bellman address uses plain HTTP
    assert line() == _saved(path) + " " + _plain_http(config.DEFAULT_SERVER_URL)
    monkeypatch.setenv(VARIABLE, OTHER_KEY)
    assert line() == FROM_VARIABLE + " " + _plain_http(config.DEFAULT_SERVER_URL)
    for address in (HTTPS_ADDRESS, "http://127.0.0.1:8710", "http://localhost:8710", "http://[::1]:8710"):
        monkeypatch.setenv("BELLMAN_MATSYA_SERVER", address)
        assert line() == FROM_VARIABLE, address
    monkeypatch.setenv("BELLMAN_MATSYA_SERVER", "http://127.0.0.2:8710")
    assert line() == FROM_VARIABLE + " " + _plain_http("http://127.0.0.2:8710")
    # an empty variable selects nothing, and the saved key is named
    monkeypatch.setenv(VARIABLE, "")
    monkeypatch.setenv("BELLMAN_MATSYA_SERVER", HTTPS_ADDRESS)
    assert line() == _saved(path)
    # a key file that holds no usable key is still named, and is not read
    path.write_bytes(b"\xff not a key\n")
    assert line() == _saved(path)
    path.unlink()
    assert line() == NONE_SELECTED
    # an address the client cannot read adds nothing, and raises nothing
    monkeypatch.setenv(VARIABLE, KEY)
    monkeypatch.setenv("BELLMAN_MATSYA_SERVER", "ftp://matsya.example.invalid")
    assert line() == FROM_VARIABLE


# ---------------------------------------------------------------------------
# §2.4: the addresses that may receive a key


ALLOWED = (
    "https://matsya.example.invalid",
    "https://45.55.225.169:8443",
    "HTTPS://matsya.example.invalid:443",
    "http://localhost:8710",
    "http://LOCALHOST:8710",
    "http://127.0.0.1:8710",
    "http://127.0.0.1",
    "http://[::1]:8710",
)
REFUSED = (
    "http://45.55.225.169:8710",
    "http://matsya.example.invalid:8710",
    "http://127.0.0.2:8710",
    "http://127.1:8710",
    "http://localhost.:8710",
    "http://localhost.localdomain:8710",
    "http://0.0.0.0:8710",
    "http://[::ffff:127.0.0.1]:8710",
    "http://[0:0:0:0:0:0:0:1]:8710",
    "http://[::1%25lo0]:8710",
)


def test_the_addresses_that_may_receive_a_key_are_tested_literally() -> None:
    """An `https` address, or an `http` address whose host, as urllib gives
    it in lower case and without brackets, is literally `localhost`,
    `127.0.0.1` or `::1`; no name is resolved. The client is constructed at
    any address; a client that holds a key is refused at the others, and a
    client that holds none is never refused."""
    for address in ALLOWED:
        assert key_destination_allowed(address), address
        MatsyaClient(TOKEN, address, anthropic_api_key=KEY).check_key_destination()
    for address in REFUSED:
        assert not key_destination_allowed(address), address
        MatsyaClient(TOKEN, address).check_key_destination()
        client = MatsyaClient(TOKEN, address + "/", anthropic_api_key=KEY)
        with pytest.raises(MatsyaError) as refused:
            client.check_key_destination()
        _no_key_in(str(refused.value), "the refusal of an address")
        assert str(refused.value) == _destination_refusal(address), address


# ---------------------------------------------------------------------------
# §2.2: selection, precedence and the check of the key


def test_the_environment_takes_precedence_over_the_saved_key_and_the_constructor_reads_neither(
    stand_in, run, monkeypatch, tmp_path
) -> None:
    def submitted() -> str:
        status, out, err = run("job", "submit", "--session", session_id, "--target", "stage")
        _no_key_in(out + err, "the output of job submit")
        assert status == 0, _named(err)
        ((route, key),) = _sent(stand_in)
        assert route == "POST /v1/model-iterations"
        return key

    session_id = MatsyaClient(TOKEN, stand_in.url).new_session("a household")["id"]
    MatsyaClient(TOKEN, stand_in.url).add_entry(session_id, "A household saves.")
    stand_in.requests.clear()
    assert submitted() == "none"
    _write_key_file(KEY.encode() + b"\n")
    assert submitted() == "KEY"
    monkeypatch.setenv(VARIABLE, OTHER_KEY)
    assert submitted() == "OTHER_KEY"
    # an empty variable supplies no key, and the saved key is used
    monkeypatch.setenv(VARIABLE, "")
    assert submitted() == "KEY"

    # the package-level functions apply the same precedence
    monkeypatch.setenv(VARIABLE, OTHER_KEY)
    bellman_matsya.submit_job(session=session_id, target="stage")
    monkeypatch.delenv(VARIABLE)
    bellman_matsya.submit_job(session=session_id, target="stage")
    _key_file().unlink()
    bellman_matsya.submit_job(session=session_id, target="stage")
    assert [key for _, key in _sent(stand_in)] == ["OTHER_KEY", "KEY", "none"]

    # the constructor reads neither the variable nor the file
    _write_key_file(KEY.encode() + b"\n")
    monkeypatch.setenv(VARIABLE, OTHER_KEY)
    MatsyaClient(TOKEN, stand_in.url).submit_job(session=session_id, target="stage")
    MatsyaClient(TOKEN, stand_in.url, anthropic_api_key=None).submit_job(session=session_id, target="stage")
    MatsyaClient(TOKEN, stand_in.url, anthropic_api_key=KEY).submit_job(session=session_id, target="stage")
    assert [key for _, key in _sent(stand_in)] == ["none", "none", "KEY"]


@pytest.mark.parametrize("name", sorted(INVALID))
def test_a_selected_key_a_header_cannot_carry_is_refused_by_its_source_before_any_request(
    stand_in, run, monkeypatch, name
) -> None:
    """Through the variable and through the saved file, one sentence that
    names the source and the remedy, exit status 1 and no traceback, before
    the client is built, for a command that would send the key and for one
    that would not; through the constructor and the package-level
    functions, `ValueError` with the sentence of §2.2. No message shows the
    key."""
    bad = INVALID[name]
    monkeypatch.setenv(VARIABLE, bad)
    for arguments in (("index",), ("job", "submit", "--session", "0" * 32, "--target", "stage")):
        status, out, err = run(*arguments)
        _no_key_in(out + err, "the refusal of the variable's key")
        assert (status, out, err) == (1, "", VARIABLE_REFUSAL), arguments
    with pytest.raises(ValueError) as refused:
        bellman_matsya.index()
    assert str(refused.value) == CONSTRUCTOR_REFUSAL
    monkeypatch.delenv(VARIABLE)

    path = _write_key_file(bad.encode("utf-8"))
    for arguments in (("index",), ("ask", "0" * 32, "What is a stage?")):
        status, out, err = run(*arguments)
        _no_key_in(out + err, "the refusal of the saved key")
        assert (status, out, err) == (1, "", _file_refusal(path)), arguments
    with pytest.raises(ValueError) as refused:
        bellman_matsya.search("stage")
    assert str(refused.value) == CONSTRUCTOR_REFUSAL

    with pytest.raises(ValueError) as refused:
        MatsyaClient(TOKEN, stand_in.url, anthropic_api_key=bad)
    _no_key_in(str(refused.value), "the constructor's refusal")
    assert str(refused.value) == CONSTRUCTOR_REFUSAL and refused.value.__cause__ is None
    assert stand_in.requests == []


def test_a_key_whose_only_fault_is_surrounding_whitespace_is_sent_without_it(stand_in, run, monkeypatch) -> None:
    session_id = MatsyaClient(TOKEN, stand_in.url).new_session("a household")["id"]
    MatsyaClient(TOKEN, stand_in.url).add_entry(session_id, "A household saves.")
    stand_in.requests.clear()
    for name, value in sorted(SURROUNDED.items()):
        monkeypatch.setenv(VARIABLE, value)
        status, _, err = run("job", "submit", "--session", session_id, "--target", "stage")
        assert (status, err) == (0, ""), name
        monkeypatch.delenv(VARIABLE)
        _write_key_file(value.encode())
        status, _, err = run("job", "submit", "--session", session_id, "--target", "stage")
        assert (status, err) == (0, ""), name
        _key_file().unlink()
        MatsyaClient(TOKEN, stand_in.url, anthropic_api_key=value).submit_job(session=session_id, target="stage")
        assert _sent(stand_in) == [("POST /v1/model-iterations", "KEY")] * 3, name


# ---------------------------------------------------------------------------
# §2.3: the requests that carry the key


def _carries_key(request: dict) -> bool:
    """Whether a request is one of the three that carry a selected key: a
    job submission, a conversation turn, and a `user` entry that names
    `replies_to` (AMD-MAT-021 §2.3)."""
    route = _route(request)
    if route in ("POST /v1/model-iterations", "POST /v1/sessions/<id>/turns"):
        return True
    body = request["body"] if isinstance(request["body"], dict) else {}
    return (
        route == "POST /v1/sessions/<id>/entries"
        and body.get("kind", "user") == "user"
        and body.get("replies_to") is not None
    )


def test_only_a_job_a_turn_and_a_reply_carry_the_key_with_the_matsya_token(
    stand_in, run, monkeypatch, tmp_path
) -> None:
    """Every command and function that sends a request, run with a selected
    key: the key travels, beside the Matsya token, with a job submission, a
    turn, and a `user` entry with `replies_to`, and with no other request,
    in no body, path or query, and in no other header."""
    monkeypatch.setenv(VARIABLE, KEY)
    model = _text(tmp_path, "model.md", "A household saves out of cash on hand.\n")
    reply = _text(tmp_path, "reply.md", "The shock is log-normal.\n")
    note = _text(tmp_path, "note.md", "The household also holds a pension.\n")
    outputs = []

    def command(*arguments: str) -> str:
        status, out, err = run(*arguments)
        outputs.append(out + err)
        assert status == 0, (arguments, _named(err))
        return out

    out = command("job", "submit", str(model), "--target", "stage")
    session_id = _identifier(r"^Session ([0-9a-f]{32}): model$", out)
    job_id = _identifier(r"^Job ([0-9a-f]{32}): queued$", out)
    command("job", "wait", job_id, "--interval", "0")
    command("job", "status", job_id)
    command("session", "show", session_id)
    question = next(e["number"] for e in stand_in.sessions[session_id]["entries"] if e["kind"] == "question")
    out = command("session", "add", session_id, str(reply), "--replies-to", str(question))
    attempt = _identifier(r"^The reply started .*: job ([0-9a-f]{32})$", out)
    command("job", "wait", attempt, "--interval", "0")
    command("session", "add", session_id, str(note))
    command("session", "add", session_id, str(note), "--kind", "paper", "--replies-to", "1")
    command("ask", session_id, "What does a stage file name?", "--interval", "0")
    answer = len(stand_in.sessions[session_id]["entries"])
    command("session", "add", session_id, "--kind", "acceptance", "--replies-to", str(answer))
    command("ask", session_id, "Submit this as a job.", "--follow", str(tmp_path / "followed"), "--interval", "0")
    command("session", "select", session_id, attempt)
    command("session", "select", session_id, "--none")
    command("index")
    command("search", "stage file")
    command("job", "files", attempt, str(tmp_path / "files"))
    command("job", "export", attempt, str(tmp_path / "export"))
    command("job", "submit", str(model), "--no-session", "--target", "stage")
    queued = _identifier(r"^Job ([0-9a-f]{32}): queued$", command("job", "submit", "--session", session_id, "--target", "stage"))
    command("job", "cancel", queued)
    folder = tmp_path / "project"
    folder.mkdir()
    _text(folder, "economics.md", "A household saves.\n")
    monkeypatch.chdir(folder)
    command("project", "init")
    stand_in.next_ends.append("converged")
    submitted = _identifier(r"^Job ([0-9a-f]{32}): queued$", command("project", "submit"))
    command("job", "wait", submitted, "--interval", "0")
    command("project", "status")
    command("project", "pull")
    _text(folder, "economics.md", "A household saves and works.\n")
    command("project", "submit")

    # the package-level functions and the client's methods
    with_key = MatsyaClient(TOKEN, stand_in.url, anthropic_api_key=KEY)
    bellman_matsya.index()
    bellman_matsya.start_job(model, target="stage")
    bellman_matsya.add_entry(session_id, "A firm hires.")
    bellman_matsya.add_entry(session_id, "Yes.", replies_to=1)
    bellman_matsya.ask(session_id, "What is a perch?", interval=0)
    with_key.passage("5" * 64)
    with_key.start_job(model, no_session=True, target="stage")
    with_key.wait_turn(session_id, stand_in.sessions[session_id]["turns"][0], interval=0)

    requests = list(stand_in.requests)
    keyed = {_route(request) for request in requests if _key_sent(request) != "none"}
    assert keyed == {
        "POST /v1/model-iterations",
        "POST /v1/sessions/<id>/turns",
        "POST /v1/sessions/<id>/entries",
    }
    for request in requests:
        expected = "KEY" if _carries_key(request) else "none"
        assert (_route(request), _key_sent(request)) == (_route(request), expected), request["body"]
        if expected == "KEY":
            assert request["headers"]["Authorization"] == f"Bearer {TOKEN}"
        other_headers = {name: value for name, value in request["headers"].items() if name.lower() != KEY_HEADER}
        _no_key_in(json.dumps(other_headers) + request["path"] + json.dumps(request["body"]), "a request")
    assert sum(_carries_key(request) for request in requests) >= 10
    for text in outputs:
        _no_key_in(text, "the output of a command")


def test_the_key_is_never_sent_without_the_matsya_token(stand_in) -> None:
    client = MatsyaClient("", stand_in.url, anthropic_api_key=KEY)
    with pytest.raises(MatsyaError) as refused:
        client.submit_job(source_text="A household saves.", target="stage")
    assert refused.value.status == 401
    ((request,),) = [stand_in.requests]
    assert _key_sent(request) == "none"
    assert "authorization" not in {name.lower() for name in request["headers"]}


# ---------------------------------------------------------------------------
# §2.4: where the key may be sent


@pytest.fixture
def at_remote(stand_in, monkeypatch: pytest.MonkeyPatch):
    """The stand-in at `REMOTE`, a plain-HTTP address whose host is not a
    loopback host: the commands' address is `REMOTE`, and each request
    addressed to it is sent to the stand-in instead, so that a command that
    sends no key is seen to proceed and no request leaves the machine."""
    original = urllib.request.OpenerDirector.open

    def readdressed(self, request, *arguments, **options):
        if isinstance(request, urllib.request.Request) and request.full_url.startswith(REMOTE):
            request.full_url = stand_in.url + request.full_url[len(REMOTE) :]
        return original(self, request, *arguments, **options)

    monkeypatch.setattr(urllib.request.OpenerDirector, "open", readdressed)
    monkeypatch.setenv("BELLMAN_MATSYA_SERVER", REMOTE)
    return stand_in


def test_at_a_plain_http_address_work_with_the_key_is_refused_before_its_first_request(
    at_remote, run, monkeypatch, tmp_path
) -> None:
    """`job submit` in every form, `session add` of a `user` entry with
    `--replies-to`, `ask` and `project submit` are refused with the
    sentence of §2.4 and exit status 1 before their first request, so that
    no session, entry, job or turn is created and no digest is recorded,
    and the same holds for the functions behind them; a command that sends
    no key proceeds at that address with the Matsya token alone."""
    stand_in = at_remote
    model = _text(tmp_path, "model.md", "A household saves.\n")
    reply = _text(tmp_path, "reply.md", "The shock is log-normal.\n")
    refusal = "Error: " + _destination_refusal(REMOTE) + "\n"

    # without a key, the work is sent, and the session is kept for what follows
    status, out, _ = run("job", "submit", str(model), "--target", "stage")
    session_id = _identifier(r"^Session ([0-9a-f]{32}): model$", out)
    job_id = _identifier(r"^Job ([0-9a-f]{32}): queued$", out)
    assert status == 0 and run("job", "wait", job_id, "--interval", "0")[0] == 0
    stand_in.requests.clear()

    monkeypatch.setenv(VARIABLE, KEY)
    sessions, jobs = len(stand_in.sessions), len(stand_in.jobs)
    entries = list(stand_in.sessions[session_id]["entries"])
    for arguments in (
        ("job", "submit", str(model), "--target", "stage"),
        ("job", "submit", str(model), "--name", "another", "--target", "stage"),
        ("job", "submit", str(model), "--session", session_id, "--target", "stage"),
        ("job", "submit", str(model), "--no-session", "--target", "stage"),
        ("job", "submit", "--session", session_id, "--target", "stage"),
        ("session", "add", session_id, str(reply), "--replies-to", "2"),
        ("ask", session_id, "What does a stage file name?"),
        ("ask", session_id, "Submit this as a job.", "--follow", str(tmp_path / "followed")),
    ):
        status, out, err = run(*arguments)
        _no_key_in(out + err, "the refusal of a plain-HTTP address")
        assert (status, out, err) == (1, "", refusal), arguments
    assert stand_in.requests == [] and (len(stand_in.sessions), len(stand_in.jobs)) == (sessions, jobs)
    assert stand_in.sessions[session_id]["entries"] == entries

    # the commands that send no key proceed there, with the Matsya token alone
    for arguments in (
        ("index",),
        ("search", "stage file"),
        ("job", "status", job_id),
        ("job", "export", job_id, str(tmp_path / "export")),
        ("session", "show", session_id),
        ("session", "add", session_id, str(reply)),
        ("session", "add", session_id, str(reply), "--kind", "paper", "--replies-to", "2"),
    ):
        status, out, err = run(*arguments)
        _no_key_in(out + err, "the output of a command that sends no key")
        assert (status, err) == (0, ""), arguments
    assert {key for _, key in _sent(stand_in)} == {"none"}

    # a project folder: init sends no key; submit is refused before it
    # appends economics.md or records its digest
    folder = tmp_path / "project"
    folder.mkdir()
    _text(folder, "economics.md", "A household saves.\n")
    monkeypatch.chdir(folder)
    assert run("project", "init")[0] == 0
    held = (folder / project.PROJECT_FILE).read_bytes()
    project_session = json.loads(held)["session"]
    assert json.loads(held)["server"] == REMOTE
    _text(folder, "economics.md", "A household saves and works.\n")
    _sent(stand_in)
    status, out, err = run("project", "submit")
    assert (status, out, err) == (1, "", refusal)
    assert stand_in.requests == [] and (folder / project.PROJECT_FILE).read_bytes() == held
    assert len(stand_in.sessions[project_session]["entries"]) == 1

    # the functions behind the commands; constructing the client is not refused
    client = MatsyaClient(TOKEN, REMOTE, anthropic_api_key=KEY)
    for call in (
        lambda: client.start_job(model, target="stage"),
        lambda: client.start_job(model, no_session=True, target="stage"),
        lambda: client.submit_job(session=session_id, target="stage"),
        lambda: client.add_entry(session_id, "Yes.", replies_to=2),
        lambda: client.ask(session_id, "What is a stage?", interval=0),
        lambda: project.submit(client, folder),
        lambda: bellman_matsya.start_job(model, target="stage"),
        lambda: bellman_matsya.add_entry(session_id, "Yes.", replies_to=2),
    ):
        with pytest.raises(MatsyaError) as refused:
            call()
        assert str(refused.value) == _destination_refusal(REMOTE)
    assert stand_in.requests == [] and (folder / project.PROJECT_FILE).read_bytes() == held
    assert client.index()["index_digest"] and client.add_entry(session_id, "A firm hires.")["entry"]
    assert client.job(job_id)["id"] == job_id
    assert {key for _, key in _sent(stand_in)} == {"none"}


class _Recording(BaseHTTPRequestHandler):
    """A server that keeps each request's method, path and headers in
    `server.seen`. With `server.location` set, a request for any other path
    is answered 303 with that address; every other request is answered
    `server.status` with `server.answer` in JSON."""

    def log_message(self, format: str, *args: object) -> None:
        """The tests print no request log."""

    def _reply(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        if length:
            self.rfile.read(length)
        self.server.seen.append({"method": self.command, "path": self.path, "headers": dict(self.headers)})
        location = self.server.location
        redirect = location is not None and self.path != urllib.parse.urlsplit(location).path
        data = json.dumps(self.server.answer).encode()
        self.send_response(303 if redirect else self.server.status)
        if redirect:
            self.send_header("Location", location)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    do_GET = do_POST = _reply


class _Malformed(BaseHTTPRequestHandler):
    """A server that reads a request and answers with the raw text
    `server.raw`, in which `{key}` and `{token}` are replaced by the
    personal key and the Matsya token the request carried, as a broken or
    hostile service might answer: a status line or a body that urllib
    cannot read."""

    def log_message(self, format: str, *args: object) -> None:
        """The tests print no request log."""

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        if length:
            self.rfile.read(length)
        key = self.headers.get(KEY_HEADER, "")
        token = self.headers.get("Authorization", "").partition(" ")[2]
        self.wfile.write(self.server.raw.format(key=key, token=token).encode("latin-1"))


class _Server:
    """A `_Recording` server, or a server of another handler, on the
    loopback address, with HTTPS when a certificate and its private key are
    given."""

    def __init__(
        self,
        status: int = 200,
        answer: object = None,
        tls: tuple[Path, Path] | None = None,
        handler: type[BaseHTTPRequestHandler] = _Recording,
    ) -> None:
        self.http = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.http.seen, self.http.status, self.http.location = [], status, None
        self.http.answer = {} if answer is None else answer
        if tls is not None:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(*tls)
            self.http.socket = context.wrap_socket(self.http.socket, server_side=True)
        scheme = "https" if tls else "http"
        self.url = f"{scheme}://127.0.0.1:{self.http.server_address[1]}"
        self.seen = self.http.seen
        self.thread = threading.Thread(
            target=self.http.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True
        )
        self.thread.start()

    def stop(self) -> None:
        self.http.shutdown()
        self.http.server_close()
        self.thread.join(5)


def test_a_loopback_address_is_reached_past_any_proxy(stand_in, run, monkeypatch) -> None:
    """With `http_proxy` set and `no_proxy` unset, a request with the key to
    `http://127.0.0.1:<port>` or `http://localhost:<port>`, and a request
    with the Matsya token alone, reach the service and no proxy, although
    urllib's own opener sends such a request to the proxy."""
    proxy = _Server(status=502, answer={"detail": "the proxy"})
    try:
        for name in ("NO_PROXY", "no_proxy"):
            monkeypatch.delenv(name, raising=False)
        for name in ("http_proxy", "HTTP_PROXY"):
            monkeypatch.setenv(name, proxy.url)
        with pytest.raises(urllib.error.HTTPError):
            urllib.request.build_opener().open(stand_in.url + "/healthz", timeout=10)
        assert [seen["path"] for seen in proxy.seen] == [stand_in.url + "/healthz"]
        proxy.seen.clear()

        port = stand_in.url.rsplit(":", 1)[1]
        for address in (stand_in.url, f"http://localhost:{port}"):
            client = MatsyaClient(TOKEN, address, anthropic_api_key=KEY)
            assert client.submit_job(source_text="A household saves.", target="stage")["credential_source"] == "client"
            assert MatsyaClient(TOKEN, address).index()["index_digest"]
        monkeypatch.setenv(VARIABLE, KEY)
        status, _, err = run("job", "submit", "--session", "0" * 32, "--target", "stage")
        assert (status, err) == (1, "Error: The service refused the request (404): Session not found.\n")
        assert proxy.seen == []
        assert _sent(stand_in) == [
            ("POST /v1/model-iterations", "KEY"),
            ("GET /v1/index", "none"),
            ("POST /v1/model-iterations", "KEY"),
            ("GET /v1/index", "none"),
            ("POST /v1/model-iterations", "KEY"),
        ]
    finally:
        proxy.stop()


@pytest.fixture
def certificate(tmp_path: Path) -> tuple[Path, Path]:
    """A self-signed certificate for `127.0.0.1` and `localhost`, made at
    the test's time with `openssl`, and its private key."""
    openssl = shutil.which("openssl")
    if openssl is None:
        pytest.skip("openssl is not installed")
    folder = tmp_path / "tls"
    folder.mkdir()
    made = subprocess.run(
        [
            openssl, "req", "-x509", "-newkey", "rsa:2048", "-nodes",
            "-keyout", str(folder / "key.pem"), "-out", str(folder / "certificate.pem"),
            "-days", "1", "-subj", "/CN=localhost",
            "-addext", "subjectAltName=DNS:localhost,IP:127.0.0.1",
        ],
        capture_output=True,
        check=False,
    )
    if made.returncode != 0:
        pytest.skip("openssl could not make a self-signed certificate")
    return folder / "certificate.pem", folder / "key.pem"


def test_https_requires_a_valid_certificate_whatever_the_process_has_set(
    stand_in, certificate, monkeypatch
) -> None:
    """In a process that has rebound `ssl._create_default_https_context` to
    `ssl._create_unverified_context` before the client is built, a request
    to a service with a self-signed certificate fails verification and is
    reported with its reason, and no request reaches the service; urllib's
    own opener, which reads the rebound default, sends one. Once the
    certificate is trusted, the request with the key is sent."""
    server = _Server(answer={"id": "0" * 32, "state": "queued", "credential_source": "client"}, tls=certificate)
    try:
        monkeypatch.setattr(ssl, "_create_default_https_context", ssl._create_unverified_context)
        client = MatsyaClient(TOKEN, server.url, anthropic_api_key=KEY)
        with pytest.raises(MatsyaError) as refused:
            client.submit_job(source_text="A household saves.", target="stage")
        message = str(refused.value)
        _no_key_in(message, "the report of a failed verification")
        assert message.startswith(f"The Matsya service at {server.url} could not be reached: ")
        assert "CERTIFICATE_VERIFY_FAILED" in message and TOKEN not in message
        assert server.seen == []
        with urllib.request.build_opener().open(server.url + "/v1/index", timeout=10) as answer:
            assert answer.status == 200
        assert [seen["path"] for seen in server.seen] == ["/v1/index"]

        server.seen.clear()
        monkeypatch.setenv("SSL_CERT_FILE", str(certificate[0]))
        trusted = MatsyaClient(TOKEN, server.url, anthropic_api_key=KEY)
        assert trusted.submit_job(source_text="A household saves.", target="stage")["credential_source"] == "client"
        assert [(seen["method"], _key_sent(seen)) for seen in server.seen] == [("POST", "KEY")]

        # a redirect from HTTPS to HTTP at the same host and port is refused
        # before anything is sent to the plain-HTTP address
        downgraded = server.url.replace("https://", "http://", 1)
        server.http.location = downgraded + "/v1/index"
        with pytest.raises(MatsyaError) as refused:
            trusted.submit_job(source_text="A household saves.", target="stage")
        assert str(refused.value).startswith(
            f"The Matsya service at {server.url} redirected the request to {downgraded}; "
        )
        assert [(seen["method"], seen["path"]) for seen in server.seen[1:]] == [("POST", "/v1/model-iterations")]
    finally:
        server.stop()


def test_a_raised_debug_level_prints_neither_secret(stand_in, monkeypatch, capsys) -> None:
    """With `http.client.HTTPConnection.debuglevel` set to 1 before the
    client is built, the client's requests print nothing, while urllib's own
    opener prints the headers it sends."""
    monkeypatch.setattr(http.client.HTTPConnection, "debuglevel", 1)
    client = MatsyaClient(TOKEN, stand_in.url, anthropic_api_key=KEY)
    client.submit_job(source_text="A household saves.", target="stage")
    client.index()
    printed = capsys.readouterr()
    _no_key_in(printed.out + printed.err, "the debugging output")
    assert TOKEN not in printed.out + printed.err
    assert printed.out == "" and printed.err == ""
    # the control: urllib's own opener, which reads the process's setting
    # from Python 3.12 (before it, the level of its handlers is 0 unless
    # given), prints the headers it sends
    if urllib.request.HTTPHandler()._debuglevel == 1:
        request = urllib.request.Request(stand_in.url + "/healthz", headers={"X-Marker": "printed-marker"})
        with urllib.request.build_opener().open(request, timeout=10):
            pass
        assert "printed-marker" in capsys.readouterr().out


def test_a_redirect_moves_no_secret_to_another_origin(stand_in) -> None:
    """A request with the key that the service redirects to another port
    is refused before anything is sent there; the redirect handler
    compares header names without regard to case and refuses a move from
    HTTPS to HTTP; a redirect to the same origin is followed, and one of a
    request with neither secret is followed anywhere."""
    accepted = {"id": "0" * 32, "state": "queued", "credential_source": "client"}
    server = _Server(answer=accepted)
    try:
        server.http.location = stand_in.url + "/v1/index"
        client = MatsyaClient(TOKEN, server.url, anthropic_api_key=KEY)
        with pytest.raises(MatsyaError) as refused:
            client.submit_job(source_text="A household saves.", target="stage")
        _no_key_in(str(refused.value), "the refusal of a redirect")
        assert str(refused.value) == (
            f"The Matsya service at {server.url} redirected the request to {stand_in.url}; the client "
            "follows a redirect only to the same scheme, host and port, so that the Matsya token and "
            "the personal Anthropic key are sent nowhere else."
        )
        # the key reached the configured service, and nothing reached the other
        assert stand_in.requests == [] and [_key_sent(seen) for seen in server.seen] == ["KEY"]

        # the same origin: followed, with both secrets
        server.http.location = "/v1/moved"
        assert client.submit_job(source_text="A household saves.", target="stage") == accepted
        assert [(seen["method"], seen["path"], _key_sent(seen)) for seen in server.seen[1:]] == [
            ("POST", "/v1/model-iterations", "KEY"),
            ("GET", "/v1/moved", "KEY"),
        ]
    finally:
        server.stop()

    handler = _SameHostRedirects(lambda text: text)
    for headers, there in (
        ({"bellman-matsya-anthropic-key": KEY}, "https://other.example.invalid/v1/index"),
        ({"BELLMAN-MATSYA-ANTHROPIC-KEY": KEY}, "http://matsya.example.invalid/v1/index"),
        ({"authorization": f"Bearer {TOKEN}"}, "http://matsya.example.invalid/v1/index"),
    ):
        request = urllib.request.Request("https://matsya.example.invalid/v1/index")
        request.headers = dict(headers)
        with pytest.raises(MatsyaError) as refused:
            handler.redirect_request(request, io.BytesIO(), 302, "Found", {}, there)
        _no_key_in(str(refused.value), "the refusal of a redirect")
    request = urllib.request.Request("https://matsya.example.invalid/v1/index")
    followed = handler.redirect_request(request, io.BytesIO(), 302, "Found", {}, "http://other.example.invalid/x")
    assert followed.full_url == "http://other.example.invalid/x"


# ---------------------------------------------------------------------------
# §2.5: what the client shows


def _session_job_awaiting_a_reply(run, stand_in, tmp_path, file_name: str = "model.md") -> tuple[str, str, int]:
    """A session whose job, submitted with the selected credential, ended
    with a question: the session, the job and the question's entry."""
    model = _text(tmp_path, file_name, "A household saves.\n")
    status, out, err = run("job", "submit", str(model), "--target", "stage")
    assert status == 0, _named(err)
    session_id = _identifier(r"^Session ([0-9a-f]{32}): ", out)
    job_id = _identifier(r"^Job ([0-9a-f]{32}): queued$", out)
    run("job", "wait", job_id, "--interval", "0")
    question = next(e["number"] for e in stand_in.sessions[session_id]["entries"] if e["kind"] == "question")
    return session_id, job_id, question


def test_the_credential_line_follows_new_work_the_service_ran_with_the_key(
    stand_in, run, monkeypatch, tmp_path
) -> None:
    monkeypatch.setenv(VARIABLE, KEY)
    model = _text(tmp_path, "model.md", "A household saves.\n")

    # job submit, in its three forms
    status, out, err = run("job", "submit", str(model), "--target", "stage")
    session_id = _identifier(r"^Session ([0-9a-f]{32}): model$", out)
    job_id = _identifier(r"^Job ([0-9a-f]{32}): queued$", out)
    assert (status, err) == (0, "")
    assert out.splitlines() == [
        f"Session {session_id}: model",
        f"Entry 1: the text of {model}",
        f"Job {job_id}: queued",
        f"Follow it with: bellman-matsya job wait {job_id}",
        f"The session, where the job's questions and your replies are kept: bellman-matsya session show {session_id}",
        CREDENTIAL,
    ]
    for arguments in (
        ("job", "submit", str(model), "--no-session", "--target", "stage"),
        ("job", "submit", "--session", session_id, "--target", "stage"),
    ):
        status, out, err = run(*arguments)
        assert (status, err, out.splitlines()[-1]) == (0, "", CREDENTIAL), arguments

    # job status and job wait name the credential of a job run with a key
    status, out, _ = run("job", "status", job_id)
    assert out.splitlines() == [
        "model · stage · job 1 · queued",
        f"Job {job_id}: queued",
        CREDENTIAL,
    ]
    status, out, _ = run("job", "wait", job_id, "--interval", "0")
    assert _final(out)[-1] == CREDENTIAL
    question = next(e["number"] for e in stand_in.sessions[session_id]["entries"] if e["kind"] == "question")

    # a reply that schedules an attempt, which records its own credential
    reply = _text(tmp_path, "reply.md", "The shock is log-normal.\n")
    status, out, err = run("session", "add", session_id, str(reply), "--replies-to", str(question))
    attempt = _identifier(r"^The reply started .*: job ([0-9a-f]{32})$", out)
    assert (status, err, out.splitlines()[-1]) == (0, "", CREDENTIAL)
    # a reply that schedules nothing, and an entry that carries no key, add no line
    status, out, _ = run("session", "add", session_id, str(reply), "--replies-to", "1")
    assert status == 0 and CREDENTIAL not in out
    status, out, _ = run("session", "add", session_id, str(reply))
    assert status == 0 and CREDENTIAL not in out

    # ask, and with --follow the job the turn started, run with the same key:
    # the turn's line follows the turn, and the job's line its report
    status, out, err = run("ask", session_id, "What does a stage file name?", "--interval", "0")
    assert (status, err) == (0, "") and ANSWER in _final(out) and _final(out)[-1] == CREDENTIAL
    folder = tmp_path / "followed"
    status, out, err = run("ask", session_id, "Submit this as a job.", "--follow", str(folder), "--interval", "0")
    assert (status, err) == (0, "")
    lines = _final(out)
    first = lines.index(CREDENTIAL)
    second = lines.index(CREDENTIAL, first + 1)
    assert "started from version" in lines[first - 1] and lines.count(CREDENTIAL) == 2
    assert lines[second - 1].startswith("Write the model folder") and lines[second + 1].startswith("Wrote ")

    # project submit
    project_folder = tmp_path / "project"
    project_folder.mkdir()
    _text(project_folder, "economics.md", "A household saves.\n")
    monkeypatch.chdir(project_folder)
    assert run("project", "init")[0] == 0
    status, out, err = run("project", "submit")
    assert (status, err, out.splitlines()[-1]) == (0, "", CREDENTIAL)

    # a job run with the service's key adds no line to job status or job wait
    monkeypatch.delenv(VARIABLE)
    status, out, _ = run("job", "submit", str(model), "--no-session", "--target", "stage")
    service_job = _identifier(r"^Job ([0-9a-f]{32}): queued$", out)
    assert status == 0 and CREDENTIAL not in out
    assert CREDENTIAL not in run("job", "status", service_job)[1]
    assert CREDENTIAL not in run("job", "wait", service_job, "--interval", "0")[1]
    # job status names the credential of a job run with a key to every user
    assert run("job", "status", attempt)[1].splitlines()[-1] == CREDENTIAL


@pytest.mark.parametrize("treatment", ["older", "ignore"])
def test_work_the_service_accepted_under_its_own_key_is_reported_with_exit_status_1(
    stand_in, run, monkeypatch, tmp_path, treatment
) -> None:
    """A service built before the amendment ignores the header and reports
    no `credential_source`; a service that reports `service` for work sent
    with a key is treated alike. The command prints its usual lines, then
    the sentence of §2.5 on standard error, with the command that cancels a
    job, and exits with status 1."""
    model = _text(tmp_path, "model.md", "A household saves.\n")
    reply = _text(tmp_path, "reply.md", "The shock is log-normal.\n")
    session_id, _, question = _session_job_awaiting_a_reply(run, stand_in, tmp_path, "prepared.md")
    monkeypatch.setenv(VARIABLE, KEY)
    stand_in.personal_keys = treatment

    status, out, err = run("job", "submit", str(model), "--target", "stage")
    job_id = _identifier(r"^Job ([0-9a-f]{32}): queued$", out)
    new_session = _identifier(r"^Session ([0-9a-f]{32}): model$", out)
    _no_key_in(out + err, "the report of work under the service's key")
    assert status == 1
    assert out.splitlines()[-1] == (
        f"The session, where the job's questions and your replies are kept: bellman-matsya session show {new_session}"
    )
    assert err == _own_key(stand_in.url, "job", job_id) + f"Cancel it with: bellman-matsya job cancel {job_id}\n"

    status, out, err = run("job", "submit", "--session", session_id, "--target", "stage", "--json")
    held = json.loads(out)
    assert status == 1 and held.get("credential_source") in (None, "service")
    assert err == _own_key(stand_in.url, "job", held["id"]) + f"Cancel it with: bellman-matsya job cancel {held['id']}\n"

    status, out, err = run("session", "add", session_id, str(reply), "--replies-to", str(question))
    attempt = _identifier(r"^The reply started .*: job ([0-9a-f]{32})$", out)
    assert status == 1 and CREDENTIAL not in out
    assert err == _own_key(stand_in.url, "job", attempt) + f"Cancel it with: bellman-matsya job cancel {attempt}\n"

    # a question: the turn is printed; with --follow the usual lines include
    # the job the turn started and its folder, and the report follows them
    status, out, err = run("ask", session_id, "What does a stage file name?", "--interval", "0")
    turn_id = stand_in.sessions[session_id]["turns"][-1]
    assert (status, err) == (1, _own_key(stand_in.url, "turn", turn_id)) and ANSWER in _final(out)
    folder = tmp_path / "followed"
    status, out, err = run("ask", session_id, "Submit this as a job.", "--follow", str(folder), "--interval", "0")
    turn_id = stand_in.sessions[session_id]["turns"][-1]
    assert (status, err) == (1, _own_key(stand_in.url, "turn", turn_id))
    assert (folder / "report.md").is_file() and CREDENTIAL not in out
    assert _final(out)[-1] == "  record.json"

    # a wait the user stops still reports the work under the service's key
    def stopped(*arguments: object, **options: object) -> None:
        raise KeyboardInterrupt

    with monkeypatch.context() as patched:
        patched.setattr(MatsyaClient, "wait_job", stopped)
        status, out, err = run(
            "ask", session_id, "Submit this as a job.", "--follow", str(tmp_path / "stopped"), "--interval", "0"
        )
    turn_id = stand_in.sessions[session_id]["turns"][-1]
    assert status == 130 and err.startswith("\nStopped waiting. The job goes on running on the service: ")
    assert err.endswith(_own_key(stand_in.url, "turn", turn_id))

    # a wait that fails, or a folder that cannot be written, after the turn
    # was accepted: the error, then the report, with exit status 1
    unwritable = tmp_path / "unwritable"

    def unreachable(*arguments: object, **options: object) -> None:
        raise MatsyaError("The Matsya service at x could not be reached: refused.")

    def denied(*arguments: object, **options: object) -> None:
        raise PermissionError(13, "Permission denied", str(unwritable))

    for method, failure, error in (
        ("wait_job", unreachable, "Error: The Matsya service at x could not be reached: refused.\n"),
        ("job_files", denied, f"Error: Permission denied: {unwritable}\n"),
    ):
        with monkeypatch.context() as patched:
            patched.setattr(MatsyaClient, method, failure)
            status, out, err = run(
                "ask", session_id, "Submit this as a job.", "--follow", str(tmp_path / method), "--interval", "0"
            )
        turn_id = stand_in.sessions[session_id]["turns"][-1]
        _no_key_in(out + err, "the report of work under the service's key after an error")
        assert (status, err) == (1, error + _own_key(stand_in.url, "turn", turn_id)), method

    project_folder = tmp_path / "project"
    project_folder.mkdir()
    _text(project_folder, "economics.md", "A household saves.\n")
    monkeypatch.chdir(project_folder)
    assert run("project", "init")[0] == 0
    status, out, err = run("project", "submit")
    submitted = _identifier(r"^Job ([0-9a-f]{32}): queued$", out)
    assert status == 1
    assert err == _own_key(stand_in.url, "job", submitted) + f"Cancel it with: bellman-matsya job cancel {submitted}\n"

    # without a key, nothing is checked
    monkeypatch.delenv(VARIABLE)
    status, out, err = run("job", "submit", str(model), "--target", "stage")
    assert (status, err) == (0, "") and CREDENTIAL not in out


def test_a_reply_without_a_key_to_a_job_run_with_one_is_refused_with_the_remedy(
    stand_in, run, monkeypatch, tmp_path
) -> None:
    """The service's refusal of §3.3 is printed with the sentence that says
    how a key is supplied; the session is unchanged; a reply with another
    personal key is accepted, and its repeated delivery, which starts no
    work, needs no key and reports no credential."""
    monkeypatch.setenv(VARIABLE, KEY)
    session_id, job_id, question = _session_job_awaiting_a_reply(run, stand_in, tmp_path)
    reply = _text(tmp_path, "reply.md", "The shock is log-normal.\n")
    monkeypatch.delenv(VARIABLE)
    entries = list(stand_in.sessions[session_id]["entries"])
    arguments = ("session", "add", session_id, str(reply), "--replies-to", str(question), "--delivery-id", "reply-1")
    assert run(*arguments) == (1, "", REPLY_REFUSAL)
    assert stand_in.sessions[session_id]["entries"] == entries
    assert stand_in.sessions[session_id]["awaiting_answer"] == job_id
    with pytest.raises(MatsyaError) as refused:
        MatsyaClient(TOKEN, stand_in.url).add_entry(session_id, "Yes.", replies_to=question)
    assert refused.value.status == 422 and "Error: " + str(refused.value) + "\n" == REPLY_REFUSAL

    monkeypatch.setenv(VARIABLE, OTHER_KEY)
    status, out, err = run(*arguments)
    assert (status, err, out.splitlines()[-1]) == (0, "", CREDENTIAL)
    assert [key for route, key in _sent(stand_in) if route.endswith("/entries")][-1] == "OTHER_KEY"
    monkeypatch.delenv(VARIABLE)
    status, out, err = run(*arguments)
    assert (status, err) == (0, "")
    assert out.splitlines() == [
        f"Session {session_id} already holds this delivery as entry {question + 1}; nothing was appended."
    ]


def test_an_answer_that_reports_a_repeated_delivery_is_not_new_work(stand_in, run, monkeypatch, tmp_path) -> None:
    """The credential of the attempt in `scheduled` is checked only when the
    answer of `session add` does not report a repeated delivery, even should
    a service name an attempt beside `repeated`."""
    monkeypatch.setenv(VARIABLE, KEY)
    attempt = "1" * 32
    answer = {
        "id": "0" * 32,
        "revision": 3,
        "entry": {"number": 3, "kind": "user"},
        "repeated": True,
        "scheduled": {"id": attempt, "status_url": f"/v1/model-iterations/{attempt}"},
    }
    monkeypatch.setattr(MatsyaClient, "add_entry", lambda self, *arguments, **options: answer)
    reply = _text(tmp_path, "reply.md", "The shock is log-normal.\n")
    status, out, err = run("session", "add", "0" * 32, str(reply), "--replies-to", "2")
    assert (status, err) == (0, "") and CREDENTIAL not in out
    answer["repeated"] = False
    status, out, err = run("session", "add", "0" * 32, str(reply), "--replies-to", "2")
    assert status == 1
    assert err == _own_key(stand_in.url, "job", attempt) + f"Cancel it with: bellman-matsya job cancel {attempt}\n"


def test_a_service_with_its_switch_off_refuses_the_key_and_creates_nothing(stand_in, run, monkeypatch, tmp_path) -> None:
    model = _text(tmp_path, "model.md", "A household saves.\n")
    monkeypatch.setenv(VARIABLE, KEY)
    stand_in.personal_keys = "refuse"
    status, out, err = run("job", "submit", str(model), "--no-session", "--target", "stage")
    assert (status, out) == (1, "")
    assert err == "Error: The service refused the request (403): This service does not accept a personal Anthropic key.\n"
    assert stand_in.jobs == {}


# ---------------------------------------------------------------------------
# §2.5 and §5 item 6: the key in messages, files, outputs and requests


def test_the_key_is_masked_in_every_message_the_client_composes(stand_in, run, monkeypatch, tmp_path) -> None:
    client = MatsyaClient(TOKEN, stand_in.url, anthropic_api_key=KEY)
    assert repr(client) == f"MatsyaClient(server_url={stand_in.url!r})"
    assert client._hidden(f"{TOKEN} and {KEY}.") == "<Matsya token> and <Anthropic API key>."
    stand_in.echo_personal_key = True
    with pytest.raises(MatsyaError) as refused:
        client.submit_job(source_text="A household saves.", target="stage")
    _no_key_in(str(refused.value) + refused.value.detail, "a refusal that echoes the key")
    assert str(refused.value) == (
        "The service refused the request (403): The personal Anthropic key <Anthropic API key> is refused."
    )
    assert refused.value.detail == "The personal Anthropic key <Anthropic API key> is refused"

    monkeypatch.setenv(VARIABLE, KEY)
    model = _text(tmp_path, "model.md", "A household saves.\n")
    status, out, err = run("job", "submit", str(model), "--target", "stage")
    _no_key_in(out + err, "the output of a refusal that echoes the key")
    assert (status, out) == (1, "")
    assert err.startswith(
        "Error: The service refused the request (403): The personal Anthropic key <Anthropic API key> is "
        "refused. Session "
    )


# answers that urllib cannot read, written from the personal key and the
# Matsya token the request carried, each with the end of the message the
# client composes for it; the names serve as the tests' identifiers
MALFORMED = {
    "a status code that is not a number": (
        "HTTP/1.1 2x0 The key {key} and the token {token} are not accepted here\r\n\r\n",
        "could not be used: the HTTP exchange failed (BadStatusLine).",
    ),
    "a status line without its protocol": (
        "{key} 200 OK\r\n\r\n",
        "could not be used: the HTTP exchange failed (BadStatusLine).",
    ),
    "an unknown protocol": (
        "HTTP/{key} 200 OK\r\n\r\n",
        "could not be used: the HTTP exchange failed (UnknownProtocol).",
    ),
    "an answer whose chunked body cannot be read": (
        "HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n{key}\r\n",
        "could not be used: the HTTP exchange failed (IncompleteRead).",
    ),
    "a refusal whose chunked body cannot be read": (
        "HTTP/1.1 400 Bad Request\r\nTransfer-Encoding: chunked\r\n\r\n{key}\r\n",
        "refused the request (400): Bad Request.",
    ),
}


@pytest.mark.parametrize("answer", sorted(MALFORMED))
def test_an_answer_urllib_cannot_read_is_reported_without_either_secret(answer, run, monkeypatch, tmp_path) -> None:
    """A service that answers with a status line or a chunked body that
    urllib cannot read, written from the secrets the request carried, is
    reported in a sentence the client composes, which names only the class
    of urllib's error: neither the Matsya token nor the personal key
    appears in the error's text, in its printed traceback or in the output
    of the command, which prints no traceback (AMD-MAT-021 §§2.5 and 4)."""
    raw, ending = MALFORMED[answer]
    server = _Server(handler=_Malformed)
    server.http.raw = raw
    try:
        with pytest.raises(MatsyaError) as refused:
            MatsyaClient(TOKEN, server.url, anthropic_api_key=KEY).submit_job(
                source_text="A household saves.", target="stage"
            )
        shown = str(refused.value) + repr(refused.value) + "".join(traceback.format_exception(refused.value))
        _no_key_in(shown, "the error of an answer urllib cannot read")
        assert TOKEN not in shown and str(refused.value).endswith(ending)

        _user(monkeypatch, tmp_path / "user-configuration", server.url, TOKEN)
        monkeypatch.setenv(VARIABLE, KEY)
        model = _text(tmp_path, "model.md", "A household saves.\n")
        status, out, err = run("job", "submit", str(model), "--no-session", "--target", "stage")
        _no_key_in(out + err, "the output of an answer urllib cannot read")
        assert TOKEN not in err and "Traceback" not in err
        assert (status, out) == (1, "") and err.startswith("Error: ") and err.endswith(ending + "\n")
    finally:
        server.stop()


@pytest.mark.parametrize("treatment", ["accept", "ignore"])
def test_an_identifier_that_repeats_the_key_is_masked_in_every_line_the_client_composes(
    stand_in, run, monkeypatch, tmp_path, treatment
) -> None:
    """A service that identifies the job, turn or attempt that a request
    with the key creates by that key, as a broken or hostile service might,
    and reports `credential_source` `client` or `service`: every line the
    command composes from its answers, on standard output and on standard
    error, the report of §2.5 and the sentence of a stopped wait among
    them, shows the identifier as `<Anthropic API key>`. With `--json`,
    standard output is the service's answer as it arrived, and standard
    error shows no key. The Python module's messages built from the
    identifier are masked alike (AMD-MAT-021 §2.5)."""
    first, _, first_question = _session_job_awaiting_a_reply(run, stand_in, tmp_path, "first.md")
    second, _, second_question = _session_job_awaiting_a_reply(run, stand_in, tmp_path, "second.md")
    model = _text(tmp_path, "model.md", "A household saves.\n")
    reply = _text(tmp_path, "reply.md", "The shock is log-normal.\n")
    project_folder = tmp_path / "project"
    project_folder.mkdir()
    _text(project_folder, "economics.md", "A household saves.\n")
    monkeypatch.chdir(project_folder)
    assert run("project", "init")[0] == 0
    monkeypatch.setenv(VARIABLE, KEY)
    stand_in.personal_keys = treatment
    stand_in.key_as_identifier = True
    expected = 0 if treatment == "accept" else 1

    def reported(kind: str) -> str:
        """What standard error holds after the command's usual lines:
        nothing for work run with the key, and otherwise the report of
        §2.5 with the identifier masked."""
        if treatment == "accept":
            return ""
        cancel = f"Cancel it with: bellman-matsya job cancel {MASK}\n" if kind == "job" else ""
        return _own_key(stand_in.url, kind, MASK) + cancel

    def command(kind: str, *arguments: str) -> list[str]:
        """Run a command that sends the key, check its exit status and its
        standard error, and return its standard output without the lines
        of progress."""
        status, out, err = run(*arguments)
        _no_key_in(out + err, "the output of a command")
        assert status == expected, arguments
        assert "".join(line + "\n" for line in _final(err)) == reported(kind), arguments
        return _final(out)

    lines = command("job", "job", "submit", str(model), "--target", "stage")
    assert lines[2:4] == [f"Job {MASK}: queued", f"Follow it with: bellman-matsya job wait {MASK}"]
    lines = command("job", "job", "submit", str(model), "--no-session", "--target", "stage")
    assert lines[:3] == [
        f"Job {MASK}: queued",
        f"Follow it with: bellman-matsya job wait {MASK}",
        f"The job has no session, and its questions stand in its record only: bellman-matsya job status {MASK}",
    ]
    assert ANSWER in command("turn", "ask", first, "What does a stage file name?", "--interval", "0")
    folder = tmp_path / "followed"
    lines = command("turn", "ask", first, "Submit this as a job.", "--follow", str(folder), "--interval", "0")
    assert any(line.endswith(f"({MASK}); follow it with: bellman-matsya job wait {MASK}") for line in lines)
    assert f"Write the model folder and its report with: bellman-matsya job files {MASK} <folder>" in lines
    lines = command("job", "session", "add", first, str(reply), "--replies-to", str(first_question))
    assert lines[1:3] == [
        f"The reply started the next preparation attempt of the job awaiting an answer: job {MASK}",
        f"Follow it with: bellman-matsya job wait {MASK}",
    ]
    lines = command("job", "project", "submit")
    assert f"Job {MASK}: queued" in lines and f"Follow it with: bellman-matsya job wait {MASK}" in lines

    # a wait the user stops: the sentence names the followed job masked
    def stopped(*arguments: object, **options: object) -> None:
        raise KeyboardInterrupt

    with monkeypatch.context() as patched:
        patched.setattr(MatsyaClient, "wait_job", stopped)
        status, out, err = run(
            "ask", first, "Submit this as a job.", "--follow", str(tmp_path / "stopped"), "--interval", "0"
        )
    _no_key_in(out + err, "the output of a stopped wait")
    assert (status, err) == (
        130,
        f"\nStopped waiting. The job goes on running on the service: bellman-matsya job wait {MASK}; "
        f"write its folder with: bellman-matsya job files {MASK} {tmp_path / 'stopped'}\n" + reported("turn"),
    )

    # with --json, standard output is the service's answer as it arrived
    for kind, arguments in (
        ("job", ("job", "submit", str(model), "--no-session", "--target", "stage", "--json")),
        ("turn", ("ask", second, "What does a stage file name?", "--interval", "0", "--json")),
        ("job", ("session", "add", second, str(reply), "--replies-to", str(second_question), "--json")),
        ("job", ("project", "submit", "--json")),
    ):
        status, out, err = run(*arguments)
        _no_key_in(err, "standard error under --json")
        assert status == expected and "".join(line + "\n" for line in _final(err)) == reported(kind), arguments
        # computed apart, so that a failure does not print the answer, which holds the key
        answered = isinstance(json.loads(out), dict)
        assert answered, arguments

    # the Python module: a message built from the identifier is masked
    client = MatsyaClient(TOKEN, stand_in.url, anthropic_api_key=KEY)
    job_id = client.submit_job(source_text="A household saves.", target="stage")["id"]
    for call in (
        lambda: client.wait_job(job_id, interval=0, timeout=0),
        lambda: client.job_files(job_id, tmp_path / "no-record"),
    ):
        with pytest.raises(MatsyaError) as refused:
            call()
        _no_key_in(str(refused.value), "an error of the Python module")
        assert str(refused.value).startswith(f"Job {MASK} ")


def test_the_key_appears_in_no_file_output_or_request_but_the_header_of_three_requests(
    stand_in, run, monkeypatch, tmp_path, caplog
) -> None:
    caplog.set_level(logging.DEBUG)
    monkeypatch.setenv(VARIABLE, KEY)
    work = tmp_path / "work"
    work.mkdir()
    session_id, job_id, question = _session_job_awaiting_a_reply(run, stand_in, work)
    reply = _text(work, "reply.md", "The shock is log-normal.\n")
    printed = []

    def command(*arguments: str) -> str:
        status, out, err = run(*arguments)
        printed.append(out + err)
        assert status == 0, arguments
        return out

    attempt = json.loads(
        command("session", "add", session_id, str(reply), "--replies-to", str(question), "--json")
    )["scheduled"]["id"]
    command("job", "wait", attempt, "--interval", "0", "--json")
    command("job", "status", job_id)
    command("job", "files", attempt, str(work / "files"))
    command("job", "export", attempt, str(work / "export"))
    command("job", "export", job_id, str(work / "export-json"), "--json")
    command("ask", session_id, "What does a stage file name?", "--interval", "0", "--json")
    command("ask", session_id, "Submit this as a job.", "--follow", str(work / "followed"), "--interval", "0")
    command("session", "show", session_id, "--json")
    command("job", "submit", str(reply), "--no-session", "--target", "stage", "--json")
    folder = work / "project"
    folder.mkdir()
    _text(folder, "economics.md", "A household saves.\n")
    monkeypatch.chdir(folder)
    command("project", "init")
    stand_in.next_ends.append("converged")
    submitted = json.loads(command("project", "submit", "--json"))["job"]["id"]
    command("job", "wait", submitted, "--interval", "0")
    command("project", "pull")
    command("project", "status")
    command()

    for text in printed:
        _no_key_in(text, "the output of a command")
    written = [path for path in tmp_path.rglob("*") if path.is_file()]
    assert any(path.name == "job.json" for path in written) and any(path.name == "project.json" for path in written)
    for path in written:
        _no_key_in(path.read_bytes(), f"the file {path.relative_to(tmp_path)}")
    for answer in stand_in.answers:
        _no_key_in(answer, "an answer of the service")
    for request in stand_in.requests:
        other_headers = {name: value for name, value in request["headers"].items() if name.lower() != KEY_HEADER}
        _no_key_in(json.dumps(other_headers) + request["path"] + json.dumps(request["body"]), "a request")
    _no_key_in(caplog.text, "a logging record")
    assert {_route(request) for request in stand_in.requests if _key_sent(request) == "KEY"} == {
        "POST /v1/model-iterations",
        "POST /v1/sessions/<id>/turns",
        "POST /v1/sessions/<id>/entries",
    }


# ---------------------------------------------------------------------------
# against the Matsya service itself


def _answered(service, passage_id: str, answer: str) -> None:
    """Script the conversation role's answer of the next turn."""
    quote = "A stage file names its arrival, decision and continuation fields"
    service.caller.replies.append(
        (
            service.role,
            json.dumps(
                {
                    "status": "answered",
                    "answer": answer,
                    "citations": [{"address": {"source": "index", "target": f"passage:{passage_id}"}, "quote": quote}],
                    "decisions": [],
                }
            ),
        )
    )


@pytest.mark.filterwarnings("ignore::DeprecationWarning")
def test_against_the_service_the_key_reaches_the_calls_of_its_job_and_turn_and_no_file(
    service, run, monkeypatch, tmp_path, caplog
) -> None:
    """Against the Matsya service of the test configuration, with its switch
    on: a job and a turn sent with the key run with callers built with that
    key, report `credential_source` `client` and print the credential line;
    with the switch off, the service refuses the key with 403 and the
    command prints the service's sentence; a turn sent without a key runs
    with the service's key. The key appears in no file that the client or
    the service wrote, the service's database among them, and in no
    logging record."""
    if not hasattr(service.application.state, "accept_personal_keys"):
        pytest.skip("the service in this checkout does not read a personal Anthropic key")
    caplog.set_level(logging.DEBUG)
    status, out, _ = run("search", "What does a stage file name?", "--collections", "repository", "--limit", "1")
    passage_id = _identifier(r"^    passage ([0-9a-f]{64})$", out)
    monkeypatch.setenv(VARIABLE, KEY)

    description = _text(tmp_path, "model.md", service.description)
    status, out, err = run("job", "submit", str(description), "--target", "stage", "--max-cycles", "1")
    _no_key_in(out + err, "the output of job submit")
    assert (status, err) == (0, "") and out.splitlines()[-1] == CREDENTIAL
    job_id = _identifier(r"^Job ([0-9a-f]{32}): queued$", out)
    session_id = _identifier(r"^Session ([0-9a-f]{32}): model$", out)
    status, out, err = run("job", "wait", job_id, "--interval", "0.05")
    assert (status, err) == (0, "") and _final(out)[-1] == CREDENTIAL
    assert _final(out)[0].endswith(f"converged ({job_id}), session {session_id}")
    assert run("job", "export", job_id, str(tmp_path / "export"))[0] == 0
    exported = json.loads((tmp_path / "export" / "job.json").read_text(encoding="utf-8"))
    assert exported["credential_source"] == "client"

    _answered(service, passage_id, "A stage file names its fields [1].")
    status, out, err = run("ask", session_id, "What does a stage file name?", "--interval", "0.05")
    assert (status, err) == (0, "") and _final(out)[-1] == CREDENTIAL
    assert "A stage file names its fields [1]." in _final(out)

    # the switch off: the key is refused, and the command prints the sentence
    service.application.state.accept_personal_keys = False
    status, out, err = run("ask", session_id, "What is a perch?", "--interval", "0.05")
    assert (status, out) == (1, "")
    assert err == (
        "Error: The service refused the request (403): This service does not accept a personal "
        "Anthropic key.\n"
    )
    service.application.state.accept_personal_keys = True

    # without a key, a turn runs with the service's key and prints no line on it
    monkeypatch.delenv(VARIABLE)
    _answered(service, passage_id, "A stage file names its laws [1].")
    status, out, err = run("ask", session_id, "What does a stage file hold?", "--interval", "0.05", "--json")
    assert status == 0 and json.loads(out)["credential_source"] == "service"
    _no_key_in(err, "the progress of ask")
    service.caller.assert_finished()
    assert service.keys == [KEY, KEY, None]

    for path in sorted(tmp_path.rglob("*")):
        if path.is_file():
            _no_key_in(path.read_bytes(), f"the file {path.relative_to(tmp_path)}")
    _no_key_in(caplog.text, "a logging record")
