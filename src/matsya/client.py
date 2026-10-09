"""The HTTP client of the Matsya service of spec 0.3.

`MatsyaClient` sends each request to one route of the service, with the
user's Matsya token in the `Authorization` header, and returns the service's
JSON answer; `start_job` sends the three requests that keep a job's file in a
session: the session, the entry and the job. A job of architect mode and a
turn of conversation mode run on the service after their routes have
answered; `wait_job` and `ask` then ask for their state until it is final.
`job_files` writes an ended job's model folder, and `report_text` composes
the folder's report from the products view of the job's record, by a
program and with no language model (AMD-MAT-010 §§4 and 5). The module uses
the standard library alone.
"""

from __future__ import annotations

import base64
import copy
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

# the seconds one request may take: every route answers at once, since a job
# or a turn runs on the service after its route has answered
REQUEST_TIMEOUT = 120
# the states in which a job and a turn have ended (spec 0.3, REQ-MAT-031;
# AMD-MAT-006 §9), a job the user cancelled among them (AMD-MAT-008 §4)
JOB_FINAL_STATES = (
    "converged",
    "not_converged",
    "needs_input",
    "cancelled",
    "failed",
    "interrupted",
)
TURN_FINAL_STATES = ("finished", "failed", "interrupted")
# the two views of a job's record that `GET /v1/model-iterations/{id}`
# returns: `products`, the default, holds the final products and the
# material of the report, and `full` the record as the job store keeps it
# (AMD-MAT-010 §3)
VIEWS = ("products", "full")
# the files of the model folder beside `declaration/` (AMD-MAT-010 §5): the
# model prose, the report and the job as the service returned it in the
# products view
ECONOMICS_FILE = "economics.md"
REPORT_FILE = "report.md"
RECORD_FILE = "record.json"
# the folder written with `all_iterates`, and the job in the full view within it
ITERATES_FOLDER = "iterates"
FULL_RECORD_FILE = "iterates/record-full.json"
# the writer's note among the files of a writing, and the texts of a note
# that leaves nothing open (`unresolved_note` of the configuration's Matsya
# handler module counts every other note as unresolved)
NOTE_FILE = "note.md"
NOTE_NONE = ("", "none", "none.")
# the headings of the report, in the order of AMD-MAT-010 §4
REPORT_HEADINGS = (
    "The job",
    "Status",
    "Cycles and version",
    "What did not match",
    "The round-trip comparison",
    "The writer's note",
    "Questions",
    "Cost",
)
REPORT_TITLE = "Report of the job"
# the fixed sentence of the report when both judges agree on every heading
JUDGES_AGREE = "The judges agree on every heading."
# the two judges of a job: the record's entry holding each one's reports,
# its name and what it compares (the terminology of 9 October 2026)
JUDGES = (
    (
        "paper_source_check",
        "prose-source-judge",
        "The prose-source-judge compares the model prose with the source material.",
    ),
    (
        "judging",
        "prose-roundtrip-judge",
        "The prose-roundtrip-judge compares the round-trip prose with the model prose.",
    ),
)
BOTH_ORDERS = (
    "Each judge reads the two texts in both orders, and a heading agrees only when both "
    "readings count no omission, addition or contradiction."
)
ORDERS = ("first", "second")
COUNTS = ("omissions", "additions", "contradictions")
CITATIONS_UNSUPPORTED = (
    "Not every block of the last cycle's stage files quotes, in a `# from:` line, a sentence "
    "that occurs in the model prose, or the stage files hold no block."
)
# the names in prose that the report's table of language-model tokens gives
# beside the roles' keys (the names of 9 October 2026); the key of the
# judges serves both of them
ROLE_NAMES = {
    "SourceMaterial_to_BellmanStageProse": "Model-prose-writer",
    "BellmanStageProse_to_BellmanSYMDeclaration": "Prose-to-Bellman-Sym",
    "ElaboratedSemanticObject_to_BellmanStageProse": "Semantics-to-Prose",
    "BellmanStageProse_judge": "prose-source-judge and prose-roundtrip-judge",
}


class MatsyaError(Exception):
    """A request the service refused or did not answer. `status` is the HTTP
    status of the service's answer, or `None` when no answer arrived, and
    `detail` is the service's own message."""

    def __init__(self, message: str, status: int | None = None, detail: str = "") -> None:
        super().__init__(message)
        self.status = status
        self.detail = detail


class AuthenticationError(MatsyaError):
    """The service refused the Matsya token (401): none was sent, or the
    service holds no such Matsya token, or it has been revoked."""


class RateLimitError(MatsyaError):
    """The service refused the request because too many arrived (429);
    `retry_after` is the number of seconds the service asks the client to
    wait, when it names one."""

    def __init__(
        self,
        message: str,
        status: int | None = 429,
        detail: str = "",
        retry_after: int | None = None,
    ) -> None:
        super().__init__(message, status, detail)
        self.retry_after = retry_after


class ServerError(MatsyaError):
    """The service failed or cannot provide the operation (5xx)."""


class ContextTooLargeError(MatsyaError):
    """The request is larger than the service accepts (413), such as a PDF
    over 16 MiB."""


def _origin(url: str) -> str:
    """The scheme and the host, with its port, of an address, in lower case,
    such as `https://matsya.example.org:8443`."""
    parts = urllib.parse.urlsplit(url)
    return f"{parts.scheme}://{parts.netloc.rpartition('@')[2]}".lower()


class _SameHostRedirects(urllib.request.HTTPRedirectHandler):
    """urllib's handler of redirects, which copies a request's headers, the
    `Authorization` header among them, to the redirected request; a request
    that carries the Matsya token is redirected only to its own scheme, host
    and port, and a redirect elsewhere raises `MatsyaError` before any
    request is sent there. `hidden` replaces the Matsya token in the
    message."""

    def __init__(self, hidden: Callable[[str], str]) -> None:
        self.hidden = hidden

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        here, there = _origin(req.full_url), _origin(newurl)
        if req.has_header("Authorization") and there != here:
            fp.close()
            raise MatsyaError(
                self.hidden(
                    f"The Matsya service at {here} redirected the request to {there}; the "
                    "client follows a redirect only to the same scheme, host and port, so that "
                    "the Matsya token is sent nowhere else."
                )
            )
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _segment(value: str) -> str:
    """One path segment of a route, such as a job's identifier."""
    return urllib.parse.quote(str(value), safe="")


def _service_message(text: str) -> str:
    """The `detail` of the service's JSON answer to a refused request, or an
    empty text when the answer holds none."""
    try:
        answer = json.loads(text)
    except ValueError:
        return ""
    detail = answer.get("detail") if isinstance(answer, dict) else None
    if isinstance(detail, str):
        return detail
    if isinstance(detail, list):
        return "; ".join(
            str(item.get("msg", item)) if isinstance(item, dict) else str(item) for item in detail
        )
    return ""


def _sentence(text: str) -> str:
    """The text with one full stop at its end."""
    text = text.strip()
    return text if text.endswith((".", "?", "!")) else text + "."


def _plain_name(name: object) -> bool:
    """Whether a name is one part of a path the client writes: a name that
    is not empty, does not begin with a dot and holds no slash, backslash,
    colon or NUL character, so that it names no path outside its folder."""
    return (
        isinstance(name, str)
        and name not in ("", ".", "..")
        and not name.startswith(".")
        and not any(character in name for character in ("/", "\\", ":", "\x00"))
    )


def _relative_name(name: object) -> str | None:
    """A file name of a record as the path the client writes, or `None` for
    a name it does not write. A name is written when it is a plain name, or
    one of the three names with a folder part that a model's declaration
    holds, `calibration/<file>`, `settings/<file>` and
    `stages/<key>/methods.yml`, each part a plain name."""
    if not isinstance(name, str):
        return None
    parts = name.split("/")
    if not all(_plain_name(part) for part in parts):
        return None
    if len(parts) == 1:
        return name
    if len(parts) == 2 and parts[0] in ("calibration", "settings"):
        return name
    if len(parts) == 3 and parts[0] == "stages" and parts[2] == "methods.yml":
        return name
    return None


def is_pdf(name: str | Path, data: bytes) -> bool:
    """Whether a file is a PDF: its name ends in `.pdf` or its first bytes
    are `%PDF-`."""
    return str(name).lower().endswith(".pdf") or data.startswith(b"%PDF-")


def last_cycle_files(record: dict[str, Any]) -> dict[str, str]:
    """The files of a job's last cycle, by file name, from the products view
    of its record (`last_cycle.files`, AMD-MAT-010 §3): the stage files, the
    writer's note and any period or trellis file; an empty mapping when the
    record holds no cycle or the last cycle stopped before its writing."""
    last = record.get("last_cycle")
    files = last.get("files") if isinstance(last, dict) else None
    return dict(files) if isinstance(files, dict) else {}


def _open_note(files: dict[str, Any]) -> str | None:
    """The text of the writer's note among a writing's files when it leaves
    something open, that is, when it is neither empty nor `none`, else
    `None`."""
    note = files.get(NOTE_FILE)
    if isinstance(note, str) and note.strip().casefold() not in NOTE_NONE:
        return note
    return None


# ---------------------------------------------------------------------------
# the report of AMD-MAT-010 §4


def _code(value: object) -> str:
    """A value of the record as a Markdown code span: a text of one line as
    it stands, and any other value in JSON."""
    if isinstance(value, str) and "\n" not in value:
        text = value
    else:
        text = json.dumps(value, ensure_ascii=False)
    fence = "`" * (max((len(run) for run in re.findall(r"`+", text)), default=0) + 1)
    pad = " " if text.startswith("`") or text.endswith("`") else ""
    return f"{fence}{pad}{text}{pad}{fence}"


def _item(prefix: str, text: str) -> list[str]:
    """A list item of the report: the text after the prefix, its further
    lines indented under the first."""
    lines = text.splitlines() or [""]
    return [prefix + lines[0]] + [" " * len(prefix) + line for line in lines[1:]]


def _role_text(role: str) -> str:
    """A role by its name in prose and its key, or by its key alone."""
    return f"{ROLE_NAMES[role]} (`{role}`)" if role in ROLE_NAMES else f"`{role}`"


def _label_line(job: dict[str, Any], label: object) -> str:
    """The content of the report's first heading: the text of the job's
    label, the job's identifier and its session's, such as "model · version
    1 · job 1 · converged (<job>), session <session>"."""
    text = label.get("text") if isinstance(label, dict) else None
    if not isinstance(text, str) or not text.strip():
        text = str(job.get("state"))
    session = job.get("session")
    return f"{text} ({job.get('id')}), " + (f"session {session}" if session else "no session")


def _status_sentence(job: dict[str, Any], record: dict[str, Any]) -> str:
    """The content of the report's second heading: the status and the
    reason in one sentence; for a job that holds no record, its state and
    its error code, or that it has not ended."""
    if not record:
        state, error = job.get("state"), job.get("error")
        if state not in JOB_FINAL_STATES:
            return f"The job has not ended; its state is {state}."
        if error:
            return f"The job ended {state}, with the error {error}."
        return f"The job ended {state}."
    status = record.get("status") or job.get("state")
    reason = record.get("reason")
    if reason:
        return f"The job ended {status}, with the reason {reason}."
    return f"The job ended {status}."


def _cycles_lines(job: dict[str, Any], record: dict[str, Any], label: object) -> list[str]:
    """The number of cycles run and the version of the session's text."""
    cycles = record.get("cycles_run")
    if type(cycles) is not int:
        ran = "The record does not state the number of cycles run."
    elif cycles == 0:
        ran = "The job ran no cycle."
    else:
        ran = f"The job ran {cycles} cycle{'s' if cycles > 1 else ''}."
    version = job.get("revision")
    if version is None and isinstance(label, dict):
        version = label.get("revision")
    if not job.get("session"):
        built = "The job has no session, so its text has no version."
    elif version is None:
        built = "The record does not state the version of the session's text."
    else:
        built = f"It was built from version {version} of the session's text."
    return [f"{ran} {built}"]


def _judge_lines(name: str, check: object) -> list[str]:
    """One judge's reports: that the record holds none, that the judge
    agrees on every heading, or each heading on which a reading disagrees,
    with its counts in both orders of the texts and its quoted sentences."""
    if not isinstance(check, dict) or not isinstance(check.get("reports"), list):
        return [f"The record holds no report of the {name}."]
    if check.get("agrees") is True:
        return [f"The {name} agrees on every heading."]
    reports = [report for report in check["reports"] if isinstance(report, dict)]
    lines: list[str] = []
    for position, report in enumerate(reports):
        form = report.get("form")
        if isinstance(form, dict) and form.get("passed") is False:
            order = ORDERS[position] if position < len(ORDERS) else str(position + 1)
            lines += [
                f"In the {order} order of the two texts, the {name} rejected the form of the "
                "prose.",
                "",
            ]
    # the headings in the order the readings hold them, and those on which a
    # reading disagrees
    held: list[str] = []
    for report in reports:
        items = report.get("items")
        for heading in items if isinstance(items, dict) else ():
            if heading not in held:
                held.append(heading)
    headings = [
        heading
        for heading in held
        if any(
            isinstance(report.get("items"), dict)
            and isinstance(report["items"].get(heading), dict)
            and report["items"][heading].get("agrees") is False
            for report in reports
        )
    ]
    for heading in headings:
        lines += [
            f"#### {heading}",
            "",
            "| Order of the texts | Omissions | Additions | Contradictions |",
            "|---|---|---|---|",
        ]
        quotes: list[str] = []
        for position, report in enumerate(reports):
            items = report.get("items")
            item = items.get(heading) if isinstance(items, dict) else None
            if not isinstance(item, dict):
                continue
            order = ORDERS[position] if position < len(ORDERS) else str(position + 1)
            counts = " | ".join(str(item.get(count, "")) for count in COUNTS)
            lines.append(f"| {order} | {counts} |")
            for quote in item.get("quotes") or []:
                if isinstance(quote, str) and quote not in quotes:
                    quotes.append(quote)
        lines.append("")
        if quotes:
            lines += ["The quoted sentences:", ""]
            for quote in quotes:
                lines += _item("- ", f'"{quote}"')
            lines.append("")
    if not lines:
        lines = [
            f"The record marks the {name} as disagreeing and names no heading on which it "
            "disagrees."
        ]
    while lines and not lines[-1]:
        lines.pop()
    return lines


def _mismatch_lines(record: dict[str, Any]) -> list[str]:
    """The section What did not match: the fixed sentence when both judges
    agree, else one subsection per judge; then the form check of the model
    prose when it failed, and the quotations of the stage files when the
    last cycle's `citations_supported` is false, that is, when a block
    quotes a sentence that does not occur in the model prose, quotes none,
    or the stage files hold no block."""
    last = record.get("last_cycle") if isinstance(record.get("last_cycle"), dict) else {}
    checks = {
        "paper_source_check": record.get("paper_source_check"),
        "judging": last.get("judging"),
    }
    verdicts = [
        check.get("agrees") if isinstance(check, dict) else None for check in checks.values()
    ]
    if all(verdict is True for verdict in verdicts):
        lines = [JUDGES_AGREE]
    else:
        lines = [BOTH_ORDERS, ""] if False in verdicts else []
        for entry, name, compares in JUDGES:
            lines += [f"### The {name}", "", compares, "", *_judge_lines(name, checks[entry]), ""]
        lines.pop()
    form = record.get("paper_form_check")
    if isinstance(form, dict) and form.get("passed") is False:
        lines += [
            "",
            "### The form of the model prose",
            "",
            "The form check of the model prose found:",
            "",
        ]
        for finding in form.get("findings") or []:
            lines += _item("- ", str(finding))
    if last.get("citations_supported") is False:
        lines += ["", "### The quotations of the stage files", "", CITATIONS_UNSUPPORTED]
    return lines


def _comparison_lines(record: dict[str, Any]) -> list[str]:
    """The section The round-trip comparison: whether the round-trip stage
    files equal the written ones, with the first difference when they do
    not."""
    last = record.get("last_cycle")
    comparison = last.get("comparison") if isinstance(last, dict) else None
    if not isinstance(comparison, dict):
        return ["The record holds no round-trip comparison."]
    if comparison.get("equal") is True:
        return ["The round-trip stage files equal the written ones."]
    if comparison.get("equal") is not False:
        return ["The record holds no verdict of the round-trip comparison."]
    lines = ["The round-trip stage files do not equal the written ones.", ""]
    difference = comparison.get("first_difference")
    if not isinstance(difference, dict) or not difference:
        return lines + ["The record names no first difference."]
    if "left" in difference or "right" in difference:
        lines.append(
            "The first difference the comparison names, in which `left` is read from the written "
            "stage files and `right` from the round-trip ones:"
        )
    else:
        lines.append("The first difference the comparison names:")
    lines.append("")
    for key, value in difference.items():
        lines.append(f"- {key}: {_code(value)}")
    return lines


def _note_lines(record: dict[str, Any]) -> list[str] | None:
    """The section The writer's note, when the record holds a note that
    leaves something open: the note's text quoted, or the fixed sentence
    that the record marks the note unresolved and holds no text of it;
    `None` when the record holds no such note."""
    last = record.get("last_cycle") if isinstance(record.get("last_cycle"), dict) else {}
    files = last.get("files") if isinstance(last.get("files"), dict) else {}
    note = _open_note(files)
    if note is not None:
        return [f"> {line}".rstrip() for line in note.rstrip("\n").splitlines()]
    if last.get("unresolved_note") is True:
        return [
            "The record marks the writer's note as unresolved, and the products hold no text of it."
        ]
    return None


def _cost_lines(record: dict[str, Any]) -> list[str]:
    """The section Cost: the language-model tokens charged to each role
    that made a call or was charged, and to the job, with the number of
    calls; and the refusal at a ceiling, when one ended the job."""
    usage = record.get("usage") if isinstance(record.get("usage"), dict) else {}
    charged = usage.get("charged")
    total = charged.get("job") if isinstance(charged, dict) else None
    if not isinstance(total, dict):
        lines = ["The record holds no account of the language-model tokens charged."]
    else:
        roles = charged.get("roles") if isinstance(charged.get("roles"), dict) else {}
        calls = usage.get("calls_by_role") if isinstance(usage.get("calls_by_role"), dict) else {}
        columns = list(total)
        names = " | ".join(column.replace("_", " ").capitalize() for column in columns)
        lines = [
            "The language-model tokens charged, by role and for the job:",
            "",
            f"| Role | Calls | {names} |",
            "|---|---|" + "---|" * len(columns),
        ]
        for role, held in roles.items():
            held = held if isinstance(held, dict) else {}
            made = calls.get(role, 0)
            if not made and not any(held.get(column) for column in columns):
                continue
            lines.append(
                f"| {_role_text(role)} | {made} | "
                + " | ".join(str(held.get(column, 0)) for column in columns)
                + " |"
            )
        made = sum(count for count in calls.values() if type(count) is int)
        charged_to_job = " | ".join(str(total.get(column)) for column in columns)
        lines.append(f"| The job | {made} | {charged_to_job} |")
    refusal = usage.get("refusal")
    if isinstance(refusal, dict):
        lines += [
            "",
            f"A language-model token ceiling refused call {refusal.get('call')}, of the role "
            f"{_code(refusal.get('role'))}, under the condition {_code(refusal.get('condition'))}: "
            f"{refusal.get('charged')} tokens were charged, the call would have added "
            f"{refusal.get('would_add')}, and the ceiling is {refusal.get('ceiling')}.",
        ]
    return lines


def _report_sections(
    products_view: dict[str, Any], label: dict[str, Any] | None = None
) -> list[tuple[str, list[str]]]:
    """The report's sections, each a heading of `REPORT_HEADINGS` and its
    lines, in the order of AMD-MAT-010 §4; The writer's note and Questions
    only when the record holds them."""
    record = products_view.get("result")
    record = record if isinstance(record, dict) else {}
    label = products_view.get("label") if label is None else label
    sections = [
        ("The job", [_label_line(products_view, label)]),
        ("Status", [_status_sentence(products_view, record)]),
        ("Cycles and version", _cycles_lines(products_view, record, label)),
        ("What did not match", _mismatch_lines(record)),
        ("The round-trip comparison", _comparison_lines(record)),
    ]
    note = _note_lines(record)
    if note is not None:
        sections.append(("The writer's note", note))
    questions = [held for held in record.get("questions") or [] if isinstance(held, str)]
    if questions:
        numbered: list[str] = []
        for number, question in enumerate(questions, 1):
            numbered += _item(f"{number}. ", question)
        sections.append(("Questions", numbered))
    sections.append(("Cost", _cost_lines(record)))
    return sections


def report_text(products_view: dict[str, Any], label: dict[str, Any] | None = None) -> str:
    """The report of an ended job, `report.md` of its model folder
    (AMD-MAT-010 §4), composed by a program and with no language model.

    `products_view` is the job as `GET /v1/model-iterations/{id}` returns
    it in the products view, the default, and as `record.json` holds it: its
    identifier, its session, its revision, its label and, under `result`,
    the products view of its record. `label` is the job's label of
    AMD-MAT-008 §2, `{"model", "revision", "number", "state", "overtaken",
    "text"}`; by default the label `products_view` holds.

    The report's headings stand in this order: The job, the label's text
    with the identifiers of the job and of its session; Status, the status
    and the reason in one sentence; Cycles and version; What did not match,
    the sentence "The judges agree on every heading." when both judges
    agree, else one subsection per judge with the headings on which it
    disagrees, each with its counts in the two orders of the texts and its
    quoted sentences; The round-trip comparison, equal or not, with the
    first difference; The writer's note, when the record holds one that
    leaves something open; Questions, when the record holds questions; and
    Cost, the language-model tokens charged by role and in total. Every
    sentence is the record's content or a fixed sentence of this module.
    """
    lines = [f"# {REPORT_TITLE}"]
    for heading, body in _report_sections(products_view, label):
        lines += ["", f"## {heading}", "", *body]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# the model folder of AMD-MAT-010 §5


def _json_text(value: object) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False) + "\n"


def _ending(text: str) -> str:
    """The text with one line break at its end."""
    return text if text.endswith("\n") else text + "\n"


def _front_value(value: object) -> str:
    """A value of the front matter in YAML: `null`, an integer, or a text in
    double quotes, which YAML reads as JSON writes it."""
    if value is None:
        return "null"
    if type(value) is int:
        return str(value)
    return json.dumps(str(value), ensure_ascii=False)


def _ended_on(job: dict[str, Any]) -> str:
    """The date on which the job ended, from its `updated_at`, the time of
    its last change, or today's date in UTC when the job holds none."""
    held = job.get("updated_at")
    if isinstance(held, str) and re.match(r"\d{4}-\d{2}-\d{2}", held):
        return held[:10]
    return datetime.now(timezone.utc).date().isoformat()


def _economics_text(job: dict[str, Any], description: str) -> str:
    """`economics.md`: the model prose after a front matter naming the job,
    its label, its session, the version of the session's text it was built
    from and the date it ended."""
    label = job.get("label") if isinstance(job.get("label"), dict) else {}
    version = job.get("revision", label.get("revision"))
    fields = (
        ("job", job.get("id")),
        ("label", label.get("text")),
        ("session", job.get("session")),
        ("version", version),
    )
    lines = ["---", *(f"{key}: {_front_value(value)}" for key, value in fields)]
    lines += [f"date: {_ended_on(job)}", "---"]
    return "\n".join(lines) + "\n\n" + _ending(description)


def _declaration_path(name: str, keys: list[str]) -> str:
    """The path in the model folder of one file of the products, placed by
    its name: a stage file `<key>.bl` under `declaration/stages/<key>/`; a
    methods file `methods.yml` beside the only stage, when the products hold
    one; and every other file, `period.yml`, `trellis.yml`,
    `calibration/<file>`, `settings/<file>` and `stages/<key>/methods.yml`
    among them, under `declaration/` by its name. The note is placed by
    `_folder_texts`."""
    if "/" not in name and name.endswith(".bl"):
        return f"declaration/stages/{name[:-3]}/{name}"
    if name == "methods.yml" and len(keys) == 1:
        return f"declaration/stages/{keys[0]}/methods.yml"
    return f"declaration/{name}"


def _checked_files(files: object, job_id: str, where: str) -> dict[str, str]:
    """The files of a writing by the paths the client writes, each name
    checked by `_relative_name`; a name the client does not write or a file
    without text raises `MatsyaError`."""
    checked: dict[str, str] = {}
    for name, text in (files.items() if isinstance(files, dict) else ()):
        relative = _relative_name(name)
        if relative is None:
            raise MatsyaError(
                f"The record of job {job_id} names a file {name!r} in {where} that the client "
                "does not write: a name must be a plain name, with no folder part and not "
                "beginning with a dot, or calibration/<file>, settings/<file> or "
                "stages/<key>/methods.yml."
            )
        if not isinstance(text, str):
            raise MatsyaError(
                f"The record of job {job_id} holds no text for the file {name!r} in {where}."
            )
        checked[relative] = text
    return checked


def _folder_texts(job: dict[str, Any]) -> dict[str, str]:
    """The model folder of an ended job from the job in the products view
    (AMD-MAT-010 §5), by path within the folder: `economics.md` when the
    record holds model prose, `report.md`, the files of the last cycle under
    `declaration/`, the writer's note when it leaves something open beside a
    single stage as `declaration/stages/<key>/<key>.md` and otherwise as
    `declaration/notes.md`, and `record.json`."""
    job_id = str(job.get("id"))
    record = job["result"]
    texts: dict[str, str] = {}
    description = record.get("description")
    if isinstance(description, str) and description.strip():
        texts[ECONOMICS_FILE] = _economics_text(job, description)
    texts[REPORT_FILE] = report_text(job)
    files = _checked_files(last_cycle_files(record), job_id, "the last cycle's writing")
    keys = [name[:-3] for name in files if "/" not in name and name.endswith(".bl")]
    for name, text in files.items():
        if name == NOTE_FILE:
            if _open_note(files) is None:
                continue
            if len(keys) == 1:
                path = f"declaration/stages/{keys[0]}/{keys[0]}.md"
            else:
                path = "declaration/notes.md"
        else:
            path = _declaration_path(name, keys)
        texts[path] = text
    texts[RECORD_FILE] = _json_text(job)
    return texts


def _cycle_rest(cycle: dict[str, Any]) -> dict[str, Any]:
    """A cycle's record without the three texts that stand beside it in its
    folder: the files of its writing, its round-trip prose and the files of
    its reconstruction."""
    rest = copy.deepcopy(cycle)
    texts = (("writing", "files"), ("prose_writing", "description"), ("reconstruction", "files"))
    for step, entry in texts:
        if isinstance(rest.get(step), dict):
            rest[step].pop(entry, None)
    return rest


def _iterate_texts(full: dict[str, Any]) -> dict[str, str]:
    """The iterates of a job from the job in the full view (AMD-MAT-010
    §5), by path within the folder: for each cycle `n`, under
    `iterates/cycle-<n>/`, the files of its writing, the model prose as
    `model-prose.md`, its round-trip prose as `round-trip-prose.md`, the
    files of its reconstruction under `round-trip/` and the rest of its
    record as `cycle.json`; and the full view as
    `iterates/record-full.json`. The model prose is the record's
    `description`, which every cycle reads unchanged (REQ-MAT-030)."""
    job_id = str(full.get("id"))
    record = full.get("result") if isinstance(full.get("result"), dict) else {}
    description = record.get("description")
    cycles = record.get("cycles") if isinstance(record.get("cycles"), list) else []
    texts: dict[str, str] = {}
    for number, cycle in enumerate(cycles, 1):
        if not isinstance(cycle, dict):
            continue
        folder = f"{ITERATES_FOLDER}/cycle-{number}"
        writing = cycle.get("writing") if isinstance(cycle.get("writing"), dict) else {}
        written = _checked_files(writing.get("files"), job_id, f"the writing of cycle {number}")
        for name, text in written.items():
            texts[f"{folder}/{name}"] = text
        if isinstance(description, str) and description.strip():
            texts[f"{folder}/model-prose.md"] = _ending(description)
        prose = cycle.get("prose_writing")
        if isinstance(prose, dict) and isinstance(prose.get("description"), str):
            texts[f"{folder}/round-trip-prose.md"] = _ending(prose["description"])
        rebuilt = cycle.get("reconstruction")
        rebuilt = rebuilt if isinstance(rebuilt, dict) else {}
        round_trip = _checked_files(
            rebuilt.get("files"), job_id, f"the reconstruction of cycle {number}"
        )
        for name, text in round_trip.items():
            texts[f"{folder}/round-trip/{name}"] = text
        texts[f"{folder}/cycle.json"] = _json_text(_cycle_rest(cycle))
    texts[FULL_RECORD_FILE] = _json_text(full)
    return texts


def _check_paths(paths: list[str], job_id: str) -> None:
    """Refuse two files the client would write at one path, compared
    without regard to case, and a file whose path is a folder of another."""
    held: dict[str, str] = {}
    for path in paths:
        if path.casefold() in held:
            raise MatsyaError(
                f"The record of job {job_id} names two files that the client would write as {path}."
            )
        held[path.casefold()] = path
    for path in paths:
        parts = path.split("/")
        for end in range(1, len(parts)):
            folder = "/".join(parts[:end]).casefold()
            if folder in held:
                raise MatsyaError(
                    f"The record of job {job_id} names a file {held[folder]} and a folder of the "
                    "same name."
                )


def check_folder(folder: str | Path, overwrite: bool = False) -> None:
    """Refuse a folder that `job_files` may not write into: a file, or a
    folder that holds anything when `overwrite` is false. `FileExistsError`
    states why; nothing is written."""
    folder = Path(folder)
    if folder.exists() and not folder.is_dir():
        raise FileExistsError(f"{folder} is a file; name a new or empty folder.")
    if not overwrite and folder.is_dir() and any(folder.iterdir()):
        raise FileExistsError(
            f"{folder} is not empty; name a new or empty folder, or write into it with --overwrite "
            "(overwrite=True in Python), which replaces the files of the same names and leaves the "
            "others."
        )


def _check_targets(folder: Path, paths: list[str]) -> None:
    """Refuse, before anything is written into an existing folder, a path
    that is a folder there or that passes through a file there, and a path
    that is, or passes through, a symbolic link within the folder, whose
    target may lie outside it; every path written resolves within the
    folder."""
    inside = folder.resolve()
    for relative in paths:
        target = folder / relative
        parts = Path(relative).parts
        for end in range(1, len(parts) + 1):
            component = folder.joinpath(*parts[:end])
            if component.is_symlink():
                raise FileExistsError(
                    f"{component} is a symbolic link; the model folder writes no file through a "
                    f"symbolic link, whose target may lie outside {folder}."
                )
        if not target.resolve().is_relative_to(inside):
            raise FileExistsError(f"{target} resolves outside {folder}; nothing is written there.")
        if target.is_dir():
            raise FileExistsError(f"{target} is a folder; the model folder writes a file there.")
        for parent in list(target.parents)[: len(Path(relative).parts) - 1]:
            if parent.exists() and not parent.is_dir():
                raise FileExistsError(
                    f"{parent} is a file; the model folder writes a folder there."
                )


class MatsyaClient:
    """A client of the Matsya service of spec 0.3 for one Matsya token.

    Parameters
    ----------
    token : str
        The Matsya token, ``msy_`` followed by 32 hexadecimal characters. An
        empty text sends no ``Authorization`` header, which the service
        refuses.
    server_url : str
        The service's address, without a route.

    Every method returns the service's JSON answer, except `job_files`,
    which returns the paths it wrote. `last_text` holds the text of the
    service's latest answer as it arrived, which the command prints with
    ``--json``. No message of the client shows the Matsya token.
    """

    def __init__(self, token: str, server_url: str) -> None:
        self.token = token
        self.server_url = server_url.rstrip("/")
        self.last_text = ""
        self._opener = urllib.request.build_opener(_SameHostRedirects(self._hidden))

    def __repr__(self) -> str:
        return f"MatsyaClient(server_url={self.server_url!r})"

    # -- one request

    def _hidden(self, text: str) -> str:
        """The text with the Matsya token replaced, so that no message shows it."""
        return text.replace(self.token, "<Matsya token>") if self.token else text

    def _request(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        """Send one request to the route `path` and return the service's
        JSON answer; a refusal raises `MatsyaError` or one of its subclasses,
        as does a redirect to another scheme, host or port
        (`_SameHostRedirects`)."""
        # imported here, since the package's __init__ imports this module first
        from matsya import __version__

        headers = {"Accept": "application/json", "User-Agent": f"econ-ark-matsya/{__version__}"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        data = None
        if body is not None:
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(
            self.server_url + path, data=data, headers=headers, method=method
        )
        try:
            with self._opener.open(request, timeout=REQUEST_TIMEOUT) as answer:
                text = answer.read().decode("utf-8")
        except urllib.error.HTTPError as error:
            raise self._refusal(error) from None
        except urllib.error.URLError as error:
            raise MatsyaError(
                self._hidden(
                    f"The Matsya service at {self.server_url} could not be reached: {error.reason}."
                )
            ) from None
        except OSError as error:
            raise MatsyaError(
                self._hidden(f"The Matsya service at {self.server_url} did not answer: {error}.")
            ) from None
        self.last_text = text
        try:
            return json.loads(text)
        except ValueError:
            raise MatsyaError(f"The answer of {method} {path} is not JSON.") from None

    def _refusal(self, error: urllib.error.HTTPError) -> MatsyaError:
        """The error for a refused request: its status and the service's own
        message, and for a refused Matsya token (401) how to supply one."""
        try:
            text = error.read().decode("utf-8", "replace")
        except OSError:
            text = ""
        status = error.code
        detail = self._hidden(
            _service_message(text) or str(error.reason or "") or "the service gave no message"
        )
        if status >= 500:
            return ServerError(
                f"The service could not answer ({status}): {_sentence(detail)}", status, detail
            )
        message = f"The service refused the request ({status}): {_sentence(detail)}"
        if status == 401:
            return AuthenticationError(
                f"{message} Run matsya configure to save the Matsya token AAS gave you, "
                "or set MATSYA_TOKEN.",
                status,
                detail,
            )
        if status == 413:
            return ContextTooLargeError(message, status, detail)
        if status == 429:
            held = error.headers.get("Retry-After") if error.headers else None
            retry_after = int(held) if held and held.isdigit() else None
            wait = f" Try again in {retry_after} seconds." if retry_after else ""
            return RateLimitError(message + wait, status, detail, retry_after)
        return MatsyaError(message, status, detail)

    def _wait(
        self,
        read: Callable[[], dict[str, Any]],
        final_states: tuple[str, ...],
        interval: float,
        on_change: Callable[[dict[str, Any]], None] | None,
        timeout: float | None,
        name: str,
    ) -> dict[str, Any]:
        """Call `read` every `interval` seconds until its answer's state is
        final and return that answer; `on_change` receives each answer whose
        state, step or cycle differs from the one before."""
        started = time.monotonic()
        seen = None
        while True:
            answer = read()
            if not isinstance(answer, dict) or "state" not in answer:
                raise MatsyaError(f"The service's answer on {name} holds no state.")
            progress = answer.get("progress") or {}
            observed = (answer["state"], progress.get("step"), progress.get("cycle"))
            if observed != seen:
                seen = observed
                if on_change is not None:
                    on_change(answer)
            if answer["state"] in final_states:
                return answer
            if timeout is not None and time.monotonic() - started >= timeout:
                raise MatsyaError(
                    f"{name} had not ended after {timeout:g} seconds; its state is {answer['state']}."
                )
            time.sleep(interval)

    # -- the index

    def index(self) -> dict[str, Any]:
        """`GET /v1/index`: the digest of the retrieval index the service
        reads, the index's embedding model and the configuration's version."""
        return self._request("GET", "/v1/index")

    def search(
        self,
        query: str,
        limit: int | None = None,
        collections: list[str] | None = None,
        source_ids: list[str] | None = None,
        boosts: dict[str, float] | None = None,
    ) -> dict[str, Any]:
        """`POST /v1/search`: the passages of the index that best match
        `query`, with the index's digest.

        `limit` is the number of passages, from 1 to 20 (the service's
        default is 8); `collections` names the collections searched among
        `repository`, `literature`, `articles`, `hark` and `buffer_stock`
        (the service's default is `repository` and `buffer_stock`);
        `source_ids` restricts the search to the sources named; `boosts`
        multiplies the weight of a collection searched. An argument left at
        `None` is not sent.
        """
        body: dict[str, Any] = {"query": query}
        if limit is not None:
            body["limit"] = limit
        if collections is not None:
            body["collections"] = list(collections)
        if source_ids is not None:
            body["source_ids"] = list(source_ids)
        if boosts is not None:
            body["boosts"] = dict(boosts)
        return self._request("POST", "/v1/search", body)

    def passage(self, passage_id: str, index_digest: str | None = None) -> dict[str, Any]:
        """`GET /v1/passages/{passage_id}`: one passage of the index, or of
        the earlier version of the index that `index_digest` names."""
        path = f"/v1/passages/{_segment(passage_id)}"
        if index_digest is not None:
            path += "?" + urllib.parse.urlencode({"index_digest": index_digest})
        return self._request("GET", path)

    # -- jobs of architect mode

    def submit_job(
        self,
        source_text: str | None = None,
        pdf_path: str | Path | None = None,
        max_cycles: int | None = None,
        session: str | None = None,
        force: bool | None = None,
    ) -> dict[str, Any]:
        """`POST /v1/model-iterations`: start a job of architect mode, and
        return its identifier, its state `queued` and its status route.

        The job reads one of three source materials: `source_text`, a model
        description, sent as ``{"kind": "description", "text": ...}``;
        `pdf_path`, a paper's PDF, sent as ``{"kind": "paper", "pdf_base64":
        ...}``; or `session`, the identifier of a session whose entries the
        service reads when the job starts, with no source sent. `max_cycles`
        limits the cycles of writing and checking. `force` sends the job on
        to writing when preparation ends with questions; every assumption
        Prose-to-Bellman-Sym then supplies is recorded. An argument left at
        `None` is not sent.
        """
        given = [value for value in (source_text, pdf_path, session) if value is not None]
        if len(given) != 1:
            raise ValueError("A job takes exactly one of source_text, pdf_path and session.")
        body: dict[str, Any] = {}
        if source_text is not None:
            body["source"] = {"kind": "description", "text": source_text}
        elif pdf_path is not None:
            encoded = base64.b64encode(Path(pdf_path).read_bytes()).decode("ascii")
            body["source"] = {"kind": "paper", "pdf_base64": encoded}
        else:
            body["session"] = session
        if max_cycles is not None:
            body["max_cycles"] = max_cycles
        if force is not None:
            body["force"] = force
        return self._request("POST", "/v1/model-iterations", body)

    def job(self, job_id: str, view: str = "products") -> dict[str, Any]:
        """`GET /v1/model-iterations/{job_id}?view=...`: a job's state; its
        label (`label`, AMD-MAT-008 §2), whose `text` gives the session's
        name, the version of the session's text the job read, the job's
        number and its state, such as "Household with firms · version 2 ·
        job 7 · running"; whether its cancellation was requested
        (`cancel_requested`); its progress (its step and cycle); its events;
        and, once it has ended, its record under `result` or its error code
        under `error`.

        `view` selects what the answer holds of an ended job's record
        (AMD-MAT-010 §3): `products`, the default, its final products and
        the material of its report, the last cycle's files, judging and
        comparison under `last_cycle` with `cycles_run`, the number of cycles
        run; or `full`, the record as the job store keeps it, every cycle and
        every call among them, which training reads. A job that holds no
        record is answered alike in both views.
        """
        query = urllib.parse.urlencode({"view": view})
        return self._request("GET", f"/v1/model-iterations/{_segment(job_id)}?{query}")

    def wait_job(
        self,
        job_id: str,
        interval: float = 5,
        on_change: Callable[[dict[str, Any]], None] | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Ask for a job's state every `interval` seconds until the job has
        ended, `converged`, `not_converged`, `needs_input`, `cancelled`,
        `failed` or `interrupted`, and return the service's last answer, in
        the products view. `on_change` is called with each answer whose
        state, step or cycle differs from the one before; after `timeout`
        seconds the wait ends with `MatsyaError`."""
        return self._wait(
            lambda: self.job(job_id), JOB_FINAL_STATES, interval, on_change, timeout, f"Job {job_id}"
        )

    def cancel_job(self, job_id: str) -> dict[str, Any]:
        """`POST /v1/model-iterations/{job_id}/cancel`, with no body: cancel
        a job of the user's own (AMD-MAT-008 §4), and return the job as
        `job` returns it.

        A queued job is `cancelled` at once and never runs. A running job is
        returned `running`, with `cancel_requested` true, and stops before
        its next call to the language-model provider: a call already sent
        finishes and is charged, and the job then ends `cancelled` with its
        record, which keeps the usage of the calls it made. A job that has
        ended cannot be cancelled: the service answers 409 with the message
        "The job has ended", raised as `MatsyaError` with `status` 409, as
        every refusal is raised.
        """
        return self._request("POST", f"/v1/model-iterations/{_segment(job_id)}/cancel")

    def job_files(
        self,
        job_id: str,
        folder: str | Path,
        overwrite: bool = False,
        all_iterates: bool = False,
    ) -> list[Path]:
        """Write an ended job's model folder (AMD-MAT-010 §5) into `folder`,
        new or empty, and return the paths written.

        From the products view of the job: `economics.md`, the model prose
        after a front matter naming the job, its session, the version of
        the session's text and the date the job ended; `report.md`, the
        report of `report_text`; under `declaration/`, each stage file
        `<key>.bl` of the last cycle as `stages/<key>/<key>.bl`, the
        writer's note, when it leaves something open, as
        `stages/<key>/<key>.md` beside a single stage and as `notes.md`
        otherwise, and each period, trellis, calibration, settings or
        methods file the products hold, placed by its name; and
        `record.json`, the job as the service returned it in the products
        view. With `all_iterates` true, also, from the full view, which
        training reads, `iterates/cycle-<n>/` for each cycle, holding its
        files, `model-prose.md`, `round-trip-prose.md`, the files written
        from the round-trip prose, the stage files and the writer's note,
        under `round-trip/`, and the rest of the cycle's record as
        `cycle.json`; and `iterates/record-full.json`, the job in the full
        view.

        A folder that holds anything is refused with `FileExistsError`
        before any request, unless `overwrite` is true, which replaces the
        files of the same names and leaves the others. A job that holds no
        record, a record that names a file the client does not write (a
        name with a folder part other than `calibration/<file>`,
        `settings/<file>` or `stages/<key>/methods.yml`, or a name beginning
        with a dot), or two files at one path raise `MatsyaError` before
        anything is written. A path within the folder that is, or passes
        through, a symbolic link is refused with `FileExistsError` before
        anything is written, since the link's target may lie outside the
        folder.
        """
        folder = Path(folder)
        check_folder(folder, overwrite)
        job = self.job(job_id)
        received = self.last_text
        if not isinstance(job.get("result"), dict):
            state = job.get("state")
            if job.get("error"):
                state = f"{state}, error {job['error']}"
            raise MatsyaError(f"Job {job_id} holds no record; its state is {state}.")
        texts = _folder_texts(job)
        if all_iterates:
            texts.update(_iterate_texts(self.job(job_id, view="full")))
            # `--json` prints the products view, the answer `record.json` holds
            self.last_text = received
        paths = list(texts)
        _check_paths(paths, str(job_id))
        _check_targets(folder, paths)
        for relative, text in texts.items():
            path = folder / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        return [folder / relative for relative in paths]

    def start_job(
        self,
        path: str | Path,
        name: str | None = None,
        session: str | None = None,
        no_session: bool = False,
        max_cycles: int | None = None,
        force: bool | None = None,
    ) -> dict[str, Any]:
        """Start a job of architect mode from a file, kept in a session, as
        `matsya job submit <file>` does, and return the service's answers.

        A Markdown or text file is appended as one `user` entry to a new
        session named after the file, its name without the extension, or
        `name`; with `session`, to that existing session. The job is then
        started from the session, with no source sent, so that its
        questions are appended to the session, where the user replies to
        them and asks questions in conversation mode. With `no_session`
        true, the text is sent as the job's source and no session is
        created, so the job's questions stand in its record only. A PDF
        cannot be attached to a session yet, so a paper's PDF is sent as the
        job's source with no session, and `name` or `session` given with a
        PDF is refused. `max_cycles` and `force` are sent as `submit_job`
        sends them.

        The answer is ``{"session": ..., "entry": ..., "job": ...}``: the
        new session's record, or `None` where none was created; the answer
        to the appended entry, the session's listing with `entry`, or
        `None`; and the job's answer, its identifier, its state `queued` and
        its status route. An argument the client refuses raises
        `ValueError`, and a file it cannot read `OSError`, before any
        request. When the service refuses the entry or the job after the
        session was created, the refusal's message names the session.
        """
        if session is not None and no_session:
            raise ValueError("A job takes session or no_session, not both.")
        if name is not None and (session is not None or no_session):
            raise ValueError(
                "name names the session start_job creates, and is not taken with session "
                "or no_session."
            )
        path = Path(path)
        data = path.read_bytes()
        options = {"max_cycles": max_cycles, "force": force}
        if is_pdf(path.name, data):
            if session is not None or name is not None:
                raise ValueError(
                    f"{path} is a PDF, and a PDF cannot be attached to a session yet; submit it "
                    "with no session and no session name, or send the paper's text as a "
                    "Markdown or text file."
                )
            return {"session": None, "entry": None, "job": self.submit_job(pdf_path=path, **options)}
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            raise ValueError(f"{path} is not text in UTF-8.") from None
        if not text.strip():
            raise ValueError(f"{path} holds no text.")
        if no_session:
            return {"session": None, "entry": None, "job": self.submit_job(source_text=text, **options)}
        created = None
        if session is None:
            created = self.new_session(path.stem if name is None else name)
            session = created["id"]
        entry = None
        try:
            entry = self.add_entry(session, text)
            job = self.submit_job(session=session, **options)
        except MatsyaError as error:
            # what the session received stays in it, and the message names it
            if entry is not None:
                held = (
                    f"Session {session} holds the text of {path} as entry "
                    f"{entry['entry']['number']}, and no job was started from it; start one "
                    f"with: matsya job submit --session {session}"
                )
            elif created is not None:
                held = f"Session {session} was created and holds no entry."
            else:
                raise
            error.args = (f"{error} {held}",)
            raise
        return {"session": created, "entry": entry, "job": job}

    # -- sessions

    def new_session(self, name: str) -> dict[str, Any]:
        """`POST /v1/sessions`: a new session of this name, with no entries."""
        return self._request("POST", "/v1/sessions", {"name": name})

    def add_entry(
        self,
        session_id: str,
        text: str | None,
        kind: str = "user",
        replies_to: int | None = None,
        delivery_id: str | None = None,
    ) -> dict[str, Any]:
        """`POST /v1/sessions/{session_id}/entries`: append one entry, and
        return the session's listing with the entry appended (`entry`),
        whether the delivery was repeated (`repeated`) and the preparation
        attempt the entry started (`scheduled`, or `None`).

        `kind` is `user`, text the user writes; `paper`, the text of a paper;
        or `acceptance`, which holds no text (`text` is `None`) and names in
        `replies_to` the number of the `answer` entry it accepts. A `user`
        entry whose `replies_to` names a question of a job awaiting an answer
        starts that job's next preparation attempt. A request with a
        `delivery_id` the session already holds appends nothing and returns
        the entry held.
        """
        body: dict[str, Any] = {"kind": kind}
        if text is not None:
            body["text"] = text
        if replies_to is not None:
            body["replies_to"] = replies_to
        if delivery_id is not None:
            body["delivery_id"] = delivery_id
        return self._request("POST", f"/v1/sessions/{_segment(session_id)}/entries", body)

    def session(self, session_id: str) -> dict[str, Any]:
        """`GET /v1/sessions/{session_id}`: the session's numbered entries,
        its revision, the job awaiting an answer, its selected job
        (`selected_job`, or `None`), its jobs in the order they were
        created, each as `{"id", "state", "revision", "current", "label"}`
        (AMD-MAT-008 §4), and its turns."""
        return self._request("GET", f"/v1/sessions/{_segment(session_id)}")

    def select_job(self, session_id: str, job_id: str | None) -> dict[str, Any]:
        """`POST /v1/sessions/{session_id}/selected-job`: make the job
        `job_id`, a job of the session that holds a record, the session's
        selected job, whose outputs a question asked in the session reads
        (AMD-MAT-008 §4); `None` clears the selection, and a question then
        reads the session's latest current job that holds a record. Returns
        the session's listing, as `session` does. The end of a job never
        changes the selection."""
        return self._request(
            "POST", f"/v1/sessions/{_segment(session_id)}/selected-job", {"job": job_id}
        )

    # -- turns of conversation mode

    def turn(self, session_id: str, turn_id: str) -> dict[str, Any]:
        """`GET /v1/sessions/{session_id}/turns/{turn_id}`: a turn's state,
        `queued`, `running`, `finished`, `failed` or `interrupted`, its
        progress and, once it is finished, its record."""
        return self._request(
            "GET", f"/v1/sessions/{_segment(session_id)}/turns/{_segment(turn_id)}"
        )

    def wait_turn(
        self,
        session_id: str,
        turn_id: str,
        interval: float = 2,
        on_change: Callable[[dict[str, Any]], None] | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Ask for a turn's state every `interval` seconds until it is
        `finished`, `failed` or `interrupted`, and return the service's last
        answer; `on_change` and `timeout` act as in `wait_job`."""
        return self._wait(
            lambda: self.turn(session_id, turn_id),
            TURN_FINAL_STATES,
            interval,
            on_change,
            timeout,
            f"Turn {turn_id}",
        )

    def ask(
        self,
        session_id: str,
        question: str,
        stage_file_path: str | Path | None = None,
        index_digest: str | None = None,
        delivery_id: str | None = None,
        interval: float = 2,
        on_change: Callable[[dict[str, Any]], None] | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Ask one question in a session and return the turn once it has
        ended.

        `POST /v1/sessions/{session_id}/turns` appends the question as an
        entry and starts the turn; the turn is then read every `interval`
        seconds until it has ended (`wait_turn`). A finished turn holds its
        record, whose `result` holds the status (`answered`, `needs_input`
        or `incomplete`), the answer, the citations, Matsya's questions,
        `job`, the identifier and label of the job whose outputs the turn
        read without a request, `{"id", "label"}`, or `None`, and
        `job_started`, the identifier and label of the job the turn started
        from the session at the user's request in the question, or `None`
        (AMD-MAT-009 §3); `wait_job` and `job_files` follow that job.
        `stage_file_path` names a stage file whose text is sent with the
        question; the service elaborates it, and the conversation role reads
        its dossier and never its text. `index_digest` names an earlier
        version of the index to read; a repeated request with the same
        `delivery_id` returns the turn already asked.
        """
        body: dict[str, Any] = {"question": question}
        if stage_file_path is not None:
            body["stage_file"] = Path(stage_file_path).read_text(encoding="utf-8")
        if index_digest is not None:
            body["index_digest"] = index_digest
        if delivery_id is not None:
            body["delivery_id"] = delivery_id
        asked = self._request("POST", f"/v1/sessions/{_segment(session_id)}/turns", body)
        return self.wait_turn(
            session_id, asked["id"], interval=interval, on_change=on_change, timeout=timeout
        )
