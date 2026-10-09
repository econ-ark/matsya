"""The Matsya user guide installed with the client.

The guide's pages are the Markdown files of the package's folder `docs`,
installed with the package as its data (AMD-MAT-015 §2). A page is named by
its path within that folder without `.md`: `index`, the guide's first page,
then the numbered pages, such as `01-working-from-the-command-line`, and a
page of a sub-folder by the sub-folder's name and its own, such as
`dev-guide/index`. `matsya docs` lists and prints the pages, and `matsya`
alone prints the folder that holds them. `matsya docs --online` reads a page
as the client's public repository holds it today, over HTTPS, so that a
reader sees a corrected page without installing a new version of the
client. The names of the pages are the installed guide's in either case,
since the host the pages are read from does not list a folder.
"""

from __future__ import annotations

import http.client
import importlib.resources
import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

# the ending of a page's file name, and the name of a folder's first page
SUFFIX = ".md"
FIRST = "index"
# the folder of the guide's pages in the client's public repository, the
# folder the release script fills, and the seconds a request for one of its
# pages waits for an answer (AMD-MAT-015 §2)
ONLINE = "https://raw.githubusercontent.com/econ-ark/matsya/main/docs/"
ONLINE_TIMEOUT = 30


class OnlineError(Exception):
    """A page of the guide that could not be read from the client's public
    repository."""


def folder() -> Any:
    """The installed folder of the pages, the package's folder `docs`: a
    `pathlib.Path` where the package is installed as files."""
    return importlib.resources.files("matsya") / "docs"


def names() -> list[str]:
    """The names of the pages in the guide's order: in each folder `index`,
    then the other pages in the order of their names, which begin with
    their numbers, then the pages of its sub-folders, each sub-folder in the
    order of its name."""
    return _names(folder(), "")


def _names(directory: Any, prefix: str) -> list[str]:
    entries = sorted(directory.iterdir(), key=lambda entry: entry.name)
    pages = sorted(
        (
            entry.name[: -len(SUFFIX)]
            for entry in entries
            if entry.is_file() and entry.name.endswith(SUFFIX)
        ),
        key=lambda name: (name != FIRST, name),
    )
    found = [prefix + name for name in pages]
    for entry in entries:
        if entry.is_dir() and not entry.name.startswith((".", "_")):
            found += _names(entry, f"{prefix}{entry.name}/")
    return found


def page_name(argument: str) -> str | None:
    """The name of the page that `argument` names, with or without `.md`,
    or None where no page has that name."""
    name = argument[: -len(SUFFIX)] if argument.endswith(SUFFIX) else argument
    return name if name in names() else None


def file_name(name: str) -> str:
    """A page's file name within the folder, such as `index.md`."""
    return name + SUFFIX


def _parts(name: str) -> tuple[list[str], str]:
    """An installed page's front matter and the rest of the page."""
    entry = folder()
    for part in file_name(name).split("/"):
        entry = entry / part
    return _split(entry.read_text(encoding="utf-8"))


def _split(page: str) -> tuple[list[str], str]:
    """A page's front matter, the lines between its opening line `---` and
    the closing one, and the rest of the page."""
    lines = page.splitlines(keepends=True)
    if lines and lines[0].rstrip() == "---":
        for number in range(1, len(lines)):
            if lines[number].rstrip() in ("---", "..."):
                return lines[1:number], "".join(lines[number + 1 :])
    return [], page


def text(name: str) -> str:
    """A page's Markdown as its file holds it, without the front matter and
    the blank lines before and after the rest."""
    return _parts(name)[1].strip("\n")


def online_url(name: str) -> str:
    """The address of a page in the client's public repository, such as
    `https://raw.githubusercontent.com/econ-ark/matsya/main/docs/index.md`."""
    return ONLINE + urllib.parse.quote(file_name(name))


def online_text(name: str) -> str:
    """A page's Markdown as the client's public repository holds it today,
    read with one request over HTTPS, without the front matter and the blank
    lines before and after the rest. A page that cannot be read, because the
    repository holds no page of that name, the request fails or the answer
    is not text in UTF-8, raises `OnlineError`."""
    url = online_url(name)
    try:
        with urllib.request.urlopen(url, timeout=ONLINE_TIMEOUT) as answer:
            page = answer.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        raise OnlineError(_unread(name, url, f"HTTP {error.code} {error.reason}")) from None
    except urllib.error.URLError as error:
        raise OnlineError(_unread(name, url, str(error.reason))) from None
    except (OSError, http.client.HTTPException) as error:
        # a connection that failed while the page was read, or a time limit
        raise OnlineError(_unread(name, url, str(error) or type(error).__name__)) from None
    except UnicodeDecodeError:
        raise OnlineError(_unread(name, url, "the answer is not text in UTF-8")) from None
    return _split(page)[1].strip("\n")


def _unread(name: str, url: str, reason: str) -> str:
    """The sentence of `OnlineError`: the page, its address and the reason."""
    return f"the page {file_name(name)} of the online guide could not be read from {url} ({reason})"


def title(name: str) -> str:
    """A page's title: the value of `title` in its front matter, else its
    first heading, else its name."""
    front, rest = _parts(name)
    for line in front:
        if line.startswith("title:") and line[len("title:") :].strip():
            return _unquoted(line[len("title:") :].strip())
    for line in rest.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return name


def _unquoted(value: str) -> str:
    """A value of the front matter without its quotation marks."""
    if len(value) >= 2 and value[0] == value[-1] == '"':
        try:
            return str(json.loads(value))
        except ValueError:
            return value[1:-1]
    if len(value) >= 2 and value[0] == value[-1] == "'":
        return value[1:-1].replace("''", "'")
    return value
