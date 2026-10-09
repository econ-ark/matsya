"""The command `matsya`, which calls the routes of the Matsya service of
spec 0.3 from a terminal:

    matsya configure
    matsya index
    matsya search "<query>" [--collections NAMES] [--limit N]
    matsya job submit <file> [--name NAME | --session <session> | --no-session]
                             [--max-cycles N] [--force]
    matsya job submit --session <session> [--max-cycles N] [--force]
    matsya job status <job>
    matsya job wait <job> [--interval SECONDS]
    matsya job files <job> <folder> [--all-iterates] [--overwrite]
    matsya job cancel <job>
    matsya session new "<name>"
    matsya session add <session> <file> [--kind user|paper] [--replies-to N]
    matsya session add <session> --kind acceptance --replies-to N
    matsya session show <session>
    matsya session select <session> <job>
    matsya session select <session> --none
    matsya ask <session> "<question>" [--stage-file PATH] [--index-digest DIGEST]
                                      [--follow FOLDER]

`job submit <file>` keeps a description file in a session, new and named
after the file unless `--session` names one, and starts the job from it;
`--no-session` sends the file as the job's source instead, and a PDF is sent
with no session. A job of a session is printed with the text of its label,
such as "Household with firms · version 2 · job 7 · converged": the session's
name, the version of its text the job read, the job's number among the
session's jobs and its state (AMD-MAT-008 §2). A job that has ended is
printed with the first two headings of its report, the label with the
identifiers and the status sentence; `job files` writes its model folder and
report (AMD-MAT-010 §§4 and 5), and `ask --follow` waits for the job a turn
started and writes its folder (AMD-MAT-009 §5). Every command but
`configure` takes `--json`, which prints the service's JSON answer as it
arrived, for `job submit` the job's and for `ask` the turn's; otherwise the
command prints plain text for a person. A refusal of the service is printed
with the service's own message, and the command exits with status 1. No
output shows the Matsya token.
"""

from __future__ import annotations

import argparse
import sys
import textwrap
import time
from pathlib import Path
from typing import Any, Callable

from matsya.client import (
    JOB_FINAL_STATES,
    MatsyaClient,
    MatsyaError,
    _report_sections,
    check_folder,
    is_pdf,
    last_cycle_files,
)
from matsya.config import ConfigurationError, load_config, save_config

# the roles that compute each step of a job or a turn, and at reconstruction
# the program of the round-trip comparison (spec 0.3 §4, REQ-MAT-017;
# AMD-MAT-006 §7; the role names of 9 October 2026)
STEP_ROLES = {
    "preparation": "the Model-prose-writer and the prose-source-judge",
    "writing": "Prose-to-Bellman-Sym",
    "prose_writing": "Semantics-to-Prose",
    "judging": "the prose-roundtrip-judge",
    "reconstruction": "Prose-to-Bellman-Sym and the round-trip comparison",
    "conversation": "the conversation role",
}
# the characters of a passage's text that a search prints
PASSAGE_EXCERPT = 600
# the seconds between two requests of `ask` for its turn and for the job
# `--follow` waits for, unless `--interval` names others
TURN_INTERVAL = 2.0
JOB_INTERVAL = 5.0
# what is printed of a running job whose cancellation was requested
# (AMD-MAT-008 §4)
CANCEL_REQUESTED = (
    "Its cancellation was requested: the job stops before its next call to the "
    "language-model provider, and a call already sent finishes and is charged."
)

EPILOG = """\
Set up once:
  matsya configure                   save your Matsya token and the service address
  export MATSYA_SERVER=...           override the saved service address
  export MATSYA_TOKEN=...            override the saved Matsya token

Examples:
  matsya index
  matsya search "decision perch state and controls" --collections repository --limit 4
  matsya job submit model.md
  matsya job wait <job>
  matsya session show <session>
  matsya session add <session> reply.md --replies-to <number>
  matsya job files <job> proposed-model
  matsya job files <job> proposed-model-iterates --all-iterates
  matsya job cancel <job>
  matsya session new "a household"
  matsya ask <session> "What does the decision perch of a stage hold?"
  matsya ask <session> "Submit this as a job." --follow proposed-model
  matsya session select <session> <job>
"""


class CommandError(Exception):
    """A command the client cannot carry out before it sends a request, such
    as one naming a file it cannot read."""


# -- reading the user's files


def _file_bytes(name: str) -> bytes:
    try:
        return Path(name).read_bytes()
    except OSError as error:
        raise CommandError(f"cannot read {name}: {error.strerror or error}") from None


def _decoded(data: bytes, name: str) -> str:
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        raise CommandError(f"{name} is not text in UTF-8") from None


def _entry_text(name: str) -> str:
    """The text of an entry: the file's text, or the standard input for `-`."""
    if name == "-":
        return sys.stdin.read()
    data = _file_bytes(name)
    if is_pdf(name, data):
        raise CommandError(
            f"{name} is a PDF, and an entry holds text; send the paper's text as a Markdown "
            "or text file, or start a job from the PDF with: matsya job submit"
        )
    return _decoded(data, name)


# -- plain text for a person


def _step_text(progress: dict[str, Any] | None) -> str:
    """The step and cycle of a job's or a turn's progress, such as
    "step writing (Prose-to-Bellman-Sym), cycle 1 of 3"."""
    if not progress or not progress.get("step"):
        return ""
    step = progress["step"]
    text = f"step {step}"
    if step in STEP_ROLES:
        text += f" ({STEP_ROLES[step]})"
    cycle, limit = progress.get("cycle"), progress.get("max_cycles")
    if cycle:  # cycle 0 is the cycle of preparation and of a turn
        text += f", cycle {cycle}" + (f" of {limit}" if limit else "")
    return text


def _reporter(stream: Any) -> Callable[[dict[str, Any]], None]:
    """The function that prints a job's or a turn's state, step and cycle
    whenever they change while the command waits."""

    def report(answer: dict[str, Any]) -> None:
        if answer.get("state") in ("queued", "running"):
            step = _step_text(answer.get("progress"))
            line = f"{answer['state']}: {step}" if step else str(answer["state"])
            print(f"{time.strftime('%H:%M:%S')}  {line}", file=stream, flush=True)

    return report


def _index_lines(index: dict[str, Any]) -> list[str]:
    return [
        f"Index digest: {index.get('index_digest')}",
        f"Embedding model: {index.get('embedding_model_id')}",
        f"Configuration version: {index.get('configuration_version')}",
    ]


def _place(path: object, location: dict[str, Any] | None, heading: object = None) -> str:
    """Where a passage stands: its path, its heading and its page."""
    location = location or {}
    parts = [str(path)]
    heading = heading or location.get("heading")
    if heading:
        parts.append(str(heading))
    if isinstance(location.get("page"), int):
        parts.append(f"page {location['page']}")
    return ", ".join(parts)


def _search_lines(found: dict[str, Any]) -> list[str]:
    passages = found.get("passages") or []
    lines = [f"Index digest: {found.get('index_digest')}", f"Passages: {len(passages)}"]
    for number, passage in enumerate(passages, 1):
        score = passage.get("score")
        held = str(passage.get("corpus"))
        if isinstance(score, (int, float)):
            held += f", score {score:.3f}"
        text = " ".join(str(passage.get("text", "")).split())
        if len(text) > PASSAGE_EXCERPT:
            text = text[:PASSAGE_EXCERPT].rstrip() + " ..."
        lines += [
            "",
            f"[{number}] {_place(passage.get('path'), passage.get('location'))} ({held})",
            f"    passage {passage.get('passage_id')}",
            textwrap.fill(text, width=88, initial_indent="    ", subsequent_indent="    "),
        ]
    return lines


def _label_text(job: dict[str, Any]) -> str | None:
    """The text of a job's label (AMD-MAT-008 §2), such as "Household with
    firms · version 2 · job 7 · converged", or None when the record carries
    no label."""
    label = job.get("label")
    text = label.get("text") if isinstance(label, dict) else None
    return text if isinstance(text, str) and text.strip() else None


def _job_name(job: dict[str, Any]) -> str:
    """A job by the text of its label and its identifier, such as
    "Household with firms · version 2 · job 7 · converged (<job>)", or
    "job <job>" when the record carries no label."""
    text = _label_text(job)
    return f"{text} ({job.get('id')})" if text else f"job {job.get('id')}"


def _label_lines(job: dict[str, Any]) -> list[str]:
    """The line of a job's label that begins its printed form. The label of
    a job of no session is its state alone, which the next line states, so
    it adds no line."""
    text = _label_text(job)
    return [text] if text and text != job.get("state") else []


def _job_lines(job: dict[str, Any]) -> list[str]:
    """A job for a person. A job that has ended with a record is printed
    with the content of the first two headings of its report, the text of
    its label with the identifiers of the job and its session, and the
    status sentence (AMD-MAT-010 §5), then its questions and the command
    that writes its model folder; any other job with the text of its label,
    then its state."""
    if job.get("state") in JOB_FINAL_STATES and isinstance(job.get("result"), dict):
        return _ended_lines(job)
    return _label_lines(job) + _state_lines(job)


def _state_lines(job: dict[str, Any]) -> list[str]:
    """A job's identifier and state; while it runs, its step and whether its
    cancellation was requested; once it has ended without a record, its
    error and the error's detail."""
    job_id = job.get("id")
    state = job.get("state")
    lines = [f"Job {job_id}: {state}"]
    if state not in JOB_FINAL_STATES:
        step = _step_text(job.get("progress"))
        if step:
            lines.append(f"Now at {step}.")
        if job.get("cancel_requested"):
            lines.append(CANCEL_REQUESTED)
        return lines
    if job.get("error"):
        lines[0] += f", error {job['error']}"
        if job.get("error_detail"):
            lines.append(f"Detail: {job['error_detail']}")
    return lines


def _ended_lines(job: dict[str, Any]) -> list[str]:
    """A job that has ended with a record: the content of the first two
    headings of its report, its questions with where they stand, the files
    of its last cycle and the command that writes its model folder."""
    job_id = job.get("id")
    state = job.get("state")
    record = job["result"]
    lines = [line for _, body in _report_sections(job)[:2] for line in body]
    questions = record.get("questions") or []
    if state == "needs_input" and questions:
        lines.append("Questions:")
        lines += [f"  {number}. {question}" for number, question in enumerate(questions, 1)]
        session = job.get("session")
        if session and job.get("current") is False:
            # a job that is not current appends no question (REQ-MAT-010)
            lines.append(
                f"Session {session} received a later entry while the job ran, "
                "so the questions were not appended to it."
            )
        elif session:
            lines += [
                f"The questions stand as entries of session {session}: matsya session show {session}",
                f"Reply to one with: matsya session add {session} <file> --replies-to <its entry number>",
            ]
    files = last_cycle_files(record)
    if files:
        lines.append("Files of the last cycle: " + ", ".join(files))
    lines.append(f"Write the model folder and its report with: matsya job files {job_id} <folder>")
    return lines


def _entry_heading(entry: dict[str, Any]) -> str:
    """An entry's number and kind, the job or turn that wrote it and the
    entry it replies to, such as "2. answer, from turn 9e...e0, replies to 1"."""
    parts = [f"{entry.get('number')}. {entry.get('kind')}"]
    origin = entry.get("origin")
    if isinstance(origin, dict):
        parts += [f"from {kind} {origin_id}" for kind, origin_id in origin.items()]
    if entry.get("replies_to") is not None:
        parts.append(f"replies to {entry['replies_to']}")
    return ", ".join(parts)


def _selected_name(session: dict[str, Any]) -> str:
    """The session's selected job by the text of its label and its
    identifier, from the session's listing of its jobs."""
    selected = session.get("selected_job")
    for job in session.get("jobs") or []:
        if job.get("id") == selected:
            return _job_name(job)
    return f"job {selected}"


def _session_lines(session: dict[str, Any]) -> list[str]:
    """A session for a person: its name and revision, the job awaiting an
    answer, the selected job, its jobs by the text of their labels and their
    identifiers in the order they were created, its turns and its entries."""
    lines = [f"Session {session.get('id')}: {session.get('name')}", f"Revision: {session.get('revision')}"]
    if session.get("awaiting_answer"):
        lines.append(f"Awaiting an answer: job {session['awaiting_answer']}")
    if session.get("selected_job"):
        lines.append(f"Selected job: {_selected_name(session)}")
    jobs = session.get("jobs") or []
    lines.append("Jobs:" if jobs else "Jobs: none")
    lines += [f"  {_job_name(job)}" for job in jobs]
    lines.append("Turns: " + (", ".join(session.get("turns") or []) or "none"))
    entries = session.get("entries") or []
    lines.append("Entries:" if entries else "Entries: none")
    for entry in entries:
        lines.append("  " + _entry_heading(entry))
        if entry.get("text"):
            lines.append(textwrap.indent(entry["text"].rstrip(), "     "))
    return lines


def _selection_lines(session: dict[str, Any]) -> list[str]:
    """The session's selected job after `session select`, or that it has
    none, and the job whose outputs a question asked in it then reads."""
    session_id = session.get("id")
    if session.get("selected_job"):
        return [
            f"Selected job of session {session_id}: {_selected_name(session)}",
            "A question asked in the session reads this job's outputs; clear the "
            f"selection with: matsya session select {session_id} --none",
        ]
    return [
        f"Session {session_id} has no selected job.",
        "A question asked in the session reads the outputs of its latest current job "
        "that holds a record.",
    ]


def _new_session_lines(session: dict[str, Any]) -> list[str]:
    session_id = session.get("id")
    return [
        f"Session {session_id}: {session.get('name')}",
        f"Add an entry with: matsya session add {session_id} <file>",
        f'Ask a question with: matsya ask {session_id} "<question>"',
    ]


def _entry_added_lines(answer: dict[str, Any]) -> list[str]:
    entry = answer.get("entry") or {}
    session_id = answer.get("id")
    if answer.get("repeated"):
        lines = [
            f"Session {session_id} already holds this delivery as entry {entry.get('number')}; "
            "nothing was appended."
        ]
    else:
        lines = [
            f"Appended entry {entry.get('number')} ({entry.get('kind')}) to session {session_id}; "
            f"the session's revision is {answer.get('revision')}."
        ]
    scheduled = answer.get("scheduled")
    if scheduled:
        lines += [
            f"The reply started the next preparation attempt of the job awaiting an answer: job {scheduled.get('id')}",
            f"Follow it with: matsya job wait {scheduled.get('id')}",
        ]
    return lines


def _citation_lines(citations: list[dict[str, Any]]) -> list[str]:
    lines = ["", "Citations:"]
    for number, citation in enumerate(citations, 1):
        identity = citation.get("identity") or {}
        path = citation.get("path") or identity.get("target") or "material with no path"
        lines.append(f"  [{number}] {_place(path, citation.get('location'), citation.get('heading'))}")
        if citation.get("quote"):
            lines.append(f'      "{citation["quote"]}"')
    return lines


def _turn_lines(turn: dict[str, Any]) -> list[str]:
    """A turn that has ended, for a person: the job whose outputs it read,
    by the text of its label and its identifier; the answer with its
    citations' paths and headings, Matsya's questions, or why the turn
    stopped."""
    if turn.get("state") != "finished":
        line = f"Turn {turn.get('id')}: {turn.get('state')}"
        if turn.get("error"):
            line += f", error {turn['error']}"
        return [line] + ([f"Detail: {turn['error_detail']}"] if turn.get("error_detail") else [])
    result = (turn.get("record") or {}).get("result") or {}
    lines = []
    if isinstance(result.get("job"), dict):
        lines.append(f"Answer from {_job_name(result['job'])}")
    if result.get("status") == "needs_input":
        lines.append("Matsya asks:")
        questions = result.get("questions") or []
        lines += [f"  {number}. {question}" for number, question in enumerate(questions, 1)]
    else:
        if result.get("status") == "incomplete":
            lines.append(f"The turn ended incomplete, reason {result.get('reason')}.")
        lines.append(str(result.get("answer", "")).rstrip())
    if result.get("citations"):
        lines += _citation_lines(result["citations"])
    if result.get("current") is False:
        lines += [
            "",
            "The session received a later entry while this turn ran; the answer does not take it into account.",
        ]
    started = _job_started(turn)
    if started is not None:
        lines += ["", _started_line(started)]
    return lines


def _job_started(turn: dict[str, Any]) -> dict[str, Any] | None:
    """The job a finished turn started from its session, `{"id", "label"}`
    (AMD-MAT-009 §3), or None."""
    result = (turn.get("record") or {}).get("result") or {}
    started = result.get("job_started")
    return started if isinstance(started, dict) and started.get("id") else None


def _started_line(started: dict[str, Any]) -> str:
    """The line `ask` prints for the job a turn started: its number, the
    version of the session's text it was built from and its identifier
    (AMD-MAT-009 §5)."""
    job_id = started.get("id")
    label = started.get("label") if isinstance(started.get("label"), dict) else {}
    number, revision = label.get("number"), label.get("revision")
    if number is None or revision is None:
        return f"A job started ({job_id}); follow it with: matsya job wait {job_id}"
    return (
        f"Job {number} started from version {revision} of this session's text ({job_id}); "
        f"follow it with: matsya job wait {job_id}"
    )


# -- the commands


def _index(client: MatsyaClient, args: argparse.Namespace) -> list[str]:
    return _index_lines(client.index())


def _search(client: MatsyaClient, args: argparse.Namespace) -> list[str]:
    collections = None
    if args.collections:
        collections = [
            name.strip() for item in args.collections for name in item.split(",") if name.strip()
        ]
    return _search_lines(client.search(args.query, limit=args.limit, collections=collections))


def _started_lines(job: dict[str, Any]) -> list[str]:
    return [
        f"Job {job.get('id')}: {job.get('state')}",
        f"Follow it with: matsya job wait {job.get('id')}",
    ]


def _kept_line(session_id: object) -> str:
    return (
        "The session, where the job's questions and your replies are kept: "
        f"matsya session show {session_id}"
    )


def _job_submit(client: MatsyaClient, args: argparse.Namespace) -> list[str]:
    options = {"max_cycles": args.max_cycles, "force": True if args.force else None}
    if args.file is None:
        # the job reads the session's entries as they stand
        job = client.submit_job(session=args.session, **options)
        return _started_lines(job) + [_kept_line(args.session)]
    try:
        started = client.start_job(
            args.file, name=args.name, session=args.session, no_session=args.no_session, **options
        )
    except OSError as error:
        raise CommandError(f"cannot read {args.file}: {error.strerror or error}") from None
    except ValueError as error:
        raise CommandError(str(error)) from None
    job, listing = started["job"], started["entry"]
    if listing is None:
        # no session: the user asked for none, or the file is a PDF
        reason = (
            "The job has no session"
            if args.no_session
            else "A PDF cannot be attached to a session yet, so the job has no session"
        )
        return _started_lines(job) + [
            f"{reason}, and its questions stand in its record only: matsya job status {job.get('id')}"
        ]
    return [
        f"Session {listing.get('id')}: {listing.get('name')}",
        f"Entry {(listing.get('entry') or {}).get('number')}: the text of {args.file}",
        *_started_lines(job),
        _kept_line(listing.get("id")),
    ]


def _job_status(client: MatsyaClient, args: argparse.Namespace) -> list[str]:
    return _job_lines(client.job(args.job_id))


def _job_wait(client: MatsyaClient, args: argparse.Namespace) -> list[str]:
    report = _reporter(sys.stderr if args.json else sys.stdout)
    return _job_lines(client.wait_job(args.job_id, interval=args.interval, on_change=report))


def _written_lines(paths: list[Path], folder: str) -> list[str]:
    """The files `job_files` wrote, by their paths within the folder."""
    return [f"Wrote {len(paths)} files to {folder}:"] + [
        f"  {path.relative_to(folder).as_posix()}" for path in paths
    ]


def _job_files(client: MatsyaClient, args: argparse.Namespace) -> list[str]:
    paths = client.job_files(
        args.job_id, args.folder, overwrite=args.overwrite, all_iterates=args.all_iterates
    )
    return _written_lines(paths, args.folder)


def _job_cancel(client: MatsyaClient, args: argparse.Namespace) -> list[str]:
    job = client.cancel_job(args.job_id)
    lines = _job_lines(job)
    if job.get("state") not in JOB_FINAL_STATES:
        lines.append(f"Follow it with: matsya job wait {job.get('id')}")
    return lines


def _session_new(client: MatsyaClient, args: argparse.Namespace) -> list[str]:
    return _new_session_lines(client.new_session(args.name))


def _session_add(client: MatsyaClient, args: argparse.Namespace) -> list[str]:
    text = None if args.kind == "acceptance" else _entry_text(args.file)
    answer = client.add_entry(
        args.session_id,
        text,
        kind=args.kind,
        replies_to=args.replies_to,
        delivery_id=args.delivery_id,
    )
    return _entry_added_lines(answer)


def _session_show(client: MatsyaClient, args: argparse.Namespace) -> list[str]:
    return _session_lines(client.session(args.session_id))


def _session_select(client: MatsyaClient, args: argparse.Namespace) -> list[str]:
    job_id = None if args.none else args.job_id
    return _selection_lines(client.select_job(args.session_id, job_id))


def _ask(client: MatsyaClient, args: argparse.Namespace) -> list[str]:
    """Ask one question and print the answer; with `--follow`, wait for the
    job the turn started, as `job wait` does, and write its model folder, as
    `job files` does (AMD-MAT-009 §5). The folder is checked before the
    question is sent, so that a folder that is not empty refuses the command
    before any request."""
    if args.follow is not None:
        check_folder(args.follow)
    stream = sys.stderr if args.json else sys.stdout
    report = _reporter(stream)
    turn = client.ask(
        args.session_id,
        args.question,
        stage_file_path=args.stage_file,
        index_digest=args.index_digest,
        interval=TURN_INTERVAL if args.interval is None else args.interval,
        on_change=report,
    )
    lines = _turn_lines(turn)
    if args.follow is None:
        return lines
    started = _job_started(turn)
    if started is None:
        return lines + ["", "The turn started no job, so no folder was written."]
    # the answer is printed before the wait, which may last many minutes; with
    # --json the command prints the turn's answer at its end
    answered = client.last_text
    if not args.json:
        print("\n".join(lines), flush=True)
    args.followed_job = started["id"]
    job = client.wait_job(
        started["id"],
        interval=JOB_INTERVAL if args.interval is None else args.interval,
        on_change=report,
    )
    lines = _job_lines(job)
    if isinstance(job.get("result"), dict):
        lines += _written_lines(client.job_files(started["id"], args.follow), args.follow)
    else:
        lines.append(f"Job {started['id']} holds no record, so no folder was written.")
    client.last_text = answered
    return lines


# -- configure


def _run_configure() -> None:
    """Ask for the Matsya token and the service address and save them in the
    user's configuration file; nothing is sent to the service."""
    print("Matsya: save your Matsya token and the service address\n")
    token = input("Enter your Matsya token: ").strip()

    if not token.startswith("msy_"):
        print(
            "Error: a Matsya token begins with msy_. "
            "Check the Matsya token you received and try again.",
            file=sys.stderr,
        )
        sys.exit(1)

    server = input("Enter the service address supplied by AAS: ").strip()
    try:
        path = save_config(token, server or None)
    except ConfigurationError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    print(f"Matsya token and service address saved to {path}")
    print()
    print("The service keeps the entries of your sessions and the records of your jobs.")
    print()
    print("Check your access with: matsya index")


def _build_client() -> MatsyaClient:
    """A client with the saved Matsya token and service address, or the
    values of MATSYA_TOKEN and MATSYA_SERVER; the command stops with status 1
    when either is missing."""
    try:
        cfg = load_config()
    except ConfigurationError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    token = cfg["token"]
    if not token:
        print(
            "Error: no Matsya token is configured. Run matsya configure, "
            "or set the environment variable MATSYA_TOKEN.",
            file=sys.stderr,
        )
        sys.exit(1)
    return MatsyaClient(token=token, server_url=cfg["server"])


# -- the parser


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="matsya",
        description=(
            "Client of the Matsya service of spec 0.3: search the index, run jobs of "
            "architect mode and ask questions in sessions."
        ),
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    commands = parser.add_subparsers(dest="command", metavar="<command>")
    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument(
        "--json", action="store_true", help="print the service's JSON answer as it arrived"
    )

    commands.add_parser("configure", help="save your Matsya token and the service address")

    index = commands.add_parser(
        "index", parents=[shared], help="the retrieval index and configuration the service reads"
    )
    index.set_defaults(handler=_index)

    search = commands.add_parser("search", parents=[shared], help="search the index")
    search.add_argument("query")
    search.add_argument(
        "--collections",
        action="append",
        metavar="NAMES",
        help=(
            "the collections to search, separated by commas: repository, literature, "
            "articles, hark, buffer_stock (the service's default is repository and buffer_stock)"
        ),
    )
    search.add_argument(
        "--limit", type=int, help="the number of passages, 1 to 20 (the service's default is 8)"
    )
    search.set_defaults(handler=_search)

    job = commands.add_parser("job", help="jobs of architect mode")
    job_commands = job.add_subparsers(dest="job_command", metavar="<job command>", required=True)
    submit = job_commands.add_parser(
        "submit",
        parents=[shared],
        help="start a job from a description kept in a session, from a PDF or from a session",
    )
    submit.add_argument(
        "file",
        nargs="?",
        help=(
            "a model description in Markdown or text, kept as an entry of the job's session, "
            "or a paper's PDF, sent with no session"
        ),
    )
    session_options = submit.add_mutually_exclusive_group()
    session_options.add_argument(
        "--name",
        help="the name of the session created for the job (default: the file's name without its extension)",
    )
    session_options.add_argument(
        "--session",
        help=(
            "append the file to this session and start the job from it; with no file, start "
            "the job from the session's entries as they stand"
        ),
    )
    session_options.add_argument(
        "--no-session",
        action="store_true",
        help="send the file as the job's source with no session; its questions then stand in its record only",
    )
    submit.add_argument("--max-cycles", type=int, help="the most cycles of writing and checking")
    submit.add_argument(
        "--force",
        action="store_true",
        help=(
            "go on to writing when preparation ends with questions; every assumption "
            "Prose-to-Bellman-Sym supplies is recorded"
        ),
    )
    submit.set_defaults(handler=_job_submit)
    status = job_commands.add_parser("status", parents=[shared], help="a job's state")
    status.add_argument("job_id", metavar="job")
    status.set_defaults(handler=_job_status)
    wait = job_commands.add_parser(
        "wait", parents=[shared], help="wait until a job has ended, printing its step and cycle"
    )
    wait.add_argument("job_id", metavar="job")
    wait.add_argument(
        "--interval", type=float, default=5.0, help="seconds between two requests (default 5)"
    )
    wait.set_defaults(handler=_job_wait)
    files = job_commands.add_parser(
        "files",
        parents=[shared],
        help=(
            "write an ended job's model folder: economics.md, report.md, the stage files under "
            "declaration/ and record.json"
        ),
    )
    files.add_argument("job_id", metavar="job")
    files.add_argument("folder", help="a new or empty folder")
    files.add_argument(
        "--all-iterates",
        action="store_true",
        help=(
            "also write, for training, every cycle's files, prose and verdicts under iterates/ "
            "and the full record"
        ),
    )
    files.add_argument(
        "--overwrite",
        action="store_true",
        help="write into a folder that is not empty, replacing the files of the same names",
    )
    files.set_defaults(handler=_job_files)
    cancel = job_commands.add_parser(
        "cancel",
        parents=[shared],
        help="cancel a queued or running job; a job that has ended cannot be cancelled",
    )
    cancel.add_argument("job_id", metavar="job")
    cancel.set_defaults(handler=_job_cancel)

    session = commands.add_parser(
        "session", help="sessions, the kept text of one model with its jobs' questions and its turns"
    )
    session_commands = session.add_subparsers(
        dest="session_command", metavar="<session command>", required=True
    )
    new = session_commands.add_parser("new", parents=[shared], help="create a session")
    new.add_argument("name")
    new.set_defaults(handler=_session_new)
    add = session_commands.add_parser("add", parents=[shared], help="append an entry to a session")
    add.add_argument("session_id", metavar="session")
    add.add_argument(
        "file", nargs="?", help="a file holding the entry's text; - reads the standard input"
    )
    add.add_argument(
        "--kind",
        choices=("user", "paper", "acceptance"),
        default="user",
        help="user (the default), paper, or acceptance of an answer, which holds no text",
    )
    add.add_argument(
        "--replies-to",
        type=int,
        metavar="N",
        help="the number of the entry this entry replies to, or of the answer it accepts",
    )
    add.add_argument(
        "--delivery-id",
        help="a name of at most 64 characters; a repeated request with it appends nothing",
    )
    add.set_defaults(handler=_session_add)
    show = session_commands.add_parser(
        "show",
        parents=[shared],
        help="a session's entries, its jobs by their labels, its selected job and its turns",
    )
    show.add_argument("session_id", metavar="session")
    show.set_defaults(handler=_session_show)
    select = session_commands.add_parser(
        "select",
        parents=[shared],
        help="select the job whose outputs the session's questions read, or clear the selection",
    )
    select.add_argument("session_id", metavar="session")
    select.add_argument(
        "job_id", metavar="job", nargs="?", help="a job of the session that holds a record"
    )
    select.add_argument(
        "--none",
        action="store_true",
        help=(
            "clear the selection; questions then read the session's latest current job "
            "that holds a record"
        ),
    )
    select.set_defaults(handler=_session_select)

    ask = commands.add_parser(
        "ask",
        parents=[shared],
        help="ask one question in a session, a turn of conversation mode, and print the answer",
    )
    ask.add_argument("session_id", metavar="session")
    ask.add_argument("question")
    ask.add_argument(
        "--stage-file",
        help="a stage file the question is about; the service elaborates it, and the answer reads its dossier",
    )
    ask.add_argument("--index-digest", help="the digest of an earlier version of the index to read")
    ask.add_argument(
        "--follow",
        metavar="FOLDER",
        help=(
            "when the answer starts a job, wait for it and write its model folder into FOLDER, "
            "a new or empty folder"
        ),
    )
    ask.add_argument(
        "--interval",
        type=float,
        help=(
            "seconds between two requests (default 2 for the turn and 5 for the job --follow "
            "waits for)"
        ),
    )
    ask.set_defaults(handler=_ask)
    return parser


def _check_arguments(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    """Refuse, before any request, the arguments the routes do not accept
    together."""
    if args.command == "job" and args.job_command == "submit":
        if args.file is None and args.session is None:
            parser.error("job submit needs a description or PDF file, or --session")
        if args.max_cycles is not None and args.max_cycles < 1:
            parser.error("--max-cycles must be a positive integer")
    if args.command == "session" and args.session_command == "add":
        if args.kind == "acceptance":
            if args.file is not None or args.replies_to is None:
                parser.error(
                    "an acceptance holds no text and names in --replies-to the answer it accepts"
                )
        elif args.file is None:
            parser.error(f"a {args.kind} entry needs a file holding its text (- reads the standard input)")
    if args.command == "session" and args.session_command == "select":
        if (args.job_id is None) == (not args.none):
            parser.error("session select names a job, or --none to clear the selection, and not both")
    if getattr(args, "interval", None) is not None and args.interval < 0:
        parser.error("--interval cannot be negative")


def _stopped(args: argparse.Namespace) -> str:
    """What the user reads when they stop a command that waits."""
    if args.command == "ask" and getattr(args, "followed_job", None):
        return (
            "Stopped waiting. The job goes on running on the service: "
            f"matsya job wait {args.followed_job}; write its folder with: "
            f"matsya job files {args.followed_job} {args.follow}"
        )
    if args.command == "ask":
        return (
            "Stopped waiting. The turn goes on running on the service, and its answer "
            f"is appended to the session: matsya session show {args.session_id}"
        )
    if args.command == "job" and args.job_command == "cancel":
        return (
            "Stopped before the service answered; whether the job was cancelled shows in: "
            f"matsya job status {args.job_id}"
        )
    if args.command == "job" and getattr(args, "job_id", None):
        return (
            "Stopped waiting. The job goes on running on the service: "
            f"matsya job wait {args.job_id}"
        )
    return "Stopped."


def main(argv: list[str] | None = None) -> int:
    """Run the command that `argv`, or the command line, names, and return
    its exit status: 0 when it was carried out, 1 when the service refused
    the request or the client could not send it."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    if args.command == "configure":
        _run_configure()
        return 0
    _check_arguments(parser, args)
    client = _build_client()
    try:
        lines = args.handler(client, args)
    except (MatsyaError, CommandError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    except OSError as error:
        reason = f"{error.strerror}: {error.filename}" if error.strerror and error.filename else error
        print(f"Error: {reason}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print(f"\n{_stopped(args)}", file=sys.stderr)
        return 130
    print(client.last_text if args.json else "\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
