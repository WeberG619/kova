"""Tests for Recal."""

import tempfile
import os
from pathlib import Path

from recal import Memory


def _tmp_mem(name="test"):
    """Create a Memory in a temp directory."""
    tmp = tempfile.mkdtemp()
    return Memory(name=name, db_dir=tmp)


def test_store_and_recall():
    mem = _tmp_mem()
    mid = mem.store("python uses snake_case", tags=["coding", "python"])
    assert mid > 0

    results = mem.recall("python naming convention")
    assert len(results) > 0
    assert any("snake_case" in r["content"] for r in results)
    mem.close()


def test_corrections_surface_first():
    mem = _tmp_mem()
    mem.store("use camelCase for variables", importance=8)
    mem.correct("use snake_case, not camelCase", context="python coding style")

    results = mem.recall("camelCase variables")
    assert len(results) >= 2
    # Correction should be first
    assert results[0]["memory_type"] == "correction"
    assert results[0]["importance"] == 10
    mem.close()


def test_correction_always_importance_10():
    mem = _tmp_mem()
    mid = mem.correct("never do this thing")
    result = mem.db.get(mid)
    assert result["importance"] == 10
    assert result["memory_type"] == "correction"
    mem.close()


def test_check_finds_relevant_corrections():
    mem = _tmp_mem()
    mem.correct(
        "never use HTTP for Revit connection, use named pipes",
        context="Revit MCP bridge communication protocol"
    )

    # Should match — shares significant words
    matches = mem.check("setting up HTTP connection for Revit bridge")
    assert len(matches) > 0

    # Should not match — no significant overlap
    no_matches = mem.check("making breakfast tomorrow morning")
    assert len(no_matches) == 0
    mem.close()


def test_helped_updates_effectiveness():
    mem = _tmp_mem()
    mid = mem.store("helpful memory")

    # Simulate surfacing
    mem.recall("helpful")

    # Mark as helped
    mem.helped(mid, True)
    result = mem.db.get(mid)
    assert result["times_helped"] == 1
    assert result["effectiveness"] > 0
    mem.close()


def test_decay_spares_corrections():
    mem = _tmp_mem()
    # Store a regular memory and surface it many times
    mid = mem.store("unhelpful thing", importance=5)
    for _ in range(6):
        mem.db.conn.execute(
            "UPDATE memories SET times_surfaced = times_surfaced + 1 WHERE id = ?",
            (mid,)
        )
    mem.db.conn.commit()

    # Store a correction and surface it too
    cid = mem.correct("important correction")
    for _ in range(6):
        mem.db.conn.execute(
            "UPDATE memories SET times_surfaced = times_surfaced + 1 WHERE id = ?",
            (cid,)
        )
    mem.db.conn.commit()

    # Decay should affect the regular memory but not the correction
    count = mem.decay(surfaced_threshold=5)
    assert count >= 1

    regular = mem.db.get(mid)
    correction = mem.db.get(cid)
    assert regular["importance"] < 5  # decayed
    assert correction["importance"] == 10  # untouched
    mem.close()


def test_forget():
    mem = _tmp_mem()
    mid = mem.store("temporary memory")
    assert mem.forget(mid) is True
    assert mem.db.get(mid) is None
    assert mem.forget(mid) is False  # already gone
    mem.close()


def test_stats():
    mem = _tmp_mem()
    mem.store("memory one")
    mem.store("memory two")
    mem.correct("correction one")

    s = mem.stats()
    assert s["total"] == 3
    assert s["corrections"] == 1
    mem.close()


def test_namespace_isolation():
    mem = _tmp_mem()
    mem.store("global memory", namespace="project_a")
    mem.store("another memory", namespace="project_b")

    results_a = mem.recall("memory", namespace="project_a")
    results_b = mem.recall("memory", namespace="project_b")

    # Each namespace should find its own memory
    contents_a = [r["content"] for r in results_a]
    contents_b = [r["content"] for r in results_b]
    assert "global memory" in contents_a
    assert "another memory" in contents_b
    mem.close()


def test_context_manager():
    tmp = tempfile.mkdtemp()
    with Memory("ctx_test", db_dir=tmp) as mem:
        mem.store("test memory")
        assert mem.stats()["total"] == 1
    # Should not raise after close


def test_tags_preserved():
    mem = _tmp_mem()
    mid = mem.store("tagged memory", tags=["important", "coding", "python"])
    result = mem.db.get(mid)
    import json
    tags = json.loads(result["tags"])
    assert "important" in tags
    assert "python" in tags
    mem.close()


if __name__ == "__main__":
    tests = [
        test_store_and_recall,
        test_corrections_surface_first,
        test_correction_always_importance_10,
        test_check_finds_relevant_corrections,
        test_helped_updates_effectiveness,
        test_decay_spares_corrections,
        test_forget,
        test_stats,
        test_namespace_isolation,
        test_context_manager,
        test_tags_preserved,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            print(f"  PASS  {test.__name__}")
            passed += 1
        except Exception as e:
            print(f"  FAIL  {test.__name__}: {e}")
            failed += 1

    print(f"\n{passed} passed, {failed} failed")
