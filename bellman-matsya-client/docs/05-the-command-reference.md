---
title: The command reference
audience: user
type: user-guide
topic: [matsya]
---

# The command reference

> [!summary]
> This page gives the commands of matsya-client, the program you run on your machine to use Matsya. It states their arguments, options, printed answers and exit statuses. It also names the fields returned by `--json`, so an assistant can read an answer without interpreting the printed prose.

> [!info]- Relationship with other documents
> **Builds on** — [Working with Matsya from the command line](02-working-from-the-command-line.md), which follows a session and a job, and [Working on a project folder](03-working-on-a-project-folder.md), which follows a model in its own folder.
> **Continued by** — [The Python module and the files the client writes](06-the-python-module.md), which gives the corresponding Python calls.
> **See also** — [Matsya in three parts](index.md), which defines a session, a job, a turn, a target and a job's label.

## 1 Reading a command's answer

`bellman-matsya --help` lists the commands. For one command's options, run its own help, for example `bellman-matsya job submit --help` or `bellman-matsya project pull --help`. In the forms below, angle brackets stand for a value you supply; square brackets enclose an optional argument. A job or session identifier is the value printed when it is created.

Every service command accepts `--json` **except** `bellman-matsya configure` and `bellman-matsya docs`. The four `bellman-matsya project` commands accept it too. For ordinary service commands, `--json` prints the service's final JSON answer unchanged. For project commands, it prints one JSON object assembled from the folder and the service's answers. `bellman-matsya job files --json` prints the job's answer, although it also writes files. `bellman-matsya ask --follow ... --json` prints the turn's answer, not the followed job's answer; progress goes to standard error. Section 8 gives the fields.

| Exit status | Meaning |
|---|---|
| `0` | The command completed. For `job wait`, inspect the returned job state: `needs_input`, `not_converged` and `failed` are final states too. |
| `1` | The service refused a request, a local file could not be read or written, the service could not be reached, or an online guide page could not be read. The error is printed on standard error. |
| `2` | The arguments were refused before a request, or a project command's conditions were not met. Argument errors include a usage line; project refusals give one sentence on standard error. |
| `130` | You interrupted a waiting command. Its message says how to inspect a job or turn that may still be running on the service. |

On a machine with no saved configuration and no `BELLMAN_MATSYA_TOKEN`, any command other than `docs` or bare `bellman-matsya` first prints two lines directing an assistant to `bellman-matsya docs --all`. Those lines precede even a JSON answer. Run `bellman-matsya configure` first if a program needs standard output to contain JSON alone. The Matsya token itself is never printed.

## 2 Orientation, configuration and the guide

### 2.1 Orientation

`bellman-matsya` with no arguments prints Markdown: what Matsya does; the installed guide's folder and the commands that print or update it; the client version; whether a token is saved or supplied by `BELLMAN_MATSYA_TOKEN`; and how to list the commands. In a project folder it also prints the session identifier, the latest job's label and any questions awaiting a reply. If the session cannot be read, it gives the reason. This form makes no change and has no `--json` option.

### 2.2 Configuration

`bellman-matsya configure` asks only for a Matsya token beginning `msy_`. It saves the token in the user's configuration file without sending a request and retains any custom service address already saved there. Otherwise the client uses `http://45.55.225.169:8710`. It prints the file's path, explains that the service keeps session entries and job records, and suggests `bellman-matsya index` to check access. `BELLMAN_MATSYA_TOKEN` and `BELLMAN_MATSYA_SERVER` override saved values for later commands. This interactive command has no `--json` option; an invalid token or saved address ends with status `1`.

### 2.3 The guide

| Command | What it prints |
|---|---|
| `bellman-matsya docs` | Each installed page's name and title, one per line. |
| `bellman-matsya docs <page>` | That page in Markdown, without its front matter. The name may omit `.md`; `dev-guide/index` names a developer-guide page. |
| `bellman-matsya docs --all` | All installed pages in order, each preceded by a `<!-- page: ... -->` line naming its file. |
| `bellman-matsya docs --path` | The folder in which the guide is installed. |

`--online` with a named page or `--all` reads its current text over HTTPS from the public Matsya client repository. The page list and titles still come from the installed client, so a newly added online page requires a client update before this command can name it. `bellman-matsya docs --online` without a page or `--all` only lists the installed pages. `--path` cannot be combined with `--online`, and a page cannot be combined with `--all` or `--path`. These argument errors end with status `2`; a failure to read an online page ends with status `1` and tells you how to read the installed guide. `docs` has no `--json` option.

## 3 The retrieval index

### 3.1 Index information

`bellman-matsya index [--json]` prints `Index digest`, `Embedding model`, `Configuration ID` and `Configuration version`. The digest identifies the version of the retrieval index the service is reading. The configuration ID and version name the service's current default. Its JSON fields are `index_digest`, `embedding_model_id`, `configuration_id` and `configuration_version`.

### 3.2 Search

`bellman-matsya search <query> [--collections NAMES] [--limit N] [--json]` searches for passages related to the query. `--collections` takes comma-separated names from `repository`, `literature`, `articles`, `hark` and `buffer_stock`; it may be repeated. Without it, the service searches every collection your Matsya token may read and ranks passages by their match to the query, with the collection weights applied. Use the option to restrict the search to named collections. `--limit` asks for 1 to 20 passages; the service's default is 8. The command prints the index digest and passage count, then each passage's path, heading and page when present, collection, score, identifier and a shortened text excerpt. The JSON answer has `index_digest` and `passages`; each passage includes its full `text`, `passage_id`, `corpus`, `path`, `location` and `score`, together with its source metadata. [Collections and weights](07-collections-and-weights.md) explains the collections and search weights.

## 4 Jobs that write and check a declaration

A **target** is the level of declaration a job is asked to return: `stage`, `period`, `trellis` or `recipe`. A stage is one stage file; a period includes its stages and period file; a trellis includes its periods and trellis file; a recipe adds the files needed to solve it. The target is required for `job submit`.

### 4.1 Submit a job

```text
bellman-matsya job submit <file> --target {stage,period,trellis,recipe} [--paper]
    [--name NAME | --session <session> | --no-session]
    [--max-cycles N] [--force] [--configuration-id ID]
    [--model-key KEY --source-cluster CLUSTER] [--json]
bellman-matsya job submit --session <session> --target {stage,period,trellis,recipe}
    [--max-cycles N] [--force] [--configuration-id ID] [--json]
```

The file must contain UTF-8 text. By default its text is a model description. `--paper` marks the text of a paper, whether Markdown, LaTeX or plain text; a PDF is refused before any request with the instruction to convert it first. Without `--session` or `--no-session`, the client creates a session named after the file without its extension; `--name` replaces that name. `--session` appends the file to an existing session, or, without a file, submits a job from the entries already in that session. `--no-session` sends the file directly; the job's questions then remain in its record. The three session options cannot be combined. `--paper` requires a file.

`--max-cycles` is a positive integer limiting iterations after the initial declaration; when omitted, the service uses its configured limit, subject to its maximum. `--force` continues to writing if preparation ends with questions and records the writer's assumptions. `--configuration-id` names the published configuration the job runs under, 64 lowercase hexadecimal characters (§9); without it the service's default runs the job, and either way the service's answer names the ID resolved. An ID of another form is refused with status `2` before any request, and an ID the service has not published is the service's 404. `--model-key` and `--source-cluster`, given together or not at all, name the groups of indexed sources the job must not read. With a file and a session, the command prints the session and entry numbers, the queued job identifier, the `job wait` line and where to see the session. Without a session it prints where to see questions in the job record. The JSON answer is the queued job object: `id`, `state`, `configuration_id` and `status_url`. Creating a session and appending an entry are separate requests; if the later job request is refused, the error names what the session retained.

### 4.2 Inspect, wait for, save or cancel a job

| Command | Options and printed answer |
|---|---|
| `bellman-matsya job status <job> [--json]` | Prints the job's label, identifier and state. While it runs, it adds the current step and any cancellation request. An ended job with a record has the label and status from the first two report headings, its questions when present, the available file names and a `job files` command. An ended job without a record has its error and detail when present. |
| `bellman-matsya job wait <job> [--interval SECONDS] [--json]` | Requests the job's state until it ends. The interval defaults to 5 seconds and cannot be negative. While waiting, it prints a time-stamped line when the state, step or cycle changes; with `--json`, these progress lines go to standard error. Its final answer is the same as `job status`. |
| `bellman-matsya job files <job> <folder> [--all-iterates] [--overwrite] [--json]` | Writes a new or empty model folder, then prints its file count and each relative path. It writes `report.md` and `record.json`, plus `economics.md` with the prose paired with the most recent available declaration files under `declaration/`, including for a `not_converged` job. The report retains that status: these files are proposals for review. `--all-iterates` also writes the initial declaration, then each iteration's declaration and its input prose under `iterates/`, with the full record. `--overwrite` permits a nonempty folder, replacing files of the same names while retaining others. A job without a record cannot be written. |
| `bellman-matsya job export <job> <folder> [--overwrite] [--json]` | Saves the job's full answer, the record as the service keeps it with every iteration and call, as `job.json` in the folder, which is created when it does not exist, for any state of the job: a cancelled or failed job without a record is saved with its state, its error, its configuration ID and its digests. Prints the path written, the job's state and its configuration ID. An existing `job.json` is refused before any request unless `--overwrite` is given. The file is written whole under a temporary name, then made visible as `job.json` in one operation. With `--json`, prints the full answer while still writing the file. A local comparison of two configurations reads this file, not the products-only `record.json` of `job files`. |
| `bellman-matsya job cancel <job> [--json]` | Cancels a queued job at once or requests cancellation of a running job, then prints its state and, if still running, the `job wait` line. A call already sent to the language-model provider completes before cancellation takes effect. An ended job cannot be cancelled. |

For `status`, `wait`, `files` and `cancel`, `--json` prints the job object defined in §8.2, and for `export` the same object in the full view. In an ordinary model folder, an open writer note is placed beside its single stage as `declaration/stages/<key>/<key>.md`, or at `declaration/notes.md` otherwise. `job files` checks the folder before requesting the job, and refuses a path through a symbolic link rather than writing through it. The job state, not the command's exit status, tells you whether the writing and checking converged.

## 5 Sessions and their entries

A **session** keeps the entries written by the user and Matsya, the jobs submitted from that text, and the turns that answer questions. Its **revision** is the number of its latest user, paper or acceptance entry. The commands below print session and entry identifiers so the next command can name them.

| Command | Options and printed answer |
|---|---|
| `bellman-matsya session new <name> [--json]` | Creates an empty session. Prints its identifier and name, then the commands to add an entry and ask a question. |
| `bellman-matsya session add <session> <file> [--kind user\|paper] [--replies-to N] [--delivery-id ID] [--json]` | Appends the file's UTF-8 text; `-` reads standard input. The default kind is `user`; `paper` marks paper text. `--replies-to` names the numbered question this entry answers. `--delivery-id` is a name of at most 64 characters; a repeated delivery appends nothing. Prints the entry number and revision, or says that delivery was already held. If a reply starts the next job, it prints its identifier and the `job wait` line. |
| `bellman-matsya session add <session> --kind acceptance --replies-to N [--delivery-id ID] [--json]` | Appends an acceptance of numbered answer entry `N`, with no file or text. It prints the same entry and revision lines as other additions. |
| `bellman-matsya session show <session> [--json]` | Prints the session's identifier, name and revision; any job awaiting an answer or selected for questions; jobs by label; turn identifiers; and numbered entries with their kinds and text. |
| `bellman-matsya session select <session> <job> [--json]` or `bellman-matsya session select <session> --none [--json]` | Selects a job of this session that holds a record, or clears the selection. Prints the selected job and explains which job's outputs later questions read. The job and `--none` cannot be combined. |

An ordinary reply is sent with `session add`, not with a project-specific reply command. A reply to a question of the job currently awaiting an answer starts its next job automatically; `session show` or `project status` prints the entry number needed by `--replies-to`.

## 6 Ask one question

```text
bellman-matsya ask <session> <question> [--stage-file PATH] [--index-digest DIGEST]
    [--follow FOLDER] [--interval SECONDS] [--configuration-id ID] [--json]
```

The question is one turn in the session. `--stage-file` sends a stage file whose elaborated account the answer can read. `--index-digest` names a stored version of the retrieval index. `--configuration-id` names the published configuration whose conversation role answers (§9); without it the default answers, and a job the turn starts runs under the same configuration as the turn. A configuration without the conversation role refuses the question before anything is appended. `--interval` sets the time between requests while waiting: by default 2 seconds for the turn and 5 seconds for a job followed with `--follow`; it cannot be negative. While the turn runs, the command prints time-stamped state and step changes. It then prints the answer, any source quotations and their locations, questions needing your reply, or the reason an incomplete turn stopped. If the turn read a job's outputs, it names that job. If it started a job, it prints the job identifier and the command to follow it.

`--follow FOLDER` checks that `FOLDER` is new or empty before sending the question. When the turn starts a job, the command waits for it and writes its model folder there if it holds a record. If no job starts, it says so and writes nothing. With `--json`, the final standard output is the turn object defined in §8.4, even when a followed job has also ended and its files were written. Progress lines go to standard error. A turn that finishes with a request for input or as incomplete still completes this command with exit status `0`; read `record.result.status`.

## 7 A model's project folder

A **project folder** can hold the author's `economics.md` and current files under `declaration/`. Its `.bellman-matsya/project.json` remembers the session and service address. Run `submit`, `status` and `pull` from that folder. These commands take `--json`, which returns the fields in §8.5. [Working on a project folder](03-working-on-a-project-folder.md) follows their use in order.

| Command | Options, default and printed answer |
|---|---|
| `bellman-matsya project init [folder] [--json]` | Makes `folder` a project; the default is the current folder, and a missing folder is created. It creates a session named after the folder, appends nonempty `economics.md` when present, writes `.bellman-matsya/project.json` and `.bellman-matsya/README.md`, and creates `AGENTS.md` with a paragraph for an assistant when no such file exists. It prints the folder and session, any entry, files written and the `project submit` line. If `AGENTS.md` exists, it leaves it unchanged and prints the paragraph for you to add. |
| `bellman-matsya project submit [--target {stage,period,trellis,recipe}] [--max-cycles N] [--configuration-id ID] [--json]` | Appends `economics.md` only if its bytes changed since the last submission. It sends recognized files under `declaration/` as the starting declaration and prints which files were sent or left out, the target, the job's label and identifier, and the `job wait` line. Without `--target`, a recipe file, methods, calibration or settings selects `recipe`; otherwise `trellis.yml` selects `trellis`, a period file selects `period`, and no such file selects `stage`. `--max-cycles` is a positive integer; without it the service uses its configured limit. `--configuration-id` is forwarded to the job as `job submit` sends it. |
| `bellman-matsya project status [--json]` | Prints the folder's session identifier, service and revision, its entries and jobs, any selected job, questions awaiting a reply and their exact `bellman-matsya session add ... --replies-to N` lines, a `bellman-matsya ask` line and whether `economics.md` changed. |
| `bellman-matsya project pull [<job>] [--replace \| --into [SUBFOLDER]] [--json]` | By default chooses the latest ended job in the session that holds a record and writes its complete model folder to `bellman-matsya-output/job-<number>/`. `--into` selects another new or empty subfolder within the project; without a value it uses that default. This output folder holds the job's model prose as `economics.md`. `--replace` instead writes declaration files into the project folder, replacing matching files while keeping declaration files the job did not produce. When a writer leaves a question open, it writes that note to `.bellman-matsya/writer-note.md`, preserving an existing stage note. It writes `report.md` and, when model prose exists, `model-prose.md`; it leaves the author's `economics.md` unchanged and prints the paths written, replaced and kept. `--replace` and `--into` cannot be combined. |

The project file contains the session identifier, service address and digest of the last submitted `economics.md`. The client sends a project's requests only to its configured service when that address matches the project file. A project command in a folder with no readable project file, or a pull of a job with no record, is refused with status `2`. A service refusal still ends with status `1`.

## 8 Fields in JSON answers

The client preserves the service's JSON field names. A field described as optional below is absent until the related event occurs; a value described as `null` is present with no value. The project commands instead compose their own objects. `configure`, `docs` and bare `bellman-matsya` have no JSON form.

### 8.1 Index and search

`index --json` has exactly `index_digest` (the index version), `embedding_model_id` (the model used to represent passages for search), `configuration_id` (the ID of the service's default configuration) and `configuration_version` (its readable version); the printed answer has one line for each. `search --json` has `index_digest` and `passages`, an array. A passage has these fields:

| Fields | Meaning |
|---|---|
| `passage_id`, `passage_sha256`, `text` | Passage identifier, digest of its full text, and that text. The printed search excerpt is shorter. |
| `corpus`, `source_root`, `source_id`, `path`, `file_sha256` | Collection, root and identifier of the source, its path and file digest. |
| `access`, `kind`, `authority`, `version`, `title`, `source_cluster`, `model_prompt` | Source access and descriptive metadata. Some values may be `null`. |
| `location` | `page`, `page_basis`, `printed_page_label`, `heading`, `line_start`, `line_end`, `char_start` and `char_end`; when applicable, also `cell_number`, `cell_type`, `stage_name`, `block_id`, `section` and `formula_continues`. |
| `index_digest`, `manifest_digest`, `corpus_revision` | Versions of the index, source manifest and collection. |
| `score`, `raw_score`, `retrieval_weight`, `lexical_score`, `dense_score` | Weighted search score, score before weighting, weight applied, word-match score and representation-match score. |

### 8.2 Jobs

`job submit --json` has `id` (job identifier), `state` (`queued`), `configuration_id` (the configuration the job runs under) and `status_url`. The other five job commands return a job object. `status`, `wait` and `files` use the service's **products view**, the final products and report material rather than every writing cycle; `cancel` returns the service's job state at cancellation; `export` returns the **full view**, the record with every iteration and call. `job files --all-iterates` writes the full record to disk but still prints the products view with `--json`.

| Field | Meaning |
|---|---|
| `id`, `state` | Job identifier and current state. States are `queued`, `running`, `converged`, `not_converged`, `needs_input`, `cancelled`, `failed` or `interrupted`. |
| `label` | Object with `model`, `target`, `revision`, `number`, `state`, `overtaken` and the one-line `text` printed for a reader. A job without a session has no model, revision or number. |
| `cancel_requested`, `progress`, `events` | Whether cancellation was requested; current step, cycle and cycle limit when reported; and the service's call events. |
| `created_at`, `updated_at` | Times recorded by the service. |
| `result` | Present when the job holds a record. Its products-view fields are listed below. |
| `error`, `error_detail` | Present when a job ends with an error. |
| `session`, `revision`, `entry_numbers`, `current` | Present for a job started from a session as each value becomes known: session identifier, version of its text, source entry numbers and whether it was current when it ended. |
| `started_by` | Turn identifier when a question submitted this job. |
| `configuration_id` | The ID of the configuration the job runs under, fixed when the service accepted the job; `null` for a job recorded before the service kept it. |
| `request_sha256`, `source_sha256`, `index_digest` | The digest of the accepted request without its `configuration_id`, fixed at acceptance; the digest of the source text the job reads, a description stripped of surrounding whitespace and a paper unchanged, fixed at acceptance for a source sent with the request and when the job starts for a session's text; and the digest of the retrieval index the job selected when it began. Each is `null` until fixed. |

In `result`, `schema` identifies the form of the job record; `target` names the requested level; `structure` is the form named in the model prose; `status` and `reason` state the outcome; `description` holds the prepared model prose; `questions` holds requested clarifications; and `paper_source_check` and `paper_form_check` hold checks of that prose against the source. `cycles_run` counts the iterations after the initial declaration. `available_writing` is `null` if no writing produced parsed files; otherwise it gives its `cycle` number, `files`, and the `description` from which those files were written. Cycle 0 is the initial writing from the prepared model prose. `last_cycle` is `null` if no iteration began; otherwise it describes the final iteration, with `files`, `judging`, `comparison` (with `equal` and `first_difference`), `citations_supported` and `unresolved_note`. `last_completed_comparison` gives the latest completed adjacent comparison, its left and right cycle numbers, its `equal` verdict and its first difference; it is `null` if no comparison completed. `reading` gives the `index_digest` and `guides` consulted. `usage` gives `charged`, `calls_by_role` and `refusal`, including any token-ceiling refusal. A field the service's record does not hold is omitted from the products view. Older records keep their original field meanings and output layout.

### 8.3 Sessions

`session new --json`, `session show --json` and `session select --json` return a session object. `session add --json` returns that same object with three additional fields: `entry` (the entry appended or previously delivered), `repeated` (whether a delivery identifier was already used) and `scheduled` (`null` or an object with `id` and `status_url` for the next job).

| Session field | Meaning |
|---|---|
| `id`, `name` | Session identifier and name. |
| `entries` | Numbered entries. Each has `number`, `kind`, `text`, `origin`, `replies_to` and `created_at`; `origin` names a job or turn when Matsya wrote the entry, otherwise it is `null`. |
| `revision` | Number of the latest user, paper or acceptance entry. |
| `awaiting_answer`, `selected_job` | Identifier of a job awaiting a reply, and identifier of the job selected for later questions; either may be `null`. |
| `jobs`, `turns` | Jobs in submission order and turn identifiers. Each listed job has `id`, `state`, `revision`, `current` and `label`. |
| `created_at`, `updated_at` | Times recorded by the service. |

### 8.4 Turns

`ask --json` returns the final turn object. It has `id`, `session`, `state`, `question` (the session entry number), `configuration_id` (the configuration whose conversation role answered), `progress`, `events`, `created_at` and `updated_at`; `record` is present when a turn has a record, while `error` and `error_detail` may be present after failure. The record has `schema`, `turn`, `session`, `question`, `index_digest`, `versions`, `stage_file`, `fields`, `calls`, `reading`, `retained`, `decisions`, `dropped_decisions`, `usage` and `result`. These record the source versions, any stage file supplied, material read, calls and decisions as well as the answer. In `record.result`, `turn` identifies the turn; `status` is `answered`, `needs_input` or `incomplete`; `answer`, `citations`, `questions` and `reason` give the response and any reason it stopped. `passages` names material supplied to the turn; `index_digest` names the index it read; `current` says whether the session's text remained current; `job` names the job whose outputs it read, if any; and `job_started` names a job it submitted, if any. A citation has `quote`, `identity`, `path`, `heading`, `location`, `authority` and `index_digest`. Both job fields are `null` when no job applies, or objects with `id` and `label` when one does.

### 8.5 Project commands

Each project answer includes `folder`, the resolved project-folder path, and `project`, the contents of `.bellman-matsya/project.json`: `session`, `server` and `economics_sha256` (the digest of the description at its last submission, or `null`). The remaining fields depend on the command:

| Command | Additional JSON fields |
|---|---|
| `project init` | `session`: the new service session; `entry`: the first entry or `null`; `written`: paths written; `agents`: `created` or `kept` for `AGENTS.md`; `agents_paragraph`: the paragraph written or offered to the user. |
| `project submit` | `economics`: `appended`, `unchanged` or `absent`; `entry`: the new entry or `null`; `target`: requested level; `target_named`: whether `--target` supplied it; `starting_declaration`: file names sent; `left_out`: paths under `declaration/` not sent; `job`: the service's job object. |
| `project status` | `session`: current service session; `awaiting`: objects with `number`, `text` and the exact `reply` command; `ask`: command to ask a question; `economics_changed`: `true`, `false` or `null` if the folder has no readable nonempty description. |
| `project pull` | `job`: selected job in the products view; `into`: output subfolder or `null` with `--replace`; `written`: paths written; `replaced`: paths that replaced files; `kept`: declaration paths the job did not write. |

## 9 Publish a configuration and set the default

```text
bellman-matsya configuration publish <folder> [--json]
bellman-matsya configuration set-default <id> [--json]
```

A **configuration** is the checked folder of instruction texts, settings, Matsya handlers and saved guides that a job or a question runs under; its **configuration ID** is the SHA-256 digest of its `manifest.json`. The service keeps every published configuration unchanged under its ID and one **default**, which a job or a question that names no ID runs under. Both commands are refused by the service with 403 for a Matsya token whose holder the service's operator has not named as an administrator; any Matsya token may select a published ID with `--configuration-id`.

`configuration publish` sends the folder's files, by their paths relative to the folder and without bytecode caches, as a ZIP archive, and prints the ID and the version the service answered with; the same folder published again prints the same ID. A folder that holds a symbolic link is refused with status `1` before any request. The service checks every file against the manifest before and after it imports the Matsya handler module, and refuses an archive that escapes its folder, holds a duplicate name or a file the manifest does not list, or expands beyond 24 MiB. Publication leaves the default as it is. The JSON answer has `configuration_id` and `version`.

`configuration set-default` makes a published ID the default and prints the new default with its version and the former default. The change takes effect for the next job or question, without a restart; a job or a question already accepted keeps the configuration pinned to it. An ID of another form than 64 lowercase hexadecimal characters is refused with status `2` before any request, and an unpublished ID is the service's 404. The JSON answer has `previous_configuration_id`, `configuration_id` and `version`.
