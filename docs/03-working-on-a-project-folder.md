---
title: Working on a project folder
audience: user
type: user-guide
topic: [matsya]
---

# Working on a project folder

> [!summary]
> This page follows one project folder, a model's own folder that keeps the model's session, from `bellman-matsya project init` to `bellman-matsya project pull`, with what each command prints, and shows a job's files written back into the folder or into a sub-folder of it.

> [!info]- Relationship with other documents
> **Builds on** — [Working with Matsya from the command line](02-working-from-the-command-line.md), the commands of a session and a job, and [For an assistant using Matsya](00-for-a-local-model.md) §4, which defines the project folder and gives its commands in order.
> **Continued by** — [Reaching the service by HTTP](04-the-service-by-http.md), the requests that the commands send, for a user without the client.

## 1 Begin with the model's files

Suppose the folder `household/` contains the description you wrote in `economics.md` and a stage file at `declaration/stages/household/household.bl`. Other project folders may also contain period, trellis, recipe, methods, calibration or settings files. [For an assistant using Matsya](00-for-a-local-model.md) §4 defines this layout and the **target**, the level of declaration the job is asked to return. This example has no such additional files, so its target is `stage`.

From inside `household/`, run:

```text
bellman-matsya project init
```

The command creates a session named `household`, appends the text of `economics.md` as its first entry, and prints its session identifier. Its output includes these lines, with the identifier and folder path filled in:

```text
Project folder: <absolute path to household>
Session <session>: household
Entry 1: the text of economics.md
Wrote .bellman-matsya/project.json and .bellman-matsya/README.md
Wrote AGENTS.md, whose paragraph points an assistant to .bellman-matsya/README.md
Submit the model, in the project folder, with: bellman-matsya project submit
```

The file `.bellman-matsya/project.json` records the session identifier, the service address and a digest of `economics.md` used to recognize later edits; it holds no Matsya token. The short `.bellman-matsya/README.md` names the files and commands of this folder. If `AGENTS.md` already exists, `init` leaves it unchanged and prints the paragraph for you to add. If `economics.md` is absent or empty, the session has no entry yet; write the description before submitting the model.

## 2 Submit and inspect a job

In the same folder, run:

```text
bellman-matsya project submit
bellman-matsya job wait <job>
```

Use the identifier in the `Follow it with: bellman-matsya job wait <job>` line printed by `submit`. The submission sends the session's text and the declaration files already in the folder. It lists each file sent as the **starting declaration**, the files the job first checks, and names any files it leaves out. A stage page such as `declaration/stages/household/household.md` is left out: it explains the stage but is not a declaration file. For this example, the printed lines include `Starting declaration: household.bl` and `Target: stage, read from declaration/`. The command then prints the job's label, its identifier, its initial state and the command for following it. Use `--target period`, `--target trellis` or `--target recipe` only when you want a different level from the one the folder implies; `--max-cycles <n>` limits its cycles of writing and checking.

The description is not appended again when its bytes have not changed since the session last received it. After you edit `economics.md`, the next `bellman-matsya project submit` appends the new text as another session entry before starting its job. `bellman-matsya project status` tells you whether it has changed. It prints the session identifier and version of its text, its numbered entries, its jobs with their labels, any selected job, any question awaiting a reply, and the commands for asking or answering a question. Use `bellman-matsya job wait <job>` to observe when a queued or running job ends. A job can end `converged`, `not_converged`, `needs_input`, `cancelled`, `failed` or `interrupted`; an ended job is not necessarily a declaration to keep.

## 3 Ask or answer a question

If the job ends `needs_input`, run `bellman-matsya project status` and read its question. If an entry was added to the session while the job ran, its questions remain in the job record instead; read them with `bellman-matsya job status <job>`. For a question that awaits a reply in the session, `project status` gives its entry number and a line of this form:

```text
Reply with: bellman-matsya session add <session> <file> --replies-to <entry number>
```

Put your answer in a text file and run that line with the actual file path. A reply to a question from the job currently waiting for input starts one new job; the command prints its identifier and `Follow it with: bellman-matsya job wait <job>`. If a later job has already started, the reply remains in the session but starts no job. To ask about the model or a job's result, use the other line printed by `project status`:

```text
bellman-matsya ask <session> "<question>"
```

This asks matsya-master, the part of Matsya that answers questions in a session. It does not write a stage file. The project has no separate `project ask` command; the ordinary `bellman-matsya ask` and `bellman-matsya session add` commands use the session identifier that `project status` prints.

## 4 Write a job's files

Inspect the job's final state and report before deciding where its files belong. `bellman-matsya project pull` chooses the latest ended job of this session that holds a record; `bellman-matsya project pull <job>` names a particular job. By default it writes a complete model folder into `bellman-matsya-output/job-<number>/`. You can name a different new or empty sub-folder with `--into <subfolder>`:

```text
bellman-matsya project pull
bellman-matsya project pull <job> --into second-look
```

The command first prints the status and source sections of the job's report, then `Wrote <n> files to <subfolder>:` and the paths it wrote. The job's model prose is `economics.md` inside this output sub-folder; the project's own `economics.md` and `declaration/` are unchanged. Use a new sub-folder for the second command; a nonempty one is refused.

When you want the job's declaration in the project folder, run:

```text
bellman-matsya project pull <job> --replace
```

This writes each returned declaration file to its corresponding path under `declaration/`, marking a file it replaced with `(replaced)` in the printed list. It writes `report.md` and, when the job holds model prose, `model-prose.md`. An open writer's note goes to `.bellman-matsya/writer-note.md`, apart from an author's stage page. It never writes the user's `economics.md`, and it keeps existing declaration files the job did not produce, listing them after the files written. `--replace` and `--into` cannot be used together. The [command reference](05-the-command-reference.md) gives every option and the exact fields of the `--json` answer.

## 5 Work with an assistant and the Workbench

An assistant can read `.bellman-matsya/README.md` and `bellman-matsya docs --all`, run these commands for you, and use `--json` on the project, job, session and ask commands to read their structured answers. You can open the same model folder in the [Bellman Workbench](../../overview/07-workbench.md) to inspect its stage files. The service keeps the session's entries and job records; `bellman-matsya project status` reads them from it each time. A pull into a sub-folder also writes a copy of the job's record there as `record.json`. You decide which job to inspect and whether to replace local files.
