"""The acceptance file of AMD-MAT-011 on the side of the client: items 5 and
6 of the amendment's §6. Against the stand-in of the service: `matsya job
submit` refuses a job whose command names no target, or another word, with
exit status 2 and the four words, and `start_job` and `submit_job` refuse
it before any request; the request carries the target given, from a file
kept in a session, from a session, from a file with no session and from a
paper; the label the commands print names the target as the service gives
it, a job of no session's label being its target and its state; and the
folder `matsya job files` writes holds the files of the target, its report
and front matter naming the target. Against the service of the test
configuration, a job of no session submitted with `--target stage`, whose
label, record and report name the target. The client's words for the four
targets and for the refusal are compared with the service's, and the
former name of the formulation is looked for in the client's files."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

import matsya
from conftest import PAPER, RECIPE_FILES, TARGET_REFUSAL, TARGETS, TWO_STAGES
from matsya.client import MatsyaClient

CLIENT = Path(__file__).resolve().parents[1]
TIME = re.compile(r"^\d\d:\d\d:\d\d  ")
MODEL = "Household with firms"
# the four words as argparse prints them in the usage line of a refusal
FOUR_WORDS = "{stage,period,trellis,recipe}"
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


def test_item_5_job_submit_without_a_target_is_refused_before_any_request(stand_in, run, tmp_path) -> None:
    """A submission whose command names no target, or a word that is no
    target, ends with exit status 2, the usage line printing the four
    words, and sends no request; `start_job` and `submit_job` require the
    target, and refuse another word with the service's sentence before any
    request, `start_job` before it reads the file or creates a session."""
    description = tmp_path / "model.md"
    description.write_text("A household works for a firm.\n", encoding="utf-8")
    for arguments, fault in (
        ((str(description),), "the following arguments are required: --target"),
        (("--session", "0" * 32), "the following arguments are required: --target"),
        ((str(description), "--no-session", "--max-cycles", "2"), "the following arguments are required: --target"),
        ((str(description), "--target", "model"), "argument --target: invalid choice: 'model'"),
        (("--session", "0" * 32, "--target", "Stage"), "argument --target: invalid choice: 'Stage'"),
    ):
        status, out, err = run("job", "submit", *arguments)
        assert (status, out) == (2, ""), arguments
        assert fault in err and FOUR_WORDS in err, err

    client = MatsyaClient(stand_in.token, stand_in.url)
    with pytest.raises(TypeError, match="target"):
        client.submit_job(session="0" * 32)
    with pytest.raises(TypeError, match="target"):
        matsya.start_job(description)
    for word in ("model", "Stage", None):
        refusal = f"^{TARGET_REFUSAL}, not {re.escape(repr(word))}\\.$"
        with pytest.raises(ValueError, match=refusal):
            client.submit_job(source_text="A household saves.", target=word)
        with pytest.raises(ValueError, match=refusal):
            matsya.submit_job(session="0" * 32, target=word)
        with pytest.raises(ValueError, match=refusal):
            matsya.start_job(description, target=word)
        with pytest.raises(ValueError, match=refusal):
            client.start_job(tmp_path / "absent.md", name="a household", target=word)
    assert stand_in.requests == [] and stand_in.sessions == {}


def test_item_5_the_request_carries_the_target_and_every_label_names_it(stand_in, run, tmp_path) -> None:
    """The target given is sent in every form of the request, and the label
    the commands print names it after the session's name, from the queue to
    the job's end, in the session's listing and for the job a reply starts,
    whose request copies the target of the job that asked; the label of a
    job of no session is its target and its state, printed as a line of its
    own while the job runs."""
    description = tmp_path / "model.md"
    description.write_text("A household works for a firm.\n", encoding="utf-8")
    status, out, _ = run("job", "submit", str(description), "--target", "trellis")
    assert status == 0
    session_id = json.loads(stand_in.answers[0])["id"]
    first = _identifier(r"^Job ([0-9a-f]{32}): queued$", out)
    assert stand_in.requests[-1]["body"] == {"session": session_id, "target": "trellis"}
    status, out, _ = run("job", "status", first)
    assert out.splitlines() == ["model · trellis · job 1 · queued", f"Job {first}: queued"]
    status, out, _ = run("job", "wait", first, "--interval", "0")
    assert _final(out)[0] == f"model · trellis · version 1 · job 1 · needs_input ({first}), session {session_id}"

    # the reply to the job's question starts the next attempt at the same target
    reply = tmp_path / "reply.md"
    reply.write_text("Income y is lognormal with mean one.\n", encoding="utf-8")
    status, out, _ = run("session", "add", session_id, str(reply), "--replies-to", "2")
    second = _identifier(r"^Follow it with: matsya job wait ([0-9a-f]{32})$", out)
    status, out, _ = run("job", "wait", second, "--interval", "0")
    assert _final(out)[0] == f"model · trellis · version 3 · job 2 · converged ({second}), session {session_id}"
    status, out, _ = run("session", "show", session_id)
    lines = out.splitlines()
    at = lines.index("Jobs:")
    assert lines[at + 1 : at + 3] == [
        f"  model · trellis · version 1 · job 1 · needs_input ({first})",
        f"  model · trellis · version 3 · job 2 · converged ({second})",
    ]

    # with no session, the label is the target and the state
    status, out, _ = run("job", "submit", str(description), "--no-session", "--target", "period")
    loose = _identifier(r"^Job ([0-9a-f]{32}): queued$", out)
    assert stand_in.requests[-1]["body"] == {
        "source": {"kind": "description", "text": "A household works for a firm.\n"},
        "target": "period",
    }
    status, out, _ = run("job", "status", loose)
    assert out.splitlines() == ["period · queued", f"Job {loose}: queued"]
    status, out, _ = run("job", "wait", loose, "--interval", "0")
    assert _final(out)[0] == f"period · converged ({loose}), no session"

    # a paper's text, and the two functions of the module
    paper = tmp_path / "paper.md"
    paper.write_text(PAPER, encoding="utf-8")
    status, _, _ = run("job", "submit", str(paper), "--paper", "--no-session", "--target", "recipe")
    assert status == 0 and stand_in.requests[-1]["body"]["target"] == "recipe"
    started = matsya.start_job(description, name="a household", target="recipe")
    assert stand_in.requests[-1]["body"] == {"session": started["session"]["id"], "target": "recipe"}
    submitted = matsya.submit_job(session=session_id, target="stage")
    assert stand_in.requests[-1]["body"] == {"session": session_id, "target": "stage"}
    assert matsya.job(submitted["id"])["label"]["text"] == "model · stage · job 3 · queued"


def test_item_5_the_folder_and_the_report_name_the_target(stand_in, run, tmp_path) -> None:
    """The folder of a recipe holds its files, the recipe `spec.yml` placed
    by its name under `declaration/`; the report's first heading and the
    front matter of `economics.md` give the label's text, which names the
    target; and `record.json` holds the target and the structure as the
    service returned them."""
    status, out, _ = run("session", "new", MODEL)
    session_id = _identifier(rf"^Session ([0-9a-f]{{32}}): {MODEL}$", out)
    entry = tmp_path / "entry.md"
    entry.write_text("A household works for a firm.\n", encoding="utf-8")
    assert run("session", "add", session_id, str(entry))[0] == 0
    stand_in.next_ends.append("recipe")
    status, out, _ = run("job", "submit", "--session", session_id, "--target", "recipe")
    job_id = _identifier(r"^Job ([0-9a-f]{32}): queued$", out)
    label = f"{MODEL} · recipe · version 1 · job 1 · not_converged"
    status, out, _ = run("job", "wait", job_id, "--interval", "0")
    assert _final(out)[0] == f"{label} ({job_id}), session {session_id}"

    folder = tmp_path / "proposed"
    status, out, _ = run("job", "files", job_id, str(folder))
    assert status == 0 and "  declaration/spec.yml" in out.splitlines()
    assert (folder / "declaration" / "spec.yml").read_text(encoding="utf-8") == RECIPE_FILES["spec.yml"]
    report = (folder / "report.md").read_text(encoding="utf-8").splitlines()
    assert report[2:5] == ["## The job", "", f"{label} ({job_id}), session {session_id}"]
    assert f'label: "{label}"' in (folder / "economics.md").read_text(encoding="utf-8").splitlines()
    held = json.loads((folder / "record.json").read_text(encoding="utf-8"))
    assert (held["label"]["target"], held["result"]["target"]) == ("recipe", "recipe")
    assert held["result"]["structure"] == TWO_STAGES


def test_item_5_against_the_service_a_job_names_its_target(service, run, tmp_path) -> None:
    """Against the service of the test configuration: the command without a
    target is refused before any request; a job of no session submitted
    with `--target stage` carries the target in its request, so that the
    service's label, which for a job of no session is its target and its
    state, its record and its products view name it; the folder's report
    names it in its first heading."""
    description = tmp_path / "model.md"
    description.write_text(service.description, encoding="utf-8")
    status, out, err = run("job", "submit", str(description), "--no-session")
    assert (status, out) == (2, "") and FOUR_WORDS in err

    status, out, _ = run(
        "job", "submit", str(description), "--no-session", "--target", "stage", "--max-cycles", "1"
    )
    assert status == 0
    job_id = _identifier(r"^Job ([0-9a-f]{32}): queued$", out)
    status, out, _ = run("job", "wait", job_id, "--interval", "0.05")
    assert status == 0
    assert _final(out)[:2] == [
        f"stage · converged ({job_id}), no session",
        "The job ended converged, with the reason source_agreement_and_semantic_fixed_point.",
    ]
    status, out, _ = run("job", "status", job_id, "--json")
    held = json.loads(out)
    assert (held["label"]["target"], held["label"]["text"]) == ("stage", "stage · converged")
    assert (held["result"]["target"], held["result"]["structure"]["level"]) == ("stage", "stage")

    folder = tmp_path / "proposed"
    assert run("job", "files", job_id, str(folder))[0] == 0
    report = (folder / "report.md").read_text(encoding="utf-8").splitlines()
    assert report[2:5] == ["## The job", "", f"stage · converged ({job_id}), no session"]
    assert (folder / "declaration" / "stages" / "example" / "example.bl").is_file()
    service.caller.assert_finished()


def test_item_6_the_former_name_of_the_formulation_appears_nowhere_in_the_client() -> None:
    """The client's code, tests, README and project file do not name the
    field `formulation` by its former name; the copies of the documentation
    under `docs/` are compared with their source by `test_docs.py`."""
    former = "target" + "_formulation"
    paths = [
        *sorted((CLIENT / "src" / "matsya").glob("*.py")),
        *sorted((CLIENT / "tests").glob("*.py")),
        CLIENT / "README.md",
        CLIENT / "pyproject.toml",
    ]
    assert [path.name for path in paths if former in path.read_text(encoding="utf-8")] == []


def test_the_client_and_the_stand_in_name_the_services_four_targets() -> None:
    """The four targets of the client and of the stand-in are the service's
    `TARGETS`, in its order, and the client's refusal of another word begins
    with the service's sentence, `TARGET_REFUSAL`."""
    meaning = pytest.importorskip("matsya_service.meaning")
    processor = pytest.importorskip("matsya_service.processor")
    assert matsya.TARGETS == TARGETS == meaning.TARGETS
    assert TARGET_REFUSAL == processor.TARGET_REFUSAL
    with pytest.raises(ValueError) as refused:
        MatsyaClient("", "http://127.0.0.1:9").submit_job(source_text="A household saves.", target="model")
    assert str(refused.value) == f"{processor.TARGET_REFUSAL}, not 'model'."
