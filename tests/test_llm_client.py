"""Mock-based tests for LLMClient.chat_with_tools.

These tests do NOT hit a real LLM. They inject a fake OpenAI client that
replays scripted responses to exercise the tool-calling loop logic.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from openprom.services.llm_client import LLMClient
from openprom.tools.schemas import Tool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_tool(name="check_meter", ret=None):
    """Create a simple Tool with a mock function."""
    func = MagicMock(return_value=ret or {"is_compliant": True})
    return Tool(
        name=name,
        description="test tool",
        parameters={"type": "object", "properties": {}},
        func=func,
    )


def _mock_message(content=None, tool_calls=None):
    """Create a mock ChatCompletionMessage."""
    msg = MagicMock()
    msg.content = content
    msg.tool_calls = tool_calls
    return msg


def _mock_choice(message):
    """Create a mock ChatCompletionChoice."""
    choice = MagicMock()
    choice.message = message
    return choice


def _mock_response(content=None, tool_calls=None):
    """Create a mock ChatCompletion."""
    resp = MagicMock()
    resp.choices = [_mock_choice(_mock_message(content, tool_calls))]
    return resp


def _mock_tool_call(name, args=None):
    """Create a mock tool call."""
    tc = MagicMock()
    tc.id = "tc-1"
    tc.type = "function"
    tc.function.name = name
    tc.function.arguments = json.dumps(args or {})
    return tc


def _make_client_with_mock_openai(responses):
    """Create an LLMClient with a mocked OpenAI client.

    ``responses`` is a list of mock ChatCompletion responses that will be
    returned in order by ``client.chat.completions.create``.
    """
    client = LLMClient(api_key="fake-key", base_url="http://fake", model="fake-model")
    mock_openai = MagicMock()
    mock_openai.chat.completions.create = MagicMock(side_effect=list(responses))
    client._client = mock_openai
    return client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestChatWithTools:
    def test_no_tools_returns_content_immediately(self):
        """When the LLM returns no tool calls, the loop ends after round 1."""
        client = _make_client_with_mock_openai([
            _mock_response(content="Hello world"),
        ])
        result = client.chat_with_tools(
            prompt="hi",
            tools=[],
            max_rounds=3,
        )
        assert result["content"] == "Hello world"
        assert len(result["messages"]) == 2  # user + assistant

    def test_tool_call_then_done(self):
        """LLM calls a tool in round 1, then returns content in round 2."""
        tool = _make_tool(ret={"is_compliant": True})
        tc = _mock_tool_call("check_meter", {"text": "test"})
        client = _make_client_with_mock_openai([
            _mock_response(content=None, tool_calls=[tc]),
            _mock_response(content="Done"),
        ])
        result = client.chat_with_tools(
            prompt="check this",
            tools=[tool],
            max_rounds=5,
        )
        assert result["content"] == "Done"
        assert len(result["messages"]) == 4  # user, assistant(+tc), tool, assistant
        tool.func.assert_called_once_with(text="test")

    def test_multiple_tool_calls_in_one_round(self):
        """LLM calls two tools in a single round."""
        tool1 = _make_tool("tool_a", ret={"ok": 1})
        tool2 = _make_tool("tool_b", ret={"ok": 2})
        tc1 = _mock_tool_call("tool_a", {"x": 1})
        tc2 = _mock_tool_call("tool_b", {"y": 2})
        client = _make_client_with_mock_openai([
            _mock_response(content=None, tool_calls=[tc1, tc2]),
            _mock_response(content="Both done"),
        ])
        result = client.chat_with_tools(
            prompt="run both",
            tools=[tool1, tool2],
            max_rounds=5,
        )
        assert result["content"] == "Both done"
        tool1.func.assert_called_once_with(x=1)
        tool2.func.assert_called_once_with(y=2)

    def test_max_rounds_exhausted(self):
        """When max_rounds is reached without a final answer, return last message."""
        tc = _mock_tool_call("check_meter", {"text": "x"})
        # Always return a tool call, never a final answer
        client = _make_client_with_mock_openai([
            _mock_response(content=None, tool_calls=[tc]),
            _mock_response(content=None, tool_calls=[tc]),
            _mock_response(content=None, tool_calls=[tc]),
        ])
        tool = _make_tool()
        result = client.chat_with_tools(
            prompt="loop",
            tools=[tool],
            max_rounds=3,
        )
        # Should return after 3 rounds; content may be empty
        assert "messages" in result
        # Tool should have been called 3 times (once per round)
        assert tool.func.call_count == 3

    def test_unknown_tool_returns_error(self):
        """Calling an unregistered tool produces an error result in messages."""
        tc = _mock_tool_call("nonexistent", {})
        client = _make_client_with_mock_openai([
            _mock_response(content=None, tool_calls=[tc]),
            _mock_response(content="ok"),
        ])
        result = client.chat_with_tools(
            prompt="x",
            tools=[],
            max_rounds=3,
        )
        # The tool result message should contain an error
        tool_msgs = [m for m in result["messages"] if m.get("role") == "tool"]
        assert len(tool_msgs) == 1
        assert "error" in tool_msgs[0]["content"].lower()

    def test_tool_exception_caught(self):
        """When a tool raises, the error is passed back as the tool result."""
        tool = _make_tool()
        tool.func = MagicMock(side_effect=RuntimeError("boom"))
        tc = _mock_tool_call("check_meter", {"text": "x"})
        client = _make_client_with_mock_openai([
            _mock_response(content=None, tool_calls=[tc]),
            _mock_response(content="recovered"),
        ])
        result = client.chat_with_tools(
            prompt="x",
            tools=[tool],
            max_rounds=3,
        )
        assert result["content"] == "recovered"
        tool_msgs = [m for m in result["messages"] if m.get("role") == "tool"]
        assert "boom" in tool_msgs[0]["content"]

    def test_progress_callback_events(self):
        """progress_callback receives thinking, tool_call, tool_result, done."""
        tool = _make_tool(ret={"ok": True})
        tc = _mock_tool_call("check_meter", {"text": "x"})
        client = _make_client_with_mock_openai([
            _mock_response(content=None, tool_calls=[tc]),
            _mock_response(content="final"),
        ])
        events = []

        def cb(event, payload):
            events.append((event, payload))

        client.chat_with_tools(
            prompt="x",
            tools=[tool],
            max_rounds=3,
            progress_callback=cb,
        )
        event_types = [e[0] for e in events]
        assert "thinking" in event_types
        assert "tool_call" in event_types
        assert "tool_result" in event_types
        assert "done" in event_types

    def test_system_prompt_included_in_messages(self):
        """When system_prompt is provided, it's the first message."""
        client = _make_client_with_mock_openai([
            _mock_response(content="ok"),
        ])
        result = client.chat_with_tools(
            prompt="hi",
            tools=[],
            system_prompt="You are a poet.",
        )
        assert result["messages"][0]["role"] == "system"
        assert result["messages"][0]["content"] == "You are a poet."

    def test_temperature_override(self):
        """Custom temperature is passed to the API."""
        client = _make_client_with_mock_openai([
            _mock_response(content="ok"),
        ])
        client.chat_with_tools(
            prompt="hi",
            tools=[],
            temperature=0.1,
        )
        call_kwargs = client._client.chat.completions.create.call_args.kwargs
        assert call_kwargs["temperature"] == 0.1


class TestChat:
    def test_simple_chat(self):
        client = _make_client_with_mock_openai([
            _mock_response(content="Hello"),
        ])
        result = client.chat(prompt="hi")
        assert result["content"] == "Hello"

    def test_json_mode_parses(self):
        client = _make_client_with_mock_openai([
            _mock_response(content='{"score": 85, "grade": "good"}'),
        ])
        result = client.chat(prompt="rate this", json_mode=True)
        assert result["score"] == 85
        assert result["grade"] == "good"

    def test_system_prompt_prepended(self):
        client = _make_client_with_mock_openai([
            _mock_response(content="ok"),
        ])
        client.chat(prompt="hi", system_prompt="Be brief.")
        msgs = client._client.chat.completions.create.call_args.kwargs["messages"]
        assert msgs[0]["role"] == "system"
        assert msgs[0]["content"] == "Be brief."
