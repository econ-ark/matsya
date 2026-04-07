# Matsya

> **This is a research development version.** Interfaces, features, and
> the knowledge base may change without notice.

Research copilot for modular dynamic programming. Helps formulate
modular DP problems from papers and notes, grounded in the Bellman-DDSL
knowledge base.

Matsya's knowledge base covers the DDSL specification and dolo-plus
syntax, dynamic programming theory and textbooks, category-theoretic
foundations, canonical stage examples and formal MDPs, research papers
on precautionary saving and buffer stock theory, and pedagogical
lecture notes on solving dynamic optimization problems.

The main workflow is: paste an excerpt from a paper, then iterate with Matsya
to identify states/controls/shocks/timing and write down a clean modular DP /
Bellman equation representation.

> **Matsya as a specialist oracle, not the main agent.** The typical
> use case is not "talk to Matsya all day." It's: you're working in a
> repo with a local coding agent (Claude Code, Cursor, etc.) that
> handles implementation. When the agent — or you — hits a question
> about modular dynamic programming theory, dolo-plus syntax, stage decomposition, or
> convergence conditions, you call matsya for a grounded answer and
> bring that back into the local session. Matsya provides the DP
> domain knowledge; your local agent does the coding. Think of it as
> a specialist you consult, not a general-purpose assistant.

## Install

```bash
pip install git+https://github.com/econ-ark/matsya.git
```

Requires Python >= 3.11. Zero external dependencies.

## Quick start

1) Configure your Matsya access token:

```bash
matsya configure
```

2) Ask a first question:

```bash
matsya "What is a stage in Bellman-DDSL?" 
```

If you see an answer, you're set.

## The main workflow: paste paper excerpts (sessions)

When you’re iteratively formalizing a model from a paper, use a session so
Matsya can remember context across turns.

### CLI example (multi-turn, multi-paragraph input)

```bash
matsya "$(cat <<'EOF'
I'm reading a paper and want to formalize the model as a modular dynamic
program.

Here is an excerpt:
<paste the relevant paragraph(s) here>

Please:
1) list the state variables, controls, shocks, and parameters
2) spell out the timing / information structure
3) write the Bellman equation (or modular decomposition) consistent with this
4) describe the transition and any constraints
EOF
)" --session paper-notes

# Follow-up turns
matsya "Now clarify what is observed when (information sets) and restate the state transition." --session paper-notes
```

Tip: for very long excerpts, it’s often easiest to do this in a notebook using
the Python API below.

## Configure (details)

You need a personal access token to use Matsya. Tokens look like
`msy_a7f3b2e1c9d4e5f6a1b2c3d4e5f6a7b8` and are issued by the Matsya admin. If
you don't have one, ask the project lead or your team contact.

### Option A: interactive setup (recommended)

```bash
matsya configure
```

This will prompt you to paste your token, validate it, and save it to
`~/.config/matsya/config.toml`.

### Option B: environment variable

Set `MATSYA_TOKEN` in your shell. This overrides any saved config:

```bash
export MATSYA_TOKEN="msy_a7f3b2e1c9d4e5f6a1b2c3d4e5f6a7b8"
matsya "What is a stage in Bellman-DDSL?"
```

To make it permanent, add the `export` line to your `~/.zshrc` or
`~/.bashrc`.

### Option C: config file directly

Create `~/.config/matsya/config.toml` manually:

```toml
token = "msy_a7f3b2e1c9d4e5f6a1b2c3d4e5f6a7b8"
```

## CLI usage

```bash
# Theory questions
matsya "What is a stage in DDSL?"
matsya "How do periods compose stages?"
matsya "Explain information sets at each perch"

# BufferStockTheory (Carroll) — boost BST content + extended thinking
matsya "Explain growth impatience and its relation to DDSL" --BST
matsya "What are the GIC and RIC convergence conditions?" --BST

# Stateful session (multi-turn model development)
matsya "Write cons_stage YAML" --session my-model
matsya "Now add portfolio choice" --session my-model

# Session management
matsya sessions                           # list sessions
matsya sessions --show my-model           # view session history

# Raw vector search only (no LLM call)
matsya "What is a stage?" --no-llm

# Optional (advanced): YAML↔MDP round-trip refinement loop
matsya "Write cons_stage YAML" --refine
```

## Python API

```python
from matsya import ask, search, sessions, session_history

# One-off question
answer = ask("What is a stage in DDSL?")

# BufferStockTheory shortcut (boost + extended thinking)
answer = ask("explain growth impatience", bst=True)

# Session (multi-turn)
answer = ask("Write cons_stage YAML", session="my-model")
answer = ask("Now add portfolio choice", session="my-model")

# Search only (no answer generation)
chunks = search("buffer stock saving", k=20, boost={"BufferStockTheory": 100})

# Sessions
for s in sessions():
    print(s["name"], s["turn_count"], s["last_active"])

for turn in session_history("my-model"):
    print(f"Q: {turn['query']}")
    print(f"A: {turn['answer'][:200]}...")
```

The Python API generates answers by default. The CLI also defaults to LLM —
use `--no-llm` for raw search results only.

## Using your own Anthropic API key (optional)

By default, Matsya uses the project's shared Anthropic key on the server.
If you want to use your own Anthropic key instead (e.g. to control your
own billing), set `MATSYA_ANTHROPIC_KEY` in your environment:

```bash
export MATSYA_ANTHROPIC_KEY="sk-ant-api03-..."
```

To make it permanent, add that line to your `~/.zshrc` or `~/.bashrc`.

This is a Matsya-specific variable — it will **not** pick up a generic
`ANTHROPIC_API_KEY` you may have set for other tools. You must
explicitly opt in by setting `MATSYA_ANTHROPIC_KEY`.

When set, the client sends your key to the server on each request. The
server uses it for the LLM call instead of the shared key. Your key is
**never** logged, stored, or echoed by the server — it is used only for
the duration of the LLM call and then discarded.

You still need a Matsya access token (`msy_...`) even when using your
own Anthropic key — the Matsya token controls access to the service,
the Anthropic key controls which billing account the LLM call charges.

## Data logging and consent

If you use sessions (`--session` / `session="..."`), your questions and answers
are stored on the server so the conversation can continue across turns. This
data is also used for research and product improvement.

If you do **not** use sessions, the server retains only minimal operational
metadata (your identity token, endpoint, timestamp, model/boost settings). Full
messages, answers, and sources are not persisted for non-session requests.

Your Anthropic key (if you provide one) is never logged, stored, or echoed by
the server.
