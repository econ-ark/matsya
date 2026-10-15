---
title: Matsya client
audience: developer
type: index
topic: [matsya]
---

# Matsya client

Matsya is a service of Project Bellman. It reads an economist's description of a dynamic model, or a paper, writes the model in Bellman-SYM, the project's language for staged Bellman problems, checks what it wrote, and answers questions about models and about the language. It holds an index of the project's documentation and of the research literature on dynamic programming, and saved instructions that direct how it writes a model and answers a question, so that it can help an economist develop a dynamic model.

This package installs the command `bellman-matsya`, through which you, or the coding assistant working for you, reach the service. The command runs on your computer. On the server, **matsya-architect** runs a **job**, one attempt to write and check the stage files of a model from its description; **matsya-master** answers questions in a **session**, the saved description, questions and replies of one model. Install and configure the command once, in steps 1 and 2. Then either let your assistant use it, step 3, or run the commands yourself, step 4; step 5 keeps one model, its session and the files Matsya writes for it together in one folder.

## 1 Install the Bellman client

With Python 3.10 or newer, install the Bellman client from the `bellman-matsya-client/` subdirectory of the public [Matsya repository](https://github.com/econ-ark/matsya). This needs Git, but it does not require a Bellman checkout on your computer:

```sh
python -m pip install 'git+https://github.com/econ-ark/matsya.git#subdirectory=bellman-matsya-client'
bellman-matsya --help
```

The package is `bellman-matsya-client`, the command is `bellman-matsya`, and the Python module is `bellman_matsya`. The client connects to an existing service; this installation does not start or install the server. The public Matsya repository also contains an earlier Bellman client at its root. That package installs the different command `matsya`.

Installing the Bellman package does not uninstall the earlier package. If you no longer use the earlier `matsya` client, remove it from the environment that supplied its command with `python -m pip uninstall econ-ark-matsya`, or `pipx uninstall econ-ark-matsya` for a pipx installation. `type -a matsya bellman-matsya` on macOS or Linux, or `Get-Command matsya,bellman-matsya -All` in PowerShell, shows which installations your terminal selects. Use `bellman-matsya` for Bellman work.

An old standalone SSH launcher, including `econ-ark-matsya.ssh-remote.bak`, is not removed by uninstalling a Python package. Remove obsolete copies during the upgrade. The current Bellman client does not use that launcher; an assistant must not run it as a fallback when `bellman-matsya` fails.

To update an existing Bellman client, run:

```sh
python -m pip install --force-reinstall 'git+https://github.com/econ-ark/matsya.git#subdirectory=bellman-matsya-client'
```

Your saved Bellman token and any custom service address remain in place.

## 2 Enter the new Bellman token

The administrator sends you a **Matsya token**, a private string beginning `msy_`. The client uses `http://45.55.225.169:8710` as the Bellman Matsya service address automatically. This preliminary HTTP connection sends the token and your requests without encryption. Keep the token private.

Run `bellman-matsya configure` and enter the new token when prompted. The command saves the token in `~/.config/bellman-matsya/config.toml` and keeps any custom service address already saved there. Without a custom address, the client uses its built-in address. The environment variables `BELLMAN_MATSYA_TOKEN` and `BELLMAN_MATSYA_SERVER` override saved values; remove outdated values before configuring a new token. The earlier `~/.config/matsya/config.toml` and `MATSYA_TOKEN` or `MATSYA_SERVER` variables are not read. The token is visible while you paste it, but later command output does not print it. Give it to the client in your terminal, not to an assistant in chat.

Run `bellman-matsya index` to check access. A successful response prints the index digest, embedding model and configuration version. A refusal means the token was not accepted; a connection error means the address or connection needs attention. Check those with the administrator before starting a job.

Only after `bellman-matsya index` succeeds may you add, if you wish, a **personal Anthropic key**, an Anthropic API key of your own, so that the language-model calls of the jobs and questions you start are charged to your own Anthropic account in place of the service's account. The key is an optional addition to the Matsya token, never a substitute for it. Run `bellman-matsya configure --set-anthropic-key` and type the key at its prompt, which does not show it; the command refuses to save a key on a machine where no Matsya token is configured, and saves it in `~/.config/bellman-matsya/anthropic-key`, a file that only you can read. `bellman-matsya configure --clear-anthropic-key` removes it. The environment variable `BELLMAN_MATSYA_ANTHROPIC_KEY`, set from a private file, supplies a key without saving it and is used in place of a saved key. The client sends the key only with a job, a question or a reply that may start a job, and only to an HTTPS address or to a service on your own machine (`localhost`, `127.0.0.1` or `::1`). The address `http://45.55.225.169:8710` uses plain HTTP, so the client refuses to send a key there, and the service at that address does not yet use personal keys. Give the key to the client in your own terminal, never to an assistant in chat. `bellman-matsya` alone says which key the next job will use, and a command whose work runs under your key prints `Credential: your Anthropic API key`; [the command-line guide](docs/02-working-from-the-command-line.md) §1.1 gives the details.

## 3 Let your assistant work with Matsya

You do not need to learn the commands. A coding assistant can run the installed client for you. The bare command `bellman-matsya` prints an introduction and points to its guide; it does not start a server. `bellman-matsya index` contacts the Bellman Matsya service.

Open the folder that holds your model's description in your coding assistant, and give it this instruction:

> In this folder, first run `bellman-matsya` and confirm that it describes Project Bellman and Bellman-SYM. Then run `bellman-matsya docs --all` and read the installed guide. Run `bellman-matsya index` to check access to the Bellman service. Tell me whether these steps succeeded. If a step fails, stop and report the problem. Do not ask me to paste my token in chat, and do not submit a job until I ask.

This instruction works for an existing installation too: the first-use message appears only when no configuration file exists. Once the assistant has completed these checks, say what you want in your own words.

Every job names its **target**, the level of the declaration it returns: `stage`, one stage file, which states one decision problem; `period`, the stage files of one model period and the period file `period.yml` that joins them; `trellis`, the stage files, the period files and `trellis.yml`, which orders the periods in time up to the terminal period; or `recipe`, the files of a trellis together with a methods file for each stage whose solution method the source states (a stage without one is admitted), the calibration and settings files, and the recipe file `spec.yml` that names them for each stage. Name the target when you ask for a build. For example:

```
Build the model described in economics.md as a trellis.
```

Claude Code runs `bellman-matsya job submit economics.md --target trellis`, follows the job to its end, and then runs `bellman-matsya job files <job> <new folder>`. The folder holds the available declaration files, `economics.md` containing the prose from which those files were written, and `report.md`. The report states whether the job converged and shows the prose judges' findings separately from the comparison of the elaborated semantic objects constructed from the declarations. A job that stopped before writing files still returns its report and record.

Two things can then happen. If the job ended with questions, because the description left something necessary unsaid, the questions stand in the session; you answer them and the next job starts from your answer, at the same target:

```
Answer matsya-architect's first question: the gross return on assets is R, and assets cannot be negative.
```

Claude Code runs `bellman-matsya session show <session>` to find the question's entry number, writes your answer to a file, runs `bellman-matsya session add <session> <file> --replies-to <entry number>`, which starts the next job, and follows that job with `bellman-matsya job wait <new job>`. A reply starts a job only when it answers a question of the latest job that is waiting for input.

If instead the job ran its cycles and its report records what the two judges found, you ask about it:

```
What did the two judges disagree on in that job?
```

Claude Code runs `bellman-matsya ask` in the session the job created and shows you the answer with its citations.

The guide the assistant reads is installed with the command; its files are also in [`bellman-matsya-client/docs/`](https://github.com/econ-ark/matsya/tree/main/bellman-matsya-client/docs) in the public Matsya repository. `bellman-matsya docs --online` reads the current pages from that directory. Those pages may describe a newer client than the one installed on your machine.

## 4 Or run the commands yourself

Every command is also meant to be typed by hand. `bellman-matsya --help` lists them, and the user guide explains each with what it prints. The four you will use most are `bellman-matsya job submit model.md --target trellis`, which has the model described in the file built and checked at the target named, `bellman-matsya job wait <job>`, which follows that work to its end, `bellman-matsya job files <job> <new folder>`, which writes the files of the target, the model prose and the report into a folder of yours, and `bellman-matsya ask <session> "your question"`, which asks a question about a model in the session the first command created. `bellman-matsya job submit` refuses a job whose command names no target, and prints the four targets.

A paper is submitted as its text, in a Markdown or LaTeX file, with the option `--paper`: `bellman-matsya job submit paper.md --paper --target stage` appends the paper to a new session as an entry of the kind `paper` and starts the job from that session; the job reads the session's text as a paper, and its questions stand in the session, as any other job's do. Without `--paper`, a file is a description. A PDF is refused before any request, with the sentence `A paper is sent as Markdown or LaTeX text; convert the PDF first.`, so convert it to Markdown or LaTeX before you submit it. The paper's text is sent to the language-model provider; ask the service's administrator before you submit a paper that may not leave your machine.

## 5 Keep a model in a project folder

A **project folder** is a folder for one model that remembers the model's session: your description in `economics.md`, the model's declaration as it stands in `declaration/`, with the stage files under `declaration/stages/<key>/<key>.bl`, and a small folder `.bellman-matsya/` that the command writes.

The Bellman client does not read an earlier `.matsya/` folder or reuse its session automatically. Keep your authored `economics.md` and `declaration/`, and run the following command in the model folder to create its Bellman session:

```
bellman-matsya project init
```

The command creates a session named after the folder, appends `economics.md` to it as the first entry, and writes `.bellman-matsya/project.json`, which holds the session's identifier, and `.bellman-matsya/README.md`, a note on the folder and its commands. It also writes `AGENTS.md`, a paragraph that points a coding assistant to that note, unless the folder already has an `AGENTS.md`, in which case it leaves the file as it is and prints the paragraph for you to add.

From then on you run four commands in the folder, and the first three find the session in `.bellman-matsya/project.json` themselves. `bellman-matsya project submit` appends `economics.md` to the session when you have changed it, and starts a job with the files of `declaration/` as its starting point, at the target those files imply, or the one `--target` names. `bellman-matsya project status` prints the session's jobs, each by its label, a line such as `household · stage · version 2 · job 3 · converged` that names the model, the target, the version of your text the job read, the job's number and its state, and each question awaiting your reply, with the exact command that answers it. `bellman-matsya project pull --replace` writes the files of the latest job that has ended with a record into `declaration/`, each replacing the file of the same name and the others left in place, together with the job's report as `report.md` and any model prose as `model-prose.md`; it never writes `economics.md`. An open writer's note goes to `.bellman-matsya/writer-note.md`, leaving your stage page in place. Without `--replace`, the command writes the job's files into a new folder, `bellman-matsya-output/job-<number>/`, and leaves `declaration/` as it is. `bellman-matsya ask <session> "your question"`, with the session's identifier that `bellman-matsya project status` prints, asks about the model. A coding assistant working in the folder reads `.bellman-matsya/README.md` and runs the same commands.

## Source and license

The Bellman client source for installation is in `bellman-matsya-client/` of the [public Matsya repository](https://github.com/econ-ark/matsya); the Bellman repository keeps a development copy in `packages/bellman-matsya-client/`. Its version is recorded in `pyproject.toml`, and its license is [Apache 2.0](LICENSE). It calls the Bellman service's `/v1/` routes. The earlier Bellman client remains at the public repository root.
