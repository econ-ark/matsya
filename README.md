# Matsya client

Matsya is a service of Project Bellman. It reads an economist's description of a dynamic model, or a paper, writes the model in Bellman-SYM, the project's language for staged Bellman problems, checks what it wrote, and answers questions about models and about the language. It holds an index of the project's documentation and of the research literature on dynamic programming, and saved instructions that direct how it writes a model and answers a question, so that it can help an economist develop a dynamic model.

This package installs the command `matsya`, through which you, or the coding assistant working for you, reach the service. The command runs on your computer. On the server, **matsya-architect** runs a **job**, one attempt to write and check the stage files of a model from its description; **matsya-master** answers questions in a **session**, the saved description, questions and replies of one model. Install and configure the command once, in steps 1 and 2. Then either let your assistant use it, step 3, or run the commands yourself, step 4.

## 1 Install the command

Open a terminal, the application in which you type commands (Terminal on a Mac, a shell on Linux, PowerShell on Windows), and type the following line, then press Enter:

```
pip install git+https://github.com/econ-ark/matsya
```

The installation needs Python 3.10 or newer and nothing else, and it ends with a line saying that `econ-ark-matsya` was installed. If your system's Python refuses to install packages, the message says so, type `pipx install git+https://github.com/econ-ark/matsya` instead, which gives the command an environment of its own. Afterwards, typing `matsya --help` prints the list of commands, which shows that the installation worked.

## 2 Enter your Matsya token

The service knows you by a **Matsya token**, a string of letters and digits beginning `msy_`, which the service's administrator sends you by private message together with the service's **address**, a line beginning `http://` or `https://`. Have both at hand, because the next command asks for them one after the other. In the terminal, type

```
matsya configure
```

and press Enter. Because no configuration file exists yet, the command first prints two lines meant for a coding assistant, which no command prints once your Matsya token and the address are saved:

```
This is the first use of matsya on this machine.
A model working for the user reads the guide first: matsya docs --all
```

Next it prints its title line,

```
Matsya: save your Matsya token and the service address
```

and then asks for the token:

```
Enter your Matsya token:
```

Paste the Matsya token after the colon, exactly as you received it, and press Enter. If what you pasted does not begin with `msy_`, the command stops with the sentence `Error: a Matsya token begins with msy_. Check the Matsya token you received and try again.`, and you type `matsya configure` once more. Otherwise it asks for the address:

```
Enter the service address supplied by Econ-ARK-admin:
```

Paste the address and press Enter. The command then prints where it saved the two,

```
Matsya token and service address saved to /Users/you/.config/matsya/config.toml
```

with your own home folder in place of `/Users/you`, followed by the reminder that the service keeps the entries of your sessions and the records of your jobs, and the line `Check your access with: matsya index`. The two values are saved in that private file only. The client does not print the Matsya token in later output, though a connection error may show the service's address; the token is shown on the screen while you paste it, so paste it where no one is looking over your shoulder. The client sends the token with each request, and if the address begins `http://` rather than `https://`, the request sends it without encryption.

To check, type `matsya index` and press Enter. When the service accepts you, it prints three lines: the index digest, a fingerprint of the indexed material the service reads, the embedding model, and the configuration's version. When it does not, it prints one line beginning `Error: The service refused the request (401)`, which means the token was mistyped or is not known to the service, or a line saying that the connection failed, which means the address was mistyped or the service is unreachable; in either case type `matsya configure` again and enter the values once more.

## 3 Let your assistant work with Matsya

You do not need to learn the commands. A coding assistant such as Claude Code runs them for you, and Matsya tells the assistant how: typed alone, `matsya` answers with where its guide is and how to read it. So instruct your assistant to ask Matsya how to read its instructions.

In Claude Code, open the folder that holds your model's description and type at its prompt:

```
Ask matsya how it works, read its instructions, and then use the matsya command for me.
```

Claude Code runs `matsya`, which points it to the guide; it reads the guide with `matsya docs --all`; and it is then ready. From then on, say what you want in your own words.

Every job names its **target**, the level of the declaration it returns: `stage`, one stage file, which states one decision problem; `period`, the stage files of one model period and the period file `period.yml` that joins them; `trellis`, the stage files, the period files and `trellis.yml`, which orders the periods in time up to the terminal period; or `recipe`, the files of a trellis together with a methods file for each stage whose solution method the source states (a stage without one is admitted), the calibration and settings files, and the recipe file `spec.yml` that names them for each stage. Name the target when you ask for a build. For example:

```
Build the model described in economics.md as a trellis.
```

Claude Code runs `matsya job submit economics.md --target trellis`, follows the job to its end, and then runs `matsya job files <job> <new folder>`, which writes the files of the target, the model prose and `report.md` into a folder of yours; it reports the job's final state (a finished job is not necessarily a converged one) and shows you the report and, when the job reached the writing step, the files it wrote, to compare with the model you intended; a job that stopped earlier to ask for input leaves `report.md` and the record and no stage file.

Two things can then happen. If the job ended with questions, because the description left something necessary unsaid, the questions stand in the session; you answer them and the next job starts from your answer, at the same target:

```
Answer matsya-architect's first question: the gross return on assets is R, and assets cannot be negative.
```

Claude Code runs `matsya session show <session>` to find the question's entry number, writes your answer to a file, runs `matsya session add <session> <file> --replies-to <entry number>`, which starts the next job, and follows that job with `matsya job wait <new job>`. A reply starts a job only when it answers a question of the latest job that is waiting for input.

If instead the job ran its cycles and its report records what the two judges found, you ask about it:

```
What did the two judges disagree on in that job?
```

Claude Code runs `matsya ask` in the session the job created and shows you the answer with its citations.

The guide the assistant reads is installed with the command; it is also online at <https://econ-ark.github.io/bellman/matsya/user-guide/>.

## 4 Or run the commands yourself

Every command is also meant to be typed by hand. `matsya --help` lists them, and the user guide explains each with what it prints. The four you will use most are `matsya job submit model.md --target trellis`, which has the model described in the file built and checked at the target named, `matsya job wait <job>`, which follows that work to its end, `matsya job files <job> <new folder>`, which writes the files of the target, the model prose and the report into a folder of yours, and `matsya ask <session> "your question"`, which asks a question about a model in the session the first command created. `matsya job submit` refuses a job whose command names no target, and prints the four targets.

A paper is submitted as its text, in a Markdown or LaTeX file, with the option `--paper`: `matsya job submit paper.md --paper --target stage` appends the paper to a new session as an entry of the kind `paper` and starts the job from that session; the job reads the session's text as a paper, and its questions stand in the session, as any other job's do. Without `--paper`, a file is a description. A PDF is refused before any request, with the sentence `A paper is sent as Markdown or LaTeX text; convert the PDF first.`, so convert it to Markdown or LaTeX before you submit it. The paper's text is sent to the language-model provider; ask the service's administrator before you submit a paper that may not leave your machine.

## Source and license

The client is developed in the Bellman project's repository and published here; its version is the one in `pyproject.toml`, tagged at each release. This repository first held an earlier client of the previous Matsya service, whose last commit was `6b1bf86`, under the Apache 2.0 license retained in [LICENSE](LICENSE); the present code calls the current Matsya service's `/v1/` routes and no other service.
