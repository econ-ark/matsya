"""The acceptance tests of AMD-MAT-020 §5 on the client: the publication
and the default change through the client and the command (item 2), the
omitted and the explicit selector through each public call (items 3 and 4),
and the export of a job's full answer (item 5); then, against the service
itself, a job submitted under the service's default ID and exported, whose
configuration digest agrees with the ID. The stand-in service answers the
routes as `api.py` does; no test calls a provider."""

from __future__ import annotations

import hashlib
import io
import json
import os
import zipfile
from pathlib import Path

import pytest

import bellman_matsya
from bellman_matsya import project
from bellman_matsya.client import (
    CONFIGURATION_ID_REFUSAL,
    MatsyaClient,
    MatsyaError,
    configuration_archive,
)
from conftest import DEFAULT_CONFIGURATION, DIGEST, JOB_REQUEST, request_digest

CANDIDATE = "e" * 64


def _sent(stand_in) -> list[tuple[str, str, object]]:
    sent = [(request["method"], request["path"], request["body"]) for request in stand_in.requests]
    stand_in.requests.clear()
    return sent


def _folder(base: Path, version: str = "0.3.99") -> Path:
    """A small configuration folder with a manifest, as the client sends
    it: the client checks nothing of the folder but its links."""
    folder = base / "candidate"
    (folder / "texts").mkdir(parents=True)
    (folder / "texts" / "writer.md").write_text("Write a stage.\n", encoding="utf-8")
    (folder / "settings.json").write_text('{"cycle_limit": 1}\n', encoding="utf-8")
    (folder / "__pycache__").mkdir()
    (folder / "__pycache__" / "x.pyc").write_bytes(b"\0")
    manifest = {"version": version, "files": {"texts/writer.md": "0" * 64, "settings.json": "1" * 64}}
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return folder


def _identity(folder: Path) -> str:
    return hashlib.sha256((folder / "manifest.json").read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# item 2


def test_item_2_an_administrator_publishes_and_sets_the_default_and_a_user_is_refused(
    stand_in, run, tmp_path: Path
) -> None:
    """`publish_configuration` sends the folder's files, by their relative
    paths and without bytecode caches, as a ZIP archive to
    `POST /v1/configurations`, and returns the ID and the version; a link
    within the folder is refused before any request. `set_default_configuration`
    sends `PUT /v1/configurations/default`. The command prints both answers
    and, with `--json`, the service's answer; a user without the permission
    reads the service's 403 and the command exits 1."""
    folder = _folder(tmp_path)
    identity = _identity(folder)
    client = MatsyaClient(stand_in.token, stand_in.url)
    data = configuration_archive(folder)
    assert sorted(zipfile.ZipFile(io.BytesIO(data)).namelist()) == [
        "manifest.json", "settings.json", "texts/writer.md",
    ]
    answer = client.publish_configuration(folder)
    assert answer == {"configuration_id": identity, "version": "0.3.99"}
    method, path, body = _sent(stand_in)[-1]
    assert (method, path) == ("POST", "/v1/configurations") and isinstance(body, bytes)
    assert stand_in.default_configuration == DEFAULT_CONFIGURATION
    assert client.publish_configuration(folder) == answer  # a repeat answers the same ID
    changed = client.set_default_configuration(identity)
    assert changed == {
        "previous_configuration_id": DEFAULT_CONFIGURATION,
        "configuration_id": identity,
        "version": "0.3.99",
    }
    assert _sent(stand_in)[-1] == ("PUT", "/v1/configurations/default", {"configuration_id": identity})
    with pytest.raises(ValueError, match="64 lowercase"):
        client.set_default_configuration("abc")
    assert not stand_in.requests

    # a symbolic link within the folder is refused before any request
    linked = tmp_path / "linked"
    linked.mkdir()
    (linked / "manifest.json").write_text("{}", encoding="utf-8")
    os.symlink(folder / "settings.json", linked / "settings.json")
    with pytest.raises(ValueError, match="symbolic link"):
        client.publish_configuration(linked)
    assert not stand_in.requests

    # the command
    status, out, _ = run("configuration", "publish", str(folder))
    assert status == 0
    assert out.splitlines()[0] == f"Published configuration {identity}, version 0.3.99"
    assert f"bellman-matsya configuration set-default {identity}" in out
    status, out, _ = run("configuration", "publish", str(folder), "--json")
    assert status == 0 and json.loads(out) == answer
    status, out, _ = run("configuration", "set-default", identity)
    assert status == 0
    assert out.splitlines()[:2] == [
        f"Default configuration: {identity}, version 0.3.99",
        f"Previous default: {identity}",
    ]
    stand_in.requests.clear()
    status, out, err = run("configuration", "set-default", "not-an-id")
    assert status == 2 and "64 lowercase hexadecimal" in err and not stand_in.requests
    status, out, err = run("configuration", "publish", str(linked))
    assert status == 1 and "symbolic link" in err and not stand_in.requests

    # a user without the permission reads the service's refusal
    stand_in.administrator = False
    with pytest.raises(MatsyaError) as refused:
        client.publish_configuration(folder)
    assert refused.value.status == 403 and "administrator" in str(refused.value)
    status, _, err = run("configuration", "set-default", identity)
    assert status == 1 and "(403)" in err and "administrator" in err
    assert stand_in.token not in err


# ---------------------------------------------------------------------------
# items 3 and 4


def test_item_3_and_4_the_selector_is_sent_by_each_call_and_omitted_by_default(
    stand_in, run, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`submit_job`, `start_job`, `project.submit`, `ask` and their package
    wrappers, and the commands `job submit`, `project submit` and `ask`,
    send `configuration_id` when it is given and no such field when it is
    not; the service's answers carry the resolved ID. A malformed ID is
    refused before any request, as is one of `model_key` and
    `source_cluster` without the other, and an unpublished ID is the
    service's 404. A job's answers carry the ID and the three digests."""
    stand_in.configurations[CANDIDATE] = "candidate"
    client = MatsyaClient(stand_in.token, stand_in.url)
    text = "  A household saves.\n"

    started = client.submit_job(source_text=text, target="stage")
    assert started["configuration_id"] == DEFAULT_CONFIGURATION
    assert "configuration_id" not in _sent(stand_in)[-1][2]
    started = client.submit_job(
        source_text=text, target="stage", configuration_id=CANDIDATE, model_key="paper-x",
        source_cluster="paper-x",
    )
    assert started["configuration_id"] == CANDIDATE
    body = _sent(stand_in)[-1][2]
    assert (body["configuration_id"], body["model_key"], body["source_cluster"]) == (
        CANDIDATE, "paper-x", "paper-x",
    )
    job = client.job(started["id"], view="full")
    assert job["configuration_id"] == CANDIDATE
    assert job["request_sha256"] == request_digest(body)
    assert job["source_sha256"] == hashlib.sha256(text.strip().encode()).hexdigest()
    assert job["index_digest"] is None  # queued: no snapshot selected yet
    ended = client.wait_job(started["id"], interval=0)
    assert (ended["configuration_id"], ended["index_digest"]) == (CANDIDATE, DIGEST)
    stand_in.requests.clear()
    for refused in (
        dict(configuration_id="F" * 64),
        dict(configuration_id="abc"),
        dict(model_key="paper-x"),
        dict(source_cluster="paper-x"),
    ):
        with pytest.raises(ValueError):
            client.submit_job(source_text=text, target="stage", **refused)
    assert not stand_in.requests
    with pytest.raises(MatsyaError) as unknown:
        client.submit_job(source_text=text, target="stage", configuration_id="f" * 64)
    assert unknown.value.status == 404

    description = tmp_path / "model.md"
    description.write_text(text, encoding="utf-8")
    kept = client.start_job(description, target="stage", configuration_id=CANDIDATE)
    assert kept["job"]["configuration_id"] == CANDIDATE
    assert _sent(stand_in)[-1][2]["configuration_id"] == CANDIDATE
    kept = client.start_job(description, target="stage", no_session=True)
    assert "configuration_id" not in _sent(stand_in)[-1][2]
    with pytest.raises(ValueError, match="64 lowercase"):
        client.start_job(description, target="stage", configuration_id="abc")

    session = client.new_session("a model")["id"]
    client.add_entry(session, text)
    turn = client.ask(session, "What is a stage?", interval=0, configuration_id=CANDIDATE)
    assert turn["configuration_id"] == CANDIDATE
    assert [request for request in _sent(stand_in) if request[0] == "POST" and request[1].endswith("/turns")][-1][2][
        "configuration_id"
    ] == CANDIDATE
    turn = client.ask(session, JOB_REQUEST, interval=0)
    assert turn["configuration_id"] == DEFAULT_CONFIGURATION
    assert turn["record"]["result"]["job_started"] is not None
    asked = [request for request in _sent(stand_in) if request[0] == "POST" and request[1].endswith("/turns")][-1][2]
    assert "configuration_id" not in asked
    with pytest.raises(ValueError, match="64 lowercase"):
        client.ask(session, "What?", configuration_id="abc")

    # the package wrappers read the user's configuration from the environment
    assert bellman_matsya.submit_job(source_text=text, target="stage", configuration_id=CANDIDATE)[
        "configuration_id"
    ] == CANDIDATE
    assert bellman_matsya.index()["configuration_id"] == DEFAULT_CONFIGURATION

    # the project folder forwards the selector to the job
    folder = tmp_path / "project"
    folder.mkdir()
    (folder / "economics.md").write_text(text, encoding="utf-8")
    project.init(client, folder)
    answer = project.submit(client, folder, configuration_id=CANDIDATE)
    assert answer["job"]["configuration_id"] == CANDIDATE
    submitted = [request for request in _sent(stand_in) if request[1] == "/v1/model-iterations"][-1][2]
    assert submitted["configuration_id"] == CANDIDATE
    answer = project.submit(client, folder)
    submitted = [request for request in _sent(stand_in) if request[1] == "/v1/model-iterations"][-1][2]
    assert "configuration_id" not in submitted

    # the commands
    status, out, _ = run(
        "job", "submit", str(description), "--target", "stage", "--no-session",
        "--configuration-id", CANDIDATE, "--model-key", "paper-x", "--source-cluster", "paper-x",
    )
    assert status == 0
    body = _sent(stand_in)[-1][2]
    assert (body["configuration_id"], body["model_key"]) == (CANDIDATE, "paper-x")
    status, out, _ = run("job", "submit", str(description), "--target", "stage", "--no-session")
    assert status == 0 and "configuration_id" not in _sent(stand_in)[-1][2]
    stand_in.requests.clear()
    for arguments in (
        ("--configuration-id", "abc"),
        ("--model-key", "paper-x"),
        ("--source-cluster", "paper-x"),
    ):
        status, _, err = run("job", "submit", str(description), "--target", "stage", "--no-session", *arguments)
        assert status == 2, arguments
    assert not stand_in.requests
    status, out, _ = run("ask", session, "What is a stage?", "--configuration-id", CANDIDATE, "--interval", "0")
    assert status == 0
    asked = [request for request in _sent(stand_in) if request[0] == "POST" and request[1].endswith("/turns")][-1][2]
    assert asked["configuration_id"] == CANDIDATE
    monkeypatch.chdir(folder)
    status, out, _ = run("project", "submit", "--configuration-id", CANDIDATE)
    assert status == 0
    submitted = [request for request in _sent(stand_in) if request[1] == "/v1/model-iterations"][-1][2]
    assert submitted["configuration_id"] == CANDIDATE
    stand_in.requests.clear()
    status, _, _ = run("project", "submit", "--configuration-id", "abc")
    assert status == 2 and not stand_in.requests


def test_job_retry_keeps_the_submitted_job_options(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A refused job leaves its session entry; the suggested retry retains
    its cycle limit, force choice, configuration and excluded source group."""
    client = MatsyaClient("unused", "https://example.invalid")
    source = tmp_path / "model.md"
    source.write_text("A household saves.\n", encoding="utf-8")
    monkeypatch.setattr(client, "new_session", lambda name: {"id": "session-1"})
    monkeypatch.setattr(client, "add_entry", lambda *args, **kwargs: {"entry": {"number": 1}})
    sent: dict[str, object] = {}

    def refuse_job(**kwargs: object) -> dict[str, object]:
        sent.update(kwargs)
        raise MatsyaError("The service refused max_cycles.", 422)

    monkeypatch.setattr(client, "submit_job", refuse_job)

    with pytest.raises(MatsyaError) as refused:
        client.start_job(
            source, target="period", max_cycles=2, force=True, configuration_id=CANDIDATE,
            model_key="paper-x", source_cluster="paper-x",
        )

    assert sent["configuration_id"] == CANDIDATE
    assert (sent["max_cycles"], sent["force"]) == (2, True)
    assert (sent["model_key"], sent["source_cluster"]) == ("paper-x", "paper-x")
    assert (
        "bellman-matsya job submit --session session-1 --target period "
        f"--max-cycles 2 --force --configuration-id {CANDIDATE} "
        "--model-key paper-x --source-cluster paper-x"
    ) in str(refused.value)


def test_project_rejects_a_malformed_selector_before_appending_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A malformed selector leaves the project's session and saved digest unchanged."""
    client = MatsyaClient("unused", "https://example.invalid")
    monkeypatch.setattr(client, "new_session", lambda name: {"id": "session-1"})
    calls: list[str] = []

    def add_entry(*args: object, **kwargs: object) -> dict[str, object]:
        calls.append("add_entry")
        return {"entry": {"number": 1}}

    monkeypatch.setattr(client, "add_entry", add_entry)
    folder = tmp_path / "project"
    folder.mkdir()
    economics = folder / "economics.md"
    economics.write_text("First description.\n", encoding="utf-8")
    project.init(client, folder)
    project_file = folder / ".bellman-matsya" / "project.json"
    before = project_file.read_bytes()
    calls.clear()
    economics.write_text("Revised description.\n", encoding="utf-8")

    with pytest.raises(ValueError, match="64 lowercase hexadecimal"):
        project.submit(client, folder, configuration_id="bad")

    assert not calls
    assert project_file.read_bytes() == before


# ---------------------------------------------------------------------------
# item 5


def test_item_5_export_writes_the_full_answer_for_any_state(stand_in, run, tmp_path: Path) -> None:
    """`export_job` and `job export` write `job.json`, the full answer of
    `GET /v1/model-iterations/{job}?view=full`, for a job with a record and
    for a cancelled job without one, with the ID and the digests; an
    existing file is refused without `--overwrite`; `--json` prints the
    full answer while the file is written; no temporary file remains; and
    `job files` still writes a model folder."""
    client = MatsyaClient(stand_in.token, stand_in.url)
    started = client.submit_job(source_text="A household saves.", target="stage")
    ended = client.wait_job(started["id"], interval=0)
    folder = tmp_path / "records" / "case-1" / "trial-1"
    answer = client.export_job(started["id"], folder)
    assert _sent(stand_in)[-1][1] == f"/v1/model-iterations/{started['id']}?view=full"
    written = json.loads((folder / "job.json").read_text(encoding="utf-8"))
    assert written == answer
    assert written["configuration_id"] == DEFAULT_CONFIGURATION
    assert written["result"]["versions"] is not None  # the full view, not the products
    assert written["request_sha256"] and written["source_sha256"] and written["index_digest"] == DIGEST
    assert sorted(path.name for path in folder.iterdir()) == ["job.json"]
    with pytest.raises(FileExistsError, match="overwrite"):
        client.export_job(started["id"], folder)
    assert not stand_in.requests
    client.export_job(started["id"], folder, overwrite=True)
    assert sorted(path.name for path in folder.iterdir()) == ["job.json"]

    # a cancelled job: no record, the state, the ID and the digests
    queued = client.submit_job(source_text="A firm hires.", target="stage")
    cancelled = client.cancel_job(queued["id"])
    assert cancelled["state"] == "cancelled"
    status, out, _ = run("job", "export", queued["id"], str(tmp_path / "cancelled"))
    assert status == 0
    assert out.strip() == (
        f"Wrote {tmp_path / 'cancelled' / 'job.json'}: job {queued['id']}, cancelled, "
        f"configuration {DEFAULT_CONFIGURATION}"
    )
    held = json.loads((tmp_path / "cancelled" / "job.json").read_text(encoding="utf-8"))
    assert held["state"] == "cancelled" and "result" not in held
    assert held["configuration_id"] == DEFAULT_CONFIGURATION and held["request_sha256"]
    status, _, err = run("job", "export", queued["id"], str(tmp_path / "cancelled"))
    assert status == 1 and "overwrite" in err
    status, out, _ = run("job", "export", queued["id"], str(tmp_path / "cancelled"), "--overwrite", "--json")
    assert status == 0 and json.loads(out) == held

    # `job files` is unchanged
    paths = client.job_files(started["id"], tmp_path / "model")
    assert (tmp_path / "model" / "record.json") in paths


def test_export_without_overwrite_preserves_a_file_created_during_the_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Another writer's job.json is not replaced after the initial file check."""
    client = MatsyaClient("unused", "https://example.invalid")
    target = tmp_path / "job.json"

    def concurrent_write(job_id: str, view: str = "products") -> dict[str, str]:
        assert (job_id, view) == ("job-1", "full")
        target.write_text("another writer\n", encoding="utf-8")
        return {"id": job_id, "state": "cancelled"}

    monkeypatch.setattr(client, "job", concurrent_write)
    with pytest.raises(FileExistsError, match="overwrite"):
        client.export_job("job-1", tmp_path)

    assert target.read_text(encoding="utf-8") == "another writer\n"
    assert sorted(path.name for path in tmp_path.iterdir()) == ["job.json"]


# ---------------------------------------------------------------------------
# against the service


def test_against_the_service_a_job_under_the_default_id_is_exported_with_its_digest(
    service, tmp_path: Path
) -> None:
    """Against the Matsya service itself: the index names the default's ID,
    a job submitted under that ID ends with its record's configuration
    digest equal to the ID, the exported `job.json` carries the ID, the
    request digest, the source digest and the index digest, and the user,
    who holds no administrator permission, cannot publish."""
    client = MatsyaClient(service.token, service.url)
    status = client.index()
    identity = status["configuration_id"]
    assert identity and status["configuration_version"] == "fixture"
    started = client.submit_job(
        source_text=service.description, target="stage", configuration_id=identity
    )
    assert started["configuration_id"] == identity
    ended = client.wait_job(started["id"], interval=0.05, timeout=60)
    assert ended["state"] == "converged", ended
    exported = client.export_job(started["id"], tmp_path / "export")
    assert exported["configuration_id"] == identity
    assert exported["result"]["versions"]["configuration"]["manifest_sha256"] == identity
    assert exported["request_sha256"] == request_digest(
        {"source": {"kind": "description", "text": service.description}, "target": "stage"}
    )
    assert exported["source_sha256"] == exported["result"]["source"]["sha256"][0]
    assert exported["index_digest"] == exported["result"]["retrieval"]["index_digest"]
    with pytest.raises(MatsyaError) as refused:
        client.publish_configuration(_folder(tmp_path))
    assert refused.value.status == 403
