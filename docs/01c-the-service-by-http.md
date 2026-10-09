---
title: Reaching the service by HTTP
audience: user
type: user-guide
topic: [matsya]
---

# Reaching the service by HTTP

> [!summary]
> The commands of matsya-client send their requests to the Matsya service over HTTP, the protocol of the web, and print its answers, and a reader without Python, or a program written in any language, can send the same requests directly. This page lists every **route** of the service, that is, every kind of request, named by an HTTP method and a path, with the body the request sends and the answer it receives. It says how the Matsya token travels with each request and how the service refuses a request, and it gives a `curl` example for each kind of request: the index, a search, a job from a description, a job's record, a session, an entry, a question and its answer, a cancellation and the selected job. For each route it names the command of matsya-client that sends the same request.

> [!info]- Relationship with other documents
> **Builds on** — [Matsya in three parts](index.md), which defines the session, the job and the turn; [Working with Matsya from the command line](01-working-from-the-command-line.md), whose commands send the requests of this page.
> **See also** — [Collections and weights](01d-collections-and-weights.md), the fields of a search and what a returned passage holds; [The Python module and the files the client writes](01a-the-python-module.md), the same requests as Python functions.
> **Explained for developers in** — the [Matsya developer guide](../dev-guide/index.md), which describes the program that answers each route.

## 1 The address, the Matsya token and the examples

The service's administrator gives you two things: the service's address, a URL, and your **Matsya token**, the password-less identifier, `msy_` followed by 32 hexadecimal characters, that the service checks on every request under `/v1/`. Every session, job and turn you create belongs to you, and the service answers a request for another person's as though it did not exist (§3).

The examples on this page read the two from environment variables, the same two that the command `matsya` reads, so that a terminal set up for the examples serves the command as well:

```sh
export MATSYA_SERVER="<the service's address, without a final slash>"
export MATSYA_TOKEN="$(cat <the private file that holds your Matsya token>)"
```

Keep the Matsya token in a file that only you can read and that stands outside every folder under version control; reading the variable from that file keeps the Matsya token out of the shell's history.

Every request to a route under `/v1/` carries the Matsya token in the `Authorization` header, after the word `Bearer` and one space:

```text
Authorization: Bearer msy_…
```

A request with a body sends one object in JSON, the text format of named fields and lists that the service reads and writes, with the header `Content-Type: application/json`, and every answer is one JSON object. The examples use `curl`, the command-line program for HTTP requests that most systems install, in version 7.76 or later. Its option `-sS` hides the progress display and keeps `curl`'s own error messages, and `--fail-with-body` prints the service's answer to a refused request and makes `curl` exit with a nonzero status. An answer arrives on one line; a JSON viewer, or `python3 -m json.tool` where Python is installed, prints it with one field per line.

The first request checks the address and the Matsya token:

```sh
curl --fail-with-body -sS "$MATSYA_SERVER/v1/index" \
  -H "Authorization: Bearer $MATSYA_TOKEN"
```

The answer names the version of the **retrieval index**, the store of passages from which a search returns those that match a query ([Collections and weights](01d-collections-and-weights.md)), by its **digest**, a 64-character code computed from the index's contents, which changes whenever the contents change; the identity of the embedding model, the model that turns each passage into a vector of numbers for the search; and the version of the configuration, the instruction texts and settings under which the service runs:

```json
{"index_digest":"…","embedding_model_id":"…","configuration_version":"…"}
```

`matsya index` sends the same request.

## 2 The routes

A part of a path in braces stands for an identifier that an earlier answer gave: the `id` of a session, a job or a turn, 32 hexadecimal characters, or the `passage_id` of a passage, 64 hexadecimal characters. A **query parameter** is a named value written into the address after the path, following `?`, in the form `name=value`, as in `/v1/model-iterations/<job>?view=full`.

| Method and path | Body | Answer | The same request from matsya-client |
|---|---|---|---|
| `GET /v1/index` | none | the index's digest, the embedding model's identity and the configuration's version | `matsya index` |
| `POST /v1/search` | a search: `query`, and optionally `collections`, `limit`, `source_ids` and `boosts`; at most 16 KiB | `index_digest` and `passages`, the passages that best match the query | `matsya search` |
| `POST /v1/answer` | the body of a search | one sentence copied from a matching passage, with its evidence, or none | none |
| `GET /v1/passages/{passage_id}` | none; the query parameter `index_digest` is optional | one passage | the function `passage` of the Python module |
| `POST /v1/sessions` | `{"name": …}`; at most 16 KiB | 201 and the new session | `matsya session new` |
| `GET /v1/sessions/{session_id}` | none | the session: its entries, the version of its text, its jobs and its turns | `matsya session show` |
| `POST /v1/sessions/{session_id}/entries` | one entry: `text`, `kind`, `replies_to`, `delivery_id`; at most 24 MiB | the session, with the entry appended | `matsya session add` |
| `POST /v1/sessions/{session_id}/selected-job` | `{"job": …}`; at most 16 KiB | the session | `matsya session select` |
| `POST /v1/sessions/{session_id}/turns` | a question; at most 256 KiB | 202, the turn's identifier and route | `matsya ask` |
| `GET /v1/sessions/{session_id}/turns/{turn_id}` | none | the turn, with its record once it has finished | `matsya ask`, while it waits |
| `POST /v1/model-iterations` | a job's request; at most 24 MiB | 202, the job's identifier and route | `matsya job submit` |
| `GET /v1/model-iterations/{job_id}` | none; the query parameter `view` is optional | the job, with its record once it has ended | `matsya job status`, `matsya job wait` |
| `POST /v1/model-iterations/{job_id}/cancel` | none | the job | `matsya job cancel` |

An answer has the status 200 unless the table names another. The service also answers `GET /healthz` with `{"status":"ok"}`, without a Matsya token; that route serves the administrator's check on the server itself, since the address the administrator gives passes only the routes under `/v1/` to the service.

Where the table names a command of matsya-client, the command sends the same request, and its option `--json` prints the service's answer as it arrived.

## 3 Refusals

The service answers a refused request with one field, `{"detail": "<a sentence>"}`, whose sentence states the fault, and one of these statuses:

| Status | When the service answers it |
|---|---|
| 401 | The `Authorization` header holds no Matsya token, or one that the service does not hold or has revoked. Check the Matsya token the administrator gave you, and ask the administrator if the service refuses it. |
| 403 | A search or an answer names a collection that your Matsya token is not granted; the sentence is `Collection access is not granted` ([Collections and weights](01d-collections-and-weights.md) §2). |
| 404 | The session, job, turn or passage does not exist or is not yours; the service does not distinguish the two cases. A passage also receives 404 when your Matsya token may not read its collection, or when the service no longer keeps the version of the index that the request names. A question also receives 404 when the service offers no turns of conversation mode, or when it keeps no version of the index with the digest the question names. |
| 409 | A cancellation names a job that has ended; the sentence is `The job has ended`. |
| 413 | The body exceeds the route's limit (§2), or a paper's PDF exceeds 16 MiB. |
| 415 | A body was sent without the header `Content-Type: application/json`. |
| 422 | The request is malformed: a field that the route does not know, a value outside its range, a view other than `products` or `full`, or an entry, a selection or a job that the session cannot hold, such as a reply that names an entry that is not a question. |
| 503 | The service cannot read its database of Matsya tokens, or holds no retrieval index. Report the route and the answer to the administrator. |

When the service refuses a request that a command of matsya-client sent, the command prints the sentence and exits with status 1.

## 4 The index, a search and a passage

A search sends a query and receives the passages of the index that best match it:

```sh
curl --fail-with-body -sS -X POST "$MATSYA_SERVER/v1/search" \
  -H "Authorization: Bearer $MATSYA_TOKEN" \
  -H "Content-Type: application/json" \
  --data '{"query": "decision perch state and controls", "collections": ["repository"], "limit": 4}'
```

The answer is `{"index_digest": "…", "passages": [ … ]}`, with the passages in the order of their scores, each with its identifier, its source, its location, its text and its scores. [Collections and weights](01d-collections-and-weights.md) gives the fields of the request (§3), how the passages are ranked (§4) and what a passage holds (§5). `matsya search "decision perch state and controls" --collections repository --limit 4` sends the same request.

`POST /v1/answer` takes the same body and answers with one sentence copied from a retrieved passage whose words match the query's, or with none. No language model is called, and nothing is paraphrased:

```json
{"answer": "…", "method": "extractive", "index_digest": "…", "passage_ids": ["…"],
 "evidence": [{"passage_id": "…", "excerpt": "…", "source_id": "…", "title": "…",
               "path": "…", "location": {"…": "…"}, "authority": "…"}],
 "explanation": "The answer quotes retrieved source text. No model checked the economics."}
```

When no short sentence matches, `answer` is `null`, `evidence` is empty and the explanation says that no matching excerpt was found. The explanation of a sentence taken from a PDF, or from a transcription or a secondary reading of an article, asks you to compare its claims with the page of the PDF before you accept them.

A passage is read again by its identifier:

```sh
curl --fail-with-body -sS "$MATSYA_SERVER/v1/passages/<passage_id>?index_digest=<index_digest>" \
  -H "Authorization: Bearer $MATSYA_TOKEN"
```

Without `index_digest`, the route reads the index the service reads now. With it, the route reads the version of the index that the digest names, so that a passage cited from an earlier version can be read again, as long as the service keeps that version and your Matsya token may read the passage's collection. The answer is the passage as a search returns it, without the scores.

## 5 A job

A job's request is one JSON object with a source and, optionally, the fields that shape the job. The roles that the table names are described in [The roles of Matsya and when to use them](01b-the-roles-and-when-to-use-them.md) §1.

| Field | What it gives |
|---|---|
| `source` | the source material, in one of three forms: `{"kind": "description", "text": "…"}`, a model's description in prose and displayed equations; `{"kind": "paper", "pages": [{"page": 1, "text": "…"}, …]}`, a paper as the texts of its pages, numbered by positive, increasing integers; or `{"kind": "paper", "pdf_base64": "…"}`, a paper's PDF file of at most 16 MiB in base64, the encoding of a file's bytes as text, from which the service extracts the text of each page |
| `session` | in place of `source`, the identifier of a session, whose text the job reads when it starts (§6) |
| `max_cycles` | the most cycles of writing and checking: a positive integer, by default the configuration's cycle limit, three at present, and at most the configuration's maximum, five at present |
| `force` | `true` sends the job on to writing when preparation, the step of the Model-prose-writer, ends with questions, which then stand in its record; without it, such a job ends `needs_input` |
| `starting_declaration` | files that the first cycle checks in place of the first writing by Prose-to-Bellman-Sym: an object that maps file names, `<name>.bl` for a stage file, `period.yml`, `trellis.yml` or `note.md`, to the files' texts; files that the elaborator, the program that checks stage files, refuses go back to Prose-to-Bellman-Sym for repair |
| `target_formulation` | a sentence of at most 500 characters that names the one formulation to write, when the source states several |
| `model_key`, `source_cluster` | two labels in lowercase letters, digits and hyphens, sent together, that name the groups of indexed sources the job must not read ([Collections and weights](01d-collections-and-weights.md) §6) |

A request that holds both `source` and `session`, or neither, or a field outside this table, is refused with 422. The source's text, a paper's included, is sent to the language-model provider, so ask the service's administrator before you submit a paper that may not leave your machine. Text that the service extracts from a PDF can lose mathematics; the form with page texts that you have checked avoids that loss.

Write the request into a file, `request.json`:

```json
{
  "source": {
    "kind": "description",
    "text": "A household lives forever with discount factor beta. It holds cash on hand m. It consumes c in [0, m] and saves a = m - c. Next period m = R a + y, with y iid lognormal, mean one, standard deviation sigma. Utility is CRRA with risk aversion rho. It maximizes expected discounted utility."
  },
  "max_cycles": 1
}
```

and send it:

```sh
curl --fail-with-body -sS -X POST "$MATSYA_SERVER/v1/model-iterations" \
  -H "Authorization: Bearer $MATSYA_TOKEN" \
  -H "Content-Type: application/json" \
  --data-binary @request.json
```

The answer, with the status 202, gives the job's identifier and the route of its record:

```json
{"id":"<job>","state":"queued","status_url":"/v1/model-iterations/<job>"}
```

`matsya job submit model.md --no-session --max-cycles 1` sends the same request for the description kept in the file `model.md`. Without `--no-session`, the command first creates a session, appends the file's text to it and starts the job from the session (§6).

The job is read from its route:

```sh
curl --fail-with-body -sS "$MATSYA_SERVER/v1/model-iterations/<job>" \
  -H "Authorization: Bearer $MATSYA_TOKEN"
```

The answer holds the job's `state`: `queued`, `running`, and at its end `converged`, `not_converged`, `needs_input`, `cancelled`, `failed` or `interrupted`. It holds the job's `label`, whose `text` names the session, the version of the session's text the job read, the job's number in the session and its state, such as `a household · version 1 · job 1 · running`, and is the state alone for a job of no session; `cancel_requested`, whether you asked to cancel the job; `progress`, the step the job has reached, `preparation`, `writing`, `prose_writing`, `judging` or `reconstruction`, with its cycle; and `events`, the records of the job's calls of language models, each with the role called, the size and digest of its message, the counts of **language-model tokens**, the pieces of text that the provider of the language model counts and charges for, and any failure, but no text. A job of a session also holds `session`; once it has started, `revision` and `entry_numbers`, the version of the text it read and the numbers of the entries it read; and at its end `current`, whether the text stayed at that version while it ran. A job that matsya-master started at your request names that turn under `started_by`.

A job runs for minutes. Read its route again every half minute until its state is neither `queued` nor `running`; `matsya job wait <job>` does this and prints each new step. In a shell without Python, this loop waits and then prints the job:

```sh
JOB="<job>"
while curl --fail-with-body -sS "$MATSYA_SERVER/v1/model-iterations/$JOB" \
    -H "Authorization: Bearer $MATSYA_TOKEN" | grep -Eq '"state": *"(queued|running)"'; do
  sleep 30
done
curl --fail-with-body -sS "$MATSYA_SERVER/v1/model-iterations/$JOB" \
  -H "Authorization: Bearer $MATSYA_TOKEN"
```

Once the job has ended, its record stands under `result`, in one of two views, which the query parameter `view` selects. The default view, `products`, gives the products of the job and the material of its report:

- `status` and `reason`, the outcome and why the job stopped, such as `source_agreement_and_semantic_fixed_point`, `cycle_limit_reached` or `token_ceiling_reached`;
- `description`, the model prose, and `questions`;
- `paper_source_check`, the reports of the prose-source-judge, and `paper_form_check`, the check of the model prose's headings and length;
- `cycles_run`, the number of cycles run, and `last_cycle`: under `files` the stage files of the last cycle, under `judging` the reports of the prose-roundtrip-judge, under `comparison` whether the files written from the round-trip prose equal the written ones (`equal`) and their first difference, under `citations_supported` whether every block of the stage files quotes the model prose and every quoted sentence occurs in it, and under `unresolved_note` whether `note.md`, the note in which Prose-to-Bellman-Sym states what it could not resolve, leaves something open;
- `reading`, the digests of the index read and of the reference guides given to the roles;
- `usage`, the language-model tokens charged to each role and to the job, the number of calls of each role, and the refusal, when a ceiling refused a call.

The roles and the two kinds of prose are described in [The roles of Matsya and when to use them](01b-the-roles-and-when-to-use-them.md). The view `full` gives the whole record, as training reads it: every cycle with its writing rounds, files, round-trip prose, judging and comparison; every call; the record of what each role read; `continues`, the earlier job of the same session that this job continues, by its identifier, its status and the digest of its source, or `null`; the versions of the program and of the configuration; and, for a converged job, `artifacts`, the files of a model folder:

```sh
curl --fail-with-body -sS "$MATSYA_SERVER/v1/model-iterations/<job>?view=full" \
  -H "Authorization: Bearer $MATSYA_TOKEN"
```

`matsya job status <job>` reads the default view, and `matsya job files <job> <folder> --all-iterates` reads the full view as well. A failed job holds no record, and its `error` names a fixed code: for instance `provider_error`; `prompt_too_long`, a message longer than its role's limit or the language model's context window; `provider_rejected_request`, a message that the language-model provider rejected without processing it; `invalid_request`, a source the service could not read; or `configuration_refused`, with the part refused under `error_detail`. A job that a restart of the service interrupted holds the code `server_restarted`.

A converged job has passed the service's checks, among them that the stage files written again from the round-trip prose have the same elaboration as the written ones and that the prose-roundtrip-judge finds the round-trip prose in agreement with the model prose. Whether the model is the one you meant is for you to judge. Its files are proposals: the service writes nothing on your machine, and `matsya job files` writes them only into the folder you name. Keep a job's identifier with its result, since the administrator needs it to trace a failure or an unexpected answer.

A queued or running job is cancelled through its route `cancel`, with no body:

```sh
curl --fail-with-body -sS -X POST "$MATSYA_SERVER/v1/model-iterations/<job>/cancel" \
  -H "Authorization: Bearer $MATSYA_TOKEN"
```

A queued job ends `cancelled` at once and never runs. A running job is marked `cancel_requested` and stops before its next call to the language-model provider: a call already sent finishes and is charged, and the job then ends `cancelled`, keeping its record with the usage of the calls it made. The answer is the job as its route gives it. A job that has ended cannot be cancelled: the service answers 409 with `{"detail":"The job has ended"}`. `matsya job cancel <job>` sends the same request.

## 6 Sessions, entries and the selected job

A session is created with its name, a text of at most 200 characters:

```sh
curl --fail-with-body -sS -X POST "$MATSYA_SERVER/v1/sessions" \
  -H "Authorization: Bearer $MATSYA_TOKEN" \
  -H "Content-Type: application/json" \
  --data '{"name": "a household"}'
```

The answer, with the status 201, is the session as its route gives it: its `id` and `name`; `entries`, its numbered entries; `revision`, the version of its text, which is the number of its last entry of the kind `user`, `paper` or `acceptance`; `awaiting_answer`, the job whose questions await your reply, or `null`; `selected_job`; `jobs`, each with its `id`, `state`, `revision`, `current` and `label`, in the order they were created; and `turns`, the identifiers of the turns asked in it. `matsya session new "a household"` sends the same request. The session is read from its route, as `matsya session show <session>` reads it:

```sh
curl --fail-with-body -sS "$MATSYA_SERVER/v1/sessions/<session>" \
  -H "Authorization: Bearer $MATSYA_TOKEN"
```

An entry is appended with its text:

```sh
curl --fail-with-body -sS -X POST "$MATSYA_SERVER/v1/sessions/<session>/entries" \
  -H "Authorization: Bearer $MATSYA_TOKEN" \
  -H "Content-Type: application/json" \
  --data '{"text": "A household saves out of cash on hand and faces a risky income."}'
```

The body holds `text`; `kind`, which is `user` by default, `paper` for the text of a paper, or `acceptance`; `replies_to`, the number of the entry it answers; and `delivery_id`, a name of 1 to 64 characters, with which a repeated request returns the entry already stored and appends nothing. A reply, of the kind `user` or `paper`, names a question of Matsya in `replies_to`. An acceptance holds no text and names in `replies_to` the answer of matsya-master it accepts; only an accepted answer enters the text that a later job reads. A reply of the kind `user` to a question of the job that the session awaits starts that job's next attempt at once.

The answer is the session with three more fields: `entry`, the entry as stored, with its `number`, `kind`, `text`, `origin`, `replies_to` and the time it was appended, where `origin` names the job or the turn that wrote an entry of Matsya and is `null` for yours; `repeated`; and `scheduled`, the identifier and route of the job that a reply started, or `null`. `matsya session add <session> notes.md` sends the same request, with `--kind`, `--replies-to` and `--delivery-id` for the other fields.

A job is started from the session's text by naming the session in place of a source:

```sh
curl --fail-with-body -sS -X POST "$MATSYA_SERVER/v1/model-iterations" \
  -H "Authorization: Bearer $MATSYA_TOKEN" \
  -H "Content-Type: application/json" \
  --data '{"session": "<session>"}'
```

The job reads the session's entries up to the version of the text at the moment it starts, an answer of matsya-master among them only when you have accepted it, and a session that holds no text is refused with 422. `matsya job submit --session <session>` sends the same request.

The **selected job** is the job of the session that matsya-master discusses; when none is selected, matsya-master discusses the latest job of the session that holds a record, was not cancelled and ran while the text did not change. The selection names a job of the session that holds a record, and `null` clears it:

```sh
curl --fail-with-body -sS -X POST "$MATSYA_SERVER/v1/sessions/<session>/selected-job" \
  -H "Authorization: Bearer $MATSYA_TOKEN" \
  -H "Content-Type: application/json" \
  --data '{"job": "<job>"}'
```

The answer is the session. A job of another session, or one that holds no record, is refused with 422. `matsya session select <session> <job>` sends the same request, and `matsya session select <session> --none` sends `{"job": null}`.

## 7 A question in a session

A question is asked in a session and answered in a turn of matsya-master:

```sh
curl --fail-with-body -sS -X POST "$MATSYA_SERVER/v1/sessions/<session>/turns" \
  -H "Authorization: Bearer $MATSYA_TOKEN" \
  -H "Content-Type: application/json" \
  --data '{"question": "What does the decision perch of a stage hold?"}'
```

The body is one JSON object of at most 256 KiB. It holds `question`, of at most 8,000 characters, and optionally:

- `stage_file`, the text of one stage file, which the service elaborates so that the language model reads its **dossier**, the printed account of what the file declares, and never the file's text;
- `refusal`, `timing` and `package_version`, material of your own: the elaborator's refusal of a file of yours, the timing of your model and the version of the `bellman` package you use (at most 200 characters), each placed in the language model's message under its name;
- `index_digest`, the digest of an earlier version of the index to read, as an earlier turn's record names it;
- `delivery_id`, a name of 1 to 64 characters, with which a repeated request returns the turn already asked.

The question is appended to the session as an entry, and the answer, with the status 202, is

```json
{"id":"<turn>","state":"queued","question":4,"repeated":false,"status_url":"/v1/sessions/<session>/turns/<turn>"}
```

where `question` is the number of your question's entry. The turn is read from its route:

```sh
curl --fail-with-body -sS "$MATSYA_SERVER/v1/sessions/<session>/turns/<turn>" \
  -H "Authorization: Bearer $MATSYA_TOKEN"
```

Its `state` is `queued` or `running`, and at its end `finished`, `failed` or `interrupted`; a turn takes about a minute, so read the route again every ten seconds until it has ended. A finished turn holds its `record`, whose `result` gives:

- `status`: `answered`; `needs_input`, with Matsya's questions in `questions`; or `incomplete`, with the reason in `reason` and an answer of two fixed sentences, for instance when the requests for further material allowed in one turn were used up or a call would have passed the turn's ceiling of language-model tokens;
- `answer` and `citations`, each citation with the quoted sentence, the identity, path, heading and location of the material it quotes, and the digest of the index read;
- `passages`, the material given to the language model, by identity, path and location;
- `job`, the job whose outputs the turn read, by its identifier and label, or `null`;
- `job_started`, the job that the turn started when you asked for one, by its identifier and label, or `null`;
- `current`, whether you added no entry to the session while the question was answered.

The record's `usage` gives the language-model tokens charged in the turn, by role and in total, and the ceilings in force. A failed turn names under `error` the code `configuration_refused`, `processing_failed` or `worker_unavailable`, and a turn that a restart of the service interrupted names `server_restarted`. The answer, or Matsya's questions, are appended to the session as entries of the kind `answer` or `question` that reply to your question's entry. `matsya ask <session> "<question>"` sends the same question, waits for the turn and prints the answer; its options `--stage-file` and `--index-digest` send the fields of those names.
