"""The acceptance file of AMD-MAT-010 on the side of the client: items 3 to 5
of the amendment's §7, the model folder, the report, and a paper's job and a
job with questions, against the stand-in of the service, whose jobs end with
the records of `conftest.py` and return them in the products view by default
and whole with `view=full`; the placement of the files of a model of two
stages and the refusal of a name outside the folder; `job wait`, which
prints the report's first two headings at a job's end (§5); and the
stand-in's reduction of each record, compared with the service's
`products_view` where the service's package is installed. Item 3 against the
service itself is in `test_acceptance.py`."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

import matsya
from conftest import (
    FIRST_STAGE,
    METHODS,
    MODEL_PROSE,
    NOTE,
    QUESTION,
    RECORDS,
    ROUND_TRIP_PROSE,
    ROUND_TRIP_STAGE,
    SHOCK,
    STAGE,
    TRELLIS_FILES,
    products_of,
)
from matsya.client import MatsyaClient

TIME = re.compile(r"^\d\d:\d\d:\d\d  ")
MODEL = "Household with firms"
# the report of the job of two cycles that reached its cycle limit, the job
# and the session named by <job> and <session>
REPORT = """# Report of the job

## The job

Household with firms · version 1 · job 1 · not_converged (<job>), session <session>

## Status

The job ended not_converged, with the reason cycle_limit_reached.

## Cycles and version

The job ran 2 cycles. It was built from version 1 of the session's text.

## What did not match

Each judge reads the two texts in both orders, and a heading agrees only when both readings count no omission, addition or contradiction.

### The prose-source-judge

The prose-source-judge compares the model prose with the source material.

The prose-source-judge agrees on every heading.

### The prose-roundtrip-judge

The prose-roundtrip-judge compares the round-trip prose with the model prose.

#### timing and information

| Order of the texts | Omissions | Additions | Contradictions |
|---|---|---|---|
| first | 0 | 0 | 0 |
| second | 0 | 0 | 1 |

The quoted sentences:

- "The agent observes x before choosing u."

#### transitions

| Order of the texts | Omissions | Additions | Contradictions |
|---|---|---|---|
| first | 1 | 0 | 0 |
| second | 0 | 0 | 0 |

The quoted sentences:

- "The continuation state a equals x_d plus the two components of u."

## The round-trip comparison

The round-trip stage files do not equal the written ones.

The first difference the comparison names, in which `left` is read from the written stage files and `right` from the round-trip ones:

- kind: `kernels`
- key: `kernel:arvl_to_dcsn.1`
- right_key: `kernel:arvl_to_dcsn.1`
- outcome: `differ`
- left: `x_d = x`
- right: `x_d = (2 * x)`
- stage: `4`
- witness: `{"point": {"x": 0.5}, "left": 0.5, "right": 1.0, "member": 0}`

## The writer's note

> The timing of the second control is left open.

## Cost

The language-model tokens charged, by role and for the job:

| Role | Calls | Input tokens | Output tokens |
|---|---|---|---|
| Model-prose-writer (`SourceMaterial_to_BellmanStageProse`) | 1 | 10 | 5 |
| Prose-to-Bellman-Sym (`BellmanStageProse_to_BellmanSYMDeclaration`) | 4 | 40 | 20 |
| Semantics-to-Prose (`ElaboratedSemanticObject_to_BellmanStageProse`) | 2 | 20 | 10 |
| prose-source-judge and prose-roundtrip-judge (`BellmanStageProse_judge`) | 6 | 60 | 30 |
| The job | 13 | 130 | 65 |
"""
# the report of the job of two cycles that converged in its second
CONVERGED_REPORT = """# Report of the job

## The job

Household with firms · version 1 · job 1 · converged (<job>), session <session>

## Status

The job ended converged, with the reason source_agreement_and_semantic_fixed_point.

## Cycles and version

The job ran 2 cycles. It was built from version 1 of the session's text.

## What did not match

The judges agree on every heading.

## The round-trip comparison

The round-trip stage files equal the written ones.

## Cost

The language-model tokens charged, by role and for the job:

| Role | Calls | Input tokens | Output tokens |
|---|---|---|---|
| Model-prose-writer (`SourceMaterial_to_BellmanStageProse`) | 1 | 10 | 5 |
| Prose-to-Bellman-Sym (`BellmanStageProse_to_BellmanSYMDeclaration`) | 4 | 40 | 20 |
| Semantics-to-Prose (`ElaboratedSemanticObject_to_BellmanStageProse`) | 2 | 20 | 10 |
| prose-source-judge and prose-roundtrip-judge (`BellmanStageProse_judge`) | 6 | 60 | 30 |
| The job | 13 | 130 | 65 |
"""


def _identifier(pattern: str, text: str) -> str:
    found = re.search(pattern, text, re.MULTILINE)
    assert found, text
    return found.group(1)


def _final(out: str) -> list[str]:
    """The lines a command printed, without the lines of progress."""
    return [line for line in out.splitlines() if not TIME.match(line)]


def _sent(stand_in) -> list[tuple[str, str, object]]:
    """The requests the stand-in received, as (method, path, body), and none
    of them kept for the next call."""
    sent = [(request["method"], request["path"], request["body"]) for request in stand_in.requests]
    stand_in.requests.clear()
    return sent


def _files(folder: Path) -> dict[str, str]:
    """Every file of a folder by its path within the folder, with its text."""
    return {
        path.relative_to(folder).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted(folder.rglob("*"))
        if path.is_file()
    }


def _ended_job(stand_in, run, tmp_path: Path, end: str) -> tuple[str, str]:
    """A job of a new session, `Household with firms`, holding one entry,
    which ends with the record `end` of `RECORDS`; the job's identifier and
    the session's."""
    status, out, _ = run("session", "new", MODEL)
    session_id = _identifier(rf"^Session ([0-9a-f]{{32}}): {MODEL}$", out)
    entry = tmp_path / "entry.md"
    entry.write_text("A household works for a firm.\n", encoding="utf-8")
    assert run("session", "add", session_id, str(entry))[0] == 0
    stand_in.next_ends.append(end)
    status, out, _ = run("job", "submit", "--session", session_id)
    job_id = _identifier(r"^Job ([0-9a-f]{32}): queued$", out)
    assert run("job", "wait", job_id, "--interval", "0")[0] == 0
    stand_in.requests.clear()
    return job_id, session_id


def test_item_3_the_model_folder_with_and_without_the_iterates(stand_in, run, tmp_path) -> None:
    """`job files` writes, from one request for the products view, the model
    prose with its front matter, the report, the last cycle's stage file,
    methods file and open note in the stage's folder, and the products view
    as received; a folder that is not empty is refused before any request
    unless `--overwrite` is given, which leaves the other files; and
    `--all-iterates` adds, from the full view, every cycle's files, prose and
    verdicts and the full record."""
    job_id, session_id = _ended_job(stand_in, run, tmp_path, "not_converged")
    client = MatsyaClient(stand_in.token, stand_in.url)
    products, full = client.job(job_id), client.job(job_id, view="full")
    assert products["result"] == products_of(RECORDS["not_converged"])
    assert full["result"] == RECORDS["not_converged"]
    stand_in.requests.clear()

    folder = tmp_path / "proposed"
    status, out, err = run("job", "files", job_id, str(folder))
    assert (status, err) == (0, "")
    assert _sent(stand_in) == [("GET", f"/v1/model-iterations/{job_id}?view=products", None)]
    assert out.splitlines() == [
        f"Wrote 6 files to {folder}:",
        "  economics.md",
        "  report.md",
        "  declaration/stages/example/example.bl",
        "  declaration/stages/example/methods.yml",
        "  declaration/stages/example/example.md",
        "  record.json",
    ]
    expected = {
        "declaration/stages/example/example.bl": STAGE,
        "declaration/stages/example/example.md": NOTE,
        "declaration/stages/example/methods.yml": METHODS,
        "economics.md": (
            f'---\njob: "{job_id}"\nlabel: "{MODEL} · version 1 · job 1 · not_converged"\n'
            f'session: "{session_id}"\nversion: 1\ndate: 2026-10-09\n---\n\n' + MODEL_PROSE
        ),
        "record.json": json.dumps(products, indent=2, ensure_ascii=False) + "\n",
        "report.md": REPORT.replace("<job>", job_id).replace("<session>", session_id),
    }
    assert _files(folder) == expected

    # a folder that is not empty is refused before any request
    status, out, err = run("job", "files", job_id, str(folder))
    assert (status, out, stand_in.requests) == (1, "", [])
    assert err == (
        f"Error: {folder} is not empty; name a new or empty folder, or write into it with "
        "--overwrite (overwrite=True in Python), which replaces the files of the same names "
        "and leaves the others.\n"
    )
    (folder / "report.md").write_text("edited\n", encoding="utf-8")
    (folder / "mine.md").write_text("kept\n", encoding="utf-8")
    status, _, _ = run("job", "files", job_id, str(folder), "--overwrite")
    assert status == 0 and _files(folder) == {**expected, "mine.md": "kept\n"}

    # every iterate, for training; --json prints the products view, the
    # answer record.json holds
    training = tmp_path / "training"
    stand_in.requests.clear()
    status, out, _ = run("job", "files", job_id, str(training), "--all-iterates", "--json")
    assert status == 0 and json.loads(out) == products
    assert _sent(stand_in) == [
        ("GET", f"/v1/model-iterations/{job_id}?view=products", None),
        ("GET", f"/v1/model-iterations/{job_id}?view=full", None),
    ]
    written = _files(training)
    assert {path: text for path, text in written.items() if not path.startswith("iterates/")} == expected
    iterates = {path: text for path, text in written.items() if path.startswith("iterates/")}
    first, second = RECORDS["not_converged"]["cycles"]
    assert iterates == {
        "iterates/cycle-1/cycle.json": iterates["iterates/cycle-1/cycle.json"],
        "iterates/cycle-1/example.bl": FIRST_STAGE,
        "iterates/cycle-1/model-prose.md": MODEL_PROSE,
        "iterates/cycle-1/note.md": NOTE,
        "iterates/cycle-1/round-trip-prose.md": ROUND_TRIP_PROSE,
        "iterates/cycle-1/round-trip/example.bl": ROUND_TRIP_STAGE,
        "iterates/cycle-2/cycle.json": iterates["iterates/cycle-2/cycle.json"],
        "iterates/cycle-2/example.bl": STAGE,
        "iterates/cycle-2/methods.yml": METHODS,
        "iterates/cycle-2/model-prose.md": MODEL_PROSE,
        "iterates/cycle-2/note.md": NOTE,
        "iterates/cycle-2/round-trip-prose.md": ROUND_TRIP_PROSE,
        "iterates/cycle-2/round-trip/example.bl": ROUND_TRIP_STAGE,
        "iterates/record-full.json": json.dumps(full, indent=2, ensure_ascii=False) + "\n",
    }
    # cycle.json holds the rest of the cycle's record, its judging and its
    # comparison among it, and not the texts that stand beside it
    for number, cycle in ((1, first), (2, second)):
        assert json.loads(iterates[f"iterates/cycle-{number}/cycle.json"]) == {
            **cycle,
            "writing": {key: value for key, value in cycle["writing"].items() if key != "files"},
            "prose_writing": {"form": cycle["prose_writing"]["form"]},
            "reconstruction": {key: value for key, value in cycle["reconstruction"].items() if key != "files"},
        }


def test_item_4_the_report(stand_in, run, tmp_path) -> None:
    """The report holds the headings of §4 in order; with judges that
    disagree, one subsection per judge with the headings on which a reading
    disagrees, its counts in both orders and its quoted sentences (the
    report `REPORT` of `test_item_3`); and with judges that agree, the fixed
    sentence. Every sentence is the record's content or a fixed sentence;
    the module's `report_text` composes it from the job as `record.json`
    holds it, and `job wait` prints its first two headings at the job's
    end."""
    job_id, session_id = _ended_job(stand_in, run, tmp_path, "converged")
    folder = tmp_path / "proposed"
    assert run("job", "files", job_id, str(folder))[0] == 0
    report = (folder / "report.md").read_text(encoding="utf-8")
    assert report == CONVERGED_REPORT.replace("<job>", job_id).replace("<session>", session_id)
    assert sorted(_files(folder)) == [
        "declaration/stages/example/example.bl",
        "economics.md",
        "record.json",
        "report.md",
    ]
    held = json.loads((folder / "record.json").read_text(encoding="utf-8"))
    assert matsya.report_text(held) == report
    for text in (report, REPORT):
        assert [line for line in text.splitlines() if line.startswith("## ")] == [
            "## The job",
            "## Status",
            "## Cycles and version",
            "## What did not match",
            "## The round-trip comparison",
            *(["## The writer's note"] if text is REPORT else []),
            "## Cost",
        ]

    # job wait and job status print the content of the first two headings
    status, out, _ = run("job", "wait", job_id, "--interval", "0")
    assert out.splitlines() == [
        f"{MODEL} · version 1 · job 1 · converged ({job_id}), session {session_id}",
        "The job ended converged, with the reason source_agreement_and_semantic_fixed_point.",
        "Files of the last cycle: example.bl, note.md",
        f"Write the model folder and its report with: matsya job files {job_id} <folder>",
    ]
    assert run("job", "status", job_id)[1] == out

    # a label given to report_text replaces the job's own
    label = {**held["label"], "text": "a label given"}
    assert matsya.report_text(held, label).splitlines()[4] == f"a label given ({job_id}), session {session_id}"


def test_item_5_a_papers_job_and_a_job_with_questions(stand_in, run, tmp_path) -> None:
    """The report of a paper's job states the prose-source-judge's
    disagreement with the paper, with its counts and quotes; the report of a
    job that ended with questions states them, and the folder of a record
    without model prose holds no `economics.md`; a writer's note that the
    record marks unresolved and holds no text of is stated by a fixed
    sentence."""
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"%PDF-1.4\nscripted text\n")
    stand_in.next_ends.append("paper")
    status, out, _ = run("job", "submit", str(pdf))
    paper_job = _identifier(r"^Job ([0-9a-f]{32}): queued$", out)
    assert run("job", "wait", paper_job, "--interval", "0")[0] == 0
    folder = tmp_path / "paper"
    assert run("job", "files", paper_job, str(folder))[0] == 0
    assert sorted(_files(folder)) == ["economics.md", "record.json", "report.md"]
    report = (folder / "report.md").read_text(encoding="utf-8")
    start, end = report.index("## What did not match"), report.index("## The round-trip comparison")
    assert report.splitlines()[4:11] == [
        f"not_converged ({paper_job}), no session",
        "",
        "## Status",
        "",
        "The job ended not_converged, with the reason paper_description_differs_from_source.",
        "",
        "## Cycles and version",
    ]
    assert "The job ran no cycle. The job has no session, so its text has no version." in report
    assert report[start:end] == (
        "## What did not match\n\n"
        "Each judge reads the two texts in both orders, and a heading agrees only when both readings "
        "count no omission, addition or contradiction.\n\n"
        "### The prose-source-judge\n\n"
        "The prose-source-judge compares the model prose with the source material.\n\n"
        "#### shocks\n\n"
        "| Order of the texts | Omissions | Additions | Contradictions |\n"
        "|---|---|---|---|\n"
        "| first | 1 | 0 | 0 |\n"
        "| second | 0 | 1 | 0 |\n\n"
        "The quoted sentences:\n\n"
        f'- "{SHOCK}"\n\n'
        "### The prose-roundtrip-judge\n\n"
        "The prose-roundtrip-judge compares the round-trip prose with the model prose.\n\n"
        "The record holds no report of the prose-roundtrip-judge.\n\n"
    )

    # a job of a session that ended with a question
    job_id, session_id = _ended_job(stand_in, run, tmp_path, "needs_input")
    folder = tmp_path / "questions"
    assert run("job", "files", job_id, str(folder))[0] == 0
    assert sorted(_files(folder)) == ["record.json", "report.md"]
    report = (folder / "report.md").read_text(encoding="utf-8")
    assert report.endswith(
        "## The round-trip comparison\n\n"
        "The record holds no round-trip comparison.\n\n"
        "## Questions\n\n"
        f"1. {QUESTION}\n\n"
        "## Cost\n\n"
        "The record holds no account of the language-model tokens charged.\n"
    )

    # a note the record marks unresolved and holds no text of
    held = json.loads((folder / "record.json").read_text(encoding="utf-8"))
    held["result"]["last_cycle"] = {
        "files": {"example.bl": STAGE, "note.md": " \n"},
        "judging": None,
        "comparison": None,
        "citations_supported": None,
        "unresolved_note": True,
    }
    assert (
        "## The writer's note\n\n"
        "The record marks the writer's note as unresolved, and the products hold no text of it.\n"
    ) in matsya.report_text(held)


def test_the_files_of_two_stages_are_placed_by_name_and_a_name_outside_is_refused(stand_in, run, tmp_path) -> None:
    """The files of a model of two stages stand in the layout of the
    applications: each stage file in its stage's folder, the period,
    trellis, calibration and settings files under `declaration/`, a stage's
    methods file in its folder, and the note, which belongs to no single
    stage, as `declaration/notes.md`; the report states the ceiling's
    refusal and the quotation the stage files lack. A record that names a
    file outside the folder writes nothing."""
    job_id, _ = _ended_job(stand_in, run, tmp_path, "trellis")
    folder = tmp_path / "trellis"
    assert run("job", "files", job_id, str(folder))[0] == 0
    written = _files(folder)
    assert {path: text for path, text in written.items() if path.startswith("declaration/")} == {
        "declaration/calibration/base.yml": TRELLIS_FILES["calibration/base.yml"],
        "declaration/notes.md": TRELLIS_FILES["note.md"],
        "declaration/period.yml": TRELLIS_FILES["period.yml"],
        "declaration/settings/base.yml": TRELLIS_FILES["settings/base.yml"],
        "declaration/stages/firm/firm.bl": TRELLIS_FILES["firm.bl"],
        "declaration/stages/household/household.bl": TRELLIS_FILES["household.bl"],
        "declaration/stages/household/methods.yml": TRELLIS_FILES["stages/household/methods.yml"],
        "declaration/trellis.yml": TRELLIS_FILES["trellis.yml"],
    }
    report = written["report.md"]
    assert (
        "### The quotations of the stage files\n\n"
        "Not every block of the last cycle's stage files quotes, in a `# from:` line, a sentence that "
        "occurs in the model prose, or the stage files hold no block.\n\n"
        "## The round-trip comparison\n\n"
        "The record holds no round-trip comparison.\n\n"
        "## The writer's note\n\n"
        "> The wage w is taken as given.\n"
    ) in report
    assert report.endswith(
        "| The job | 4 | 40 | 20 |\n\n"
        "A language-model token ceiling refused call 5, of the role "
        "`ElaboratedSemanticObject_to_BellmanStageProse`, under the condition `job_input_tokens`: "
        "40 tokens were charged, the call would have added 120, and the ceiling is 100.\n"
    )

    job_id, _ = _ended_job(stand_in, run, tmp_path, "outside")
    folder = tmp_path / "outside"
    status, out, err = run("job", "files", job_id, str(folder))
    assert (status, out) == (1, "")
    assert err == (
        f"Error: The record of job {job_id} names a file '../outside.bl' in the last cycle's "
        "writing that the client does not write: a name must be a plain name, with no folder part "
        "and not beginning with a dot, or calibration/<file>, settings/<file> or "
        "stages/<key>/methods.yml.\n"
    )
    assert not folder.exists()


def test_the_stand_in_reduces_each_record_as_the_service_does() -> None:
    """The stand-in's products view of each record of `RECORDS` equals the
    service's `products_view` of it, so that the tests against the stand-in
    read what the service returns."""
    processor = pytest.importorskip("matsya_service.processor")
    for name, record in RECORDS.items():
        assert products_of(record) == processor.products_view(record), name
