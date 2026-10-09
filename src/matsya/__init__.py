"""Matsya: the command `matsya` and the Python functions of the Matsya
service of spec 0.3.

Each function below reads the Matsya token and the service address from the
user's configuration file, which `matsya configure` writes, or from the
environment variables MATSYA_TOKEN and MATSYA_SERVER, which override it. It
sends one request; or, for `start_job`, up to three, the session, the entry
and the job; or, for `wait_job` and `ask`, one request every few seconds
until the job or the turn has ended; and returns the service's JSON answer.
`job_files` writes an ended job's model folder and returns the paths it
wrote, and `report_text` composes the folder's report from a job in the
products view without any request (AMD-MAT-010 §§4 and 5). `start_job` and
`submit_job` require the job's target, written `target=`, one of `TARGETS`:
`stage`, `period`, `trellis` or `recipe` (AMD-MAT-011 §3). A paper is sent
as its text, in Markdown or LaTeX, which `paper=True` marks on either
function, and a PDF is refused with `ValueError` before any request
(AMD-MAT-012 §2). `MatsyaClient` takes an explicit Matsya token and service
address instead, and holds the same operations as methods.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from matsya.client import (
    TARGETS,
    AuthenticationError,
    ContextTooLargeError,
    MatsyaClient,
    MatsyaError,
    RateLimitError,
    ServerError,
    report_text,
)
from matsya.config import ConfigurationError, load_config

__version__ = "0.8.0"

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
    "index",
    "job",
    "job_files",
    "new_session",
    "passage",
    "report_text",
    "search",
    "select_job",
    "session",
    "start_job",
    "submit_job",
    "wait_job",
]


def _make_client() -> MatsyaClient:
    """A client with the configured Matsya token and service address."""
    cfg = load_config()
    if not cfg["token"]:
        raise ConfigurationError(
            "No Matsya token is configured. Run matsya configure, or set the "
            "environment variable MATSYA_TOKEN."
        )
    return MatsyaClient(token=cfg["token"], server_url=cfg["server"])


def index() -> dict[str, Any]:
    """The retrieval index and configuration the service reads
    (`GET /v1/index`; `MatsyaClient.index`)."""
    return _make_client().index()


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
) -> dict[str, Any]:
    """Start a job of architect mode from a file at the target `target`, as
    `matsya job submit <file> --target <target>` does: a Markdown, LaTeX or
    plain-text file becomes one entry of a new session named after the
    file, or `name`, or of the existing `session`, of the kind `user`, a
    description, or with `paper=True` of the kind `paper`, as `--paper`
    marks it, and the job starts from that session; `no_session` sends the
    text as the job's source with no session. A PDF is refused with
    `ValueError` before any request. `target` is required: the level of the
    declaration the job returns, `stage`, `period`, `trellis` or `recipe`.
    Returns the service's answers as ``{"session": ..., "entry": ...,
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
    )


def submit_job(
    source_text: str | None = None,
    max_cycles: int | None = None,
    session: str | None = None,
    force: bool | None = None,
    *,
    target: str,
    paper: bool = False,
) -> dict[str, Any]:
    """Start a job of architect mode from a description's text, a paper's
    text with `paper=True`, or a session, at the target `target`, which is
    required: `stage`, `period`, `trellis` or `recipe`
    (`POST /v1/model-iterations`; `MatsyaClient.submit_job`)."""
    return _make_client().submit_job(
        source_text=source_text,
        max_cycles=max_cycles,
        session=session,
        force=force,
        target=target,
        paper=paper,
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
) -> dict[str, Any]:
    """Ask one question in a session and return the turn once it has ended
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
    )
