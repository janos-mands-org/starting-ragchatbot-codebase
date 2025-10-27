# RAG Chatbot Test Suite

This directory contains comprehensive tests for the RAG chatbot system.

## Test Structure

- **`conftest.py`** - Shared fixtures and test configuration
- **`test_vector_store.py`** - Tests for ChromaDB vector store operations
- **`test_course_search_tool.py`** - Tests for CourseSearchTool and ToolManager
- **`test_ai_generator.py`** - Tests for AI generation and tool calling
- **`test_rag_system_integration.py`** - End-to-end integration tests

## Running Tests

### Install Dependencies
```bash
# Install pytest and pytest-mock
uv add --dev pytest pytest-mock
```

### Run All Tests
```bash
cd backend
uv run pytest tests/ -v
```

### Run Specific Test File
```bash
uv run pytest tests/test_vector_store.py -v
```

### Run Tests with Output
```bash
uv run pytest tests/ -v -s
```

### Run Specific Test
```bash
uv run pytest tests/test_vector_store.py::TestSearch::test_search_with_zero_max_results -v -s
```

## Critical Tests

The following tests are designed to reveal the **MAX_RESULTS=0 bug**:

1. **`test_vector_store.py::TestSearch::test_search_with_zero_max_results`**
   - Directly tests VectorStore with max_results=0
   - Shows that ChromaDB returns 0 results

2. **`test_course_search_tool.py::TestCourseSearchToolExecution::test_execute_with_zero_max_results`**
   - Tests CourseSearchTool when VectorStore has max_results=0
   - Shows that tool returns "No relevant content found"

3. **`test_ai_generator.py::TestToolCallingBehavior::test_tool_calling_with_zero_max_results`**
   - Tests AI tool calling when max_results=0
   - Shows that AI receives empty results and can't answer

4. **`test_rag_system_integration.py::TestQueryWithProductionConfig::test_query_with_zero_max_results`**
   - End-to-end test with production config
   - Shows complete failure path: Query → Empty search → Failed response

## Test Coverage

### Unit Tests
- VectorStore operations (add, search, filter, metadata)
- CourseSearchTool execute and formatting
- ToolManager registration and execution
- AIGenerator response generation and tool calling

### Integration Tests
- Complete RAG system query flow
- Document loading and processing
- Session management
- Course analytics
- Incremental loading (duplicate prevention)

## Expected Results

With the current **MAX_RESULTS=0 bug** in `config.py`, the following tests will **FAIL or show the bug**:

- ✅ `test_search_with_zero_max_results` - Passes but demonstrates the bug
- ✅ `test_execute_with_zero_max_results` - Passes but shows tool failure
- ✅ `test_tool_calling_with_zero_max_results` - Passes but shows AI can't answer
- ❌ `test_initialization_with_production_config` - **FAILS** due to assertion
- ✅ `test_query_with_zero_max_results` - Passes but demonstrates complete failure

After fixing MAX_RESULTS to 5 (or higher), all tests should pass correctly.

## Debugging

To see detailed output from bug tests:
```bash
uv run pytest tests/test_rag_system_integration.py::TestQueryWithProductionConfig -v -s
```

This will show the complete query flow and failure path.
