"""A project folder: a model folder that remembers its Matsya session
(AMD-MAT-013 §§2 and 3; AMD-MAT-015 §2).

A project folder holds `economics.md`, the user's description of the
model, which is the source material of the folder's jobs and which the
client never writes; `declaration/`, the stage files and the period,
trellis, recipe, methods, calibration and settings files as they stand,
possibly none, in the layout of the model folder (AMD-MAT-010 §5); and
`.bellman-matsya/`, which the client writes: `project.json`, which holds the
session's identifier, the service's address and the digest of
`economics.md` as the session last received it, and `README.md`, the note
on the folder and its commands that a reader or an assistant reads first.
An assistant such as Claude Code can run the client's commands on the
user's machine; the language model it calls may run elsewhere. The
assistant is no part of Matsya.

The four commands of `bellman-matsya project` are the functions `init`, `submit`,
`status` and `pull`, each called with a `MatsyaClient` and the folder, and
each returning the answer the command prints with `--json`. Their requests
are the client's own (`new_session`, `add_entry`, `submit_job`, `job` and
`session`), and their files are written by `write_texts`, which writes no
file through a symbolic link. A project's requests go only to the service
address the client is configured with, which must be the address the
folder records, so that the Matsya token is never sent to an address read
from a folder. A personal Anthropic key the client holds is sent only with
the job request of `submit` (AMD-MAT-021 §2.3). `ProjectRefusal` is the
client's refusal of a command it does not carry out, stated in one
sentence; the command exits with status 2.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Iterable

from bellman_matsya.client import (
    ECONOMICS_FILE,
    RECORD_FILE,
    MatsyaClient,
    MatsyaError,
    _check_configuration_id,
    _check_paths,
    _check_target,
    _folder_texts,
    write_texts,
)

# the folder the client keeps in a project folder, and its two files
PROJECT_FOLDER = ".bellman-matsya"
PROJECT_FILE = f"{PROJECT_FOLDER}/project.json"
README_FILE = f"{PROJECT_FOLDER}/README.md"
# the file in which an assistant such as Claude Code or Codex reads the
# instructions of a folder it opens
AGENTS_FILE = "AGENTS.md"
# the declaration as it stands, and the file in which a pull with
# `replace` writes the model prose beside the user's `economics.md`
# (AMD-MAT-013 §7)
DECLARATION_FOLDER = "declaration"
MODEL_PROSE_FILE = "model-prose.md"
WRITER_NOTE_FILE = f"{PROJECT_FOLDER}/writer-note.md"
# the folder under which a pull writes a job's model folder by default, as
# `bellman-matsya-output/job-<number>/`
OUTPUT_FOLDER = "bellman-matsya-output"
# the states of a job that may hold a record (AMD-MAT-008 §4): a job that
# failed or was interrupted holds none, and a job in the state `cancelled`
# holds one when the user canceled it while it ran
RECORD_STATES = ("converged", "not_converged", "needs_input", "cancelled")
# the files of `declaration/` that a starting declaration holds, by their
# paths in the model folder's layout, and the names under which the service
# reads them (`allowed_declaration_name` of the service's `meaning.py`): a
# stage file `stages/<key>/<key>.bl`, read as `<key>.bl`; and, by their
# paths, a period file `period.yml` or `period.<name>.yml`, the trellis
# file, the recipe `spec.yml`, a stage's methods file
# `stages/<key>/methods.yml` and the calibration and settings files
# `calibration/<name>.yml` and `settings/<name>.yml`
_KEY = r"[a-zA-Z0-9][a-zA-Z0-9_-]*"
_NAME = r"[a-z0-9][a-z0-9_-]*"
STAGE_PATH = re.compile(rf"stages/({_KEY})/\1\.bl")
PERIOD_PATH = re.compile(rf"period(?:\.{_NAME})?\.yml")
METHODS_PATH = re.compile(rf"stages/{_KEY}/methods\.yml")
SOURCE_PATH = re.compile(rf"(?:calibration|settings)/{_NAME}\.yml")
TRELLIS_FILE = "trellis.yml"
RECIPE_FILE = "spec.yml"

# the sentences of the refusals that name no object of the folder
NO_PROJECT = (
    "This folder is not a Matsya project, since it holds no .bellman-matsya/project.json; make it "
    "one with: bellman-matsya project init"
)
REPLACE_AND_INTO = (
    "--replace writes the job's files into this folder and --into writes them into a "
    "sub-folder, so give one of the two."
)
LINKED_ECONOMICS = (
    "economics.md is a symbolic link, whose target may lie outside the folder, and the client "
    "sends no file of a project folder through one; put the description itself in economics.md."
)
# the paragraph `init` writes into a new `AGENTS.md`, or prints for the user
# to add to an existing one: it points an assistant to the folder's note
# and to the user guide (AMD-MAT-015 §§2 and 6)
AGENTS_PARAGRAPH = (
    "This folder is a Matsya project: its model, described in `economics.md` and declared in "
    "`declaration/`, is written and checked by the Matsya service through the command "
    "`bellman-matsya`, and the folder's session on the service keeps the model's text, its jobs and "
    "their questions. Before you work on the model, read `.bellman-matsya/README.md`, which names the "
    "session and the commands used most, and run `bellman-matsya docs --all`, which prints the whole "
    "user guide of the command. Project, job, session, ask, index and search commands accept "
    "`--json` for structured answers."
)


class ProjectRefusal(Exception):
    """A command of a project folder that the client does not carry out: no
    project in the folder, or one whose project file cannot be read; a
    project already there, or a folder named to `init` that is a file;
    `--replace` with `--into`; a job that holds no record, or a session
    none of whose jobs holds one; a sub-folder for `--into` that is a file
    or is not empty; an `economics.md` that is a symbolic link; and a
    sub-folder outside the project; and a folder whose service address is not the client's. Its message is one
    sentence; the command prints it and exits with status 2."""


def sha256_of(data: bytes) -> str:
    """The SHA-256 digest of a file's bytes, in hexadecimal."""
    return hashlib.sha256(data).hexdigest()


def reply_command(session_id: str, number: object) -> str:
    """The command that answers the question of entry `number` of the
    session, `<file>` standing for the file that holds the reply."""
    return f"bellman-matsya session add {session_id} <file> --replies-to {number}"


def ask_command(session_id: str) -> str:
    """The command that asks matsya-master a question in the session."""
    return f'bellman-matsya ask {session_id} "<question>"'


def note_text(session_id: str, server: str) -> str:
    """`.bellman-matsya/README.md`: what the folder is, its session and service,
    the files the client keeps and writes in it, the four commands used
    most, and `bellman-matsya docs` for the rest (AMD-MAT-015 §2)."""
    return "\n".join(
        [
            "# This folder is a Matsya project",
            "",
            "Matsya is a service of Project Bellman. From an economist's description of a dynamic "
            "model it writes the model in Bellman-SYM, the project's language for staged Bellman "
            "problems, checks what it wrote, and answers questions about the model. The work on "
            "this folder's model is kept on the service in a **session**, the numbered text of "
            "one model: your entries, Matsya's questions and answers, and the **jobs** started "
            "from it, each one attempt to write and check the model's declaration.",
            "",
            f"- Session: `{session_id}`",
            f"- Service: `{server}`",
            "",
            "## The files",
            "",
            "- `economics.md`: your description of the model, from which every job starts. The "
            "client reads it and never writes it.",
            "- `declaration/`: the declaration as it stands: the stage files "
            "`stages/<key>/<key>.bl`, each of which states one decision problem, and the period, "
            "trellis, recipe, methods, calibration and settings files, which join the stages in "
            "time and bind their methods and values. `bellman-matsya project submit` sends these files "
            "as the job's starting declaration, the files its first cycle starts from; the notes "
            "beside the stage files are not sent.",
            "- `report.md` and `model-prose.md`: the report of the job last written into this "
            "folder, and, when the job produced it, the model prose written from `economics.md`; "
            "`bellman-matsya project pull --replace` writes these files.",
            "- `bellman-matsya-output/job-<number>/`: the products of a job as a model folder of their "
            "own, which `bellman-matsya project pull` writes without `--replace`.",
            "- `.bellman-matsya/project.json`: the session's identifier, the service's address and the "
            "digest of `economics.md` as the session last received it, which the client writes.",
            "- `.bellman-matsya/README.md`: this note, which `bellman-matsya project init` writes.",
            "- `.bellman-matsya/writer-note.md`: the writer's note from the latest pull into this folder "
            "that produced one. It is kept apart from an author's stage page.",
            "",
            "Everything else, the session's entries and the jobs with their records, is kept on "
            "the service. `.bellman-matsya/project.json` names the service's address and holds no Matsya "
            "token; commit `.bellman-matsya/` with the folder, or add it to the folder's `.gitignore` when "
            "the folder's repository is public.",
            "",
            "## The commands used most",
            "",
            "Run them in this folder.",
            "",
            "- `bellman-matsya project status` prints the session: its entries; its jobs, each by its "
            "label, such as `household · stage · version 2 · job 3 · converged`, which names the "
            "model, the job's target, the version of the text the job read, the job's number and "
            "its state; and each question awaiting a reply, with the command that answers it.",
            "- `bellman-matsya project submit` appends `economics.md` to the session when it has changed "
            "since the session last received it, and starts a job with the files of "
            "`declaration/` as its starting declaration. The job's target, the level of the "
            "declaration it returns, is read from those files: `recipe` with a methods, "
            "calibration, settings or recipe file, `trellis` with `trellis.yml`, `period` with a "
            "period file, and `stage` otherwise; `--target` names another.",
            "- `bellman-matsya project pull` writes the products of the session's latest job that holds "
            "a record: with `--replace` into this folder, each file of the job's declaration "
            "replacing the file of the same path, the files the job did not write kept and "
            "`economics.md` left as it is; otherwise into `bellman-matsya-output/job-<number>/`.",
            f"- `{ask_command(session_id)}` asks matsya-master, the service's conversation side, "
            "a question about this model.",
            "",
            "Project, job, session, ask, index and search commands print structured answers with "
            "`--json` and refuse what they cannot do with one sentence. `bellman-matsya docs` lists the "
            "pages of the user guide installed with the "
            "client, and `bellman-matsya docs --all` prints them all.",
            "",
        ]
    )


def _project_text(held: dict[str, Any]) -> str:
    """`.bellman-matsya/project.json` in JSON."""
    return json.dumps(held, indent=2, ensure_ascii=False) + "\n"


def _named(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def read_project(folder: str | Path) -> dict[str, Any]:
    """The folder's `.bellman-matsya/project.json`, as `{"session", "server",
    "economics_sha256"}`; `ProjectRefusal` when the folder holds none or it
    cannot be read."""
    path = Path(folder) / PROJECT_FILE
    if not os.path.lexists(path):
        raise ProjectRefusal(NO_PROJECT)
    redo = "remove it and make the folder a project again with: bellman-matsya project init"
    try:
        held = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ProjectRefusal(f"{PROJECT_FILE} cannot be read ({error}); {redo}") from None
    digest = held.get("economics_sha256") if isinstance(held, dict) else None
    if not (
        isinstance(held, dict)
        and _named(held.get("session"))
        and _named(held.get("server"))
        and (digest is None or isinstance(digest, str))
    ):
        raise ProjectRefusal(
            f"{PROJECT_FILE} does not hold a session's identifier and a service's address; {redo}"
        )
    return {
        "session": held["session"],
        "server": held["server"].rstrip("/"),
        "economics_sha256": digest,
    }


def check_init(folder: str | Path) -> None:
    """Refuse to make `folder` a project when it is a file or already holds
    `.bellman-matsya/project.json`; nothing is sent or written."""
    folder = Path(folder)
    if os.path.lexists(folder) and not folder.is_dir():
        raise ProjectRefusal(f"{folder} is a file, and a project is a folder.")
    if os.path.lexists(folder / PROJECT_FILE):
        try:
            held = f", of session {read_project(folder)['session']}"
        except ProjectRefusal:
            held = ""
        raise ProjectRefusal(
            f"The folder {folder.resolve()} is already a Matsya project{held}; bellman-matsya project "
            "status shows it."
        )


def check_server(client: MatsyaClient, held: dict[str, Any]) -> None:
    """Refuse a project whose service address differs from the client's, so
    that the Matsya token is sent only to the address the client is
    configured with, never to an address read from a folder."""
    if client.server_url.rstrip("/") != held["server"]:
        raise ProjectRefusal(
            f"This folder's session is kept by the service at {held['server']}, and the client "
            f"is configured for the service at {client.server_url}; the client sends a folder's "
            "requests only to the service it is configured for."
        )


def read_economics(folder: str | Path) -> tuple[str | None, str | None]:
    """The text of the folder's `economics.md` and the digest of its bytes,
    or `(None, None)` when the folder holds no such file or it holds no
    text. An `economics.md` that is a symbolic link is refused with
    `ProjectRefusal`, and one that is not text in UTF-8 raises
    `ValueError`."""
    path = Path(folder) / ECONOMICS_FILE
    if path.is_symlink():
        raise ProjectRefusal(LINKED_ECONOMICS)
    if not path.is_file():
        return None, None
    data = path.read_bytes()
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise ValueError(f"{ECONOMICS_FILE} is not text in UTF-8.") from None
    if not text.strip():
        return None, None
    return text, sha256_of(data)


def declaration_name(path: str) -> str | None:
    """The name under which a job's starting declaration holds the file at
    `path` within `declaration/`, such as `example.bl` for
    `stages/example/example.bl`; `None` for a file it does not hold, the
    note of a stage among them."""
    stage = STAGE_PATH.fullmatch(path)
    if stage:
        return f"{stage.group(1)}.bl"
    if path in (TRELLIS_FILE, RECIPE_FILE) or any(
        pattern.fullmatch(path) for pattern in (PERIOD_PATH, METHODS_PATH, SOURCE_PATH)
    ):
        return path
    return None


def declaration_paths(folder: str | Path) -> list[str]:
    """The files of the folder's `declaration/` by their paths within the
    project folder, such as `declaration/stages/example/example.bl`, in the
    order of their paths. A name beginning with a dot is passed over, and a
    symbolic link to a folder, `declaration/` itself among them, is listed
    with a closing slash and not entered."""
    folder = Path(folder)
    root = folder / DECLARATION_FOLDER
    if root.is_symlink():
        return [f"{DECLARATION_FOLDER}/"]
    if not root.is_dir():
        return []
    found: list[str] = []
    for directory, folders, names in os.walk(root):
        here = Path(directory)
        for name in list(folders):
            if name.startswith(".") or (here / name).is_symlink():
                folders.remove(name)
                if not name.startswith("."):
                    found.append((here / name).relative_to(folder).as_posix() + "/")
        found += [
            (here / name).relative_to(folder).as_posix() for name in names if not name.startswith(".")
        ]
    return sorted(found)


def declaration_files(folder: str | Path) -> tuple[dict[str, str], list[str]]:
    """The starting declaration that the folder's `declaration/` gives a
    job, each file's text under the name the service reads; and the files
    of `declaration/` it does not hold, by their paths within the folder:
    the notes of the stages, any file outside the layout, and a symbolic
    link, which is not read, since its target may lie outside the folder. A
    file of the starting declaration that is not text in UTF-8 raises
    `ValueError`."""
    folder = Path(folder)
    files: dict[str, str] = {}
    left_out: list[str] = []
    for path in declaration_paths(folder):
        within = path[len(DECLARATION_FOLDER) + 1 :]
        name = None if path.endswith("/") else declaration_name(within)
        if name is None or (folder / path).is_symlink():
            left_out.append(path)
            continue
        try:
            files[name] = (folder / path).read_bytes().decode("utf-8")
        except UnicodeDecodeError:
            raise ValueError(f"{path} is not text in UTF-8.") from None
    return files, left_out


def folder_target(names: Iterable[str]) -> str:
    """The target that a project folder's declaration implies (AMD-MAT-013
    §2), from the names of its starting declaration: `recipe` when it holds
    a methods, calibration, settings or recipe file; `trellis` when it holds
    `trellis.yml`; `period` when it holds a period file; and `stage`
    otherwise, an empty declaration among them."""
    names = list(names)
    if any(
        name == RECIPE_FILE or METHODS_PATH.fullmatch(name) or SOURCE_PATH.fullmatch(name)
        for name in names
    ):
        return "recipe"
    if TRELLIS_FILE in names:
        return "trellis"
    if any(PERIOD_PATH.fullmatch(name) for name in names):
        return "period"
    return "stage"


def awaiting(session: dict[str, Any]) -> list[dict[str, Any]]:
    """The questions awaiting a reply in a session, as the service lists
    it: the `question` entries of its job awaiting an answer
    (`awaiting_answer`), each as `{"number", "text", "reply"}`, `reply`
    being the command that answers it; a reply to one of them starts that
    job's next attempt (AMD-MAT-006 §8)."""
    job_id = session.get("awaiting_answer")
    if not job_id:
        return []
    session_id = str(session.get("id"))
    return [
        {
            "number": entry.get("number"),
            "text": entry.get("text"),
            "reply": reply_command(session_id, entry.get("number")),
        }
        for entry in session.get("entries") or []
        if isinstance(entry, dict)
        and entry.get("kind") == "question"
        and entry.get("origin") == {"job": job_id}
    ]


def latest_recorded_job(client: MatsyaClient, session: dict[str, Any]) -> dict[str, Any] | None:
    """The latest job of the session, as the service lists its jobs in the
    order they were created, that has ended and holds a record, in the
    products view; `None` when no job holds one."""
    for listed in reversed(session.get("jobs") or []):
        if isinstance(listed, dict) and listed.get("state") in RECORD_STATES:
            job = client.job(str(listed.get("id")))
            if isinstance(job.get("result"), dict):
                return job
    return None


def default_subfolder(job: dict[str, Any]) -> str:
    """The sub-folder a pull writes a job's model folder into by default,
    `bellman-matsya-output/job-<number>`, the job's number among its session's
    jobs, or its identifier for a job of no session."""
    label = job.get("label") if isinstance(job.get("label"), dict) else {}
    number = label.get("number")
    return f"{OUTPUT_FOLDER}/job-{job.get('id') if number is None else number}"


def no_record(job_id: str, job: dict[str, Any]) -> str:
    """The refusal of a pull of a job that holds no record."""
    state = job.get("state")
    if job.get("error"):
        state = f"{state}, error {job['error']}"
    return f"Job {job_id} holds no record, so it has no products to write; its state is {state}."


def init(client: MatsyaClient, folder: str | Path = ".") -> dict[str, Any]:
    """Make `folder`, by default this folder, a project folder, as
    `bellman-matsya project init` does (AMD-MAT-013 §3; AMD-MAT-015 §2): create the
    folder's session, named after the folder; write `.bellman-matsya/project.json`
    and `.bellman-matsya/README.md`; append `economics.md` to the session as its
    first entry, of the kind `user`, when the folder holds one with text,
    and record its digest; and create `AGENTS.md` holding
    `AGENTS_PARAGRAPH` when the folder has none, leaving an existing one as
    it is. A folder that is a file or already a project is refused with
    `ProjectRefusal` before any request; a folder that does not exist is
    created.

    Returns `{"folder", "project", "session", "entry", "written",
    "agents", "agents_paragraph"}`: the folder's path; the contents of
    `.bellman-matsya/project.json`; the service's answer that created the session;
    the entry appended, or `None`; the files written, by their paths in the
    folder; `"created"` or `"kept"` for `AGENTS.md`; and the paragraph."""
    folder = Path(folder)
    check_init(folder)
    text, digest = read_economics(folder)
    created = client.new_session(folder.resolve().name or "project")
    held = {
        "session": created["id"],
        "server": client.server_url.rstrip("/"),
        "economics_sha256": None,
    }
    written = [PROJECT_FILE, README_FILE]
    write_texts(
        folder,
        {PROJECT_FILE: _project_text(held), README_FILE: note_text(held["session"], held["server"])},
    )
    entry = None
    if text is not None:
        try:
            entry = client.add_entry(held["session"], text, kind="user")["entry"]
        except MatsyaError as error:
            # the session's identifier is the service's (AMD-MAT-021 §2.5)
            error.args = (
                client._hidden(
                    f"{error} The folder is a project of session {held['session']}, which holds "
                    "no entry; bellman-matsya project submit appends economics.md to it."
                ),
            )
            raise
        held["economics_sha256"] = digest
        write_texts(folder, {PROJECT_FILE: _project_text(held)})
    agents = "kept" if os.path.lexists(folder / AGENTS_FILE) else "created"
    if agents == "created":
        write_texts(folder, {AGENTS_FILE: AGENTS_PARAGRAPH + "\n"})
        written.append(AGENTS_FILE)
    return {
        "folder": str(folder.resolve()),
        "project": held,
        "session": created,
        "entry": entry,
        "written": written,
        "agents": agents,
        "agents_paragraph": AGENTS_PARAGRAPH,
    }


def submit(
    client: MatsyaClient,
    folder: str | Path = ".",
    target: str | None = None,
    max_cycles: int | None = None,
    configuration_id: str | None = None,
) -> dict[str, Any]:
    """Submit a job from the folder's session, as `bellman-matsya project submit`
    does (AMD-MAT-013 §3): append `economics.md` as a new entry of the kind
    `user` when its digest differs from the one recorded, and record the new
    digest; send the files of `declaration/` as the job's starting
    declaration (`declaration_files`), none when it holds none; and start
    the job at `target`, by default the folder's target (`folder_target`),
    with `max_cycles` when given and under the published configuration
    `configuration_id` when given, else the default (AMD-MAT-020 §3). The
    job is then read once, for its label. A personal Anthropic key the
    client holds is sent with the job's request alone; at an address that
    fails `key_destination_allowed` the submission raises `MatsyaError`
    before its first request, so that no entry of `economics.md` is
    appended and no new digest is recorded (AMD-MAT-021 §2.4).

    Returns `{"folder", "project", "economics", "entry", "target",
    "target_named", "starting_declaration", "left_out", "job"}`: the
    folder's path; the contents of `.bellman-matsya/project.json`; `"appended"`,
    `"unchanged"` or `"absent"` for `economics.md`; the entry appended, or
    `None`; the target and whether it was named; the names of the starting
    declaration's files; the files of `declaration/` not sent; and the job
    as the service returns it, with its label."""
    folder = Path(folder)
    if target is not None:
        _check_target(target)
    _check_configuration_id(configuration_id)
    held = read_project(folder)
    check_server(client, held)
    client.check_key_destination()
    text, digest = read_economics(folder)
    files, left_out = declaration_files(folder)
    chosen = folder_target(files) if target is None else target
    entry = None
    if text is not None and digest != held["economics_sha256"]:
        entry = client.add_entry(held["session"], text, kind="user")["entry"]
        held["economics_sha256"] = digest
        write_texts(folder, {PROJECT_FILE: _project_text(held)})
    started = client.submit_job(
        session=held["session"],
        target=chosen,
        max_cycles=max_cycles,
        starting_declaration=files or None,
        configuration_id=configuration_id,
    )
    job = client.job(str(started["id"]))
    return {
        "folder": str(folder.resolve()),
        "project": held,
        "economics": "appended" if entry is not None else ("absent" if text is None else "unchanged"),
        "entry": entry,
        "target": chosen,
        "target_named": target is not None,
        "starting_declaration": sorted(files),
        "left_out": left_out,
        "job": job,
    }


def status(client: MatsyaClient, folder: str | Path = ".") -> dict[str, Any]:
    """The folder's session, as `bellman-matsya project status` prints it
    (AMD-MAT-013 §3).

    Returns `{"folder", "project", "session", "awaiting", "ask",
    "economics_changed"}`: the folder's path; the contents of
    `.bellman-matsya/project.json`; the session as the service lists it, its
    entries, its revision, its jobs with their labels and its selected job;
    the questions awaiting a reply (`awaiting`); the command that asks a
    question; and whether `economics.md` has changed since the session last
    received it, `None` when the folder holds no `economics.md` with text."""
    folder = Path(folder)
    held = read_project(folder)
    check_server(client, held)
    session = client.session(held["session"])
    try:
        digest = read_economics(folder)[1]
    except (ProjectRefusal, ValueError, OSError):
        digest = None
    return {
        "folder": str(folder.resolve()),
        "project": held,
        "session": session,
        "awaiting": awaiting(session),
        "ask": ask_command(held["session"]),
        "economics_changed": None if digest is None else digest != held["economics_sha256"],
    }


def pull(
    client: MatsyaClient,
    folder: str | Path = ".",
    job: str | None = None,
    replace: bool = False,
    into: str | None = None,
) -> dict[str, Any]:
    """Write the products of a job, as `bellman-matsya project pull` does
    (AMD-MAT-013 §§3 and 7): of `job`, or by default of the latest job of
    the folder's session that has ended and holds a record.

    With `replace`, into the folder: each file of the job's declaration, a
    stage file, or a
    period, trellis, recipe, methods, calibration or settings file, at its
    path under `declaration/`, replacing the file of the same path;
    `report.md`; the model prose as `model-prose.md`; and an open writer's
    note as `.bellman-matsya/writer-note.md`, apart from an author's stage page;
    `economics.md` is not written, nor the record, and the files of
    `declaration/` the job did not write are kept. Otherwise the job's model folder, the layout of
    `bellman-matsya job files`, into the sub-folder `into`, by default
    `bellman-matsya-output/job-<number>/`, which must be new or empty; the folder's
    declaration is not touched. Every file is written by `write_texts`.

    `replace` with `into`, a job that holds no record, a session none of
    whose jobs holds one, and a sub-folder that is not empty are refused
    with `ProjectRefusal`, before anything is written.

    Returns `{"folder", "project", "job", "into", "written", "replaced",
    "kept"}`: the folder's path; the contents of `.bellman-matsya/project.json`; the
    job in the products view; the sub-folder written into, or `None` with
    `replace`; the paths written, within the folder written into; those
    that replaced a file; and the files of `declaration/` kept."""
    folder = Path(folder)
    if replace and into is not None:
        raise ProjectRefusal(REPLACE_AND_INTO)
    held = read_project(folder)
    check_server(client, held)
    if job is None:
        chosen = latest_recorded_job(client, client.session(held["session"]))
        if chosen is None:
            raise ProjectRefusal(
                f"No job of session {held['session']} holds a record yet, so there is nothing to "
                "write; bellman-matsya project status lists its jobs."
            )
    else:
        chosen = client.job(job)
        if not isinstance(chosen.get("result"), dict):
            raise ProjectRefusal(no_record(job, chosen))
    texts = _folder_texts(chosen)
    subfolder = None
    if replace:
        texts = {
            (
                MODEL_PROSE_FILE
                if path == ECONOMICS_FILE
                else WRITER_NOTE_FILE
                if path == "declaration/notes.md"
                or (path.startswith("declaration/stages/") and path.endswith(".md"))
                else path
            ): text
            for path, text in texts.items()
            if path != RECORD_FILE
        }
        target = folder
        before = [path for path in declaration_paths(folder) if not path.endswith("/")]
    else:
        subfolder = into or default_subfolder(chosen)
        target = folder / subfolder
        relative = Path(subfolder)
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or target.resolve() == folder.resolve()
            or not target.resolve().is_relative_to(folder.resolve())
        ):
            raise ProjectRefusal(
                f"{subfolder} is not a sub-folder of this project; name a sub-folder within it "
                "with --into <subfolder>"
            )
        if os.path.lexists(target) and not target.is_dir():
            raise ProjectRefusal(
                f"{subfolder} is a file; name a new or empty sub-folder with --into <subfolder>"
            )
        if target.is_dir() and any(target.iterdir()):
            raise ProjectRefusal(
                f"{subfolder} is not empty; name a new or empty sub-folder with --into <subfolder>"
            )
        before = []
    _check_paths(list(texts), str(chosen.get("id")))
    replaced = [path for path in texts if os.path.lexists(target / path)]
    write_texts(target, texts)
    return {
        "folder": str(folder.resolve()),
        "project": held,
        "job": chosen,
        "into": subfolder,
        "written": list(texts),
        "replaced": replaced,
        "kept": sorted(set(before) - set(texts)),
    }
