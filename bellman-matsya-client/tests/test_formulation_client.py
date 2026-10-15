"""The formulation selected for a job reaches the request through each client entry point."""

from __future__ import annotations

import shlex
from pathlib import Path

import pytest

import bellman_matsya
from bellman_matsya.client import MatsyaClient, MatsyaError


def _last_job_request(stand_in) -> dict:
    requests = [
        request["body"]
        for request in stand_in.requests
        if request["method"] == "POST" and request["path"] == "/v1/model-iterations"
    ]
    assert requests
    return requests[-1]


def test_python_calls_forward_formulation_and_omit_it_by_default(
    stand_in, tmp_path: Path
) -> None:
    client = MatsyaClient(stand_in.token, stand_in.url)
    formulation = "The household with a borrowing constraint"
    source = "The paper describes two household problems.\n"

    client.submit_job(source_text=source, target="stage", formulation=formulation)
    assert _last_job_request(stand_in)["formulation"] == formulation
    padded = f"  {formulation}  "
    client.submit_job(source_text=source, target="stage", formulation=padded)
    assert _last_job_request(stand_in)["formulation"] == padded
    client.submit_job(source_text=source, target="stage", formulation="x" * 500)
    assert _last_job_request(stand_in)["formulation"] == "x" * 500
    client.submit_job(source_text=source, target="stage")
    assert "formulation" not in _last_job_request(stand_in)

    session = client.new_session("two models")["id"]
    client.add_entry(session, source)
    client.submit_job(session=session, target="stage", formulation=formulation)
    assert _last_job_request(stand_in)["formulation"] == formulation
    assert _last_job_request(stand_in)["session"] == session

    paper = tmp_path / "paper.md"
    paper.write_text(source, encoding="utf-8")
    client.start_job(paper, paper=True, target="stage", formulation=formulation)
    assert _last_job_request(stand_in)["formulation"] == formulation
    assert "source" not in _last_job_request(stand_in)

    bellman_matsya.start_job(
        paper, paper=True, no_session=True, target="stage", formulation=formulation
    )
    assert _last_job_request(stand_in)["source"] == {"kind": "paper", "text": source}
    assert _last_job_request(stand_in)["formulation"] == formulation
    bellman_matsya.submit_job(
        source_text=source, target="stage", formulation=formulation
    )
    assert _last_job_request(stand_in)["formulation"] == formulation


@pytest.mark.parametrize("formulation", ["", " \n ", "x" * 501, 42])
def test_invalid_formulation_is_refused_before_a_session_or_request(
    stand_in, tmp_path: Path, formulation: object
) -> None:
    client = MatsyaClient(stand_in.token, stand_in.url)
    paper = tmp_path / "paper.md"
    paper.write_text("Two household problems.\n", encoding="utf-8")

    with pytest.raises(ValueError, match="formulation"):
        client.submit_job(
            source_text="Two household problems.",
            target="stage",
            formulation=formulation,
        )
    with pytest.raises(ValueError, match="formulation"):
        client.start_job(paper, target="stage", formulation=formulation)
    assert stand_in.requests == []
    assert stand_in.sessions == {}


def test_job_submit_command_forwards_formulation_for_file_and_session(
    stand_in, run, tmp_path: Path
) -> None:
    formulation = "The second household problem"
    paper = tmp_path / "paper.md"
    paper.write_text("Two household problems.\n", encoding="utf-8")

    status, _, _ = run(
        "job",
        "submit",
        str(paper),
        "--paper",
        "--target",
        "stage",
        "--formulation",
        formulation,
    )
    assert status == 0
    assert _last_job_request(stand_in)["formulation"] == formulation
    assert "session" in _last_job_request(stand_in)

    status, _, _ = run(
        "job",
        "submit",
        str(paper),
        "--no-session",
        "--target",
        "stage",
        "--formulation",
        formulation,
    )
    assert status == 0
    assert _last_job_request(stand_in)["formulation"] == formulation
    assert _last_job_request(stand_in)["source"]["kind"] == "description"

    client = MatsyaClient(stand_in.token, stand_in.url)
    session = client.new_session("two models")["id"]
    client.add_entry(session, "Two household problems.")
    status, _, _ = run(
        "job",
        "submit",
        "--session",
        session,
        "--target",
        "stage",
        "--formulation",
        formulation,
    )
    assert status == 0
    assert _last_job_request(stand_in)["session"] == session
    assert _last_job_request(stand_in)["formulation"] == formulation

    status, help_text, _ = run("job", "submit", "--help")
    assert status == 0 and "--formulation TEXT" in help_text


@pytest.mark.parametrize("formulation", ["", "  ", "x" * 501])
def test_command_refuses_invalid_formulation_before_any_request(
    stand_in, run, tmp_path: Path, formulation: str
) -> None:
    paper = tmp_path / "paper.md"
    paper.write_text("Two household problems.\n", encoding="utf-8")

    status, _, error = run(
        "job", "submit", str(paper), "--target", "stage", "--formulation", formulation
    )
    assert status == 2 and "formulation" in error
    assert stand_in.requests == []
    assert stand_in.sessions == {}


def test_refused_session_job_retry_keeps_the_selected_formulation(
    stand_in, tmp_path: Path
) -> None:
    paper = tmp_path / "paper.md"
    paper.write_text("Two household problems.\n", encoding="utf-8")
    formulation = "The household's second problem"
    client = MatsyaClient(stand_in.token, stand_in.url)

    with pytest.raises(MatsyaError) as refused:
        client.start_job(paper, target="stage", max_cycles=0, formulation=formulation)

    retry = str(refused.value).split("start one with: ", 1)[1]
    assert shlex.split(retry)[-2:] == ["--formulation", formulation]
