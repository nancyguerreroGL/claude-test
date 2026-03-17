import sys
import os

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

import pytest
from unittest.mock import MagicMock


# ---------------------------------------------------------------------------
# Shared config fixture
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
# Shared RAGSystem fixture — all heavy deps mocked
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_rag_system():
    """Fully mocked RAGSystem for API-level tests."""
    rag = MagicMock()
    rag.query.return_value = ("Default answer", [])
    rag.get_course_analytics.return_value = {
        "total_courses": 0,
        "course_titles": [],
    }
    rag.session_manager.create_session.return_value = "test-session-id"
    return rag
