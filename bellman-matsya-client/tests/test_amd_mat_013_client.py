"""The acceptance file of AMD-MAT-013 on the side of the client: the four
commands of a project folder of the amendment's §3, `bellman-matsya project init`,
`submit`, `status` and `pull`, and the orientation `bellman-matsya` prints in a
project folder (AMD-MAT-015 §2). Against the stand-in of the service:
`init` writes `.bellman-matsya/project.json` and `.bellman-matsya/README.md`, names the
session after the folder and writes or prints the paragraph for a local
model; `submit` appends `economics.md` only when its digest has changed and
sends the files of `declaration/` as the job's starting declaration at the
folder's target (item 3); `status` prints the session's identifier, the
labels and the exact reply line, which then starts the next job (item 4);
`pull` writes a job's model folder into `bellman-matsya-output/job-1/` and leaves
the declaration as it was (item 2); and the refusals, each one sentence with
exit status 2. Against the service of the test configuration, with the
scripted caller: `init`, `submit`, `status` and `pull --replace` on a folder
of one stage (item 1). A sixth test runs the project commands by the
installed command reference (item 5); item 6 is the client's suite."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest

import bellman_matsya
from conftest import MODEL_PROSE, NOTE, QUESTION, STAGE
from bellman_matsya import project

TIME = re.compile(r"^\d\d:\d\d:\d\d  ")
JOB = r"^Job ([0-9a-f]{32}): (?:queued|running)$"
ECONOMICS = (
    "# A household\n"
    "\n"
    "The household observes its resources x and then chooses two real controls u.\n"
)
# the page that explains a stage, which a job neither reads nor writes
STAGE_PAGE = "The stage `example` moves the resources x to the decision unchanged.\n"
PERIOD = "!period\nname: main\nstages:\n  - example\n"
# the service's libraries warn of their own deprecations under Python 3.14;
# a warning of the client is still shown
pytestmark = [
    pytest.mark.filterwarnings(f"ignore::{category}:{module}")
    for category in ("DeprecationWarning", "PendingDeprecationWarning")
    for module in ("fastapi", "starlette", "uvicorn", "uvloop", "websockets")
]


def _folder(root: Path, name: str, files: dict[str, str]) -> Path:
    """The folder `name` under `root`, holding `files` by their paths."""
    folder = root / name
    folder.mkdir()
    for path, text in files.items():
        (folder / path).parent.mkdir(parents=True, exist_ok=True)
        (folder / path).write_text(text, encoding="utf-8")
    return folder


def _held(folder: Path) -> dict:
    """The folder's `.bellman-matsya/project.json`."""
    return json.loads((folder / ".bellman-matsya" / "project.json").read_text(encoding="utf-8"))


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _identifier(pattern: str, text: str) -> str:
    found = re.search(pattern, text, re.MULTILINE)
    assert found, text
    return found.group(1)


def _final(out: str) -> list[str]:
    """The lines a command printed, without the lines of progress."""
    return [line for line in out.splitlines() if not TIME.match(line)]


def _files(folder: Path) -> dict[str, bytes]:
    """The files under `folder`, by their paths within it, with their bytes."""
    return {
        path.relative_to(folder).as_posix(): path.read_bytes()
        for path in sorted(folder.rglob("*"))
        if path.is_file()
    }


def test_init_writes_the_two_files_and_names_the_session_after_the_folder(
    stand_in, run, tmp_path, monkeypatch
) -> None:
    """`project init` creates the folder's session, named after the folder,
    with `economics.md` as entry 1, and writes `.bellman-matsya/project.json`, with
    the session's identifier, the service's address and the digest of
    `economics.md`, `.bellman-matsya/README.md`, with the identifier and the four
    commands used most, and `AGENTS.md`, with the paragraph for a local
    model; a folder with an `AGENTS.md` of its own keeps it, and the
    paragraph is printed for the user to add. In a folder that is no
    project the other commands are refused, and in a project a second
    `init`, each with one sentence, exit status 2 and no request."""
    folder = _folder(
        tmp_path,
        "household",
        {"economics.md": ECONOMICS, "declaration/stages/example/example.bl": STAGE},
    )
    monkeypatch.chdir(folder)
    for command in (("status",), ("submit",), ("pull",), ("pull", "--replace")):
        assert run("project", *command) == (2, "", f"Error: {project.NO_PROJECT}\n"), command
    assert stand_in.requests == []

    status, out, err = run("project", "init")
    assert (status, err) == (0, "")
    held = _held(folder)
    session_id = held["session"]
    assert held == {
        "session": session_id,
        "server": stand_in.url,
        "economics_sha256": _digest(folder / "economics.md"),
    }
    session = stand_in.sessions[session_id]
    assert session["name"] == "household"
    assert [(entry["number"], entry["kind"], entry["text"]) for entry in session["entries"]] == [
        (1, "user", ECONOMICS.strip())
    ]
    assert out.splitlines() == [
        f"Project folder: {folder.resolve()}",
        f"Session {session_id}: household",
        "Entry 1: the text of economics.md",
        "Wrote .bellman-matsya/project.json and .bellman-matsya/README.md",
        "Wrote AGENTS.md, whose paragraph points an assistant to .bellman-matsya/README.md",
        "Submit the model, in the project folder, with: bellman-matsya project submit",
    ]
    note = (folder / ".bellman-matsya" / "README.md").read_text(encoding="utf-8")
    for line in (
        f"- Session: `{session_id}`",
        f"- Service: `{stand_in.url}`",
        "- `bellman-matsya project status` prints the session",
        "- `bellman-matsya project submit` appends `economics.md`",
        "- `bellman-matsya project pull` writes the products",
        f'- `bellman-matsya ask {session_id} "<question>"` asks matsya-master',
        "`bellman-matsya docs` lists the pages of the user guide",
    ):
        assert line in note, line
    assert (folder / "AGENTS.md").read_text(encoding="utf-8") == project.AGENTS_PARAGRAPH + "\n"
    assert "`.bellman-matsya/README.md`" in project.AGENTS_PARAGRAPH
    assert "`bellman-matsya docs --all`" in project.AGENTS_PARAGRAPH

    # a second init is refused before any request and changes nothing
    sent = len(stand_in.requests)
    assert run("project", "init") == (
        2,
        "",
        f"Error: The folder {folder.resolve()} is already a Matsya project, of session "
        f"{session_id}; bellman-matsya project status shows it.\n",
    )
    assert len(stand_in.requests) == sent and _held(folder) == held

    # a folder named on the command line, with an AGENTS.md of its own
    ours = "Our own instructions for a local model.\n"
    other = _folder(tmp_path, "second model", {"AGENTS.md": ours, "economics.md": ECONOMICS})
    status, out, err = run("project", "init", str(other))
    assert (status, err) == (0, "")
    assert out.splitlines()[4:] == [
        "AGENTS.md exists and was left as it is; add this paragraph to it for an assistant:",
        "",
        project.AGENTS_PARAGRAPH,
        "",
        "Submit the model, in the project folder, with: bellman-matsya project submit",
    ]
    assert (other / "AGENTS.md").read_text(encoding="utf-8") == ours
    assert stand_in.sessions[_held(other)["session"]]["name"] == "second model"

    # a new folder without economics.md, with --json: the session holds no entry
    third = tmp_path / "third"
    status, out, err = run("project", "init", str(third), "--json")
    assert (status, err) == (0, "")
    answer = json.loads(out)
    assert answer["project"] == _held(third) and answer["project"]["economics_sha256"] is None
    assert answer["session"]["name"] == "third" and answer["entry"] is None
    assert (answer["folder"], answer["agents"]) == (str(third.resolve()), "created")
    assert answer["written"] == [".bellman-matsya/project.json", ".bellman-matsya/README.md", "AGENTS.md"]
    assert answer["agents_paragraph"] == project.AGENTS_PARAGRAPH
    assert stand_in.sessions[answer["project"]["session"]]["entries"] == []


def test_submit_appends_economics_only_when_it_changed_and_sends_the_declaration_at_its_target(
    stand_in, run, tmp_path, monkeypatch
) -> None:
    """`project submit` sends the folder's stage file as the job's starting
    declaration, under its name, leaves out the page beside it, and starts
    the job at the target the declaration implies, `stage`, then `period`
    with a period file and `recipe` with a calibration file; `economics.md`,
    which `init` appended, is appended again only after an edit, once, and
    the job then built shows the next version and number in its label;
    `--target` and `--max-cycles` are sent as named."""
    folder = _folder(
        tmp_path,
        "household",
        {
            "economics.md": ECONOMICS,
            "declaration/stages/example/example.bl": STAGE,
            "declaration/stages/example/example.md": STAGE_PAGE,
        },
    )
    monkeypatch.chdir(folder)
    assert run("project", "init")[0] == 0
    session_id = _held(folder)["session"]

    def requests() -> list[dict]:
        return [
            held["body"]
            for held in stand_in.requests
            if (held["method"], held["path"]) == ("POST", "/v1/model-iterations")
        ]

    def entries() -> list[tuple[int, str]]:
        return [(entry["number"], entry["kind"]) for entry in stand_in.sessions[session_id]["entries"]]

    status, out, err = run("project", "submit")
    assert (status, err) == (0, "")
    job_id = _identifier(JOB, out)
    assert out.splitlines() == [
        f"economics.md is unchanged since session {session_id} last received it, so no entry "
        "was appended.",
        "Starting declaration: example.bl",
        "Left out of the starting declaration: declaration/stages/example/example.md",
        "Target: stage, read from declaration/",
        "household · stage · job 1 · queued",
        f"Job {job_id}: queued",
        f"Follow it with: bellman-matsya job wait {job_id}",
    ]
    assert requests() == [
        {"session": session_id, "target": "stage", "starting_declaration": {"example.bl": STAGE}}
    ]

    # a period file makes the target period, and a calibration file recipe
    (folder / "declaration" / "period.yml").write_text(PERIOD, encoding="utf-8")
    status, out, _ = run("project", "submit", "--json")
    answer = json.loads(out)
    assert set(answer) == {
        "folder",
        "project",
        "economics",
        "entry",
        "target",
        "target_named",
        "starting_declaration",
        "left_out",
        "job",
    }
    assert (answer["economics"], answer["entry"], answer["target"], answer["target_named"]) == (
        "unchanged",
        None,
        "period",
        False,
    )
    assert answer["starting_declaration"] == ["example.bl", "period.yml"]
    assert answer["left_out"] == ["declaration/stages/example/example.md"]
    assert answer["job"]["label"]["text"] == "household · period · job 2 · queued"
    (folder / "declaration" / "calibration").mkdir()
    (folder / "declaration" / "calibration" / "base.yml").write_text("β: 0.96\n", encoding="utf-8")
    assert json.loads(run("project", "submit", "--json")[1])["target"] == "recipe"
    assert requests()[-1]["starting_declaration"] == {
        "example.bl": STAGE,
        "period.yml": PERIOD,
        "calibration/base.yml": "β: 0.96\n",
    }
    assert entries() == [(1, "user")]

    # an edit of economics.md is appended once, and --target names the target
    (folder / "economics.md").write_text(ECONOMICS + "Its income is risky.\n", encoding="utf-8")
    status, out, _ = run("project", "submit", "--target", "trellis", "--max-cycles", "2")
    assert status == 0
    job_id = _identifier(JOB, out)
    lines = out.splitlines()
    assert lines[0] == f"Entry 2: the text of economics.md, appended to session {session_id}"
    assert lines[3] == "Target: trellis, named by --target"
    assert (requests()[-1]["target"], requests()[-1]["max_cycles"]) == ("trellis", 2)
    assert entries() == [(1, "user"), (2, "user")]
    assert _held(folder)["economics_sha256"] == _digest(folder / "economics.md")
    status, out, _ = run("job", "wait", job_id, "--interval", "0")
    assert _final(out)[0] == (
        f"household · trellis · version 2 · job 4 · needs_input ({job_id}), session {session_id}"
    )
    # without a further edit, nothing is appended; the question is the job's
    assert run("project", "submit")[0] == 0
    assert entries() == [(1, "user"), (2, "user"), (3, "question")]


def test_status_prints_the_session_its_labels_and_the_exact_reply_line(
    stand_in, run, tmp_path, monkeypatch
) -> None:
    """`project status` prints the session's identifier, its entries, its
    jobs by their labels and the question of the job that ended
    `needs_input` with the exact command that answers it; `bellman-matsya` alone
    adds the session, the latest job's label and the question to the
    orientation; and the reply line, run as printed, starts the next job,
    which `project status` then lists."""
    folder = _folder(
        tmp_path,
        "household",
        {"economics.md": ECONOMICS, "declaration/stages/example/example.bl": STAGE},
    )
    monkeypatch.chdir(folder)
    assert run("project", "init")[0] == 0
    session_id = _held(folder)["session"]
    job_id = _identifier(JOB, run("project", "submit")[1])
    assert run("job", "wait", job_id, "--interval", "0")[0] == 0

    status, out, err = run("project", "status")
    assert (status, err) == (0, "")
    reply = f"bellman-matsya session add {session_id} <file> --replies-to 2"
    assert out.splitlines() == [
        f"Session {session_id}: household",
        f"Service: {stand_in.url}",
        "Version of the text: 1",
        "Entries:",
        "  1. user",
        f"  2. question, from job {job_id}",
        "Jobs:",
        f"  household · stage · version 1 · job 1 · needs_input ({job_id})",
        "Questions awaiting a reply:",
        f"  2. {QUESTION}",
        f"     Reply with: {reply}",
        f'Ask a question with: bellman-matsya ask {session_id} "<question>"',
        "economics.md is unchanged since the session last received it.",
    ]
    answer = json.loads(run("project", "status", "--json")[1])
    assert answer["awaiting"] == [{"number": 2, "text": QUESTION, "reply": reply}]
    assert (answer["session"]["id"], answer["economics_changed"]) == (session_id, False)

    # the orientation names the session, the latest job and the question
    status, out, err = run()
    assert (status, err) == (0, "")
    lines = out.splitlines()
    end = lines.index("`bellman-matsya --help` lists the commands.")
    assert lines[end - 5 : end] == [
        "",
        f"This folder is a Matsya project: its session is `{session_id}`, kept by the service "
        f"at `{stand_in.url}`, and `.bellman-matsya/README.md` describes the folder and its commands. "
        f"Its latest job is household · stage · version 1 · job 1 · needs_input (`{job_id}`). "
        "One question awaits a reply:",
        "",
        f"- Entry 2: {QUESTION} Reply with `{reply}`.",
        "",
    ]

    # the reply line, run as printed, starts the job's next attempt
    (folder / "reply.md").write_text("The shock y is standard normal.\n", encoding="utf-8")
    status, out, _ = run(*reply.replace("<file>", "reply.md").split()[1:])
    assert status == 0
    following = _identifier(r"of the job awaiting an answer: job ([0-9a-f]{32})$", out)
    lines = run("project", "status")[1].splitlines()
    jobs = lines.index("Jobs:")
    assert lines[jobs + 1 : jobs + 3] == [
        f"  household · stage · version 1 · job 1 · needs_input ({job_id})",
        f"  household · stage · job 2 · queued ({following})",
    ]
    assert "No question awaits a reply." in lines


def test_init_submit_status_and_pull_replace_against_the_service(
    service, run, tmp_path, monkeypatch
) -> None:
    """Item 1 against the service of the test configuration: in a folder of
    one stage, whose stage file the elaborator refuses, `init` names the
    session after the folder; `submit` sends the stage file as the job's
    starting declaration, which Prose-to-Bellman-Sym repairs; `status`
    lists the job by its label, which shows the target `stage`; and
    `pull --replace` replaces the stage file with the job's, writes
    `report.md` and `model-prose.md`, keeps the page beside the stage,
    which the job did not write, and leaves `economics.md` byte for byte."""
    from scripted import STAGE as WRITTEN

    refused = WRITTEN.replace(" x_d = x\n", " x_d =\n")
    assert refused != WRITTEN
    folder = _folder(
        tmp_path,
        "household",
        {
            "economics.md": service.description,
            "declaration/stages/example/example.bl": refused,
            "declaration/stages/example/example.md": STAGE_PAGE,
        },
    )
    economics = (folder / "economics.md").read_bytes()
    monkeypatch.chdir(folder)
    status, out, err = run("project", "init")
    assert (status, err) == (0, "")
    session_id = _held(folder)["session"]
    assert bellman_matsya.session(session_id)["name"] == "household"

    status, out, err = run("project", "submit", "--max-cycles", "1")
    assert (status, err) == (0, "")
    job_id = _identifier(JOB, out)
    assert out.splitlines()[1:4] == [
        "Starting declaration: example.bl",
        "Left out of the starting declaration: declaration/stages/example/example.md",
        "Target: stage, read from declaration/",
    ]
    assert run("job", "wait", job_id, "--interval", "0.05")[0] == 0
    full = bellman_matsya.job(job_id, view="full")["result"]
    assert full["starting_declaration"] == {"example.bl": hashlib.sha256(refused.encode()).hexdigest()}
    assert [held["status"] for held in full["initial_writing"]["rounds"]] == [
        "supplied_refused",
        "elaborated",
    ]
    assert [held["status"] for held in full["cycles"][0]["writing"]["rounds"]] == [
        "elaborated"
    ]

    status, out, _ = run("project", "status")
    lines = out.splitlines()
    assert lines[:3] == [
        f"Session {session_id}: household",
        f"Service: {service.url}",
        "Version of the text: 1",
    ]
    assert lines[lines.index("Jobs:") + 1] == (
        f"  household · stage · version 1 · job 1 · converged ({job_id})"
    )
    assert "No question awaits a reply." in lines

    status, out, err = run("project", "pull", "--replace")
    assert (status, err) == (0, "")
    assert _final(out) == [
        f"household · stage · version 1 · job 1 · converged ({job_id}), session {session_id}",
        f"The job ended converged, with the reason {bellman_matsya.job(job_id)['result']['reason']}.",
        "Wrote 3 files into this folder:",
        "  model-prose.md",
        "  report.md",
        "  declaration/stages/example/example.bl (replaced)",
        "Kept 1 file of declaration/ that the job did not write:",
        "  declaration/stages/example/example.md",
        "economics.md was not written.",
    ]
    stage = folder / "declaration" / "stages" / "example" / "example.bl"
    assert stage.read_text(encoding="utf-8") == WRITTEN
    assert (folder / "declaration" / "stages" / "example" / "example.md").read_text(
        encoding="utf-8"
    ) == STAGE_PAGE
    assert (folder / "economics.md").read_bytes() == economics
    ended = bellman_matsya.job(job_id)
    assert (folder / "model-prose.md").read_text(encoding="utf-8") == (
        f'---\njob: "{job_id}"\nlabel: "household · stage · version 1 · job 1 · converged"\n'
        f'session: "{session_id}"\nversion: 1\ndate: {ended["updated_at"][:10]}\n---\n\n'
        + full["cycles"][0]["prose_writing"]["description"]
    )
    report = (folder / "report.md").read_text(encoding="utf-8").splitlines()
    assert report[0] == "# Report of the job" and "The judges agree on every heading." in report
    assert not (folder / "record.json").exists()
    service.caller.assert_finished()


def test_pull_into_writes_the_model_folder_and_leaves_the_declaration(
    stand_in, run, tmp_path, monkeypatch
) -> None:
    """`project pull` without `--replace` writes the model folder of the
    latest job that holds a record, passing over a later job that has not
    ended, into `bellman-matsya-output/job-1/`, and leaves the folder's declaration
    and `economics.md` as they were; with `--into` it writes into the
    sub-folder named. A session with no recorded job, `--replace` with
    `--into`, a job that holds no record, a sub-folder that is not empty
    and a folder of another service are refused, each with one sentence
    and exit status 2."""
    folder = _folder(
        tmp_path,
        "household",
        {
            "economics.md": ECONOMICS,
            "declaration/stages/example/example.bl": STAGE,
            "declaration/stages/example/example.md": STAGE_PAGE,
        },
    )
    monkeypatch.chdir(folder)
    assert run("project", "init")[0] == 0
    session_id = _held(folder)["session"]
    assert run("project", "pull") == (
        2,
        "",
        f"Error: No job of session {session_id} holds a record yet, so there is nothing to "
        "write; bellman-matsya project status lists its jobs.\n",
    )
    stand_in.next_ends = ["not_converged"]
    ended = _identifier(JOB, run("project", "submit")[1])
    assert run("job", "wait", ended, "--interval", "0")[0] == 0
    later = _identifier(JOB, run("project", "submit")[1])
    declaration = _files(folder / "declaration")

    assert run("project", "pull", "--replace", "--into") == (
        2,
        "",
        f"Error: {project.REPLACE_AND_INTO}\n",
    )
    assert run("project", "pull", later) == (
        2,
        "",
        f"Error: Job {later} holds no record, so it has no products to write; its state is "
        "running.\n",
    )

    status, out, err = run("project", "pull")
    assert (status, err) == (0, "")
    assert _final(out) == [
        f"household · stage · version 1 · job 1 · not_converged ({ended}), session {session_id}",
        "The job ended not_converged, with the reason cycle_limit_reached.",
        "The returned declaration files are provisional; the job did not establish convergence.",
        "Wrote 6 files to bellman-matsya-output/job-1:",
        "  economics.md",
        "  report.md",
        "  declaration/stages/example/example.bl",
        "  declaration/stages/example/methods.yml",
        "  declaration/stages/example/example.md",
        "  record.json",
        "declaration/ was not written.",
    ]
    written = _files(folder / "bellman-matsya-output" / "job-1")
    assert sorted(written) == [
        "declaration/stages/example/example.bl",
        "declaration/stages/example/example.md",
        "declaration/stages/example/methods.yml",
        "economics.md",
        "record.json",
        "report.md",
    ]
    assert written["economics.md"].decode("utf-8").endswith("\n---\n\n" + MODEL_PROSE)
    assert json.loads(written["record.json"])["id"] == ended
    assert _files(folder / "declaration") == declaration
    assert (folder / "economics.md").read_text(encoding="utf-8") == ECONOMICS

    # the same sub-folder again is refused; --into names another
    assert run("project", "pull") == (
        2,
        "",
        "Error: bellman-matsya-output/job-1 is not empty; name a new or empty sub-folder with "
        "--into <subfolder>\n",
    )
    status, out, _ = run("project", "pull", ended, "--into", "second-look", "--json")
    answer = json.loads(out)
    assert set(answer) == {"folder", "project", "job", "into", "written", "replaced", "kept"}
    assert (answer["into"], answer["replaced"], answer["kept"]) == ("second-look", [], [])
    assert answer["job"]["id"] == ended and sorted(answer["written"]) == sorted(written)
    assert _files(folder / "second-look") == written

    # --into names a sub-folder of the project, including when a path
    # outside it is supplied through an existing symbolic link.
    outside = tmp_path / "outside"
    for named in ("../outside", str(outside)):
        assert run("project", "pull", ended, "--into", named) == (
            2,
            "",
            f"Error: {named} is not a sub-folder of this project; name a sub-folder within it "
            "with --into <subfolder>\n",
        )
    (folder / "linked-output").symlink_to(tmp_path, target_is_directory=True)
    assert run("project", "pull", ended, "--into", "linked-output/outside") == (
        2,
        "",
        "Error: linked-output/outside is not a sub-folder of this project; name a sub-folder "
        "within it with --into <subfolder>\n",
    )
    assert not outside.exists()

    status, out, err = run("project", "pull", ended, "--replace")
    assert (status, err) == (0, "")
    assert "  .bellman-matsya/writer-note.md" in out.splitlines()
    assert (folder / ".bellman-matsya" / "writer-note.md").read_text(encoding="utf-8") == NOTE
    assert (folder / "declaration" / "stages" / "example" / "example.md").read_text(
        encoding="utf-8"
    ) == STAGE_PAGE

    # a folder whose service is not the client's sends no request there
    sent = len(stand_in.requests)
    monkeypatch.setenv("BELLMAN_MATSYA_SERVER", "http://127.0.0.1:9")
    assert run("project", "status") == (
        2,
        "",
        f"Error: This folder's session is kept by the service at {stand_in.url}, and the client "
        "is configured for the service at http://127.0.0.1:9; the client sends a folder's "
        "requests only to the service it is configured for.\n",
    )
    assert len(stand_in.requests) == sent


def test_the_command_reference_drives_one_project_run(stand_in, run, tmp_path, monkeypatch) -> None:
    """The installed reference's four project command forms are enough to
    create a project, submit a job, inspect its session and write its files.
    Its `--json` forms return the fields the reference names."""
    reference = (
        Path(__file__).resolve().parents[1] / "docs" / "05-the-command-reference.md"
    ).read_text(encoding="utf-8")
    forms = {
        name: form
        for form, name in re.findall(
            r"^\| `(bellman-matsya project (init|submit|status|pull)[^`]*)` \|",
            reference,
            re.MULTILINE,
        )
    }
    assert set(forms) == {"init", "submit", "status", "pull"}
    assert all("[--json]" in form for form in forms.values())
    assert "bellman-matsya job wait <job>" in reference

    def command(name: str) -> tuple[int, str, str]:
        words = forms[name].partition(" [")[0].split()
        assert words == ["bellman-matsya", "project", name]
        return run(*words[1:], "--json")

    folder = _folder(
        tmp_path,
        "household",
        {"economics.md": ECONOMICS, "declaration/stages/example/example.bl": STAGE},
    )
    monkeypatch.chdir(folder)
    assert command("init")[0] == 0
    stand_in.next_ends = ["not_converged"]
    status, out, err = command("submit")
    assert (status, err) == (0, "")
    submitted = json.loads(out)
    assert submitted["target"] == "stage"
    assert submitted["starting_declaration"] == ["example.bl"]
    job_id = submitted["job"]["id"]
    assert run("job", "wait", job_id, "--interval", "0")[0] == 0
    status, out, err = command("status")
    assert (status, err) == (0, "")
    assert json.loads(out)["session"]["jobs"][-1]["id"] == job_id
    status, out, err = command("pull")
    assert (status, err) == (0, "")
    pulled = json.loads(out)
    assert pulled["into"] == "bellman-matsya-output/job-1"
    assert {"economics.md", "report.md", "record.json"}.issubset(pulled["written"])
    assert (folder / "bellman-matsya-output" / "job-1" / "record.json").exists()
