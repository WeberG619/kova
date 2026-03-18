"""Recal Demo — Run this to see persistent, correctable AI memory in action.

Usage:
    pip install recal
    python demo.py
"""

from recal import Memory

print("=" * 60)
print("  RECAL — Persistent, Correctable Memory for AI")
print("  The memory layer that learns from mistakes.")
print("=" * 60)

# Create a memory store (stored at ~/.recal/demo.db)
mem = Memory("demo")

# --- STEP 1: Store memories ---
print("\n[1] Storing memories...")
mem.store("Python uses snake_case for variable names", tags=["python", "style"])
mem.store("API rate limit is 100 requests per minute", tags=["api", "limits"])
mem.store("User prefers dark mode in all applications", tags=["preference", "ui"])
print("    Stored 3 memories.")

# --- STEP 2: Store a correction ---
print("\n[2] Storing a CORRECTION (the killer feature)...")
mem.correct(
    "Never use HTTP for internal services — always use gRPC. "
    "HTTP caused 3x latency in production.",
    context="service-to-service communication protocol",
    tags=["architecture", "performance"]
)
print("    Correction stored at importance 10 (maximum).")
print("    This will ALWAYS surface before regular memories.")

# --- STEP 3: Recall — corrections surface first ---
print("\n[3] Recalling 'service communication protocol'...")
results = mem.recall("service communication protocol")
for r in results:
    marker = " ** CORRECTION **" if r["memory_type"] == "correction" else ""
    print(f"    #{r['id']} [importance: {r['importance']}]{marker}")
    print(f"    {r['content'][:80]}")
    print()

# --- STEP 4: Pre-flight check ---
print("[4] Pre-flight check: 'setting up HTTP for internal service communication'")
warnings = mem.check("setting up HTTP for internal service communication")
if warnings:
    print("    !! WARNINGS FOUND:")
    for w in warnings:
        print(f"    #{w['id']}: {w['content'][:80]}")
else:
    print("    No warnings. Clear to proceed.")

# --- STEP 5: Feedback loop ---
print("\n[5] Marking the correction as helpful (feedback loop)...")
if results:
    mem.helped(results[0]["id"], True)
    print("    Memory strengthened. It will rank even higher next time.")

# --- STEP 6: Stats ---
print("\n[6] Memory store stats:")
s = mem.stats()
print(f"    Total memories:    {s['total']}")
print(f"    Corrections:       {s['corrections']}")
print(f"    Avg importance:    {s['avg_importance']:.1f}")
print(f"    Avg effectiveness: {(s['avg_effectiveness'] or 0):.2f}")

# --- STEP 7: Persistence ---
print("\n[7] Persistence test...")
mem.close()
mem2 = Memory("demo")
results2 = mem2.recall("service communication")
print(f"    Reopened database. Found {len(results2)} memories.")
print(f"    Correction still there: {'YES' if any(r['memory_type'] == 'correction' for r in results2) else 'NO'}")
mem2.close()

print("\n" + "=" * 60)
print("  Your memories are saved at ~/.recal/demo.db")
print("  They persist across sessions. Corrections never decay.")
print("  That's Recal. Memory that learns from mistakes.")
print("=" * 60)
print("\n  GitHub: https://github.com/WeberG619/recal")
print("  PyPI:   pip install recal")
print()
