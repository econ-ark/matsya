---
title: The Python module and the files the client writes
audience: user
type: user-guide
topic: [matsya]
---

# The Python module and the files the client writes

> [!summary]
> The package `econ-ark-matsya` is also a Python module, `matsya`, with one function for each command that sends a request to the service, reading the same configuration and returning the service's JSON answer. This page gives the module's functions and the exact files `matsya job files` writes, with the report's headings, for a reader who scripts the client or reads its output by program. The commands themselves are in [Working with Matsya from the command line](01-working-from-the-command-line.md).

> [!info]- Relationship with other documents
> **Builds on** — [Matsya in three parts](index.md) and [Working with Matsya from the command line](01-working-from-the-command-line.md).

## 1 The module

The module `matsya` holds the same operations as functions, which read the same configuration and return the service's JSON answer, except `job_files`, which returns the paths it wrote, and `start_job`, which returns the service's answers to its requests as `{"session": ..., "entry": ..., "job": ...}`, with `None` for a session it did not create or an entry it did not append. The functions correspond to the commands as follows: `index` to `matsya index`, `search` to `matsya search`, `start_job` to `matsya job submit <file>`, `submit_job` to `matsya job submit --session <session>` with no file, the job's request alone, or, given a description's text as `source_text` in place of `session`, to `matsya job submit --no-session <file>`, or, given a paper's text as `source_text` with `paper=True`, to `matsya job submit --paper --no-session <file>`, `job` to `matsya job status`, which takes `view`, `products` by default or `full`, the complete record, `wait_job` to `matsya job wait`, `job_files` to `matsya job files`, which takes `overwrite` and `all_iterates`, `cancel_job` to `matsya job cancel`, `new_session` to `matsya session new`, `add_entry` to `matsya session add`, `session` to `matsya session show`, `select_job` to `matsya session select`, with the job `None` for `--none`, and `ask` to `matsya ask`, which returns the turn, whose `turn["record"]["result"]["job_started"]` names the job the turn started, or is `None`; the function `passage`, which returns one passage of the index by its identifier, and `report_text`, which composes `report.md` from a job as `record.json` holds it and sends no request, have no command. A request the service refuses raises `MatsyaError`, whose `status` holds the HTTP status of the service's answer and `detail` its message: for `cancel_job` of a job that has ended, 409 and `The job has ended`. `MatsyaClient(token, server_url)` holds them as methods for a Matsya token and a service address given explicitly.

```python
import matsya

started = matsya.start_job("model.md", target="stage")
job = matsya.wait_job(started["job"]["id"])
print(matsya.report_text(job))
matsya.job_files(job["id"], "proposed-model")
```

The requests themselves, with `curl` examples for a user without Python, are in [Reaching the service by HTTP](01c-the-service-by-http.md).

## 2 The model folder and the report

A job returns by default its final products and the material of its report: the files of its last cycle, its model prose, its questions, the reports of its two judges, the verdict of the last cycle's round-trip comparison with its first difference, and the language-model tokens charged by role and in total. The iterates, the rest of the record, which holds every cycle's writing rounds and files, round-trip prose, judging, reconstruction and comparison profile, every call and the record of what the roles read, stay on the server, which keeps each job's complete record and returns it whole on request, as training reads it.

`matsya job files <job> <folder>` writes an ended job's products into a new or empty folder, in the layout of the model folders of the project's applications:

```text
proposed-model/
├── economics.md              the model prose, after a front matter naming the job, its label, the session,
│                             the version of the session's text and the date the job ended
├── report.md                 the report
├── record.json               the job as the service returned it, in the products view
└── declaration/
    ├── period.yml            a period or trellis file, when the job wrote one
    ├── trellis.yml
    ├── calibration/, settings/   calibration and settings files, when the job wrote them
    └── stages/<key>/
        ├── <key>.bl          each stage file of the last cycle, <key> its name without the extension
        ├── <key>.md          the writer's note, when it leaves something open, beside a single stage
        └── methods.yml       a stage's methods file, when the job wrote one
```

With several stages, the writer's note stands as `declaration/notes.md`. A note that reads `none` leaves nothing open and is not written, and a record without model prose, such as that of a job that stopped in preparation with questions, writes no `economics.md`. A folder that holds anything is refused before any request unless `--overwrite` is given, which replaces the files of the same names and leaves the others. A record that names a file the client would write outside the folder is refused, and nothing is written.

`report.md` is composed by the client, a program with no language model, from the record alone: every sentence is the record's content or a fixed sentence, and nothing is paraphrased. Its headings stand in this order: **The job**, the job's label with the identifiers of the job and of its session; **Status**, the status and the reason in one sentence; **Cycles and version**, the number of cycles run and the version of the session's text the job was built from; **What did not match**, the sentence "The judges agree on every heading." when the prose-source-judge and the prose-roundtrip-judge both agree, and otherwise one subsection per judge with each heading on which it disagrees, its counts of omissions, additions and contradictions in both orders of the two texts and the sentences it quotes, followed by the form check of the model prose when it failed and by the stage files' quotations when a block quotes a sentence that does not occur in the model prose, quotes none, or the stage files hold no block; **The round-trip comparison**, whether the stage files written from the round-trip prose equal the written ones, with the first difference when they do not; **The writer's note**, when it leaves something open; **Questions**, when the record holds questions, which are those of a job that ended `needs_input` or those its preparation asked when the job was submitted with `--force`, the option that sends a job on to writing despite them; and **Cost**, the language-model tokens charged to each role and to the job, with the refusal at a ceiling when one stopped the job.

`--all-iterates`, which is for training, adds every iterate, read from the full view of the record: for each cycle `<n>`, `iterates/cycle-<n>/` holds the files of its writing, the model prose as `model-prose.md`, its round-trip prose as `round-trip-prose.md`, the files written from the round-trip prose, the stage files and the writer's note, under `round-trip/`, and the rest of the cycle's record, its judging and its comparison among it, as `cycle.json`; and `iterates/record-full.json` holds the job with its complete record.

```sh
matsya job files <job> proposed-model-iterates --all-iterates
```

## 3 The commands in detail

A job of architect mode turns a model description into proposed stage files, the Bellman-SYM files (`.bl`) that declare a model's stages, and checks them. Write the description in a Markdown or text file, submit it, wait for the job to end, and write its model folder, the stage files with the model prose and the report described in §2:

```sh
matsya job submit model.md --target stage
matsya job wait <job>
matsya job files <job> proposed-model
```

`job submit` creates a session named `model`, after the file, appends the file's text to it as entry 1 and starts the job from that session. It prints the session's identifier and the job's, which replace `<session>` and `<job>`. `--name` gives the session another name, and `--session <session>` appends the file to a session you already have. While it waits, `job wait` prints the job's step and cycle whenever they change; a job may run for many minutes and ends `converged`, `not_converged`, `needs_input`, `cancelled`, `failed` or `interrupted`. A job that ends `needs_input` appends its questions to the session, unless you added an entry to the session while it ran; in that case they stand in its record only, and `matsya job status <job>` says so. `matsya session show <session>` prints the appended questions with their numbers, and `matsya session add <session> reply.md --replies-to <number>` replies to one; the first reply starts the job's next attempt, unless a later job of the session has started since. `job files` writes the job's model folder into a new or empty folder.

While a job is queued or runs, `job status` prints first the job's label, such as `model · stage · version 1 · job 1 · running`: the session's name, the job's target, the version of the session's text the job read, which a queued job shows only when matsya-master submitted it, the job's number among the session's jobs in the order they were created, and its state. While it waits, `job wait` prints no label: each line it prints gives the time with the job's state, step and cycle, such as `14:03:05  running: step writing (Prose-to-Bellman-Sym), cycle 1 of 3`. At the end of a job that holds a record, `job status` and `job wait` print the content of the first two headings of its report: the label with the identifiers of the job and of its session, such as `model · stage · version 1 · job 1 · converged (<job>), session <session>`, and the status and the reason in one sentence, such as `The job ended converged, with the reason source_agreement_and_semantic_fixed_point.`; then the job's questions, the files of its last cycle and the command that writes its model folder. The version is the session's revision, the number of the last entry you added: a description, a paper, a reply, a question you asked or an acceptance of an answer. The label of a running job whose session's text has changed since it started ends `, text changed since`. The label of a job that ended `converged`, `not_converged` or `needs_input` after its session's text changed while it ran ends `, built from an earlier version`; the label of a job that ended `cancelled`, `failed` or `interrupted` has no such ending. The label of a job of no session is its target and its state, such as `stage · running`, and at its end the report's heading reads `stage · converged (<job>), no session`.

`matsya job cancel` cancels a queued or running job:

```sh
matsya job cancel <job>
```

The command prints the job's label and state after the request. A queued job is cancelled at once and never runs. A running job stops before its next call to the language-model provider: a call already sent finishes and is charged, and the job then ends `cancelled`, keeping its record with the usage of the calls it made; `matsya job wait <job>` waits until it has ended. A cancellation that arrives after the job's last call has finished changes nothing, and the job ends with the status it reached, such as `converged`. Cancelling a job that has ended is refused: the service answers 409, `The job has ended`, and the command exits with status 1.

A paper is submitted as its text, a Markdown or LaTeX file, with `matsya job submit paper.md --paper --target stage`, or from Python with `matsya.start_job("paper.md", paper=True, target="stage")`. The paper becomes an entry of the kind `paper` of a new session named after the file, or of the session that `--session` or `session=` names, and the job starts from that session, so that its questions stand in the session as any other job's do. With `--no-session`, or `no_session=True`, the paper is sent as the job's source and the job has no session, as `matsya.submit_job(source_text=text, paper=True, target="stage")` sends a paper's text. Without `--paper`, or `paper=True`, a file is a description. A PDF is refused before any request, the command exiting with status 2 and `start_job` raising `ValueError`, each with the sentence `A paper is sent as Markdown or LaTeX text; convert the PDF first.` Ask the service's administrator before you submit a paper, since its text is sent to the language-model provider.

A search returns the passages of the index, the documentation and literature the service reads, that best match a query, each with its path, its heading and its identifier:

```sh
matsya search "decision perch state and controls" --collections repository --limit 4
```

The collections that `--collections` names are listed by `matsya search --help`; without the option the service searches `repository` and `buffer_stock`, and a search that names a collection your Matsya token may not read is refused with 403, `Collection access is not granted`.

Matsya works in two modes, and a session serves both. A **job** is one run of architect mode, carried out by matsya-architect, and asks nothing of you while it runs: from its source material, the text of a session at one version or a file submitted with no session, Matsya restates the model in prose, writes the stage files and checks them, and a question it cannot settle ends the job `needs_input`. A **session** is the kept text of one model, numbered entry by entry: your descriptions, the questions of its jobs with your replies, and the questions you ask with Matsya's answers. A **turn** is one question answered in conversation mode by matsya-master: its conversation role answers it from the index, the session's text and the outputs of the session's jobs, and writes no stage file itself; the stage files of a model are written by a job. `matsya ask` asks one question and prints the answer with the paths and headings of the material it cites; when the conversation role was given the outputs of the job the conversation discusses, the first line names that job by its label and identifier, as `Answer from model · version 1 · job 1 · converged (<job>)`, whether or not the answer cites those outputs:

```sh
matsya session new "a household"
matsya session add <session> notes.md
matsya ask <session> "What does the decision perch of a stage hold?"
matsya session show <session>
```

A question may also be asked in the session that `job submit` created. Once the job has ended with a record, the answer reads that job's outputs, unless you cancelled the job or added an entry to the session while it ran, a question included; in those cases select the job, as described below. `matsya job submit --session <session>` with no file starts a job from a session's entries as they stand.

A job may also be started by asking matsya-master for one in words, such as "Submit this as a job.": the conversation role then starts a job from the session's text as it stands, the question included, and the command prints, after the answer, the line `Job <number> started from version <revision> of this session's text (<job>); follow it with: matsya job wait <job>`. A question that only mentions a job starts nothing. With `--follow <folder>`, the command then waits for that job as `matsya job wait` does, printing its steps, and at its end writes the model folder into the folder as `matsya job files` does; the command checks before it sends the question that the folder is new or empty. The job runs on the server either way, and `--follow` only keeps the command attached to it:

```sh
matsya ask <session> "Submit this as a job." --follow proposed-model
```

`session show` lists the session's jobs by their labels and identifiers, in the order they were created, and names the selected job when one is set. A question reads the outputs of the session's selected job or, when none is selected, of its latest current job that holds a record. A job is current when you added no entry to the session while it ran, whether a description, a paper, a reply, a question you asked or an acceptance of an answer. A cancelled job is never current. To discuss another job of the session, one that holds a record, select it; `--none` clears the selection, and the end of a job never changes it:

```sh
matsya session select <session> <job>
matsya session select <session> --none
```

Every command but `configure` and `docs` takes `--json`, which prints the service's JSON answer unchanged; `job submit`, which may send three requests, prints the answer to the job's request, `ask` the answer on the finished turn, also with `--follow`, and `job files` the job in the products view, the answer `record.json` holds. `matsya <command> --help` lists a command's options. When the service refuses a request, for example for a Matsya token it does not hold (401), a job or session that is not yours (404), a job that has ended for `job cancel` (409) or a malformed request (422), the command prints the service's message and exits with status 1. No command prints your Matsya token.
