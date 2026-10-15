"""The acceptance of AMD-MAT-021 §5 item 7 on the side of the client's
documentation, against no service. The pages and sections that the
amendment's §4 names, read from the client's folder `docs/` as
`test_amd_mat_015_client.py` reads them, state how a registered holder of a
Matsya token supplies a personal Anthropic key after the Matsya-token
procedure: the two options of `bellman-matsya configure`, the environment
variable, the key file, the header, the two values of `credential_source`,
the rule that the key travels only over HTTPS or to a loopback address, and
the client's and the service's sentences as the amendment quotes them.
`bellman-matsya docs --all` prints the same pages; the client's README states
the same order of set-up (§2.1); and no installed page says that the Matsya
token is the only secret the client holds. The equality of the copies with
their committed source is tested in `test_docs.py`. No test sends a request,
and none names a key."""

from __future__ import annotations

import importlib.resources
import re
from pathlib import Path

import pytest

from bellman_matsya import config

CLIENT = Path(__file__).resolve().parents[1]
DOCS = CLIENT / "docs"
README = CLIENT / "README.md"

# the names the amendment fixes (AMD-MAT-021 §§2.2–2.5 and 3.1–3.4)
SET_OPTION = "--set-anthropic-key"
CLEAR_OPTION = "--clear-anthropic-key"
VARIABLE = "BELLMAN_MATSYA_ANTHROPIC_KEY"
KEY_FILE = "~/.config/bellman-matsya/anthropic-key"
HEADER = "Bellman-Matsya-Anthropic-Key"
KEYWORD = "anthropic_api_key"
FIELD = "`credential_source`"
SOURCES = ("`client`", "`service`")
CODE = "provider_rejected_credential"
LOOPBACK = ("`localhost`", "`127.0.0.1`", "`::1`")
# the three routes that read the header (§2.3)
ROUTES = (
    "POST /v1/model-iterations",
    "POST /v1/sessions/{session_id}/turns",
    "POST /v1/sessions/{session_id}/entries",
)
# the public address that uses plain HTTP and cannot receive a key (§2.6)
PLAIN_ADDRESS = "http://45.55.225.169:8710"

# the client's sentences, as the amendment quotes them (§§2.1–2.5)
NO_TOKEN = (
    "Error: no Matsya token is configured. A personal Anthropic key is an addition to a Matsya "
    "token, not a substitute for it: save the Matsya token the service's administrator gave you "
    "with bellman-matsya configure, or set BELLMAN_MATSYA_TOKEN."
)
CONSTRUCTOR_REFUSAL = (
    "The personal Anthropic key is empty or contains a space, a line break or a character outside "
    "printable ASCII"
)
VARIABLE_REFUSAL = (
    "Error: the personal Anthropic key in BELLMAN_MATSYA_ANTHROPIC_KEY is empty or contains a "
    "space, a line break or another character that an HTTP header does not allow; set the "
    "variable to the key alone, or unset it to use the service's key."
)
FILE_REFUSAL = (
    "Error: the personal Anthropic key in the saved file <path> is empty or contains a space, a "
    "line break or another character that an HTTP header does not allow; set it again with "
    "bellman-matsya configure --set-anthropic-key, or remove it with bellman-matsya configure "
    "--clear-anthropic-key."
)
ENTERED_REFUSAL = (
    "Error: the key you entered is empty or contains a space, a line break or another character "
    "that an HTTP header does not allow; nothing was saved."
)
DESTINATION_REFUSAL = (
    "A personal Anthropic key is sent only over HTTPS or to localhost, 127.0.0.1 or ::1, and the "
    "service address is <address>; use an HTTPS address, or stop selecting the key: unset "
    "BELLMAN_MATSYA_ANTHROPIC_KEY, run bellman-matsya configure --clear-anthropic-key, or omit "
    "anthropic_api_key."
)
ORIENTATION_VARIABLE = (
    "The environment variable `BELLMAN_MATSYA_ANTHROPIC_KEY` is set; new jobs, questions and "
    "replies that continue a job use its value in place of any saved key, and the Anthropic "
    "account of that key is charged."
)
ORIENTATION_SAVED = (
    "A personal Anthropic key is saved on this machine, in `<file>`; new jobs, questions and "
    "replies that continue a job use it, and the Anthropic account of that key is charged."
)
ORIENTATION_NONE = (
    "No personal Anthropic key is selected; new jobs and questions use the service's key, and a "
    "reply that would continue a job run with a personal key is refused until one is selected."
)
ORIENTATION_PLAIN_HTTP = (
    "The service address <address> uses plain HTTP, so the client refuses to send a job, a "
    "question or a reply with this key."
)
CREDENTIAL_LINE = "Credential: your Anthropic API key"
ACCEPTED_UNDER_SERVICE_KEY = (
    "Error: the service at <address> accepted {work} <id> under its own Anthropic key, not yours."
)
CANCEL_LINE = "Cancel it with: bellman-matsya job cancel <id>"
KEY_REMEDY = (
    "Supply one with bellman-matsya configure --set-anthropic-key, BELLMAN_MATSYA_ANTHROPIC_KEY, "
    "or MatsyaClient(..., anthropic_api_key=...)."
)
# the service's sentences, as the amendment quotes them (§§3.1–3.3)
EMPTY_HEADER = "The Bellman-Matsya-Anthropic-Key header is empty"
NOT_ACCEPTED = "This service does not accept a personal Anthropic key"
REPLY_NEEDS_KEY = (
    "The job awaiting this reply ran under a personal Anthropic key; send the reply with a "
    "personal Anthropic key"
)
TURN_REFUSED_KEY = (
    "Matsya could not answer, because the language-model provider refused the Anthropic API key "
    "used for this turn."
)
# the set-up of the Matsya token, which comes first (§2.1)
TOKEN_SET_UP = "bellman-matsya configure\nbellman-matsya index\n"
KEY_SET_UP = f"bellman-matsya configure {SET_OPTION}"
# the sentence of the user guide's page `index.md` that §4 replaces
ONLY_SECRET = "The Matsya token is the only secret the client holds"

# what each section that §4 names states, by page and section number
NAMED_SECTIONS = {
    ("index", "1"): (
        "The Matsya token is required for every request.",
        "**service key**",
        "stays on the server",
        "**personal Anthropic key**",
        "an optional addition to the Matsya token, never a substitute for it",
    ),
    ("00-for-a-local-model", "3"): (
        KEY_FILE,
        f"bellman-matsya configure {SET_OPTION}",
        f"bellman-matsya configure {CLEAR_OPTION}",
        VARIABLE,
        "after its line on the Matsya token, one line that says which key",
        "an assistant never asks for the key, never receives it in chat and never types it",
    ),
    ("00-for-a-local-model", "5"): (
        f"bellman-matsya configure {SET_OPTION}",
        VARIABLE,
        "HTTPS",
        *LOOPBACK,
        "1 when",
    ),
    ("02-working-from-the-command-line", "1"): (
        TOKEN_SET_UP,
        KEY_SET_UP,
        f"bellman-matsya configure {CLEAR_OPTION}",
        KEY_FILE,
        VARIABLE,
        f'export {VARIABLE}="$(cat ',
        HEADER,
        NO_TOKEN,
        DESTINATION_REFUSAL.replace("<address>", PLAIN_ADDRESS),
        *LOOPBACK,
        "3,000,000 input tokens and 300,000 output tokens",
        "600,000 input tokens and 60,000 output tokens",
        FIELD,
        *SOURCES,
        CREDENTIAL_LINE,
        ACCEPTED_UNDER_SERVICE_KEY.format(work="<job or turn>"),
        CANCEL_LINE,
        CODE,
        "an assistant never asks for it, receives it in chat or types it",
    ),
    ("04-the-service-by-http", "1"): (
        HEADER,
        *ROUTES,
        f'export {VARIABLE}="$(cat ',
        "refused with 401",
        "HTTPS",
        *LOOPBACK,
        PLAIN_ADDRESS,
        FIELD,
    ),
    ("04-the-service-by-http", "2"): (HEADER, FIELD),
    ("04-the-service-by-http", "3"): (EMPTY_HEADER, NOT_ACCEPTED, REPLY_NEEDS_KEY, HEADER),
    ("04-the-service-by-http", "5"): (HEADER, FIELD, '"credential_source":"client"', *SOURCES, CODE),
    ("04-the-service-by-http", "6"): (HEADER, REPLY_NEEDS_KEY, KEY_REMEDY, FIELD),
    ("04-the-service-by-http", "7"): (FIELD, *SOURCES, CODE, TURN_REFUSED_KEY),
    ("05-the-command-reference", "2.1"): (
        ORIENTATION_VARIABLE,
        ORIENTATION_SAVED,
        ORIENTATION_NONE,
        ORIENTATION_PLAIN_HTTP,
    ),
    ("05-the-command-reference", "2.2"): (
        KEY_SET_UP,
        f"bellman-matsya configure {CLEAR_OPTION}",
        KEY_FILE,
        VARIABLE,
        NO_TOKEN,
        ENTERED_REFUSAL,
        VARIABLE_REFUSAL,
        FILE_REFUSAL,
        HEADER,
        "<Anthropic API key>",
    ),
    ("05-the-command-reference", "4"): (
        HEADER,
        DESTINATION_REFUSAL,
        CREDENTIAL_LINE,
        ACCEPTED_UNDER_SERVICE_KEY.format(work="job"),
        CANCEL_LINE,
        FIELD,
    ),
    ("05-the-command-reference", "5"): ("--replies-to", CREDENTIAL_LINE, REPLY_NEEDS_KEY, KEY_REMEDY),
    ("05-the-command-reference", "6"): (
        CREDENTIAL_LINE,
        ACCEPTED_UNDER_SERVICE_KEY.format(work="turn"),
        CODE,
        TURN_REFUSED_KEY,
    ),
    ("05-the-command-reference", "7"): ("`project submit`", "no entry is appended", "no new digest"),
    ("05-the-command-reference", "8"): (FIELD, *SOURCES, CODE),
    ("06-the-python-module", "1"): (
        f"MatsyaClient(token, server_url, {KEYWORD}=key)",
        "`ValueError`",
        CONSTRUCTOR_REFUSAL,
        "`MatsyaError`",
        DESTINATION_REFUSAL,
        VARIABLE,
        HEADER,
        FIELD,
        KEY_REMEDY,
        "<Anthropic API key>",
    ),
    ("dev-guide/02-what-matsya-reads", "4"): (
        "`key_variable`",
        "**service key**",
        "**personal Anthropic key**",
        HEADER,
        FIELD,
        *SOURCES,
        CODE,
    ),
}


def _no_request(*arguments: object, **options: object) -> None:
    raise AssertionError("these tests send no request")


@pytest.fixture
def no_configuration(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A machine on which the client holds nothing of the user's: a
    temporary home folder with no configuration file and no saved key, no
    Matsya token, service address or personal key in the environment, and no
    request possible."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(config, "CONFIG_DIR", home / ".config" / "bellman-matsya")
    monkeypatch.setattr(config, "CONFIG_FILE", home / ".config" / "bellman-matsya" / "config.toml")
    for variable in ("BELLMAN_MATSYA_TOKEN", "BELLMAN_MATSYA_SERVER", VARIABLE):
        monkeypatch.delenv(variable, raising=False)
    # the client's opener and `urlopen` both send through `OpenerDirector.open`
    monkeypatch.setattr("urllib.request.OpenerDirector.open", _no_request)


def _page(name: str) -> str:
    """A page of the client's folder `docs/`, named without `.md`."""
    return (DOCS / f"{name}.md").read_text(encoding="utf-8")


def _section(text: str, number: str) -> str:
    """The section numbered `number`, such as "1" or "2.2", of a Markdown
    text whose sections are headed `## 1 ...` and `### 2.2 ...`: the lines
    after its heading up to the next heading of the same or a higher level."""
    depth = number.count(".") + 2
    heading = re.search(rf"^{'#' * depth} {re.escape(number)} .*$", text, re.MULTILINE)
    assert heading is not None, f"no section {number}"
    rest = text[heading.end():]
    following = re.search(rf"^#{{2,{depth}}} ", rest, re.MULTILINE)
    return rest[: following.start()] if following else rest


def _installed_pages() -> dict[str, str]:
    """Every page of the guide as the package installs it, by its path in
    the installed folder."""
    installed = Path(str(importlib.resources.files("bellman_matsya") / "docs"))
    return {
        page.relative_to(installed).as_posix(): page.read_text(encoding="utf-8")
        for page in sorted(installed.rglob("*.md"))
    }


@pytest.mark.parametrize(
    ("page", "number"), sorted(NAMED_SECTIONS), ids=lambda value: str(value).replace("/", "-")
)
def test_item_7_each_named_section_states_the_personal_key(page: str, number: str) -> None:
    section = _section(_page(page), number)
    missing = [phrase for phrase in NAMED_SECTIONS[page, number] if phrase not in section]
    assert missing == [], f"{page}.md §{number} does not state {missing}"


@pytest.mark.parametrize(
    ("text", "token_set_up"),
    [
        (lambda: _section(_page("02-working-from-the-command-line"), "1"), TOKEN_SET_UP),
        (
            lambda: _section(_page("00-for-a-local-model"), "3"),
            "runs `bellman-matsya configure`, which, run without an option, asks only for the Matsya token",
        ),
        (lambda: _section(README.read_text(encoding="utf-8"), "2"), "Run `bellman-matsya index`"),
    ],
    ids=["command-line-page", "assistant-page", "readme"],
)
def test_item_7_the_key_is_set_up_after_the_matsya_token(text, token_set_up: str) -> None:
    section = text()
    # the Matsya token is configured and checked first, and the personal key
    # is added only after it (AMD-MAT-021 §2.1)
    assert token_set_up in section and KEY_SET_UP in section
    assert section.index(token_set_up) < section.index(KEY_SET_UP)


def test_item_7_the_readme_states_the_order_and_the_rules() -> None:
    second = _section(README.read_text(encoding="utf-8"), "2")
    for phrase in (
        "Run `bellman-matsya configure`",
        KEY_SET_UP,
        f"bellman-matsya configure {CLEAR_OPTION}",
        KEY_FILE,
        VARIABLE,
        *LOOPBACK,
        PLAIN_ADDRESS,
        CREDENTIAL_LINE,
        "never a substitute for it",
        "never to an assistant in chat",
    ):
        assert phrase in second, phrase
    assert second.index("Run `bellman-matsya configure`") < second.index(KEY_SET_UP)


def test_item_7_docs_all_prints_the_procedure_after_the_matsya_token(no_configuration, run) -> None:
    status, out, err = run("docs", "--all")
    assert (status, err) == (0, "")
    for phrase in (
        SET_OPTION,
        CLEAR_OPTION,
        VARIABLE,
        KEY_FILE,
        HEADER,
        KEYWORD,
        FIELD,
        *SOURCES,
        DESTINATION_REFUSAL,
        *LOOPBACK,
        CREDENTIAL_LINE,
        CODE,
    ):
        assert phrase in out, phrase
    # within the page that follows one piece of work, the Matsya token's
    # set-up is printed before the personal key's
    page = out.split("<!-- page: 02-working-from-the-command-line.md -->\n", 1)[1]
    page = page.split("<!-- page: ", 1)[0]
    assert page.index(TOKEN_SET_UP) < page.index(KEY_SET_UP)
    assert ONLY_SECRET not in out
    # the guide needs no Matsya token and writes nothing
    assert not config.CONFIG_DIR.exists()


def test_item_7_no_installed_page_says_the_matsya_token_is_the_only_secret() -> None:
    pages = _installed_pages()
    assert "index.md" in pages and "dev-guide/02-what-matsya-reads.md" in pages
    stating = sorted(path for path, text in pages.items() if "only secret" in text)
    assert stating == []
    copies = {page.relative_to(DOCS).as_posix() for page in DOCS.rglob("*.md")}
    assert set(pages) == copies
