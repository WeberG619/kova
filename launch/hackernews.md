# Hacker News — Show HN Post

## Title
Show HN: Kova – I gave AI persistent memory that learns from corrections (400 lines, zero deps)

## Body

Every AI agent has amnesia. You correct it on Monday, it makes the same mistake on Tuesday. The 1M context window isn't memory — it's short-term recall that vanishes when the session ends.

I've been running persistent memory on my AI workflows for 4 months. 1,421 memories, 87 corrections, daily use across 11 memory types. My most-used correction has been surfaced 491 times — and the AI hasn't repeated that mistake since the day I stored it.

Today I'm open-sourcing the core as Kova — a 400-line Python library with zero dependencies (just SQLite).

**What makes it different from Mem0, Engram, etc.:**

Most memory systems do Store → Recall. That's it. Kova does five things:

1. **Store** — Save what matters (SQLite + FTS5)
2. **Recall** — Find what's relevant (BM25 ranking)
3. **Correct** — Override what was wrong (always surfaces first, never decays)
4. **Feedback** — Strengthen what helped, weaken what didn't
5. **Decay** — Unhelpful memories lose importance over time

Step 3 is the one nobody else does well. Corrections are stored at max importance, always surface before regular memories, and are immune to decay. You correct the AI once — it's fixed permanently.

```python
from kova import Memory

mem = Memory("my_app")
mem.store("user prefers dark mode")
mem.correct("never use HTTP for this API — use websockets")
mem.recall("API connection method")  # correction surfaces first

# Pre-flight check before taking action
mem.check("setting up HTTP connection")  # warns you
```

It also ships as an MCP server, so Claude Code, Cursor, or any MCP client gets persistent memory instantly.

- GitHub: https://github.com/WeberG619/kova
- Zero dependencies (just Python's built-in sqlite3)
- ~400 lines of actual code
- 11 tests passing
- MIT licensed
