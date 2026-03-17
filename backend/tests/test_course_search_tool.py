"""
Tests for CourseSearchTool.execute() and ToolManager.
VectorStore is fully mocked — no real ChromaDB calls.
"""

import pytest
from unittest.mock import MagicMock
from search_tools import CourseSearchTool, ToolManager
from vector_store import SearchResults

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_store():
    return MagicMock()


@pytest.fixture
def search_tool(mock_store):
    return CourseSearchTool(mock_store)


def _empty_results():
    return SearchResults(documents=[], metadata=[], distances=[], error=None)


def _one_result(
    doc="Content about MCP.",
    course="MCP Course",
    lesson=2,
    link="https://example.com/lesson2",
):
    return SearchResults(
        documents=[doc],
        metadata=[
            {"course_title": course, "lesson_number": lesson, "lesson_link": link}
        ],
        distances=[0.1],
        error=None,
    )


# ---------------------------------------------------------------------------
# execute() — error path
# ---------------------------------------------------------------------------


def test_execute_returns_error_string_when_store_returns_error(search_tool, mock_store):
    mock_store.search.return_value = SearchResults(
        documents=[],
        metadata=[],
        distances=[],
        error="Search error: collection is empty",
    )
    result = search_tool.execute(query="what is MCP")
    assert result == "Search error: collection is empty"


# ---------------------------------------------------------------------------
# execute() — empty results path
# ---------------------------------------------------------------------------


def test_execute_returns_no_content_message_when_results_empty(search_tool, mock_store):
    mock_store.search.return_value = _empty_results()
    result = search_tool.execute(query="deep learning")
    assert result == "No relevant content found."


def test_execute_no_content_message_includes_course_filter(search_tool, mock_store):
    mock_store.search.return_value = _empty_results()
    result = search_tool.execute(query="neural networks", course_name="ML Course")
    assert "in course 'ML Course'" in result


def test_execute_no_content_message_includes_lesson_filter(search_tool, mock_store):
    mock_store.search.return_value = _empty_results()
    result = search_tool.execute(query="activations", lesson_number=3)
    assert "in lesson 3" in result


def test_execute_no_content_message_includes_both_filters(search_tool, mock_store):
    mock_store.search.return_value = _empty_results()
    result = search_tool.execute(
        query="activations", course_name="Deep Learning", lesson_number=3
    )
    assert "in course 'Deep Learning'" in result
    assert "in lesson 3" in result


# ---------------------------------------------------------------------------
# execute() — successful results formatting
# ---------------------------------------------------------------------------


def test_execute_formats_header_with_course_and_lesson(search_tool, mock_store):
    mock_store.search.return_value = _one_result()
    result = search_tool.execute(query="MCP servers")
    assert "[MCP Course - Lesson 2]" in result
    assert "Content about MCP." in result


def test_execute_formats_header_without_lesson_number(search_tool, mock_store):
    mock_store.search.return_value = SearchResults(
        documents=["Some content."],
        metadata=[
            {"course_title": "MCP Course", "lesson_number": None, "lesson_link": ""}
        ],
        distances=[0.1],
        error=None,
    )
    result = search_tool.execute(query="test")
    assert "[MCP Course]" in result
    assert "- Lesson" not in result


def test_execute_formats_multiple_results_separated_by_blank_line(
    search_tool, mock_store
):
    mock_store.search.return_value = SearchResults(
        documents=["Doc A.", "Doc B."],
        metadata=[
            {"course_title": "Course A", "lesson_number": 1, "lesson_link": ""},
            {"course_title": "Course B", "lesson_number": 2, "lesson_link": ""},
        ],
        distances=[0.1, 0.2],
        error=None,
    )
    result = search_tool.execute(query="test")
    assert "[Course A - Lesson 1]" in result
    assert "[Course B - Lesson 2]" in result
    assert "\n\n" in result


# ---------------------------------------------------------------------------
# execute() — source tracking
# ---------------------------------------------------------------------------


def test_execute_populates_last_sources_with_link(search_tool, mock_store):
    mock_store.search.return_value = _one_result(link="https://example.com/lesson2")
    search_tool.execute(query="test")
    assert len(search_tool.last_sources) == 1
    assert (
        search_tool.last_sources[0]
        == "MCP Course - Lesson 2||https://example.com/lesson2"
    )


def test_execute_populates_last_sources_without_link(search_tool, mock_store):
    mock_store.search.return_value = SearchResults(
        documents=["Doc."],
        metadata=[
            {"course_title": "MCP Course", "lesson_number": 1, "lesson_link": ""}
        ],
        distances=[0.1],
        error=None,
    )
    search_tool.execute(query="test")
    assert search_tool.last_sources[0] == "MCP Course - Lesson 1"


def test_execute_populates_last_sources_without_lesson_number(search_tool, mock_store):
    mock_store.search.return_value = SearchResults(
        documents=["Doc."],
        metadata=[
            {"course_title": "MCP Course", "lesson_number": None, "lesson_link": ""}
        ],
        distances=[0.1],
        error=None,
    )
    search_tool.execute(query="test")
    assert search_tool.last_sources[0] == "MCP Course"


# ---------------------------------------------------------------------------
# execute() — filter delegation to store
# ---------------------------------------------------------------------------


def test_execute_passes_all_filters_to_store(search_tool, mock_store):
    mock_store.search.return_value = _empty_results()
    search_tool.execute(query="topic", course_name="Python Basics", lesson_number=5)
    mock_store.search.assert_called_once_with(
        query="topic", course_name="Python Basics", lesson_number=5
    )


# ---------------------------------------------------------------------------
# Tool definition
# ---------------------------------------------------------------------------


def test_get_tool_definition_name_is_search_course_content(search_tool):
    defn = search_tool.get_tool_definition()
    assert defn["name"] == "search_course_content"


def test_get_tool_definition_query_is_required(search_tool):
    defn = search_tool.get_tool_definition()
    assert "query" in defn["input_schema"]["required"]


# ---------------------------------------------------------------------------
# ToolManager
# ---------------------------------------------------------------------------


def test_tool_manager_execute_unknown_tool_returns_error_string():
    manager = ToolManager()
    result = manager.execute_tool("nonexistent_tool", query="x")
    assert result == "Tool 'nonexistent_tool' not found"


def test_tool_manager_get_last_sources_after_search():
    mock_store = MagicMock()
    mock_store.search.return_value = _one_result()
    tool = CourseSearchTool(mock_store)
    manager = ToolManager()
    manager.register_tool(tool)
    manager.execute_tool("search_course_content", query="MCP")
    assert len(manager.get_last_sources()) > 0


def test_tool_manager_reset_clears_sources():
    mock_store = MagicMock()
    mock_store.search.return_value = _one_result()
    tool = CourseSearchTool(mock_store)
    manager = ToolManager()
    manager.register_tool(tool)
    manager.execute_tool("search_course_content", query="MCP")
    manager.reset_sources()
    assert manager.get_last_sources() == []
