"""Matsya: the command `bellman-matsya` and the Python functions of the Matsya
service of spec 0.3.

Each function below reads the Matsya token from the user's configuration file,
which `bellman-matsya configure` writes, or from BELLMAN_MATSYA_TOKEN. It uses
BELLMAN_MATSYA_SERVER, a saved service address, or the built-in Bellman address,
in that order. Most operations send one request. `start_job` can send three:
the session, entry and job requests. `wait_job` and `ask` send requests every
few seconds until the job or turn ends. Each operation returns the service's
JSON answer.
`job_files` writes an ended job's model folder and returns the paths it
wrote, and `report_text` composes the folder's report from a job in the
products view without any request (AMD-MAT-010 §§4 and 5). `start_job` and
`submit_job` require the job's target, written `target=`, one of `TARGETS`:
`stage`, `period`, `trellis` or `recipe` (AMD-MAT-011 §3). A paper is sent
as its text, in Markdown or LaTeX, which `paper=True` marks on either
function, and a PDF is refused with `ValueError` before any request
(AMD-MAT-012 §2). A job or a turn names a published configuration with
`configuration_id`, or takes the service's default; `export_job` saves a
job's full answer as `job.json`; `publish_configuration` and
`set_default_configuration` are the administrator's operations
(AMD-MAT-020 §§2–3). `MatsyaClient` takes an explicit Matsya token and
service address instead, and holds the same operations as methods. The module
`bellman_matsya.project` holds the four commands of a project folder, a model
folder that remembers its session (AMD-MAT-013 §3): `init`, `submit`,
`status` and `pull`, each called with a `MatsyaClient` and the folder.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from bellman_matsya.client import (
    TARGETS,
    AuthenticationError,
    ContextTooLargeError,
    MatsyaClient,
    MatsyaError,
    RateLimitError,
    ServerError,
    report_text,
)
from bellman_matsya.config import ConfigurationError, load_config

__version__ = "0.11.1"

__all__ = [
    "TARGETS",
    "AuthenticationError",
    "ConfigurationError",
    "ContextTooLargeError",
    "MatsyaClient",
    "MatsyaError",
    "RateLimitError",
    "ServerError",
    "add_entry",
    "ask",
    "cancel_job",
    "export_job",
    "index",
    "job",
    "job_files",
    "new_session",
    "passage",
    "publish_configuration",
    "report_text",
    "search",
    "select_job",
    "session",
    "set_default_configuration",
    "start_job",
    "submit_job",
    "wait_job",
]


def _make_client() -> MatsyaClient:
    """A client with the configured Matsya token and service address."""
    cfg = load_config()
    if not cfg["token"]:
        raise ConfigurationError(
            "No Matsya token is configured. Run bellman-matsya configure, or set the "
            "environment variable BELLMAN_MATSYA_TOKEN."
        )
    return MatsyaClient(token=cfg["token"], server_url=cfg["server"])


def index() -> dict[str, Any]:
    """The retrieval index the service reads and its default configuration's
    ID and version (`GET /v1/index`; `MatsyaClient.index`)."""
    return _make_client().index()


def publish_configuration(folder: str | Path) -> dict[str, Any]:
    """Publish a checked configuration folder as a ZIP archive and return
    its ID and version; an administrator's operation
    (`POST /v1/configurations`; `MatsyaClient.publish_configuration`)."""
    return _make_client().publish_configuration(folder)


def set_default_configuration(configuration_id: str) -> dict[str, Any]:
    """Make a published configuration the default and return the former and
    the new ID with the version; an administrator's operation
    (`PUT /v1/configurations/default`;
    `MatsyaClient.set_default_configuration`)."""
    return _make_client().set_default_configuration(configuration_id)


def search(
    query: str,
    limit: int | None = None,
    collections: list[str] | None = None,
    source_ids: list[str] | None = None,
    boosts: dict[str, float] | None = None,
) -> dict[str, Any]:
    """The passages of the index that best match `query`
    (`POST /v1/search`; `MatsyaClient.search`)."""
    return _make_client().search(
        query, limit=limit, collections=collections, source_ids=source_ids, boosts=boosts
    )


def passage(passage_id: str, index_digest: str | None = None) -> dict[str, Any]:
    """One passage of the index (`GET /v1/passages/{passage_id}`;
    `MatsyaClient.passage`)."""
    return _make_client().passage(passage_id, index_digest=index_digest)


def start_job(
    path: str | Path,
    name: str | None = None,
    session: str | None = None,
    no_session: bool = False,
    max_cycles: int | None = None,
    force: bool | None = None,
    *,
    target: str,
    paper: bool = False,
    configuration_id: str | None = None,
    model_key: str | None = None,
    source_cluster: str | None = None,
) -> dict[str, Any]:
    """Start a job of architect mode from a file at the target `target`, as
    `bellman-matsya job submit <file> --target <target>` does: a Markdown, LaTeX or
    plain-text file becomes one entry of a new session named after the
    file, or `name`, or of the existing `session`, of the kind `user`, a
    description, or with `paper=True` of the kind `paper`, as `--paper`
    marks it, and the job starts from that session; `no_session` sends the
    text as the job's source with no session. A PDF is refused with
    `ValueError` before any request. `target` is required: the level of the
    declaration the job returns, `stage`, `period`, `trellis` or `recipe`.
    `configuration_id` names a published configuration, or the default is
    taken; `model_key` and `source_cluster` are given together or not at
    all. Returns the service's answers as ``{"session": ..., "entry": ...,
    "job": ...}`` (`MatsyaClient.start_job`)."""
    return _make_client().start_job(
        path,
        name=name,
        session=session,
        no_session=no_session,
        max_cycles=max_cycles,
        force=force,
        target=target,
        paper=paper,
        configuration_id=configuration_id,
        model_key=model_key,
        source_cluster=source_cluster,
    )


def submit_job(
    source_text: str | None = None,
    max_cycles: int | None = None,
    session: str | None = None,
    force: bool | None = None,
    *,
    target: str,
    paper: bool = False,
    starting_declaration: dict[str, str] | None = None,
    configuration_id: str | None = None,
    model_key: str | None = None,
    source_cluster: str | None = None,
) -> dict[str, Any]:
    """Start a job of architect mode from a description's text, a paper's
    text with `paper=True`, or a session, at the target `target`, which is
    required: `stage`, `period`, `trellis` or `recipe`; with
    `starting_declaration`, the files the job's first cycle starts from,
    by their names in a declaration, such as `example.bl`; with
    `configuration_id`, under a published configuration, else the default;
    and with `model_key` and `source_cluster`, a pair given together, the
    job's own source cluster excluded from what it reads
    (`POST /v1/model-iterations`; `MatsyaClient.submit_job`)."""
    return _make_client().submit_job(
        source_text=source_text,
        max_cycles=max_cycles,
        session=session,
        force=force,
        target=target,
        paper=paper,
        starting_declaration=starting_declaration,
        configuration_id=configuration_id,
        model_key=model_key,
        source_cluster=source_cluster,
    )


def job(job_id: str, view: str = "products") -> dict[str, Any]:
    """A job's state and, once it has ended, its record in the view `view`:
    `products`, the default, its final products and the material of its
    report, or `full`, the record as the service keeps it
    (`GET /v1/model-iterations/{job_id}?view=...`; `MatsyaClient.job`)."""
    return _make_client().job(job_id, view=view)


def wait_job(
    job_id: str,
    interval: float = 5,
    on_change: Callable[[dict[str, Any]], None] | None = None,
    timeout: float | None = None,
) -> dict[str, Any]:
    """Wait until a job has ended and return the service's last answer on it
    (`MatsyaClient.wait_job`)."""
    return _make_client().wait_job(job_id, interval=interval, on_change=on_change, timeout=timeout)


def cancel_job(job_id: str) -> dict[str, Any]:
    """Cancel a queued or running job, and return the job: `cancelled`, or
    `running` with `cancel_requested` true; a job that has ended raises
    `MatsyaError` with status 409 (`POST /v1/model-iterations/{job_id}/cancel`;
    `MatsyaClient.cancel_job`)."""
    return _make_client().cancel_job(job_id)


def export_job(job_id: str, folder: str | Path, *, overwrite: bool = False) -> dict[str, Any]:
    """Save a job's full answer as `job.json` in `folder`, for any state of
    the job, and return that answer; an existing file is refused unless
    `overwrite` is true (`GET /v1/model-iterations/{job_id}?view=full`;
    `MatsyaClient.export_job`)."""
    return _make_client().export_job(job_id, folder, overwrite=overwrite)


def job_files(
    job_id: str, folder: str | Path, overwrite: bool = False, all_iterates: bool = False
) -> list[Path]:
    """Write an ended job's model folder into `folder`, new or empty unless
    `overwrite` is true: `economics.md`, `report.md`, the stage files under
    `declaration/` and `record.json`, and with `all_iterates` every cycle
    under `iterates/` with the full record; return the paths written
    (`MatsyaClient.job_files`)."""
    return _make_client().job_files(
        job_id, folder, overwrite=overwrite, all_iterates=all_iterates
    )


def new_session(name: str) -> dict[str, Any]:
    """A new session of this name (`POST /v1/sessions`;
    `MatsyaClient.new_session`)."""
    return _make_client().new_session(name)


def add_entry(
    session_id: str,
    text: str | None,
    kind: str = "user",
    replies_to: int | None = None,
    delivery_id: str | None = None,
) -> dict[str, Any]:
    """Append one entry to a session (`POST /v1/sessions/{session_id}/entries`;
    `MatsyaClient.add_entry`)."""
    return _make_client().add_entry(
        session_id, text, kind=kind, replies_to=replies_to, delivery_id=delivery_id
    )


def session(session_id: str) -> dict[str, Any]:
    """A session's entries, revision, selected job, jobs with their labels
    and turns (`GET /v1/sessions/{session_id}`; `MatsyaClient.session`)."""
    return _make_client().session(session_id)


def select_job(session_id: str, job_id: str | None) -> dict[str, Any]:
    """Select the job of a session whose outputs its questions read, or
    clear the selection with `None`, and return the session's listing
    (`POST /v1/sessions/{session_id}/selected-job`;
    `MatsyaClient.select_job`)."""
    return _make_client().select_job(session_id, job_id)


def ask(
    session_id: str,
    question: str,
    stage_file_path: str | Path | None = None,
    index_digest: str | None = None,
    delivery_id: str | None = None,
    interval: float = 2,
    on_change: Callable[[dict[str, Any]], None] | None = None,
    timeout: float | None = None,
    configuration_id: str | None = None,
) -> dict[str, Any]:
    """Ask one question in a session and return the turn once it has ended;
    `configuration_id` names the published configuration whose
    conversation role answers, else the default
    (`POST /v1/sessions/{session_id}/turns`, then
    `GET /v1/sessions/{session_id}/turns/{turn_id}`; `MatsyaClient.ask`)."""
    return _make_client().ask(
        session_id,
        question,
        stage_file_path=stage_file_path,
        index_digest=index_digest,
        delivery_id=delivery_id,
        interval=interval,
        on_change=on_change,
        timeout=timeout,
        configuration_id=configuration_id,
    )
