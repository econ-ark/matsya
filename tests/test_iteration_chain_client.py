"""The client writes each declaration beside the prose that produced it."""

from __future__ import annotations

import json
from copy import deepcopy

from bellman_matsya import MatsyaClient
from bellman_matsya import cli
from bellman_matsya.client import _folder_texts, _iterate_texts, report_text


def _job(*, cycle: int, partial_second: bool = False) -> tuple[dict, dict]:
    original, first, second = "Prepared model M.\n", "Model M′.\n", "Model M′′.\n"
    initial = {"files": {"household.bl": "initial D\n"}, "digest": "0" * 64}
    cycles = [
        {
            "number": 1,
            "prose_writing": {"description": first},
            "writing": {"files": {"household.bl": "first D′\n"}, "digest": "1" * 64},
            "comparison": {
                "equal": False,
                "profile": {"first_difference": {"kind": "kernel"}},
            },
        },
        {
            "number": 2,
            "prose_writing": {"description": second},
            "writing": {"files": {"household.bl": "second D′′\n"}, "digest": "2" * 64},
            "comparison": {"equal": True, "profile": {"first_difference": None}},
        },
    ]
    if partial_second:
        cycles[1].pop("writing")
        cycles[1].pop("comparison")
    selected = cycle if not partial_second else 1
    descriptions = {0: original, 1: first, 2: second}
    files = (
        initial["files"] if selected == 0 else cycles[selected - 1]["writing"]["files"]
    )
    result = {
        "schema": "matsya-model-iteration/7",
        "description": original,
        "status": "not_converged" if partial_second else "converged",
        "reason": "stage_file_refused" if partial_second else "semantic_fixed_point",
        "cycles_run": len(cycles),
        "last_cycle": {
            "files": (
                None if partial_second else deepcopy(cycles[-1]["writing"]["files"])
            ),
            "judging": None,
            "comparison": (
                None if partial_second else {"equal": True, "first_difference": None}
            ),
        },
        "last_completed_comparison": (
            {
                "left_cycle": 0,
                "right_cycle": 1,
                "equal": False,
                "first_difference": {"kind": "kernel"},
            }
            if partial_second
            else {
                "left_cycle": 1,
                "right_cycle": 2,
                "equal": True,
                "first_difference": None,
            }
        ),
        "available_writing": {
            "cycle": selected,
            "files": deepcopy(files),
            "description": descriptions[selected],
        },
    }
    product = {
        "id": "a" * 32,
        "state": result["status"],
        "session": None,
        "updated_at": "2026-10-12T00:00:00+00:00",
        "result": result,
    }
    full = deepcopy(product)
    full["result"] = {
        "schema": result["schema"],
        "description": original,
        "initial_writing": initial,
        "cycles": cycles,
        "status": result["status"],
        "reason": result["reason"],
    }
    return product, full


def test_two_iterations_have_three_declarations_and_matching_prose(
    monkeypatch, tmp_path
) -> None:
    product, full = _job(cycle=2)
    client = MatsyaClient("test-token", "http://127.0.0.1:1")
    monkeypatch.setattr(
        client, "job", lambda _id, view="products": full if view == "full" else product
    )

    folder = tmp_path / "model"
    client.job_files(product["id"], folder, all_iterates=True)

    assert (
        (folder / "economics.md")
        .read_text(encoding="utf-8")
        .endswith("\n---\n\nModel M′′.\n")
    )
    assert (
        folder / "declaration/stages/household/household.bl"
    ).read_text() == "second D′′\n"
    assert (
        folder / "iterates/initial/model-prose.md"
    ).read_text() == "Prepared model M.\n"
    assert (folder / "iterates/initial/household.bl").read_text() == "initial D\n"
    assert (folder / "iterates/cycle-1/model-prose.md").read_text() == "Model M′.\n"
    assert (folder / "iterates/cycle-1/household.bl").read_text() == "first D′\n"
    assert (folder / "iterates/cycle-2/model-prose.md").read_text() == "Model M′′.\n"
    assert (folder / "iterates/cycle-2/household.bl").read_text() == "second D′′\n"
    assert not (folder / "iterates/cycle-3").exists()
    assert not list((folder / "iterates").rglob("round-trip"))
    assert (
        json.loads((folder / "iterates/cycle-2/cycle.json").read_text())["comparison"][
            "equal"
        ]
        is True
    )
    report = (folder / "report.md").read_text()
    assert "Comparison of elaborated semantic objects" in report
    assert "## Iterations and version" in report
    assert "The job ran 2 numbered iterations." in report
    assert "The elaborated semantic objects from iterations 1 and 2 are equivalent." in report


def test_partial_second_iteration_returns_the_last_paired_prose_and_files() -> None:
    product, full = _job(cycle=1, partial_second=True)
    texts = _folder_texts(product)
    iterates = _iterate_texts(full)

    assert texts["economics.md"].endswith("Model M′.\n")
    assert texts["declaration/stages/household/household.bl"] == "first D′\n"
    assert "The declaration files come from iteration 1" in texts["report.md"]
    assert iterates["iterates/cycle-2/model-prose.md"] == "Model M′′.\n"
    assert "iterates/cycle-2/household.bl" not in iterates


def test_report_names_first_comparison_when_second_writing_has_provisional_files() -> None:
    product, _ = _job(cycle=2)
    result = product["result"]
    result["status"] = "not_converged"
    result["reason"] = "stage_file_refused"
    result["last_cycle"]["comparison"] = None
    result["last_completed_comparison"] = {
        "left_cycle": 0,
        "right_cycle": 1,
        "equal": False,
        "first_difference": {"kind": "kernel"},
    }

    texts = _folder_texts(product)
    report = texts["report.md"]

    assert texts["economics.md"].endswith("Model M′′.\n")
    assert texts["declaration/stages/household/household.bl"] == "second D′′\n"
    assert "The returned declaration files are provisional" in report
    assert "The elaborated semantic objects from the initial writing and iteration 1 differ." in report
    assert "Iteration 2 ended before its adjacent comparison." in report
    assert "The record holds no comparison of adjacent elaborated semantic objects." not in report


def test_initial_writing_remains_available_when_iteration_one_stops() -> None:
    product, full = _job(cycle=0, partial_second=True)
    product["result"]["cycles_run"] = 1
    product["result"]["last_cycle"] = {"files": None, "comparison": None}
    product["result"]["available_writing"] = {
        "cycle": 0,
        "files": full["result"]["initial_writing"]["files"],
        "description": full["result"]["description"],
    }
    texts = _folder_texts(product)

    assert texts["economics.md"].endswith("Prepared model M.\n")
    assert texts["declaration/stages/household/household.bl"] == "initial D\n"
    assert "the initial writing" in texts["report.md"]
    assert (
        "Available provisional files from the initial writing: household.bl"
        in cli._job_lines(product)
    )


def test_new_record_does_not_pair_later_files_with_unrelated_prepared_prose() -> None:
    product, _ = _job(cycle=2)
    product["result"]["available_writing"].pop("description")

    texts = _folder_texts(product)

    assert "economics.md" not in texts
    assert texts["declaration/stages/household/household.bl"] == "second D′′\n"


def test_initial_writing_progress_is_named() -> None:
    assert cli._step_text({"step": "writing", "cycle": 0, "max_cycles": 2}) == (
        "step writing (Prose-to-Bellman-Sym), initial declaration"
    )


def test_older_record_keeps_its_round_trip_layout() -> None:
    from conftest import RECORDS, products_of

    record = RECORDS["not_converged"]
    job = {"id": "a" * 32, "state": record["status"], "result": products_of(record)}
    full = {**job, "result": record}
    texts = _folder_texts(job)
    iterates = _iterate_texts(full)

    assert texts["economics.md"].endswith(record["description"])
    assert "## The round-trip comparison" in report_text(job)
    assert "## Cycles and version" in report_text(job)
    assert "The job ran 2 cycles." in report_text(job)
    assert "iterates/cycle-1/round-trip-prose.md" in iterates
    assert "iterates/cycle-1/round-trip/example.bl" in iterates
    assert "iterates/initial/model-prose.md" not in iterates
