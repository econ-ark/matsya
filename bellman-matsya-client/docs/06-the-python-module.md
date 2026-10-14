---
title: The Python module and the files the client writes
audience: user
type: user-guide
topic: [matsya]
---

# The Python module and the files the client writes

> [!summary]
> The package `bellman-matsya-client` is also a Python module, `bellman_matsya`, with one function for each command that sends a request to the service, reading the same configuration and returning the service's JSON answer. This page gives the module's functions and the exact files `bellman-matsya job files` writes, with the report's headings, for a reader who scripts the client or reads its output by program. The commands themselves are followed in [Working with Matsya from the command line](02-working-from-the-command-line.md) and given in full in [The command reference](05-the-command-reference.md).

> [!info]- Relationship with other documents
> **Builds on** — [Matsya in three parts](index.md), which defines the session, the job, the label and the target, and [The command reference](05-the-command-reference.md), whose commands the module's functions correspond to.
> **Continued by** — [Collections and weights](07-collections-and-weights.md), the collections of the retrieval index, the grants that open them and the weights of a search.
> **See also** — [Reaching the service by HTTP](04-the-service-by-http.md), the requests the functions send; [Working with Matsya from the command line](02-working-from-the-command-line.md), the commands followed through one piece of work.

## 1 The module

The module `bellman_matsya` holds the same operations as functions, which read the same configuration and return the service's JSON answer, except `job_files`, which returns the paths it wrote, and `start_job`, which returns the service's answers to its requests as `{"session": ..., "entry": ..., "job": ...}`, with `None` for a session it did not create or an entry it did not append. The functions correspond to the commands as follows: `index` to `bellman-matsya index`, `search` to `bellman-matsya search`, `start_job` to `bellman-matsya job submit <file>`, `submit_job` to `bellman-matsya job submit --session <session>` with no file, the job's request alone, or, given a description's text as `source_text` in place of `session`, to `bellman-matsya job submit --no-session <file>`, or, given a paper's text as `source_text` with `paper=True`, to `bellman-matsya job submit --paper --no-session <file>`, `job` to `bellman-matsya job status`, which takes `view`, `products` by default or `full`, the complete record, `wait_job` to `bellman-matsya job wait`, `job_files` to `bellman-matsya job files`, which takes `overwrite` and `all_iterates`, `export_job` to `bellman-matsya job export`, which takes `overwrite` and returns the job's full answer after writing `job.json`, `cancel_job` to `bellman-matsya job cancel`, `new_session` to `bellman-matsya session new`, `add_entry` to `bellman-matsya session add`, `session` to `bellman-matsya session show`, `select_job` to `bellman-matsya session select`, with the job `None` for `--none`, and `ask` to `bellman-matsya ask`, which returns the turn, whose `turn["record"]["result"]["job_started"]` names the job the turn started, or is `None`; `publish_configuration` to `bellman-matsya configuration publish`, which takes the folder and returns its ID and version, and `set_default_configuration` to `bellman-matsya configuration set-default`; the function `passage`, which returns one passage of the index by its identifier, and `report_text`, which composes `report.md` from a job as `record.json` holds it and sends no request, have no command. `submit_job`, `start_job` and `ask` take `configuration_id`, the ID of a published configuration, as `--configuration-id` names it, and `submit_job` and `start_job` take `model_key` and `source_cluster`, given together or not at all; an ID of another form than 64 lowercase hexadecimal characters raises `ValueError` before any request. A request the service refuses raises `MatsyaError`, whose `status` holds the HTTP status of the service's answer and `detail` its message: for `cancel_job` of a job that has ended, 409 and `The job has ended`. `MatsyaClient(token, server_url)` holds them as methods for a Matsya token and a service address given explicitly.

```python
import bellman_matsya

started = bellman_matsya.start_job("model.md", target="stage")
job = bellman_matsya.wait_job(started["job"]["id"])
print(bellman_matsya.report_text(job))
bellman_matsya.job_files(job["id"], "proposed-model")
```

The requests themselves, with `curl` examples for a user without Python, are in [Reaching the service by HTTP](04-the-service-by-http.md).

## 2 The model folder and the report

A job returns by default its prepared model prose, the latest available declaration files and the prose from which those files were written (`available_writing`), its questions and the material of its report. The report includes the prose judges' findings, the latest completed comparison of adjacent elaborated semantic objects, and whether a later iteration stopped before comparison, and the language-model tokens charged. A job that ends `not_converged` still returns its available work; its status and reason explain why the comparison did not establish convergence. The full record also holds the initial writing, each iteration's prose, declaration and comparison, every call, and what the roles read.

`bellman-matsya job files <job> <folder>` writes an ended job's products into a new or empty folder, in the layout of the model folders of the project's applications:

```text
proposed-model/
├── economics.md              the prose paired with the available declaration, after front matter naming the job, its label, the session,
│                             the version of the session's text and the date the job ended
├── report.md                 the report
├── record.json               the job as the service returned it, in the products view
└── declaration/
    ├── period.yml            a period or trellis file, when the job wrote one
    ├── trellis.yml
    ├── calibration/, settings/   calibration and settings files, when the job wrote them
    └── stages/<key>/
        ├── <key>.bl          each available stage file, <key> its name without the extension
        ├── <key>.md          the writer's note, when it leaves something open, beside a single stage
        └── methods.yml       a stage's methods file, when the job wrote one
```

With several stages, the writer's note stands as `declaration/notes.md`. A note that reads `none` leaves nothing open and is not written, and a record without model prose, such as that of a job that stopped in preparation with questions, writes no `economics.md`. A folder that holds anything is refused before any request unless `--overwrite` is given, which replaces the files of the same names and leaves the others. A record that names a file the client would write outside the folder is refused, and nothing is written.

`report.md` is composed by the client from the record, without a language model. It gives the job, its status, the number of iterations, the prose judges' findings, the latest completed comparison of adjacent elaborated semantic objects, and whether a later iteration stopped before comparison, any open writer's note or questions, and the tokens charged. A prose disagreement is reported without deciding convergence. For an older job, the report keeps its original **The round-trip comparison** heading and wording.

`--all-iterates`, which is for examining or training the procedure, adds `iterates/initial/` with the first declaration and the prepared prose in `model-prose.md`. Each `iterates/cycle-<n>/` then holds one later declaration, the prose from which it was written in `model-prose.md`, and the remaining iteration data in `cycle.json`. `iterates/record-full.json` holds the complete job record. Thus two iterations yield the initial declaration and two later declarations, with no additional elaboration. The files of an older job retain their original round-trip layout.

```sh
bellman-matsya job files <job> proposed-model-iterates --all-iterates
```

## 3 The commands in detail

A job of matsya-architect turns a model description into proposed stage files, the Bellman-SYM files (`.bl`) that declare a model's stages, and checks them. Write the description in a Markdown or text file, submit it, wait for the job to end, and write its model folder, the stage files with the model prose and the report described in §2:

```sh
bellman-matsya job submit model.md --target stage
bellman-matsya job wait <job>
bellman-matsya job files <job> proposed-model
```

`job submit` creates a session named `model`, after the file, appends the file's text to it as entry 1 and starts the job from that session. It prints the session's identifier and the job's, which replace `<session>` and `<job>`. `--name` gives the session another name, and `--session <session>` appends the file to a session you already have. While it waits, `job wait` prints the job's step and cycle whenever they change; a job may run for many minutes and ends `converged`, `not_converged`, `needs_input`, `cancelled`, `failed` or `interrupted`. A job that ends `needs_input` appends its questions to the session, unless you added an entry to the session while it ran; in that case they stand in its record only, and `bellman-matsya job status <job>` says so. `bellman-matsya session show <session>` prints the appended questions with their numbers, and `bellman-matsya session add <session> reply.md --replies-to <number>` replies to one; the first reply starts the job's next attempt, unless a later job of the session has started since. `job files` writes the job's model folder into a new or empty folder.

While a job is queued or runs, `job status` prints first the job's label ([Matsya in three parts](index.md) §2), such as `model · stage · version 1 · job 1 · running`; a queued job shows the version only when matsya-master submitted it. While it waits, `job wait` prints no label: each line it prints gives the time with the job's state, step and cycle, such as `14:03:05  running: step writing (Prose-to-Bellman-Sym), cycle 1 of 3`. At the end of a job that holds a record, `job status` and `job wait` print the content of the first two headings of its report: the label with the identifiers of the job and of its session, such as `model · stage · version 1 · job 1 · converged (<job>), session <session>`, and the status and the reason in one sentence, such as `The job ended converged, with the reason semantic_fixed_point.`; then the job's questions, the available files and the command that writes its model folder. If those files came from an earlier cycle, the output names that cycle. A `not_converged` result can be saved by `job files` for inspection; its stage files are proposals, and the report states why the job did not converge. The label of a running job whose session's text has changed since it started ends `, text changed since`. The label of a job that ended `converged`, `not_converged` or `needs_input` after its session's text changed while it ran ends `, built from an earlier version`; the label of a job that ended `cancelled`, `failed` or `interrupted` has no such ending. The label of a job of no session is its target and its state, such as `stage · running`, and at its end the report's heading reads `stage · converged (<job>), no session`.

`bellman-matsya job cancel` cancels a queued or running job:

```sh
bellman-matsya job cancel <job>
```

The command prints the job's label and state after the request. A queued job is cancelled at once and never runs. A running job stops before its next call to the language-model provider: a call already sent finishes and is charged, and the job then ends `cancelled`, keeping its record with the usage of the calls it made; `bellman-matsya job wait <job>` waits until it has ended. A cancellation that arrives after the job's last call has finished changes nothing, and the job ends with the status it reached, such as `converged`. Cancelling a job that has ended is refused: the service answers 409, `The job has ended`, and the command exits with status 1.

A paper is submitted as its text, a Markdown or LaTeX file, with `bellman-matsya job submit paper.md --paper --target stage`, or from Python with `bellman_matsya.start_job("paper.md", paper=True, target="stage")`. The paper becomes an entry of the kind `paper` of a new session named after the file, or of the session that `--session` or `session=` names, and the job starts from that session, so that its questions stand in the session as any other job's do. With `--no-session`, or `no_session=True`, the paper is sent as the job's source and the job has no session, as `bellman_matsya.submit_job(source_text=text, paper=True, target="stage")` sends a paper's text. Without `--paper`, or `paper=True`, a file is a description. A PDF is refused before any request, the command exiting with status 2 and `start_job` raising `ValueError`, each with the sentence `A paper is sent as Markdown or LaTeX text; convert the PDF first.` Ask the service's administrator before you submit a paper, since its text is sent to the language-model provider.

A search returns the passages of the index, the documentation and literature the service reads, that best match a query, each with its path, its heading and its identifier:

```sh
bellman-matsya search "decision perch state and controls" --collections repository --limit 4
```

The collections that `--collections` names are listed by `bellman-matsya search --help`; without the option the service searches every collection your Matsya token may read. The Python function `search` does the same when `collections` is omitted. An explicit list restricts the search to those collections, and a list that names a collection your Matsya token may not read is refused with 403, `Collection access is not granted`.

A session serves both sides of the service: a job of matsya-architect writes the stage files of a model, and a turn of matsya-master answers one question and writes no stage file ([Matsya in three parts](index.md) §2 defines the three). `bellman-matsya ask` asks one question and prints the answer with the paths and headings of the material it cites; when the conversation role was given the outputs of the job the conversation discusses, the first line names that job by its label and identifier, as `Answer from model · stage · version 1 · job 1 · converged (<job>)`, whether or not the answer cites those outputs:

```sh
bellman-matsya session new "a household"
bellman-matsya session add <session> notes.md
bellman-matsya ask <session> "What does the decision perch of a stage hold?"
bellman-matsya session show <session>
```

A question may also be asked in the session that `job submit` created. Once the job has ended with a record, the answer reads that job's outputs, unless you cancelled the job or added an entry to the session while it ran, a question included; in those cases select the job, as described below. `bellman-matsya job submit --session <session>` with no file starts a job from a session's entries as they stand.

A job may also be started by asking matsya-master for one in words, such as "Submit this as a job.": the conversation role then starts a job from the session's text as it stands, the question included, and the command prints, after the answer, the line `Job <number> started from version <revision> of this session's text (<job>); follow it with: bellman-matsya job wait <job>`. A question that only mentions a job starts nothing. With `--follow <folder>`, the command then waits for that job as `bellman-matsya job wait` does, printing its steps, and at its end writes the model folder into the folder as `bellman-matsya job files` does; the command checks before it sends the question that the folder is new or empty. The job runs on the server either way, and `--follow` only keeps the command attached to it:

```sh
bellman-matsya ask <session> "Submit this as a job." --follow proposed-model
```

A job or a question runs under one published configuration, the service's default unless `--configuration-id <id>` names another, and every answer on the job or the turn names the ID resolved. To compare two configurations on the same source, submit the same text directly to each, so that a session's later entries cannot change what a queued job reads, and save each job's full answer:

```sh
bellman-matsya job submit model.md --target stage --no-session --configuration-id <id A>
bellman-matsya job submit model.md --target stage --no-session --configuration-id <id B>
bellman-matsya job export <job A> records/case-1/<id A>/trial-1
bellman-matsya job export <job B> records/case-1/<id B>/trial-1
```

`job export` writes `job.json`, the job's full answer, for any state of the job, a failed or cancelled job among them, with its configuration ID and the digests of its accepted request, its source text and its index. The paired check `meaning-map-config-pair` of the package `meaning-map-training` reads two such files with their local configuration snapshots and reports whether the two jobs' inputs were comparable; the [Matsya developer guide](../dev-guide/04-updating-configurations.md) describes it. `bellman-matsya configuration publish <folder>` and `bellman-matsya configuration set-default <id>` are the administrator's commands that publish a configuration and make one the default.

`session show` lists the session's jobs by their labels and identifiers, in the order they were created, and names the selected job when one is set. A question reads the outputs of the selected job or, when none is selected, of the latest job that [Matsya in three parts](index.md) §3 names; any entry you add while a job runs, a description, a paper, a reply, a question or an acceptance of an answer, keeps that job from being chosen this way. To discuss another job of the session, one that holds a record, select it; `--none` clears the selection, and the end of a job never changes it:

```sh
bellman-matsya session select <session> <job>
bellman-matsya session select <session> --none
```

Service commands take `--json` to print the service's JSON answer unchanged; the project commands use it to print an answer assembled from the folder and the service. Bare `bellman-matsya`, `configure` and `docs` have no JSON form. `job submit`, which may send three requests, prints the answer to the job's request, `ask` the answer on the finished turn, also with `--follow`, and `job files` the job in the products view, the answer `record.json` holds. `bellman-matsya <command> --help` lists a command's options. When the service refuses a request, for example for a Matsya token it does not hold (401), a job or session that is not yours (404), a job that has ended for `job cancel` (409) or a malformed request (422), the command prints the service's message and exits with status 1. No command prints your Matsya token.
