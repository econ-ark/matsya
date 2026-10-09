"""The documentation travels with the client: the pages under ``docs/`` are the
pages of the Bellman documentation's Matsya user guide and, under
``docs/dev-guide/``, of its developer guide, byte for byte as committed, and
they are installed with the package as its data (AMD-MAT-015 §2)."""

from __future__ import annotations

import importlib.resources
import subprocess
from pathlib import Path

import pytest

CLIENT = Path(__file__).resolve().parents[1]
DOCS = CLIENT / "docs"
REPOSITORY = CLIENT.parents[2]
SOURCES = {
    "": REPOSITORY / "docs" / "matsya" / "user-guide",
    "dev-guide": REPOSITORY / "docs" / "matsya" / "dev-guide",
}


def _copies(folder: str) -> dict[str, bytes]:
    return {path.name: path.read_bytes() for path in (DOCS / folder).glob("*.md")}


def _committed(source: Path) -> dict[str, bytes] | None:
    """The committed pages of ``source``, read from the repository's HEAD so that
    an edit another session has not yet committed does not count; None when the
    client is not beside the documentation's source."""
    if not source.is_dir():
        return None
    relative = source.relative_to(REPOSITORY).as_posix()
    listing = subprocess.run(
        ["git", "-C", str(REPOSITORY), "ls-tree", "--name-only", "HEAD", relative + "/"],
        capture_output=True, text=True, check=False,
    )
    if listing.returncode != 0:
        return None
    pages = {}
    for line in listing.stdout.split():
        if line.endswith(".md"):
            shown = subprocess.run(
                ["git", "-C", str(REPOSITORY), "show", f"HEAD:{line}"], capture_output=True, check=True
            )
            pages[Path(line).name] = shown.stdout
    return pages


def test_the_pages_are_installed_with_the_package() -> None:
    installed = importlib.resources.files("matsya") / "docs"
    names = sorted(entry.name for entry in installed.iterdir() if entry.name.endswith(".md"))
    assert names == sorted(path.name for path in DOCS.glob("*.md"))
    assert names, "the package carries no page"
    guide = installed / "dev-guide"
    assert sorted(e.name for e in guide.iterdir() if e.name.endswith(".md")) == sorted(_copies("dev-guide"))


@pytest.mark.parametrize("folder", sorted(SOURCES))
def test_the_pages_equal_their_committed_source(folder: str) -> None:
    committed = _committed(SOURCES[folder])
    if committed is None:
        pytest.skip("the documentation's source is not beside the client (an installed copy)")
    assert _copies(folder) == committed, (
        "copy the committed pages of the documentation into the client's docs folder"
    )
