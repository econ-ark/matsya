# econ-ark-matsya

CLI and Python API for querying the Matsya research RAG — a retrieval-augmented
generation system over the Bellman-DDSL knowledge base (dynamic programming
theory, dolo-plus YAML syntax, economic models).

## Install

```bash
pip install econ-ark-matsya
```

Requires Python >= 3.11. Zero external dependencies.

## Configure

You need a personal access token to use Matsya. Tokens look like
`msy_a7f3b2e1c9d4e5f6a1b2c3d4e5f6a7b8` and are issued by the Matsya
admin. If you don't have one, ask the project lead or your team contact.

### Option A: interactive setup (recommended)

```bash
matsya configure
```

This will prompt you to paste your token, validate it, and save it to
`~/.config/matsya/config.toml`. You only need to do this once.

### Option B: environment variable

Set `MATSYA_TOKEN` in your shell. This overrides any saved config and
is useful for CI, containers, or temporary use:

```bash
export MATSYA_TOKEN="msy_a7f3b2e1c9d4e5f6a1b2c3d4e5f6a7b8"
matsya "What is a stage?"
```

To make it permanent, add the `export` line to your `~/.zshrc` or
`~/.bashrc`.

### Option C: config file directly

Create `~/.config/matsya/config.toml` manually:

```toml
token = "msy_a7f3b2e1c9d4e5f6a1b2c3d4e5f6a7b8"
```

### Verify

```bash
matsya "What is a stage?"
```

If you see an answer, you're set. If you get an authentication error,
double-check your token or ask the admin to confirm it hasn't been
revoked.

## CLI usage

Matsya has two primary modes:

### Mode 1: Translate (YAML ↔ formal MDP)

Convert between dolo-plus stage YAML and formal mathematical MDP
writeups. Use this when formalizing a model or checking that your
YAML expresses the Bellman problem you intend.

```bash
# Model description → dolo-plus YAML
matsya "Write the dolo-plus YAML for a consumption-savings stage with IID shocks"

# YAML → formal MDP (paste your YAML in the query)
matsya "Translate this stage to a formal MDP:
name: cons_stage
symbols:
  states:
    m: '@in R++'
  controls:
    c: '@in R++'
..."

# Round-trip refinement: YAML → MDP → YAML until convergence
matsya "Write cons_stage YAML" --refine
```

### Mode 2: Dynamic programming theory and DDSL syntax

Ask questions about Bellman calculus, DDSL concepts, dolo-plus syntax,
perch/stage/period structure, or the research literature indexed in
the RAG.

```bash
# Theory questions
matsya "What is a stage in DDSL?"
matsya "How do periods compose stages?"
matsya "Explain information sets at each perch"

# BufferStockTheory (Carroll) — boost BST content + extended thinking
matsya "Explain growth impatience and its relation to DDSL" --BST
matsya "What are the GIC and RIC convergence conditions?" --BST
```

### Sessions and other options

```bash
# Stateful session (multi-turn model development)
matsya "Write cons_stage YAML" --session my-model
matsya "Now add portfolio choice" --session my-model

# Session management
matsya sessions                           # list sessions
matsya sessions --show my-model           # view session history

# Raw vector search only (no LLM call)
matsya "What is a stage?" --no-llm
```

## Python API

```python
from matsya import ask, search, sessions, session_history

# Stateless query
answer = ask("What is a stage in DDSL?")

# BST boost
answer = ask("explain growth impatience", bst=True)

# Stateful session
answer = ask("Write cons_stage YAML", session="my-model")
answer = ask("Now add portfolio choice", session="my-model")

# Raw search (no LLM)
chunks = search("buffer stock saving", k=20, boost={"BufferStockTheory": 100})

# Sessions
for s in sessions():
    print(s["name"], s["turn_count"], s["last_active"])

for turn in session_history("my-model"):
    print(f"Q: {turn['query']}")
    print(f"A: {turn['answer'][:200]}...")
```

The Python API defaults to `llm=True`. The CLI also defaults to LLM —
use `--no-llm` for raw vector search results.

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

Session-backed queries and answers are logged on the server for research and
product improvement. This includes: queries, answers, retrieved source paths
and scores, timestamps, session metadata, model and boost parameters, and
full refine iteration paths.

Stateless `/chat` requests and non-session `/refine` requests retain only
minimal operational metadata (principal/token identity, endpoint, model,
timestamp). Full messages, answers, and sources are not persisted for
stateless requests.

Anthropic BYOK keys are never logged, persisted, or echoed by the server.
