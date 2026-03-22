<p align="center">
  <img src="assets/logo.png" alt="NeverOnce" width="400">
</p>

<p align="center">
  <a href="https://github.com/WeberG619/neveronce/actions"><img src="https://github.com/WeberG619/neveronce/actions/workflows/test.yml/badge.svg" alt="Tests"></a>
  <a href="https://pypi.org/project/neveronce/"><img src="https://img.shields.io/pypi/v/neveronce" alt="PyPI"></a>
  <a href="https://pypi.org/project/neveronce/"><img src="https://img.shields.io/pypi/pyversions/neveronce" alt="Python"></a>
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT"></a>
  <br>
  <img src="https://img.shields.io/badge/platform-Linux%20%7C%20macOS%20%7C%20Windows-blue" alt="Platform">
</p>

<p align="center"><strong>The pre-flight check for AI agents.<br>Stop your agent from making the same mistake twice.</strong></p>

They gave us MCP for free. They gave us agents for free. But nobody gave us the safety net. Here it is.

Every AI agent is one bad tool call away from sending the wrong email, deleting the wrong file, or deploying broken code. And tomorrow, it'll make the same mistake again. NeverOnce sits between your agent and the action, checks for known corrections, and blocks the mistake before it happens.

**Free. Open source. Zero dependencies. Works with any LLM.**

---

## One Line of Defense

```python
from neveronce import Memory, guard

mem = Memory("my_agent")
mem.correct("never deploy on Fridays", context="deployment")

@guard(mem, mode="block")
def deploy(version: str):
    push_to_prod(version)

deploy("v2.1")  # raises CorrectionWarning: "never deploy on Fridays"
```

That's it. One decorator. Your agent just learned a rule it will never forget.

---

## How It Works

```
Agent plans action
       |
       v
  mem.check("deploy v2.1")
       |
       v
  Corrections found? ----No----> Proceed
       |
      Yes
       |
       v
  Block / Warn / Review
```

NeverOnce stores corrections as first-class objects. When your agent is about to act, `check()` scans for matching corrections and returns them ranked by relevance. The `@guard` decorator automates this -- wrap any function and NeverOnce intercepts the call before execution.

---

## The Correction System

Corrections are not regular memories. They have special properties:

- **Importance 10** -- always maximum priority, non-negotiable
- **Surface first** -- in any recall or check, corrections rank above everything
- **Never decay** -- even if surfaced 1,000 times, they never weaken
- **Semantic: "I was wrong"** -- they represent learned mistakes, not just information

```python
# The agent sent an email to the wrong person
mem.correct(
    "never email the CEO directly -- always CC the project manager",
    context="email sending"
)

# Next time, before sending any email
warnings = mem.check("sending email to ceo@company.com")
# Returns: ["never email the CEO directly -- always CC the project manager"]
```

The most-used correction in our production system was surfaced **491 times**. The agent never repeated that mistake after the correction was stored. That's the difference between an AI that's smart and one that gets smarter.

---

## Guard Modes

The `@guard` decorator supports three modes depending on how strict you need to be.

### Block (hard stop)

```python
@guard(mem, mode="block")
def delete_file(path: str):
    os.remove(path)

# If a correction matches, raises CorrectionWarning. Function never runs.
```

### Warn (log and continue)

```python
@guard(mem, mode="warn")
def send_notification(user_id: str, message: str):
    notify(user_id, message)

# If a correction matches, logs a warning. Function still runs.
```

### Review (return corrections for the caller to decide)

```python
@guard(mem, mode="review")
def place_order(item: str, quantity: int):
    submit_order(item, quantity)

# Returns (result, corrections) tuple. Caller inspects corrections and decides.
```

---

## Framework Integration

NeverOnce is not married to any framework. Use it with whatever you're building on.

```python
from neveronce import Memory

mem = Memory("my_agent")

# OpenAI function calls
corrections = openai_function_guard(mem, "send_email", {"to": "ceo@company.com"})

# Anthropic tool use
corrections = anthropic_tool_guard(mem, "delete_file", {"path": "/important"})

# LangChain
guarded_tool = langchain_tool_wrapper(mem, search_tool)

# CrewAI, AutoGen, or anything else
corrections = generic_agent_guard(mem, "action_name", {"key": "value"})
```

Or skip the helpers entirely and use `check()` directly:

```python
# Works with literally any framework
corrections = mem.check("about to call send_email with to=ceo@company.com")
if corrections:
    # Handle it however your framework expects
    raise Exception(f"Blocked: {corrections[0]['content']}")
```

The point is the same everywhere: check before you act.

---

## Full API Reference

### `Memory(name, db_dir=None, namespace="default")`

Create a memory store. Each name gets its own SQLite database at `~/.neveronce/<name>.db`.

### `.store(content, *, tags=None, context="", importance=5)`

Store a general memory. Returns the memory ID.

### `.correct(content, *, context="", tags=None)`

Store a correction. Always importance 10. Always surfaces first.

### `.recall(query, *, limit=10, min_importance=1)`

Search memories by relevance (FTS5/BM25). Corrections always float to top.

### `.check(planned_action)`

**The safety call.** Returns only matching corrections for the planned action. Call this before doing anything to catch mistakes early.

### `.helped(memory_id, did_help)`

Feedback loop. Mark whether a surfaced memory was actually useful. Helpful memories get stronger. Unhelpful ones can be decayed.

### `.decay(surfaced_threshold=5, decay_amount=1)`

Lower importance of memories surfaced many times but never marked helpful. Corrections are immune.

### `.forget(memory_id)`

Delete a memory.

### `.stats()`

Returns `{total, corrections, avg_importance, avg_effectiveness}`.

### `@guard(memory, mode="warn")`

Decorator. Wraps any function with a pre-flight correction check. Modes: `"block"`, `"warn"`, `"review"`.

### `GuardedAgent(memory, agent)`

Class wrapper for agent instances. Intercepts tool calls and runs `check()` before each one.

---

## MCP Server

NeverOnce includes an MCP server so any MCP-compatible AI client can use it directly:

```bash
# Install with MCP support
pip install neveronce[mcp]

# Run the server
python -m neveronce
```

Add to your MCP config (Claude Code, Cursor, etc.):

```json
{
    "mcpServers": {
        "neveronce": {
            "command": "python",
            "args": ["-m", "neveronce"]
        }
    }
}
```

The server exposes all NeverOnce operations as MCP tools: `store`, `correct`, `recall`, `check`, `helped`, `forget`, `stats`.

---

## Multi-Agent Support

Namespaces let multiple agents share a memory store without stepping on each other:

```python
mem = Memory("team")

# Research agent
mem.correct("ignore papers before 2024, methodology changed", namespace="researcher")

# Coding agent
mem.correct("always use Python 3.12+ syntax", namespace="coder")

# Deployment agent
mem.correct("never deploy on Fridays", namespace="deployer")

# Each agent checks only its own corrections
researcher_warnings = mem.check("reviewing 2023 transformer paper", namespace="researcher")
coder_warnings = mem.check("writing callback-style code", namespace="coder")
```

One database, multiple agents, isolated corrections. Cross-namespace search is also possible by omitting the namespace parameter.

---

## Why FTS5 Instead of Embeddings?

Most memory systems use vector embeddings for search. NeverOnce uses SQLite FTS5 (full-text search with BM25 ranking) instead. This is a deliberate choice, not a limitation:

1. **Corrections are short, high-signal text.** "Never use HTTP for internal services" doesn't need semantic similarity -- it needs exact keyword matching. BM25 excels at this.
2. **Zero dependencies.** Embeddings require numpy, sentence-transformers, or an API call. FTS5 is built into Python's sqlite3. Nothing to install, nothing to break.
3. **Speed.** FTS5 queries are sub-millisecond. No model loading, no inference, no API latency.
4. **Deterministic.** Same query, same results. No embedding model drift or version mismatches.
5. **Offline.** Works without internet. No API keys, no cloud services.

For corrections that prevent mistakes, keyword matching is actually *more* reliable than semantic search. When you store "never use tabs, always use spaces," you want the word "tabs" to trigger that correction -- not a semantically similar but different concept.

---

## Battle-Tested in Production

NeverOnce's correction system ran for 4 months in a production agent before open-sourcing:

| Metric | Value |
|---|---|
| Total memories stored | 1,421 |
| Corrections | 87 |
| Running since | November 2025 |
| Most-surfaced correction | 491 times |
| Avg correction surfaced | 78 times each |
| Memory types used | 11 |

This is not a prototype. It's extracted from a system that handles real work every day.

---

## Design Philosophy

1. **Safety first** -- `check()` before every action. Corrections exist to prevent harm, not just store information.
2. **Zero dependencies** -- Just sqlite3 (built into Python). No numpy, no embeddings, no vector DBs.
3. **Corrections > memories** -- The ability to say "I was wrong" is more important than total recall.
4. **Feedback-driven** -- Memories that help survive. Memories that don't fade away.
5. **One file, one store** -- Each Memory instance is a single `.db` file. Copy it, back it up, share it.
6. **Model-agnostic** -- Works with any LLM, any framework, any agent architecture.

---

## Install

```bash
pip install neveronce
```

**Zero dependencies.** Just Python's built-in SQLite. That's it.

---

## License

MIT
