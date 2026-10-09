"""The fixtures of the client's tests.

The package's source is put first on the import path, so that the tests read
it whether or not the package is installed. `stand_in` starts a stand-in of
the Matsya service of spec 0.3 on the loopback address, which answers each
route with the form of `packages/matsya/matsya_service/api.py`; its jobs end
with the records of this module, which a job returns in the products view by
default and whole with `view=full` (AMD-MAT-010 §3), and `products_of`
reduces a record as the service's `products_view` does. `service`
starts the Matsya service itself under the test configuration of
`packages/matsya/tests/fixtures/`, with a scripted caller in place of the
model provider, on the loopback address; it is skipped where the service
package, uvicorn or those tests are absent. No test reaches another address
or calls a model provider, and none reads the user's own configuration file.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
import shutil
import socket
import sqlite3
import sys
import threading
import time
import urllib.parse
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from matsya import config  # noqa: E402

TOKEN = "msy_" + "0123456789abcdef" * 2
DIGEST = "d" * 64
NOW = "2026-10-09T12:00:00+00:00"
# the service's own tests and their configuration, in this checkout
SERVICE_TESTS = Path(__file__).resolve().parents[4] / "packages" / "matsya" / "tests"

PASSAGE = {
    "passage_id": "5" * 64,
    "corpus": "repository",
    "access": "public",
    "source_id": "repository:docs/Bellman-Sym/01-stage",
    "path": "docs/Bellman-Sym/01-stage.md",
    "kind": "markdown",
    "authority": "primary",
    "title": None,
    "location": {
        "page": None,
        "page_basis": None,
        "printed_page_label": None,
        "heading": "The stage",
        "line_start": 3,
        "line_end": 3,
        "char_start": 13,
        "char_end": 109,
        "section": "the-stage",
    },
    "text": "A stage file names its arrival, decision and continuation fields, its laws and its policy block.",
    "passage_sha256": "6" * 64,
    "index_digest": DIGEST,
    "score": 0.712345678,
}
STAGE = """@stage: example
[id=arvl_to_dcsn, (x : ℝ) : !arvl -> (x_d : ℝ) : !dcsn] {
 x_d = x
}
"""
QUESTION = "What is the distribution of the income shock y?"
CITATION = {
    "quote": "A stage file names its arrival, decision and continuation fields",
    "identity": {"source": "index", "target": "passage:" + PASSAGE["passage_id"]},
    "path": PASSAGE["path"],
    "heading": "The stage",
    "location": PASSAGE["location"],
    "authority": "primary",
    "index_digest": DIGEST,
}
ANSWER = "A stage file names its fields and its laws [1]."
# the answer of a turn whose question asks for a job, and the words by which
# the stand-in recognizes such a question (AMD-MAT-009 §3)
JOB_ANSWER = "A job of architect mode is being started from this session's text."
JOB_REQUEST = "submit this as a job"
# the routes of spec 0.3 §3, as `api.py` declares them
ROUTES = (
    ("GET", r"/v1/index", "index"),
    ("POST", r"/v1/search", "search"),
    ("GET", r"/v1/passages/(?P<passage_id>[^/]+)", "passage"),
    ("POST", r"/v1/sessions", "new_session"),
    ("GET", r"/v1/sessions/(?P<session_id>[^/]+)", "session"),
    ("POST", r"/v1/sessions/(?P<session_id>[^/]+)/entries", "add_entry"),
    ("POST", r"/v1/sessions/(?P<session_id>[^/]+)/selected-job", "select"),
    ("POST", r"/v1/sessions/(?P<session_id>[^/]+)/turns", "ask"),
    ("GET", r"/v1/sessions/(?P<session_id>[^/]+)/turns/(?P<turn_id>[^/]+)", "turn"),
    ("POST", r"/v1/model-iterations", "submit"),
    ("GET", r"/v1/model-iterations/(?P<job_id>[^/]+)", "job"),
    ("POST", r"/v1/model-iterations/(?P<job_id>[^/]+)/cancel", "cancel"),
)
# the keys of a job's label (AMD-MAT-008 §2), the states in which a job has
# ended and those in which it holds a record (AMD-MAT-008 §4)
LABEL_KEYS = ("model", "revision", "number", "state", "overtaken", "text")
JOB_ENDED = ("converged", "not_converged", "needs_input", "cancelled", "failed", "interrupted")
RECORD_STATES = ("converged", "not_converged", "needs_input", "cancelled")
JOB_FIELDS = {
    "source",
    "max_cycles",
    "starting_declaration",
    "model_key",
    "source_cluster",
    "target_formulation",
    "session",
    "force",
}
TURN_FIELDS = {"question", "stage_file", "refusal", "timing", "package_version", "index_digest", "delivery_id"}
# the most cycles a job request may name, `cycle_maximum` of the service's
# configuration
CYCLE_MAXIMUM = 5


# ---------------------------------------------------------------------------
# the records with which the stand-in's jobs end, in the form of the
# service's record `matsya-model-iteration/5` (REQ-MAT-034)

PREPARER = "SourceMaterial_to_BellmanStageProse"
WRITER = "BellmanStageProse_to_BellmanSYMDeclaration"
PROSE = "ElaboratedSemanticObject_to_BellmanStageProse"
JUDGE = "BellmanStageProse_judge"
JUDGE_ITEMS = (
    "state space",
    "timing and information",
    "shocks",
    "transitions",
    "payoff and aggregator",
    "constraints",
    "recursion",
    "optimality condition",
    "terminal or boundary condition",
    "parameters",
)
OBSERVED = "The agent observes x before choosing u."
OMITTED = "The continuation state a equals x_d plus the two components of u."
SHOCK = "Labor income is subject to a permanent and a transitory shock."
MODEL_PROSE = (
    "## States\n"
    f"The arrival state is x, and the decision state x_d equals it. {OBSERVED}\n\n"
    "## Laws of motion\n"
    f"{OMITTED}\n"
)
ROUND_TRIP_PROSE = (
    "## States\n"
    "The arrival state is x, and the decision state x_d equals it.\n\n"
    "## Laws of motion\n"
    "The continuation state a equals x_d plus the first component of u.\n"
)
NOTE = "The timing of the second control is left open.\n"
METHODS = "policy: !egm\n"
FIRST_STAGE = STAGE.replace("x_d = x\n", "x_d = x + 1\n")
ROUND_TRIP_STAGE = STAGE.replace("x_d = x\n", "x_d = 2 * x\n")
# the files of a model of two stages, with the period, trellis, calibration,
# settings and methods files a later writer may return
TRELLIS_FILES = {
    "household.bl": STAGE.replace("@stage: example", "@stage: household"),
    "firm.bl": STAGE.replace("@stage: example", "@stage: firm"),
    "period.yml": "!period\nname: year\nstages:\n  - household\n  - firm\n",
    "trellis.yml": "!trellis\ntemplate: period.yml\n",
    "calibration/base.yml": "β: 0.96\n",
    "settings/base.yml": "n_a: 50\n",
    "stages/household/methods.yml": METHODS,
    "note.md": "The wage w is taken as given.\n",
}
REFUSAL = {
    "call": 5,
    "role": PROSE,
    "condition": "job_input_tokens",
    "charged": 40,
    "would_add": 120,
    "ceiling": 100,
}


def judge_report(differences: dict | None = None, form_passed: bool = True) -> dict:
    """One reading of a judge: the ten headings in agreement but those of
    `differences`, each `(omissions, additions, contradictions, quotes)`."""
    items = {
        item: {"omissions": 0, "additions": 0, "contradictions": 0, "agrees": True, "quotes": []}
        for item in JUDGE_ITEMS
    }
    for item, (omissions, additions, contradictions, quotes) in (differences or {}).items():
        items[item] = {
            "omissions": omissions,
            "additions": additions,
            "contradictions": contradictions,
            "agrees": False,
            "quotes": list(quotes),
        }
    return {"form": {"passed": form_passed}, "items": items}


def judged(*reports: dict) -> dict:
    """A judge's record: its readings in the two orders of the texts, and
    whether every heading of both agrees."""
    agrees = all(
        report["form"]["passed"] and all(item["agrees"] for item in report["items"].values())
        for report in reports
    )
    return {"agrees": agrees, "reports": list(reports)}


AGREEING = judged(judge_report(), judge_report())
DISAGREEING = judged(
    judge_report({"transitions": (1, 0, 0, [OMITTED])}),
    judge_report({"timing and information": (0, 0, 1, [OBSERVED])}),
)


def first_difference(left: str, right: str) -> dict:
    """The first difference of a comparison profile of one stage."""
    return {
        "kind": "kernels",
        "key": "kernel:arvl_to_dcsn.1",
        "right_key": "kernel:arvl_to_dcsn.1",
        "outcome": "differ",
        "left": left,
        "right": right,
        "stage": 4,
        "witness": {"point": {"x": 0.5}, "left": 0.5, "right": 1.0, "member": 0},
    }


def cycle_record(number: int, files: dict, *, judging: dict, round_trip: dict, difference, note_open: bool) -> dict:
    """One cycle of a record: its writing, its round-trip prose, its judging,
    its reconstruction, its comparison and its two checks."""
    return {
        "number": number,
        "writing": {
            "rounds": [{"number": 1, "status": "elaborated"}],
            "files": files,
            "citations": [{"file": "example.bl", "block": "arvl_to_dcsn", "sentences": []}],
            "digest": str(number) * 64,
        },
        "prose_writing": {
            "description": MODEL_PROSE if difference is None else ROUND_TRIP_PROSE,
            "form": {"passed": True, "findings": [], "words": 41},
        },
        "judging": judging,
        "reconstruction": {
            "rounds": [{"number": 1, "status": "elaborated"}],
            "files": round_trip,
            "digest": "f" * 64,
        },
        "comparison": {
            "equal": difference is None,
            "profile": {
                "verdict": "equal" if difference is None else "differ",
                "outcomes": [],
                "first_difference": difference,
            },
        },
        "citations_supported": True,
        "unresolved_note": note_open,
    }


def usage_record(calls: dict[str, int], refusal: dict | None = None) -> dict:
    """The language-model token ledger of a job whose every call is charged
    10 input and 5 output tokens."""
    listed = []
    for role, count in calls.items():
        for _ in range(count):
            listed.append(
                {"number": len(listed) + 1, "role": role, "prompt_sha256": "0" * 64, "count": 100}
            )
    roles = {
        role: {"input_tokens": 10 * calls.get(role, 0), "output_tokens": 5 * calls.get(role, 0)}
        for role in (PREPARER, WRITER, PROSE, JUDGE, "distribution_check")
    }
    total = {
        "input_tokens": sum(held["input_tokens"] for held in roles.values()),
        "output_tokens": sum(held["output_tokens"] for held in roles.values()),
    }
    return {
        "counter": "stand-in",
        "ceilings": {"job": {"input_tokens": 100000, "output_tokens": 50000}},
        "calls": listed,
        "charged": {"job": total, "roles": roles},
        "refusal": refusal,
    }


def job_record(status: str, reason: str, cycles: list, **fields) -> dict:
    """A finished job's record of a typed description, with the fields given."""
    return {
        "schema": "matsya-model-iteration/5",
        "target_formulation": None,
        "source": {"kind": "description", "sha256": "1" * 64},
        "session": None,
        "versions": {"configuration": {"version": "0.3.7"}},
        "retrieval": {"index_digest": DIGEST},
        "continues": None,
        "calls": [{"step": "writing", "cycle": 1, "role": WRITER}],
        "cycles": cycles,
        "description": MODEL_PROSE,
        "page_references": [],
        "paper_source_check": AGREEING,
        "paper_form_check": {"passed": True, "findings": [], "words": 41},
        "status": status,
        "reason": reason,
        "files": cycles[-1]["writing"]["files"] if cycles else {},
        "reading": {
            "index_digest": DIGEST,
            "guides": {"calculus": "c" * 64, "writer": "a" * 64},
            "invocations": [{"role": WRITER, "step": "writing", "cycle": 1}],
            "allowed_sources": [["repository", "public"]],
        },
        "usage": usage_record({PREPARER: 1, WRITER: 4, PROSE: 2, JUDGE: 6}),
        **fields,
    }


FIRST_CYCLE = cycle_record(
    1,
    {"example.bl": FIRST_STAGE, "note.md": NOTE},
    judging=judged(judge_report({"transitions": (1, 0, 0, [OMITTED])}), judge_report()),
    round_trip={"example.bl": ROUND_TRIP_STAGE},
    difference=first_difference("x_d = (x + 1)", "x_d = (2 * x)"),
    note_open=True,
)
# the records with which the stand-in's jobs end, by the names a test gives
# `StandIn.next_ends`: a job of two cycles that converges in its second, one
# of two cycles that reaches its cycle limit with an omission and a
# contradiction of the prose-roundtrip-judge, a round-trip difference and a
# note left open, a job that asks a question, a cancelled job, a paper whose
# model prose the prose-source-judge finds to differ from it, a model of two
# stages whose job a language-model token ceiling stopped after its first
# writing, and a record naming a file outside the folder
RECORDS = {
    "converged": job_record(
        "converged",
        "source_agreement_and_semantic_fixed_point",
        [
            FIRST_CYCLE,
            cycle_record(
                2,
                {"example.bl": STAGE, "note.md": "none\n"},
                judging=AGREEING,
                round_trip={"example.bl": STAGE},
                difference=None,
                note_open=False,
            ),
        ],
        artifacts={"economics.md": MODEL_PROSE, "declaration/stages/example/example.bl": STAGE},
    ),
    "not_converged": job_record(
        "not_converged",
        "cycle_limit_reached",
        [
            FIRST_CYCLE,
            cycle_record(
                2,
                {"example.bl": STAGE, "methods.yml": METHODS, "note.md": NOTE},
                judging=DISAGREEING,
                round_trip={"example.bl": ROUND_TRIP_STAGE},
                difference=first_difference("x_d = x", "x_d = (2 * x)"),
                note_open=True,
            ),
        ],
    ),
    "needs_input": {
        "schema": "matsya-model-iteration/5",
        "status": "needs_input",
        "reason": "distribution_needs_specification",
        "questions": [QUESTION],
        "cycles": [],
    },
    "cancelled": {
        "schema": "matsya-model-iteration/5",
        "status": "cancelled",
        "reason": "cancelled_by_user",
        "cycles": [],
        "usage": {"calls": []},
    },
    "paper": job_record(
        "not_converged",
        "paper_description_differs_from_source",
        [],
        source={"kind": "paper", "sha256": "2" * 64, "pages": 12, "page_basis": "pdf"},
        paper_source_check=judged(
            judge_report({"shocks": (1, 0, 0, [SHOCK])}),
            judge_report({"shocks": (0, 1, 0, [SHOCK])}),
        ),
        usage=usage_record({PREPARER: 1, JUDGE: 2}),
    ),
    "trellis": job_record(
        "not_converged",
        "token_ceiling_reached",
        [
            {
                "number": 1,
                "writing": {"rounds": [], "files": TRELLIS_FILES, "citations": [], "digest": "9" * 64},
                "citations_supported": False,
                "unresolved_note": True,
            }
        ],
        usage=usage_record({PREPARER: 1, JUDGE: 2, WRITER: 1}, REFUSAL),
    ),
    "outside": job_record(
        "not_converged",
        "cycle_limit_reached",
        [
            cycle_record(
                1,
                {"example.bl": STAGE, "../outside.bl": STAGE, "note.md": NOTE},
                judging=AGREEING,
                round_trip={"example.bl": STAGE},
                difference=None,
                note_open=True,
            )
        ],
    ),
}
PRODUCT_FIELDS = ("status", "reason", "description", "questions", "paper_source_check", "paper_form_check")


def products_of(record: dict) -> dict:
    """The products view of a record, reduced as `products_view` of the
    service's `processor.py` reduces it (AMD-MAT-010 §3) for the records of
    this module, whose comparison profiles are those of one stage; a test
    compares the two on every record of `RECORDS`."""
    cycles = record.get("cycles") if isinstance(record.get("cycles"), list) else []
    view = {key: copy.deepcopy(record[key]) for key in PRODUCT_FIELDS if key in record}
    view["cycles_run"] = len(cycles)
    view["last_cycle"] = None
    if cycles:
        held = cycles[-1]
        writing, comparison = held.get("writing"), held.get("comparison")
        profile = comparison.get("profile") if isinstance(comparison, dict) else None
        view["last_cycle"] = {
            "files": copy.deepcopy(writing.get("files")) if isinstance(writing, dict) else None,
            "judging": copy.deepcopy(held.get("judging")),
            "comparison": (
                {
                    "equal": comparison.get("equal"),
                    "first_difference": (
                        copy.deepcopy(profile.get("first_difference")) if isinstance(profile, dict) else None
                    ),
                }
                if isinstance(comparison, dict)
                else None
            ),
            "citations_supported": held.get("citations_supported"),
            "unresolved_note": held.get("unresolved_note"),
        }
    reading = record.get("reading")
    if isinstance(reading, dict):
        view["reading"] = {key: copy.deepcopy(reading[key]) for key in ("index_digest", "guides") if key in reading}
    usage = record.get("usage")
    if isinstance(usage, dict):
        charged = usage.get("charged")
        roles = charged.get("roles") if isinstance(charged, dict) else None
        calls_by_role = dict.fromkeys(roles if isinstance(roles, dict) else (), 0)
        for call in usage.get("calls") or []:
            if isinstance(call, dict) and isinstance(call.get("role"), str):
                calls_by_role[call["role"]] = calls_by_role.get(call["role"], 0) + 1
        view["usage"] = {
            "charged": copy.deepcopy(charged),
            "calls_by_role": calls_by_role,
            "refusal": copy.deepcopy(usage.get("refusal")),
        }
    return view


class _Handler(BaseHTTPRequestHandler):
    """One request to the stand-in, answered by `StandIn.answer`."""

    def log_message(self, format: str, *args: object) -> None:
        """The tests print no request log."""

    def do_GET(self) -> None:
        self._answer("GET")

    def do_POST(self) -> None:
        self._answer("POST")

    def _answer(self, method: str) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        try:
            body = json.loads(raw) if raw else None
        except ValueError:
            body = None
        status, text = self.server.stand_in.answer(method, self.path, dict(self.headers), body)
        data = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class StandIn:
    """A stand-in of the Matsya service of spec 0.3 on the loopback address.

    It answers each route of `ROUTES` with the form of `api.py` and
    `jobs.py`; holds sessions in memory; takes a job and a turn through
    `queued` and `running` to their end, one state per request for its
    state, a job's present state being the state its latest such request
    returned, or `queued` before the first; and keeps every request
    (`requests`: method, path with its query, headers and JSON body) and the
    text of every answer (`answers`). A job ends with a record of `RECORDS`:
    a job from a session `needs_input`, which, when it is current at its
    end, appends its question to the session, and any other job
    `converged`, unless `next_ends` names the record of the next job
    submitted. A reply to that question starts a job that converges. A job's
    record is returned in the products view, or whole with `view=full`
    (AMD-MAT-010 §3). A question that asks for a job (`JOB_REQUEST`) starts
    one from the session, whose version is the session's revision with the
    question, and the turn's result names it under `job_started`
    (AMD-MAT-009 §3); any other turn's `job_started` is null. A job of a session carries
    the label of AMD-MAT-008 §2, its version the session's revision when it
    first runs; the session's listing gives its jobs as records with their
    labels and its selected job. The
    cancel route cancels a queued job at once, marks a running one, which
    then ends `cancelled` with a record, and refuses an ended one with 409;
    the selection route takes a job of the session that holds a record, or
    `null`. A turn's result names, as `job`, the session's selected job or
    else its latest current job that holds a record. A session's name of
    more than 200 characters and a `max_cycles` outside 1 to
    `CYCLE_MAXIMUM` are refused, as the service refuses them. With
    `echo_token` true, a refused Matsya token is repeated in the refusal's
    message, as a careless proxy might repeat it.
    """

    def __init__(self, token: str) -> None:
        self.token = token
        self.echo_token = False
        self.requests: list[dict[str, Any]] = []
        self.answers: list[str] = []
        self.sessions: dict[str, dict[str, Any]] = {}
        self.jobs: dict[str, dict[str, Any]] = {}
        self.turns: dict[str, list[dict[str, Any]]] = {}
        self.ended: set[str] = set()
        # the names of `RECORDS` with which the next jobs submitted end
        self.next_ends: list[str] = []
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self.server.stand_in = self
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.thread = threading.Thread(
            target=self.server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True
        )

    def start(self) -> None:
        self.thread.start()

    def stop(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(5)

    def answer(
        self, method: str, target: str, headers: dict[str, str], body: Any
    ) -> tuple[int, str]:
        self.requests.append({"method": method, "path": target, "headers": headers, "body": body})
        split = urllib.parse.urlsplit(target)
        status, payload = self._route(
            method, split.path, headers.get("Authorization", ""), body, split.query
        )
        text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        self.answers.append(text)
        return status, text

    def _route(
        self, method: str, path: str, authorization: str, body: Any, query: str = ""
    ) -> tuple[int, Any]:
        if (method, path) == ("GET", "/healthz"):
            return 200, {"status": "ok"}
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token.strip():
            return 401, {"detail": "A Matsya bearer token is required"}
        if token.strip() != self.token:
            detail = "The Matsya bearer token is invalid"
            return 401, {"detail": f"{detail}: {token.strip()}" if self.echo_token else detail}
        for verb, pattern, name in ROUTES:
            found = re.fullmatch(pattern, path)
            if verb == method and found:
                arguments = found.groupdict()
                if name == "job":
                    arguments["query"] = dict(urllib.parse.parse_qsl(query))
                return getattr(self, "_" + name)(body, **arguments)
        return 404, {"detail": "Not Found"}

    # -- the index

    def _index(self, body: Any) -> tuple[int, Any]:
        return 200, {
            "index_digest": DIGEST,
            "embedding_model_id": "stand-in-embedding-v1",
            "configuration_version": "0.3.5",
        }

    def _search(self, body: Any) -> tuple[int, Any]:
        if not isinstance(body, dict) or set(body) - {"query", "collections", "limit", "source_ids", "boosts"}:
            return 422, {"detail": "Unknown search field"}
        limit = body.get("limit", 8)
        if type(limit) is not int or not 1 <= limit <= 20:
            return 422, {"detail": "Search limit must be from 1 to 20"}
        return 200, {"index_digest": DIGEST, "passages": [PASSAGE][:limit]}

    def _passage(self, body: Any, passage_id: str) -> tuple[int, Any]:
        if passage_id != PASSAGE["passage_id"]:
            return 404, {"detail": "Passage not found"}
        return 200, PASSAGE

    # -- sessions and turns

    def _listing(self, session_id: str) -> dict[str, Any]:
        """A session as the service lists it: its jobs as records
        `{"id", "state", "revision", "current", "label"}` in the order they
        were created."""
        held = self.sessions[session_id]
        jobs = []
        for job_id in held["jobs"]:
            job = self.jobs[job_id]
            state = self._present(job)["state"]
            jobs.append(
                {
                    "id": job_id,
                    "state": state,
                    "revision": job["revision"],
                    "current": job["current"],
                    "label": self._label(job_id, state),
                }
            )
        return {**held, "jobs": jobs}

    def _new_session(self, body: Any) -> tuple[int, Any]:
        name = body.get("name") if isinstance(body, dict) else None
        if set(body or {}) != {"name"} or not isinstance(name, str) or not name.strip():
            return 422, {"detail": "A session needs a name and nothing else"}
        if len(name) > 200:
            return 422, {"detail": "A session's name has at most 200 characters"}
        session_id = uuid.uuid4().hex
        self.sessions[session_id] = {
            "id": session_id,
            "name": name.strip(),
            "entries": [],
            "revision": 0,
            "awaiting_answer": None,
            "selected_job": None,
            "jobs": [],
            "turns": [],
            "created_at": NOW,
            "updated_at": NOW,
        }
        return 201, self._listing(session_id)

    def _session(self, body: Any, session_id: str) -> tuple[int, Any]:
        if session_id not in self.sessions:
            return 404, {"detail": "Session not found"}
        return 200, self._listing(session_id)

    def _select(self, body: Any, session_id: str) -> tuple[int, Any]:
        held = self.sessions.get(session_id)
        if held is None:
            return 404, {"detail": "Session not found"}
        job_id = body.get("job") if isinstance(body, dict) else None
        if set(body or {}) != {"job"} or not (
            job_id is None or (isinstance(job_id, str) and re.fullmatch(r"[0-9a-f]{32}", job_id))
        ):
            return 422, {"detail": "A selection holds job, a job's identifier or null"}
        if job_id is not None:
            if job_id not in held["jobs"]:
                return 422, {"detail": "The job is not a job of this session"}
            if "result" not in self._present(self.jobs[job_id]):
                return 422, {"detail": "The job holds no record to discuss"}
        held["selected_job"] = job_id
        return 200, self._listing(session_id)

    def _append(self, session_id: str, kind: str, text: str, origin=None, replies_to=None) -> dict:
        held = self.sessions[session_id]
        entry = {
            "number": len(held["entries"]) + 1,
            "kind": kind,
            "text": text,
            "origin": origin,
            "replies_to": replies_to,
            "created_at": NOW,
        }
        held["entries"].append(entry)
        if kind in ("user", "paper", "acceptance"):
            held["revision"] = entry["number"]
        return entry

    def _add_entry(self, body: Any, session_id: str) -> tuple[int, Any]:
        held = self.sessions.get(session_id)
        if held is None:
            return 404, {"detail": "Session not found"}
        if not isinstance(body, dict) or set(body) - {"text", "kind", "replies_to", "delivery_id"}:
            return 422, {"detail": "An entry holds text, kind, replies_to and delivery_id and nothing else"}
        kind = body.get("kind", "user")
        replies_to = body.get("replies_to")
        if kind not in ("user", "paper", "acceptance"):
            return 422, {"detail": "An entry's kind is user, paper or acceptance"}
        if kind == "acceptance":
            if "text" in body:
                return 422, {"detail": "An acceptance holds no text"}
            if type(replies_to) is not int:
                return 422, {"detail": "An acceptance names in replies_to the answer entry it accepts"}
        elif not isinstance(body.get("text"), str) or not body["text"].strip():
            return 422, {"detail": "An entry needs a text"}
        replied = (
            held["entries"][replies_to - 1]
            if type(replies_to) is int and 0 < replies_to <= len(held["entries"])
            else None
        )
        entry = self._append(session_id, kind, str(body.get("text", "")).strip(), replies_to=replies_to)
        scheduled = None
        if kind == "user" and held["awaiting_answer"] and replied and replied["kind"] == "question":
            job_id = self._new_job(session_id, "converged")
            held["awaiting_answer"] = None
            scheduled = {"id": job_id, "status_url": f"/v1/model-iterations/{job_id}"}
        return 200, {**self._listing(session_id), "entry": entry, "repeated": False, "scheduled": scheduled}

    def _default_job(self, session_id: str) -> str | None:
        """The job a turn reads without a request: the session's selected
        job, else its latest current job that holds a record, else None."""
        held = self.sessions[session_id]
        recorded = [job_id for job_id in held["jobs"] if "result" in self._present(self.jobs[job_id])]
        if held["selected_job"] in recorded:
            return held["selected_job"]
        for job_id in reversed(recorded):
            job = self.jobs[job_id]
            if job["current"] is not False and self._present(job)["state"] != "cancelled":
                return job_id
        return None

    def _ask(self, body: Any, session_id: str) -> tuple[int, Any]:
        if session_id not in self.sessions:
            return 404, {"detail": "Session not found"}
        if not isinstance(body, dict) or set(body) - TURN_FIELDS:
            return 422, {"detail": "A turn's request has no field such as that"}
        if not isinstance(body.get("question"), str) or not body["question"].strip():
            return 422, {"detail": "A turn needs a question"}
        question = self._append(session_id, "user", body["question"])
        turn_id = uuid.uuid4().hex
        self.sessions[session_id]["turns"].append(turn_id)
        base = {"id": turn_id, "session": session_id, "question": question["number"], "events": []}
        default = self._default_job(session_id)
        started = None
        if JOB_REQUEST in body["question"].casefold():
            # the job's version is fixed at the submission, the question
            # included (AMD-MAT-009 §3)
            job_id = self._new_job(session_id, self.next_ends.pop(0) if self.next_ends else "converged")
            self.jobs[job_id]["revision"] = self.sessions[session_id]["revision"]
            started = {"id": job_id, "label": self._label(job_id, "queued")}
        result = {
            "turn": turn_id,
            "status": "answered",
            "answer": ANSWER if started is None else JOB_ANSWER,
            "citations": [CITATION],
            "questions": [],
            "reason": None,
            "passages": [],
            "index_digest": DIGEST,
            "current": True,
            "job": (
                None
                if default is None
                else {
                    "id": default,
                    "label": self._label(default, self._present(self.jobs[default])["state"]),
                }
            ),
            "job_started": started,
        }
        record = {
            "schema": "matsya-conversation-turn/1",
            "turn": turn_id,
            "session": session_id,
            "question": question["number"],
            "result": result,
        }
        self.turns[turn_id] = [
            {**base, "state": "queued", "progress": None},
            {**base, "state": "running", "progress": {"step": "conversation", "cycle": 0}},
            {**base, "state": "finished", "progress": {"step": "conversation", "cycle": 0}, "record": record},
        ]
        return 202, {
            "id": turn_id,
            "state": "queued",
            "question": question["number"],
            "repeated": False,
            "status_url": f"/v1/sessions/{session_id}/turns/{turn_id}",
        }

    def _turn(self, body: Any, session_id: str, turn_id: str) -> tuple[int, Any]:
        frames = self.turns.get(turn_id)
        if frames is None or frames[0]["session"] != session_id:
            return 404, {"detail": "Turn not found"}
        answer = frames.pop(0) if len(frames) > 1 else frames[0]
        if answer["state"] == "finished" and turn_id not in self.ended:
            self.ended.add(turn_id)
            text = answer["record"]["result"]["answer"]
            self._append(session_id, "answer", text, {"turn": turn_id}, answer["question"])
        return 200, answer

    # -- jobs

    @staticmethod
    def _at(job: dict[str, Any]) -> int:
        """The position of a job's present state among its frames: the frame
        of its latest request for its state, or `queued` before the first."""
        return min(max(job["served"] - 1, 0), len(job["frames"]) - 1)

    def _present(self, job: dict[str, Any]) -> dict[str, Any]:
        return job["frames"][self._at(job)]

    def _label(self, job_id: str, state: str) -> dict[str, Any]:
        """A job's label in the form of `job_label` of `jobs.py`."""
        job = self.jobs[job_id]
        if job["session"] is None:
            return dict(zip(LABEL_KEYS, (None, None, None, state, False, state)))
        held = self.sessions[job["session"]]
        revision = job["revision"]
        if state == "running":
            overtaken = revision is not None and held["revision"] > revision
        else:
            overtaken = state in RECORD_STATES and state != "cancelled" and job["current"] is False
        pieces = [held["name"]] + ([f"version {revision}"] if revision is not None else [])
        text = " · ".join(pieces + [f"job {job['number']}", state])
        if overtaken:
            text += ", text changed since" if state == "running" else ", built from an earlier version"
        return dict(zip(LABEL_KEYS, (held["name"], revision, job["number"], state, overtaken, text)))

    def _shown(self, job_id: str, frame: dict[str, Any]) -> dict[str, Any]:
        """A frame as `GET /v1/model-iterations/{id}` answers it: with the
        job's label, whether its cancellation was requested and, for a job
        of a session, its revision once it has run and whether it was
        current at its end."""
        job = self.jobs[job_id]
        shown = {
            **frame,
            "label": self._label(job_id, frame["state"]),
            "cancel_requested": job["cancel_requested"],
        }
        if job["revision"] is not None:
            shown["revision"] = job["revision"]
        if job["current"] is not None and frame["state"] in JOB_ENDED:
            shown["current"] = job["current"]
        return shown

    def _new_job(self, session_id: str | None, end: str) -> str:
        job_id = uuid.uuid4().hex
        base = {"id": job_id, "events": [], "created_at": NOW, "updated_at": NOW}
        number = None
        if session_id is not None:
            base["session"] = session_id
            self.sessions[session_id]["jobs"].append(job_id)
            number = len(self.sessions[session_id]["jobs"])
        record = RECORDS[end]
        queued = {**base, "state": "queued", "progress": None}
        preparing = {**base, "state": "running", "progress": {"step": "preparation", "cycle": 0, "max_cycles": 2}}
        frames = [queued, preparing]
        for cycle in range(1, len(record["cycles"]) + 1):
            frames.append(
                {**base, "state": "running", "progress": {"step": "writing", "cycle": cycle, "max_cycles": 2}}
            )
        progress = (
            {"step": "reconstruction", "cycle": len(record["cycles"]), "max_cycles": 2}
            if record["cycles"]
            else preparing["progress"]
        )
        frames.append({**base, "state": record["status"], "progress": progress, "result": record})
        self.jobs[job_id] = {
            "frames": frames,
            "served": 0,
            "session": session_id,
            "number": number,
            "revision": None,
            "current": None,
            "cancel_requested": False,
        }
        return job_id

    def _submit(self, body: Any) -> tuple[int, Any]:
        if not isinstance(body, dict) or set(body) - JOB_FIELDS:
            return 422, {"detail": "The model request has unsupported fields"}
        if "source" not in body and "session" not in body:
            return 422, {"detail": "The model request needs a source or a session"}
        cycles = body.get("max_cycles")
        if cycles is not None and (type(cycles) is not int or cycles < 1):
            return 422, {"detail": "max_cycles must be a positive integer"}
        if cycles is not None and cycles > CYCLE_MAXIMUM:
            return 422, {"detail": f"max_cycles must be an integer from 1 to {CYCLE_MAXIMUM}"}
        session_id = body.get("session")
        if session_id is not None:
            if "source" in body:
                return 422, {"detail": "A job from a session takes the session's text as its source"}
            if session_id not in self.sessions:
                return 404, {"detail": "Session not found"}
            if self.sessions[session_id]["revision"] == 0:
                return 422, {"detail": "The session holds no text"}
        else:
            source = body["source"]
            if source.get("kind") == "description":
                if set(source) != {"kind", "text"} or not str(source.get("text", "")).strip():
                    return 422, {"detail": "A description needs source.text"}
            elif source.get("kind") != "paper" or set(source) != {"kind", "pdf_base64"}:
                return 422, {"detail": "A paper accepts kind and one source form"}
        end = self.next_ends.pop(0) if self.next_ends else ("needs_input" if session_id else "converged")
        job_id = self._new_job(session_id, end)
        return 202, {"id": job_id, "state": "queued", "status_url": f"/v1/model-iterations/{job_id}"}

    def _job(self, body: Any, job_id: str, query: dict[str, str] | None = None) -> tuple[int, Any]:
        """A job as the service returns it: an ended job's record in the
        products view by default and whole with `view=full`; another view
        answers 422."""
        view = (query or {}).get("view", "products")
        if view not in ("products", "full"):
            return 422, {"detail": "The view is products or full"}
        job = self.jobs.get(job_id)
        if job is None:
            return 404, {"detail": "Model iteration not found"}
        frames = job["frames"]
        answer = frames[min(job["served"], len(frames) - 1)]
        job["served"] += 1
        session_id = job["session"]
        if session_id is not None and answer["state"] == "running" and job["revision"] is None:
            # a job of a session reads the session's text as it stands when
            # the job starts to run
            job["revision"] = self.sessions[session_id]["revision"]
        if answer["state"] in JOB_ENDED and job_id not in self.ended:
            self.ended.add(job_id)
            if session_id is not None:
                held = self.sessions[session_id]
                job["current"] = answer["state"] != "cancelled" and held["revision"] == job["revision"]
                if answer["state"] == "needs_input" and job["current"]:
                    for question in answer["result"]["questions"]:
                        self._append(session_id, "question", question, {"job": job_id})
                    held["awaiting_answer"] = job_id
        shown = self._shown(job_id, answer)
        if view == "products" and isinstance(shown.get("result"), dict):
            shown["result"] = products_of(shown["result"])
        return 200, shown

    def _cancel(self, body: Any, job_id: str) -> tuple[int, Any]:
        """A queued job becomes `cancelled` at once and never runs; a running
        job is marked and ends `cancelled` with a record at its next state;
        an ended job is refused."""
        job = self.jobs.get(job_id)
        if job is None:
            return 404, {"detail": "Model iteration not found"}
        present = self._present(job)
        if present["state"] == "queued":
            cancelled = {**present, "state": "cancelled"}
            job.update(frames=[cancelled], served=1, cancel_requested=True)
            self.ended.add(job_id)
            if job["session"] is not None:
                job["current"] = False
            return 200, self._shown(job_id, cancelled)
        if present["state"] == "running":
            ended = {**present, "state": "cancelled", "result": RECORDS["cancelled"]}
            job.update(frames=job["frames"][: self._at(job) + 1] + [ended], cancel_requested=True)
            return 200, self._shown(job_id, present)
        return 409, {"detail": "The job has ended"}


def _loopback_only(monkeypatch: pytest.MonkeyPatch) -> None:
    """Send the tests' requests to the loopback address directly, past any
    proxy the environment names."""
    for name in ("http_proxy", "HTTP_PROXY", "https_proxy", "HTTPS_PROXY", "all_proxy", "ALL_PROXY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    monkeypatch.setenv("no_proxy", "127.0.0.1,localhost")


def _user(monkeypatch: pytest.MonkeyPatch, folder: Path, server: str, token: str) -> None:
    """The environment of a user whose saved configuration is an empty
    folder of the test's own and whose Matsya token and service address are
    MATSYA_TOKEN and MATSYA_SERVER."""
    monkeypatch.setattr(config, "CONFIG_DIR", folder)
    monkeypatch.setattr(config, "CONFIG_FILE", folder / "config.toml")
    monkeypatch.setenv("MATSYA_TOKEN", token)
    monkeypatch.setenv("MATSYA_SERVER", server)
    _loopback_only(monkeypatch)


@pytest.fixture
def stand_in(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """The stand-in service, started on the loopback address, and a user
    whose Matsya token it accepts."""
    service = StandIn(TOKEN)
    service.start()
    _user(monkeypatch, tmp_path / "user-configuration", service.url, TOKEN)
    yield service
    service.stop()


@pytest.fixture
def run(capsys: pytest.CaptureFixture[str]):
    """Run the command `matsya` with the arguments given, and return its
    exit status, its standard output and its standard error."""
    from matsya import cli

    def command(*arguments: str) -> tuple[int | str | None, str, str]:
        try:
            status = cli.main(list(arguments))
        except SystemExit as stopped:
            status = stopped.code
        captured = capsys.readouterr()
        return status, captured.out, captured.err

    return command


class _StandInEmbeddings:
    """A sentence encoder for the tests, as in the service's tests: every
    text is one fixed vector, so that an index is built and searched without
    the optional retrieval libraries."""

    model_id = "stand-in-embedding-v1"

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.1] for _ in texts]


@pytest.fixture
def service(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """The Matsya service of spec 0.3 under the test configuration, with the
    conversation role enabled, a small index of one published page and a
    scripted caller in place of the model provider, served by uvicorn on the
    loopback address; and a user whose Matsya token it accepts. The caller
    holds the replies of one job that converges in one cycle; a test adds the
    reply of a turn to `caller.replies`. `application` is the service's
    application, whose `state.runner` is its job runner."""
    uvicorn = pytest.importorskip("uvicorn")
    pytest.importorskip("matsya_service")
    if not (SERVICE_TESTS / "scripted.py").is_file():
        pytest.skip("the tests of the Matsya service are not in this checkout")
    monkeypatch.syspath_prepend(str(SERVICE_TESTS))
    from conversation_parts import ROLE, add_conversation_role, remove_conversation_role
    from matsya_service.api import create_app
    from matsya_service.configuration import write_manifest
    from matsya_service.processor import ModelProcessor
    from matsya_service.retrieval import activate_candidate, build_candidate, load_active
    from scripted import DESCRIPTION, ScriptedCaller, converging

    folder = tmp_path / "configuration"
    shutil.copytree(
        SERVICE_TESTS / "fixtures" / "configuration",
        folder,
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    remove_conversation_role(folder)
    add_conversation_role(folder)
    write_manifest(folder, "fixture")

    repository = tmp_path / "repository"
    page = repository / "docs" / "Bellman-Sym" / "01-stage.md"
    page.parent.mkdir(parents=True)
    page.write_text("# The stage\n\n" + PASSAGE["text"] + "\n", encoding="utf-8")
    sources = tmp_path / "sources.json"
    sources.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "corpus_revisions": {},
                "sources": [
                    {
                        "corpus": "repository",
                        "source_id": PASSAGE["source_id"],
                        "path": PASSAGE["path"],
                        "sha256": hashlib.sha256(page.read_bytes()).hexdigest(),
                        "kind": "markdown",
                        "authority": "primary",
                        "access": "public",
                        "model_prompt": True,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    roots = {"repository": repository}
    index_root = tmp_path / "index"
    candidate = build_candidate(sources, roots, index_root, _StandInEmbeddings())
    activate_candidate(candidate, index_root, roots, _StandInEmbeddings())

    tokens = tmp_path / "tokens.db"
    with sqlite3.connect(tokens) as db:
        db.execute(
            "CREATE TABLE tokens (id INTEGER PRIMARY KEY, principal_id INTEGER, "
            "token_hash TEXT, revoked_at TEXT)"
        )
        db.execute(
            "INSERT INTO tokens VALUES (1, 11, ?, NULL)", (hashlib.sha256(TOKEN.encode()).hexdigest(),)
        )
    caller = ScriptedCaller(converging())
    application = create_app(
        processor=ModelProcessor(folder, caller_factory=lambda roles, ledger: caller),
        retrieval_index=load_active(index_root, _StandInEmbeddings(), None),
        token_db_path=tokens,
        job_db_path=tmp_path / "jobs.db",
        configuration=folder,
    )
    listening = socket.socket()
    listening.bind(("127.0.0.1", 0))
    server = uvicorn.Server(
        uvicorn.Config(application, log_level="warning", log_config=None, lifespan="on")
    )
    thread = threading.Thread(target=server.run, kwargs={"sockets": [listening]}, daemon=True)
    thread.start()
    for _ in range(1000):
        if server.started or not thread.is_alive():
            break
        time.sleep(0.01)
    if not server.started:
        pytest.fail("the Matsya service of the test configuration did not start")
    url = f"http://127.0.0.1:{listening.getsockname()[1]}"
    _user(monkeypatch, tmp_path / "user-configuration", url, TOKEN)
    yield SimpleNamespace(
        url=url,
        token=TOKEN,
        caller=caller,
        role=ROLE,
        description=DESCRIPTION,
        application=application,
    )
    server.should_exit = True
    thread.join(10)
    listening.close()
