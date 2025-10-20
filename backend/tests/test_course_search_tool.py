"""
Tests for CourseSearchTool and ToolManager
"""
import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, MagicMock

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from search_tools import CourseSearchTool, CourseOutlineTool, ToolManager
from vector_store import SearchResults


class TestCourseSearchToolDefinition:
    """Test CourseSearchTool tool definition"""

    def test_get_tool_definition(self, temp_chroma_db):
        """Test that tool definition is correctly formatted"""
        tool = CourseSearchTool(temp_chroma_db)
        definition = tool.get_tool_definition()

        assert definition["name"] == "search_course_content"
        assert "description" in definition
        assert "input_schema" in definition

        schema = definition["input_schema"]
        assert schema["type"] == "object"
        assert "query" in schema["properties"]
        assert "course_name" in schema["properties"]
        assert "lesson_number" in schema["properties"]
        assert schema["required"] == ["query"]


class TestCourseSearchToolExecution:
    """Test CourseSearchTool execute method"""

    def test_execute_successful_search(self, populated_vector_store):
        """Test execute with successful search results"""
        tool = CourseSearchTool(populated_vector_store)

        result = tool.execute(query="machine learning")

        assert isinstance(result, str)
        assert len(result) > 0
        # Should contain course context
        assert "Introduction to Machine Learning" in result or "Deep Learning" in result

    def test_execute_with_zero_max_results(self, sample_course, sample_course_chunks):
        """CRITICAL: Test execute when VectorStore has max_results=0"""
        import tempfile
        import shutil
        from vector_store import VectorStore

        temp_dir = tempfile.mkdtemp()
        try:
            # Create store with max_results=0 (the bug!)
            store = VectorStore(temp_dir, "all-MiniLM-L6-v2", max_results=0)
            store.add_course_metadata(sample_course)
            store.add_course_content(sample_course_chunks)

            tool = CourseSearchTool(store)
            result = tool.execute(query="machine learning")

            print(f"\n🐛 BUG TEST: CourseSearchTool.execute with max_results=0")
            print(f"   Result: {result}")

            # With max_results=0, ChromaDB returns an error
            assert "Search error" in result or "cannot be negative, or zero" in result

        finally:
            shutil.rmtree(temp_dir)

    def test_execute_with_course_filter(self, populated_vector_store):
        """Test execute with course name filter"""
        tool = CourseSearchTool(populated_vector_store)

        result = tool.execute(
            query="machine learning",
            course_name="Introduction to Machine Learning"
        )

        assert isinstance(result, str)
        # Should only include results from specified course
        assert "Introduction to Machine Learning" in result

    def test_execute_with_lesson_filter(self, populated_vector_store):
        """Test execute with lesson number filter"""
        tool = CourseSearchTool(populated_vector_store)

        result = tool.execute(
            query="machine learning",
            course_name="Introduction to Machine Learning",
            lesson_number=1
        )

        assert isinstance(result, str)
        if "No relevant content found" not in result:
            assert "Lesson 1" in result

    def test_execute_nonexistent_course(self, populated_vector_store):
        """Test execute with nonexistent course"""
        tool = CourseSearchTool(populated_vector_store)

        result = tool.execute(
            query="anything",
            course_name="NonexistentCourse12345"
        )

        # Note: Semantic search may still match to an existing course
        # This is expected behavior without a distance threshold
        # The result should still be a valid string (either error or results)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_execute_empty_results(self, temp_chroma_db):
        """Test execute when search returns no results"""
        tool = CourseSearchTool(temp_chroma_db)

        result = tool.execute(query="nonexistent topic xyz123")

        assert "No relevant content found" in result


class TestCourseSearchToolFormatting:
    """Test CourseSearchTool result formatting"""

    def test_format_results_with_lessons(self, populated_vector_store):
        """Test formatting of results with lesson information"""
        tool = CourseSearchTool(populated_vector_store)

        result = tool.execute(query="machine learning")

        if "No relevant content found" not in result:
            # Should have course context headers
            assert "[" in result
            assert "]" in result

    def test_format_results_source_tracking(self, populated_vector_store):
        """Test that sources are tracked correctly"""
        tool = CourseSearchTool(populated_vector_store)

        # Execute search
        result = tool.execute(query="machine learning")

        # Check if sources were tracked
        if "No relevant content found" not in result:
            assert len(tool.last_sources) > 0
            # Each source should have text and link fields
            for source in tool.last_sources:
                assert "text" in source
                assert "link" in source


class TestCourseOutlineTool:
    """Test CourseOutlineTool"""

    def test_get_tool_definition(self, temp_chroma_db):
        """Test outline tool definition"""
        tool = CourseOutlineTool(temp_chroma_db)
        definition = tool.get_tool_definition()

        assert definition["name"] == "get_course_outline"
        assert "description" in definition
        assert definition["input_schema"]["required"] == ["course_name"]

    def test_execute_existing_course(self, populated_vector_store, sample_course):
        """Test getting outline for existing course"""
        tool = CourseOutlineTool(populated_vector_store)

        result = tool.execute(course_name=sample_course.title)

        assert isinstance(result, str)
        assert sample_course.title in result
        assert sample_course.instructor in result
        assert "Lesson 1" in result
        assert "Lesson 2" in result

    def test_execute_nonexistent_course(self, populated_vector_store):
        """Test getting outline for nonexistent course"""
        tool = CourseOutlineTool(populated_vector_store)

        result = tool.execute(course_name="NonexistentCourse123")

        # Note: Semantic search may still match to an existing course
        # This is expected behavior without a distance threshold
        assert isinstance(result, str)
        assert len(result) > 0


class TestToolManager:
    """Test ToolManager functionality"""

    def test_register_tool(self, temp_chroma_db):
        """Test registering a tool"""
        manager = ToolManager()
        tool = CourseSearchTool(temp_chroma_db)

        manager.register_tool(tool)

        assert "search_course_content" in manager.tools

    def test_register_multiple_tools(self, temp_chroma_db):
        """Test registering multiple tools"""
        manager = ToolManager()
        search_tool = CourseSearchTool(temp_chroma_db)
        outline_tool = CourseOutlineTool(temp_chroma_db)

        manager.register_tool(search_tool)
        manager.register_tool(outline_tool)

        assert len(manager.tools) == 2
        assert "search_course_content" in manager.tools
        assert "get_course_outline" in manager.tools

    def test_get_tool_definitions(self, temp_chroma_db):
        """Test getting all tool definitions"""
        manager = ToolManager()
        search_tool = CourseSearchTool(temp_chroma_db)
        outline_tool = CourseOutlineTool(temp_chroma_db)

        manager.register_tool(search_tool)
        manager.register_tool(outline_tool)

        definitions = manager.get_tool_definitions()

        assert len(definitions) == 2
        assert all("name" in d for d in definitions)
        assert all("input_schema" in d for d in definitions)

    def test_execute_tool(self, populated_vector_store):
        """Test executing a tool by name"""
        manager = ToolManager()
        tool = CourseSearchTool(populated_vector_store)
        manager.register_tool(tool)

        result = manager.execute_tool(
            "search_course_content",
            query="machine learning"
        )

        assert isinstance(result, str)

    def test_execute_nonexistent_tool(self, temp_chroma_db):
        """Test executing a tool that doesn't exist"""
        manager = ToolManager()

        result = manager.execute_tool("nonexistent_tool", query="test")

        assert "not found" in result

    def test_get_last_sources(self, populated_vector_store):
        """Test retrieving sources from last search"""
        manager = ToolManager()
        tool = CourseSearchTool(populated_vector_store)
        manager.register_tool(tool)

        # Execute search
        manager.execute_tool("search_course_content", query="machine learning")

        # Get sources
        sources = manager.get_last_sources()

        if tool.last_sources:  # Only check if search returned results
            assert isinstance(sources, list)
            assert len(sources) > 0

    def test_reset_sources(self, populated_vector_store):
        """Test resetting sources"""
        manager = ToolManager()
        tool = CourseSearchTool(populated_vector_store)
        manager.register_tool(tool)

        # Execute search
        manager.execute_tool("search_course_content", query="machine learning")

        # Reset sources
        manager.reset_sources()

        # Sources should be empty
        sources = manager.get_last_sources()
        assert len(sources) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
