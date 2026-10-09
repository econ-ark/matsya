"""The acceptance file of AMD-MAT-015 on the side of the client, against no
service: the command `matsya docs` of the amendment's §2, which lists the
pages of the user guide installed with the client, prints one page, every
page or the folder that holds them, and refuses a page it does not hold;
with `--online`, which reads a page or every page from the client's public
repository through a stand-in for `urllib.request.urlopen`, so that no
request is sent; and the parts of item 5 that need no project folder:
`matsya` alone prints the orientation, with and without a saved Matsya
token, and a command run with no configuration file and MATSYA_TOKEN unset
prints the two first-use lines before anything else, which no command
prints once the configuration file exists. The expected pages are read from
the client's folder `docs/`, so that a page added or renumbered (§3) leaves
these tests as they are; the copies' equality with their source is tested
in `test_docs.py`."""

from __future__ import annotations

import importlib.resources
import json
import re
import urllib.error
from pathlib import Path

import pytest

from conftest import TOKEN
from matsya import __version__, config

DOCS = Path(__file__).resolve().parents[1] / "docs"
FIRST_USE = (
    "This is the first use of matsya on this machine.\n"
    "A model working for the user reads the guide first: matsya docs --all\n"
)
ADDRESS = "https://service.example.invalid"
# the folder of the guide's pages in the client's public repository
ONLINE = "https://raw.githubusercontent.com/econ-ark/matsya/main/docs/"
# the sentence the stand-in repository adds to every page
CORRECTION = "A sentence corrected in the public repository."
# the three parts as the user guide's page `index.md` defines them
THREE_PARTS = (
    "**matsya-client**, the command you run on your own machine, a program with no language "
    "model in it; **matsya-architect**, the service's job side, which builds and checks a "
    "declaration in one run; and **matsya-master**, the service's conversation side, which "
    "answers one question at a time."
)


def _no_request(*arguments: object, **options: object) -> None:
    raise AssertionError("these tests send no request")


@pytest.fixture
def new_machine(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """A machine on which the client was never used: a temporary home folder
    with no configuration file, neither MATSYA_TOKEN nor MATSYA_SERVER set,
    and no request possible. Returns the configuration file's path."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(config, "CONFIG_DIR", home / ".config" / "matsya")
    monkeypatch.setattr(config, "CONFIG_FILE", home / ".config" / "matsya" / "config.toml")
    for variable in ("MATSYA_TOKEN", "MATSYA_SERVER"):
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setattr("urllib.request.urlopen", _no_request)
    return config.CONFIG_FILE


def _pages() -> list[tuple[str, Path]]:
    """The pages of the client's folder `docs/`, each with its name, in the
    guide's order: in each folder `index`, then the other pages by name,
    then the pages of the sub-folders."""
    found = [
        path.relative_to(DOCS)
        for path in DOCS.rglob("*.md")
        if not any(part.startswith((".", "_")) for part in path.relative_to(DOCS).parts[:-1])
    ]
    found.sort(key=lambda page: (page.parts[:-1], page.stem != "index", page.name))
    return [(page.with_suffix("").as_posix(), DOCS / page) for page in found]


def _title(path: Path) -> str:
    """A page's title as its front matter writes it."""
    value = re.search(r"^title:(.*)$", path.read_text(encoding="utf-8"), re.MULTILINE).group(1).strip()
    return json.loads(value) if value.startswith('"') else value


def _body(path: Path) -> str:
    """A page without its front matter and the blank lines around the rest."""
    return _body_text(path.read_text(encoding="utf-8"))


def _body_text(page: str) -> str:
    """A page's text without its front matter and the blank lines around
    the rest."""
    return re.sub(r"\A---\n.*?\n---\n", "", page, count=1, flags=re.DOTALL).strip("\n")


class _Answer:
    """What the stand-in for `urllib.request.urlopen` returns: a page's
    bytes, read once within a `with` statement."""

    def __init__(self, data: bytes) -> None:
        self.data = data

    def __enter__(self) -> "_Answer":
        return self

    def __exit__(self, *exception: object) -> None:
        return None

    def read(self) -> bytes:
        return self.data


def test_item_1_docs_lists_prints_and_locates_the_installed_pages(new_machine, run) -> None:
    pages = _pages()
    assert pages[0][0] == "index" and len(pages) > 1
    width = max(len(name) for name, _ in pages)
    listing = "".join(f"{name:<{width}}  {_title(path)}\n" for name, path in pages)
    assert run("docs") == (0, listing, "")
    for name, path in pages:
        body = _body(path)
        assert body.startswith("# ")
        assert run("docs", name) == (0, body + "\n", "")
        assert run("docs", f"{name}.md") == (0, body + "\n", "")
    every_page = "\n".join(f"<!-- page: {name}.md -->\n{_body(path)}\n" for name, path in pages)
    assert run("docs", "--all") == (0, every_page, "")
    installed = importlib.resources.files("matsya") / "docs"
    assert run("docs", "--path") == (0, f"{installed}\n", "")
    printed = Path(str(installed))
    assert {page.relative_to(printed): page.read_bytes() for page in printed.rglob("*.md")} == {
        page.relative_to(DOCS): page.read_bytes() for page in DOCS.rglob("*.md")
    }
    # `matsya docs` needs no Matsya token: no first-use lines, no file written
    assert not new_machine.exists()


def test_a_page_the_guide_does_not_hold_or_a_page_with_all_or_path_is_refused(new_machine, run) -> None:
    names = ", ".join(name for name, _ in _pages())
    status, out, err = run("docs", "no-such-page")
    assert (status, out) == (2, "")
    assert err.endswith(
        'matsya docs: error: argument page: no page of the user guide is named "no-such-page"; '
        f"the pages are {names}\n"
    )
    for arguments in (
        ("docs", "index", "--all"),
        ("docs", "--path", "index"),
        ("docs", "--all", "--path"),
        ("docs", "--online", "--path"),
        ("docs", "--path", "--online"),
    ):
        status, out, err = run(*arguments)
        assert (status, out) == (2, "") and "not allowed with argument" in err, arguments
    assert err.endswith("matsya docs: error: argument --online: not allowed with argument --path\n")


def test_docs_online_reads_the_pages_as_the_public_repository_holds_them(
    new_machine, run, monkeypatch
) -> None:
    pages = _pages()
    # the stand-in public repository holds every installed page with one
    # sentence added at its end
    held = {
        f"{ONLINE}{name}.md": (path.read_text(encoding="utf-8") + f"\n{CORRECTION}\n").encode()
        for name, path in pages
    }
    requested: list[tuple[str, object]] = []

    def answer(url: str, timeout: object = None) -> _Answer:
        requested.append((url, timeout))
        if url not in held:
            raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)
        return _Answer(held[url])

    monkeypatch.setattr("urllib.request.urlopen", answer)

    def online_body(name: str) -> str:
        return _body_text(held[f"{ONLINE}{name}.md"].decode("utf-8"))

    # one page, named with or without .md: one request, to that page's
    # address, with a time limit, and the page as the repository holds it
    name, path = pages[-1]
    assert online_body(name) == _body(path) + "\n\n" + CORRECTION
    for arguments in (("docs", name, "--online"), ("docs", "--online", f"{name}.md")):
        requested.clear()
        assert run(*arguments) == (0, online_body(name) + "\n", "")
        assert [url for url, _ in requested] == [f"{ONLINE}{name}.md"]
        assert all(isinstance(limit, (int, float)) and limit > 0 for _, limit in requested)

    # every page, in the installed guide's order, one request for each
    requested.clear()
    every_page = "\n".join(f"<!-- page: {name}.md -->\n{online_body(name)}\n" for name, _ in pages)
    assert run("docs", "--all", "--online") == (0, every_page, "")
    assert [url for url, _ in requested] == [f"{ONLINE}{name}.md" for name, _ in pages]

    # the list of pages is the installed guide's, and it sends no request
    requested.clear()
    assert run("docs", "--online") == run("docs")
    assert requested == []

    # a page the repository does not hold: one sentence on standard error,
    # status 1, and no part of the guide printed
    missing = pages[1][0]
    del held[f"{ONLINE}{missing}.md"]
    assert run("docs", "--all", "--online") == (
        1,
        "",
        f"Error: the page {missing}.md of the online guide could not be read from "
        f"{ONLINE}{missing}.md (HTTP 404 Not Found); without --online, matsya docs prints the "
        "installed guide.\n",
    )

    # no connection: the same sentence with the reason the request failed
    def unreachable(url: str, timeout: object = None) -> _Answer:
        raise urllib.error.URLError(ConnectionRefusedError(61, "Connection refused"))

    monkeypatch.setattr("urllib.request.urlopen", unreachable)
    assert run("docs", "index", "--online") == (
        1,
        "",
        f"Error: the page index.md of the online guide could not be read from {ONLINE}index.md "
        "([Errno 61] Connection refused); without --online, matsya docs prints the installed "
        "guide.\n",
    )
    # `matsya docs --online` needs no Matsya token: no first-use lines, no file written
    assert not new_machine.exists()


def test_item_5_matsya_alone_prints_the_orientation_with_and_without_a_saved_token(
    new_machine, run, monkeypatch
) -> None:
    status, out, err = run()
    assert (status, err) == (0, "")
    lines = out.splitlines()
    assert lines[:2] == ["# Matsya", ""]
    assert lines[2].startswith(
        "Matsya turns an economist's description of a dynamic model, or a paper, into a "
        "declaration in Bellman-SYM"
    )
    assert lines[2].endswith(" It has three parts: " + THREE_PARTS)
    assert THREE_PARTS in (DOCS / "index.md").read_text(encoding="utf-8")
    installed = importlib.resources.files("matsya") / "docs"
    assert lines[3:] == [
        "",
        f"The user guide is installed on this machine in the folder `{installed}`. The installed "
        f"guide describes the commands of this client, version {__version__}. `matsya docs` lists "
        "its pages, `matsya docs --all` prints the whole installed guide, which a model working "
        "for the user reads first, and `matsya docs --all --online` prints the whole guide as it "
        "stands today in the client's public repository. `pip install --upgrade "
        "git+https://github.com/econ-ark/matsya` upgrades the client and its installed guide.",
        "",
        "No Matsya token is saved on this machine; `matsya configure` saves it.",
        "",
        "`matsya --help` lists the commands.",
    ]
    # the orientation needs no Matsya token: no first-use lines, no file written
    assert not new_machine.exists()

    config.save_config(TOKEN, ADDRESS)
    status, out, err = run()
    assert (status, err) == (0, "")
    assert out.splitlines()[6] == f"A Matsya token is saved on this machine, in `{new_machine}`."
    assert TOKEN not in out and "matsya configure" not in out
    monkeypatch.setenv("MATSYA_TOKEN", TOKEN)
    status, out, _ = run()
    assert out.splitlines()[6] == (
        f"A Matsya token is saved on this machine, in `{new_machine}`. The environment variable "
        "`MATSYA_TOKEN` is set, and the commands use its value in place of a saved Matsya token."
    )
    assert TOKEN not in out

    # `matsya --help` keeps the usage text
    status, out, err = run("--help")
    assert (status, err) == (0, "")
    assert out.startswith("usage: matsya [-h] <command> ...\n") and "\nRead first:\n" in out


def test_item_5_the_first_use_lines_come_first_until_the_configuration_file_exists(
    new_machine, run, monkeypatch, tmp_path
) -> None:
    # with no configuration file and MATSYA_TOKEN unset, a command prints the
    # two lines and then refuses with its present sentence
    assert run("index") == (
        1,
        FIRST_USE,
        "Error: No Matsya service address configured. Set MATSYA_SERVER to the address "
        "supplied by Econ-ARK-admin, or run matsya configure.\n",
    )
    monkeypatch.setenv("MATSYA_SERVER", ADDRESS)
    assert run("index") == (
        1,
        FIRST_USE,
        "Error: no Matsya token is configured. Run matsya configure, or set the environment "
        "variable MATSYA_TOKEN.\n",
    )
    # configure prints them before its own lines, then asks and saves
    answers = [TOKEN, ADDRESS]
    monkeypatch.setattr("builtins.input", lambda prompt="": answers.pop(0))
    status, out, err = run("configure")
    assert (status, err) == (0, "")
    assert out.startswith(FIRST_USE + "Matsya: save your Matsya token and the service address\n")
    assert new_machine.exists() and TOKEN not in out

    # once the configuration file exists, no command prints them
    answers += [TOKEN, ADDRESS]
    status, out, _ = run("configure")
    assert status == 0 and out.startswith("Matsya: save your Matsya token and the service address\n")
    absent = tmp_path / "absent.md"
    status, out, err = run("job", "submit", str(absent))
    assert (status, out) == (1, "") and err.startswith(f"Error: cannot read {absent}")
    # nor does a command run with MATSYA_TOKEN set and no configuration file
    new_machine.unlink()
    monkeypatch.setenv("MATSYA_TOKEN", TOKEN)
    status, out, err = run("job", "submit", str(absent))
    assert (status, out) == (1, "") and err.startswith(f"Error: cannot read {absent}")
