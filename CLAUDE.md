# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Running the Application
```bash
# Quick start (recommended)
./run.sh

# Manual start
cd backend && uv run uvicorn app:app --reload --port 8000

# Access points
# - Web UI: http://localhost:8000
# - API docs: http://localhost:8000/docs (auto-generated Swagger)
```

### Package Management
```bash
# Install/sync dependencies
uv sync

# Run commands with uv
uv run <command>

# Example: Run Python script
uv run python backend/script.py
```

### Environment Setup
- Copy `.env.example` to `.env` and add your `ANTHROPIC_API_KEY`
- Requires Python 3.13+ and uv package manager
- For Windows: Use Git Bash to run commands

### Working with Documents
```bash
# Documents are auto-loaded from docs/ on startup
# Supported formats: .txt, .pdf, .docx

# Expected document format:
# Course Title: [title]
# Course Link: [url]
# Course Instructor: [instructor]
#
# Lesson 0: [lesson title]
# Lesson Link: [url]
# [lesson content]
```

## Architecture Overview

This is a full-stack RAG (Retrieval-Augmented Generation) system using **tool-based architecture** where Claude calls search tools via function calling rather than direct context injection.

### Core Architecture Principles

**Tool-Based Search Pattern**
- AI doesn't receive search results upfront
- Instead, AI has access to `search_course_content` tool
- AI decides when/what to search based on user query
- Reduces token usage and prevents hallucinations

**Dual Vector Store Design**
- `course_catalog` collection: Course metadata for discovery
- `course_content` collection: Actual content chunks for retrieval
- Enables both "what courses exist?" and "what does course X say about Y?" queries

**Component Initialization Flow**
```
Config → RAGSystem → {
    DocumentProcessor,
    VectorStore (ChromaDB),
    AIGenerator (Anthropic),
    SessionManager,
    ToolManager → CourseSearchTool
}
```

### Key Components (`backend/`)

**RAGSystem (`rag_system.py`)** - Main orchestrator
- `add_course_document()`: Process single file → Course + CourseChunks
- `add_course_folder()`: Batch process with deduplication on `course.title`
- `query()`: Process user query with tool-based search
- `get_course_analytics()`: Return catalog statistics

**VectorStore (`vector_store.py`)** - ChromaDB wrapper
- Two collections: `course_catalog` (metadata) + `course_content` (chunks)
- `search()`: Unified search interface with course/lesson filtering
- `_resolve_course_name()`: Semantic matching for partial course names
- Embedding: sentence-transformers `all-MiniLM-L6-v2` model

**AIGenerator (`ai_generator.py`)** - Claude integration
- Agentic workflow with tool calling loop
- System prompt guides tool usage strategy
- `_handle_tool_execution()`: Execute tools and get follow-up response
- Config: claude-sonnet-4-20250514, temp=0, max_tokens=800

**SearchTools (`search_tools.py`)** - Extensible tool framework
- Abstract `Tool` base class for new tools
- `CourseSearchTool`: Implements search with filtering
- `ToolManager`: Registers tools, provides definitions, executes calls
- Source tracking for UI citation display

**DocumentProcessor (`document_processor.py`)** - Text processing
- Parses structured course format (title, instructor, lessons)
- Sentence-aware chunking: 800 chars + 100 overlap
- Handles abbreviations (Dr., etc.) to avoid mid-sentence splits
- Creates `CourseChunk` objects with metadata

**SessionManager (`session_manager.py`)** - Conversation history
- In-memory storage (not persistent across restarts)
- Maintains last 2 conversation turns (configurable via `MAX_HISTORY`)
- Provides conversation context to AI for follow-up questions

**Models (`models.py`)** - Pydantic schemas
```python
Course: title, course_link, instructor, lessons[]
Lesson: lesson_number, title, lesson_link
CourseChunk: content, course_title, lesson_number, chunk_index
```

**Config (`config.py`)** - Centralized settings
- All tunable parameters in one place
- Loads from environment variables
- Key settings: CHUNK_SIZE=800, CHUNK_OVERLAP=100, MAX_RESULTS=5

**FastAPI App (`app.py`)** - Web server
- `POST /api/query`: Main query endpoint (query, session_id → answer, sources, session_id)
- `GET /api/courses`: Catalog analytics endpoint
- CORS enabled, serves frontend as static files
- Loads docs folder on startup with incremental loading

### Data Models

The three core models represent the data pipeline:

```
Text File → DocumentProcessor → Course + List[CourseChunk] → VectorStore
                                    ↓
                        User Query → Tool Search → Results
```

**Course**: Full course metadata with lessons array (unique by title)
**Lesson**: Individual lesson within course (numbered sequentially)
**CourseChunk**: Vector-searchable text unit (800 chars, includes course/lesson context)

### Key Implementation Details

**Incremental Document Loading**
- `add_course_folder()` checks existing course titles before processing
- Avoids re-embedding documents on server restart
- Deduplication based on `course.title`, not filename

**Tool Execution Flow**
1. User query → AIGenerator receives query + tool definitions
2. Claude decides to call `search_course_content` tool
3. ToolManager routes to CourseSearchTool
4. VectorStore performs semantic search with filters
5. Results formatted and returned to Claude
6. Claude generates final response using search results
7. Sources tracked and returned to frontend

**Sentence-Aware Chunking**
- Splits on sentence boundaries, not arbitrary character counts
- Maintains 100-char overlap to preserve context across chunks
- First chunk of each lesson includes lesson context
- Handles common abbreviations (Mr., Dr., etc.) correctly

**Session Management**
- Unique session IDs track conversations
- History format: `[{role: user, content: ...}, {role: assistant, content: ...}]`
- Limited to 2 turns to balance context vs token cost
- Frontend persists session_id for multi-turn conversations

### Configuration Parameters

All in `config.py` (override via environment variables):

```python
ANTHROPIC_API_KEY: str         # Required API key
ANTHROPIC_MODEL: str           # "claude-sonnet-4-20250514"
EMBEDDING_MODEL: str           # "all-MiniLM-L6-v2"
CHUNK_SIZE: int                # 800 (characters per chunk)
CHUNK_OVERLAP: int             # 100 (overlap between chunks)
MAX_RESULTS: int               # 5 (search results per query)
MAX_HISTORY: int               # 2 (conversation turns to remember)
CHROMA_PATH: str               # "./chroma_db" (vector DB location)
```

### Adding New Tools

To extend tool capabilities:

1. Create new class inheriting from `Tool` in `search_tools.py`
2. Implement `get_tool_definition()` with Anthropic schema
3. Implement `execute(**kwargs)` with tool logic
4. Register in RAGSystem: `self.tool_manager.register_tool(NewTool())`

Example tool structure:
```python
class NewTool(Tool):
    def get_tool_definition(self) -> Dict[str, Any]:
        return {
            "name": "tool_name",
            "description": "What the tool does",
            "input_schema": {
                "type": "object",
                "properties": {...},
                "required": [...]
            }
        }

    def execute(self, **kwargs) -> str:
        # Tool implementation
        return result_string
```

- do not run the server using ./run.sh i will start it myself