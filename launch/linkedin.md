# LinkedIn Post

---

Every AI has amnesia.

You spend 20 minutes correcting it. Next session — same mistakes. Gone. Like it never happened.

OpenAI, Anthropic, Google — they're all racing to make models smarter. Bigger context windows. Better reasoning. More parameters.

But none of them are solving the real problem: LLMs don't remember.

A 1M token context window isn't memory. It's short-term recall that dies when the session ends. That's like having a brilliant employee who gets amnesia every night.

I decided to fix it myself.

For the last 3 months, I've been running persistent memory on my AI workflows. Every correction I make gets stored permanently. Every time the AI surfaces a memory that helps, it gets stronger. Every memory that doesn't help fades away.

1,421 memories. 87 corrections. 4 months of daily use. My most-used correction has been surfaced 491 times — and the AI hasn't repeated that mistake once since the day I corrected it.

The result? I correct it once — it never makes that mistake again. Not in the next session. Not ever.

Today I'm open-sourcing this as Kova — a lightweight memory layer any developer can plug into any AI application.

The core idea is simple. Most memory systems do two things: store and recall. Kova does five:

Store → Recall → Correct → Feedback → Decay

That third step — Correct — is what nobody else does well. Corrections override normal memories. They always surface first. They never fade. One correction, permanent fix.

400 lines of Python. Zero dependencies. Works with any LLM.

Because the future of AI isn't just smarter models. It's models that learn from their mistakes.

Link in comments.

#AI #LLM #OpenSource #MachineLearning #AIMemory #DevTools

---

## First Comment (post immediately after)

GitHub: https://github.com/WeberG619/kova

Quick start:
```
pip install kova
```

```python
from kova import Memory
mem = Memory("my_app")
mem.correct("never do X, always do Y")
mem.recall("how should I do this?")  # correction surfaces first
```

Works as a standalone library or as an MCP server for Claude Code, Cursor, and any MCP-compatible AI client.
