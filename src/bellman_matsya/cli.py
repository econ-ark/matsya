"""The command `bellman-matsya`, which calls the routes of the Matsya service of
spec 0.3 from a terminal and prints the user guide installed with it:

    matsya
    bellman-matsya docs [<page> | --all] [--online]
    bellman-matsya docs --path
    bellman-matsya configure [--set-anthropic-key | --clear-anthropic-key]
    bellman-matsya index
    bellman-matsya search "<query>" [--collections NAMES] [--limit N]
    bellman-matsya job submit <file> --target {stage,period,trellis,recipe} [--paper]
                             [--name NAME | --session <session> | --no-session]
                             [--max-cycles N] [--force] [--configuration-id ID]
                             [--model-key KEY --source-cluster CLUSTER] [--formulation TEXT]
    bellman-matsya job submit --session <session> --target {stage,period,trellis,recipe}
                      [--max-cycles N] [--force] [--configuration-id ID] [--formulation TEXT]
    bellman-matsya job status <job>
    bellman-matsya job wait <job> [--interval SECONDS]
    bellman-matsya job files <job> <folder> [--all-iterates] [--overwrite]
    bellman-matsya job export <job> <folder> [--overwrite]
    bellman-matsya job cancel <job>
    bellman-matsya session new "<name>"
    bellman-matsya session add <session> <file> [--kind user|paper] [--replies-to N]
    bellman-matsya session add <session> --kind acceptance --replies-to N
    bellman-matsya session show <session>
    bellman-matsya session select <session> <job>
    bellman-matsya session select <session> --none
    bellman-matsya ask <session> "<question>" [--stage-file PATH] [--index-digest DIGEST]
                                      [--follow FOLDER] [--configuration-id ID]
    bellman-matsya project init [<folder>]
    bellman-matsya project submit [--target {stage,period,trellis,recipe}] [--max-cycles N]
                                  [--configuration-id ID]
    bellman-matsya project status
    bellman-matsya project pull [<job>] [--replace | --into [SUBFOLDER]]
    bellman-matsya configuration publish <folder>
    bellman-matsya configuration set-default <id>

`job submit <file>` keeps the file, text in UTF-8, in a session, new and
named after the file unless `--session` names one, as an entry of the kind
`user`, a description, or with `--paper` of the kind `paper`, and starts the
job from it; `--no-session` sends the file as the job's source instead, a
description or with `--paper` a paper. A PDF, known by its name or its first
bytes, is refused by `job submit` and `session add` before any request, with
exit status 2 and the sentence `PDF_REFUSAL` (AMD-MAT-012 §2). Every job
names its target, the level of the declaration it returns, `stage`,
`period`, `trellis` or `recipe` (AMD-MAT-011 §3):
`job submit` requires `--target`, and without it, or with another word, the
command is refused with exit status 2 before any request, argparse printing
the four words in the command's usage line. A job of a session is printed
with the text of its label, such as "Household with firms · trellis ·
version 2 · job 7 · converged": the session's name, the job's target, the
version of its text the job read, the job's number among the session's jobs
and its state (AMD-MAT-008 §2); a job of no session is printed with its
target and its state, such as "trellis · converged". A job that has ended is
printed with the first two headings of its report, the label with the
identifiers and the status sentence; `job files` writes its model folder and
report (AMD-MAT-010 §§4 and 5), and `ask --follow` waits for the job a turn
started and writes its folder (AMD-MAT-009 §5). Every command but
`configure` and `docs` takes `--json`, which prints the service's JSON
answer as it arrived, for `job submit` the job's and for `ask` the turn's,
and for a `project` command the answer the client composes (below);
otherwise the command prints plain text for a person. A refusal of the
service is printed with the service's own message, and the command exits
with status 1. No output shows the Matsya token.

`bellman-matsya` alone prints an orientation in Markdown: what Matsya is, where the
user guide is installed, the version of the client it describes, the
commands that print it and the one that upgrades the client, and whether a
Matsya token is saved; `docs` lists the guide's pages and prints them as
they are installed or, with `--online`, as the client's public repository
holds them today (AMD-MAT-015 §2). A command run at the first use of the
client on a machine, with no configuration file and BELLMAN_MATSYA_TOKEN unset,
first prints two lines that send an assistant working for the user to the guide;
`bellman-matsya` alone, `docs` and `--help` need no Matsya token and do not print
them.

A job or a question names a published configuration with
`--configuration-id`, or takes the service's default; `job export` saves a
job's full answer as `job.json` for any state of the job; `configuration
publish` sends a checked configuration folder and `configuration
set-default` changes the default, both refused by the service for a user
without administrator permission (AMD-MAT-020 §§2–3).

`project` works on a project folder, a model folder that remembers its
session in `.bellman-matsya/project.json` (AMD-MAT-013 §§2 and 3, `bellman_matsya.project`):
`init` makes the folder a project, `submit` sends `economics.md` when it has
changed and the files of `declaration/` as a job's starting declaration,
`status` prints the session with the questions awaiting a reply, and `pull`
writes a job's products into the folder or into a sub-folder. Each runs in
the project folder, `init` in the folder it names, and with `--json` prints
the answer the client composes from the folder and the service's answers,
the dictionary the function of `bellman_matsya.project` returns. A command the
client does not carry out, such as one run in a folder that is no project,
is refused with one sentence and exit status 2, before any request. In a
project folder, `bellman-matsya` alone adds the folder's session, its latest job's
label and the questions awaiting a reply to the orientation (AMD-MAT-015
§2).

A registered holder of a Matsya token may add a personal Anthropic API key
once the Matsya token is configured, never in its place (AMD-MAT-021 §2).
`configure --set-anthropic-key` asks for the key at a prompt that does not
show it and saves it in an owner-only file, `configure --clear-anthropic-key`
removes it, and a nonempty BELLMAN_MATSYA_ANTHROPIC_KEY supplies a key
without saving it, in place of a saved key. The selected key is checked
before the client is built, and a key that an HTTP header cannot carry is
refused with one sentence naming its source and exit status 1. The key is
sent only by `job submit`, `project submit`, `ask` and `session add` of a
`user` entry with `--replies-to`, which are refused before their first
request at an address that is neither HTTPS nor a literal loopback host,
unless the environment holds BELLMAN_MATSYA_ANTHROPIC_KEY_OVER_HTTP=accept
(`key_over_http_accepted`, D-021-4), when the command sends the key and
prints `client.KEY_OVER_HTTP_WARNING` once on standard error.
For new work sent with the key, a command prints `CREDENTIAL_LINE` when the
service reports `credential_source` `client`; otherwise it prints its usual
lines, reports on standard error that the service accepted the work under
its own key, and exits with status 1. `job status` and `job wait` print the
same line for a job run with a personal key, and `bellman-matsya` alone
names the credential that the next job, question or reply uses. Every line
the command composes, its errors among them, shows the Matsya token as
`<Matsya token>` and the key as `<Anthropic API key>`.
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
import textwrap
import time
from pathlib import Path
from typing import Any, Callable

from bellman_matsya import __version__, guide, project
from bellman_matsya.client import (
    CONFIGURATION_ID,
    CONFIGURATION_ID_REFUSAL,
    EXPORT_FILE,
    JOB_FINAL_STATES,
    CHAIN_SCHEMA,
    PDF_REFUSAL,
    TARGETS,
    MatsyaClient,
    MatsyaError,
    _check_formulation,
    _item,
    _report_sections,
    check_folder,
    is_pdf,
    available_writing_files,
    key_destination_allowed,
    key_over_http_accepted,
)
from bellman_matsya.config import (
    ANTHROPIC_KEY_VARIABLE,
    ConfigurationError,
    anthropic_key_file,
    check_anthropic_key,
    clear_anthropic_key,
    first_use,
    load_config,
    save_anthropic_key,
    save_config,
    selected_anthropic_key,
    token_file,
)
from bellman_matsya.project import ProjectRefusal

# The roles displayed for job steps. `reconstruction` remains for records
# created before the adjacent-iteration procedure.
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
# what Matsya is and its three parts, in the words of the summary of the user
# guide's page `index.md`, which the orientation prints (AMD-MAT-015 §2)
ABOUT = (
    "Matsya turns an economist's description of a dynamic model, or a paper, into a "
    "declaration in Bellman-SYM, Project Bellman's language for staged Bellman problems, "
    "checks the declaration, and answers questions about models and about the language. "
    "It has three parts: **matsya-client**, the command you run on your own machine, a "
    "program with no language model in it; **matsya-architect**, the service's job side, "
    "which builds and checks a declaration in one run; and **matsya-master**, the "
    "service's conversation side, which answers one question at a time."
)
# the command that upgrades the client and the guide installed with it, which
# the orientation prints (AMD-MAT-015 §2)
UPGRADE = (
    "python -m pip install --force-reinstall "
    "git+https://github.com/econ-ark/matsya.git"
)
# the two lines a command prints first at the first use of the client on a
# machine (AMD-MAT-015 §2)
FIRST_USE = (
    "This is the first use of bellman-matsya on this machine.\n"
    "An assistant working for the user reads the guide first: bellman-matsya docs --all"
)
# the line printed for new work that the service ran with the holder's
# personal Anthropic key, and by `job status` and `job wait` for such a job
# (AMD-MAT-021 §2.5)
CREDENTIAL_LINE = "Credential: your Anthropic API key"
# the refusal of `configure --set-anthropic-key` on a machine with no Matsya
# token (AMD-MAT-021 §2.1)
NO_TOKEN_FOR_KEY = (
    "Error: no Matsya token is configured. A personal Anthropic key is an addition to a Matsya "
    "token, not a substitute for it: save the Matsya token the service's administrator gave you "
    "with bellman-matsya configure, or set BELLMAN_MATSYA_TOKEN."
)
# the refusals of a key that is empty or holds a character an HTTP header
# does not allow: a selected key, by its source, and a key entered at the
# prompt of `configure --set-anthropic-key` (AMD-MAT-021 §2.2)
VARIABLE_KEY_REFUSAL = (
    "Error: the personal Anthropic key in BELLMAN_MATSYA_ANTHROPIC_KEY is empty or contains a "
    "space, a line break or another character that an HTTP header does not allow; set the "
    "variable to the key alone, or unset it to use the service's key."
)
FILE_KEY_REFUSAL = (
    "Error: the personal Anthropic key in the saved file {path} is empty or contains a space, a "
    "line break or another character that an HTTP header does not allow; set it again with "
    "bellman-matsya configure --set-anthropic-key, or remove it with bellman-matsya configure "
    "--clear-anthropic-key."
)
ENTERED_KEY_REFUSAL = (
    "Error: the key you entered is empty or contains a space, a line break or another character "
    "that an HTTP header does not allow; nothing was saved."
)
# the prompt of `configure --set-anthropic-key`, which does not show what is
# typed
KEY_PROMPT = "Enter your Anthropic API key (it is not shown): "
# the orientation's line on the credential the next job, question or reply
# uses, in its three states, checked in this order, and the sentence added
# when a key is selected and the service address would not receive it
# (AMD-MAT-021 §2.5); `configure --set-anthropic-key` prints the same
# sentence after it saves a key at such an address
KEY_FROM_VARIABLE = (
    "The environment variable `BELLMAN_MATSYA_ANTHROPIC_KEY` is set; new jobs, questions and "
    "replies that continue a job use its value in place of any saved key, and the Anthropic "
    "account of that key is charged."
)
KEY_SAVED = (
    "A personal Anthropic key is saved on this machine, in `{file}`; new jobs, questions and "
    "replies that continue a job use it, and the Anthropic account of that key is charged."
)
NO_KEY = (
    "No personal Anthropic key is selected; new jobs and questions use the service's key, and a "
    "reply that would continue a job run with a personal key is refused until one is selected."
)
PLAIN_HTTP = (
    "The service address {address} uses plain HTTP, so the client refuses to send a job, a "
    "question or a reply with this key."
)
# the sentence printed in place of PLAIN_HTTP when the environment holds
# BELLMAN_MATSYA_ANTHROPIC_KEY_OVER_HTTP=accept (`key_over_http_accepted`, D-021-4)
KEY_OVER_HTTP = (
    "BELLMAN_MATSYA_ANTHROPIC_KEY_OVER_HTTP=accept is set, so the client sends this key "
    "unencrypted to {address}, which uses plain HTTP."
)

EPILOG = """\
Read first:
  bellman-matsya                     what Matsya is and where its user guide is installed
  bellman-matsya docs --all                  the user guide, every page in Markdown

Set up once:
  bellman-matsya configure                   save your Matsya token
  export BELLMAN_MATSYA_SERVER=...           override the Bellman service address
  export BELLMAN_MATSYA_TOKEN=...            override the saved Matsya token

Optional additions, once the Matsya token is configured: your own Anthropic API key, whose
account is then charged for your jobs, your questions and your replies that continue a job:
  bellman-matsya configure --set-anthropic-key     save the key; the prompt does not show it
  bellman-matsya configure --clear-anthropic-key   remove the saved key
  export BELLMAN_MATSYA_ANTHROPIC_KEY="$(cat <private file>)"
                                                   use a key without saving it

Examples:
  bellman-matsya index
  bellman-matsya search "decision perch state and controls" --collections repository --limit 4
  bellman-matsya job submit model.md --target trellis
  bellman-matsya job submit paper.md --paper --target stage
  bellman-matsya job wait <job>
  bellman-matsya session show <session>
  bellman-matsya session add <session> reply.md --replies-to <number>
  bellman-matsya job files <job> proposed-model
  bellman-matsya job files <job> proposed-model-iterates --all-iterates
  bellman-matsya job export <job> records/case-1/trial-1
  bellman-matsya job cancel <job>
  bellman-matsya session new "a household"
  bellman-matsya ask <session> "What does the decision perch of a stage hold?"
  bellman-matsya ask <session> "Submit this as a job." --follow proposed-model
  bellman-matsya session select <session> <job>

Work on a project folder, a model folder that remembers its session:
  bellman-matsya project init                make this folder a project, with its session
  bellman-matsya project submit              send economics.md and declaration/ as a job
  bellman-matsya project status              the session, its jobs and its questions
  bellman-matsya project pull --replace      write the latest job's files into this folder
  bellman-matsya project pull                write them into bellman-matsya-output/job-<number>/

Publish and select configurations (an administrator publishes and sets the default):
  bellman-matsya configuration publish <folder>
  bellman-matsya job submit model.md --target stage --no-session --configuration-id <id>
  bellman-matsya configuration set-default <id>
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


def _names_a_pdf(name: str) -> bool:
    """Whether the file a command names is a PDF, by its name or, when the
    file can be read, by its first bytes (`is_pdf`); a file that cannot be
    read is refused later, with the reason."""
    try:
        with open(name, "rb") as handle:
            start = handle.read(5)
    except OSError:
        start = b""
    return is_pdf(name, start)


def _entry_text(name: str) -> str:
    """The text of an entry: the file's text, or the standard input for `-`;
    a file that is a PDF was refused before, by `_check_arguments`."""
    if name == "-":
        return sys.stdin.read()
    return _decoded(_file_bytes(name), name)


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
    if step == "writing" and cycle == 0:
        text += ", initial declaration"
    elif cycle:  # cycle 0 is also used by preparation and a turn
        text += f", cycle {cycle}" + (f" of {limit}" if limit else "")
    return text


def _reporter(stream: Any, hidden: Callable[[str], str]) -> Callable[[dict[str, Any]], None]:
    """The function that prints a job's or a turn's state, step and cycle
    whenever they change while the command waits, each line passed through
    `hidden`, the client's mask of the Matsya token and the personal key
    (AMD-MAT-021 §2.5)."""

    def report(answer: dict[str, Any]) -> None:
        if answer.get("state") in ("queued", "running"):
            step = _step_text(answer.get("progress"))
            line = f"{answer['state']}: {step}" if step else str(answer["state"])
            print(f"{time.strftime('%H:%M:%S')}  {hidden(line)}", file=stream, flush=True)

    return report


def _index_lines(index: dict[str, Any]) -> list[str]:
    return [
        f"Index digest: {index.get('index_digest')}",
        f"Embedding model: {index.get('embedding_model_id')}",
        f"Configuration ID: {index.get('configuration_id')}",
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
    """The text of a job's label (AMD-MAT-008 §2), as the service gives it,
    such as "Household with firms · trellis · version 2 · job 7 · converged",
    the job's target after the session's name (AMD-MAT-011 §3), or None
    when the record carries no label."""
    label = job.get("label")
    text = label.get("text") if isinstance(label, dict) else None
    return text if isinstance(text, str) and text.strip() else None


def _job_name(job: dict[str, Any]) -> str:
    """A job by the text of its label and its identifier, such as
    "Household with firms · trellis · version 2 · job 7 · converged
    (<job>)", or "job <job>" when the record carries no label."""
    text = _label_text(job)
    return f"{text} ({job.get('id')})" if text else f"job {job.get('id')}"


def _label_lines(job: dict[str, Any]) -> list[str]:
    """The line of a job's label that begins its printed form. The label of
    a job of no session is its target and its state, such as "trellis ·
    queued" (AMD-MAT-011 §3), and is printed as its own line; a label that
    is the job's state alone, that of a job of no session whose request
    names no target, which a job created before AMD-MAT-011 is, adds no
    line, since the next line states the state."""
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
                f"The questions stand as entries of session {session}: bellman-matsya session show {session}",
                f"Reply to one with: bellman-matsya session add {session} <file> --replies-to <its entry number>",
            ]
    files = available_writing_files(record)
    if files:
        available = record.get("available_writing")
        cycle = available.get("cycle") if isinstance(available, dict) else None
        if type(cycle) is int:
            source = (
                "the initial writing"
                if record.get("schema") == CHAIN_SCHEMA and cycle == 0
                else f"cycle {cycle}"
            )
            qualifier = "provisional " if state != "converged" else ""
            label = f"Available {qualifier}files from {source}: "
        else:
            label = "Files of the last cycle: "
        lines.append(label + ", ".join(files))
    lines.append(f"Write the model folder and its report with: bellman-matsya job files {job_id} <folder>")
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
            f"selection with: bellman-matsya session select {session_id} --none",
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
        f"Add an entry with: bellman-matsya session add {session_id} <file>",
        f'Ask a question with: bellman-matsya ask {session_id} "<question>"',
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
            f"Follow it with: bellman-matsya job wait {scheduled.get('id')}",
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
        return f"A job started ({job_id}); follow it with: bellman-matsya job wait {job_id}"
    return (
        f"Job {number} started from version {revision} of this session's text ({job_id}); "
        f"follow it with: bellman-matsya job wait {job_id}"
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
        f"Follow it with: bellman-matsya job wait {job.get('id')}",
    ]


def _kept_line(session_id: object) -> str:
    return (
        "The session, where the job's questions and your replies are kept: "
        f"bellman-matsya session show {session_id}"
    )


def _credential_lines(
    client: MatsyaClient, args: argparse.Namespace, work: dict[str, Any], kind: str
) -> list[str]:
    """The line on the credential of new work, a job or a turn, that the
    client sent with a personal Anthropic key (AMD-MAT-021 §2.5):
    `CREDENTIAL_LINE` when the work's `credential_source` is `client`.
    When the field is absent or `service`, as from a service built before
    the amendment, which ignores the key, no line is added, and the refusal
    that the command prints on standard error after its usual lines, with
    exit status 1, is kept in `args.credential_refusal`: the service
    accepted the work under its own key, and a job can be cancelled. Both
    lines hold the identifier the service gave and pass through the
    client's mask of the two secrets. A client that holds no key adds
    nothing."""
    if not client.holds_personal_key:
        return []
    if work.get("credential_source") == "client":
        return [CREDENTIAL_LINE]
    work_id = work.get("id")
    args.credential_refusal = [
        client._hidden(
            f"Error: the service at {client.server_url} accepted {kind} {work_id} under its own "
            "Anthropic key, not yours."
        )
    ]
    if kind == "job":
        args.credential_refusal.append(
            client._hidden(f"Cancel it with: bellman-matsya job cancel {work_id}")
        )
    return []


def _status_credential(job: dict[str, Any]) -> list[str]:
    """`CREDENTIAL_LINE` for a job whose `credential_source` is `client`,
    which `job status` and `job wait` print; nothing for a job run with the
    service's key (AMD-MAT-021 §2.5)."""
    return [CREDENTIAL_LINE] if job.get("credential_source") == "client" else []


def _job_submit(client: MatsyaClient, args: argparse.Namespace) -> list[str]:
    # the target, which the parser requires, is sent in every form of the
    # request (AMD-MAT-011 §3)
    options = {
        "target": args.target,
        "max_cycles": args.max_cycles,
        "force": True if args.force else None,
        "configuration_id": args.configuration_id,
        "model_key": args.model_key,
        "source_cluster": args.source_cluster,
        "formulation": args.formulation,
    }
    if args.file is None:
        # the job reads the session's entries as they stand
        job = client.submit_job(session=args.session, **options)
        return (
            _started_lines(job)
            + [_kept_line(args.session)]
            + _credential_lines(client, args, job, "job")
        )
    try:
        started = client.start_job(
            args.file,
            name=args.name,
            session=args.session,
            no_session=args.no_session,
            paper=args.paper,
            **options,
        )
    except OSError as error:
        raise CommandError(f"cannot read {args.file}: {error.strerror or error}") from None
    except ValueError as error:
        raise CommandError(str(error)) from None
    job, listing = started["job"], started["entry"]
    credential = _credential_lines(client, args, job, "job")
    if listing is None:
        # no session, as the user asked with --no-session
        return _started_lines(job) + [
            "The job has no session, and its questions stand in its record only: "
            f"bellman-matsya job status {job.get('id')}"
        ] + credential
    entry = listing.get("entry") or {}
    # a paper is an entry of the kind paper, which the line names
    # (AMD-MAT-012 §2)
    marked = " (paper)" if entry.get("kind") == "paper" else ""
    return [
        f"Session {listing.get('id')}: {listing.get('name')}",
        f"Entry {entry.get('number')}{marked}: the text of {args.file}",
        *_started_lines(job),
        _kept_line(listing.get("id")),
        *credential,
    ]


def _job_status(client: MatsyaClient, args: argparse.Namespace) -> list[str]:
    job = client.job(args.job_id)
    return _job_lines(job) + _status_credential(job)


def _job_wait(client: MatsyaClient, args: argparse.Namespace) -> list[str]:
    report = _reporter(sys.stderr if args.json else sys.stdout, client._hidden)
    job = client.wait_job(args.job_id, interval=args.interval, on_change=report)
    return _job_lines(job) + _status_credential(job)


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


def _job_export(client: MatsyaClient, args: argparse.Namespace) -> list[str]:
    """Save the job's full answer as `job.json` in the folder, for any state
    of the job, and print the path written; with `--json`, the full answer
    is printed as it arrived (AMD-MAT-020 §3)."""
    job = client.export_job(args.job_id, args.folder, overwrite=args.overwrite)
    held = f"Wrote {Path(args.folder) / EXPORT_FILE}: job {job.get('id')}, {job.get('state')}"
    if job.get("error"):
        held += f", error {job['error']}"
    held += f", configuration {job.get('configuration_id')}"
    return [held]


def _job_cancel(client: MatsyaClient, args: argparse.Namespace) -> list[str]:
    job = client.cancel_job(args.job_id)
    lines = _job_lines(job)
    if job.get("state") not in JOB_FINAL_STATES:
        lines.append(f"Follow it with: bellman-matsya job wait {job.get('id')}")
    return lines


def _session_new(client: MatsyaClient, args: argparse.Namespace) -> list[str]:
    return _new_session_lines(client.new_session(args.name))


def _session_add(client: MatsyaClient, args: argparse.Namespace) -> list[str]:
    """Append an entry and print it, with the preparation attempt a reply
    started. A `user` entry with `--replies-to` carries a held personal
    key, and the attempt it scheduled, unless the delivery was repeated, is
    new work whose credential is checked (AMD-MAT-021 §2.5)."""
    text = None if args.kind == "acceptance" else _entry_text(args.file)
    answer = client.add_entry(
        args.session_id,
        text,
        kind=args.kind,
        replies_to=args.replies_to,
        delivery_id=args.delivery_id,
    )
    lines = _entry_added_lines(answer)
    scheduled = answer.get("scheduled")
    if (
        args.kind == "user"
        and args.replies_to is not None
        and isinstance(scheduled, dict)
        and not answer.get("repeated")
    ):
        lines += _credential_lines(client, args, scheduled, "job")
    return lines


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
    before any request. A question sent with a personal Anthropic key is
    followed by the turn's credential line; when the service ran the turn
    under its own key, the command prints its usual lines, the followed
    job's among them, and then reports that the service accepted the turn
    under its own key (AMD-MAT-021 §2.5). The job's lines name its
    credential as `job wait` names it."""
    if args.follow is not None:
        check_folder(args.follow)
    stream = sys.stderr if args.json else sys.stdout
    report = _reporter(stream, client._hidden)
    turn = client.ask(
        args.session_id,
        args.question,
        stage_file_path=args.stage_file,
        index_digest=args.index_digest,
        interval=TURN_INTERVAL if args.interval is None else args.interval,
        on_change=report,
        configuration_id=args.configuration_id,
    )
    lines = _turn_lines(turn) + _credential_lines(client, args, turn, "turn")
    if args.follow is None:
        return lines
    started = _job_started(turn)
    if started is None:
        return lines + ["", "The turn started no job, so no folder was written."]
    # the answer is printed before the wait, which may last many minutes; with
    # --json the command prints the turn's answer at its end
    answered = client.last_text
    if not args.json:
        print(client._hidden("\n".join(lines)), flush=True)
    args.followed_job = started["id"]
    job = client.wait_job(
        started["id"],
        interval=JOB_INTERVAL if args.interval is None else args.interval,
        on_change=report,
    )
    lines = _job_lines(job) + _status_credential(job)
    if isinstance(job.get("result"), dict):
        lines += _written_lines(client.job_files(started["id"], args.follow), args.follow)
    else:
        lines.append(f"Job {started['id']} holds no record, so no folder was written.")
    client.last_text = answered
    return lines


# -- the project folder (AMD-MAT-013 §3)


def _count(number: int, noun: str) -> str:
    """A number of things in words, such as "1 file" or "3 files"."""
    return f"{number} {noun}" + ("" if number == 1 else "s")


def _project_check(args: argparse.Namespace) -> None:
    """Refuse, before the Matsya token is read and before any request, a
    project command the client does not carry out where it is run: `init`
    in a folder that is a file or already a project, `pull` with both
    `--replace` and `--into`, and any other command in a folder that is no
    project. `ProjectRefusal` states the refusal in one sentence."""
    if args.project_command == "init":
        project.check_init(args.folder)
        return
    if args.project_command == "pull" and args.replace and args.into is not None:
        raise ProjectRefusal(project.REPLACE_AND_INTO)
    project.read_project(Path.cwd())


def _project_answer(
    args: argparse.Namespace, function: Callable[..., dict[str, Any]], *arguments: Any, **options: Any
) -> dict[str, Any]:
    """The answer of a function of `bellman_matsya.project`, kept as the answer the
    command prints with `--json`; a file of the folder that is not text in
    UTF-8 (`ValueError`) is refused as a command's unreadable file is."""
    try:
        args.answer = function(*arguments, **options)
    except ValueError as error:
        raise CommandError(str(error)) from None
    return args.answer


def _project_init(client: MatsyaClient, args: argparse.Namespace) -> list[str]:
    """The folder, its new session, the entry of `economics.md`, the files
    written, and `AGENTS.md` written or, when the folder has one, the
    paragraph for the user to add to it."""
    answer = _project_answer(args, project.init, client, args.folder)
    lines = [
        f"Project folder: {answer['folder']}",
        f"Session {answer['project']['session']}: {answer['session'].get('name')}",
    ]
    entry = answer["entry"]
    if entry is None:
        lines.append(
            "The folder holds no economics.md with text, so the session holds no entry yet; "
            "write the model's description in economics.md before you submit the model."
        )
    else:
        lines.append(f"Entry {entry.get('number')}: the text of economics.md")
    lines.append(f"Wrote {project.PROJECT_FILE} and {project.README_FILE}")
    if answer["agents"] == "created":
        lines.append(
            f"Wrote {project.AGENTS_FILE}, whose paragraph points an assistant to "
            f"{project.README_FILE}"
        )
    else:
        lines += [
            f"{project.AGENTS_FILE} exists and was left as it is; add this paragraph to it for an "
            "assistant:",
            "",
            answer["agents_paragraph"],
            "",
        ]
    lines.append("Submit the model, in the project folder, with: bellman-matsya project submit")
    return lines


def _project_submit(client: MatsyaClient, args: argparse.Namespace) -> list[str]:
    """Whether `economics.md` was appended, the starting declaration and
    the files left out of it, the target and where it was read, then the
    job's label and the line that follows the job, and for a job sent with
    a personal Anthropic key its credential line (AMD-MAT-021 §2.5)."""
    answer = _project_answer(
        args,
        project.submit,
        client,
        Path.cwd(),
        target=args.target,
        max_cycles=args.max_cycles,
        configuration_id=args.configuration_id,
    )
    session_id = answer["project"]["session"]
    if answer["economics"] == "appended":
        lines = [
            f"Entry {answer['entry'].get('number')}: the text of economics.md, appended to "
            f"session {session_id}"
        ]
    elif answer["economics"] == "unchanged":
        lines = [
            f"economics.md is unchanged since session {session_id} last received it, so no "
            "entry was appended."
        ]
    else:
        lines = [
            "The folder holds no economics.md with text, so the job reads the entries of "
            f"session {session_id} as they stand."
        ]
    if answer["starting_declaration"]:
        lines.append("Starting declaration: " + ", ".join(answer["starting_declaration"]))
    else:
        lines.append(
            "declaration/ holds no file of a declaration, so the job has no starting declaration."
        )
    if answer["left_out"]:
        lines.append("Left out of the starting declaration: " + ", ".join(answer["left_out"]))
    where = "named by --target" if answer["target_named"] else "read from declaration/"
    lines.append(f"Target: {answer['target']}, {where}")
    job = answer["job"]
    return (
        lines + _label_lines(job) + _started_lines(job) + _credential_lines(client, args, job, "job")
    )


def _project_status(client: MatsyaClient, args: argparse.Namespace) -> list[str]:
    """The session's identifier, name, service and version; its entries;
    its jobs by the text of their labels; its selected job; each question
    awaiting a reply with the command that answers it; the command that
    asks a question; and whether `economics.md` has changed since the
    session last received it."""
    answer = _project_answer(args, project.status, client, Path.cwd())
    session = answer["session"]
    lines = [
        f"Session {session.get('id')}: {session.get('name')}",
        f"Service: {answer['project']['server']}",
        f"Version of the text: {session.get('revision')}",
    ]
    entries = session.get("entries") or []
    lines.append("Entries:" if entries else "Entries: none")
    lines += ["  " + _entry_heading(entry) for entry in entries]
    jobs = session.get("jobs") or []
    lines.append("Jobs:" if jobs else "Jobs: none")
    lines += [f"  {_job_name(job)}" for job in jobs]
    if session.get("selected_job"):
        lines.append(f"Selected job: {_selected_name(session)}")
    questions = answer["awaiting"]
    if questions:
        lines.append("Questions awaiting a reply:")
        for question in questions:
            prefix = f"  {question['number']}. "
            lines += _item(prefix, str(question["text"] or "").strip())
            lines.append(" " * len(prefix) + f"Reply with: {question['reply']}")
    else:
        lines.append("No question awaits a reply.")
    lines.append(f"Ask a question with: {answer['ask']}")
    if answer["economics_changed"] is True:
        lines.append(
            "economics.md has changed since the session last received it; bellman-matsya project "
            "submit appends it."
        )
    elif answer["economics_changed"] is False:
        lines.append("economics.md is unchanged since the session last received it.")
    return lines


def _project_pull(client: MatsyaClient, args: argparse.Namespace) -> list[str]:
    """The first two headings of the job's report, then the files written,
    those that replaced a file of the same path marked, and with
    `--replace` the files of `declaration/` the job did not write, which
    are kept."""
    answer = _project_answer(
        args,
        project.pull,
        client,
        Path.cwd(),
        job=args.job_id,
        replace=args.replace,
        into=args.into,
    )
    lines = [line for _, body in _report_sections(answer["job"])[:2] for line in body]
    written = answer["written"]
    if answer["into"] is None:
        replaced = set(answer["replaced"])
        lines.append(f"Wrote {_count(len(written), 'file')} into this folder:")
        lines += [f"  {path}" + (" (replaced)" if path in replaced else "") for path in written]
        if answer["kept"]:
            lines.append(
                f"Kept {_count(len(answer['kept']), 'file')} of declaration/ that the job did "
                "not write:"
            )
            lines += [f"  {path}" for path in answer["kept"]]
        lines.append("economics.md was not written.")
    else:
        lines.append(f"Wrote {_count(len(written), 'file')} to {answer['into']}:")
        lines += [f"  {path}" for path in written]
        lines.append("declaration/ was not written.")
    return lines


def _project_orientation(folder: Path) -> list[str]:
    """In a project folder, the paragraph the orientation adds (AMD-MAT-015
    §2): the folder's session and service, its latest job by the text of
    its label, and each question awaiting a reply with the command that
    answers it, read with one request to the service the client is
    configured for; where the session cannot be read, the reason. Outside a
    project folder, nothing."""
    if not os.path.lexists(folder / project.PROJECT_FILE):
        return []
    try:
        held = project.read_project(folder)
    except ProjectRefusal as error:
        return ["", f"This folder holds a Matsya project that the client cannot read: {error}"]
    session_id = held["session"]
    opening = (
        f"This folder is a Matsya project: its session is `{session_id}`, kept by the service at "
        f"`{held['server']}`, and `{project.README_FILE}` describes the folder and its commands."
    )
    try:
        settings = load_config()
        if not settings["token"]:
            raise ConfigurationError("no Matsya token is configured; `bellman-matsya configure` saves one.")
        client = MatsyaClient(token=settings["token"], server_url=settings["server"])
        project.check_server(client, held)
        session = client.session(session_id)
    except (ConfigurationError, ProjectRefusal, MatsyaError) as error:
        return ["", f"{opening} The session's state could not be read: {error}"]
    jobs = session.get("jobs") or []
    if not jobs:
        latest = "No job has been submitted from it yet; `bellman-matsya project submit` submits one."
    elif _label_text(jobs[-1]):
        latest = f"Its latest job is {_label_text(jobs[-1])} (`{jobs[-1].get('id')}`)."
    else:
        latest = f"Its latest job is `{jobs[-1].get('id')}`, {jobs[-1].get('state')}."
    questions = project.awaiting(session)
    if not questions:
        return [
            "",
            f"{opening} {latest} No question awaits a reply; `bellman-matsya project status` shows the "
            "session.",
        ]
    count = "One question awaits" if len(questions) == 1 else f"{len(questions)} questions await"
    lines = ["", f"{opening} {latest} {count} a reply:", ""]
    for question in questions:
        text = " ".join(str(question["text"] or "").split())
        lines.append(f"- Entry {question['number']}: {text} Reply with `{question['reply']}`.")
    return lines


# -- the configurations (AMD-MAT-020 §§2 and 3)


def _configuration_publish(client: MatsyaClient, args: argparse.Namespace) -> list[str]:
    """Publish a checked configuration folder and print the ID and the
    version the service answered with; publication does not change the
    default."""
    try:
        answer = client.publish_configuration(args.folder)
    except ValueError as error:
        raise CommandError(str(error)) from None
    identity = answer.get("configuration_id")
    return [
        f"Published configuration {identity}, version {answer.get('version')}",
        "The default is unchanged. Select this configuration for a job with "
        f"--configuration-id {identity}, or make it the default with: "
        f"bellman-matsya configuration set-default {identity}",
    ]


def _configuration_set_default(client: MatsyaClient, args: argparse.Namespace) -> list[str]:
    """Make a published configuration the default and print the former and
    the new default."""
    answer = client.set_default_configuration(args.configuration_id)
    return [
        f"Default configuration: {answer.get('configuration_id')}, version {answer.get('version')}",
        f"Previous default: {answer.get('previous_configuration_id')}",
        "Jobs and questions already accepted keep the configuration pinned to them.",
    ]


# -- the user guide and the orientation


def _key_line() -> str:
    """The orientation's line after its Matsya-token line, which names the
    credential that the next job, question or reply uses and never prints a
    key (AMD-MAT-021 §2.5). Exactly one of three states applies, checked in
    this order: BELLMAN_MATSYA_ANTHROPIC_KEY is set and nonempty; a key is
    saved; no key is selected. When a key is selected and the selected
    service address fails `key_destination_allowed`, the line adds that the
    client refuses to send work with the key there or, under the operator's
    testing override `key_over_http_accepted` (D-021-4), that it sends the
    key unencrypted. The key file is not read."""
    if os.environ.get(ANTHROPIC_KEY_VARIABLE):
        line = KEY_FROM_VARIABLE
    elif anthropic_key_file().is_file():
        line = KEY_SAVED.format(file=anthropic_key_file())
    else:
        return NO_KEY
    try:
        address = load_config()["server"]
    except (ValueError, OSError):
        # an address that cannot be read is refused by every command
        return line
    if not key_destination_allowed(address):
        plain = KEY_OVER_HTTP if key_over_http_accepted() else PLAIN_HTTP
        line += " " + plain.format(address=address)
    return line


def _orientation_lines() -> list[str]:
    """What `bellman-matsya` alone prints, in Markdown (AMD-MAT-015 §2): what Matsya
    is and its three parts, in the words of the user guide's page
    `index.md`; the folder where the guide is installed, the version of the
    client whose commands it describes, the commands that print it as
    installed and as the client's public repository holds it today, and the
    command that upgrades the client; whether a Matsya token is saved on
    this machine, never the Matsya token itself, and on the next line the
    credential that the next job, question or reply uses, never a key
    (`_key_line`, AMD-MAT-021 §2.5); in a project folder, the folder's
    session, its latest job and the questions awaiting a reply
    (`_project_orientation`); and the command that lists the commands."""
    saved = token_file()
    if saved is None:
        token = "No Matsya token is saved on this machine; `bellman-matsya configure` saves it."
    else:
        token = f"A Matsya token is saved on this machine, in `{saved}`."
    if os.environ.get("BELLMAN_MATSYA_TOKEN"):
        token += (
            " The environment variable `BELLMAN_MATSYA_TOKEN` is set, and the commands use its value "
            "in place of a saved Matsya token."
        )
    return [
        "# Matsya",
        "",
        ABOUT,
        "",
        f"The user guide is installed on this machine in the folder `{guide.folder()}`. "
        f"The installed guide describes the commands of this client, version {__version__}. "
        "`bellman-matsya docs` lists its pages, `bellman-matsya docs --all` prints the whole installed guide, "
        "which an assistant working for the user reads first, and `bellman-matsya docs --all --online` "
        "prints the current guide from the public Matsya repository. "
        f"`{UPGRADE}` updates the client and its installed guide.",
        "",
        token,
        _key_line(),
        *_project_orientation(Path.cwd()),
        "",
        "`bellman-matsya --help` lists the commands.",
    ]


def _page_argument(value: str) -> str:
    """The name of the page of the user guide that `value` names, with or
    without `.md`; any other value is refused, with the names of the pages,
    and the command exits with status 2."""
    name = guide.page_name(value)
    if name is None:
        raise argparse.ArgumentTypeError(
            f'no page of the user guide is named "{value}"; the pages are '
            + ", ".join(guide.names())
        )
    return name


def _docs_lines(args: argparse.Namespace) -> list[str]:
    """What `bellman-matsya docs` prints (AMD-MAT-015 §2): with `--path`, the folder
    that holds the pages; with `--all`, every page in order, each after a
    line naming its file; one page by its name; or, with no page named, one
    line for each page, its name and its title. A page is printed in
    Markdown as its file holds it, without its front matter. With
    `--online`, a page printed is read as the client's public repository
    holds it today; the list of pages, and the titles, are the installed
    guide's, and the list sends no request. Every page is read before
    anything is printed, so that a page that cannot be read leaves no part
    of the guide printed."""
    if args.path:
        return [str(guide.folder())]
    text = guide.online_text if args.online else guide.text
    if args.all:
        lines: list[str] = []
        for name in guide.names():
            lines += ([""] if lines else []) + [
                f"<!-- page: {guide.file_name(name)} -->",
                text(name),
            ]
        return lines
    if args.page is not None:
        return [text(args.page)]
    names = guide.names()
    width = max((len(name) for name in names), default=0)
    return [f"{name:<{width}}  {guide.title(name)}" for name in names]


# -- configure


def _run_configure() -> None:
    """Ask for the Matsya token and save it without contacting the service."""
    print("Matsya: save your Matsya token\n")
    token = input("Enter your Matsya token: ").strip()

    if not token.startswith("msy_"):
        print(
            "Error: a Matsya token begins with msy_. "
            "Check the Matsya token you received and try again.",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        path = save_config(token)
    except ConfigurationError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    print(f"Matsya token saved to {path}")
    print(f"Bellman service address: {load_config()['server']}")
    print()
    print("The service keeps the entries of your sessions and the records of your jobs.")
    print()
    print("Check your access with: bellman-matsya index")


def _set_anthropic_key() -> None:
    """`configure --set-anthropic-key` (AMD-MAT-021 §§2.1 and 2.2). A
    personal key is an addition to a Matsya token: without a configured
    Matsya token, saved by `configure` or set in BELLMAN_MATSYA_TOKEN, the
    command prints `NO_TOKEN_FOR_KEY` and exits with status 1, before any
    prompt and without writing anything, and an address that cannot be read
    is reported as `configure` reports it. Otherwise it asks for the key at
    a prompt that does not show it, never for the Matsya token; refuses a
    key that is empty or holds a character an HTTP header does not allow
    with `ENTERED_KEY_REFUSAL`; and saves the key in its owner-only file,
    replacing a key saved before, then prints the file's path, the account
    that is charged and how to remove the key. The key is never printed and
    no service is contacted."""
    try:
        settings = load_config()
    except (ValueError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    if not settings["token"]:
        print(NO_TOKEN_FOR_KEY, file=sys.stderr)
        sys.exit(1)
    print("Matsya: save a personal Anthropic API key\n", flush=True)
    try:
        entered = getpass.getpass(KEY_PROMPT)
    except EOFError:
        # the end of the input is an empty key, which is refused below
        entered = ""
    except KeyboardInterrupt:
        print("\nStopped; nothing was saved.", file=sys.stderr)
        sys.exit(130)
    try:
        check_anthropic_key(entered)
    except ValueError:
        print(ENTERED_KEY_REFUSAL, file=sys.stderr)
        sys.exit(1)
    try:
        path = save_anthropic_key(entered)
    except OSError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    print(f"Personal Anthropic key saved to {path}")
    if os.environ.get(ANTHROPIC_KEY_VARIABLE):
        print(
            "The environment variable BELLMAN_MATSYA_ANTHROPIC_KEY is set, and new jobs, questions "
            "and replies that continue a job use its value in place of this key until it is unset."
        )
    else:
        print(
            "New jobs, questions and replies that continue a job use this key, and the Anthropic "
            "account of this key is charged."
        )
    if not key_destination_allowed(settings["server"]):
        plain = KEY_OVER_HTTP if key_over_http_accepted() else PLAIN_HTTP
        print(plain.format(address=settings["server"]))
    print("Remove it with: bellman-matsya configure --clear-anthropic-key")


def _clear_anthropic_key() -> None:
    """`configure --clear-anthropic-key` (AMD-MAT-021 §2.2): delete the file
    of a saved personal key, which needs no Matsya token, since it only
    removes a value; print whether a saved key was removed and which key the
    next job or question uses."""
    path = anthropic_key_file()
    try:
        removed = clear_anthropic_key()
    except OSError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    if removed:
        print(f"Removed the saved personal Anthropic key, {path}.")
    else:
        print(f"No personal Anthropic key was saved on this machine, in {path}; nothing was removed.")
    if os.environ.get(ANTHROPIC_KEY_VARIABLE):
        print(
            "The environment variable BELLMAN_MATSYA_ANTHROPIC_KEY is set, and new jobs, questions "
            "and replies that continue a job use its value until it is unset."
        )
    else:
        print("New jobs and questions use the service's key.")


def _selected_key() -> str | None:
    """The personal Anthropic key the command sends, BELLMAN_MATSYA_ANTHROPIC_KEY
    when it is set and nonempty, else the saved key, without its
    surrounding whitespace, or None (AMD-MAT-021 §2.2). A selected key that
    is empty or holds a character an HTTP header does not allow is refused
    with the sentence that names its source and the remedy, and exit status
    1, before the client is built; the key is not shown."""
    value, source = selected_anthropic_key()
    if value is None:
        return None
    try:
        return check_anthropic_key(value)
    except ValueError:
        if source == "environment":
            print(VARIABLE_KEY_REFUSAL, file=sys.stderr)
        else:
            print(FILE_KEY_REFUSAL.format(path=source), file=sys.stderr)
        sys.exit(1)


def _build_client() -> MatsyaClient:
    """Use the saved token, the selected address and the selected personal
    Anthropic key (`_selected_key`); refuse a missing token, and a selected
    key that an HTTP header cannot carry."""
    try:
        cfg = load_config()
    except ConfigurationError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    token = cfg["token"]
    if not token:
        print(
            "Error: no Matsya token is configured. Run bellman-matsya configure, "
            "or set the environment variable BELLMAN_MATSYA_TOKEN.",
            file=sys.stderr,
        )
        sys.exit(1)
    return MatsyaClient(token=token, server_url=cfg["server"], anthropic_api_key=_selected_key())


# -- the parser


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bellman-matsya",
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

    docs = commands.add_parser(
        "docs",
        help=(
            "print the user guide in Markdown, installed with the client or, with --online, "
            "read from its public repository"
        ),
        description=(
            "Print the Matsya user guide, installed with the client, in Markdown: the list of "
            "its pages, one page, every page with --all, or with --path the folder that "
            "holds them. With --online, the page or every page is read as the client's "
            "public repository holds it today, over HTTPS."
        ),
    )
    # the subparser's own refusal, for --online with --path, which the
    # mutually exclusive group below cannot express
    docs.set_defaults(docs_parser=docs)
    shown = docs.add_mutually_exclusive_group()
    shown.add_argument(
        "page",
        nargs="?",
        type=_page_argument,
        help="the page to print, named with or without .md, such as index",
    )
    shown.add_argument(
        "--all", action="store_true", help="print every page in order, each after a line naming it"
    )
    shown.add_argument(
        "--path", action="store_true", help="print the folder where the pages are installed"
    )
    docs.add_argument(
        "--online",
        action="store_true",
        help=(
            "read the page, or with --all every page, as the client's public repository on "
            "GitHub holds it today, in place of the installed copy; the list of pages stays "
            "the installed one"
        ),
    )

    configure = commands.add_parser(
        "configure",
        help="save your Matsya token; once it is saved, optionally a personal Anthropic API key",
        description=(
            "Save the Matsya token the service's administrator gave you; the command asks for "
            "it and contacts no service. Once the Matsya token is configured, you may add a "
            "personal Anthropic API key, whose Anthropic account is then charged for the jobs "
            "and questions you start and for the replies that continue a job: --set-anthropic-key "
            "saves it, and --clear-anthropic-key removes it. Neither option asks for the Matsya "
            "token. The environment variable BELLMAN_MATSYA_ANTHROPIC_KEY supplies a key without "
            "saving it, in place of a saved key; set it from a private file, "
            'export BELLMAN_MATSYA_ANTHROPIC_KEY="$(cat <private file>)", and never type the '
            "key on the command line."
        ),
    )
    key_options = configure.add_mutually_exclusive_group()
    key_options.add_argument(
        "--set-anthropic-key",
        action="store_true",
        help=(
            "optional, once the Matsya token is configured: ask for a personal Anthropic API key "
            "at a prompt that does not show it, and save it in "
            "~/.config/bellman-matsya/anthropic-key, readable by you alone"
        ),
    )
    key_options.add_argument(
        "--clear-anthropic-key",
        action="store_true",
        help=(
            "remove the saved personal Anthropic key; new jobs and questions then use the "
            "service's key, unless BELLMAN_MATSYA_ANTHROPIC_KEY is set"
        ),
    )

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
            "articles, hark, buffer_stock (by default, every collection your Matsya token may read)"
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
        help=(
            "start a job at the target named, from a description or a paper kept in a session, "
            "or from a session"
        ),
    )
    submit.add_argument(
        "file",
        nargs="?",
        help=(
            "a model description, or with --paper a paper, in Markdown, LaTeX or plain text, "
            "kept as an entry of the job's session; a PDF is refused"
        ),
    )
    # required, so that the parser refuses a job without a target with exit
    # status 2 and prints the four words in the usage line (AMD-MAT-011 §3,
    # AAS's answer to Q-M18)
    submit.add_argument(
        "--target",
        required=True,
        choices=TARGETS,
        help=(
            "the level of the declaration the job returns, required: stage, one stage file; "
            "period, the stage files of one period and period.yml; trellis, the stage files, "
            "the period files and trellis.yml; recipe, the files of a trellis with a methods "
            "file for each stage the source says how to solve, the calibration, the settings "
            "and the recipe spec.yml"
        ),
    )
    # the mark of a paper, sent as its text (AMD-MAT-012 §2)
    submit.add_argument(
        "--paper",
        action="store_true",
        help=(
            "the file is a paper's text in Markdown or LaTeX, appended to the job's session as "
            "an entry of the kind paper, or with --no-session sent as the job's source of that kind"
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
    submit.add_argument(
        "--configuration-id",
        metavar="ID",
        help=(
            "the published configuration the job runs under, its ID of 64 hexadecimal "
            "characters; by default the service's default configuration"
        ),
    )
    submit.add_argument(
        "--model-key",
        metavar="KEY",
        help=(
            "with --source-cluster, the lowercase identifiers of the model and of the source "
            "cluster the job excludes from what it reads"
        ),
    )
    submit.add_argument("--source-cluster", metavar="CLUSTER", help="see --model-key")
    submit.add_argument(
        "--formulation",
        metavar="TEXT",
        help="the model to write when the source states several; at most 500 characters",
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
            "write an ended job's model folder: economics.md, report.md, the files of the job's "
            "target under declaration/ and record.json"
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
    export = job_commands.add_parser(
        "export",
        parents=[shared],
        help=(
            "save a job's full answer as job.json in a folder, for any state of the job, with "
            "its configuration ID and digests"
        ),
    )
    export.add_argument("job_id", metavar="job")
    export.add_argument("folder", help="the folder, created when it does not exist")
    export.add_argument(
        "--overwrite", action="store_true", help="replace an existing job.json in the folder"
    )
    export.set_defaults(handler=_job_export)
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
    ask.add_argument(
        "--configuration-id",
        metavar="ID",
        help=(
            "the published configuration whose conversation role answers; by default the "
            "service's default configuration"
        ),
    )
    ask.set_defaults(handler=_ask)

    # the project folder (AMD-MAT-013 §3), whose commands print with --json
    # the answer the client composes from the folder and the service's answers
    composed = argparse.ArgumentParser(add_help=False)
    composed.add_argument(
        "--json",
        action="store_true",
        help=(
            "print the answer as JSON: the folder's project file, what was sent or written, and "
            "the service's answers"
        ),
    )
    project_parser = commands.add_parser(
        "project",
        help="work on a project folder, a model folder that remembers its session",
        description=(
            "Work on a project folder: a model folder that holds economics.md, the model's "
            "description, and declaration/, the declaration as it stands, and that remembers "
            "its session in .bellman-matsya/project.json. Run each command in the project folder; "
            "init makes a folder one."
        ),
    )
    project_commands = project_parser.add_subparsers(
        dest="project_command", metavar="<project command>", required=True
    )
    project_init = project_commands.add_parser(
        "init",
        parents=[composed],
        help=(
            "make a folder a project: its session, named after the folder, with economics.md "
            "as the first entry, .bellman-matsya/ and AGENTS.md"
        ),
    )
    project_init.add_argument(
        "folder",
        nargs="?",
        default=".",
        help="the folder (default: this folder); a folder that does not exist is created",
    )
    project_init.set_defaults(handler=_project_init)
    project_submit = project_commands.add_parser(
        "submit",
        parents=[composed],
        help=(
            "append economics.md to the session when it has changed, and start a job with the "
            "files of declaration/ as its starting declaration"
        ),
    )
    project_submit.add_argument(
        "--target",
        choices=TARGETS,
        help=(
            "the level of the declaration the job returns; by default read from declaration/: "
            "recipe with a methods, calibration, settings or recipe file, trellis with "
            "trellis.yml, period with a period file, stage otherwise"
        ),
    )
    project_submit.add_argument(
        "--max-cycles", type=int, help="the most cycles of writing and checking"
    )
    project_submit.add_argument(
        "--configuration-id",
        metavar="ID",
        help="the published configuration the job runs under; by default the service's default",
    )
    project_submit.set_defaults(handler=_project_submit)
    project_status = project_commands.add_parser(
        "status",
        parents=[composed],
        help=(
            "the folder's session: its entries, its jobs by their labels and the questions "
            "awaiting a reply, with the commands that answer one and ask one"
        ),
    )
    project_status.set_defaults(handler=_project_status)
    project_pull = project_commands.add_parser(
        "pull",
        parents=[composed],
        help="write a job's products into this folder with --replace, or into a sub-folder",
    )
    project_pull.add_argument(
        "job_id",
        metavar="job",
        nargs="?",
        help="the job (default: the latest job of the folder's session that holds a record)",
    )
    project_pull.add_argument(
        "--replace",
        action="store_true",
        help=(
            "write into this folder: each declaration file replaces the file of the same path, "
            "report.md and model-prose.md are written, economics.md is not, and the files of "
            "declaration/ the job did not write are kept"
        ),
    )
    project_pull.add_argument(
        "--into",
        nargs="?",
        const="",
        metavar="SUBFOLDER",
        help=(
            "write the job's model folder into SUBFOLDER, new or empty; without --replace this "
            "is done in any case, by default into bellman-matsya-output/job-<number>"
        ),
    )
    project_pull.set_defaults(handler=_project_pull)

    configuration = commands.add_parser(
        "configuration",
        help="publish a configuration and set the default (administrator operations)",
        description=(
            "Publish a checked configuration folder to the service under its ID, the digest of "
            "its manifest, and make a published configuration the default. The service refuses "
            "both for a Matsya token without administrator permission."
        ),
    )
    configuration_commands = configuration.add_subparsers(
        dest="configuration_command", metavar="<configuration command>", required=True
    )
    publish = configuration_commands.add_parser(
        "publish",
        parents=[shared],
        help="send a checked configuration folder as a ZIP archive; prints its ID and version",
    )
    publish.add_argument("folder", help="the checked configuration folder, with its manifest.json")
    publish.set_defaults(handler=_configuration_publish)
    set_default = configuration_commands.add_parser(
        "set-default",
        parents=[shared],
        help="make a published configuration the default for requests that name none",
    )
    set_default.add_argument("configuration_id", metavar="id", help="the configuration's ID")
    set_default.set_defaults(handler=_configuration_set_default)
    return parser


def _check_configuration_option(parser: argparse.ArgumentParser, value: object) -> None:
    """Refuse, with exit status 2 and before any request, a configuration ID
    of another form than 64 lowercase hexadecimal characters."""
    if value is not None and not (isinstance(value, str) and CONFIGURATION_ID.fullmatch(value)):
        parser.error(CONFIGURATION_ID_REFUSAL.rstrip("."))


def _check_arguments(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    """Refuse, before any request, the arguments the routes do not accept
    together, and a file that is a PDF, which the client sends neither as a
    job's source nor as an entry (`PDF_REFUSAL`, AMD-MAT-012 §2)."""
    if args.command == "job" and args.job_command == "submit":
        if args.file is None and args.session is None:
            parser.error("job submit needs a file, a description or a paper, or --session")
        if args.file is None and args.paper:
            parser.error(
                "--paper marks the file submitted as a paper; a job from --session alone reads "
                "the session's entries as they stand"
            )
        if args.file is not None and _names_a_pdf(args.file):
            parser.error(PDF_REFUSAL)
        if args.max_cycles is not None and args.max_cycles < 1:
            parser.error("--max-cycles must be a positive integer")
        _check_configuration_option(parser, args.configuration_id)
        if (args.model_key is None) != (args.source_cluster is None):
            parser.error("--model-key and --source-cluster are given together or not at all")
        try:
            _check_formulation(args.formulation)
        except ValueError as error:
            parser.error(str(error))
    if args.command == "ask":
        _check_configuration_option(parser, args.configuration_id)
    if args.command == "configuration" and args.configuration_command == "set-default":
        _check_configuration_option(parser, args.configuration_id)
    if args.command == "session" and args.session_command == "add":
        if args.kind == "acceptance":
            if args.file is not None or args.replies_to is None:
                parser.error(
                    "an acceptance holds no text and names in --replies-to the answer it accepts"
                )
        elif args.file is None:
            parser.error(f"a {args.kind} entry needs a file holding its text (- reads the standard input)")
        elif args.file != "-" and _names_a_pdf(args.file):
            parser.error(PDF_REFUSAL)
    if args.command == "session" and args.session_command == "select":
        if (args.job_id is None) == (not args.none):
            parser.error("session select names a job, or --none to clear the selection, and not both")
    if args.command == "project" and args.project_command == "submit":
        if args.max_cycles is not None and args.max_cycles < 1:
            parser.error("--max-cycles must be a positive integer")
        _check_configuration_option(parser, args.configuration_id)
    if getattr(args, "interval", None) is not None and args.interval < 0:
        parser.error("--interval cannot be negative")


def _stopped(args: argparse.Namespace) -> str:
    """What the user reads when they stop a command that waits."""
    if args.command == "ask" and getattr(args, "followed_job", None):
        return (
            "Stopped waiting. The job goes on running on the service: "
            f"bellman-matsya job wait {args.followed_job}; write its folder with: "
            f"bellman-matsya job files {args.followed_job} {args.follow}"
        )
    if args.command == "ask":
        return (
            "Stopped waiting. The turn goes on running on the service, and its answer "
            f"is appended to the session: bellman-matsya session show {args.session_id}"
        )
    if args.command == "job" and args.job_command == "cancel":
        return (
            "Stopped before the service answered; whether the job was cancelled shows in: "
            f"bellman-matsya job status {args.job_id}"
        )
    if args.command == "job" and getattr(args, "job_id", None):
        return (
            "Stopped waiting. The job goes on running on the service: "
            f"bellman-matsya job wait {args.job_id}"
        )
    return "Stopped."


def _masked(client: MatsyaClient | None, text: str) -> str:
    """The text with the Matsya token and the personal Anthropic key
    replaced by `<Matsya token>` and `<Anthropic API key>` once the client
    is built (AMD-MAT-021 §2.5); a message printed before it holds no
    answer of the service."""
    return text if client is None else client._hidden(text)


def main(argv: list[str] | None = None) -> int:
    """Run the command that `argv`, or the command line, names, and return
    its exit status: 0 when it was carried out, 1 when the service refused
    the request or the client could not send it, or `docs --online` could
    not read a page. Arguments the parser refuses, such as `job submit`
    without `--target`, end the command with status 2 before any request,
    as does a project command the client refuses (`ProjectRefusal`), whose
    one sentence is printed on standard error. With `--json`, a project
    command prints the answer the client composes (`bellman_matsya.project`), and
    every other command the service's answer as it arrived. New work sent
    with a personal Anthropic key that the service accepted under its own
    key is reported on standard error after that output, or after the
    error that ended the command once the service had accepted the work,
    and the command exits with status 1, or 130 when the user stopped it
    (AMD-MAT-021 §2.5). Once the client
    is built, every line printed for a person and every error pass through
    the client's mask of the Matsya token and the personal key; the JSON
    printed with `--json` is left as it is. With no command, print the
    orientation. At the first use of the client on this machine, a command
    other than `docs` first prints the two lines of `FIRST_USE`."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        print("\n".join(_orientation_lines()))
        return 0
    if args.command == "docs":
        if args.online and args.path:
            args.docs_parser.error("argument --online: not allowed with argument --path")
        try:
            lines = _docs_lines(args)
        except guide.OnlineError as error:
            print(
                f"Error: {error}; without --online, bellman-matsya docs prints the installed guide.",
                file=sys.stderr,
            )
            return 1
        print("\n".join(lines))
        return 0
    if first_use():
        # flushed, so that the two lines precede a refusal on standard error
        print(FIRST_USE, flush=True)
    if args.command == "configure":
        if args.set_anthropic_key:
            _set_anthropic_key()
        elif args.clear_anthropic_key:
            _clear_anthropic_key()
        else:
            _run_configure()
        return 0
    _check_arguments(parser, args)
    client: MatsyaClient | None = None
    try:
        if args.command == "project":
            _project_check(args)
        client = _build_client()
        lines = args.handler(client, args)
    except ProjectRefusal as error:
        print(_masked(client, f"Error: {error}"), file=sys.stderr)
        return 2
    except (MatsyaError, CommandError) as error:
        print(_masked(client, f"Error: {error}"), file=sys.stderr)
        refusal = getattr(args, "credential_refusal", None)
        if refusal:
            # an error after the service accepted the work, such as a failed
            # wait for the job a turn started, does not hide work that runs
            # under the service's key (AMD-MAT-021 §2.5)
            print("\n".join(refusal), file=sys.stderr)
        return 1
    except OSError as error:
        reason = f"{error.strerror}: {error.filename}" if error.strerror and error.filename else error
        print(_masked(client, f"Error: {reason}"), file=sys.stderr)
        refusal = getattr(args, "credential_refusal", None)
        if refusal:
            # nor does a folder that cannot be written (AMD-MAT-021 §2.5)
            print("\n".join(refusal), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print(_masked(client, f"\n{_stopped(args)}"), file=sys.stderr)
        refusal = getattr(args, "credential_refusal", None)
        if refusal:
            # a wait the user stopped does not hide work that runs under
            # the service's key (AMD-MAT-021 §2.5)
            print("\n".join(refusal), file=sys.stderr)
        return 130
    composed = getattr(args, "answer", None)
    if not args.json:
        print(client._hidden("\n".join(lines)))
    elif composed is not None:
        print(json.dumps(composed, ensure_ascii=False, indent=2))
    else:
        print(client.last_text)
    refusal = getattr(args, "credential_refusal", None)
    if refusal:
        # the work runs under the service's key, not the holder's (AMD-MAT-021 §2.5)
        print("\n".join(refusal), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
