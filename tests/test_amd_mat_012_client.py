"""The acceptance file of AMD-MAT-012 on the side of the client: a paper is
sent as its text, in Markdown or LaTeX, and a PDF is refused (§2; items 1 to
3 of §4). Against the stand-in of the service: a PDF, known by its name or
its first bytes, is refused by `matsya job submit` and `matsya session add`
with exit status 2 and by `start_job` with `ValueError`, each with the fixed
sentence, before any request, and the argument that sent a PDF is gone;
`matsya job submit <file> --paper` appends the paper to the job's session as
an entry of the kind `paper` and starts the job from that session, whose
label the job carries, and with `--no-session` sends the paper as the job's
source, its text unchanged; `start_job` and `submit_job` take `paper=True`;
and the stand-in refuses a paper in the earlier forms with the service's
sentence and records a paper's `references`. The former names of the PDF's
field, of the argument that sent it and of the record's page references are
looked for in the client's files. Against the service of the test
configuration, a Markdown paper submitted with `--paper --target stage`
runs from its session as a paper, and its record, in the schema
`matsya-model-iteration/6`, holds its references."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
from pathlib import Path

import pytest

import matsya
from conftest import (
    EARLIER_PAPER_FORMS,
    LATEX,
    PAPER,
    PAPER_AS_TEXT,
    PAPER_REFERENCES,
    RECORDS,
    SCHEMA,
    SERVICE_TESTS,
)
from matsya.client import PDF_REFUSAL, MatsyaClient, MatsyaError

CLIENT = Path(__file__).resolve().parents[1]
GUIDE = CLIENT.parents[2] / "docs" / "matsya" / "user-guide"
# the two pages of the user guide that describe a paper
PAGES = ("01-working-from-the-command-line.md", "01a-the-python-module.md")
TIME = re.compile(r"^\d\d:\d\d:\d\d  ")
# the service's libraries warn of their own deprecations under Python 3.14;
# a warning of the client is still shown
pytestmark = [
    pytest.mark.filterwarnings(f"ignore::{category}:{module}")
    for category in ("DeprecationWarning", "PendingDeprecationWarning")
    for module in ("fastapi", "starlette", "uvicorn", "uvloop", "websockets")
]


def _identifier(pattern: str, text: str) -> str:
    found = re.search(pattern, text, re.MULTILINE)
    assert found, text
    return found.group(1)


def _final(out: str) -> list[str]:
    """The lines a command printed, without the lines of progress."""
    return [line for line in out.splitlines() if not TIME.match(line)]


def _sent(stand_in) -> list[tuple[str, str, object]]:
    """The requests the stand-in received, as (method, path, body), and
    none of them kept for the next call."""
    sent = [(request["method"], request["path"], request["body"]) for request in stand_in.requests]
    stand_in.requests.clear()
    return sent


def test_item_3_a_pdf_is_refused_before_any_request(stand_in, run, tmp_path) -> None:
    """A PDF, by its name or by its first bytes, with or without `--paper`
    and whatever names the session, is refused by `job submit` and by
    `session add` with exit status 2 and the fixed sentence, and by
    `start_job` with `ValueError` and the same sentence; `submit_job` no
    longer takes the argument that sent a PDF. No request reaches the
    stand-in and no session is created."""
    assert PDF_REFUSAL == "A paper is sent as Markdown or LaTeX text; convert the PDF first."
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"%PDF-1.4\nscripted text\n")
    renamed = tmp_path / "paper.md"
    renamed.write_bytes(pdf.read_bytes())
    for arguments in (
        ("job", "submit", str(pdf), "--target", "stage"),
        ("job", "submit", str(pdf), "--paper", "--target", "stage"),
        ("job", "submit", str(pdf), "--paper", "--no-session", "--target", "stage"),
        ("job", "submit", str(pdf), "--session", "0" * 32, "--target", "stage"),
        ("job", "submit", str(pdf), "--paper", "--name", "a paper", "--target", "stage"),
        ("job", "submit", str(renamed), "--paper", "--target", "stage"),
        ("session", "add", "0" * 32, str(pdf), "--kind", "paper"),
        ("session", "add", "0" * 32, str(renamed)),
    ):
        status, out, err = run(*arguments)
        assert (status, out, err.splitlines()[-1]) == (2, "", f"matsya: error: {PDF_REFUSAL}"), arguments

    client = MatsyaClient(stand_in.token, stand_in.url)
    for start in (
        lambda: matsya.start_job(pdf, target="stage"),
        lambda: matsya.start_job(pdf, no_session=True, paper=True, target="stage"),
        lambda: client.start_job(pdf, session="0" * 32, paper=True, target="stage"),
        lambda: client.start_job(renamed, name="a paper", paper=True, target="stage"),
    ):
        with pytest.raises(ValueError) as refused:
            start()
        assert str(refused.value) == PDF_REFUSAL
    # the argument that sent a PDF is removed, with no form kept in its place
    removed = {"pdf" + "_path": pdf}
    with pytest.raises(TypeError):
        matsya.submit_job(target="stage", **removed)
    with pytest.raises(TypeError):
        client.submit_job(target="stage", **removed)
    assert stand_in.requests == [] and stand_in.sessions == {}


def test_item_2_a_paper_is_appended_to_the_session_as_a_paper_entry(stand_in, run, tmp_path) -> None:
    """`job submit <file> --paper` creates a session named after the file,
    appends the paper's text to it as an entry of the kind `paper` and
    starts the job from that session, whose label the job carries and in
    which its question stands after the paper. A LaTeX paper is appended to
    an existing session by `start_job` with `paper=True`, and a plain-text
    file without the mark is appended as a description."""
    paper = tmp_path / "saving.md"
    paper.write_text(PAPER, encoding="utf-8")
    status, out, _ = run("job", "submit", str(paper), "--paper", "--target", "stage")
    assert status == 0
    session_id = json.loads(stand_in.answers[0])["id"]
    job_id = json.loads(stand_in.answers[-1])["id"]
    assert _sent(stand_in) == [
        ("POST", "/v1/sessions", {"name": "saving"}),
        ("POST", f"/v1/sessions/{session_id}/entries", {"kind": "paper", "text": PAPER}),
        ("POST", "/v1/model-iterations", {"session": session_id, "target": "stage"}),
    ]
    assert out.splitlines() == [
        f"Session {session_id}: saving",
        f"Entry 1 (paper): the text of {paper}",
        f"Job {job_id}: queued",
        f"Follow it with: matsya job wait {job_id}",
        f"The session, where the job's questions and your replies are kept: matsya session show {session_id}",
    ]
    status, out, _ = run("job", "wait", job_id, "--interval", "0")
    assert _final(out)[0] == (
        f"saving · stage · version 1 · job 1 · needs_input ({job_id}), session {session_id}"
    )
    status, out, _ = run("session", "show", session_id)
    lines = out.splitlines()
    assert "  1. paper" in lines and f"  2. question, from job {job_id}" in lines

    stand_in.requests.clear()
    latex = tmp_path / "saving.tex"
    latex.write_text(LATEX, encoding="utf-8")
    notes = tmp_path / "notes.txt"
    notes.write_text("Income is paid at the start of the period.\n", encoding="utf-8")
    appended = [
        matsya.start_job(latex, session=session_id, paper=True, target="stage"),
        matsya.start_job(notes, session=session_id, target="stage"),
    ]
    assert [(held["session"], held["entry"]["entry"]["kind"]) for held in appended] == [
        (None, "paper"),
        (None, "user"),
    ]
    assert _sent(stand_in) == [
        ("POST", f"/v1/sessions/{session_id}/entries", {"kind": "paper", "text": LATEX}),
        ("POST", "/v1/model-iterations", {"session": session_id, "target": "stage"}),
        (
            "POST",
            f"/v1/sessions/{session_id}/entries",
            {"kind": "user", "text": "Income is paid at the start of the period.\n"},
        ),
        ("POST", "/v1/model-iterations", {"session": session_id, "target": "stage"}),
    ]


def test_item_1_a_paper_with_no_session_is_sent_as_its_text(stand_in, run, tmp_path) -> None:
    """`job submit <file> --paper --no-session` sends the file's text
    unchanged as the job's source of the kind `paper`, and without the mark
    the same file is sent as a description; `start_job` with
    `no_session=True` and `submit_job` with `paper=True` send the same
    source, and `paper=True` with a session alone is refused before any
    request. `job submit --help` names the mark."""
    latex = tmp_path / "saving.tex"
    latex.write_text(LATEX, encoding="utf-8")
    status, out, _ = run("job", "submit", str(latex), "--paper", "--no-session", "--target", "stage")
    assert status == 0
    job_id = json.loads(stand_in.answers[-1])["id"]
    assert _sent(stand_in) == [
        ("POST", "/v1/model-iterations", {"source": {"kind": "paper", "text": LATEX}, "target": "stage"})
    ]
    assert out.splitlines() == [
        f"Job {job_id}: queued",
        f"Follow it with: matsya job wait {job_id}",
        f"The job has no session, and its questions stand in its record only: matsya job status {job_id}",
    ]
    status, _, _ = run("job", "submit", str(latex), "--no-session", "--target", "stage")
    assert status == 0 and _sent(stand_in) == [
        ("POST", "/v1/model-iterations", {"source": {"kind": "description", "text": LATEX}, "target": "stage"})
    ]

    paper = tmp_path / "saving.md"
    paper.write_text(PAPER, encoding="utf-8")
    matsya.start_job(paper, no_session=True, paper=True, target="period")
    matsya.submit_job(source_text=PAPER, paper=True, max_cycles=2, target="trellis")
    assert [body for _, _, body in _sent(stand_in)] == [
        {"source": {"kind": "paper", "text": PAPER}, "target": "period"},
        {"source": {"kind": "paper", "text": PAPER}, "target": "trellis", "max_cycles": 2},
    ]
    with pytest.raises(ValueError, match="^paper marks source_text as a paper's text"):
        matsya.submit_job(session="0" * 32, paper=True, target="stage")
    assert stand_in.requests == []
    status, out, _ = run("job", "submit", "--help")
    assert status == 0 and "--paper" in out


def test_the_stand_in_refuses_the_earlier_forms_and_records_references(stand_in) -> None:
    """The stand-in refuses a paper sent as numbered pages or as a PDF, with
    or without a text, with 422 and the service's sentence, and creates no
    job; its records carry the service's schema, and the record of a paper
    holds `references`, which the full view returns and the products view
    leaves out, as the service's does. Where the service's package is
    installed, its sentence, its schema and its request check are compared
    with the stand-in's."""
    pdf_field = EARLIER_PAPER_FORMS[1]
    pages = [{"page": 1, "text": PAPER}]
    earlier = (
        {"kind": "paper", "pages": pages},
        {"kind": "paper", pdf_field: "JVBERi0xLjQK"},
        {"kind": "paper", "text": PAPER, "pages": pages},
        {"kind": "paper", "text": PAPER, pdf_field: "JVBERi0xLjQK"},
    )
    client = MatsyaClient(stand_in.token, stand_in.url)
    for source in earlier:
        with pytest.raises(MatsyaError) as refused:
            client._request("POST", "/v1/model-iterations", {"source": source, "target": "stage"})
        assert (refused.value.status, refused.value.detail) == (422, PAPER_AS_TEXT)
    assert stand_in.jobs == {}

    assert {record["schema"] for record in RECORDS.values()} == {SCHEMA}
    assert RECORDS["paper"]["references"] == PAPER_REFERENCES
    assert PAPER.splitlines()[PAPER_REFERENCES[0]["lines"][0] - 1].startswith(PAPER_REFERENCES[0]["point"])
    stand_in.next_ends.append("paper")
    submitted = client.submit_job(source_text=PAPER, paper=True, target="stage")
    ended = client.wait_job(submitted["id"], interval=0)
    held = client.job(submitted["id"], view="full")["result"]
    assert (held["schema"], held["source"]["kind"], held["references"]) == (SCHEMA, "paper", PAPER_REFERENCES)
    assert "references" not in ended["result"]

    if importlib.util.find_spec("matsya_service") is None:
        return
    from matsya_service import processor

    assert (processor.PAPER_AS_TEXT, processor.SCHEMA) == (PAPER_AS_TEXT, SCHEMA)
    for source in earlier:
        with pytest.raises(processor.RequestRefused, match=re.escape(PAPER_AS_TEXT)):
            processor.check_request({"source": source, "target": "stage"})


def test_the_former_names_appear_nowhere_in_the_client() -> None:
    """The client's code, tests and README and the two pages of the user
    guide that describe a paper, the client's copies and, beside the
    client, their source, name neither the PDF's field nor the argument
    that sent it nor the record's page references."""
    former = ("pdf" + "_base64", "pdf" + "_path", "page" + "_references")
    paths = [
        *sorted((CLIENT / "src" / "matsya").glob("*.py")),
        *sorted((CLIENT / "tests").glob("*.py")),
        CLIENT / "README.md",
        *[CLIENT / "docs" / page for page in PAGES],
        *[GUIDE / page for page in PAGES if GUIDE.is_dir()],
    ]
    named = [
        f"{path}: {name}" for path in paths for name in former if name in path.read_text(encoding="utf-8")
    ]
    assert named == []


def test_item_1_against_the_service_a_markdown_paper_runs_from_its_session(service, run, tmp_path) -> None:
    """Against the service of the test configuration: a Markdown paper,
    the service's fixture paper, submitted with `--paper --target stage`,
    is appended to a session named after the file as a `paper` entry, and
    the job started from that session carries the session's label, reads
    the session's text as a paper, its kind named in the Model-prose-writer's
    message, and converges. Its record, in the schema
    `matsya-model-iteration/6`, names the source as a paper by the digest of
    the session's text and holds the reference the scripted
    Model-prose-writer gave, with the heading it stands under and the lines
    on which the service found its quotation in the session's text."""
    fixture = SERVICE_TESTS / "fixtures" / "papers" / "two-controls.md"
    if not fixture.is_file():
        pytest.skip("the service's fixture paper is not in this checkout")
    from scripted import QUOTE, converging

    text = fixture.read_text(encoding="utf-8")
    paper = tmp_path / "two-controls.md"
    paper.write_text(text, encoding="utf-8")
    heading = "### 2.1 States and controls"
    service.caller.replies.clear()
    service.caller.replies.extend(converging(references=[{"heading": heading, "point": QUOTE}]))

    status, out, _ = run("job", "submit", str(paper), "--paper", "--target", "stage", "--max-cycles", "1")
    assert status == 0
    session_id = _identifier(r"^Session ([0-9a-f]{32}): two-controls$", out)
    job_id = _identifier(r"^Job ([0-9a-f]{32}): queued$", out)
    assert f"Entry 1 (paper): the text of {paper}" in out.splitlines()
    status, out, _ = run("job", "wait", job_id, "--interval", "0.05")
    assert status == 0
    assert _final(out)[:2] == [
        f"two-controls · stage · version 1 · job 1 · converged ({job_id}), session {session_id}",
        "The job ended converged, with the reason source_agreement_and_semantic_fixed_point.",
    ]
    assert "===== the kind of the source material =====\n\npaper\n" in service.caller.prompts[0]

    record = matsya.job(job_id, view="full")["result"]
    material = f"Entry 1 (paper):\n{text.strip()}"
    line = next(number for number, held in enumerate(material.splitlines(), 1) if QUOTE in held)
    assert record["schema"] == SCHEMA == "matsya-model-iteration/6"
    assert record["source"] == {
        "kind": "paper",
        "sha256": [hashlib.sha256(material.encode("utf-8")).hexdigest()],
    }
    assert record["references"] == [{"heading": heading, "lines": [line, line], "point": QUOTE}]
    assert "page" + "_references" not in record
    service.caller.assert_finished()
