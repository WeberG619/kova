"""Tests for neveronce.guard module."""

import logging
import tempfile
from pathlib import Path

import pytest

from neveronce import Memory
from neveronce.guard import (
    ActionLog,
    CorrectionWarning,
    GuardedAgent,
    guard,
    guard_tool_call,
    _action_logs,
)


@pytest.fixture
def mem(tmp_path):
    """Fresh Memory instance with a temp database."""
    m = Memory("test", db_dir=str(tmp_path))
    yield m
    m.close()


@pytest.fixture(autouse=True)
def clear_action_logs():
    """Clear global action logs between tests."""
    _action_logs.clear()
    yield
    _action_logs.clear()


def _seed_corrections(mem: Memory):
    """Insert corrections that will match specific actions."""
    mem.correct(
        "Never send email to banned@example.com — compliance violation",
        context="send email banned recipient",
        tags=["email", "compliance"],
    )
    mem.correct(
        "Never delete production database without backup",
        context="delete database production backup",
        tags=["database", "safety"],
    )
    mem.correct(
        "Always deploy with rollback plan in place",
        context="deploy production rollback version",
        tags=["deploy", "safety"],
    )


# -------------------------------------------------------------------------
# CorrectionWarning exception
# -------------------------------------------------------------------------

class TestCorrectionWarning:
    def test_has_corrections_attribute(self):
        corrections = [{"content": "don't do that", "id": 1}]
        exc = CorrectionWarning("some action", corrections)
        assert exc.corrections == corrections
        assert exc.action == "some action"

    def test_message_includes_content(self):
        corrections = [{"content": "never do X"}]
        exc = CorrectionWarning("do X", corrections)
        assert "never do X" in str(exc)
        assert "1 correction(s)" in str(exc)

    def test_is_exception(self):
        exc = CorrectionWarning("act", [])
        assert isinstance(exc, Exception)


# -------------------------------------------------------------------------
# @guard decorator — warn mode
# -------------------------------------------------------------------------

class TestGuardWarnMode:
    def test_proceeds_when_no_corrections(self, mem):
        @guard(mem, mode="warn")
        def greet(name: str) -> str:
            """Say hello."""
            return f"hello {name}"

        result = greet("Weber")
        assert result == "hello Weber"

    def test_warns_and_proceeds_when_corrections_match(self, mem, caplog):
        _seed_corrections(mem)

        @guard(mem, mode="warn")
        def send_email(to: str, subject: str) -> str:
            """Send an email to the specified recipient."""
            return f"sent to {to}"

        with caplog.at_level(logging.WARNING, logger="neveronce.guard"):
            result = send_email("banned@example.com", "hello")

        assert result == "sent to banned@example.com"
        assert any("NeverOnce correction" in r.message for r in caplog.records)

    def test_preserves_function_metadata(self, mem):
        @guard(mem, mode="warn")
        def my_func():
            """My docstring."""
            pass

        assert my_func.__name__ == "my_func"
        assert my_func.__doc__ == "My docstring."
        assert my_func._neveronce_guarded is True


# -------------------------------------------------------------------------
# @guard decorator — block mode
# -------------------------------------------------------------------------

class TestGuardBlockMode:
    def test_raises_when_corrections_match(self, mem):
        _seed_corrections(mem)

        @guard(mem, mode="block")
        def delete_database(db_name: str):
            """Delete the specified database."""
            return "deleted"

        with pytest.raises(CorrectionWarning) as exc_info:
            delete_database("production")

        assert len(exc_info.value.corrections) > 0
        assert "production" in exc_info.value.action or "database" in exc_info.value.action

    def test_proceeds_when_no_corrections(self, mem):
        @guard(mem, mode="block")
        def safe_action():
            """Do something safe."""
            return "ok"

        assert safe_action() == "ok"


# -------------------------------------------------------------------------
# @guard decorator — review mode
# -------------------------------------------------------------------------

class TestGuardReviewMode:
    def test_proceeds_when_reviewer_approves(self, mem):
        _seed_corrections(mem)
        decisions = []

        def approve(action, corrections):
            decisions.append(("approve", action, corrections))
            return True

        @guard(mem, mode="review", reviewer=approve)
        def deploy_to_prod(version: str):
            """Deploy version to production."""
            return f"deployed {version}"

        result = deploy_to_prod("v2.0")
        assert result == "deployed v2.0"
        assert len(decisions) == 1

    def test_blocks_when_reviewer_rejects(self, mem):
        _seed_corrections(mem)

        def reject(action, corrections):
            return False

        @guard(mem, mode="review", reviewer=reject)
        def deploy_to_prod(version: str):
            """Deploy version to production."""
            return f"deployed {version}"

        with pytest.raises(CorrectionWarning):
            deploy_to_prod("v2.0")

    def test_reviewer_not_called_when_no_corrections(self, mem):
        called = []

        def spy(action, corrections):
            called.append(True)
            return True

        @guard(mem, mode="review", reviewer=spy)
        def safe_action():
            """Nothing risky."""
            return "ok"

        assert safe_action() == "ok"
        assert len(called) == 0

    def test_review_mode_requires_reviewer(self, mem):
        with pytest.raises(ValueError, match="reviewer"):
            @guard(mem, mode="review")
            def bad():
                pass

    def test_invalid_mode_raises(self, mem):
        with pytest.raises(ValueError, match="mode"):
            @guard(mem, mode="explode")
            def bad():
                pass


# -------------------------------------------------------------------------
# ActionLog
# -------------------------------------------------------------------------

class TestActionLog:
    def test_records_guarded_calls(self, mem):
        _seed_corrections(mem)

        @guard(mem, mode="warn")
        def send_email(to: str):
            """Send an email to the specified recipient."""
            return "sent"

        send_email("banned@example.com")
        send_email("ok@example.com")

        log = ActionLog(mem)
        entries = log.recent(limit=10)
        assert len(entries) == 2
        assert entries[0]["action"] == "send_email"

    def test_recent_returns_newest_first(self, mem):
        @guard(mem, mode="warn")
        def action_a():
            """Action A."""
            pass

        @guard(mem, mode="warn")
        def action_b():
            """Action B."""
            pass

        action_a()
        action_b()

        log = ActionLog(mem)
        entries = log.recent()
        assert entries[0]["action"] == "action_b"
        assert entries[1]["action"] == "action_a"

    def test_records_outcome(self, mem):
        _seed_corrections(mem)

        @guard(mem, mode="block")
        def delete_database(db_name: str):
            """Delete the specified database."""
            return "deleted"

        with pytest.raises(CorrectionWarning):
            delete_database("production")

        log = ActionLog(mem)
        entries = log.recent()
        assert entries[0]["outcome"] == "blocked"

    def test_records_no_match_outcome(self, mem):
        @guard(mem, mode="warn")
        def safe():
            """Safe operation."""
            pass

        safe()
        log = ActionLog(mem)
        entries = log.recent()
        assert entries[0]["outcome"] == "no_match"
        assert entries[0]["corrections_matched"] == []

    def test_clear(self, mem):
        @guard(mem, mode="warn")
        def action():
            """Do something."""
            pass

        action()
        log = ActionLog(mem)
        assert len(log) == 1
        log.clear()
        assert len(log) == 0

    def test_all(self, mem):
        @guard(mem, mode="warn")
        def a():
            """A."""
            pass

        @guard(mem, mode="warn")
        def b():
            """B."""
            pass

        a()
        b()
        log = ActionLog(mem)
        entries = log.all()
        assert entries[0]["action"] == "a"
        assert entries[1]["action"] == "b"

    def test_has_timestamp(self, mem):
        @guard(mem, mode="warn")
        def action():
            """Do."""
            pass

        action()
        log = ActionLog(mem)
        entry = log.recent()[0]
        assert "timestamp" in entry
        assert "T" in entry["timestamp"]  # ISO format


# -------------------------------------------------------------------------
# GuardedAgent
# -------------------------------------------------------------------------

class TestGuardedAgent:
    def test_register_and_run(self, mem):
        agent = GuardedAgent(memory=mem, mode="warn")

        @agent.tool
        def search_web(query: str) -> str:
            """Search the web."""
            return f"results for {query}"

        result = agent.run("search_web", query="python")
        assert result == "results for python"

    def test_unknown_tool_raises(self, mem):
        agent = GuardedAgent(memory=mem, mode="warn")

        with pytest.raises(KeyError, match="Unknown tool"):
            agent.run("nonexistent", x=1)

    def test_list_tools(self, mem):
        agent = GuardedAgent(memory=mem, mode="warn")

        @agent.tool
        def tool_b():
            """B."""
            pass

        @agent.tool
        def tool_a():
            """A."""
            pass

        assert agent.list_tools() == ["tool_a", "tool_b"]

    def test_blocks_in_block_mode(self, mem):
        _seed_corrections(mem)
        agent = GuardedAgent(memory=mem, mode="block")

        @agent.tool
        def delete_database(db_name: str):
            """Delete the specified database."""
            return "deleted"

        with pytest.raises(CorrectionWarning):
            agent.run("delete_database", db_name="production")

    def test_review_mode(self, mem):
        _seed_corrections(mem)

        def always_approve(action, corrections):
            return True

        agent = GuardedAgent(memory=mem, mode="review", reviewer=always_approve)

        @agent.tool
        def deploy_to_prod(version: str):
            """Deploy version to production."""
            return f"deployed {version}"

        result = agent.run("deploy_to_prod", version="v3.0")
        assert result == "deployed v3.0"

    def test_invalid_mode_raises(self, mem):
        with pytest.raises(ValueError):
            GuardedAgent(memory=mem, mode="bad")

    def test_review_requires_reviewer(self, mem):
        with pytest.raises(ValueError, match="reviewer"):
            GuardedAgent(memory=mem, mode="review")

    def test_logs_recorded_for_agent_tools(self, mem):
        agent = GuardedAgent(memory=mem, mode="warn")

        @agent.tool
        def ping() -> str:
            """Ping."""
            return "pong"

        agent.run("ping")
        log = ActionLog(mem)
        assert len(log) == 1


# -------------------------------------------------------------------------
# guard_tool_call helper
# -------------------------------------------------------------------------

class TestGuardToolCall:
    def test_returns_none_when_no_corrections(self, mem):
        result = guard_tool_call(mem, "search_web", {"query": "hello"})
        assert result is None

    def test_returns_corrections_in_warn_mode(self, mem, caplog):
        _seed_corrections(mem)
        with caplog.at_level(logging.WARNING, logger="neveronce.guard"):
            result = guard_tool_call(
                mem, "send_email", {"to": "banned@example.com", "subject": "hello"}
            )
        assert result is not None
        assert len(result) > 0

    def test_raises_in_block_mode(self, mem):
        _seed_corrections(mem)
        with pytest.raises(CorrectionWarning):
            guard_tool_call(
                mem, "delete_database", {"db_name": "production"}, mode="block"
            )

    def test_review_mode_proceed(self, mem):
        _seed_corrections(mem)
        result = guard_tool_call(
            mem,
            "deploy_to_prod",
            {"version": "v1"},
            mode="review",
            reviewer=lambda a, c: True,
        )
        assert result is not None

    def test_review_mode_block(self, mem):
        _seed_corrections(mem)
        result = guard_tool_call(
            mem,
            "deploy_to_prod",
            {"version": "v1"},
            mode="review",
            reviewer=lambda a, c: False,
        )
        assert result is None

    def test_invalid_mode(self, mem):
        with pytest.raises(ValueError):
            guard_tool_call(mem, "x", {}, mode="nope")

    def test_review_without_reviewer(self, mem):
        with pytest.raises(ValueError, match="reviewer"):
            guard_tool_call(mem, "x", {}, mode="review")

    def test_empty_args(self, mem):
        result = guard_tool_call(mem, "noop", {})
        assert result is None

    def test_none_args(self, mem):
        result = guard_tool_call(mem, "noop", None)
        assert result is None


# -------------------------------------------------------------------------
# Edge cases
# -------------------------------------------------------------------------

class TestEdgeCases:
    def test_guard_with_no_args_function(self, mem):
        @guard(mem, mode="warn")
        def no_args():
            """No arguments."""
            return 42

        assert no_args() == 42

    def test_guard_with_kwargs_only(self, mem):
        _seed_corrections(mem)

        @guard(mem, mode="warn")
        def send_email(to: str = "", subject: str = ""):
            """Send an email to the specified recipient."""
            return "sent"

        result = send_email(to="banned@example.com", subject="test")
        assert result == "sent"

    def test_guard_with_mixed_args(self, mem):
        @guard(mem, mode="warn")
        def func(a: int, b: str, c: float = 1.0):
            """Mixed args."""
            return (a, b, c)

        assert func(1, "two", c=3.0) == (1, "two", 3.0)

    def test_multiple_corrections_match(self, mem):
        # Store corrections with overlapping keywords
        mem.correct(
            "Never deploy without testing first",
            context="deploy production testing version",
        )
        mem.correct(
            "Always deploy with rollback plan",
            context="deploy production rollback version",
        )

        @guard(mem, mode="warn")
        def deploy_to_prod(version: str):
            """Deploy version to production."""
            return "deployed"

        result = deploy_to_prod("v1.0")
        assert result == "deployed"

        log = ActionLog(mem)
        entries = log.recent()
        assert len(entries[0]["corrections_matched"]) >= 1

    def test_function_with_no_docstring(self, mem):
        @guard(mem, mode="warn")
        def undocumented(x: int):
            return x * 2

        assert undocumented(5) == 10
