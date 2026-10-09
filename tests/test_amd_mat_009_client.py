"""The acceptance file of AMD-MAT-009 on the side of the client: item 5 of
the amendment's §7 against the stand-in of the service, whose turn starts a
job from the session when the question asks for one ("submit this as a
job") and names it under `job_started`. `matsya ask` prints the job's line
when the result names a job and nothing when it holds null; with `--follow
<folder>` it waits for the job as `matsya job wait` does and writes the
model folder and the report as `matsya job files` does. The same against the
service itself is in `test_acceptance.py`."""

from __future__ import annotations

import json
import re

from conftest import ANSWER, CITATION, JOB_ANSWER, RECORDS, products_of

TIME = re.compile(r"^\d\d:\d\d:\d\d  ")
MODEL = "Household with firms"
# the lines that follow every answer of the stand-in: its one citation
CITED = [
    "",
    "Citations:",
    "  [1] docs/Bellman-Sym/01-stage.md, The stage",
    f'      "{CITATION["quote"]}"',
]


def _final(out: str) -> list[str]:
    """The lines a command printed, without the lines of progress."""
    return [line for line in out.splitlines() if not TIME.match(line)]


def _steps(out: str) -> list[str]:
    """The lines of progress a command printed, without the local time."""
    return [TIME.sub("", line) for line in out.splitlines() if TIME.match(line)]


def test_item_5_ask_prints_the_job_a_turn_started_and_follow_writes_its_folder(stand_in, run, tmp_path) -> None:
    status, out, _ = run("session", "new", MODEL)
    session_id = re.search(rf"^Session ([0-9a-f]{{32}}): {MODEL}$", out, re.MULTILINE).group(1)
    entry = tmp_path / "entry.md"
    entry.write_text("A household works for a firm.\n", encoding="utf-8")
    assert run("session", "add", session_id, str(entry))[0] == 0
    jobs = stand_in.sessions[session_id]["jobs"]

    # a question that asks for no job: the result's job_started is null and
    # ask prints no job's line
    status, out, err = run("ask", session_id, "What does the model contain?", "--interval", "0")
    assert (status, err, jobs) == (0, "", [])
    assert _final(out) == [ANSWER, *CITED]

    # a question that asks for a job: the job's number, the version of the
    # session's text it was built from, which holds the question as entry 4,
    # and its identifier
    status, out, err = run("ask", session_id, "Submit this as a job.", "--interval", "0")
    (first,) = jobs
    assert (status, err) == (0, "")
    assert _final(out) == [
        JOB_ANSWER,
        *CITED,
        "",
        f"Job 1 started from version 4 of this session's text ({first}); "
        f"follow it with: matsya job wait {first}",
    ]

    # with --follow the command waits for the job, printing its steps, and
    # writes its model folder
    folder = tmp_path / "proposed"
    stand_in.next_ends.append("not_converged")
    status, out, err = run(
        "ask", session_id, "Submit this as a job.", "--follow", str(folder), "--interval", "0"
    )
    second = jobs[-1]
    assert (status, err, len(jobs)) == (0, "", 2)
    assert _steps(out) == [
        "queued",
        "running: step conversation (the conversation role)",
        "queued",
        "running: step preparation (the Model-prose-writer and the prose-source-judge)",
        "running: step writing (Prose-to-Bellman-Sym), cycle 1 of 2",
        "running: step writing (Prose-to-Bellman-Sym), cycle 2 of 2",
    ]
    assert _final(out) == [
        JOB_ANSWER,
        *CITED,
        "",
        f"Job 2 started from version 6 of this session's text ({second}); "
        f"follow it with: matsya job wait {second}",
        f"{MODEL} · stage · version 6 · job 2 · not_converged ({second}), session {session_id}",
        "The job ended not_converged, with the reason cycle_limit_reached.",
        "Files of the last cycle: example.bl, methods.yml, note.md",
        f"Write the model folder and its report with: matsya job files {second} <folder>",
        f"Wrote 6 files to {folder}:",
        "  economics.md",
        "  report.md",
        "  declaration/stages/example/example.bl",
        "  declaration/stages/example/methods.yml",
        "  declaration/stages/example/example.md",
        "  record.json",
    ]
    held = json.loads((folder / "record.json").read_text(encoding="utf-8"))
    assert (held["id"], held["result"]) == (second, products_of(RECORDS["not_converged"]))
    assert (folder / "report.md").read_text(encoding="utf-8").splitlines()[4] == (
        f"{MODEL} · stage · version 6 · job 2 · not_converged ({second}), session {session_id}"
    )

    # --json prints the turn's answer; the steps go to the standard error
    folder = tmp_path / "printed"
    status, out, err = run(
        "ask", session_id, "Submit this as a job.", "--follow", str(folder), "--interval", "0", "--json"
    )
    turn = json.loads(out)
    assert (status, turn["state"]) == (0, "finished")
    assert turn["record"]["result"]["job_started"]["id"] == jobs[-1] != second
    assert "running: step writing (Prose-to-Bellman-Sym), cycle 2 of 2" in err
    assert (folder / "report.md").is_file()

    # a question that starts no job writes no folder
    folder = tmp_path / "none"
    status, out, _ = run("ask", session_id, "What else?", "--follow", str(folder), "--interval", "0")
    assert status == 0 and _final(out)[-2:] == ["", "The turn started no job, so no folder was written."]
    assert not folder.exists() and len(jobs) == 3

    # a folder that is not empty is refused before the question is sent
    stand_in.requests.clear()
    status, out, err = run("ask", session_id, "Submit this as a job.", "--follow", str(tmp_path))
    assert (status, out, stand_in.requests) == (1, "", [])
    assert err.startswith(f"Error: {tmp_path} is not empty; name a new or empty folder")
