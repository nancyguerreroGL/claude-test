"""
Tests for AIGenerator.generate_response() and _handle_tool_execution().
The Anthropic client is fully mocked — no real API calls.
"""

import pytest
from unittest.mock import MagicMock, patch
from ai_generator import AIGenerator

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_text_response(text="Answer"):
    """Mock a Claude response with stop_reason=end_turn and a text block."""
    block = MagicMock()
    block.type = "text"
    block.text = text
    response = MagicMock()
    response.stop_reason = "end_turn"
    response.content = [block]
    return response


def make_tool_use_response(name="search_course_content", tool_id="tu_1", inp=None):
    """Mock a Claude response with stop_reason=tool_use."""
    block = MagicMock()
    block.type = "tool_use"
    block.name = name
    block.id = tool_id
    block.input = inp or {"query": "test query"}
    response = MagicMock()
    response.stop_reason = "tool_use"
    response.content = [block]
    return response


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def generator_and_client():
    with patch("ai_generator.anthropic.Anthropic") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        gen = AIGenerator(api_key="fake-key", model="claude-sonnet-4-6")
        yield gen, mock_client


# ---------------------------------------------------------------------------
# Direct (no-tool) response path
# ---------------------------------------------------------------------------


def test_direct_response_returned_when_no_tool_use(generator_and_client):
    gen, client = generator_and_client
    client.messages.create.return_value = make_text_response("The answer")
    result = gen.generate_response("What is MCP?")
    assert result == "The answer"
    assert client.messages.create.call_count == 1


def test_tools_not_in_params_when_not_provided(generator_and_client):
    gen, client = generator_and_client
    client.messages.create.return_value = make_text_response()
    gen.generate_response("Hello")
    call_kwargs = client.messages.create.call_args[1]
    assert "tools" not in call_kwargs


def test_tools_added_to_params_when_provided(generator_and_client):
    gen, client = generator_and_client
    client.messages.create.return_value = make_text_response()
    tool_defs = [{"name": "search_course_content", "description": "search"}]
    gen.generate_response("test", tools=tool_defs)
    call_kwargs = client.messages.create.call_args[1]
    assert "tools" in call_kwargs
    assert call_kwargs["tool_choice"] == {"type": "auto"}


def test_conversation_history_appended_to_system_prompt(generator_and_client):
    gen, client = generator_and_client
    client.messages.create.return_value = make_text_response()
    gen.generate_response(
        "follow up", conversation_history="User: hello\nAssistant: hi"
    )
    call_kwargs = client.messages.create.call_args[1]
    assert "Previous conversation:" in call_kwargs["system"]
    assert "User: hello" in call_kwargs["system"]


def test_model_and_temperature_in_api_params(generator_and_client):
    gen, client = generator_and_client
    client.messages.create.return_value = make_text_response()
    gen.generate_response("test")
    call_kwargs = client.messages.create.call_args[1]
    assert call_kwargs["model"] == "claude-sonnet-4-6"
    assert call_kwargs["temperature"] == 0
    assert call_kwargs["max_tokens"] == 800


# ---------------------------------------------------------------------------
# Tool-use path
# ---------------------------------------------------------------------------


def test_tool_use_response_triggers_second_api_call(generator_and_client):
    gen, client = generator_and_client
    tool_use_resp = make_tool_use_response()
    final_resp = make_text_response("Final answer")
    client.messages.create.side_effect = [tool_use_resp, final_resp]

    mock_tool_manager = MagicMock()
    mock_tool_manager.execute_tool.return_value = (
        "[MCP Course - Lesson 1]\nContent here."
    )

    result = gen.generate_response(
        "What is MCP?",
        tools=[{"name": "search_course_content"}],
        tool_manager=mock_tool_manager,
    )
    assert result == "Final answer"
    assert client.messages.create.call_count == 2


def test_second_api_call_includes_tool_result_message(generator_and_client):
    gen, client = generator_and_client
    tool_use_resp = make_tool_use_response(tool_id="tu_123")
    final_resp = make_text_response("Done")
    client.messages.create.side_effect = [tool_use_resp, final_resp]

    mock_tool_manager = MagicMock()
    mock_tool_manager.execute_tool.return_value = "search result"

    gen.generate_response(
        "query",
        tools=[{"name": "search_course_content"}],
        tool_manager=mock_tool_manager,
    )

    second_call_kwargs = client.messages.create.call_args_list[1][1]
    messages = second_call_kwargs["messages"]
    last_message = messages[-1]
    assert last_message["role"] == "user"
    assert last_message["content"][0]["type"] == "tool_result"
    assert last_message["content"][0]["tool_use_id"] == "tu_123"


def test_tools_present_in_loop_api_calls(generator_and_client):
    gen, client = generator_and_client
    client.messages.create.side_effect = [
        make_tool_use_response(tool_id="tu_1"),
        make_tool_use_response(tool_id="tu_2"),
        make_text_response("Done"),
    ]
    mock_tool_manager = MagicMock()
    mock_tool_manager.execute_tool.return_value = "result"
    gen.generate_response("q", tools=[{"name": "t"}], tool_manager=mock_tool_manager)
    assert "tools" in client.messages.create.call_args_list[1][1]
    assert "tools" in client.messages.create.call_args_list[2][1]


def test_tool_manager_execute_tool_called_with_correct_args(generator_and_client):
    gen, client = generator_and_client
    client.messages.create.side_effect = [
        make_tool_use_response(
            name="search_course_content", inp={"query": "test query"}
        ),
        make_text_response("Done"),
    ]
    mock_tool_manager = MagicMock()
    mock_tool_manager.execute_tool.return_value = "result"
    gen.generate_response("q", tools=[{"name": "t"}], tool_manager=mock_tool_manager)
    mock_tool_manager.execute_tool.assert_called_once_with(
        "search_course_content", query="test query"
    )


def test_no_second_call_when_tool_manager_is_none(generator_and_client):
    gen, client = generator_and_client
    client.messages.create.return_value = make_tool_use_response()
    gen.generate_response("q", tools=[{"name": "t"}], tool_manager=None)
    assert client.messages.create.call_count == 1


# ---------------------------------------------------------------------------
# Bug 1 regression: invalid model raises exception (not swallowed)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Sequential tool calling (up to 2 rounds)
# ---------------------------------------------------------------------------


def test_two_sequential_tool_calls_three_api_calls_total(generator_and_client):
    gen, client = generator_and_client
    client.messages.create.side_effect = [
        make_tool_use_response(name="get_course_outline", tool_id="tu_1"),
        make_tool_use_response(name="search_course_content", tool_id="tu_2"),
        make_text_response("Combined answer"),
    ]
    mock_tool_manager = MagicMock()
    mock_tool_manager.execute_tool.side_effect = ["outline result", "search result"]
    result = gen.generate_response(
        "q", tools=[{"name": "t"}], tool_manager=mock_tool_manager
    )
    assert client.messages.create.call_count == 3
    assert mock_tool_manager.execute_tool.call_count == 2
    assert result == "Combined answer"


def test_message_list_grows_correctly_across_two_rounds(generator_and_client):
    gen, client = generator_and_client
    client.messages.create.side_effect = [
        make_tool_use_response(tool_id="tu_1"),
        make_tool_use_response(tool_id="tu_2"),
        make_text_response("Done"),
    ]
    mock_tool_manager = MagicMock()
    mock_tool_manager.execute_tool.return_value = "result"
    gen.generate_response(
        "query", tools=[{"name": "t"}], tool_manager=mock_tool_manager
    )

    third_call_messages = client.messages.create.call_args_list[2][1]["messages"]
    assert len(third_call_messages) == 5
    assert third_call_messages[0]["role"] == "user"
    assert third_call_messages[1]["role"] == "assistant"
    assert third_call_messages[2]["role"] == "user"
    assert third_call_messages[2]["content"][0]["type"] == "tool_result"
    assert third_call_messages[2]["content"][0]["tool_use_id"] == "tu_1"
    assert third_call_messages[3]["role"] == "assistant"
    assert third_call_messages[4]["role"] == "user"
    assert third_call_messages[4]["content"][0]["type"] == "tool_result"
    assert third_call_messages[4]["content"][0]["tool_use_id"] == "tu_2"


def test_early_exit_when_end_turn_after_round_1(generator_and_client):
    gen, client = generator_and_client
    client.messages.create.side_effect = [
        make_tool_use_response(),
        make_text_response("Final"),
    ]
    mock_tool_manager = MagicMock()
    mock_tool_manager.execute_tool.return_value = "result"
    result = gen.generate_response(
        "q", tools=[{"name": "t"}], tool_manager=mock_tool_manager
    )
    assert client.messages.create.call_count == 2
    assert mock_tool_manager.execute_tool.call_count == 1
    assert result == "Final"


def test_tool_execution_error_handled_gracefully(generator_and_client):
    gen, client = generator_and_client
    client.messages.create.side_effect = [
        make_tool_use_response(),
        make_text_response("Fallback response"),
    ]
    mock_tool_manager = MagicMock()
    mock_tool_manager.execute_tool.side_effect = Exception("DB error")
    result = gen.generate_response(
        "q", tools=[{"name": "t"}], tool_manager=mock_tool_manager
    )
    assert client.messages.create.call_count == 2
    assert result == "Fallback response"


def test_max_rounds_respected(generator_and_client):
    gen, client = generator_and_client
    client.messages.create.side_effect = [
        make_tool_use_response(tool_id="tu_1"),
        make_tool_use_response(tool_id="tu_2"),
        make_tool_use_response(tool_id="tu_3"),
    ]
    mock_tool_manager = MagicMock()
    mock_tool_manager.execute_tool.return_value = "result"
    result = gen.generate_response(
        "q", tools=[{"name": "t"}], tool_manager=mock_tool_manager
    )
    assert client.messages.create.call_count == 3
    assert mock_tool_manager.execute_tool.call_count == 2
    assert result == ""


# ---------------------------------------------------------------------------
# Bug 1 regression: invalid model raises exception (not swallowed)
# ---------------------------------------------------------------------------


def test_invalid_model_raises_exception(generator_and_client):
    """
    Documents that AIGenerator does NOT swallow API exceptions.
    When the model ID is wrong, the Anthropic API raises; that exception
    must propagate so callers (RAGSystem → FastAPI) can handle it.
    """
    gen, client = generator_and_client
    client.messages.create.side_effect = Exception(
        "model: claude-sonnet-4-20250514 does not exist"
    )
    with pytest.raises(Exception, match="does not exist"):
        gen.generate_response("what is MCP?")
