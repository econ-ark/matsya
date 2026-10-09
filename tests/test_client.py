"""The client against the stand-in service: each group of commands through
`MatsyaClient` and through `cli.main`, the requests by which `job submit`
keeps a description file in a session (D-G25), the labels, the selection
and the cancellation of AMD-MAT-008 §4, the first two headings of the
report with which `job wait` prints an ended job (AMD-MAT-010 §5), the
answer `--json` prints, and the refusals 401, 404, 409 and 422, printed
with the service's message, with a nonzero exit status and without the
Matsya token. The model folder, the report and `ask --follow` are tested in
`test_amd_mat_010_client.py` and `test_amd_mat_009_client.py`."""

from __future__ import annotations

import base64
import io
import json
import re

import pytest

import matsya
from conftest import ANSWER, CITATION, DIGEST, PASSAGE, QUESTION, STAGE
from matsya.cli import CANCEL_REQUESTED
from matsya.client import AuthenticationError, MatsyaClient, MatsyaError

TIME = re.compile(r"^\d\d:\d\d:\d\d  ")


def _identifier(pattern: str, text: str) -> str:
    found = re.search(pattern, text, re.MULTILINE)
    assert found, text
    return found.group(1)


def _final(out: str) -> list[str]:
    """The lines a command printed, without the lines of progress that a
    wait prints with the local time."""
    return [line for line in out.splitlines() if not TIME.match(line)]


def _sent(stand_in) -> list[tuple[str, str, object]]:
    """The requests the stand-in received, as (method, path, body), and
    none of them kept for the next call."""
    sent = [(request["method"], request["path"], request["body"]) for request in stand_in.requests]
    stand_in.requests.clear()
    return sent


def test_index_search_and_passage(stand_in, run) -> None:
    client = MatsyaClient(stand_in.token, stand_in.url)
    assert client.index()["index_digest"] == DIGEST
    found = client.search("stage file", limit=1, collections=["repository"])
    assert found["passages"][0]["passage_id"] == PASSAGE["passage_id"]
    assert stand_in.requests[-1]["body"] == {
        "query": "stage file",
        "limit": 1,
        "collections": ["repository"],
    }
    assert client.passage(PASSAGE["passage_id"], index_digest=DIGEST)["text"] == PASSAGE["text"]
    assert stand_in.requests[-1]["path"] == f"/v1/passages/{PASSAGE['passage_id']}?index_digest={DIGEST}"

    status, out, _ = run("index")
    assert status == 0
    assert out.splitlines() == [
        f"Index digest: {DIGEST}",
        "Embedding model: stand-in-embedding-v1",
        "Configuration version: 0.3.5",
    ]
    status, out, _ = run(
        "search", "stage file", "--collections", "repository,literature", "--collections", "hark", "--limit", "3"
    )
    assert status == 0
    assert stand_in.requests[-1]["body"] == {
        "query": "stage file",
        "limit": 3,
        "collections": ["repository", "literature", "hark"],
    }
    assert "[1] docs/Bellman-Sym/01-stage.md, The stage (repository, score 0.712)" in out
    assert f"    passage {PASSAGE['passage_id']}" in out
    assert "    A stage file names its arrival, decision and continuation fields" in out


def test_a_description_is_kept_in_a_session_named_after_the_file(stand_in, run, tmp_path) -> None:
    description = tmp_path / "model.md"
    description.write_text("A household saves out of cash on hand.\n", encoding="utf-8")
    status, out, _ = run("job", "submit", str(description), "--max-cycles", "2", "--force")
    assert status == 0
    session_id = json.loads(stand_in.answers[0])["id"]
    job_id = json.loads(stand_in.answers[-1])["id"]
    assert _sent(stand_in) == [
        ("POST", "/v1/sessions", {"name": "model"}),
        (
            "POST",
            f"/v1/sessions/{session_id}/entries",
            {"kind": "user", "text": "A household saves out of cash on hand.\n"},
        ),
        ("POST", "/v1/model-iterations", {"session": session_id, "max_cycles": 2, "force": True}),
    ]
    assert out.splitlines() == [
        f"Session {session_id}: model",
        f"Entry 1: the text of {description}",
        f"Job {job_id}: queued",
        f"Follow it with: matsya job wait {job_id}",
        f"The session, where the job's questions and your replies are kept: matsya session show {session_id}",
    ]

    # the job's questions are appended to the session, after the file's text;
    # the job is named by its label, the session's name, the version of its
    # text the job read, the job's number and its state
    status, out, _ = run("job", "wait", job_id, "--interval", "0")
    assert _final(out)[:2] == [
        f"model · version 1 · job 1 · needs_input ({job_id}), session {session_id}",
        "The job ended needs_input, with the reason distribution_needs_specification.",
    ]
    assert f"The questions stand as entries of session {session_id}: matsya session show {session_id}" in out
    status, out, _ = run("session", "show", session_id)
    lines = out.splitlines()
    assert lines[:5] == [
        f"Session {session_id}: model",
        "Revision: 1",
        f"Awaiting an answer: job {job_id}",
        "Jobs:",
        f"  model · version 1 · job 1 · needs_input ({job_id})",
    ]
    assert lines[-4:] == [
        "  1. user",
        "     A household saves out of cash on hand.",
        f"  2. question, from job {job_id}",
        f"     {QUESTION}",
    ]

    # with --session the file is appended to that session and the job starts
    # from it; --name names the session the command creates
    stand_in.requests.clear()
    status, out, _ = run("job", "submit", str(description), "--session", session_id)
    later = json.loads(stand_in.answers[-1])["id"]
    assert _sent(stand_in) == [
        (
            "POST",
            f"/v1/sessions/{session_id}/entries",
            {"kind": "user", "text": "A household saves out of cash on hand.\n"},
        ),
        ("POST", "/v1/model-iterations", {"session": session_id}),
    ]
    assert out.splitlines()[:3] == [
        f"Session {session_id}: model",
        f"Entry 3: the text of {description}",
        f"Job {later}: queued",
    ]
    status, out, _ = run("job", "submit", str(description), "--name", "a household")
    assert status == 0 and _sent(stand_in)[0] == ("POST", "/v1/sessions", {"name": "a household"})
    assert re.match(r"Session [0-9a-f]{32}: a household\nEntry 1: the text of ", out)

    # the same through the module's function
    started = matsya.start_job(description, name="a second household", max_cycles=2)
    assert (started["session"]["name"], started["entry"]["entry"]["number"]) == ("a second household", 1)
    assert started["entry"]["entry"]["text"] == "A household saves out of cash on hand."
    assert started["job"]["state"] == "queued"
    assert _sent(stand_in)[-1] == (
        "POST",
        "/v1/model-iterations",
        {"session": started["session"]["id"], "max_cycles": 2},
    )


def test_a_job_with_no_session_is_submitted_followed_and_written(stand_in, run, tmp_path) -> None:
    description = tmp_path / "model.md"
    description.write_text("A household saves out of cash on hand.\n", encoding="utf-8")
    status, out, _ = run("job", "submit", str(description), "--no-session", "--max-cycles", "2", "--force")
    assert status == 0
    job_id = json.loads(stand_in.answers[-1])["id"]
    assert _sent(stand_in) == [
        (
            "POST",
            "/v1/model-iterations",
            {
                "source": {"kind": "description", "text": "A household saves out of cash on hand.\n"},
                "max_cycles": 2,
                "force": True,
            },
        )
    ]
    assert out.splitlines() == [
        f"Job {job_id}: queued",
        f"Follow it with: matsya job wait {job_id}",
        "The job has no session, and its questions stand in its record only: "
        f"matsya job status {job_id}",
    ]
    started = matsya.start_job(description, no_session=True)
    assert (started["session"], started["entry"], started["job"]["state"]) == (None, None, "queued")
    assert [path for _, path, _ in _sent(stand_in)] == ["/v1/model-iterations"]

    status, out, _ = run("job", "wait", job_id, "--interval", "0")
    assert status == 0
    lines = out.splitlines()
    assert [TIME.sub("", line) for line in lines if TIME.match(line)] == [
        "queued",
        "running: step preparation (the Model-prose-writer and the prose-source-judge)",
        "running: step writing (Prose-to-Bellman-Sym), cycle 1 of 2",
        "running: step writing (Prose-to-Bellman-Sym), cycle 2 of 2",
    ]
    # the job ended with a record: the first two headings of its report, the
    # label of a job of no session being its state
    assert _final(out) == [
        f"converged ({job_id}), no session",
        "The job ended converged, with the reason source_agreement_and_semantic_fixed_point.",
        "Files of the last cycle: example.bl, note.md",
        f"Write the model folder and its report with: matsya job files {job_id} <folder>",
    ]
    status, out, _ = run("job", "status", job_id)
    assert out.splitlines()[0] == f"converged ({job_id}), no session"

    folder = tmp_path / "proposed"
    status, out, _ = run("job", "files", job_id, str(folder))
    assert status == 0 and out.splitlines()[0] == f"Wrote 4 files to {folder}:"
    assert (folder / "declaration" / "stages" / "example" / "example.bl").read_text(encoding="utf-8") == STAGE


def test_a_paper_is_sent_as_its_pdf_in_base64(stand_in, run, tmp_path) -> None:
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"%PDF-1.4\nscripted text\n")
    encoded = base64.b64encode(pdf.read_bytes()).decode("ascii")
    client = MatsyaClient(stand_in.token, stand_in.url)
    submitted = client.submit_job(pdf_path=pdf)
    assert stand_in.requests[-1]["body"] == {"source": {"kind": "paper", "pdf_base64": encoded}}
    seen = []
    ended = client.wait_job(submitted["id"], interval=0, on_change=seen.append)
    assert [answer["state"] for answer in seen] == ["queued", "running", "running", "running", "converged"]
    assert ended is seen[-1]
    with pytest.raises(ValueError):
        client.submit_job(source_text="A household saves.", session="0" * 32)

    # the command reads a PDF by its first bytes as well as by its name, and
    # sends it with no session, since a PDF cannot be attached to one yet
    renamed = tmp_path / "paper.bin"
    renamed.write_bytes(pdf.read_bytes())
    stand_in.requests.clear()
    status, out, _ = run("job", "submit", str(renamed))
    assert status == 0
    assert _sent(stand_in) == [
        ("POST", "/v1/model-iterations", {"source": {"kind": "paper", "pdf_base64": encoded}})
    ]
    job_id = _identifier(r"^Job ([0-9a-f]{32}): queued$", out)
    assert out.splitlines()[-1] == (
        "A PDF cannot be attached to a session yet, so the job has no session, and its "
        f"questions stand in its record only: matsya job status {job_id}"
    )


def test_a_job_from_a_session_asks_and_the_reply_starts_the_next_attempt(stand_in, run, tmp_path) -> None:
    status, out, _ = run("session", "new", "a household")
    session_id = _identifier(r"^Session ([0-9a-f]{32}): a household$", out)
    entry = tmp_path / "entry.md"
    entry.write_text("Income y is risky.\n", encoding="utf-8")
    status, out, _ = run("session", "add", session_id, str(entry))
    assert out.splitlines()[0] == (
        f"Appended entry 1 (user) to session {session_id}; the session's revision is 1."
    )
    status, out, _ = run("job", "submit", "--session", session_id)
    assert stand_in.requests[-1]["body"] == {"session": session_id}
    job_id = _identifier(r"^Job ([0-9a-f]{32}): queued$", out)
    assert out.splitlines()[-1] == (
        f"The session, where the job's questions and your replies are kept: matsya session show {session_id}"
    )

    status, out, _ = run("job", "wait", job_id, "--interval", "0")
    assert status == 0
    assert "The job ended needs_input, with the reason distribution_needs_specification." in out
    assert f"  1. {QUESTION}" in out
    assert f"The questions stand as entries of session {session_id}: matsya session show {session_id}" in out

    status, out, _ = run("session", "show", session_id)
    assert f"  2. question, from job {job_id}" in out
    assert f"     {QUESTION}" in out
    assert f"Awaiting an answer: job {job_id}" in out

    reply = tmp_path / "reply.md"
    reply.write_text("Income y is lognormal with mean one.\n", encoding="utf-8")
    status, out, _ = run("session", "add", session_id, str(reply), "--replies-to", "2")
    assert stand_in.requests[-1]["body"] == {
        "kind": "user",
        "text": "Income y is lognormal with mean one.\n",
        "replies_to": 2,
    }
    scheduled = _identifier(r"^Follow it with: matsya job wait ([0-9a-f]{32})$", out)
    status, out, _ = run("job", "wait", scheduled, "--interval", "0")
    assert "The job ended converged, with the reason source_agreement_and_semantic_fixed_point." in out


def test_a_question_in_a_session_prints_the_answer_and_its_citations(stand_in, run, tmp_path, monkeypatch) -> None:
    status, out, _ = run("session", "new", "a household")
    session_id = _identifier(r"^Session ([0-9a-f]{32}): a household$", out)
    stage = tmp_path / "example.bl"
    stage.write_text(STAGE, encoding="utf-8")
    status, out, err = run(
        "ask", session_id, "What does a stage file name?", "--stage-file", str(stage), "--interval", "0"
    )
    assert status == 0, err
    asked = [request for request in stand_in.requests if request["path"].endswith("/turns")]
    assert asked[0]["body"] == {"question": "What does a stage file name?", "stage_file": STAGE}
    assert [TIME.sub("", line) for line in out.splitlines() if TIME.match(line)] == [
        "queued",
        "running: step conversation (the conversation role)",
    ]
    # a session with no job: the answer reads no job's outputs and names none
    assert _final(out)[0] == ANSWER
    assert "  [1] docs/Bellman-Sym/01-stage.md, The stage" in out
    assert f'      "{CITATION["quote"]}"' in out

    status, out, _ = run("session", "show", session_id)
    assert re.search(r"^  2\. answer, from turn [0-9a-f]{32}, replies to 1$", out, re.MULTILINE)
    assert "Jobs: none" in out.splitlines()

    # an answer is accepted by an entry with no text, and an entry's text may
    # come from the standard input
    status, out, _ = run("session", "add", session_id, "--kind", "acceptance", "--replies-to", "2")
    assert stand_in.requests[-1]["body"] == {"kind": "acceptance", "replies_to": 2}
    assert out.startswith(f"Appended entry 3 (acceptance) to session {session_id}")
    monkeypatch.setattr("sys.stdin", io.StringIO("The household also holds a pension.\n"))
    status, out, _ = run("session", "add", session_id, "-")
    assert stand_in.requests[-1]["body"] == {"kind": "user", "text": "The household also holds a pension.\n"}

    # the same operations through the client
    client = MatsyaClient(stand_in.token, stand_in.url)
    other = client.new_session("a second household")["id"]
    added = client.add_entry(other, "The household holds a pension.", delivery_id="first")
    assert (added["entry"]["number"], added["repeated"], added["scheduled"]) == (1, False, None)
    assert stand_in.requests[-1]["body"] == {
        "kind": "user",
        "text": "The household holds a pension.",
        "delivery_id": "first",
    }
    seen = []
    turn = client.ask(other, "What does a stage file name?", interval=0, on_change=seen.append)
    assert [answer["state"] for answer in seen] == ["queued", "running", "finished"]
    assert turn["record"]["result"]["citations"] == [CITATION]
    assert [entry["kind"] for entry in client.session(other)["entries"]] == ["user", "user", "answer"]


def test_json_prints_the_service_answer_unchanged(stand_in, run, tmp_path) -> None:
    for arguments in (
        ("index", "--json"),
        ("search", "stage", "--json"),
        ("session", "new", "a household", "--json"),
    ):
        status, out, _ = run(*arguments)
        assert status == 0 and out == stand_in.answers[-1] + "\n", arguments
    session_id = json.loads(out)["id"]
    description = tmp_path / "model.md"
    description.write_text("A household saves out of cash on hand.\n", encoding="utf-8")
    status, out, _ = run("job", "submit", str(description), "--json")
    assert out == stand_in.answers[-1] + "\n" and len(stand_in.answers) == 6
    assert json.loads(stand_in.answers[3])["name"] == "model"
    status, out, _ = run("job", "submit", str(description), "--no-session", "--json")
    assert out == stand_in.answers[-1] + "\n"
    status, out, err = run("job", "wait", json.loads(out)["id"], "--interval", "0", "--json")
    assert out == stand_in.answers[-1] + "\n" and json.loads(out)["state"] == "converged"
    assert "running: step writing (Prose-to-Bellman-Sym), cycle 1 of 2" in err
    status, out, err = run("ask", session_id, "What does a stage file name?", "--interval", "0", "--json")
    assert out == stand_in.answers[-1] + "\n" and json.loads(out)["state"] == "finished"
    status, out, _ = run("session", "select", session_id, "--none", "--json")
    assert out == stand_in.answers[-1] + "\n" and json.loads(out)["selected_job"] is None
    status, out, _ = run("job", "submit", str(description), "--no-session", "--json")
    status, out, _ = run("job", "cancel", json.loads(out)["id"], "--json")
    assert out == stand_in.answers[-1] + "\n" and json.loads(out)["state"] == "cancelled"


def test_a_refused_matsya_token_is_reported_without_the_token(stand_in, run, monkeypatch) -> None:
    wrong = "msy_" + "f" * 32
    monkeypatch.setenv("MATSYA_TOKEN", wrong)
    stand_in.echo_token = True
    status, out, err = run("index")
    assert (status, out) == (1, "")
    assert err == (
        "Error: The service refused the request (401): The Matsya bearer token is invalid: "
        "<Matsya token>. Run matsya configure to save the Matsya token AAS gave you, or set "
        "MATSYA_TOKEN.\n"
    )
    with pytest.raises(AuthenticationError) as refused:
        MatsyaClient(wrong, stand_in.url).index()
    assert refused.value.status == 401
    assert wrong not in str(refused.value) + refused.value.detail + repr(MatsyaClient(wrong, stand_in.url))
    with pytest.raises(AuthenticationError, match="A Matsya bearer token is required"):
        MatsyaClient("", stand_in.url).index()
    assert "authorization" not in {name.lower() for name in stand_in.requests[-1]["headers"]}


def test_not_found_and_a_refused_request_print_the_service_message(stand_in, run, tmp_path) -> None:
    status, out, err = run("session", "show", "0" * 32)
    assert (status, out, err) == (1, "", "Error: The service refused the request (404): Session not found.\n")
    status, out, err = run("search", "stage", "--limit", "50")
    assert (status, out) == (1, "")
    assert err == "Error: The service refused the request (422): Search limit must be from 1 to 20.\n"
    status, _, err = run("job", "files", "0" * 32, str(tmp_path / "folder"))
    assert status == 1 and err == "Error: The service refused the request (404): Model iteration not found.\n"

    client = MatsyaClient(stand_in.token, stand_in.url)
    submitted = client.submit_job(source_text="A household saves.")
    with pytest.raises(MatsyaError, match="holds no record; its state is queued"):
        client.job_files(submitted["id"], tmp_path / "early")
    assert not (tmp_path / "early").exists()


def test_arguments_the_routes_do_not_accept_are_refused_before_any_request(stand_in, run, tmp_path) -> None:
    description = tmp_path / "model.md"
    description.write_text("A household saves.\n", encoding="utf-8")
    for arguments in (
        ("job", "submit"),
        ("job", "submit", "--no-session"),
        ("job", "submit", "--name", "a household"),
        ("job", "submit", str(description), "--session", "0" * 32, "--no-session"),
        ("job", "submit", str(description), "--name", "a household", "--session", "0" * 32),
        ("job", "submit", str(description), "--name", "a household", "--no-session"),
        ("job", "submit", str(description), "--max-cycles", "0"),
        ("session", "add", "0" * 32),
        ("session", "add", "0" * 32, str(description), "--kind", "acceptance", "--replies-to", "2"),
        ("session", "add", "0" * 32, "--kind", "acceptance"),
        ("job", "wait", "0" * 32, "--interval", "-1"),
        ("job", "cancel"),
        ("session", "select", "0" * 32),
        ("session", "select", "0" * 32, "1" * 32, "--none"),
    ):
        status, _, _ = run(*arguments)
        assert status == 2, arguments
    status, _, err = run("job", "submit", str(tmp_path / "absent.md"))
    assert status == 1 and err.startswith(f"Error: cannot read {tmp_path / 'absent.md'}")
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")
    status, _, err = run("session", "add", "0" * 32, str(pdf), "--kind", "paper")
    assert status == 1 and "is a PDF, and an entry holds text" in err
    # a PDF cannot be attached to a session yet; an empty file or one not in
    # UTF-8 is refused before a session is created for it
    for arguments in (("--session", "0" * 32), ("--name", "a paper")):
        status, _, err = run("job", "submit", str(pdf), *arguments)
        assert status == 1 and f"Error: {pdf} is a PDF, and a PDF cannot be attached to a session yet" in err
    empty = tmp_path / "empty.md"
    empty.write_text(" \n", encoding="utf-8")
    status, _, err = run("job", "submit", str(empty))
    assert (status, err) == (1, f"Error: {empty} holds no text.\n")
    latin = tmp_path / "latin.md"
    latin.write_bytes("Épargne\n".encode("latin-1"))
    status, _, err = run("job", "submit", str(latin))
    assert (status, err) == (1, f"Error: {latin} is not text in UTF-8.\n")
    with pytest.raises(ValueError, match="takes session or no_session, not both"):
        matsya.start_job(description, session="0" * 32, no_session=True)
    assert stand_in.requests == []


def test_a_refusal_after_the_session_was_created_names_the_session(stand_in, run, tmp_path) -> None:
    description = tmp_path / "model.md"
    description.write_text("A household saves.\n", encoding="utf-8")
    status, out, err = run("job", "submit", str(description), "--max-cycles", "9")
    session_id = json.loads(stand_in.answers[0])["id"]
    assert (status, out) == (1, "")
    assert err == (
        "Error: The service refused the request (422): max_cycles must be an integer from 1 to 5. "
        f"Session {session_id} holds the text of {description} as entry 1, and no job was started "
        f"from it; start one with: matsya job submit --session {session_id}\n"
    )
    with pytest.raises(MatsyaError) as refused:
        MatsyaClient(stand_in.token, stand_in.url).start_job(description, name="x" * 201)
    # the name is refused before any session exists, so the message names none
    assert str(refused.value) == (
        "The service refused the request (422): A session's name has at most 200 characters."
    )


def test_no_api_token_is_sent(stand_in, run, monkeypatch) -> None:
    monkeypatch.setenv("MATSYA_ANTHROPIC_KEY", "sk-ant-api-test-value")
    status, _, _ = run("index")
    assert status == 0
    headers = stand_in.requests[-1]["headers"]
    assert headers["Authorization"] == f"Bearer {stand_in.token}"
    assert "x-anthropic-key" not in {name.lower() for name in headers}
    assert not any("sk-ant" in value for value in headers.values())


def _session_with_text(run, tmp_path, name: str, text: str) -> str:
    """A new session of this name holding one entry, and its identifier."""
    status, out, _ = run("session", "new", name)
    session_id = _identifier(rf"^Session ([0-9a-f]{{32}}): {re.escape(name)}$", out)
    entry = tmp_path / "entry.md"
    entry.write_text(text, encoding="utf-8")
    status, _, _ = run("session", "add", session_id, str(entry))
    assert status == 0
    return session_id


def test_a_queued_or_running_job_is_cancelled_and_an_ended_job_is_not(stand_in, run, tmp_path) -> None:
    session_id = _session_with_text(run, tmp_path, "Household with firms", "A household works for a firm.\n")
    status, out, _ = run("job", "submit", "--session", session_id)
    queued = _identifier(r"^Job ([0-9a-f]{32}): queued$", out)

    # a queued job is cancelled at once, by a request with no body, and the
    # command prints the job's label and state; the job has not started, so
    # its label names no version
    stand_in.requests.clear()
    status, out, err = run("job", "cancel", queued)
    assert (status, err) == (0, "")
    assert _sent(stand_in) == [("POST", f"/v1/model-iterations/{queued}/cancel", None)]
    assert out.splitlines() == ["Household with firms · job 1 · cancelled", f"Job {queued}: cancelled"]
    status, out, _ = run("job", "status", queued)
    assert out.splitlines() == ["Household with firms · job 1 · cancelled", f"Job {queued}: cancelled"]
    status, out, _ = run("job", "wait", queued, "--interval", "0")
    assert (status, out.splitlines()) == (
        0,
        ["Household with firms · job 1 · cancelled", f"Job {queued}: cancelled"],
    )

    # a job that has ended cannot be cancelled: the service's 409 is printed
    # and the command exits with status 1
    status, out, err = run("job", "cancel", queued)
    assert (status, out, err) == (
        1,
        "",
        "Error: The service refused the request (409): The job has ended.\n",
    )
    status, out, err = run("job", "cancel", "0" * 32)
    assert (status, err) == (1, "Error: The service refused the request (404): Model iteration not found.\n")

    # a running job is marked: the command prints that its cancellation was
    # requested, and the job ends cancelled with its record
    status, out, _ = run("job", "submit", "--session", session_id)
    running = _identifier(r"^Job ([0-9a-f]{32}): queued$", out)
    for state in ("queued", "running"):
        status, out, _ = run("job", "status", running)
        assert f"Job {running}: {state}" in out.splitlines()
    assert out.splitlines()[0] == "Household with firms · version 1 · job 2 · running"
    status, out, _ = run("job", "cancel", running)
    assert out.splitlines() == [
        "Household with firms · version 1 · job 2 · running",
        f"Job {running}: running",
        "Now at step preparation (the Model-prose-writer and the prose-source-judge).",
        CANCEL_REQUESTED,
        f"Follow it with: matsya job wait {running}",
    ]
    status, out, _ = run("job", "wait", running, "--interval", "0")
    assert (status, out.splitlines()) == (
        0,
        [
            f"Household with firms · version 1 · job 2 · cancelled ({running}), session {session_id}",
            "The job ended cancelled, with the reason cancelled_by_user.",
            f"Write the model folder and its report with: matsya job files {running} <folder>",
        ],
    )

    # the same through the client, which raises the 409 as the refusal it is,
    # and through the module's function
    client = MatsyaClient(stand_in.token, stand_in.url)
    with pytest.raises(MatsyaError) as refused:
        client.cancel_job(running)
    assert (refused.value.status, refused.value.detail) == (409, "The job has ended")
    third = client.submit_job(session=session_id)["id"]
    cancelled = matsya.cancel_job(third)
    assert (cancelled["state"], cancelled["cancel_requested"]) == ("cancelled", True)
    assert cancelled["label"]["text"] == "Household with firms · job 3 · cancelled"


def test_a_session_lists_its_jobs_by_label_and_selects_the_job_its_questions_read(stand_in, run, tmp_path) -> None:
    session_id = _session_with_text(run, tmp_path, "Household with firms", "Income y is risky.\n")
    status, out, _ = run("job", "submit", "--session", session_id)
    first = _identifier(r"^Job ([0-9a-f]{32}): queued$", out)
    status, out, _ = run("job", "wait", first, "--interval", "0")
    assert _final(out)[:2] == [
        f"Household with firms · version 1 · job 1 · needs_input ({first}), session {session_id}",
        "The job ended needs_input, with the reason distribution_needs_specification.",
    ]
    reply = tmp_path / "reply.md"
    reply.write_text("Income y is lognormal with mean one.\n", encoding="utf-8")
    status, out, _ = run("session", "add", session_id, str(reply), "--replies-to", "2")
    second = _identifier(r"^Follow it with: matsya job wait ([0-9a-f]{32})$", out)
    status, out, _ = run("job", "wait", second, "--interval", "0")
    assert _final(out)[:2] == [
        f"Household with firms · version 3 · job 2 · converged ({second}), session {session_id}",
        "The job ended converged, with the reason source_agreement_and_semantic_fixed_point.",
    ]

    # with no job selected, a question reads the latest current job that
    # holds a record, and the answer names it first
    status, out, err = run("ask", session_id, "What does the model contain?", "--interval", "0")
    assert status == 0, err
    assert _final(out)[:2] == [
        f"Answer from Household with firms · version 3 · job 2 · converged ({second})",
        ANSWER,
    ]

    # the listing names each job by its label and its identifier
    status, out, _ = run("session", "show", session_id)
    lines = out.splitlines()
    assert not any(line.startswith("Selected job") for line in lines)
    at = lines.index("Jobs:")
    assert lines[at + 1 : at + 3] == [
        f"  Household with firms · version 1 · job 1 · needs_input ({first})",
        f"  Household with firms · version 3 · job 2 · converged ({second})",
    ]

    # the selected job is the one a question reads, and the listing names it
    stand_in.requests.clear()
    status, out, _ = run("session", "select", session_id, first)
    assert _sent(stand_in) == [("POST", f"/v1/sessions/{session_id}/selected-job", {"job": first})]
    assert out.splitlines() == [
        f"Selected job of session {session_id}: Household with firms · version 1 · job 1 · needs_input ({first})",
        "A question asked in the session reads this job's outputs; clear the selection with: "
        f"matsya session select {session_id} --none",
    ]
    status, out, _ = run("session", "show", session_id)
    assert f"Selected job: Household with firms · version 1 · job 1 · needs_input ({first})" in out.splitlines()
    status, out, _ = run("ask", session_id, "And the first job?", "--interval", "0")
    assert _final(out)[0] == f"Answer from Household with firms · version 1 · job 1 · needs_input ({first})"

    # --none clears the selection
    status, out, _ = run("session", "select", session_id, "--none")
    assert stand_in.requests[-1]["body"] == {"job": None}
    assert out.splitlines() == [
        f"Session {session_id} has no selected job.",
        "A question asked in the session reads the outputs of its latest current job that holds a record.",
    ]
    status, out, _ = run("session", "show", session_id)
    assert not any(line.startswith("Selected job") for line in out.splitlines())

    # a job that holds no record cannot be selected
    status, out, _ = run("job", "submit", "--session", session_id)
    queued = _identifier(r"^Job ([0-9a-f]{32}): queued$", out)
    status, out, err = run("session", "select", session_id, queued)
    assert (status, out, err) == (
        1,
        "",
        "Error: The service refused the request (422): The job holds no record to discuss.\n",
    )

    # the same through the client and the module's function
    client = MatsyaClient(stand_in.token, stand_in.url)
    assert client.select_job(session_id, second)["selected_job"] == second
    listed = matsya.select_job(session_id, None)
    assert listed["selected_job"] is None
    assert [job["id"] for job in listed["jobs"]] == [first, second, queued]
