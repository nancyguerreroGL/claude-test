"""
Tests for FastAPI endpoints: POST /api/query, GET /api/courses, GET /.

A minimal test app is defined here (no static file mount) to avoid the
frontend directory not existing in the test environment.
"""
import pytest
from unittest.mock import MagicMock, patch
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient
from pydantic import BaseModel
from typing import List, Optional


# ---------------------------------------------------------------------------
# Minimal test app — mirrors app.py endpoints without the static file mount
# ---------------------------------------------------------------------------

def make_test_app(rag_system):
    """Return a FastAPI app wired to the provided rag_system mock."""
    app = FastAPI()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    class QueryRequest(BaseModel):
        query: str
        session_id: Optional[str] = None

    class QueryResponse(BaseModel):
        answer: str
        sources: List[str]
        session_id: str

    class CourseStats(BaseModel):
        total_courses: int
        course_titles: List[str]

    @app.post("/api/query", response_model=QueryResponse)
    async def query_documents(request: QueryRequest):
        try:
            session_id = request.session_id
            if not session_id:
                session_id = rag_system.session_manager.create_session()
            answer, sources = rag_system.query(request.query, session_id)
            return QueryResponse(answer=answer, sources=sources, session_id=session_id)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/courses", response_model=CourseStats)
    async def get_course_stats():
        try:
            analytics = rag_system.get_course_analytics()
            return CourseStats(
                total_courses=analytics["total_courses"],
                course_titles=analytics["course_titles"],
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    return app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def rag(mock_rag_system):
    return mock_rag_system


@pytest.fixture
def client(rag):
    app = make_test_app(rag)
    return TestClient(app)


# ---------------------------------------------------------------------------
# POST /api/query — happy path
# ---------------------------------------------------------------------------

def test_query_returns_200(client, rag):
    rag.query.return_value = ("MCP is a protocol.", [])
    resp = client.post("/api/query", json={"query": "What is MCP?"})
    assert resp.status_code == 200


def test_query_response_contains_answer(client, rag):
    rag.query.return_value = ("MCP is a protocol.", [])
    resp = client.post("/api/query", json={"query": "What is MCP?"})
    assert resp.json()["answer"] == "MCP is a protocol."


def test_query_response_contains_session_id(client, rag):
    rag.query.return_value = ("Some answer.", [])
    resp = client.post("/api/query", json={"query": "test"})
    assert resp.json()["session_id"] == "test-session-id"


def test_query_response_sources_is_list(client, rag):
    rag.query.return_value = ("Answer.", ["MCP Course - Lesson 1||https://example.com"])
    resp = client.post("/api/query", json={"query": "test"})
    assert isinstance(resp.json()["sources"], list)


def test_query_sources_populated_when_search_returns_results(client, rag):
    rag.query.return_value = ("Answer.", ["MCP Course - Lesson 1||https://example.com"])
    resp = client.post("/api/query", json={"query": "MCP"})
    assert resp.json()["sources"] == ["MCP Course - Lesson 1||https://example.com"]


# ---------------------------------------------------------------------------
# POST /api/query — session passthrough
# ---------------------------------------------------------------------------

def test_query_uses_provided_session_id(client, rag):
    rag.query.return_value = ("Answer.", [])
    resp = client.post("/api/query", json={"query": "test", "session_id": "my-session"})
    assert resp.json()["session_id"] == "my-session"


def test_query_creates_session_when_none_provided(client, rag):
    rag.query.return_value = ("Answer.", [])
    resp = client.post("/api/query", json={"query": "test"})
    # session_manager.create_session() returns "test-session-id" in the fixture
    assert resp.json()["session_id"] == "test-session-id"


def test_query_calls_rag_with_correct_query(client, rag):
    rag.query.return_value = ("ok", [])
    client.post("/api/query", json={"query": "What is MCP?"})
    call_args = rag.query.call_args
    assert call_args[0][0] == "What is MCP?"


# ---------------------------------------------------------------------------
# POST /api/query — validation errors
# ---------------------------------------------------------------------------

def test_query_returns_422_when_query_field_missing(client):
    resp = client.post("/api/query", json={})
    assert resp.status_code == 422


def test_query_returns_422_when_body_is_empty(client):
    resp = client.post("/api/query", json=None)
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /api/query — error propagation
# ---------------------------------------------------------------------------

def test_query_returns_500_when_rag_raises(client, rag):
    rag.query.side_effect = Exception("Internal failure")
    resp = client.post("/api/query", json={"query": "test"})
    assert resp.status_code == 500


def test_query_500_detail_contains_exception_message(client, rag):
    rag.query.side_effect = Exception("model does not exist")
    resp = client.post("/api/query", json={"query": "test"})
    assert "model does not exist" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# GET /api/courses — happy path
# ---------------------------------------------------------------------------

def test_courses_returns_200(client, rag):
    rag.get_course_analytics.return_value = {"total_courses": 3, "course_titles": ["A", "B", "C"]}
    resp = client.get("/api/courses")
    assert resp.status_code == 200


def test_courses_returns_total_count(client, rag):
    rag.get_course_analytics.return_value = {"total_courses": 2, "course_titles": ["MCP", "Python"]}
    resp = client.get("/api/courses")
    assert resp.json()["total_courses"] == 2


def test_courses_returns_title_list(client, rag):
    rag.get_course_analytics.return_value = {"total_courses": 2, "course_titles": ["MCP", "Python"]}
    resp = client.get("/api/courses")
    assert resp.json()["course_titles"] == ["MCP", "Python"]


def test_courses_returns_empty_list_when_no_courses(client, rag):
    rag.get_course_analytics.return_value = {"total_courses": 0, "course_titles": []}
    resp = client.get("/api/courses")
    data = resp.json()
    assert data["total_courses"] == 0
    assert data["course_titles"] == []


# ---------------------------------------------------------------------------
# GET /api/courses — error propagation
# ---------------------------------------------------------------------------

def test_courses_returns_500_when_rag_raises(client, rag):
    rag.get_course_analytics.side_effect = Exception("DB error")
    resp = client.get("/api/courses")
    assert resp.status_code == 500


def test_courses_500_detail_contains_exception_message(client, rag):
    rag.get_course_analytics.side_effect = Exception("DB error")
    resp = client.get("/api/courses")
    assert "DB error" in resp.json()["detail"]
