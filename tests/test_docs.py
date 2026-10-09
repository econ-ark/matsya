"""The user guide travels with the client: the pages under ``docs/`` are the
pages of the Bellman documentation's Matsya user guide, byte for byte, and
they are installed with the package as its data (AMD-MAT-015 §2)."""

from __future__ import annotations

import importlib.resources
from pathlib import Path

import pytest

CLIENT = Path(__file__).resolve().parents[1]
DOCS = CLIENT / "docs"
SOURCE = CLIENT.parents[2] / "docs" / "matsya" / "user-guide"


def test_the_pages_are_installed_with_the_package() -> None:
    installed = importlib.resources.files("matsya") / "docs"
    names = sorted(entry.name for entry in installed.iterdir() if entry.name.endswith(".md"))
    assert names == sorted(path.name for path in DOCS.glob("*.md"))
    assert names, "the package carries no page"


def test_the_pages_equal_their_source() -> None:
    if not SOURCE.is_dir():
        pytest.skip("the documentation's source is not beside the client (an installed copy)")
    source = {path.name: path.read_bytes() for path in SOURCE.glob("*.md")}
    copies = {path.name: path.read_bytes() for path in DOCS.glob("*.md")}
    assert copies == source, "run the release's copy of the user guide into the client's docs folder"
