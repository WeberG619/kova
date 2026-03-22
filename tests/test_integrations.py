"""Tests for neveronce.integrations — no framework dependencies required."""

import tempfile
import os
import pytest

from neveronce import Memory
from neveronce.integrations import (
    generic_agent_guard,
    langchain_tool_wrapper,
    openai_function_guard,
    anthropic_tool_guard,
    crewai_task_guard,
    autogen_message_guard,
    _build_action_string,
)


@pytest.fixture
def mem():
    """Memory instance with a temp directory, pre-loaded with corrections."""
    tmpdir = tempfile.mkdtemp()
    m = Memory("test_integrations", db_dir=tmpdir)
    # Seed corrections that the guards should catch
    m.correct("never send email to production users during testing",
              context="send_email production users testing")
    m.correct("always use staging database for integration tests",
              context="database staging integration tests")
    m.correct("never delete files from shared config directory",
              context="delete files shared config directory")
    yield m
    m.close()


class TestBuildActionString:
    def test_name_only(self):
        result = _build_action_string("send_email")
        assert result == "send_email"

    def test_with_params(self):
        result = _build_action_string("send_email", {"to": "a@b.com", "subject": "hi"})
        assert "send_email" in result
        assert "to=a@b.com" in result
        assert "subject=hi" in result

    def test_with_description(self):
        result = _build_action_string("search", description="Search the web")
        assert "search" in result
        assert "Search the web" in result

    def test_with_all(self):
        result = _build_action_string("deploy", {"env": "prod"}, "Deploy application")
        assert "deploy" in result
        assert "env=prod" in result
        assert "Deploy application" in result


class TestGenericAgentGuard:
    def test_returns_none_when_no_match(self, mem):
        result = generic_agent_guard(mem, "calculate", {"x": 1, "y": 2})
        assert result is None

    def test_returns_corrections_on_match(self, mem):
        result = generic_agent_guard(mem, "send_email",
                                     {"to": "production users during testing"})
        assert result is not None
        assert len(result) >= 1
        assert any("email" in c["content"] for c in result)

    def test_returns_none_for_unrelated_action(self, mem):
        result = generic_agent_guard(mem, "read_file", {"path": "/tmp/safe.txt"})
        assert result is None


class TestLangchainToolWrapper:
    def test_wraps_tool_and_blocks(self, mem):
        class FakeTool:
            name = "send_email"
            description = "Send email to production users during testing"
            def _run(self, query):
                return f"sent: {query}"

        guarded = langchain_tool_wrapper(mem, FakeTool())
        result = guarded._run("send to production users during testing")
        assert "BLOCKED" in result

    def test_wraps_tool_and_allows(self, mem):
        class FakeTool:
            name = "calculator"
            description = "Do math"
            def _run(self, query):
                return f"result: {query}"

        guarded = langchain_tool_wrapper(mem, FakeTool())
        result = guarded._run("2 + 2")
        assert result == "result: 2 + 2"

    def test_preserves_name(self, mem):
        class FakeTool:
            name = "my_tool"
            description = ""
            def _run(self, q):
                return q

        guarded = langchain_tool_wrapper(mem, FakeTool())
        assert guarded.name == "my_tool"

    def test_proxies_attributes(self, mem):
        class FakeTool:
            name = "t"
            description = ""
            custom_attr = 42
            def _run(self, q):
                return q

        guarded = langchain_tool_wrapper(mem, FakeTool())
        assert guarded.custom_attr == 42


class TestOpenAIFunctionGuard:
    def test_catches_correction(self, mem):
        result = openai_function_guard(
            mem,
            function_name="send_email",
            arguments={"to": "production users during testing"}
        )
        assert result is not None
        assert len(result) >= 1

    def test_allows_safe_call(self, mem):
        result = openai_function_guard(
            mem,
            function_name="get_weather",
            arguments={"city": "Seattle"}
        )
        assert result is None


class TestAnthropicToolGuard:
    def test_catches_correction(self, mem):
        result = anthropic_tool_guard(
            mem,
            tool_name="delete",
            tool_input={"path": "files from shared config directory"}
        )
        assert result is not None

    def test_allows_safe_call(self, mem):
        result = anthropic_tool_guard(
            mem,
            tool_name="read_file",
            tool_input={"path": "/tmp/notes.txt"}
        )
        assert result is None


class TestCrewAITaskGuard:
    def test_catches_correction(self, mem):
        result = crewai_task_guard(
            mem,
            "send_email to production users during testing phase"
        )
        assert result is not None

    def test_allows_safe_task(self, mem):
        result = crewai_task_guard(mem, "summarize the quarterly report")
        assert result is None


class TestAutoGenMessageGuard:
    def test_string_message_catches(self, mem):
        result = autogen_message_guard(
            mem,
            "please send_email to production users during testing"
        )
        assert result is not None

    def test_dict_message_catches(self, mem):
        result = autogen_message_guard(
            mem,
            {"content": "delete files from shared config directory now",
             "role": "assistant"}
        )
        assert result is not None

    def test_safe_message(self, mem):
        result = autogen_message_guard(mem, "what is 2+2?")
        assert result is None

    def test_dict_without_content_key(self, mem):
        result = autogen_message_guard(mem, {"text": "hello"})
        # Should not crash, just uses str representation
        assert result is None or isinstance(result, list)
