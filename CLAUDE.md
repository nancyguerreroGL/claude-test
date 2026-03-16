# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Package Manager

Always use `uv` to run the server and manage packages. Never use `pip` directly.

## Commands

**Install dependencies:**
```bash
uv sync
```

**Run the application:**
```bash
./run.sh
# or manually:
cd backend && uv run uvicorn app:app --reload --port 8000
```

The app is served at `http://localhost:8000`. API docs at `http://localhost:8000/docs`.

**Environment setup:** Create a `.env` file in the project root:
```
ANTHROPIC_API_KEY=your_key_here
```

## Architecture

The backend lives entirely in `backend/` and is run from that directory — all imports are relative to it (no package structure, just flat modules).

**Request lifecycle:**
1. `app.py` receives `POST /api/query` and delegates to `RAGSystem.query()`
2. `rag_system.py` passes the query + conversation history to `AIGenerator`
3. `ai_generator.py` calls Claude with tools defined in `search_tools.py`
4. Claude decides whether to invoke `CourseSearchTool`, which calls `VectorStore.search()`
5. `vector_store.py` queries ChromaDB and returns ranked chunks
6. Claude synthesizes a final response; `session_manager.py` persists the turn

**Two ChromaDB collections** (stored in `backend/chroma_db/`):
- `course_catalog` — course-level metadata (title, instructor, lessons list) used for course name resolution via vector similarity
- `course_content` — text chunks with `course_title` and `lesson_number` metadata, used for semantic retrieval

**Document ingestion** happens at startup (`app.py` → `RAGSystem.add_course_folder()`). `document_processor.py` expects this format in each `.txt` file:
```
Course Title: ...
Course Link: ...
Course Instructor: ...
Lesson 1: Title
Lesson Link: ...
[content]
Lesson 2: Title
...
```
Chunks are sentence-boundary-split at 800 chars with 100-char overlap. Course deduplication prevents re-indexing on restart.

**Frontend** (`frontend/`) is plain HTML/CSS/JS served as static files by FastAPI. It communicates only via `/api/query` and `/api/courses`.
