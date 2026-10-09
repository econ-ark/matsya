"""The acceptance items of the brief of unit (g),
the brief of unit (g) of the Matsya specification, §3 (the client package a user installs):
item 1 by the package's metadata and imports, and items 2 to 4 against the
Matsya service of the test configuration on the loopback address, with a
scripted caller in place of the model provider. Item 2's job is submitted
from a description file and so runs from a session of its own, named after
the file (AAS, 9 October 2026, D-G25), whose listing the test reads. Item 5,
the user note, lies outside this package; item 6 is the run of the existing
suites. Item 2 writes the model folder and the report of AMD-MAT-010 §§4
and 5 of the converged job, with and without its iterates. The last two
tests run the client's commands of AMD-MAT-008 §4, the cancellation, the
selection and the labels, and the client's part of AMD-MAT-009 §5, a job
that a turn starts and `ask --follow` writes, against the same service."""

from __future__ import annotations

import ast
import json
import re
import sys
import threading
import urllib.request
from pathlib import Path

import pytest

import matsya
from conftest import PASSAGE
from matsya.client import AuthenticationError, MatsyaClient

CLIENT = Path(__file__).resolve().parents[1]
TIME = re.compile(r"^\d\d:\d\d:\d\d  ")
# the service's libraries warn of their own deprecations under Python 3.14;
# a warning of the client is still shown
pytestmark = [
    pytest.mark.filterwarnings(f"ignore::{category}:{module}")
    for category in ("DeprecationWarning", "PendingDeprecationWarning")
    for module in ("fastapi", "starlette", "uvicorn", "uvloop", "websockets")
]


def test_item_1_the_package_needs_nothing_beyond_python() -> None:
    tomllib = pytest.importorskip("tomllib")
    import matsya

    project = tomllib.loads((CLIENT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert "dependencies" not in project and "optional-dependencies" not in project
    assert project["scripts"] == {"matsya": "matsya.cli:main"}
    assert project["version"] == matsya.__version__
    imported = set()
    for path in (CLIENT / "src" / "matsya").glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                imported |= {alias.name.split(".")[0] for alias in node.names}
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                imported.add(node.module.split(".")[0])
    assert imported - set(sys.stdlib_module_names) == {"matsya"}


def test_item_2_each_command_against_the_service_of_the_test_configuration(service, run, tmp_path) -> None:
    status, out, _ = run("index")
    assert status == 0 and "Embedding model: stand-in-embedding-v1" in out.splitlines()

    status, out, _ = run("search", "What does a stage file name?", "--collections", "repository", "--limit", "2")
    assert status == 0 and "[1] docs/Bellman-Sym/01-stage.md, The stage (repository, score" in out
    passage_id = re.search(r"^    passage ([0-9a-f]{64})$", out, re.MULTILINE).group(1)

    description = tmp_path / "model.md"
    description.write_text(service.description, encoding="utf-8")
    status, out, _ = run("job", "submit", str(description), "--max-cycles", "1")
    job_session = re.search(r"^Session ([0-9a-f]{32}): model$", out, re.MULTILINE).group(1)
    job_id = re.search(r"^Job ([0-9a-f]{32}): queued$", out, re.MULTILINE).group(1)
    assert f"Entry 1: the text of {description}" in out.splitlines()
    status, out, _ = run("job", "wait", job_id, "--interval", "0.05")
    assert status == 0
    assert [line for line in out.splitlines() if not TIME.match(line)][:3] == [
        f"model · version 1 · job 1 · converged ({job_id}), session {job_session}",
        "The job ended converged, with the reason source_agreement_and_semantic_fixed_point.",
        "Files of the last cycle: example.bl, note.md",
    ]
    assert any(line.endswith("(Prose-to-Bellman-Sym), cycle 1 of 1") for line in out.splitlines() if TIME.match(line))

    # the session holds the file's text as its one entry and lists the job
    # by its label
    status, out, _ = run("session", "show", job_session)
    lines = out.splitlines()
    assert status == 0 and lines[0] == f"Session {job_session}: model"
    assert lines[lines.index("Jobs:") + 1] == f"  model · version 1 · job 1 · converged ({job_id})"
    entries = lines[lines.index("Entries:") + 1 :]
    assert entries[0] == "  1. user"
    assert "\n".join(line[5:] for line in entries[1:]) == service.description.strip()

    # the model folder of the converged job: its note says none, so no note
    # stands beside the stage
    folder = tmp_path / "proposed"
    status, out, _ = run("job", "files", job_id, str(folder))
    assert status == 0
    assert sorted(path.relative_to(folder).as_posix() for path in folder.rglob("*") if path.is_file()) == [
        "declaration/stages/example/example.bl",
        "economics.md",
        "record.json",
        "report.md",
    ]
    job = json.loads((folder / "record.json").read_text(encoding="utf-8"))
    assert (job["id"], job["result"]["status"], job["result"]["cycles_run"]) == (job_id, "converged", 1)
    assert "cycles" not in job["result"] and "calls" not in job["result"]
    written = job["result"]["last_cycle"]["files"]
    assert written["note.md"].strip() == "none"
    stage = folder / "declaration" / "stages" / "example" / "example.bl"
    assert stage.read_text(encoding="utf-8") == written["example.bl"]
    assert (folder / "economics.md").read_text(encoding="utf-8") == (
        f'---\njob: "{job_id}"\nlabel: "model · version 1 · job 1 · converged"\n'
        f'session: "{job_session}"\nversion: 1\ndate: {job["updated_at"][:10]}\n---\n\n'
        + service.description
    )
    report = (folder / "report.md").read_text(encoding="utf-8").splitlines()
    assert [line for line in report if line.startswith("## ")] == [
        "## The job",
        "## Status",
        "## Cycles and version",
        "## What did not match",
        "## The round-trip comparison",
        "## Cost",
    ]
    assert "The judges agree on every heading." in report
    assert "The round-trip stage files equal the written ones." in report
    assert "The job ran 1 cycle. It was built from version 1 of the session's text." in report

    # every iterate, from the full view, for training
    training = tmp_path / "training"
    status, out, _ = run("job", "files", job_id, str(training), "--all-iterates")
    assert status == 0
    full = json.loads((training / "iterates" / "record-full.json").read_text(encoding="utf-8"))
    (cycle,) = full["result"]["cycles"]
    held = training / "iterates" / "cycle-1"
    assert (held / "example.bl").read_text(encoding="utf-8") == cycle["writing"]["files"]["example.bl"]
    assert (held / "model-prose.md").read_text(encoding="utf-8") == full["result"]["description"]
    assert (held / "round-trip-prose.md").read_text(encoding="utf-8") == cycle["prose_writing"]["description"]
    assert (held / "round-trip" / "example.bl").read_text(encoding="utf-8") == (
        cycle["reconstruction"]["files"]["example.bl"]
    )
    rest = json.loads((held / "cycle.json").read_text(encoding="utf-8"))
    assert (rest["judging"], rest["comparison"]) == (cycle["judging"], cycle["comparison"])

    status, out, _ = run("session", "new", "a household")
    session_id = re.search(r"^Session ([0-9a-f]{32}): a household$", out, re.MULTILINE).group(1)
    entry = tmp_path / "entry.md"
    entry.write_text("A household saves out of cash on hand.\n", encoding="utf-8")
    status, out, _ = run("session", "add", session_id, str(entry))
    assert out.startswith(f"Appended entry 1 (user) to session {session_id}; the session's revision is 1.")

    quote = "A stage file names its arrival, decision and continuation fields"
    service.caller.replies.append(
        (
            service.role,
            json.dumps(
                {
                    "status": "answered",
                    "answer": "A stage file names its fields [1].",
                    "citations": [
                        {"address": {"source": "index", "target": f"passage:{passage_id}"}, "quote": quote}
                    ],
                    "decisions": [],
                }
            ),
        )
    )
    status, out, err = run("ask", session_id, "What does a stage file name?", "--interval", "0.05")
    assert status == 0, err
    assert "A stage file names its fields [1]." in out.splitlines()
    assert "  [1] docs/Bellman-Sym/01-stage.md, The stage" in out
    assert f'      "{quote}"' in out

    status, out, _ = run("session", "show", session_id)
    assert status == 0
    assert "  2. user" in out
    assert re.search(r"^  3\. answer, from turn [0-9a-f]{32}, replies to 2$", out, re.MULTILINE)
    service.caller.assert_finished()


def test_item_3_a_missing_or_wrong_matsya_token_is_refused(service, run, monkeypatch) -> None:
    with pytest.raises(AuthenticationError, match="A Matsya bearer token is required") as refused:
        MatsyaClient("", service.url).index()
    assert refused.value.status == 401
    wrong = "msy_" + "f" * 32
    monkeypatch.setenv("MATSYA_TOKEN", wrong)
    status, out, err = run("search", "stage", "--json")
    assert (status, out) == (1, "")
    assert err.startswith(
        "Error: The service refused the request (401): The Matsya bearer token is invalid."
    )
    assert wrong not in out + err and service.token not in out + err


def test_item_4_json_prints_the_service_answer_unchanged(service, run) -> None:
    status, out, _ = run("index", "--json")
    request = urllib.request.Request(
        service.url + "/v1/index", headers={"Authorization": f"Bearer {service.token}"}
    )
    with urllib.request.urlopen(request, timeout=30) as answer:
        text = answer.read().decode("utf-8")
    assert status == 0 and out == text + "\n"
    status, out, _ = run("search", "stage file", "--collections", "repository", "--json")
    assert json.loads(out)["passages"][0]["path"] == PASSAGE["path"]


def test_a_queued_job_of_a_session_is_cancelled_and_listed_by_its_label(service, run, tmp_path) -> None:
    """AMD-MAT-008 §4 against the service of the test configuration: a job of
    a session, held in the queue while the job runner's two workers are
    occupied, is cancelled by `job cancel` and never runs; the session's
    listing names each job by its label; the converged job is selected and
    a question reads it; and cancelling that ended job is refused with 409."""
    description = tmp_path / "model.md"
    description.write_text(service.description, encoding="utf-8")
    status, out, _ = run("job", "submit", str(description), "--max-cycles", "1")
    session_id = re.search(r"^Session ([0-9a-f]{32}): model$", out, re.MULTILINE).group(1)
    built = re.search(r"^Job ([0-9a-f]{32}): queued$", out, re.MULTILINE).group(1)
    status, out, _ = run("job", "wait", built, "--interval", "0.05")
    assert status == 0
    assert "The job ended converged, with the reason source_agreement_and_semantic_fixed_point." in out

    # the job runner's two workers are occupied, so that the next job of the
    # session stays queued until they are released
    runner = service.application.state.runner
    release = threading.Event()
    occupied = [threading.Event(), threading.Event()]

    def occupy(started: threading.Event) -> None:
        started.set()
        release.wait(30)

    calls = len(service.caller.called)
    try:
        for started in occupied:
            runner.executor.submit(occupy, started)
        assert all(started.wait(10) for started in occupied)
        status, out, _ = run("job", "submit", "--session", session_id)
        queued = re.search(r"^Job ([0-9a-f]{32}): queued$", out, re.MULTILINE).group(1)
        status, out, _ = run("job", "status", queued)
        assert out.splitlines() == ["model · job 2 · queued", f"Job {queued}: queued"]
        status, out, err = run("job", "cancel", queued)
        assert (status, err) == (0, "")
        assert out.splitlines() == ["model · job 2 · cancelled", f"Job {queued}: cancelled"]
    finally:
        release.set()
    # two tasks that wait for each other run only once both workers are
    # free, that is, once the queued job's start has run and found the job
    # cancelled
    barrier = threading.Barrier(2, timeout=10)
    for done in [runner.executor.submit(barrier.wait) for _ in range(2)]:
        done.result(timeout=10)
    status, out, _ = run("job", "status", queued, "--json")
    held = json.loads(out)
    assert (held["state"], held["cancel_requested"], held["events"]) == ("cancelled", True, [])
    assert "result" not in held and len(service.caller.called) == calls

    # the listing names each job by its label, in the order of creation
    status, out, _ = run("session", "show", session_id)
    lines = out.splitlines()
    at = lines.index("Jobs:")
    assert lines[at + 1 : at + 3] == [
        f"  model · version 1 · job 1 · converged ({built})",
        f"  model · job 2 · cancelled ({queued})",
    ]

    # the converged job is selected, and a question reads it
    status, out, _ = run("session", "select", session_id, built)
    assert out.splitlines()[0] == (
        f"Selected job of session {session_id}: model · version 1 · job 1 · converged ({built})"
    )
    status, out, _ = run("session", "show", session_id)
    assert f"Selected job: model · version 1 · job 1 · converged ({built})" in out.splitlines()
    service.caller.replies.append(
        (
            service.role,
            json.dumps(
                {
                    "status": "answered",
                    "answer": "The model has one household.",
                    "citations": [],
                    "decisions": [],
                }
            ),
        )
    )
    status, out, err = run("ask", session_id, "What does the model contain?", "--interval", "0.05")
    assert status == 0, err
    assert [line for line in out.splitlines() if not TIME.match(line)][:2] == [
        f"Answer from model · version 1 · job 1 · converged ({built})",
        "The model has one household.",
    ]

    # a job that has ended cannot be cancelled
    status, out, err = run("job", "cancel", built)
    assert (status, out, err) == (
        1,
        "",
        "Error: The service refused the request (409): The job has ended.\n",
    )
    service.caller.assert_finished()


def test_a_turn_starts_a_job_that_follow_waits_for_and_writes(service, run, tmp_path) -> None:
    """AMD-MAT-009 §5 against the service of the test configuration: the
    conversation role answers a question that asks for a job with
    `submit_job`, the turn runner starts the job from the session's text
    with the question, `ask` prints the job's line, and with `--follow` it
    waits for the job as `job wait` does and writes the converged job's
    model folder as `job files` does."""
    status, out, _ = run("session", "new", "a household")
    session_id = re.search(r"^Session ([0-9a-f]{32}): a household$", out, re.MULTILINE).group(1)
    description = tmp_path / "model.md"
    description.write_text(service.description, encoding="utf-8")
    status, _, _ = run("session", "add", session_id, str(description))
    assert status == 0
    started = "A job of architect mode is being started from version 2 of this session's text."
    service.caller.replies.appendleft(
        (
            service.role,
            json.dumps(
                {
                    "status": "answered",
                    "answer": started,
                    "citations": [],
                    "decisions": [],
                    "submit_job": {"max_cycles": 1},
                }
            ),
        )
    )
    folder = tmp_path / "proposed"
    status, out, err = run(
        "ask", session_id, "Submit this as a job.", "--follow", str(folder), "--interval", "0.05"
    )
    assert status == 0, err
    lines = [line for line in out.splitlines() if not TIME.match(line)]
    job_id = re.search(r"\(([0-9a-f]{32})\); follow it with", out).group(1)
    assert lines == [
        started,
        "",
        f"Job 1 started from version 2 of this session's text ({job_id}); "
        f"follow it with: matsya job wait {job_id}",
        f"a household · version 2 · job 1 · converged ({job_id}), session {session_id}",
        "The job ended converged, with the reason source_agreement_and_semantic_fixed_point.",
        "Files of the last cycle: example.bl, note.md",
        f"Write the model folder and its report with: matsya job files {job_id} <folder>",
        f"Wrote 4 files to {folder}:",
        "  economics.md",
        "  report.md",
        "  declaration/stages/example/example.bl",
        "  record.json",
    ]

    # the job was started by the turn, from the session's text with the
    # question, and the folder holds its products
    turn_id = matsya.session(session_id)["turns"][-1]
    job = json.loads((folder / "record.json").read_text(encoding="utf-8"))
    assert (job["id"], job["started_by"], job["revision"], job["entry_numbers"]) == (job_id, turn_id, 2, [1, 2])
    stage = folder / "declaration" / "stages" / "example" / "example.bl"
    assert stage.read_text(encoding="utf-8") == job["result"]["last_cycle"]["files"]["example.bl"]
    service.caller.assert_finished()
