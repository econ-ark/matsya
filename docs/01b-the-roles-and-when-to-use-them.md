---
title: The roles of Matsya and when to use them
audience: user
type: user-guide
topic: [matsya]
---

# The roles of Matsya and when to use them

> [!summary]
> Matsya's work is done by language-model **roles**, each with a fixed instruction text, a fixed input and a fixed output, called by the program in a fixed order; nothing else in Matsya decides anything about economics. This page names the roles, says what each receives and returns, and then says which command a user, or the assistant working for the user, runs for each kind of request: a question, a build, a reply to the architect's question, a reading of the result, a stop. The three parts of Matsya are defined in [Matsya in three parts](index.md); the commands in [Working with Matsya from the command line](01-working-from-the-command-line.md).

> [!info]- Relationship with other documents
> **Builds on** — [Matsya in three parts](index.md).
> **Explained for developers in** — the [Matsya developer guide](../dev-guide/index.md): [What Matsya reads](../dev-guide/02-what-matsya-reads.md) for what each role is given, and [Matsya handlers](../dev-guide/03-matsya-handlers.md) for the program that calls the roles.

## 1 The roles of a job

A job of matsya-architect runs its roles in cycles. Each role is a language model with one instruction text; what it may read is fixed by the program, and what it returns is checked by the program before anything else happens.

| Role | Receives | Returns | What it is for |
|---|---|---|---|
| **Model-prose-writer** | the source material: the session's text or the submitted file, with the passages of the index that match it and the pages of the reference guides | the **model prose**: the model restated as a paper's model section under fixed headings (states, controls, shocks and their timing, laws of motion, the recursion, the condition that determines the policy, the parameters), or questions when the source leaves a necessary thing unsaid | to fix what model is meant before anything is written in the language |
| **prose-source-judge** | the model prose and the source material | for each heading, whether the prose omits, adds or contradicts something the source says, with the sentences quoted | to stop a restatement that departs from what the author wrote |
| **Prose-to-Bellman-Sym** | the model prose, the reference guides of the language, the passages it requests, and, in a later cycle, the disagreements of the judges | the **stage files** of the declaration, in Bellman-SYM, with a note on every assumption it had to supply; a period file and a trellis file when the model has several stages | to write the declaration; it builds it from the prose and copies no example |
| the **elaborator** (a program, not a role) | the stage files | acceptance, or a refusal naming the rule, the line and what to write instead, which goes back to Prose-to-Bellman-Sym for repair | to check that the files parse and mean what they say |
| **Semantics-to-Prose** | the elaborated declaration, as the program prints it, and nothing of the source | the **round-trip prose**: the model as the declaration states it, under the same headings | to read back what was written, without seeing what was meant |
| **prose-roundtrip-judge** | the model prose and the round-trip prose | for each heading, whether the two agree, with the sentences quoted | to decide whether the declaration says what the prose meant |

A cycle ends when the judges agree on every heading, and the job ends `converged`; otherwise the disagreements go to Prose-to-Bellman-Sym and the next cycle begins, up to the number of cycles allowed; a job that reaches that number ends `not_converged`, and its report says which headings still disagree. A job that stopped at the Model-prose-writer's questions ends `needs_input`, and the questions stand in the session for the user to answer.

## 2 The role of a turn

matsya-master has one role, the **conversation role**. It receives the question, the passages of the index that match it, the session's text and the outputs of the session's jobs, and it may ask the program for more pages or passages a bounded number of times. It returns an answer with citations, each a quoted sentence of what it read, and the program accepts no citation it cannot find in that material. It writes no stage file. When the user asks it to build or to submit, it sets one field of its reply and the program starts a job from the session; it starts no job otherwise.

## 3 Which command for which request

| The request | What runs | The command |
|---|---|---|
| a question about a model, about the language, about why a judge disagreed, about what a job produced | one turn of the conversation role, about a minute, a fraction of a job's cost | `matsya ask <session> "…"` |
| build a declaration from a description, or rebuild it after an edit of the description | one job of all the roles of §1, several minutes, charged by the language-model text of every call | `matsya job submit model.md` (a session is created for the file) |
| build from the discussion so far | the same job, started by the conversation role from the session's text | `matsya ask <session> "Submit this as a job."` |
| answer a question the architect asked | the reply appended to the session, which starts the next job with the reply in its text | `matsya session add <session> reply.md --replies-to <entry>` |
| read what a job produced, or its report of what did not match | nothing on the server; the client writes the folder and the report | `matsya job files <job> <folder>` |
| see the jobs of a model, their labels and which one the conversation discusses | nothing on the server; a listing | `matsya session show <session>` |
| make the conversation discuss an earlier job | a mark on the session | `matsya session select <session> <job>` |
| stop a job that is queued or running | the job ends before its next call; a call already sent is charged | `matsya job cancel <job>` |
| search the documentation and the literature without a question | the index alone, no role | `matsya search "…"` |

Two rules follow for an assistant acting for a user. A job costs money and minutes and is started only when the user asks to build; a question costs little and is the way to understand a result before building again. And a job's questions are answered in the session, not by editing the files, because the next job reads the session's text.
