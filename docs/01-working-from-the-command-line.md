---
title: Working with Matsya from the command line
audience: user
type: user-guide
topic: [matsya]
---

# Working with Matsya from the command line

> [!summary]
> This page follows one piece of work through the command `matsya`, from installation to the folder of stage files, with the commands as you type them and what each prints. The command is matsya-client of [Matsya in three parts](index.md): a program that sends your requests to the service and writes what comes back. Every command but `configure` and `docs` takes `--json`, which prints the service's answer unchanged, and `matsya <command> --help` lists a command's options.

> [!info]- Relationship with other documents
> **Builds on** — [Matsya in three parts](index.md), which defines the three parts and the words session, job and turn.
> **Explained for developers in** — the [Matsya developer guide](../dev-guide/index.md).
> **See also** — [Stages](../../Bellman-Sym/01-stage.md) and [Constraints](../../Bellman-Sym/10-constraints.md) in the language guide, for reading the stage files a job writes.

## 1 Installing and setting up

The package `econ-ark-matsya` installs the command `matsya` and the Python module `matsya`; it needs Python 3.10 or newer and nothing else. It installs into any Python environment with `pip`; where the system's Python refuses a plain install, `pipx` gives the command an environment of its own, and a virtual environment serves as well. An earlier `matsya` client of the previous service has the same package name, so installing this one replaces it, and the two share one configuration file, so `matsya configure` is run again afterwards with this service's address. It is installed from the public repository `econ-ark/matsya`, and the service's address comes with the access instructions the service's administrator gives you, together with your Matsya token, the password-less identifier beginning `msy_` that the service checks on every request. Set up once:

```
pip install git+https://github.com/econ-ark/matsya
matsya configure
```

The command asks for the Matsya token and the address, saves both in a private file in your home folder, and sends nothing. At the first use of `matsya` on a machine, with no configuration file saved and `MATSYA_TOKEN` unset, the command first prints two lines that send a model working for you to this guide, `matsya docs --all`. The environment variables `MATSYA_TOKEN` and `MATSYA_SERVER` override the saved values, which is how a script or a second machine uses the command. Then check the connection:

```
matsya index
```

It prints the digest of the retrieval index the service reads, the identity of the model that embeds the passages, and the configuration's version. A refused request is printed as the service's message, with exit status 1; the Matsya token never appears in any output.

## 2 A job from a description

Write the model's description in a Markdown file, with the states, the choices, the constraints, the shocks, the timing and the objective in prose and displayed equations. Then:

```
matsya job submit model.md --target stage
```

The option `--target` names what the job is to return, a **stage**, one decision problem in one file; a **period**, the stages of one model period with their connections; a **trellis**, the periods in time; or a **recipe**, the trellis with the methods, calibration and settings the Workbench loads; the command refuses a submission that names none. The command creates a session named `model`, after the file, appends the file's text to it as entry 1, and starts a job from that session. It prints the session's identifier and name, the entry's number, the job's identifier and its state `queued`, and two lines: how to follow the job, and how to see the session, where the job's questions and your replies are kept. `--name "Household with firms"` gives the session another name; `--max-cycles 2` limits the cycles of writing and checking; `--no-session` submits the file as the job's source with no session, in which case the job's questions stand in its record only.

```
matsya job wait <job>
```

The command polls the job and prints a line whenever its step or cycle changes, naming the step and the role that computes it: `preparation` (the Model-prose-writer and the prose-source-judge), `writing` (Prose-to-Bellman-Sym, whose files the elaborator checks within the step), `prose_writing` (Semantics-to-Prose), `judging` (the prose-roundtrip-judge) and `reconstruction` (Prose-to-Bellman-Sym and the round-trip comparison). When the job ends it prints the final state and its reason: `converged`; `not_converged`, with the reason, such as the cycle limit reached; `needs_input`, with the numbered questions and a sentence that says whether they stand in the session; or `failed`, with its code. `matsya job status <job>` prints the same without waiting.

```
matsya job files <job> proposed-model
```

The command writes the job's products into the folder, which must be new or empty: the stage files under `declaration/stages/<key>/<key>.bl`, the writer's note, when it leaves something open, beside a single stage as `<key>.md` and otherwise as `declaration/notes.md`, any period, trellis, calibration, settings or methods file under `declaration/` by its name, the model prose as `economics.md`, the report as `report.md`, and the record the service returned as `record.json`. The report states the job's label, its final state and reason, the cycles run, what each judge found not to match with the quoted sentences, whether the round-trip files equal the written ones, the questions, and the language-model text charged; every sentence of it is the record's content or a fixed sentence. `--all-iterates` adds, for training, a folder `iterates/` with every cycle's files, prose and verdicts and the full record.

## 3 Replying to a job's questions

A job that ends `needs_input` has written its questions into the session as entries, provided you added no entry to the session while it ran; otherwise they stand in its record alone, where `matsya job status` prints them, and you submit again. Read them and reply:

```
matsya session show <session>
matsya session add <session> reply.md --replies-to <entry number>
```

The reply is an entry of the session, and because it answers a question of the session's latest job, it starts the next job at once, with the text as it now stands. Follow it with `matsya job wait`. A reply is kept in the session but starts nothing when a later job of the session has started since the question was asked, or when an earlier reply to the same job's questions has already started its next attempt; submit again instead, with `matsya job submit --session <session>`.

## 4 Asking questions in a session

```
matsya ask <session> "Which equation characterizes the optimal consumption choice in this model?"
```

matsya-master answers from the retrieval index, the session's text and the outputs of the session's jobs. The command waits for the turn and prints, when the answer read a job's outputs, the line `Answer from` with the label and identifier of the job it used; then the answer; then the citations, each with the passage's path or the output's address, the heading, the page where the index records one, and the quoted sentence. Questions that end in a request for more information from you are printed as such. `--stage-file <path>` attaches a stage file of your own to the question; the service elaborates it and the answer reads its dossier.

A session may hold nothing but questions and answers, created with `matsya session new "a name"` and fed with `matsya session add <session> notes.md`; and a question may be asked in the session `matsya job submit` created, in which case, once the job has ended with a record, the answer reads that job's outputs.

## 5 Asking matsya-master to submit a job

In a session, after some discussion, you may ask in words:

```
matsya ask <session> "Submit this as a job."
```

matsya-master recognizes the request, starts a job from the session's text as it then stands, your request included, and answers with the job's label and identifier; the command prints the line to follow the job. With `--follow proposed-model` the command stays attached to that job, prints its steps, and writes the folder of §2 when it ends. Without the option the job runs on the server all the same, and `matsya job wait` follows it later. A question that merely mentions a job starts nothing: the role submits only on a request to build or to submit.

## 6 Several jobs on one model

Each submission from a session is a new job with the next number, and the session lists them with their labels:

```
matsya session show <session>
```

When no job is selected, matsya-master discusses the session's latest job that holds a record and during whose run you added no entry to the session; the questions you ask after it ended do not change which job that is, and a cancelled job is never chosen this way. To discuss another job of the session that holds a record, select it; to stop a queued or running job, cancel it:

```
matsya session select <session> <job>
matsya job cancel <job>
```

A job cancelled while it runs keeps its record and the usage of the calls it had made; a provider request already sent completes before it stops, and the interface promises nothing else. A job cancelled while queued never runs and holds no record. Cancelling a job that has already ended is refused with the sentence that the job has ended.

## 7 A paper

A paper is submitted as its text, in a Markdown or LaTeX file, and marked as a paper with `--paper`:

```
matsya job submit paper.md --paper --target stage
```

The command creates a session named `paper`, after the file, appends the paper's text to it as an entry of the kind `paper`, and starts the job from that session; `--name` gives the session another name, and `--session <session>` appends the paper to a session you already have and starts the job from it. The job reads the session's text as a paper: the Model-prose-writer quotes the passages of the paper on which the model prose rests, each with the heading it stands under where a heading stands above it, and the job goes on only when every quotation is found in the session's text and, where a heading is given with it, under that heading. Because the paper is an entry of the session, a job that ends `needs_input` appends its questions to the session after the paper; you reply to them there as §3 describes, and ask about the paper and the job's outputs in the same session (§4). `--no-session` sends the paper as the job's source with no session, and its questions then stand in its record only. Without `--paper` a file is a description. `matsya session add <session> paper.md --kind paper` appends a paper to a session without starting a job.

A PDF is refused before any request, with the sentence `A paper is sent as Markdown or LaTeX text; convert the PDF first.`; convert it to Markdown or LaTeX and submit that file. The paper's text is sent to the language-model provider; ask the service's administrator before submitting a paper that may not leave your machine.

## 8 The commands

| Command | What it does |
|---|---|
| `matsya`, `matsya docs [<page>] [--online]`, `matsya docs --all [--online]`, `matsya docs --path` | what Matsya is, where its guide is installed and whether a Matsya token is saved; this guide's pages in Markdown, as installed with the client or, with `--online`, as its public repository holds them today |
| `matsya configure` | saves your Matsya token and the service's address |
| `matsya index` | the index the service reads, the embedding model and the configuration's version |
| `matsya search "<query>" [--collections …] [--limit n]` | the passages of the index that match a query |
| `matsya job submit <file> --target <stage\|period\|trellis\|recipe> [--paper] [--name …] [--max-cycles n] [--no-session]`, `matsya job submit --session <session> --target …` | starts a job, from a file through a session it creates, or from a session's text |
| `matsya job status <job>`, `matsya job wait <job>` | a job's state, once or until it ends |
| `matsya job files <job> <folder> [--all-iterates] [--overwrite]` | writes the products, the report and the record into a folder |
| `matsya job cancel <job>` | cancels a queued or running job |
| `matsya session new "<name>"`, `matsya session add <session> <file> [--kind …] [--replies-to n]`, `matsya session show <session>`, `matsya session select <session> <job>` or `--none` | the session's record |
| `matsya ask <session> "<question>" [--stage-file <path>] [--follow <folder>]` | one question answered by matsya-master |
