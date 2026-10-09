---
title: Matsya in three parts
audience: user
type: user-guide
topic: [matsya]
---

# Matsya in three parts

> [!summary]
> Matsya turns an economist's description of a dynamic model, or a paper, into a declaration in [Bellman-SYM](../../wiki/sym.md), the project's language for staged Bellman problems, checks the declaration, and answers questions about models and about the language. It has three parts, and this page says what each does and what it does not do: **matsya-client**, the command you run on your own machine, a program with no language model in it; **matsya-architect**, the service's job side, which builds and checks a declaration in one run; and **matsya-master**, the service's conversation side, which answers one question at a time. It then defines the three words that the parts share, **session**, **job** and **turn**, and shows how a piece of work moves between them.

> [!info]- Relationship with other documents
> **Continued by** — [Working with Matsya from the command line](01-working-from-the-command-line.md), the commands and what each prints, [The Python module and the files the client writes](01a-the-python-module.md), and [The roles of Matsya and when to use them](01b-the-roles-and-when-to-use-them.md), which says which command answers which kind of request.
> **For a coding assistant reading this for a user** — these pages are the instructions: what Matsya is, the commands and what each prints, and where the local files live; every command answers in JSON with `--json`, and a refusal is one sentence with exit status 1 (the service refused) or 2 (the arguments).
> **Explained for developers in** — the [Matsya developer guide](../dev-guide/index.md), which describes the program, the configuration, the retrieval index and the handlers.
> **See also** — the wiki pages [Matsya collection](../../wiki/matsya_collection.md), [Matsya handler](../../wiki/matsya_handler.md) and [Matsya instructions](../../wiki/matsya_instructions.md); [Stages](../../Bellman-Sym/01-stage.md) in the language guide for the stage files a job writes.

## 1 The three parts

**matsya-client** is the command `matsya` and the Python module of the same name, installed on your machine from the package `econ-ark-matsya`. It is a program: it holds no language model and makes no decision about economics. It sends your requests to the service with your **Matsya token**, the password-less identifier the service's administrator gives you; it waits for a job and prints its progress; it writes the files a job produced into a folder in the layout the project's applications use; and it composes the job's report from the job's record. Everything it prints or writes is either the service's answer or a fixed sentence.

**matsya-architect** is the job side of the service. One **job** is one run: from the source material, the text of a session or a file submitted on its own, the Model-prose-writer restates the model in prose, Prose-to-Bellman-Sym writes the stage files, the elaborator checks that they parse and mean what they say, Semantics-to-Prose writes the model back into prose from the checked files, and two judges compare the prose with its source and with that round-trip prose; the cycle repeats until the comparisons agree or the allowed number of cycles is spent. A job asks nothing of you while it runs. It is interactive in one sense only: a question it cannot settle ends the job, the question is written into the session, and your reply starts the next attempt, which is a new job. A job runs on the server for minutes and is charged for the language-model text it sends and receives.

**matsya-master** is the conversation side of the service. It answers one question at a time, asked in a session, from three things: the passages of the retrieval index, the project's documentation and the literature your Matsya token may read; the session's text; and the outputs of the session's jobs. Its answers quote their sources and cite them. It writes no stage file itself. When you ask it to build, it submits a job to matsya-architect from the session, and tells you so by the job's label.

| Part | Where it runs | What it does | What it does not do |
|---|---|---|---|
| matsya-client | your machine | sends requests, waits, writes the folder, composes the report | nothing with a language model |
| matsya-architect | the server | builds and checks a declaration in one run of cycles | talk to you while it runs |
| matsya-master | the server | answers one question in a session; submits a job when asked | write a stage file; cancel or select a job |

## 2 Sessions, jobs and turns

A **session** is the kept, numbered text of one model: the description you write, a paper you attach, the questions Matsya puts to you and your replies, and the answers of matsya-master that you accept. Its entries are numbered in the order they arrive, and the **version** of the text is the number of the last entry you wrote or accepted; an entry Matsya writes does not change the version. A session is neither a job nor a conversation: both sides use it. A session may hold nothing but questions and answers, or it may prepare and hold several jobs.

A **job** is one run of matsya-architect, from one version of the text. Within its session a job has a number, its rank among the session's jobs, and a **label** that names the model, the version of the text it read, its number and its state, for instance "Household with firms · version 2 · job 7 · running". A job that was still running when you changed the text is marked as built from an earlier version, and its results never stand as the session's latest preparation. Several jobs may belong to one session; each keeps its record, and submitting again never overwrites an earlier job.

A **turn** is one question answered by matsya-master in a session: the question, the passages read, the answer with its citations, and the record of what was read. A turn takes about a minute and costs a fraction of a job.

What a job returns is, by default, its final products and the material of a short report: the stage files of its last cycle, the model prose, the questions if it stopped for input, what the two judges found not to match, whether the round-trip files equal the written ones, and the language-model text charged. The intermediate iterates, every earlier cycle's files, prose and verdicts and every call, stay in the server's record and are returned only when asked for, which is the case of training.

## 3 How a piece of work moves between the parts

You write the model's description in a Markdown file and submit it. matsya-client creates a session named after the file, appends the text to it, and asks the server to start a job from that session. matsya-architect runs the job; matsya-client waits, printing each step and cycle, and at the end writes the stage files, the model prose and the report into a folder.

If the job ends with a question, the question is an entry of the session. You reply with a file, naming the question's entry; the reply starts the next job, which reads the text with your reply in it, and the two jobs stand linked in the session.

You ask about the result in the same session: what the declaration assumes, how a constraint is written, why a judge disagreed. matsya-master answers each question from the index, the session's text and the job's outputs, and names the job it read. If you say "submit this as a job", matsya-master starts one from the session's text as it then stands, your request included, and its answer gives the job's label; matsya-client can stay attached to that job until it ends and then write the folder.

Nothing passes between matsya-architect and matsya-master except through the session's written record and the jobs' stored results. Neither reads the other's working memory, and the client reads only what the server returns.
