---
title: Working with Matsya from the command line
audience: user
type: user-guide
topic: [matsya]
---

# Working with Matsya from the command line

> [!summary]
> This page follows one piece of work through the command `bellman-matsya`, from installation to the folder of stage files, with the commands as you type them and what each prints. The command is matsya-client of [Matsya in three parts](index.md): a program that sends your requests to the service and writes what comes back. Service commands take `--json` to print the service's answer unchanged; project commands use it to print an answer assembled from the project folder and the service. The bare `bellman-matsya` command, `configure` and `docs` have no JSON form. `bellman-matsya <command> --help` lists a command's options.

> [!info]- Relationship with other documents
> **Builds on** — [Matsya in three parts](index.md), which defines the three parts and the words session, job, turn, version, label and target, and [The roles and the work of a job](01-the-roles-and-the-work-of-a-job.md), which names the roles whose steps `bellman-matsya job wait` prints.
> **Continued by** — [Working on a project folder](03-working-on-a-project-folder.md), the same work done in a model's own folder, which remembers the model's session.
> **See also** — [The command reference](05-the-command-reference.md), every option, printed line, exit status and JSON field of the commands this page uses; [Stages](../../Bellman-Sym/01-stage.md) and [Constraints](../../Bellman-Sym/10-constraints.md) in the language guide, for reading the stage files a job writes.
> **Explained for developers in** — the [Matsya developer guide](../dev-guide/index.md).

## 1 Installing and setting up

The package `bellman-matsya-client` installs the command `bellman-matsya` and the Python module `bellman_matsya`; it needs Python 3.10 or newer. Install it from the `bellman-matsya-client/` subdirectory of the public [Matsya repository](https://github.com/econ-ark/matsya). This needs Git, but no Bellman checkout on your computer:

```sh
python -m pip install 'git+https://github.com/econ-ark/matsya.git#subdirectory=bellman-matsya-client'
bellman-matsya --help
```

To update the client, run `python -m pip install --force-reinstall 'git+https://github.com/econ-ark/matsya.git#subdirectory=bellman-matsya-client'`. The client installation does not install or start the service.

The public Matsya repository retains an earlier Bellman client package, `econ-ark-matsya`, at its root. It installs the different command `matsya`; the current Bellman installation does not remove it. If you no longer use it, remove it from its Python environment with `python -m pip uninstall econ-ark-matsya`, or use `pipx uninstall econ-ark-matsya` for a pipx installation. To find command installations, use `type -a matsya bellman-matsya` on macOS or Linux, or `Get-Command matsya,bellman-matsya -All` in PowerShell. Use `bellman-matsya` for Bellman work.

The service's administrator gives you a new token beginning `msy_`. The client uses the Bellman service at `http://45.55.225.169:8710` automatically. This preliminary HTTP connection sends the token and your requests without encryption. Keep the token private. Run:

```
bellman-matsya configure
bellman-matsya index
```

`configure` asks only for the token, then saves it in `~/.config/bellman-matsya/config.toml` without contacting the service. It retains a custom service address already saved in that file; otherwise the client uses its built-in address. This file survives a package upgrade. `BELLMAN_MATSYA_TOKEN` and `BELLMAN_MATSYA_SERVER` override saved values, so remove outdated values before configuring a new token. The earlier `~/.config/matsya/config.toml` and `MATSYA_TOKEN` or `MATSYA_SERVER` variables are not read. At the first use with neither a Bellman configuration file nor `BELLMAN_MATSYA_TOKEN`, the command prints two lines directing an assistant to `bellman-matsya docs --all`; an upgrade with an existing configuration file does not print them. `index` checks access and prints the digest of the material Matsya can retrieve, the embedding model and the configuration version. A refused request or connection error needs correction before a job is submitted. The command does not print the token in its later output.

An earlier `.matsya/project.json` is not read by this client. Keep your authored `economics.md` and `declaration/`, then run `bellman-matsya project init` in the model folder to create a Bellman session and its `.bellman-matsya/` metadata. [Working on a project folder](03-working-on-a-project-folder.md) gives the remaining steps.

## 2 A job from a description

Write the model's description in a Markdown file, with the states, the choices, the constraints, the shocks, the timing and the objective in prose and displayed equations. Then:

```
bellman-matsya job submit model.md --target stage
```

The option `--target` names the job's target, what the job is to return, `stage`, `period`, `trellis` or `recipe`, as [Matsya in three parts](index.md) §2 defines them; the command refuses a submission that names none, before any request. The command creates a session named `model`, after the file, appends the file's text to it as entry 1, and starts a job from that session. It prints the session's identifier and name, the entry's number, the job's identifier and its state `queued`, and two lines: how to follow the job, and how to see the session, where the job's questions and your replies are kept. `--name "Household with firms"` gives the session another name; `--max-cycles 2` permits two iterations after the initial declaration, hence at most three declarations and their elaborated semantic objects; `--no-session` submits the file as the job's source with no session, in which case the job's questions stand in its record only.

```
bellman-matsya job wait <job>
```

The command polls the job and prints a line whenever its step or iteration changes, naming the step and the role that computes it, among the roles of [The roles and the work of a job](01-the-roles-and-the-work-of-a-job.md) §1: `preparation` (the Model-prose-writer and the prose-source-judge), `writing` (Prose-to-Bellman-Sym and elaboration, first for the initial declaration and then once per iteration), `prose_writing` (Semantics-to-Prose) and `judging` (the prose-roundtrip-judge). The program compares adjacent elaborated semantic objects after writing. When the job ends it prints the final state and its reason: `converged`; `not_converged`, with the reason, such as the cycle limit reached; `needs_input`, with the numbered questions and a sentence that says whether they stand in the session; or `failed`, with its code. `bellman-matsya job status <job>` prints the same without waiting.

```
bellman-matsya job files <job> proposed-model
```

The command writes the job's products into the folder, which must be new or empty: the available stage files under `declaration/stages/<key>/<key>.bl`, the writer's note, when it leaves something open, beside a single stage as `<key>.md` and otherwise as `declaration/notes.md`, any period, trellis, calibration, settings or methods file under `declaration/` by its name, the prose paired with those files as `economics.md`, the report as `report.md`, and the record the service returned as `record.json`. Run it for a `not_converged` job too: it saves any work the job produced, while the report says why the checks did not conclude. If no declaration file was produced, the folder contains only the prose, report and record that exist. The report states the job's label, its final state and reason, the iterations run, what each judge found, whether the adjacent elaborated semantic objects are equivalent, the questions and the language-model tokens charged. `--all-iterates` adds `iterates/initial/` and one `iterates/cycle-<n>/` folder per iteration, with each declaration and its input prose, plus the complete record.

## 3 Replying to a job's questions

A job that ends `needs_input` has written its questions into the session as entries, provided you added no entry to the session while it ran; otherwise they stand in its record alone, where `bellman-matsya job status` prints them, and you submit again. Read them and reply:

```
bellman-matsya session show <session>
bellman-matsya session add <session> reply.md --replies-to <entry number>
```

The reply is an entry of the session, and because it answers a question of the session's latest job, it starts the next job at once, with the text as it now stands. Follow it with `bellman-matsya job wait`. A reply is kept in the session but starts nothing when a later job of the session has started since the question was asked, or when an earlier reply to the same job's questions has already started its next attempt; submit again instead, with `bellman-matsya job submit --session <session>`.

## 4 Asking questions in a session

```
bellman-matsya ask <session> "Which equation characterizes the optimal consumption choice in this model?"
```

matsya-master answers from the retrieval index, the session's text and the outputs of the session's jobs. The command waits for the turn and prints, when the answer read a job's outputs, the line `Answer from` with the label and identifier of the job it used; then the answer; then the citations, each with the passage's path or the output's address, the heading, the page where the index records one, and the quoted sentence. Questions that end in a request for more information from you are printed as such. `--stage-file <path>` attaches a stage file of your own to the question; the service elaborates it and the answer reads its dossier ([The roles and the work of a job](01-the-roles-and-the-work-of-a-job.md) §1).

A session may hold nothing but questions and answers, created with `bellman-matsya session new "a name"` and fed with `bellman-matsya session add <session> notes.md`; and a question may be asked in the session `bellman-matsya job submit` created, in which case, once the job has ended with a record, the answer reads that job's outputs.

## 5 Asking matsya-master to submit a job

In a session, after some discussion, you may ask in words:

```
bellman-matsya ask <session> "Submit this as a job."
```

matsya-master recognizes the request, starts a job from the session's text as it then stands, your request included, and answers with the job's label and identifier; the command prints the line to follow the job. With `--follow proposed-model` the command stays attached to that job, prints its steps, and writes the folder of §2 when it ends. Without the option the job runs on the server all the same, and `bellman-matsya job wait` follows it later. A question that merely mentions a job starts nothing: the role submits only on a request to build or to submit.

## 6 Several jobs on one model

Each submission from a session is a new job with the next number, and the session lists them with their labels:

```
bellman-matsya session show <session>
```

matsya-master discusses the session's selected job or, when none is selected, the latest job that [Matsya in three parts](index.md) §3 names; the questions you ask after that job ended do not change which job it is. To discuss another job of the session that holds a record, select it; to stop a queued or running job, cancel it:

```
bellman-matsya session select <session> <job>
bellman-matsya job cancel <job>
```

A job cancelled while it runs keeps its record and the usage of the calls it had made; a provider request already sent completes before it stops, and the interface promises nothing else. A job cancelled while queued never runs and holds no record. Cancelling a job that has already ended is refused with the sentence that the job has ended.

## 7 A paper

A paper is submitted as its text, in a Markdown or LaTeX file, and marked as a paper with `--paper`:

```
bellman-matsya job submit paper.md --paper --target stage
```

The command creates a session named `paper`, after the file, appends the paper's text to it as an entry of the kind `paper`, and starts the job from that session; `--name` gives the session another name, and `--session <session>` appends the paper to a session you already have and starts the job from it. The job reads the session's text as a paper: the Model-prose-writer quotes the passages of the paper on which the model prose rests, each with the heading it stands under where a heading stands above it, and the job goes on only when every quotation is found in the session's text and, where a heading is given with it, under that heading. Because the paper is an entry of the session, a job that ends `needs_input` appends its questions to the session after the paper; you reply to them there as §3 describes, and ask about the paper and the job's outputs in the same session (§4). `--no-session` sends the paper as the job's source with no session, and its questions then stand in its record only. Without `--paper` a file is a description. `bellman-matsya session add <session> paper.md --kind paper` appends a paper to a session without starting a job.

A PDF is refused before any request, with the sentence `A paper is sent as Markdown or LaTeX text; convert the PDF first.`; convert it to Markdown or LaTeX and submit that file. The paper's text is sent to the language-model provider; ask the service's administrator before submitting a paper that may not leave your machine.

## 8 The commands

The table lists the commands of this page. [The command reference](05-the-command-reference.md) gives each command with its options and their defaults, the lines it prints, its exit statuses and the fields of its `--json` answer, and [Working on a project folder](03-working-on-a-project-folder.md) follows the commands of a project folder.

| Command | What it does |
|---|---|
| `bellman-matsya`, `bellman-matsya docs [<page>] [--online]`, `bellman-matsya docs --all [--online]`, `bellman-matsya docs --path` | what Matsya is, where its guide is installed and whether a Matsya token is saved; this guide's pages in Markdown, as installed with the client or, with `--online`, as its public repository holds them today |
| `bellman-matsya configure` | saves your Matsya token and retains any custom service address already saved |
| `bellman-matsya index` | the index the service reads, the embedding model and the configuration's version |
| `bellman-matsya search "<query>" [--collections …] [--limit n]` | the passages of the index that match a query |
| `bellman-matsya job submit <file> --target <stage\|period\|trellis\|recipe> [--paper] [--name …] [--max-cycles n] [--no-session]`, `bellman-matsya job submit --session <session> --target …` | starts a job, from a file through a session it creates, or from a session's text |
| `bellman-matsya job status <job>`, `bellman-matsya job wait <job>` | a job's state, once or until it ends |
| `bellman-matsya job files <job> <folder> [--all-iterates] [--overwrite]` | writes the products, the report and the record into a folder |
| `bellman-matsya job cancel <job>` | cancels a queued or running job |
| `bellman-matsya session new "<name>"`, `bellman-matsya session add <session> <file> [--kind …] [--replies-to n]`, `bellman-matsya session show <session>`, `bellman-matsya session select <session> <job>` or `--none` | the session's record |
| `bellman-matsya ask <session> "<question>" [--stage-file <path>] [--follow <folder>]` | one question answered by matsya-master |
