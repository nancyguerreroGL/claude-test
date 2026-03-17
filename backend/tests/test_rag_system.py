"""
Tests for RAGSystem.query() end-to-end.
AIGenerator, VectorStore, and DocumentProcessor are all mocked.
"""

import pytest
from unittest.mock import MagicMock, patch
from rag_system import RAGSystem

# ---------------------------------------------------------------------------
# Config fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_config():
    cfg = MagicMock()
    cfg.ANTHROPIC_API_KEY = "fake-key"
    cfg.ANTHROPIC_MODEL = "claude-sonnet-4-6"
    cfg.EMBEDDING_MODEL = "all-MiniLM-L6-v2"
    cfg.CHUNK_SIZE = 800
    cfg.CHUNK_OVERLAP = 100
    cfg.MAX_RESULTS = 5
    cfg.MAX_HISTORY = 2
    cfg.CHROMA_PATH = "/tmp/test_chroma"
    return cfg


# ---------------------------------------------------------------------------
# RAGSystem fixture — all heavy deps mocked
# ---------------------------------------------------------------------------


@pytest.fixture
def rag_and_mocks(mock_config):
    with (
        patch("rag_system.AIGenerator") as ai_cls,
        patch("rag_system.VectorStore") as vs_cls,
        patch("rag_system.DocumentProcessor"),
    ):

        mock_ai = MagicMock()
        ai_cls.return_value = mock_ai

        mock_vs = MagicMock()
        vs_cls.return_value = mock_vs

        system = RAGSystem(mock_config)
        yield system, mock_ai, mock_vs


# ---------------------------------------------------------------------------
# query() — basic return values
# ---------------------------------------------------------------------------


def test_query_returns_response_string(rag_and_mocks):
    rag, mock_ai, _ = rag_and_mocks
    mock_ai.generate_response.return_value = "The answer"
    response, sources = rag.query("what is MCP?")
    assert response == "The answer"


def test_query_returns_sources_list(rag_and_mocks):
    rag, mock_ai, _ = rag_and_mocks
    mock_ai.generate_response.return_value = "Answer"
    response, sources = rag.query("test")
    assert isinstance(sources, list)


# ---------------------------------------------------------------------------
# query() — prompt wrapping
# ---------------------------------------------------------------------------


def test_query_wraps_user_question_in_prompt(rag_and_mocks):
    rag, mock_ai, _ = rag_and_mocks
    mock_ai.generate_response.return_value = "ok"
    rag.query("what is MCP?")
    call_kwargs = mock_ai.generate_response.call_args[1]
    assert call_kwargs["query"].startswith(
        "Answer this question about course materials:"
    )
    assert "what is MCP?" in call_kwargs["query"]


# ---------------------------------------------------------------------------
# query() — tool plumbing
# ---------------------------------------------------------------------------


def test_query_passes_tool_definitions_to_ai(rag_and_mocks):
    rag, mock_ai, _ = rag_and_mocks
    mock_ai.generate_response.return_value = "ok"
    rag.query("test")
    call_kwargs = mock_ai.generate_response.call_args[1]
    assert isinstance(call_kwargs["tools"], list)
    assert len(call_kwargs["tools"]) > 0


def test_query_passes_tool_manager_to_ai(rag_and_mocks):
    rag, mock_ai, _ = rag_and_mocks
    mock_ai.generate_response.return_value = "ok"
    rag.query("test")
    call_kwargs = mock_ai.generate_response.call_args[1]
    assert call_kwargs["tool_manager"] is not None


def test_query_tool_definitions_include_search_course_content(rag_and_mocks):
    rag, mock_ai, _ = rag_and_mocks
    mock_ai.generate_response.return_value = "ok"
    rag.query("test")
    tools = mock_ai.generate_response.call_args[1]["tools"]
    names = [t["name"] for t in tools]
    assert "search_course_content" in names


# ---------------------------------------------------------------------------
# query() — session / conversation history
# ---------------------------------------------------------------------------


def test_query_no_session_passes_none_history(rag_and_mocks):
    rag, mock_ai, _ = rag_and_mocks
    mock_ai.generate_response.return_value = "ok"
    rag.query("test", session_id=None)
    call_kwargs = mock_ai.generate_response.call_args[1]
    assert call_kwargs["conversation_history"] is None


def test_query_with_session_passes_history_string(rag_and_mocks):
    rag, mock_ai, _ = rag_and_mocks
    mock_ai.generate_response.return_value = "ok"
    sid = rag.session_manager.create_session()
    rag.session_manager.add_exchange(sid, "prior question", "prior answer")
    rag.query("follow up", session_id=sid)
    call_kwargs = mock_ai.generate_response.call_args[1]
    history = call_kwargs["conversation_history"]
    assert history is not None
    assert "prior question" in history
    assert "prior answer" in history


def test_query_stores_exchange_in_session(rag_and_mocks):
    rag, mock_ai, _ = rag_and_mocks
    mock_ai.generate_response.return_value = "The answer"
    sid = rag.session_manager.create_session()
    rag.query("my question", session_id=sid)
    history = rag.session_manager.get_conversation_history(sid)
    assert "my question" in history
    assert "The answer" in history


def test_query_without_session_does_not_create_history(rag_and_mocks):
    rag, mock_ai, _ = rag_and_mocks
    mock_ai.generate_response.return_value = "ok"
    rag.query("test", session_id=None)
    assert rag.session_manager.sessions == {}


# ---------------------------------------------------------------------------
# query() — source management
# ---------------------------------------------------------------------------


def test_query_resets_sources_after_retrieval(rag_and_mocks):
    rag, mock_ai, _ = rag_and_mocks
    mock_ai.generate_response.return_value = "ok"
    rag.search_tool.last_sources = ["MCP Course - Lesson 1||https://example.com"]
    rag.query("test")
    assert rag.search_tool.last_sources == []


def test_query_returns_sources_populated_by_search_tool(rag_and_mocks):
    rag, mock_ai, _ = rag_and_mocks

    def _set_sources_and_return(*args, **kwargs):
        rag.search_tool.last_sources = ["MCP Course - Lesson 1||https://example.com"]
        return "Answer"

    mock_ai.generate_response.side_effect = _set_sources_and_return
    response, sources = rag.query("test")
    assert sources == ["MCP Course - Lesson 1||https://example.com"]


# ---------------------------------------------------------------------------
# Bug 1 regression: exception from AIGenerator propagates (not swallowed)
# ---------------------------------------------------------------------------


def test_query_propagates_ai_generator_exception(rag_and_mocks):
    """
    When AIGenerator raises (e.g., invalid model ID), RAGSystem.query()
    must NOT swallow it. FastAPI catches it and returns HTTP 500, which
    the frontend renders as 'query failed'. This test confirms the path.
    """
    rag, mock_ai, _ = rag_and_mocks
    mock_ai.generate_response.side_effect = Exception(
        "model: claude-sonnet-4-20250514 does not exist"
    )
    with pytest.raises(Exception, match="does not exist"):
        rag.query("what is MCP?")


# ---------------------------------------------------------------------------
# add_course_folder — non-existent path
# ---------------------------------------------------------------------------


def test_add_course_folder_returns_zero_for_nonexistent_path(rag_and_mocks):
    rag, _, _ = rag_and_mocks
    courses, chunks = rag.add_course_folder("/tmp/this_path_does_not_exist_xyz")
    assert courses == 0
    assert chunks == 0
